from copy import deepcopy

import pytest
from ofc.engine import public_view
from ofc.rules import ROWS, evaluate

from ofc_training.environment import RULES, PineappleEnv
from ofc_training.search import estimate_moves, legal_moves, unseen_cards


def final_view():
    return {
        "hand": {
            "status": "playing",
            "turn": {"player": "cpu", "keep": 2},
            "boards": {
                "cpu": {
                    "top": ["2c", "2d", "3h"],
                    "middle": ["4c", "4d", "5h", "6s"],
                    "bottom": ["Ac", "Ad", "7h", "8s"],
                }
            },
            "draws": {"cpu": ["4h", "9c", "Tc"]},
            "discards": {"cpu": []},
        }
    }


def test_final_draw_estimates_are_exact_and_apply_one_joint_foul_penalty():
    view = final_view()
    estimates = estimate_moves(view, "cpu", RULES, samples=2, foul_penalty=9)
    assert estimates[0]["valid_probability"] == 1
    assert any(item["foul_probability"] == 1 for item in estimates)
    for item in estimates:
        board = {
            row: view["hand"]["boards"]["cpu"][row] + item["move"]["placements"][row]
            for row in ROWS
        }
        result = evaluate(board, RULES)
        assert item["utility"] == (
            -9 if result["foul"] else sum(result["royalties"].values())
        )
        assert item["exact"]
        assert item["utility_standard_error"] == 0
        assert all(
            sum(counts.values()) == 1
            for counts in item["row_category_probabilities"].values()
        )


def test_full_draw_moves_include_same_row_placements():
    board = {row: [] for row in ROWS}
    moves = list(legal_moves(board, ["Ac", "Ad", "Ah"], 2))
    assert len(moves) == 27
    assert any(len(move["placements"]["middle"]) == 2 for move in moves)


def test_rollouts_are_reproducible_and_ignore_private_fields(monkeypatch):
    from ofc import search

    env = PineappleEnv("random")
    env.reset(seed=9, options={"seat": 1})
    view = public_view(env.game, env.actor)
    # advance to a late turn to keep the test fast while retaining future draws.
    while sum(map(len, env.game["hand"]["boards"][env.actor].values())) < 9:
        import numpy as np

        env.step(int(np.flatnonzero(env.action_masks())[0]))
    view = public_view(env.game, env.actor)
    before = deepcopy(view)
    futures_seen = []
    complete = search._complete

    def record_future(board, future, rules):
        futures_seen.append(tuple(future))
        assert len(set(future)) == len(future)
        assert set(future) <= set(unseen_cards(before, env.actor))
        return complete(board, future, rules)

    monkeypatch.setattr(search, "_complete", record_future)
    result = estimate_moves(view, env.actor, RULES, samples=3, seed=4)
    assert all(
        futures_seen[start : start + 3] == futures_seen[:3]
        for start in range(0, len(futures_seen), 3)
    )
    assert view == before
    view["hand"]["deck"] = ["Ac"]
    view["hand"]["draws"][env.other] = ["Ac", "Ad"]
    view["hand"]["discards"][env.other] = ["Ah"]
    assert estimate_moves(view, env.actor, RULES, samples=3, seed=4) == result
    for item in result:
        assert item["utility"] == pytest.approx(
            item["valid_royalty_contribution"] - 6 * item["foul_probability"]
        )
        assert not item["exact"]
        assert item["samples"] == 3


def test_known_cards_excluded_and_unsupported_rules_rejected():
    view = final_view()
    view["hand"]["boards"]["other"] = {"top": ["Ks"], "middle": [], "bottom": []}
    view["hand"]["discards"]["cpu"] = ["Qs"]
    unseen = unseen_cards(view, "cpu")
    assert "Ks" not in unseen and "Qs" not in unseen and "4h" not in unseen
    from ofc.rules import Rules

    with pytest.raises(ValueError, match="ordinary Pineapple"):
        estimate_moves(view, "cpu", Rules(variant="classic", fantasyland="standard"))
