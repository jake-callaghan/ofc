"""ordinary hands count toward the limit; fantasyland chains finish in full."""

import pytest
from test_engine import auto_command, game

from ofc.engine import start_hand, transition
from ofc.rules import DECK, RuleError, Rules


def finish(state):
    while state["hand"]["status"] == "playing":
        actor, command = auto_command(state)
        state = transition(state, actor, command)
    return state


@pytest.mark.parametrize("count,orbits", [(2, 1), (3, 2)])
def test_limits_count_starting_players_and_block_extra_hands(count, orbits):
    state = game(Rules(fantasyland="off", orbits=orbits), count)
    dealers = []
    for number in range(count * orbits):
        start_hand(state, "a", state["members"], DECK)
        dealers.append(state["hand"]["dealer"])
        state = finish(state)
        assert state["normal_hands"] == number + 1
    assert dealers == state["members"] * orbits
    assert state["status"] == "complete"
    with pytest.raises(RuleError, match="orbit limit reached"):
        start_hand(state, "a", state["members"], DECK)


def test_final_fantasyland_chain_does_not_count_or_end_early(monkeypatch):
    state = game(Rules(orbits=1), 2)
    monkeypatch.setattr("ofc.engine.next_fantasy", lambda *args: 0)
    start_hand(state, "a", ["a", "b"], DECK)
    state = finish(state)
    monkeypatch.setattr("ofc.engine.next_fantasy", lambda *args: 14)
    start_hand(state, "a", ["a", "b"], DECK)
    state = finish(state)
    assert state["normal_hands"] == 2
    assert state["status"] == "active"
    dealer = state["button"]
    start_hand(state, "a", ["a", "b"], DECK)
    state = finish(state)
    assert state["normal_hands"] == 2
    assert state["status"] == "active"
    assert state["button"] == dealer
    monkeypatch.setattr("ofc.engine.next_fantasy", lambda *args: 0)
    start_hand(state, "a", ["a", "b"], DECK)
    state = finish(state)
    assert state["normal_hands"] == 2
    assert state["hand_number"] == 4
    assert state["status"] == "complete"


def test_pending_fantasy_cannot_be_skipped_and_new_members_do_not_extend_limit():
    state = game(Rules(orbits=1), 3)
    start_hand(state, "a", ["a", "b"], DECK)
    state = finish(state)
    assert state["orbit_size"] == 2
    state["fantasy"]["b"] = 14
    with pytest.raises(RuleError, match="pending fantasyland"):
        start_hand(state, "a", ["a", "c"], DECK)


def test_unlimited_games_remain_open():
    state = game(Rules(fantasyland="off"), 2)
    for _ in range(3):
        start_hand(state, "a", ["a", "b"], DECK)
        state = finish(state)
    assert state["status"] == "active"
    # retain the starting seat count if the owner later enables a limit.
    assert state["orbit_size"] == 2


@pytest.mark.parametrize("value", [0, -1, 101, True, 1.5, "2"])
def test_invalid_orbit_limit(value):
    with pytest.raises(RuleError):
        Rules(orbits=value)
