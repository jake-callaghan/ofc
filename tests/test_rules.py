from collections import Counter
from itertools import combinations

import pytest

from ofc.rules import (
    DECK,
    RuleError,
    Rules,
    compare,
    evaluate,
    next_fantasy,
    rank,
    royalties,
    settle,
)


def cards(text):
    return text.split()


def board(top, middle, bottom):
    return {"top": cards(top), "middle": cards(middle), "bottom": cards(bottom)}


VALID = board("Qc Qd 2s", "3c 4d 5h 6s 7c", "8c 9c Tc Jc Kc")


@pytest.mark.parametrize(
    "text,category",
    [
        ("Ac Kd 9h 7s 3c", 0),
        ("Ac Ad 9h 7s 3c", 1),
        ("Ac Ad 9h 9s 3c", 2),
        ("Ac Ad Ah 7s 3c", 3),
        ("Ac 2d 3h 4s 5c", 4),
        ("Ac Jc 9c 7c 3c", 5),
        ("Ac Ad Ah 7s 7c", 6),
        ("Ac Ad Ah As 3c", 7),
        ("Tc Jc Qc Kc Ac", 8),
    ],
)
def test_categories(text, category):
    assert rank(cards(text))[0] == category


def test_kickers_wheel_and_top_ranking():
    assert rank(cards("2c 3d 4h 5s 6c")) > rank(cards("Ac 2d 3h 4s 5c"))
    assert rank(cards("Ac Ad Kh")) > rank(cards("As Ah Qd"))
    assert rank(cards("Ac Kc Qc"))[0] == 0
    assert rank(cards("2c 3d 4h"))[0] == 0
    assert rank(cards("Qc Qd 9h 8s 2c")) > rank(cards("Qh Qs 9c"))


def test_all_three_card_category_counts():
    counts = Counter(rank(c)[0] for c in combinations(DECK, 3))
    assert counts == {0: 18304, 1: 3744, 3: 52}


@pytest.mark.parametrize("text", ["Ac Ac Ad", "1c 2d 3h", "Ac Kd"])
def test_invalid_cards(text):
    with pytest.raises(RuleError):
        rank(cards(text))


def test_royalties_and_fantasy():
    result = evaluate(VALID, Rules())
    assert not result["foul"]
    assert result["royalties"] == {"top": 7, "middle": 4, "bottom": 4}
    assert next_fantasy(result, Rules()) == 14
    assert next_fantasy(result, Rules(), True) == 0
    assert royalties("top", rank(cards("Ac Ad Ah"))) == 22
    assert royalties("middle", rank(cards("2c 2d 2h 4c 5s"))) == 2
    assert royalties("bottom", rank(cards("Tc Jc Qc Kc Ac"))) == 25
    assert royalties("middle", rank(cards("Tc Jc Qc Kc Ac"))) == 50


def test_foul_and_double_foul():
    bad = evaluate(board("Ac Ad Ah", "2c 4d 6h 8s Tc", "3c 5d 7h 9s Jc"), Rules())
    good = evaluate(VALID, Rules())
    assert bad["foul"] and not any(bad["royalties"].values())
    assert compare(good, bad)["total"] == 21
    assert compare(bad, good)["total"] == -21
    assert compare(bad, bad)["total"] == 0


def test_pairwise_zero_sum_and_scoop():
    a = board("Ac Ad 2h", "3c 4c 5c 6c 7c", "8d 9d Td Jd Qd")
    b = board("Kc Kh 2s", "3h 4h 5h 6h 7h", "8s 9s Ts Js Qs")
    result = settle({"a": a, "b": b}, Rules())
    assert sum(result["units"].values()) == 0
    assert result["pairs"][0]["rows"] == 1
    assert result["pairs"][0]["scoop"] == 0
    weak = evaluate(board("2c 4d 6h", "7c 7d 3h 5s 8c", "9h 9d Tc Js Qh"), Rules())
    strong = evaluate(VALID, Rules())
    assert compare(strong, weak)["scoop"] == 3
    assert compare(strong, weak)["total"] == -compare(weak, strong)["total"]


def test_moon_replaces_normal_score():
    moon = board("2c 4d 6h", "3c 5d 7h 8s 9c", "2h 4s 6c 8d Jh")
    evaluated = evaluate(moon, Rules(moon=True))
    assert evaluated["moon"] and not evaluated["foul"]
    assert compare(evaluated, evaluate(VALID, Rules()))["total"] == 20
    assert compare(evaluated, evaluated)["total"] == 0
    assert not evaluate(moon, Rules())["moon"]


def test_candyland_overrides_foul_and_moon():
    candy = board("Ac Kc Qc", "2d 4d 6d 8d Ad", "3h 5h 7h 9h Jh")
    assert evaluate(candy, Rules())["foul"]
    value = evaluate(candy, Rules(candyland=True))
    assert value["candyland"] and not value["foul"]
    assert compare(value, evaluate(VALID, Rules()))["total"] == 18
    assert next_fantasy(value, Rules(candyland=True)) == 15
    assert compare(value, value)["total"] == 0


@pytest.mark.parametrize(
    "top,award",
    [("Qc Qd 2s", 14), ("Kc Kd 2s", 15), ("Ac Ad 2s", 16), ("2c 2d 2h", 17)],
)
def test_progressive_awards(top, award):
    value = evaluate(board(top, "3c 4c 5c 6c 7c", "8h 9h Th Jh Qh"), Rules())
    assert next_fantasy(value, Rules()) == award


def test_invalid_rules_and_duplicates():
    with pytest.raises(RuleError):
        Rules(variant="classic")
    with pytest.raises(RuleError):
        settle({"a": VALID, "b": VALID}, Rules())
