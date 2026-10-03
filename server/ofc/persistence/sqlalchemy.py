"""sql adapter for local sqlite and managed postgres, using short-lived sessions."""

from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy

from sqlalchemy import event, func, or_, select
from sqlalchemy.orm import Session

from ofc.database import connection_url, create_database_engine
from ofc.persistence.models import (
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
        self.games = {}
        self.balance_cache = {}

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
        if row is not None:
            self.games[game_id] = row
        return GameRecord(row.id, row.invite_hash, deepcopy(row.state)) if row else None

    def save_game(self, game_id: str, state: State) -> None:
        row = self.games.get(game_id)
        if row is None:
            row = self.session.get(GameRow, game_id)
        if row is None:
            raise LookupError("cannot save a missing game")
        row.state = deepcopy(state)

    def lobby_games(self):
        state = GameRow.state
        rows = self.session.execute(
            select(
                GameRow.id,
                state["name"].as_string(),
                state["visibility"].as_string(),
                state["members"],
                state["rules"]["variant"].as_string(),
                state["hand"]["status"].as_string(),
                state["hand_number"].as_integer(),
                state["unit_pence"].as_integer(),
                state["leaderboard_enabled"].as_boolean(),
            )
            .where(
                state["status"].as_string() == "active",
                state["owner"].as_string().is_not(None),
            )
            .order_by(GameRow.id)
        )
        return [
            {
                "id": gid,
                "name": name,
                "visibility": visibility or "private",
                "members": members,
                "variant": variant,
                "phase": "playing" if hand_status == "playing" else "between_hands",
                "hand_number": number,
                "unit_pence": unit_pence if unit_pence is not None else 10,
                "leaderboard_enabled": enabled if enabled is not None else True,
            }
            for gid, name, visibility, members, variant, hand_status, number, unit_pence, enabled in rows
        ]

    def due_game_ids(self, now: float) -> list[str]:
        return list(
            self.session.scalars(
                select(GameRow.id).where(
                    GameRow.state["hand"]["deadline"].as_float() <= now
                )
            )
        )

    def receipt(self, game_id: str, actor: str, request_id: str) -> Receipt | None:
        row = self.session.get(CommandRow, (game_id, actor, request_id))
        return Receipt(deepcopy(row.payload), row.version) if row else None

    def inactive_game_ids(self, cutoff: float, limit: int = 500) -> list[str]:
        state = GameRow.state
        updated = state["updated_at"].as_float()
        phase = state["hand"]["status"].as_string()
        return list(
            self.session.scalars(
                select(GameRow.id)
                .where(
                    state["status"].as_string().in_(["active", "complete"]),
                    or_(phase.is_(None), phase != "playing"),
                    or_(updated.is_(None), updated <= cutoff),
                )
                .order_by(updated, GameRow.id)
                .limit(limit)
            )
        )

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
        self.balance_cache.pop(game_id, None)
        accounting = hand.get("accounting")
        if accounting:
            accounting = {
                **accounting,
                "cpu_involved": bool(
                    accounting.get("cpu_involved")
                    or set(hand["result"]["units"]) & set(hand.get("cpu_players", []))
                ),
            }
        self.session.add(
            HandRow(
                game_id=game_id,
                number=hand["number"],
                result=deepcopy(hand["result"]),
                boards=deepcopy(hand["boards"]),
                rules=deepcopy(rules),
                accounting=deepcopy(accounting),
            )
        )
        # insert the parent before its ledger entries; all stay in one transaction.
        self.session.flush()
        self.session.add_all(
            [
                LedgerRow(
                    game_id=game_id,
                    hand=hand["number"],
                    player=p,
                    units=n,
                    amount_pence=n * accounting["unit_pence"] if accounting else None,
                    leaderboard_pence=(
                        n * accounting["unit_pence"]
                        if accounting
                        and accounting["leaderboard_enabled"]
                        and not accounting["cpu_involved"]
                        else None
                    ),
                )
                for p, n in hand["result"]["units"].items()
            ]
        )

    def balances(self, game_id: str) -> dict[str, int]:
        # postgres sum(bigint) returns decimal; ledger units are exact integers.
        return {player: int(units) for player, units, _ in self._ledger_totals(game_id)}

    def _ledger_totals(self, game_id):
        # both currencies share one aggregate within this transaction.
        if game_id not in self.balance_cache:
            self.balance_cache[game_id] = self.session.execute(
                select(
                    LedgerRow.player,
                    func.sum(LedgerRow.units),
                    func.sum(LedgerRow.amount_pence),
                )
                .where(LedgerRow.game_id == game_id)
                .group_by(LedgerRow.player)
            ).all()
        return self.balance_cache[game_id]

    def history(
        self,
        game_id: str,
        after: int,
        limit: int,
        *,
        newest: bool = False,
        before: int | None = None,
    ) -> list[State]:
        query = select(HandRow).where(
            HandRow.game_id == game_id, HandRow.number > after
        )
        if before is not None:
            query = query.where(HandRow.number < before)
        rows = self.session.scalars(
            query.order_by(HandRow.number.desc() if newest else HandRow.number).limit(
                limit
            )
        )
        return [
            deepcopy(
                {
                    "number": r.number,
                    "result": r.result,
                    "boards": r.boards,
                    "rules": r.rules,
                    "accounting": r.accounting,
                }
            )
            for r in rows
        ]

    def gbp_balances(self, game_id: str) -> dict[str, int]:
        return {
            player: int(pence)
            for player, _, pence in self._ledger_totals(game_id)
            if pence is not None
        }

    def leaderboard(self, limit: int, offset: int) -> list[State]:
        total = func.sum(LedgerRow.leaderboard_pence)
        rows = self.session.execute(
            select(LedgerRow.player, PlayerRow.name, total, func.count())
            .join(PlayerRow, PlayerRow.id == LedgerRow.player)
            .where(LedgerRow.leaderboard_pence.is_not(None))
            .group_by(LedgerRow.player, PlayerRow.name)
            .order_by(total.desc(), PlayerRow.name, LedgerRow.player)
            .offset(offset)
            .limit(limit)
        )
        return [
            {"player_id": player, "name": name, "net_pence": int(pence), "hands": count}
            for player, name, pence, count in rows
        ]


class SQLAlchemyRepository:
    def __init__(self, database_url: str):
        url = connection_url(database_url)
        self.sqlite = url.get_backend_name() == "sqlite"
        self.engine = create_database_engine(
            url,
            pool_pre_ping=True,
            **(
                {"connect_args": {"check_same_thread": False, "timeout": 10}}
                if self.sqlite
                else {"pool_size": 5, "max_overflow": 2}
            ),
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
        """explicitly apply migrations to a development/test database."""
        from ofc.schema import upgrade

        upgrade(self.engine.url.render_as_string(hide_password=False))

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
