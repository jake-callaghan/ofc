"""idle cleanup uses persisted activity and rechecks under the game lock."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from db_helpers import build_repository
from test_engine import auto_command

from ofc.rules import RuleError, Rules
from ofc.store import Store


@pytest.fixture
def table(tmp_path):
    now = [1000.0]
    store = Store(
        build_repository(f"sqlite:///{tmp_path / 'cleanup.sqlite3'}"),
        clock=lambda: now[0],
    )
    a = store.register("Alice")["player_id"]
    b = store.register("Bob")["player_id"]
    gid = store.create(a, "Idle", Rules())["game_id"]
    store.join(gid, b, "join")
    yield store, gid, a, b, now
    store.repository.close()


def raw(store, gid):
    with store.repository.transaction() as uow:
        return uow.get_game(gid).state


def test_eight_hour_boundary_and_concurrent_workers(table):
    store, gid, a, b, now = table
    now[0] += 8 * 3600 - 1
    assert store.reap_inactive() == 0
    store.get(gid, a)
    store.shared_snapshot(gid)
    now[0] += 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(lambda _: store.reap_inactive(), range(2))) == 1
    state = store.get(gid, a)
    assert state["status"] == "closed"
    assert state["closed_reason"] == "inactive"
    assert store.lobby(a) == []
    for command in (
        {"type": "start", "players": [a, b]},
        {"type": "add_cpu"},
        {"type": "join"},
    ):
        with pytest.raises(RuleError, match="closed"):
            store.command(gid, a, uuid4().hex, state["version"], command)
    with pytest.raises(RuleError, match="closed"):
        store.chat_message(gid, a, "closed", "hello")


def test_live_hands_never_reaped_and_results_survive(table):
    store, gid, a, b, now = table
    store.command(gid, a, "start", 1, {"type": "start", "players": [a, b]})
    now[0] += 20 * 3600
    assert store.reap_inactive() == 0
    while (state := raw(store, gid))["hand"]["status"] == "playing":
        actor, move = auto_command(state)
        store.command(gid, actor, uuid4().hex, state["version"], move)
    balances = store.get(gid, a)["balances"]
    now[0] += 8 * 3600
    assert store.reap_inactive() == 1
    assert len(store.history(gid, a)) == 1
    assert store.get(gid, a)["balances"] == balances


def test_chat_activity_and_stale_candidates_are_rechecked(table):
    store, gid, a, _, now = table
    now[0] += 8 * 3600
    store.chat_message(gid, a, "chat", "Still here")
    assert not store._reap_table(gid)
    now[0] += 8 * 3600 - 1
    store.chat_message(gid, a, "chat", "Still here")
    # idempotent retries do not extend the activity window.
    now[0] += 1
    assert store.reap_inactive() == 1


def test_legacy_game_gets_eight_hours_from_first_scan(table):
    store, gid, a, _, now = table
    with store.repository.transaction(write=True) as uow:
        state = uow.get_game(gid).state
        del state["updated_at"]
        uow.save_game(gid, state)
    now[0] += 100000
    assert store.reap_inactive() == 0
    assert store.get(gid, a)["updated_at"] == now[0]
    now[0] += 8 * 3600
    assert store.reap_inactive() == 1
