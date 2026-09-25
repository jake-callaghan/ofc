"""same-origin login endpoints; browsers receive only opaque, http-only cookies."""

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ofc.auth_provider import AuthError

SESSION_COOKIE = "ofc_session"


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(
        min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    password: str = Field(min_length=1, max_length=256)


class SignupInput(LoginInput):
    password: str = Field(min_length=12, max_length=256)
    name: str = Field(min_length=1, max_length=80, pattern=r".*\S.*")


class PasswordInput(BaseModel):
    password: str = Field(min_length=12, max_length=256)


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
            "dev_login": request.app.state.dev_login,
        }

    @routes.get("/session")
    def session(request: Request):
        auth = service(request)
        profile, _ = auth.session(
            request.cookies.get(SESSION_COOKIE)
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
        tokens = auth.provider.request(
            "POST",
            "/signup",
            data={
                "email": body.email.strip(),
                "password": body.password,
                "data": {"name": body.name.strip()},
            },
        )
        if not tokens.get("access_token") or not tokens.get("refresh_token"):
            raise AuthError(
                "Signup is not configured for immediate login. Please contact the administrator.",
                503,
            )
        token, profile = auth.login(
            tokens, old_token=request.cookies.get(SESSION_COOKIE)
        )
        cookie(response, auth, SESSION_COOKIE, token, auth.settings.session_seconds)
        return profile

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
