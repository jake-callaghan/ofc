"""http commands and authenticated websocket snapshots for a react client."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from ofc.bootstrap import build_repository
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


def create_app(
    database_url: str | None = None, *, repository: Repository | None = None
):
    @asynccontextmanager
    async def lifespan(app):
        adapter = (
            repository if repository is not None else build_repository(database_url)
        )
        app.state.store = Store(adapter)
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
            if repository is None:
                adapter.close()

    app = FastAPI(title="OFC backend", version="0.1.0", lifespan=lifespan)
    bearer = HTTPBearer()

    def store():
        return app.state.store

    def player(credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]):
        return store().authenticate(credentials.credentials)

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

    @app.websocket("/games/{game_id}/events")
    async def events(websocket: WebSocket, game_id: str):
        await websocket.accept()
        try:
            # the first frame carries the token, keeping credentials out of urls.
            auth = await asyncio.wait_for(websocket.receive_json(), timeout=10)
            if not isinstance(auth, dict) or not isinstance(auth.get("token"), str):
                raise Unauthorized("token required")
            actor = await run_in_threadpool(store().authenticate, auth["token"])
            version = -1
            while True:
                snapshot = await run_in_threadpool(store().get, game_id, actor)
                if snapshot["version"] != version:
                    await websocket.send_json(
                        {
                            "type": "snapshot",
                            "state": snapshot,
                            "server_time": time.time(),
                        }
                    )
                    version = snapshot["version"]
                # a timed receive detects disconnects even when a game is idle.
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                except TimeoutError:
                    pass
        except (TimeoutError, Unauthorized, RuleError, Missing, ValueError):
            await websocket.close(code=1008)
        except WebSocketDisconnect:
            pass

    return app


app = create_app()
