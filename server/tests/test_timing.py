"""deadline enforcement uses an injected clock, not wall-clock sleeps."""

from concurrent.futures import ThreadPoolExecutor
from random import Random
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_engine import auto_command

from ofc.api import create_app
from ofc.bootstrap import build_repository
from ofc.rules import RuleError, Rules
from ofc.store import Conflict, Store
from ofc.timing import random_move


@pytest.fixture
def timed(tmp_path):
    clock = [1000.0]
    store = Store(
        build_repository(f"sqlite:///{tmp_path / 'timed.sqlite3'}"),
        clock=lambda: clock[0],
    )
    a = store.register("Alice")["player_id"]
    b = store.register("Bob")["player_id"]
    game = store.create(a, "Timed", Rules(turn_seconds=30))
    gid = game["game_id"]
    store.join(gid, b, "join", game["invite"])
    yield store, gid, a, b, clock
    store.repository.close()


def raw(store, gid):
    with store.repository.transaction() as uow:
        return uow.get_game(gid).state


def start(timed):
    store, gid, a, b, _ = timed
    store.command(gid, a, "start", 1, {"type": "start", "players": [a, b]})


def test_late_command_commits_random_move_and_rejects_submission(timed):
    store, gid, _, _, clock = timed
    start(timed)
    state = raw(store, gid)
    actor, move = auto_command(state)
    assert state["hand"]["deadline"] == 1030
    clock[0] = 1030
    with pytest.raises(Conflict, match="expired"):
        store.command(gid, actor, "late", state["version"], move)
    updated = raw(store, gid)
    assert updated["version"] == state["version"] + 1
    assert sum(map(len, updated["hand"]["boards"][actor].values())) == 5
    assert updated["hand"]["deadline"] == 1060
    assert updated["hand"]["last_timeout"]["player"] == actor
    assert store.expire_turn(gid) is False


def test_timely_move_and_retry_do_not_reset_deadline(timed):
    store, gid, _, _, clock = timed
    start(timed)
    state = raw(store, gid)
    actor, move = auto_command(state)
    clock[0] = 1029
    store.command(gid, actor, "on-time", state["version"], move)
    clock[0] = 1040
    result = store.command(gid, actor, "on-time", state["version"], move)
    assert result["state"]["hand"]["deadline"] == 1059


def test_timeout_workers_race_once_and_restart_recovers(timed):
    store, gid, _, _, clock = timed
    start(timed)
    clock[0] = 1030
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: store.expire_turn(gid), range(2))) == [
            False,
            True,
        ]
    clock[0] = 1060
    restored = Store(store.repository, clock=lambda: clock[0])
    restored.process_timeouts()
    assert raw(store, gid)["version"] == 4


def test_every_turn_can_timeout_and_settlement_is_recorded_once(timed):
    store, gid, a, _, clock = timed
    start(timed)
    while raw(store, gid)["hand"]["status"] == "playing":
        state = raw(store, gid)
        clock[0] = state["hand"]["deadline"]
        store.process_timeouts()
    hand = raw(store, gid)["hand"]
    assert hand["deadline"] is None
    assert all(sum(map(len, board.values())) == 13 for board in hand["boards"].values())
    assert all(len(cards) == 4 for cards in hand["discards"].values())
    store.process_timeouts()
    assert len(store.history(gid, a)) == 1
    assert sum(store.get(gid, a)["balances"].values()) == 0


def test_fantasyland_untimed_normal_player_gets_full_timer(timed):
    store, gid, a, b, clock = timed
    with store.repository.transaction(write=True) as uow:
        state = uow.get_game(gid).state
        state["fantasy"][a] = 14
        uow.save_game(gid, state)
    start(timed)
    assert raw(store, gid)["hand"]["deadline"] is None
    clock[0] += 5000
    store.process_timeouts()
    state = raw(store, gid)
    assert state["hand"]["queue"][0]["player"] == a
    actor, move = auto_command(state)
    store.command(gid, actor, "fantasy", state["version"], move)
    assert raw(store, gid)["hand"]["deadline"] == clock[0] + 30
    assert raw(store, gid)["hand"]["queue"][0]["player"] == b


def test_untimed_table_and_classic_random_placement(timed):
    store, _, a, b, clock = timed
    created = store.create(
        a, "Classic", Rules(variant="classic", fantasyland="standard")
    )
    gid = created["game_id"]
    store.join(gid, b, "join", created["invite"])
    store.command(gid, a, "start", 1, {"type": "start", "players": [a, b]})
    clock[0] += 10000
    store.process_timeouts()
    assert raw(store, gid)["hand"]["deadline"] is None
    while raw(store, gid)["hand"]["status"] == "playing":
        state = raw(store, gid)
        actor = state["hand"]["queue"][0]["player"]
        store.command(
            gid, actor, str(uuid4()), state["version"], random_move(state, Random(5))
        )
    assert len(store.history(gid, a)) == 1


@pytest.mark.parametrize("value", [0, -1, 9, 301, True, "30"])
def test_timer_validation(value):
    with pytest.raises(RuleError):
        Rules(turn_seconds=value)


def test_api_timer_configuration(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'api.sqlite3'}")) as client:
        player = client.post("/players", json={"name": "Alice"}).json()
        headers = {"Authorization": f"Bearer {player['token']}"}
        response = client.post(
            "/games",
            json={"name": "Timed", "rules": {"turn_seconds": 30}},
            headers=headers,
        )
        assert response.status_code == 201
        assert response.json()["state"]["rules"]["turn_seconds"] == 30
        assert (
            client.post(
                "/games",
                json={"name": "Invalid", "rules": {"turn_seconds": 0}},
                headers=headers,
            ).status_code
            == 422
        )


def test_background_timer_runs_without_any_connected_clients(tmp_path, monkeypatch):
    from threading import Event

    applied = Event()
    original = Store.expire_turn

    def observe(store, gid):
        result = original(store, gid)
        if result:
            applied.set()
        return result

    monkeypatch.setattr(Store, "expire_turn", observe)
    app = create_app(f"sqlite:///{tmp_path / 'background.sqlite3'}")
    with TestClient(app):
        store = app.state.store
        clock = [1000.0]
        store.clock = lambda: clock[0]
        a = store.register("Alice")["player_id"]
        b = store.register("Bob")["player_id"]
        created = store.create(a, "Timed", Rules(turn_seconds=30))
        gid = created["game_id"]
        store.join(gid, b, "join", created["invite"])
        store.command(gid, a, "start", 1, {"type": "start", "players": [a, b]})
        clock[0] = 1030
        assert applied.wait(timeout=3), "lifespan worker did not apply the timeout"
        assert raw(store, gid)["version"] == 3


def test_cpu_receives_move_immediately_then_human_gets_full_time(timed):
    store, gid, a, _, clock = timed
    result = store.command(gid, a, "cpu", 1, {"type": "add_cpu"})
    cpu = result["state"]["cpu_players"][0]
    store.command(gid, a, "start", 2, {"type": "start", "players": [a, cpu]})
    state = raw(store, gid)
    assert sum(map(len, state["hand"]["boards"][cpu].values())) == 5
    assert state["hand"]["queue"][0]["player"] == a
    assert state["hand"]["deadline"] == clock[0] + 30
