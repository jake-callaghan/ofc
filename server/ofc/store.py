"""application service; persistence is supplied through a repository protocol."""

import secrets
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4

from ofc.cpu import choose_move
from ofc.engine import new_game, public_view, transition
from ofc.persistence.ports import GameRecord, Receipt, Repository, State, UnitOfWork
from ofc.rules import RuleError, Rules


class Missing(LookupError):
    pass


class Unauthorized(PermissionError):
    pass


class Conflict(RuleError):
    pass


class Store:
    def __init__(self, repository: Repository):
        self.repository = repository

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
        view["player_names"] = uow.player_names(state["members"])
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

    def command(
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
                    "state": self._view(uow, game_id, state, actor),
                }
            if command["type"] == "join":
                if not secrets.compare_digest(
                    record.invite_hash, self.digest(command.get("invite", ""))
                ):
                    raise Unauthorized("invalid invitation")
            elif actor not in state["members"]:
                raise Unauthorized("not a member")
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
            # finish consecutive CPU turns in the same transaction. a disconnect
            # cannot leave a committed game waiting for a background worker.
            while updated["hand"] and updated["hand"]["status"] == "playing":
                cpu_id = updated["hand"]["queue"][0]["player"]
                if cpu_id not in updated.get("cpu_players", []):
                    break
                move = choose_move(
                    public_view(updated, cpu_id), cpu_id, Rules(**updated["rules"])
                )
                updated = transition(updated, cpu_id, move)
            hand = updated["hand"]
            if (
                hand
                and hand["status"] == "complete"
                and state["hand"]
                and state["hand"]["status"] != "complete"
            ):
                uow.record_hand(game_id, hand, updated["rules"])
            uow.save_game(game_id, updated)
            uow.add_receipt(
                game_id, actor, request_id, Receipt(payload, updated["version"])
            )
            return {
                "applied_version": updated["version"],
                "state": self._view(uow, game_id, updated, actor),
            }

    def history(
        self, game_id: str, actor: str, after: int = 0, limit: int = 50
    ) -> list[State]:
        with self.repository.transaction() as uow:
            record = self._load(uow, game_id)
            public_view(record.state, actor)
            return uow.history(game_id, after, limit)
