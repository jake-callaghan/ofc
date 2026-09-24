"""table visibility controls joining, while authenticated spectators see safe views."""

import pytest
from db_helpers import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def lobby(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'lobby.sqlite3'}")
    with TestClient(app) as client:
        players = [
            client.post("/players", json={"name": name}).json()
            for name in ("owner", "guest")
        ]
        headers = [{"Authorization": "Bearer " + p["token"]} for p in players]
        yield client, app.state.store, players, headers


def test_listing_includes_private_and_open_but_no_hidden_game_data(lobby):
    client, store, _, headers = lobby
    assert client.get("/games").status_code == 401
    open_table = client.post("/games", headers=headers[0], json={"name": "open"}).json()
    private = client.post(
        "/games", headers=headers[0], json={"name": "private", "visibility": "private"}
    ).json()
    assert open_table["state"]["visibility"] == "open"
    listed = client.get("/games", headers=headers[1]).json()
    assert {t["id"] for t in listed} == {open_table["game_id"], private["game_id"]}
    assert {t["visibility"] for t in listed} == {"open", "private"}
    assert all(not t["is_member"] for t in listed)
    assert all(
        set(t)
        == {
            "id",
            "name",
            "visibility",
            "variant",
            "phase",
            "hand_number",
            "member_count",
            "is_member",
        }
        for t in listed
    )
    with store.repository.transaction(write=True) as uow:
        state = uow.get_game(open_table["game_id"]).state
        state["status"] = "complete"
        uow.save_game(open_table["game_id"], state)
    assert [t["id"] for t in client.get("/games", headers=headers[1]).json()] == [
        private["game_id"]
    ]


def test_private_requires_invite_for_both_join_endpoints(lobby):
    client, _, players, headers = lobby
    table = client.post(
        "/games", headers=headers[0], json={"name": "private", "visibility": "private"}
    ).json()
    gid = table["game_id"]
    assert client.get(f"/games/{gid}", headers=headers[1]).status_code == 200
    for invite in (None, "wrong"):
        assert (
            client.post(
                f"/games/{gid}/join",
                headers=headers[1],
                json={"request_id": str(invite), "invite": invite},
            ).status_code
            == 401
        )
        assert (
            client.post(
                f"/games/{gid}/commands",
                headers=headers[1],
                json={
                    "request_id": str(invite),
                    "version": 0,
                    "command": {"type": "join", "invite": invite},
                },
            ).status_code
            == 401
        )
    result = client.post(
        f"/games/{gid}/join",
        headers=headers[1],
        json={"request_id": "valid", "invite": table["invite"]},
    )
    assert result.status_code == 200
    assert players[1]["player_id"] in result.json()["state"]["members"]


def test_open_join_and_owner_visibility_changes(lobby):
    client, _, _, headers = lobby
    table = client.post("/games", headers=headers[0], json={"name": "open"}).json()
    gid = table["game_id"]
    body = {"request_id": "join"}
    response = client.post(f"/games/{gid}/join", headers=headers[1], json=body)
    assert response.status_code == 200
    assert (
        client.post(f"/games/{gid}/join", headers=headers[1], json=body).json()
        == response.json()
    )
    change = {
        "request_id": "settings",
        "version": 1,
        "command": {
            "type": "update_settings",
            "turn_seconds": None,
            "orbits": None,
            "visibility": "private",
        },
    }
    assert (
        client.post(
            f"/games/{gid}/commands", headers=headers[1], json=change
        ).status_code
        == 422
    )
    assert (
        client.post(f"/games/{gid}/commands", headers=headers[0], json=change).json()[
            "state"
        ]["visibility"]
        == "private"
    )


def test_spectator_websocket_hides_draws_fantasy_and_chat(lobby):
    client, store, players, headers = lobby
    table = client.post(
        "/games", headers=headers[0], json={"name": "private", "visibility": "private"}
    ).json()
    gid = table["game_id"]
    owner = players[0]["player_id"]
    store.command(gid, owner, "cpu", 0, {"type": "add_cpu"})
    with store.repository.transaction(write=True) as uow:
        state = uow.get_game(gid).state
        state["fantasy"][owner] = 14
        uow.save_game(gid, state)
    store.command(
        gid, owner, "start", 1, {"type": "start", "players": state["members"]}
    )
    store.chat_message(gid, owner, "chat", "members only")
    with client.websocket_connect(f"/games/{gid}/events") as ws:
        ws.send_json({"token": players[1]["token"]})
        view = ws.receive_json()["state"]
        assert view["hand"]["draws"] == {}
        assert view["hand"]["discards"] == {}
        assert "deck" not in view["hand"]
        assert "queue" not in view["hand"]
        assert all(not cards for cards in view["hand"]["boards"][owner].values())
        assert "chat" not in view
        assert players[1]["player_id"] not in view["members"]
    assert (
        client.post(
            f"/games/{gid}/chat",
            headers=headers[1],
            json={"request_id": "spectator", "text": "hello"},
        ).status_code
        == 401
    )


def test_older_tables_remain_invite_only(lobby):
    client, store, _, headers = lobby
    table = client.post("/games", headers=headers[0], json={"name": "old"}).json()
    gid = table["game_id"]
    with store.repository.transaction(write=True) as uow:
        state = uow.get_game(gid).state
        del state["visibility"]
        uow.save_game(gid, state)
    assert client.get("/games", headers=headers[1]).json()[0]["visibility"] == "private"
    assert (
        client.post(
            f"/games/{gid}/join", headers=headers[1], json={"request_id": "join"}
        ).status_code
        == 401
    )
