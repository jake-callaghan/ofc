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


def auto_command(state, actor=None):
    hand = state["hand"]
    pending = hand.get("fantasy_pending", [])
    actor = actor or (pending[0] if pending else hand["queue"][0]["player"])
    turn = {"keep": 13} if actor in pending else hand["queue"][0]
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


@pytest.mark.parametrize("fantasy_first", [False, True])
def test_independent_fantasy_and_shared_showdown(fantasy_first):
    state = game()
    state["fantasy"] = {"a": 14, "c": 16}
    start_hand(state, "a", state["members"], DECK)
    assert {t["player"] for t in state["hand"]["queue"]} == {"b"}
    opening = deepcopy(state["hand"]["draws"])
    # one fantasy player can confirm before the other, in either seat order.
    _, move = auto_command(state, "c")
    queue = deepcopy(state["hand"]["queue"])
    state = transition(state, "c", move)
    assert state["hand"]["queue"] == queue
    assert state["hand"]["draws"]["b"] == opening["b"]
    with pytest.raises(RuleError):
        transition(state, "c", move)
    if fantasy_first:
        _, move = auto_command(state, "a")
        state = transition(state, "a", move)
    while state["hand"]["queue"]:
        _, move = auto_command(state, "b")
        state = transition(state, "b", move)
        if state["hand"]["status"] == "playing":
            assert not any(public_view(state, "a")["hand"]["boards"]["b"].values())
            assert not any(public_view(state, "b")["hand"]["boards"]["c"].values())
    if not fantasy_first:
        assert state["hand"]["status"] == "playing"
        assert state["hand"]["result"] is None
        assert public_view(state, "b")["hand"]["turn"] is None
        _, move = auto_command(state, "a")
        state = transition(state, "a", move)
    assert state["hand"]["status"] == "complete"
    for actor in state["members"]:
        assert public_view(state, actor)["hand"]["boards"] == state["hand"]["boards"]
    assert sum(state["hand"]["result"]["units"].values()) == 0


def test_normal_opponents_remain_visible_while_fantasy_is_isolated():
    state = game()
    state["fantasy"]["a"] = 14
    start_hand(state, "a", state["members"], DECK)
    _, move = auto_command(state, "b")
    state = transition(state, "b", move)
    assert (
        public_view(state, "c")["hand"]["boards"]["b"] == state["hand"]["boards"]["b"]
    )
    assert not any(public_view(state, "a")["hand"]["boards"]["b"].values())
    assert not any(public_view(state, "c")["hand"]["boards"]["a"].values())


@pytest.mark.parametrize("variant", ["pineapple", "classic"])
def test_every_street_is_dealt_privately_before_anyone_confirms(variant):
    state = game(Rules(variant=variant, fantasyland="standard"), count=3)
    state["fantasy"]["a"] = 14 if variant == "pineapple" else 13
    start_hand(state, "a", state["members"], DECK)
    fantasy_draw = list(state["hand"]["draws"]["a"])
    streets = 5 if variant == "pineapple" else 9
    for street in range(streets):
        hand = state["hand"]
        draw_count = 5 if street == 0 else 3 if variant == "pineapple" else 1
        keep = 5 if street == 0 else 2 if variant == "pineapple" else 1
        reserved = deepcopy(hand["draws"])
        assert all(len(reserved[p]) == draw_count for p in ("b", "c"))
        for actor in ("b", "c"):
            view = public_view(state, actor)["hand"]
            assert view["draws"] == {actor: reserved[actor]}
            assert view["draw_keep"] == keep
        _, early = auto_command(state, "c")
        with pytest.raises(RuleError, match="not your turn"):
            transition(state, "c", early)
        actor, move = auto_command(state, "b")
        state = transition(state, actor, move)
        assert state["hand"]["draws"]["b"] == []
        assert state["hand"]["draws"]["c"] == reserved["c"]
        actor, move = auto_command(state, "c")
        state = transition(state, actor, move)
        assert state["hand"]["draws"]["a"] == fantasy_draw
    assert not state["hand"]["queue"]
    assert state["hand"]["status"] == "playing"
    actor, move = auto_command(state, "a")
    state = transition(state, actor, move)
    used = (
        state["hand"]["deck"]
        + [
            c
            for board in state["hand"]["boards"].values()
            for row in board.values()
            for c in row
        ]
        + [c for cards in state["hand"]["discards"].values() for c in cards]
    )
    assert len(used) == len(set(used)) == 52
    assert state["hand"]["status"] == "complete"
