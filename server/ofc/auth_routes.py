"""same-origin login endpoints; browsers receive only opaque, http-only cookies."""

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from ofc.auth_provider import AuthError

SESSION_COOKIE = "ofc_session"
FLOW_COOKIE = "ofc_auth_flow"


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(
        min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    password: str = Field(min_length=1, max_length=256)


class SignupInput(LoginInput):
    password: str = Field(min_length=12, max_length=256)
    name: str = Field(min_length=1, max_length=80, pattern=r".*\S.*")


class EmailInput(BaseModel):
    email: str = Field(
        min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )


class PasswordInput(BaseModel):
    password: str = Field(min_length=12, max_length=256)


class GoogleInput(BaseModel):
    link: bool = False


def service(request):
    auth = request.app.state.auth
    if auth is None:
        raise AuthError("Login is not configured yet.", 503)
    return auth


def cookie(response, auth, name, value, age):
    response.set_cookie(
        name,
        value,
        max_age=age,
        secure=auth.settings.secure,
        httponly=True,
        samesite="lax",
        path="/",
    )


def router():
    routes = APIRouter(prefix="/auth")

    @routes.get("/config")
    def config(request: Request):
        return {
            "enabled": request.app.state.auth is not None,
            "legacy": request.app.state.allow_legacy_keys,
        }

    @routes.get("/session")
    def session(request: Request):
        auth = service(request)
        profile, _ = auth.session(
            request.cookies.get(SESSION_COOKIE), allow_recovery=True
        )
        return profile

    @routes.post("/login")
    def login(body: LoginInput, request: Request, response: Response):
        auth = service(request)
        tokens = auth.provider.token(
            "password", email=body.email.strip(), password=body.password
        )
        token, profile = auth.login(
            tokens, old_token=request.cookies.get(SESSION_COOKIE)
        )
        cookie(response, auth, SESSION_COOKIE, token, auth.settings.session_seconds)
        return profile

    @routes.post("/signup")
    def signup(body: SignupInput, request: Request, response: Response):
        auth = service(request)
        flow, challenge = auth.flow("signup")
        try:
            auth.provider.request(
                "POST",
                "/signup",
                params={"redirect_to": auth.settings.callback},
                data={
                    "email": body.email.strip(),
                    "password": body.password,
                    "data": {"name": body.name.strip()},
                    "code_challenge": challenge,
                    "code_challenge_method": "s256",
                },
            )
        except AuthError as error:
            if error.status != 401:
                raise
        cookie(response, auth, FLOW_COOKIE, flow, 3600)
        return {
            "message": "Check your email to confirm your account. Open the link in this browser. If you already have an account, sign in or reset your password."
        }

    @routes.post("/recover")
    def recover(body: EmailInput, request: Request, response: Response):
        auth = service(request)
        flow, challenge = auth.flow("recovery")
        auth.provider.request(
            "POST",
            "/recover",
            params={"redirect_to": auth.settings.callback},
            data={
                "email": body.email.strip(),
                "code_challenge": challenge,
                "code_challenge_method": "s256",
            },
        )
        cookie(response, auth, FLOW_COOKIE, flow, 3600)
        return {
            "message": "If that email has an account, a reset link is on its way. Open it in this browser."
        }

    @routes.post("/google")
    def google(body: GoogleInput, request: Request, response: Response):
        auth = service(request)
        player, access = None, None
        if body.link:
            profile, access = auth.session(
                request.cookies.get(SESSION_COOKIE), recent=True
            )
            player = profile["player_id"]
        flow, challenge = auth.flow("link" if body.link else "google", player)
        url = auth.provider.google_url(challenge, access)
        cookie(response, auth, FLOW_COOKIE, flow, 3600)
        return {"url": url}

    @routes.get("/callback")
    def callback(request: Request, code: str = ""):
        auth = service(request)
        try:
            token, profile = auth.callback(
                request.cookies.get(FLOW_COOKIE),
                code,
                request.cookies.get(SESSION_COOKIE),
            )
        except AuthError:
            response = RedirectResponse(
                auth.settings.origin + "/?auth_error=callback", status_code=303
            )
        else:
            response = RedirectResponse(
                auth.settings.origin
                + ("/?auth=recovery" if profile["recovery"] else "/?auth=success"),
                status_code=303,
            )
            cookie(
                response,
                auth,
                SESSION_COOKIE,
                token,
                900 if profile["recovery"] else auth.settings.session_seconds,
            )
        response.delete_cookie(FLOW_COOKIE, path="/")
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @routes.post("/password")
    def password(body: PasswordInput, request: Request, response: Response):
        auth = service(request)
        auth.password(request.cookies.get(SESSION_COOKIE), body.password)
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"message": "Password saved. Sign in with your email and new password."}

    @routes.post("/logout")
    def logout(request: Request, response: Response):
        auth = service(request)
        auth.logout(request.cookies.get(SESSION_COOKIE))
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"ok": True}

    return routes
