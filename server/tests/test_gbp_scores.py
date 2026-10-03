"""money is frozen per hand and accumulated as integer pence, never floats."""

from uuid import uuid4

import pytest
from alembic import command
from db_helpers import build_repository, create_app
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_engine import auto_command

from ofc.engine import new_game, start_hand, transition
from ofc.persistence.sqlalchemy import SQLAlchemyRepository
from ofc.rules import DECK, RuleError, Rules
from ofc.schema import configuration
from ofc.store import Store


@pytest.fixture
def scores(tmp_path):
    store = Store(build_repository(f"sqlite:///{tmp_path / 'gbp.sqlite3'}"))
    a = store.register("Alice")["player_id"]
    b = store.register("Bob")["player_id"]
    yield store, a, b
    store.repository.close()


def test_net_gbp_uses_each_hand_stake_and_participation(scores):
    store, a, b = scores
    cpu = store.register("CPU")["player_id"]
    for price, enabled, amount in [(10, True, 3), (50, True, -2), (100, False, 20)]:
        gid = store.create(
            a, "Scores", Rules(), unit_pence=price, leaderboard_enabled=enabled
        )["game_id"]
        with store.repository.transaction(write=True) as uow:
            hand = {
                "number": 1,
                "result": {"units": {a: amount, b: -amount, cpu: 0}},
                "boards": {},
                "accounting": {"unit_pence": price, "leaderboard_enabled": enabled},
                "cpu_players": [cpu],
            }
            uow.record_hand(gid, hand, {})
        assert store.get(gid, a)["gbp_balances"][a] == price * amount
        state = store.get(gid, a)
        store.command(
            gid, a, "close", state["version"], {"type": "leave", "close_table": True}
        )
    assert store.leaderboard() == [
        {"player_id": b, "name": "Bob", "net_pence": 70, "hands": 2},
        {"player_id": a, "name": "Alice", "net_pence": -70, "hands": 2},
    ]
    assert store.leaderboard(limit=1, offset=1)[0]["player_id"] == a
    assert store.leaderboard(offset=2) == []


def test_settlement_retries_and_settings_do_not_reprice_history(scores):
    store, a, b = scores
    gid = store.create(a, "Play", Rules(fantasyland="off"), unit_pence=50)["game_id"]
    store.join(gid, b, "join")
    store.command(gid, a, "start", 1, {"type": "start", "players": [a, b]})
    while True:
        with store.repository.transaction() as uow:
            state = uow.get_game(gid).state
        if state["hand"]["status"] == "complete":
            break
        actor, move = auto_command(state)
        request_id = uuid4().hex
        store.command(gid, actor, request_id, state["version"], move)
        store.command(gid, actor, request_id, state["version"], move)
    balances = store.get(gid, a)["balances"]
    assert store.get(gid, a)["gbp_balances"] == {p: n * 50 for p, n in balances.items()}
    assert all(row["hands"] == 1 for row in store.leaderboard())
    ranked = store.leaderboard()
    store.command(
        gid,
        a,
        "settings",
        state["version"],
        {
            "type": "update_settings",
            "turn_seconds": None,
            "orbits": None,
            "unit_pence": 100,
            "leaderboard_enabled": False,
        },
    )
    assert store.leaderboard() == ranked
    history = store.history(gid, a)
    assert history[0]["accounting"] == {"unit_pence": 50, "leaderboard_enabled": True}
    result = store.command(
        gid, a, "next", state["version"] + 1, {"type": "start", "players": [a, b]}
    )
    assert result["state"]["hand"]["accounting"] == {
        "unit_pence": 100,
        "leaderboard_enabled": False,
    }


def test_settings_only_owner_between_hands():
    state = new_game("a", "Money", Rules())
    state = transition(state, "b", {"type": "join"})
    change = {
        "type": "update_settings",
        "turn_seconds": None,
        "orbits": None,
        "unit_pence": 100,
        "leaderboard_enabled": False,
    }
    with pytest.raises(RuleError, match="owner"):
        transition(state, "b", change)
    start_hand(state, "a", ["a", "b"], DECK)
    with pytest.raises(RuleError, match="between hands"):
        transition(state, "a", change)
    assert state["hand"]["accounting"] == {
        "unit_pence": 10,
        "leaderboard_enabled": True,
    }


def test_api_defaults_validation_and_auth(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'api.sqlite3'}")) as client:
        player = client.post("/players", json={"name": "Alice"}).json()
        headers = {"Authorization": f"Bearer {player['token']}"}
        assert client.get("/leaderboard").status_code == 401
        assert client.get("/leaderboard", headers=headers).json() == []
        default = client.post(
            "/games", headers=headers, json={"name": "Default"}
        ).json()["state"]
        assert default["unit_pence"] == 10
        assert default["leaderboard_enabled"] is True
        for invalid in [0, 20, 99, "10", True]:
            assert (
                client.post(
                    "/games",
                    headers=headers,
                    json={"name": "Invalid", "unit_pence": invalid},
                ).status_code
                == 422
            )
        for price in [10, 50, 100]:
            response = client.post(
                "/games",
                headers=headers,
                json={
                    "name": "Custom",
                    "unit_pence": price,
                    "leaderboard_enabled": False,
                },
            )
            assert response.status_code == 201
            assert response.json()["state"]["unit_pence"] == price


def test_migration_leaves_historical_gbp_unknown(tmp_path):
    url = f"sqlite:///{tmp_path / 'legacy.sqlite3'}"
    config = configuration(url)
    command.upgrade(config, "0002")
    adapter = SQLAlchemyRepository(url)
    with adapter.engine.begin() as connection:
        connection.execute(text("INSERT INTO players (id,name) VALUES ('a','Alice')"))
        connection.execute(
            text("INSERT INTO games (id,invite_hash,state) VALUES ('g','hash','{}')")
        )
        connection.execute(
            text(
                "INSERT INTO hands (game_id,number,result,boards,rules) VALUES ('g',1,'{}','{}','{}')"
            )
        )
        connection.execute(
            text("INSERT INTO ledger (game_id,hand,player,units) VALUES ('g',1,'a',12)")
        )
    command.upgrade(config, "head")
    with adapter.transaction() as uow:
        assert uow.balances("g") == {"a": 12}
        assert uow.gbp_balances("g") == {}
        assert uow.leaderboard(50, 0) == []
        assert uow.history("g", 0, 50)[0]["accounting"] is None
    adapter.close()
