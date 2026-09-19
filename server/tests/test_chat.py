import pytest
from fastapi.testclient import TestClient

from ofc.api import create_app
from ofc.bootstrap import build_repository
from ofc.rules import Rules
from ofc.store import Store, Unauthorized


def test_chat_live_updates_are_private_and_do_not_change_game_version(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'chat.sqlite3'}")) as client:
        owner = client.post("/players", json={"name": "Owner"}).json()
        guest = client.post("/players", json={"name": "Guest"}).json()
        auth = {"Authorization": "Bearer " + owner["token"]}
        other = {"Authorization": "Bearer " + guest["token"]}
        created = client.post("/games", headers=auth, json={"name": "Chat"}).json()
        url = f"/games/{created['game_id']}"
        body = {"request_id": "hello", "text": "Hello <script>"}
        assert client.post(url + "/chat", headers=other, json=body).status_code == 401
        with client.websocket_connect(url + "/events") as ws:
            ws.send_json({"token": owner["token"]})
            initial = ws.receive_json()["state"]
            assert (
                client.post(url + "/chat", headers=auth, json=body).status_code == 200
            )
            message_state = ws.receive_json()["state"]
            assert message_state["version"] == initial["version"]
            message = message_state["chat"][0]
            assert message["text"] == body["text"]
            assert message["name"] == "Owner"
            assert (
                client.post(url + "/chat", headers=auth, json=body).status_code == 200
            )
            assert len(client.get(url, headers=auth).json()["chat"]) == 1
            reaction_url = url + f"/chat/{message['id']}/reactions"
            reaction = {"emoji": "👍", "active": True}
            assert (
                client.post(reaction_url, headers=other, json=reaction).status_code
                == 401
            )
            assert (
                client.post(reaction_url, headers=auth, json=reaction).status_code
                == 200
            )
            assert ws.receive_json()["state"]["chat"][0]["reactions"]["👍"] == [
                owner["player_id"]
            ]
            client.post(reaction_url, headers=auth, json=reaction)
            assert client.get(url, headers=auth).json()["chat_version"] == 2
            client.post(
                reaction_url, headers=auth, json={"emoji": "👍", "active": False}
            )
            assert ws.receive_json()["state"]["chat"][0]["reactions"]["👍"] == []
        for text in ["   ", "a" * 1001]:
            assert (
                client.post(
                    url + "/chat",
                    headers=auth,
                    json={"request_id": "invalid", "text": text},
                ).status_code
                == 422
            )
        assert (
            client.post(
                url + "/chat", headers=auth, json={**body, "text": "changed"}
            ).status_code
            == 409
        )


def test_chat_retention_persistence_and_leaving(tmp_path):
    database = f"sqlite:///{tmp_path / 'persist.sqlite3'}"
    store = Store(build_repository(database))
    owner = store.register("Owner")["player_id"]
    created = store.create(owner, "Chat", Rules())
    gid = created["game_id"]
    for index in range(101):
        store.chat_message(gid, owner, str(index), str(index))
    restored = Store(build_repository(database))
    state = restored.get(gid, owner)
    assert len(state["chat"]) == 100
    assert state["chat"][0]["text"] == "1"
    assert state["chat"][-1]["text"] == "100"
    assert state["version"] == 0
    restored.chat_message(gid, owner, "0", "0")
    assert restored.get(gid, owner)["chat_version"] == 101
    restored.command(gid, owner, "leave", 0, {"type": "leave"})
    with pytest.raises(Unauthorized):
        restored.chat_message(gid, owner, "late", "late")
    store.repository.close()
    restored.repository.close()
