from copy import deepcopy

import pytest
from db_helpers import create_app
from fastapi.testclient import TestClient
from test_engine import game
from test_orbits import finish

from ofc.engine import start_hand, transition
from ofc.rules import DECK, RuleError, Rules


def settings(timer=None, orbits=None):
    return {"type": "update_settings", "turn_seconds": timer, "orbits": orbits}


def test_only_owner_between_hands_and_validation():
    state = game(Rules(fantasyland="off"), 2)
    with pytest.raises(RuleError, match="owner"):
        transition(state, "b", settings(30, 2))
    for command in [settings(5, 1), settings(30, 0), settings(True, 2)]:
        with pytest.raises(RuleError):
            transition(state, "a", command)
    start_hand(state, "a", state["members"], DECK)
    before = deepcopy(state)
    with pytest.raises(RuleError, match="between hands"):
        transition(state, "a", settings(30, 2))
    assert state == before


def test_limits_preserve_progress_and_can_reopen_completed_game():
    state = game(Rules(fantasyland="off"), 2)
    for _ in range(2):
        start_hand(state, "a", state["members"], DECK)
        state = finish(state)
    old_hand = deepcopy(state["hand"])
    state = transition(state, "a", settings(30, 1))
    assert state["status"] == "complete"
    assert state["normal_hands"] == 2
    assert state["orbit_size"] == 2
    assert state["hand"] == old_hand
    state = transition(state, "a", settings(None, 2))
    assert state["status"] == "active"
    assert state["rules"]["turn_seconds"] is None
    state = transition(state, "a", settings())
    assert state["rules"]["orbits"] is None
    start_hand(state, "a", state["members"], DECK)


def test_reduced_limit_keeps_pending_fantasyland():
    state = game(Rules(fantasyland="off"), 2)
    for _ in range(2):
        start_hand(state, "a", state["members"], DECK)
        state = finish(state)
    state["fantasy"]["a"] = 14
    updated = transition(state, "a", settings(60, 1))
    assert updated["status"] == "active"
    assert updated["fantasy"] == state["fantasy"]


def test_api_persists_settings_and_handles_retries(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'settings.sqlite3'}")) as client:
        owner = client.post("/players", json={"name": "Owner"}).json()
        headers = {"Authorization": "Bearer " + owner["token"]}
        created = client.post(
            "/games", headers=headers, json={"name": "Editable"}
        ).json()
        url = f"/games/{created['game_id']}"
        body = {"request_id": "settings", "version": 0, "command": settings(45, 3)}
        result = client.post(url + "/commands", headers=headers, json=body)
        assert result.status_code == 200
        assert result.json()["state"]["rules"]["turn_seconds"] == 45
        assert (
            client.post(url + "/commands", headers=headers, json=body).json()[
                "applied_version"
            ]
            == 1
        )
        stored = client.get(url, headers=headers).json()
        assert stored["rules"]["orbits"] == 3
        body["request_id"] = "stale"
        assert (
            client.post(url + "/commands", headers=headers, json=body).status_code
            == 409
        )
