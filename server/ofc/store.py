"""application service; persistence is supplied through a repository protocol."""

import logging
import secrets
import time
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4

from ofc.bootstrap import build_cpu
from ofc.engine import new_game, public_view, transition
from ofc.persistence.ports import GameRecord, Receipt, Repository, State, UnitOfWork
from ofc.rules import RuleError, Rules
from ofc.timing import expired, random_move, set_deadline


class Missing(LookupError):
    pass


class Unauthorized(PermissionError):
    pass


class Conflict(RuleError):
    pass


class Store:
    def __init__(self, repository: Repository, *, clock=time.time, cpu=None):
        self.repository = repository
        self.clock = clock
        self.cpu = cpu if cpu is not None else build_cpu()

    def register(self, name: str) -> State:
        if not name.strip():
            raise RuleError("name cannot be empty")
        player, token = str(uuid4()), secrets.token_urlsafe(32)
        with self.repository.transaction(write=True) as uow:
            uow.add_player(player, name.strip(), self.digest(token))
        return {"player_id": player, "token": token, "name": name.strip()}

    @staticmethod
    def digest(token: str) -> str:
        return sha256(token.encode()).hexdigest()

    def authenticate(self, token: str) -> str:
        with self.repository.transaction() as uow:
            player = uow.player_for_token(self.digest(token))
        if player is None:
            raise Unauthorized("invalid player token")
        return player

    def create(self, actor: str, name: str, rules: Rules) -> State:
        game_id, invite = str(uuid4()), secrets.token_urlsafe(24)
        state = new_game(actor, name, rules)
        with self.repository.transaction(write=True) as uow:
            uow.add_game(GameRecord(game_id, self.digest(invite), state))
            view = self._view(uow, game_id, state, actor)
        return {"game_id": game_id, "invite": invite, "state": view}

    def _load(self, uow: UnitOfWork, game_id: str) -> GameRecord:
        record = uow.get_game(game_id)
        if record is None:
            raise Missing("game not found")
        return record

    def _view(self, uow: UnitOfWork, game_id: str, state: State, actor: str) -> State:
        view = public_view(state, actor)
        view["game_id"] = game_id
        view["balances"] = dict.fromkeys(state["members"], 0) | uow.balances(game_id)
        view["player_names"] = uow.player_names(
            list(set(state["members"]) | set(view["balances"]))
        )
        return view

    def get(self, game_id: str, actor: str) -> State:
        with self.repository.transaction() as uow:
            record = self._load(uow, game_id)
            return self._view(uow, game_id, record.state, actor)

    def join(self, game_id: str, actor: str, request_id: str, invite: str) -> State:
        # invitation holders cannot read the table version until they are members.
        return self.command(
            game_id, actor, request_id, None, {"type": "join", "invite": invite}
        )

    def command(self, game_id, actor, request_id, version, command):
        result = self._command(game_id, actor, request_id, version, command)
        # raise after commit so rejecting a late command cannot roll back the timeout.
        if result is None:
            raise Conflict("turn expired; a random placement was submitted")
        return result

    def _command(
        self, game_id: str, actor: str, request_id: str, version: int, command: State
    ) -> State:
        payload = dict(command)
        if payload.get("type") == "join":
            payload["invite"] = self.digest(payload.get("invite", ""))
        with self.repository.transaction(write=True) as uow:
            record = self._load(uow, game_id)
            state = record.state
            previous = uow.receipt(game_id, actor, request_id)
            if previous:
                if previous.payload != payload:
                    raise Conflict("request id reused with a different command")
                return {
                    "applied_version": previous.version,
                    "state": None
                    if payload["type"] == "leave"
                    else self._view(uow, game_id, state, actor),
                }
            if command["type"] == "join":
                if not secrets.compare_digest(
                    record.invite_hash, self.digest(command.get("invite", ""))
                ):
                    raise Unauthorized("invalid invitation")
            elif actor not in state["members"]:
                raise Unauthorized("not a member")
            if self._expire_locked(uow, game_id, state):
                return None
            if command["type"] == "join" and actor in state["members"]:
                return {
                    "applied_version": state["version"],
                    "state": self._view(uow, game_id, state, actor),
                }
            if version is None and command["type"] != "join":
                raise RuleError("a version is required for game commands")
            if version is not None and state["version"] != version:
                raise Conflict("stale version; fetch the latest game")
            if command["type"] == "add_cpu":
                rules = Rules(**state["rules"])
                if actor != state["owner"]:
                    raise Unauthorized("only the owner may add CPU players")
                if state["hand"] and state["hand"]["status"] == "playing":
                    raise RuleError("add CPU players between hands")
                if len(state.get("cpu_players", [])) >= rules.capacity - 1:
                    raise RuleError("CPU seat limit reached")
                updated = deepcopy(state)
                cpu_id = str(uuid4())
                cpus = updated.setdefault("cpu_players", [])
                uow.add_player(
                    cpu_id,
                    f"CPU {len(cpus) + 1}",
                    self.digest(secrets.token_urlsafe(32)),
                )
                cpus.append(cpu_id)
                updated["members"].append(cpu_id)
                updated["version"] += 1
            else:
                if command["type"] == "start" and all(
                    p in state.get("cpu_players", []) for p in command["players"]
                ):
                    raise RuleError("select at least one human player")
                updated = transition(state, actor, command)
            if command["type"] in {"start", "place"}:
                updated = self._finish_turns(updated)
            self._save(uow, game_id, state, updated)
            uow.add_receipt(
                game_id, actor, request_id, Receipt(payload, updated["version"])
            )
            return {
                "applied_version": updated["version"],
                "state": None
                if command["type"] == "leave"
                else self._view(uow, game_id, updated, actor),
            }

    def _finish_turns(self, state):
        # cpu moves and the next human deadline commit together.
        while state["hand"] and state["hand"]["status"] == "playing":
            player = state["hand"]["queue"][0]["player"]
            if player not in state.get("cpu_players", []):
                break
            move = self.cpu(public_view(state, player), player, Rules(**state["rules"]))
            state = transition(state, player, move)
        set_deadline(state, self.clock())
        return state

    @staticmethod
    def _save(uow, game_id, previous, updated):
        hand = updated["hand"]
        if (
            hand
            and hand["status"] == "complete"
            and previous["hand"]
            and previous["hand"]["status"] != "complete"
        ):
            uow.record_hand(game_id, hand, updated["rules"])
        uow.save_game(game_id, updated)

    def _expire_locked(self, uow, game_id, state):
        if not expired(state, self.clock()):
            return False
        player = state["hand"]["queue"][0]["player"]
        updated = transition(state, player, random_move(state))
        updated["hand"]["last_timeout"] = {
            "player": player,
            "version": updated["version"],
        }
        updated = self._finish_turns(updated)
        self._save(uow, game_id, state, updated)
        return True

    def expire_turn(self, game_id):
        with self.repository.transaction(write=True) as uow:
            state = self._load(uow, game_id).state
            return self._expire_locked(uow, game_id, state)

    def process_timeouts(self):
        # deadlines are persisted, so this also recovers turns after a restart.
        with self.repository.transaction() as uow:
            game_ids = uow.due_game_ids(self.clock())
        for game_id in game_ids:
            try:
                self.expire_turn(game_id)
            except Exception:
                logging.getLogger(__name__).exception(
                    "turn timeout failed for %s", game_id
                )

    def history(
        self, game_id: str, actor: str, after: int = 0, limit: int = 50
    ) -> list[State]:
        with self.repository.transaction() as uow:
            record = self._load(uow, game_id)
            public_view(record.state, actor)
            return uow.history(game_id, after, limit)

    def chat_message(self, game_id, actor, request_id, text):
        text = text.strip()
        if not text or len(text) > 1000:
            raise RuleError("messages must contain 1-1000 characters")
        payload = {"type": "chat_message", "text": text}
        with self.repository.transaction(write=True) as uow:
            state = self._load(uow, game_id).state
            if actor not in state["members"]:
                raise Unauthorized("not a member")
            previous = uow.receipt(game_id, actor, request_id)
            if previous:
                if previous.payload != payload:
                    raise Conflict("request id reused with a different message")
                return {"ok": True}
            messages = state.setdefault("chat", [])
            messages.append(
                {
                    "id": str(uuid4()),
                    "player": actor,
                    "name": uow.player_names([actor])[actor],
                    "text": text,
                    "created_at": self.clock(),
                    "reactions": {},
                }
            )
            state["chat"] = messages[-100:]
            state["chat_version"] = state.get("chat_version", 0) + 1
            uow.save_game(game_id, state)
            uow.add_receipt(
                game_id, actor, request_id, Receipt(payload, state["version"])
            )
        return {"ok": True}

    def chat_reaction(self, game_id, actor, message_id, emoji, active):
        if emoji not in {"👍", "❤️", "😂", "🎉", "😮", "🐟"} or type(active) is not bool:
            raise RuleError("invalid reaction")
        with self.repository.transaction(write=True) as uow:
            state = self._load(uow, game_id).state
            if actor not in state["members"]:
                raise Unauthorized("not a member")
            message = next(
                (m for m in state.get("chat", []) if m["id"] == message_id), None
            )
            if message is None:
                raise Missing("message no longer available")
            players = message["reactions"].get(emoji, [])
            if active == (actor in players):
                return {"ok": True}
            if active:
                message["reactions"][emoji] = [*players, actor]
            else:
                message["reactions"][emoji] = [p for p in players if p != actor]
            state["chat_version"] = state.get("chat_version", 0) + 1
            uow.save_game(game_id, state)
        return {"ok": True}
