"""storage contract checks shared by local and optionally managed sql databases."""

import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ofc.api import create_app
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
        assert uow.balances(game_id) == {player: 0}
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
