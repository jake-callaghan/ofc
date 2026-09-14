from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_engine import auto_command

from ofc.api import create_app
from ofc.bootstrap import build_repository
from ofc.rules import Rules
from ofc.store import Conflict, Store


def setup_store(tmp_path):
    store = Store(build_repository(f"sqlite:///{tmp_path / 'test.sqlite3'}"))
    a = store.register("alice")["player_id"]
    b = store.register("bob")["player_id"]
    created = store.create(a, "friends", Rules())
    gid = created["game_id"]
    store.command(gid, b, "join", 0, {"type": "join", "invite": created["invite"]})
    return store, gid, a, b


def test_persistence_idempotency_and_ledger(tmp_path):
    store, gid, a, b = setup_store(tmp_path)
    command = {"type": "start", "players": [a, b]}
    store.command(gid, a, "start", 1, command)
    assert store.command(gid, a, "start", 1, command)["applied_version"] == 2
    with pytest.raises(Conflict):
        store.command(gid, a, "stale", 1, command)
    with pytest.raises(Conflict):
        store.command(gid, a, "start", 1, {"type": "start", "players": [b, a]})
    while True:
        with store.repository.transaction() as uow:
            state = uow.get_game(gid).state
        if state["hand"]["status"] == "complete":
            break
        actor, command = auto_command(state)
        rid = str(uuid4())
        response = store.command(gid, actor, rid, state["version"], command)
        store.command(gid, actor, rid, state["version"], command)
    restored = Store(build_repository(f"sqlite:///{tmp_path / 'test.sqlite3'}"))
    assert restored.get(gid, a) == store.get(gid, a)
    assert sum(response["state"]["balances"].values()) == 0
    assert len(restored.history(gid, a)) == 1
    with restored.repository.transaction() as uow:
        assert len(uow.balances(gid)) == 2
    assert restored.history(gid, a, after=1) == []


def test_concurrent_command_applied_once(tmp_path):
    store, gid, a, b = setup_store(tmp_path)

    def start(request_id):
        try:
            return store.command(
                gid, a, request_id, 1, {"type": "start", "players": [a, b]}
            )
        except Conflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(start, ["one", "two"]))
    assert sum(r is not None for r in results) == 1
    assert store.get(gid, a)["version"] == 2


def test_http_and_websocket(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'api.sqlite3'}")) as client:
        assert client.get("/health").status_code == 200
        a = client.post("/players", json={"name": "alice"}).json()
        b = client.post("/players", json={"name": "bob"}).json()
        auth_a = {"Authorization": "Bearer " + a["token"]}
        auth_b = {"Authorization": "Bearer " + b["token"]}
        created = client.post("/games", headers=auth_a, json={"name": "friends"}).json()
        gid = created["game_id"]
        assert client.get(f"/games/{gid}", headers=auth_b).status_code == 422
        assert (
            client.get(
                f"/games/{gid}", headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )
        url = f"/games/{gid}/commands"
        join = {
            "request_id": "join",
            "version": 0,
            "command": {"type": "join", "invite": "wrong"},
        }
        assert client.post(url, headers=auth_b, json=join).status_code == 401
        join["command"]["invite"] = created["invite"]
        assert client.post(url, headers=auth_b, json=join).status_code == 200
        with client.websocket_connect(f"/games/{gid}/events") as ws:
            ws.send_json({"token": a["token"]})
            assert ws.receive_json()["state"]["version"] == 1
            start = {
                "request_id": "start",
                "version": 1,
                "command": {
                    "type": "start",
                    "players": [a["player_id"], b["player_id"]],
                },
            }
            assert client.post(url, headers=auth_a, json=start).status_code == 200
            snapshot = ws.receive_json()["state"]
            assert snapshot["version"] == 2
            assert "deck" not in snapshot["hand"]
            assert b["player_id"] not in snapshot["hand"]["draws"]
        assert (
            client.post(
                url, headers=auth_a, json={**start, "request_id": "new"}
            ).status_code
            == 409
        )
        assert (
            client.post(
                url, headers=auth_a, json={**start, "version": True}
            ).status_code
            == 422
        )


def test_multiple_hands_accumulate_without_overwriting(tmp_path):
    store, gid, a, b = setup_store(tmp_path)
    totals = {a: 0, b: 0}
    for number in range(1, 4):
        current = store.get(gid, a)
        store.command(
            gid,
            a,
            str(uuid4()),
            current["version"],
            {"type": "start", "players": [a, b]},
        )
        while True:
            with store.repository.transaction() as uow:
                state = uow.get_game(gid).state
            if state["hand"]["status"] == "complete":
                break
            actor, command = auto_command(state)
            store.command(gid, actor, str(uuid4()), state["version"], command)
        for p, units in state["hand"]["result"]["units"].items():
            totals[p] += units
        assert store.get(gid, a)["balances"] == totals
        assert len(store.history(gid, a)) == number


def test_websocket_rejects_outsiders_and_bad_tokens(tmp_path):
    from starlette.websockets import WebSocketDisconnect

    with TestClient(create_app(f"sqlite:///{tmp_path / 'ws.sqlite3'}")) as client:
        a = client.post("/players", json={"name": "alice"}).json()
        b = client.post("/players", json={"name": "bob"}).json()
        gid = client.post(
            "/games",
            headers={"Authorization": "Bearer " + a["token"]},
            json={"name": "friends"},
        ).json()["game_id"]
        for token in ["bad", b["token"]]:
            with client.websocket_connect(f"/games/{gid}/events") as ws:
                ws.send_json({"token": token})
                with pytest.raises(WebSocketDisconnect) as error:
                    ws.receive_json()
                assert error.value.code == 1008
