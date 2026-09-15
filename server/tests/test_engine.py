import random
from copy import deepcopy

import pytest

from ofc.engine import new_game, public_view, start_hand, transition
from ofc.rules import DECK, ROWS, RuleError, Rules


def game(rules=None, count=3):
    rules = rules or Rules()
    state = new_game("a", "friends", rules)
    state["members"] = list("abcd"[:count])
    return state


def auto_command(state):
    hand = state["hand"]
    turn = hand["queue"][0]
    actor = turn["player"]
    draw = hand["draws"][actor]
    remaining = list(draw[: turn["keep"]])
    placements = {}
    for row, size in ROWS.items():
        n = min(size - len(hand["boards"][actor][row]), len(remaining))
        placements[row] = remaining[:n]
        del remaining[:n]
    return actor, {
        "type": "place",
        "placements": placements,
        "discards": draw[turn["keep"] :],
    }


@pytest.mark.parametrize(
    "rules,count,remaining",
    [(Rules(), 3, 1), (Rules(variant="classic", fantasyland="standard"), 4, 0)],
)
def test_complete_deal(rules, count, remaining):
    state = game(rules, count)
    start_hand(state, "a", state["members"], DECK)
    while state["hand"]["status"] == "playing":
        actor, command = auto_command(state)
        state = transition(state, actor, command)
    hand = state["hand"]
    assert len(hand["deck"]) == remaining
    assert all(sum(map(len, b.values())) == 13 for b in hand["boards"].values())
    assert sum(hand["result"]["units"].values()) == 0
    used = (
        hand["deck"]
        + [c for b in hand["boards"].values() for row in b.values() for c in row]
        + [c for cs in hand["discards"].values() for c in cs]
    )
    assert len(used) == len(set(used)) == 52


def test_invalid_action_is_atomic():
    state = game()
    start_hand(state, "a", ["a", "b"], DECK)
    before = deepcopy(state)
    actor, command = auto_command(state)
    command["placements"] = {"top": state["hand"]["draws"][actor]}
    with pytest.raises(RuleError):
        transition(state, actor, command)
    assert state == before
    with pytest.raises(RuleError):
        transition(state, "outsider", command)


def test_private_fantasy_and_draws():
    state = game()
    state["fantasy"]["a"] = 17
    start_hand(state, "a", ["a", "b", "c"], DECK)
    actor, command = auto_command(state)
    state = transition(state, actor, command)
    other = public_view(state, "b")["hand"]
    assert "deck" not in other and "queue" not in other
    assert set(other["draws"]) == {"b"}
    assert set(other["discards"]) == {"b"}
    assert not any(other["boards"]["a"].values())
    assert sum(map(len, public_view(state, "a")["hand"]["boards"]["a"].values())) == 13
    while state["hand"]["status"] == "playing":
        actor, command = auto_command(state)
        state = transition(state, actor, command)
    assert sum(map(len, public_view(state, "b")["hand"]["boards"]["a"].values())) == 13


def test_capacity_and_owner():
    state = game(count=4)
    with pytest.raises(RuleError):
        start_hand(state, "a", state["members"])
    with pytest.raises(RuleError):
        start_hand(state, "b", ["a", "b"])
    state = game(Rules(variant="classic", fantasyland="standard"), 4)
    state["fantasy"]["a"] = 14
    with pytest.raises(RuleError):
        start_hand(state, "a", state["members"])


def test_many_seeded_games_preserve_cards_and_units():
    for seed in range(30):
        state = game()
        deck = list(DECK)
        random.Random(seed).shuffle(deck)
        start_hand(state, "a", state["members"], deck)
        while state["hand"]["status"] == "playing":
            actor, command = auto_command(state)
            state = transition(state, actor, command)
        assert sum(state["hand"]["result"]["units"].values()) == 0


@pytest.mark.parametrize("fantasies", [{"a": 14, "b": 15, "c": 17}, {"a": 17, "c": 16}])
def test_mixed_and_all_fantasy_hands(fantasies):
    state = game()
    state["fantasy"] = fantasies.copy()
    start_hand(state, "a", state["members"], DECK)
    while state["hand"]["status"] == "playing":
        actor, command = auto_command(state)
        state = transition(state, actor, command)
    assert all(
        sum(map(len, b.values())) == 13 for b in state["hand"]["boards"].values()
    )
    assert sum(state["hand"]["result"]["units"].values()) == 0


def test_sitting_out_preserves_fantasy():
    state = game()
    state["fantasy"]["c"] = 17
    start_hand(state, "a", ["a", "b"], DECK)
    while state["hand"]["status"] == "playing":
        actor, command = auto_command(state)
        state = transition(state, actor, command)
    assert state["fantasy"]["c"] == 17


@pytest.mark.parametrize("variant,count", [("pineapple", 3), ("classic", 4)])
def test_opening_draws_visible_privately_and_not_redealt(variant, count):
    state = game(Rules(variant=variant, fantasyland="standard"), count)
    start_hand(state, "a", state["members"], DECK)
    opening = deepcopy(state["hand"]["draws"])
    assert all(len(cards) == 5 for cards in opening.values())
    assert len({card for cards in opening.values() for card in cards}) == count * 5
    for player in state["members"]:
        assert public_view(state, player)["hand"]["draws"] == {player: opening[player]}
    first, command = auto_command(state)
    other = next(p for p in state["members"] if p != first)
    with pytest.raises(RuleError, match="not your turn"):
        transition(state, other, command)
    for _ in range(count):
        actor, command = auto_command(state)
        assert state["hand"]["draws"][actor] == opening[actor]
        state = transition(state, actor, command)


def test_last_human_can_leave_and_rejoin_cpu_table():
    state = game(count=2)
    state["cpu_players"] = ["b"]
    state = transition(state, "a", {"type": "leave"})
    assert state["members"] == ["b"]
    assert state["owner"] is None
    state = transition(state, "c", {"type": "join"})
    assert state["owner"] == "c"
    start_hand(state, "c", ["b", "c"], DECK)
