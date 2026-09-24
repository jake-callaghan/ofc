"""storage contract checks shared by local and optionally managed sql databases."""

import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from db_helpers import create_app
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ofc.engine import new_game
from ofc.persistence.models import LedgerRow
from ofc.persistence.ports import GameRecord, Receipt
from ofc.persistence.sqlalchemy import SQLAlchemyRepository
from ofc.rules import Rules
from ofc.store import Store


@pytest.fixture(params=["sqlite", "postgresql"])
def repository(request, tmp_path):
    if request.param == "postgresql":
        url = os.environ.get("OFC_TEST_DATABASE_URL")
        if not url:
            pytest.skip(
                "set OFC_TEST_DATABASE_URL to a dedicated postgres test database"
            )
        if not url.startswith("postgresql"):
            pytest.fail("OFC_TEST_DATABASE_URL must select postgres")
    else:
        url = f"sqlite:///{tmp_path / 'contract.sqlite3'}"
    adapter = SQLAlchemyRepository(url)
    adapter.create_schema()
    yield adapter
    adapter.close()


def test_transaction_rollback_and_detached_reads(repository):
    player = str(uuid4())
    game_id = str(uuid4())
    with repository.transaction(write=True) as uow:
        uow.add_player(player, "alice", uuid4().hex)
        uow.add_game(
            GameRecord(game_id, uuid4().hex, new_game(player, "friends", Rules()))
        )
    with repository.transaction() as uow:
        detached = uow.get_game(game_id)
        detached.state["name"] = "changed without save"
    with pytest.raises(RuntimeError), repository.transaction(write=True) as uow:
        state = uow.get_game(game_id).state
        assert state["name"] == "friends"
        state["version"] = 100
        uow.save_game(game_id, state)
        uow.add_receipt(game_id, player, "failed", Receipt({"type": "start"}, 100))
        raise RuntimeError("simulate a failure before commit")
    with repository.transaction() as uow:
        assert uow.get_game(game_id).state["version"] == 0
        assert uow.receipt(game_id, player, "failed") is None


def test_hand_and_ledger_rollback_together(repository):
    player = str(uuid4())
    game_id = str(uuid4())
    with repository.transaction(write=True) as uow:
        uow.add_player(player, "alice", uuid4().hex)
        uow.add_game(
            GameRecord(game_id, uuid4().hex, new_game(player, "friends", Rules()))
        )
    with pytest.raises(RuntimeError), repository.transaction(write=True) as uow:
        uow.get_game(game_id)
        uow.record_hand(
            game_id, {"number": 1, "result": {"units": {player: 0}}, "boards": {}}, {}
        )
        balances = uow.balances(game_id)
        assert balances == {player: 0}
        assert type(balances[player]) is int
        raise RuntimeError("simulate ledger transaction failure")
    with repository.transaction() as uow:
        assert uow.history(game_id, 0, 50) == []
        assert uow.balances(game_id) == {}


def test_schema_migration_matches_orm(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migrations.sqlite3'}"
    monkeypatch.setenv("OFC_DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    command.check(config)
    adapter = SQLAlchemyRepository(url)
    service = Store(adapter)
    player = service.register("alice")
    assert service.authenticate(player["token"]) == player["player_id"]
    with adapter.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(LedgerRow)) == 0
    adapter.close()
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_api_accepts_non_sql_repository():
    # a small read adapter demonstrates that transport never depends on an orm.
    from contextlib import contextmanager

    class ReadUnitOfWork:
        def player_for_token(self, token_hash):
            return "alice"

        def get_game(self, game_id):
            return GameRecord(
                game_id, "unused", new_game("alice", "remote game", Rules())
            )

        def balances(self, game_id):
            return {"alice": 42}

        def player_names(self, players):
            return {"alice": "Alice"}

    class RemoteRepository:
        @contextmanager
        def transaction(self, *, write=False):
            assert not write
            yield ReadUnitOfWork()

        def close(self):
            raise AssertionError("injected adapter lifecycle belongs to its caller")

    with TestClient(create_app(repository=RemoteRepository())) as client:
        response = client.get(
            "/games/remote-id", headers={"Authorization": "Bearer token"}
        )
        assert response.status_code == 200
        assert response.json()["balances"] == {"alice": 42}


def test_startup_requires_migrations(tmp_path):
    from ofc.bootstrap import build_repository
    from ofc.schema import upgrade

    url = f"sqlite:///{tmp_path / 'empty.sqlite3'}"
    with pytest.raises(RuntimeError, match="schema is not current"):
        build_repository(url)
    upgrade(url)
    adapter = build_repository(url)
    adapter.close()


def test_reset_clears_data_and_replays_migrations(tmp_path):
    from ofc.schema import configuration, reset, upgrade

    url = f"sqlite:///{tmp_path / 'reset.sqlite3'}"
    upgrade(url)
    adapter = SQLAlchemyRepository(url)
    store = Store(adapter)
    player = store.register("alice")
    store.create(player["player_id"], "old table", Rules())
    adapter.close()
    reset(url)
    adapter = SQLAlchemyRepository(url)
    with adapter.engine.connect() as connection:
        from ofc.persistence.models import GameRow, PlayerRow

        assert connection.scalar(select(func.count()).select_from(PlayerRow)) == 0
        assert connection.scalar(select(func.count()).select_from(GameRow)) == 0
    adapter.close()
    command.check(configuration(url))


def test_reset_refuses_unrelated_tables(tmp_path):
    from sqlalchemy import create_engine

    from ofc.schema import reset

    url = f"sqlite:///{tmp_path / 'unrelated.sqlite3'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE unrelated (id INTEGER)")
    with pytest.raises(ValueError, match="non-OFC"):
        reset(url)
    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT * FROM unrelated")
    engine.dispose()


def test_postgres_schema_isolation_and_reset():
    from sqlalchemy import create_engine, text

    from ofc.database import connection_url
    from ofc.schema import configuration, reset, upgrade

    url = os.environ.get("OFC_TEST_DATABASE_URL")
    if not url:
        pytest.skip("set OFC_TEST_DATABASE_URL to a dedicated postgres test database")
    # an unrelated schema represents data owned by another service, such as auth.
    other = "other_" + uuid4().hex
    engine = create_engine(connection_url(url))
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{other}"'))
            connection.execute(
                text(f'CREATE TABLE "{other}".keep_me (id INTEGER PRIMARY KEY)')
            )
            connection.execute(text(f'INSERT INTO "{other}".keep_me VALUES (42)'))
        upgrade(url)
        command.check(configuration(url))
        adapter = SQLAlchemyRepository(url)
        with adapter.engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == "ofc"
        adapter.close()
        with engine.begin() as connection:
            connection.execute(
                text(
                    f'ALTER TABLE ofc.players ADD COLUMN external_id INTEGER REFERENCES "{other}".keep_me(id)'
                )
            )
        reset(url)
        command.check(configuration(url))
        with engine.connect() as connection:
            assert connection.scalar(text(f'SELECT id FROM "{other}".keep_me')) == 42
            assert (
                connection.scalar(text("SELECT version_num FROM ofc.alembic_version"))
                == "0002"
            )
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS "{other}".keep_me'))
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{other}"'))
        engine.dispose()


def test_auth_migration_preserves_existing_players_and_games(tmp_path):
    from sqlalchemy import text

    from ofc.schema import configuration

    url = f"sqlite:///{tmp_path / 'previous.sqlite3'}"
    config = configuration(url)
    command.upgrade(config, "0001")
    adapter = SQLAlchemyRepository(url)
    with adapter.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO players (id,name,token_hash) VALUES ('existing','Alice','hash')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO games (id,invite_hash,state) VALUES ('game','invite','{}')"
            )
        )
    command.upgrade(config, "head")
    command.check(config)
    with adapter.engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT name FROM players WHERE id='existing'"))
            == "Alice"
        )
        assert connection.scalar(text("SELECT count(*) FROM games")) == 1
    adapter.close()
