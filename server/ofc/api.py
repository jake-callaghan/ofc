"""http commands and authenticated websocket snapshots for a react client."""

import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from threading import Lock
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from ofc.auth_provider import AuthError, AuthSettings, SupabaseAuth
from ofc.auth_routes import SESSION_COOKIE
from ofc.auth_routes import router as auth_router
from ofc.auth_service import AuthService
from ofc.bootstrap import build_repository
from ofc.game_updates import GameUpdates
from ofc.persistence.ports import Repository
from ofc.rules import RuleError, Rules
from ofc.store import Conflict, Missing, Store, Unauthorized


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PlayerInput(Model):
    name: str = Field(min_length=1, max_length=80)


class RuleInput(Model):
    variant: Literal["classic", "pineapple"] = "pineapple"
    fantasyland: Literal["off", "standard", "progressive"] = "progressive"
    moon: bool = False
    candyland: bool = False
    turn_seconds: int | None = Field(default=None, ge=10, le=300)
    orbits: int | None = Field(default=None, ge=1, le=100)


class GameInput(Model):
    name: str = Field(min_length=1, max_length=120)
    rules: RuleInput = Field(default_factory=RuleInput)


class Join(Model):
    type: Literal["join"]
    invite: str = Field(min_length=1, max_length=128)


class JoinInput(Model):
    invite: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)


class Start(Model):
    type: Literal["start"]
    players: list[str] = Field(min_length=2, max_length=4)


class AddCPU(Model):
    type: Literal["add_cpu"]


class Leave(Model):
    type: Literal["leave"]


class UpdateSettings(Model):
    type: Literal["update_settings"]
    turn_seconds: int | None = Field(ge=10, le=300)
    orbits: int | None = Field(ge=1, le=100)


class Place(Model):
    type: Literal["place"]
    placements: dict[Literal["top", "middle", "bottom"], list[str]]
    discards: list[str] = Field(default_factory=list, max_length=4)


class CommandInput(Model):
    request_id: str = Field(min_length=1, max_length=128)
    version: int = Field(ge=0)
    command: Annotated[
        Join | Start | Place | AddCPU | Leave | UpdateSettings,
        Field(discriminator="type"),
    ]


class ChatMessage(Model):
    request_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=1000)


class ChatReaction(Model):
    emoji: Literal["👍", "❤️", "😂", "🎉", "😮", "🐟"]
    active: bool


def create_app(
    database_url: str | None = None,
    *,
    repository: Repository | None = None,
    auth_provider=None,
    allow_legacy_keys: bool | None = None,
):
    if allow_legacy_keys is None:
        allow_legacy_keys = os.environ.get("OFC_ALLOW_LEGACY_KEYS") == "1"

    @asynccontextmanager
    async def lifespan(app):
        adapter = (
            repository if repository is not None else build_repository(database_url)
        )
        app.state.store = Store(adapter)
        app.state.updates = GameUpdates(app.state.store)
        settings = auth_provider.settings if auth_provider else AuthSettings.load()
        provider = auth_provider or (SupabaseAuth(settings) if settings else None)
        app.state.auth = AuthService(adapter, provider) if provider else None
        app.state.allow_legacy_keys = allow_legacy_keys and provider is None

        stopped = asyncio.Event()

        async def timers():
            while not stopped.is_set():
                try:
                    await run_in_threadpool(app.state.store.process_timeouts)
                except Exception:
                    logging.getLogger(__name__).exception("turn timer scan failed")
                try:
                    await asyncio.wait_for(stopped.wait(), timeout=0.5)
                except TimeoutError:
                    pass

        timer_task = asyncio.create_task(timers())
        try:
            yield
        finally:
            stopped.set()
            await timer_task
            if provider and auth_provider is None:
                provider.close()
            if repository is None:
                adapter.close()

    app = FastAPI(title="OFC backend", version="0.1.0", lifespan=lifespan)
    bearer = HTTPBearer(auto_error=False)
    app.include_router(auth_router())
    attempts = defaultdict(deque)
    attempt_lock = Lock()

    @app.middleware("http")
    async def auth_boundary(request, call_next):
        path = request.scope["path"].removeprefix(request.scope.get("root_path", ""))
        auth_path = path.startswith("/auth/")
        guarded = auth_path or bool(request.cookies.get(SESSION_COOKIE))
        if request.method not in {"GET", "HEAD", "OPTIONS"} and guarded:
            auth = request.app.state.auth
            if auth and (
                request.headers.get("origin") != auth.settings.origin
                or request.headers.get("x-ofc-request") != "1"
            ):
                return JSONResponse(
                    {"detail": "Request origin rejected."}, status_code=403
                )
            if auth_path:
                now = time.monotonic()
                address = request.client.host if request.client else "unknown"
                with attempt_lock:
                    for key in list(attempts):
                        while attempts[key] and attempts[key][0] < now - 60:
                            attempts[key].popleft()
                        if not attempts[key]:
                            del attempts[key]
                    if len(attempts) >= 10000 or len(attempts[address]) >= 30:
                        return JSONResponse(
                            {"detail": "Too many attempts. Try again shortly."},
                            status_code=429,
                        )
                    attempts[address].append(now)
        response = await call_next(request)
        if auth_path:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(AuthError)
    async def auth_error(request, error):
        return JSONResponse(
            {"detail": str(error)},
            status_code=error.status,
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse(
            {
                "detail": [
                    {"loc": e["loc"], "msg": e["msg"], "type": e["type"]}
                    for e in error.errors()
                ]
            },
            status_code=422,
        )

    def store():
        return app.state.store

    def player(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ):
        token = request.cookies.get(SESSION_COOKIE)
        if token and app.state.auth:
            profile, _ = app.state.auth.session(token)
            return profile["player_id"]
        if app.state.allow_legacy_keys and credentials:
            return store().authenticate(credentials.credentials)
        raise AuthError("Please sign in.", 401)

    @app.exception_handler(RuleError)
    async def rule_error(request, exc):
        return JSONResponse(
            status_code=409 if isinstance(exc, Conflict) else 422,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Unauthorized)
    async def unauthorized(request, exc):
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(Missing)
    async def missing(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/players", status_code=201)
    def register(body: PlayerInput):
        if not app.state.allow_legacy_keys:
            raise AuthError("Player keys have been replaced by account login.", 410)
        return store().register(body.name)

    @app.post("/games", status_code=201)
    def create_game(body: GameInput, actor: Annotated[str, Depends(player)]):
        return store().create(actor, body.name, Rules(**body.rules.model_dump()))

    @app.post("/games/{game_id}/join")
    def join_game(
        game_id: str, body: JoinInput, actor: Annotated[str, Depends(player)]
    ):
        return store().join(game_id, actor, body.request_id, body.invite)

    @app.get("/games/{game_id}")
    def game(game_id: str, actor: Annotated[str, Depends(player)]):
        return store().get(game_id, actor)

    @app.post("/games/{game_id}/commands")
    def command(
        game_id: str, body: CommandInput, actor: Annotated[str, Depends(player)]
    ):
        return store().command(
            game_id, actor, body.request_id, body.version, body.command.model_dump()
        )

    @app.get("/games/{game_id}/hands")
    def history(
        game_id: str,
        actor: Annotated[str, Depends(player)],
        after: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ):
        return store().history(game_id, actor, after, limit)

    @app.post("/games/{game_id}/chat")
    def chat_message(
        game_id: str, body: ChatMessage, actor: Annotated[str, Depends(player)]
    ):
        return store().chat_message(game_id, actor, body.request_id, body.text)

    @app.post("/games/{game_id}/chat/{message_id}/reactions")
    def chat_reaction(
        game_id: str,
        message_id: str,
        body: ChatReaction,
        actor: Annotated[str, Depends(player)],
    ):
        return store().chat_reaction(
            game_id, actor, message_id, body.emoji, body.active
        )

    @app.websocket("/games/{game_id}/events")
    async def events(websocket: WebSocket, game_id: str):
        await websocket.accept()
        try:
            cookie_token = websocket.cookies.get(SESSION_COOKIE)
            if app.state.auth and cookie_token:
                if websocket.headers.get("origin") != app.state.auth.settings.origin:
                    raise Unauthorized("origin rejected")
                profile, _ = await run_in_threadpool(
                    app.state.auth.session, cookie_token
                )
                actor = profile["player_id"]
            elif app.state.allow_legacy_keys:
                auth = await asyncio.wait_for(websocket.receive_json(), timeout=10)
                if not isinstance(auth, dict) or not isinstance(auth.get("token"), str):
                    raise Unauthorized("token required")
                actor = await run_in_threadpool(store().authenticate, auth["token"])
            else:
                raise Unauthorized("sign in required")
            async with app.state.updates.subscribe(game_id) as entry:
                checked_at = time.monotonic()
                version = -1
                while True:
                    if cookie_token and time.monotonic() - checked_at >= 5:
                        await run_in_threadpool(app.state.auth.session, cookie_token)
                        checked_at = time.monotonic()
                    snapshot = await app.state.updates.get(game_id, entry, actor)
                    revision = (snapshot["version"], snapshot.get("chat_version", 0))
                    if revision != version:
                        await websocket.send_json(
                            {
                                "type": "snapshot",
                                "state": snapshot,
                                "server_time": time.time(),
                            }
                        )
                        version = revision
                    # a timed receive detects disconnects even when a game is idle.
                    try:
                        await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                    except TimeoutError:
                        pass
        except (TimeoutError, Unauthorized, RuleError, Missing, ValueError, AuthError):
            await websocket.close(code=1008)
        except WebSocketDisconnect:
            pass

    return app


app = create_app()
