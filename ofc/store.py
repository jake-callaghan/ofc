"""application service; persistence is supplied through a repository protocol."""

import secrets
from hashlib import sha256
from uuid import uuid4

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
            if state["version"] != version:
                raise Conflict("stale version; fetch the latest game")
            updated = transition(state, actor, command)
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
