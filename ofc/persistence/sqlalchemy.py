"""sql adapter for local sqlite and managed postgres, using short-lived sessions."""

from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from ofc.persistence.models import (
    Base,
    CommandRow,
    GameRow,
    HandRow,
    LedgerRow,
    PlayerRow,
)
from ofc.persistence.ports import GameRecord, Receipt, State


class SQLUnitOfWork:
    def __init__(self, session: Session, *, write: bool):
        self.session = session
        self.write = write

    def add_player(self, player_id: str, name: str, token_hash: str) -> None:
        self.session.add(PlayerRow(id=player_id, name=name, token_hash=token_hash))

    def player_for_token(self, token_hash: str) -> str | None:
        return self.session.scalar(
            select(PlayerRow.id).where(PlayerRow.token_hash == token_hash)
        )

    def player_names(self, players: list[str]) -> dict[str, str]:
        return dict(
            self.session.execute(
                select(PlayerRow.id, PlayerRow.name).where(PlayerRow.id.in_(players))
            ).all()
        )

    def add_game(self, game: GameRecord) -> None:
        self.session.add(
            GameRow(
                id=game.id, invite_hash=game.invite_hash, state=deepcopy(game.state)
            )
        )

    def get_game(self, game_id: str) -> GameRecord | None:
        query = select(GameRow).where(GameRow.id == game_id)
        if self.write:
            query = query.with_for_update()
        row = self.session.scalar(query)
        return GameRecord(row.id, row.invite_hash, deepcopy(row.state)) if row else None

    def save_game(self, game_id: str, state: State) -> None:
        row = self.session.get(GameRow, game_id)
        if row is None:
            raise LookupError("cannot save a missing game")
        row.state = deepcopy(state)

    def receipt(self, game_id: str, actor: str, request_id: str) -> Receipt | None:
        row = self.session.get(CommandRow, (game_id, actor, request_id))
        return Receipt(deepcopy(row.payload), row.version) if row else None

    def add_receipt(
        self, game_id: str, actor: str, request_id: str, receipt: Receipt
    ) -> None:
        self.session.add(
            CommandRow(
                game_id=game_id,
                actor=actor,
                request_id=request_id,
                payload=deepcopy(receipt.payload),
                version=receipt.version,
            )
        )

    def record_hand(self, game_id: str, hand: State, rules: State) -> None:
        self.session.add(
            HandRow(
                game_id=game_id,
                number=hand["number"],
                result=deepcopy(hand["result"]),
                boards=deepcopy(hand["boards"]),
                rules=deepcopy(rules),
            )
        )
        # insert the parent before its ledger entries; all stay in one transaction.
        self.session.flush()
        self.session.add_all(
            [
                LedgerRow(game_id=game_id, hand=hand["number"], player=p, units=n)
                for p, n in hand["result"]["units"].items()
            ]
        )

    def balances(self, game_id: str) -> dict[str, int]:
        return dict(
            self.session.execute(
                select(LedgerRow.player, func.sum(LedgerRow.units))
                .where(LedgerRow.game_id == game_id)
                .group_by(LedgerRow.player)
            ).all()
        )

    def history(self, game_id: str, after: int, limit: int) -> list[State]:
        rows = self.session.scalars(
            select(HandRow)
            .where(HandRow.game_id == game_id, HandRow.number > after)
            .order_by(HandRow.number)
            .limit(limit)
        )
        return [
            deepcopy(
                {
                    "number": r.number,
                    "result": r.result,
                    "boards": r.boards,
                    "rules": r.rules,
                }
            )
            for r in rows
        ]


class SQLAlchemyRepository:
    def __init__(self, database_url: str):
        url = make_url(database_url)
        dialect = url.get_backend_name()
        if dialect not in {"sqlite", "postgresql"}:
            raise ValueError("supported sql adapters are sqlite and postgresql")
        self.sqlite = dialect == "sqlite"
        if self.sqlite:
            if not url.database or url.database == ":memory:":
                raise ValueError("use a sqlite file for durable concurrent games")
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False, "timeout": 10}
            if self.sqlite
            else {},
        )
        if self.sqlite:

            @event.listens_for(self.engine, "connect")
            def sqlite_connect(connection, record):
                connection.isolation_level = None
                connection.execute("PRAGMA foreign_keys=ON")

            @event.listens_for(self.engine, "begin")
            def sqlite_begin(connection):
                immediate = connection.get_execution_options().get("ofc_write", False)
                connection.exec_driver_sql("BEGIN IMMEDIATE" if immediate else "BEGIN")

    def create_schema(self) -> None:
        """bootstrap an empty development/test database; deployments use alembic."""
        Base.metadata.create_all(self.engine)

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[SQLUnitOfWork]:
        with self.engine.connect() as connection:
            if self.sqlite:
                connection = connection.execution_options(ofc_write=write)
            elif not write:
                # state and ledger must come from the same committed snapshot.
                connection = connection.execution_options(
                    isolation_level="REPEATABLE READ"
                )
            # postgres writes use read committed plus a game row lock. a waiting
            # writer then sees the preceding commit before checking its version.
            with connection.begin(), Session(bind=connection) as session:
                yield SQLUnitOfWork(session, write=write)
                session.flush()

    def close(self) -> None:
        self.engine.dispose()
