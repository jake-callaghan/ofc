from copy import deepcopy

import pytest
from db_helpers import build_repository, create_app
from fastapi.testclient import TestClient
from test_engine import auto_command

from ofc.cpu import choose_move
from ofc.engine import new_game, public_view, start_hand, transition
from ofc.rules import DECK, Rules
from ofc.store import Store


@pytest.mark.parametrize("variant", ["classic", "pineapple"])
def test_cpu_game_runs_to_completion_and_posts_once(tmp_path, variant):
    store = Store(build_repository(f"sqlite:///{tmp_path / 'cpu.sqlite3'}"))
    human = store.register("Human")["player_id"]
    created = store.create(
        human, "Practice", Rules(variant=variant, fantasyland="standard")
    )
    gid = created["game_id"]
    result = store.command(gid, human, "cpu", 0, {"type": "add_cpu"})
    cpu = result["state"]["cpu_players"][0]
    duplicate = store.command(gid, human, "cpu", 0, {"type": "add_cpu"})
    assert duplicate["state"]["cpu_players"] == [cpu]
    result = store.command(
        gid, human, "start", 1, {"type": "start", "players": [human, cpu]}
    )
    for i in range(12):
        view = result["state"]
        assert set(view["hand"]["draws"]) == {human}
        if view["hand"]["status"] == "complete":
            break
        assert view["hand"]["turn"]["player"] == human
        with store.repository.transaction() as uow:
            state = uow.get_game(gid).state
        actor, command = auto_command(state)
        result = store.command(gid, actor, f"move-{i}", view["version"], command)
        repeated = store.command(gid, actor, f"move-{i}", view["version"], command)
        assert repeated["state"]["version"] == result["state"]["version"]
    assert result["state"]["hand"]["status"] == "complete"
    assert sum(result["state"]["balances"].values()) == 0
    assert len(store.history(gid, human)) == 1
    restored = Store(build_repository(f"sqlite:///{tmp_path / 'cpu.sqlite3'}"))
    assert restored.get(gid, human)["cpu_players"] == [cpu]


@pytest.mark.parametrize("award", [13, 14, 15, 16, 17])
def test_fantasy_strategy_produces_a_legal_move(award):
    state = new_game("human", "Practice", Rules())
    state["members"].append("cpu")
    state["fantasy"]["cpu"] = award
    start_hand(state, "human", ["human", "cpu"], DECK)
    before = deepcopy(state)
    view = public_view(state, "cpu")
    assert "deck" not in view["hand"]
    move = choose_move(view, "cpu", Rules())
    assert state == before
    after = transition(state, "cpu", move)
    assert sum(map(len, after["hand"]["boards"]["cpu"].values())) == 13
    assert len(after["hand"]["discards"]["cpu"]) == award - 13


def test_cpu_endpoint_permissions_and_limits(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'api.sqlite3'}")) as client:
        owner = client.post("/players", json={"name": "Owner"}).json()
        guest = client.post("/players", json={"name": "Guest"}).json()
        auth = {"Authorization": "Bearer " + owner["token"]}
        other = {"Authorization": "Bearer " + guest["token"]}
        game = client.post("/games", headers=auth, json={"name": "Practice"}).json()
        url = f"/games/{game['game_id']}/commands"
        client.post(
            f"/games/{game['game_id']}/join",
            headers=other,
            json={"invite": game["invite"], "request_id": "join"},
        )
        body = {"request_id": "cpu", "version": 1, "command": {"type": "add_cpu"}}
        assert client.post(url, headers=other, json=body).status_code == 401
        first = client.post(url, headers=auth, json=body)
        assert first.status_code == 200
        body.update(request_id="cpu2", version=2)
        second = client.post(url, headers=auth, json=body).json()["state"]
        body.update(request_id="cpu3", version=3)
        assert client.post(url, headers=auth, json=body).status_code == 422
        body.update(
            command={"type": "start", "players": second["cpu_players"]},
            request_id="allcpu",
        )
        assert client.post(url, headers=auth, json=body).status_code == 422
        body.update(
            command={
                "type": "start",
                "players": [owner["player_id"], *second["cpu_players"]],
            },
            request_id="start",
        )
        response = client.post(url, headers=auth, json=body)
        assert response.status_code == 200
        assert response.json()["state"]["hand"]["turn"]["player"] == owner["player_id"]
        body.update(
            command={"type": "add_cpu"},
            version=response.json()["state"]["version"],
            request_id="midhand",
        )
        assert client.post(url, headers=auth, json=body).status_code == 422


def test_strategy_avoids_an_available_foul_on_last_draw():
    from ofc.rules import evaluate

    board = {
        "top": ["2c", "2d", "3h"],
        "middle": ["4c", "4d", "5h", "6s"],
        "bottom": ["Ac", "Ad", "7h", "8s"],
    }
    view = {
        "hand": {
            "draws": {"cpu": ["4h", "9c", "Tc"]},
            "boards": {"cpu": board},
            "turn": {"keep": 2},
        }
    }
    move = choose_move(view, "cpu", Rules())
    final = {r: board[r] + move["placements"][r] for r in board}
    assert not evaluate(final, Rules())["foul"]


@pytest.mark.parametrize(
    "human_fantasy,cpu_fantasy", [(True, False), (False, True), (True, True)]
)
def test_cpu_and_fantasy_progress_independently(tmp_path, human_fantasy, cpu_fantasy):
    store = Store(build_repository(f"sqlite:///{tmp_path / 'independent.sqlite3'}"))
    human = store.register("Human")["player_id"]
    created = store.create(human, "Practice", Rules())
    gid = created["game_id"]
    result = store.command(gid, human, "cpu", 0, {"type": "add_cpu"})
    cpu = result["state"]["cpu_players"][0]
    with store.repository.transaction(write=True) as uow:
        state = uow.get_game(gid).state
        state["fantasy"] = {
            human: 14 if human_fantasy else 0,
            cpu: 14 if cpu_fantasy else 0,
        }
        uow.save_game(gid, state)
    result = store.command(
        gid, human, "start", 1, {"type": "start", "players": [human, cpu]}
    )
    assert cpu not in result["state"]["hand"]["fantasy_pending"]
    if human_fantasy:
        assert sum(map(len, result["state"]["hand"]["boards"][cpu].values())) == 0
        assert result["state"]["hand"]["turn"] is None
    for i in range(10):
        if result["state"]["hand"]["status"] == "complete":
            break
        with store.repository.transaction() as uow:
            state = uow.get_game(gid).state
        actor, move = auto_command(state, human)
        result = store.command(gid, actor, f"move-{i}", state["version"], move)
    assert result["state"]["hand"]["status"] == "complete"
    assert len(store.history(gid, human)) == 1
