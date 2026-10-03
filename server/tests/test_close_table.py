"""host closure is atomic, idempotent and preserves completed results."""

import pytest
from db_helpers import create_app
from fastapi.testclient import TestClient
from test_engine import game

from ofc.engine import start_hand, transition
from ofc.rules import DECK, RuleError, Rules


def test_close_requires_host_between_hands():
    state = game(Rules(), 2)
    close = {"type": "leave", "close_table": True}
    with pytest.raises(RuleError, match="owner"):
        transition(state, "b", close)
    start_hand(state, "a", state["members"], DECK)
    with pytest.raises(RuleError, match="between hands"):
        transition(state, "a", close)


def test_close_via_api_retry_and_remaining_members_can_leave(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'close.sqlite3'}")
    with TestClient(app) as client:
        store = app.state.store
        owner = store.register("Alice")
        guest = store.register("Bob")
        a, b = owner["player_id"], guest["player_id"]
        gid = store.create(a, "Close me", Rules())["game_id"]
        store.join(gid, b, "join")
        url = f"/games/{gid}"
        headers = {"Authorization": f"Bearer {owner['token']}"}
        body = {
            "request_id": "close",
            "version": 1,
            "command": {"type": "leave", "close_table": True},
        }
        response = client.post(url + "/commands", headers=headers, json=body)
        assert response.status_code == 200
        assert response.json()["state"] is None
        assert (
            client.post(url + "/commands", headers=headers, json=body).json()
            == response.json()
        )
        closed = store.get(gid, b)
        assert closed["status"] == "closed"
        assert closed["owner"] is None
        assert a not in closed["members"]
        assert closed["closed_reason"] == "host"
        assert closed["closed_at"] == closed["updated_at"]
        assert store.lobby(b) == []
        store.command(gid, b, "leave", closed["version"], {"type": "leave"})
        assert store.get(gid, b)["status"] == "closed"


def test_ordinary_leave_keeps_table_open_and_transfers_host():
    state = transition(game(Rules(), 2), "a", {"type": "leave", "close_table": False})
    assert state["status"] == "active"
    assert state["owner"] == "b"
