from copy import deepcopy

import pytest

from ofc import search
from ofc.engine import new_game, public_view, start_hand, transition
from ofc.rules import DECK, Rules


def test_default_pineapple_uses_bounded_search_with_default_house_rules(monkeypatch):
    calls = []
    sentinel = {"type": "place"}

    def search_move(view, actor, rules, **kwargs):
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(search, "choose_search_move", search_move)
    assert (
        search.choose_default_move(
            {"hand": {"fantasy": {"cpu": 0}}}, "cpu", Rules(moon=True)
        )
        == sentinel
    )
    assert calls == [{"samples": 8, "seed": 0, "max_candidates": 16}]


@pytest.mark.parametrize("variant,award", [("classic", 0), ("pineapple", 14)])
def test_unsupported_turns_use_heuristic(monkeypatch, variant, award):
    sentinel = {"type": "place"}
    monkeypatch.setattr(search, "choose_move", lambda *args: sentinel)
    rules = Rules(variant=variant, fantasyland="standard")
    assert (
        search.choose_default_move({"hand": {"fantasy": {"cpu": award}}}, "cpu", rules)
        == sentinel
    )


def test_search_is_legal_with_progressive_and_moon():
    rules = Rules(moon=True)
    game = new_game("human", "Search", rules)
    game["members"].append("cpu")
    start_hand(game, "human", ["human", "cpu"], DECK)
    view = public_view(game, "cpu")
    before = deepcopy(view)
    move = search.choose_default_move(view, "cpu", rules, samples=1)
    assert view == before
    state = transition(game, "cpu", move)
    assert sum(map(len, state["hand"]["boards"]["cpu"].values())) == 5
