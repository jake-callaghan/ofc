"""the transactional contract every database or cloud adapter must satisfy."""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol

State = dict[str, Any]


@dataclass(frozen=True)
class GameRecord:
    id: str
    invite_hash: str
    state: State


@dataclass(frozen=True)
class Receipt:
    payload: State
    version: int


class UnitOfWork(Protocol):
    """one atomic operation, with consistent reads and serialised game writes.

    get_game in a write transaction must lock the game until commit/rollback,
    or provide equivalent conditional-write conflict detection. returned values
    must be detached: mutating a result must not mutate committed storage.
    """

    def add_player(self, player_id: str, name: str, token_hash: str) -> None: ...
    def player_for_token(self, token_hash: str) -> str | None: ...
    def player_names(self, players: list[str]) -> dict[str, str]: ...
    def add_game(self, game: GameRecord) -> None: ...
    def get_game(self, game_id: str) -> GameRecord | None: ...
    def save_game(self, game_id: str, state: State) -> None: ...
    def due_game_ids(self, now: float) -> list[str]:
        """find expired deadlines; callers must lock and recheck before writing."""
        ...

    def receipt(self, game_id: str, actor: str, request_id: str) -> Receipt | None: ...
    def add_receipt(
        self, game_id: str, actor: str, request_id: str, receipt: Receipt
    ) -> None: ...
    def record_hand(self, game_id: str, hand: State, rules: State) -> None: ...
    def balances(self, game_id: str) -> dict[str, int]: ...
    def history(self, game_id: str, after: int, limit: int) -> list[State]: ...


class Repository(Protocol):
    """commit on success and roll back all writes on any exception.

    read transactions must return a consistent snapshot across state, results,
    and ledger reads. adapters must enforce unique command receipts and unique
    ledger entries per game/hand/player. remote calls need equivalent guarantees.
    """

    def transaction(
        self, *, write: bool = False
    ) -> AbstractContextManager[UnitOfWork]: ...
    def close(self) -> None: ...
