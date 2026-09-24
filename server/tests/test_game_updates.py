"""shared reads must reduce queries without leaking cards or missing commits."""

import asyncio

import pytest
from sqlalchemy import event
from test_store_api import setup_store

from ofc.game_updates import GameUpdates
from ofc.rules import Rules
from ofc.store import Store


def test_shared_polling_queries_privacy_and_external_updates(tmp_path):
    store, gid, alice, bob = setup_store(tmp_path)
    store.command(gid, alice, "start", 1, {"type": "start", "players": [alice, bob]})
    queries = []

    def record(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(store.repository.engine, "before_cursor_execute", record)
    now = [100.0]
    updates = GameUpdates(store, clock=lambda: now[0])

    async def exercise():
        async with updates.subscribe(gid) as first, updates.subscribe(gid) as second:
            views = await asyncio.gather(
                updates.get(gid, first, alice), updates.get(gid, second, bob)
            )
            assert len(queries) == 3
            assert set(views[0]["hand"]["draws"]) == {alice}
            assert set(views[1]["hand"]["draws"]) == {bob}
            assert "deck" not in views[0]["hand"]
            views[0]["player_names"][alice] = "mutated"
            assert (await updates.get(gid, first, alice))["player_names"][
                alice
            ] == "alice"
            spectator = await updates.get(gid, first, "outsider")
            assert spectator["hand"]["draws"] == {}
            assert len(queries) == 3
            queries.clear()
            now[0] += 0.6
            await asyncio.gather(
                updates.get(gid, first, alice), updates.get(gid, second, bob)
            )
            assert len(queries) == 1

            # another store does not notify this cache; polling must still see it.
            other = Store(store.repository)
            other.chat_message(gid, bob, "chat", "hello")
            expected = other.get(gid, alice)
            queries.clear()
            now[0] += 0.6
            assert await updates.get(gid, first, alice) == expected
            assert len(queries) == 3
        assert updates.games == {}

    try:
        asyncio.run(exercise())
    finally:
        event.remove(store.repository.engine, "before_cursor_execute", record)
        store.repository.close()


def test_shared_poll_failure_does_not_serve_stale_state(tmp_path):
    store, gid, alice, _ = setup_store(tmp_path)
    now = [100.0]
    updates = GameUpdates(store, clock=lambda: now[0])
    original = store.shared_snapshot

    def unavailable(*args):
        raise RuntimeError("database unavailable")

    async def exercise():
        async with updates.subscribe(gid) as entry:
            await updates.get(gid, entry, alice)
            now[0] += 1
            store.shared_snapshot = unavailable
            with pytest.raises(RuntimeError, match="database unavailable"):
                await updates.get(gid, entry, alice)
            store.shared_snapshot = original
            assert (await updates.get(gid, entry, alice))["version"] == 1
        assert not updates.games

    try:
        asyncio.run(exercise())
    finally:
        store.repository.close()


def test_saving_loaded_game_does_not_select_it_again(tmp_path):
    store, gid, _, _ = setup_store(tmp_path)
    queries = []

    def record(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(store.repository.engine, "before_cursor_execute", record)
    try:
        with store.repository.transaction(write=True) as uow:
            state = uow.get_game(gid).state
            state["name"] = "updated"
            uow.save_game(gid, state)
        assert len(queries) == 1
        with store.repository.transaction() as uow:
            assert uow.get_game(gid).state["name"] == "updated"
    finally:
        event.remove(store.repository.engine, "before_cursor_execute", record)
        store.repository.close()


def test_new_member_can_connect_before_next_poll(tmp_path):
    store, _, alice, bob = setup_store(tmp_path)
    created = store.create(alice, "new table", Rules())
    gid = created["game_id"]
    now = [100.0]
    updates = GameUpdates(store, clock=lambda: now[0])

    async def exercise():
        async with updates.subscribe(gid) as entry:
            await updates.get(gid, entry, alice)
            store.join(gid, bob, "join-new", created["invite"])
            # a new viewer can connect immediately, then sees membership on the next poll.
            await updates.get(gid, entry, bob)
            now[0] += 0.6
            view = await updates.get(gid, entry, bob)
            assert bob in view["members"]
            assert view["version"] == 1

    try:
        asyncio.run(exercise())
    finally:
        store.repository.close()
