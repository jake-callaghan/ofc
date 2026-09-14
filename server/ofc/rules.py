"""pure hand evaluation and pairwise unit scoring."""

from collections import Counter
from dataclasses import dataclass
from itertools import combinations

RANKS = "23456789TJQKA"
DECK = tuple(r + s for r in RANKS for s in "cdhs")
ROWS = {"top": 3, "middle": 5, "bottom": 5}


class RuleError(ValueError):
    """a command or ruleset violates a game invariant."""


@dataclass(frozen=True)
class Rules:
    variant: str = "pineapple"
    fantasyland: str = "progressive"
    moon: bool = False
    candyland: bool = False

    def __post_init__(self):
        if self.variant not in {"classic", "pineapple"}:
            raise RuleError("unknown dealing variant")
        if self.fantasyland not in {"off", "standard", "progressive"}:
            raise RuleError("unknown fantasyland mode")
        if self.variant == "classic" and self.fantasyland == "progressive":
            raise RuleError("progressive fantasyland requires pineapple")
        if self.candyland and self.fantasyland == "off":
            raise RuleError("candyland requires fantasyland")

    @property
    def capacity(self):
        return 3 if self.variant == "pineapple" or self.candyland else 4


def rank(cards):
    """return a comparable category and kickers; top straights/flushes do not count.

    missing top kickers compare as zero, so equal pairs use actual remaining
    cards when comparing a three-card row against a five-card row.
    """
    if len(cards) not in {3, 5} or len(set(cards)) != len(cards):
        raise RuleError("expected three or five distinct cards")
    if any(c not in DECK for c in cards):
        raise RuleError("unknown card")
    values = sorted((RANKS.index(c[0]) + 2 for c in cards), reverse=True)
    groups = sorted(((n, v) for v, n in Counter(values).items()), reverse=True)
    flush = len(cards) == 5 and len({c[1] for c in cards}) == 1
    unique = sorted(set(values))
    straight = 0
    if len(unique) == 5:
        if unique[-1] - unique[0] == 4:
            straight = unique[-1]
        elif unique == [2, 3, 4, 5, 14]:
            straight = 5
    counts = [n for n, _ in groups]
    ordered = [v for _, v in groups]
    if straight and flush:
        result = [8, straight]
    elif counts[0] == 4:
        result = [7, *ordered]
    elif counts == [3, 2]:
        result = [6, *ordered]
    elif flush:
        result = [5, *values]
    elif straight:
        result = [4, straight]
    elif counts[0] == 3:
        result = [3, *ordered]
    elif counts[:2] == [2, 2]:
        result = [2, *ordered]
    elif counts[0] == 2:
        result = [1, *ordered]
    else:
        result = [0, *values]
    return tuple(result + [0] * (6 - len(result)))


def royalties(row, value):
    category, high, *_ = value
    if row == "top":
        return high + 8 if category == 3 else max(0, high - 5) if category == 1 else 0
    base = {4: 2, 5: 4, 6: 6, 7: 10, 8: 25 if high == 14 else 15}.get(category, 0)
    return (2 if category == 3 else base * 2) if row == "middle" else base


def evaluate(board, rules):
    if set(board) != set(ROWS) or any(len(board[r]) != n for r, n in ROWS.items()):
        raise RuleError("board must contain rows of 3, 5, and 5 cards")
    cards = [card for row in ROWS for card in board[row]]
    if len(set(cards)) != 13:
        raise RuleError("board contains duplicate cards")
    ranks = {r: rank(board[r]) for r in ROWS}
    candy = rules.candyland and all(len({c[1] for c in board[r]}) == 1 for r in ROWS)
    foul = not candy and not (ranks["bottom"] >= ranks["middle"] >= ranks["top"])
    bonus = {r: 0 if foul else royalties(r, ranks[r]) for r in ROWS}
    moon = rules.moon and not foul and not candy and ranks["bottom"][:2] == (0, 11)
    return {
        "ranks": ranks,
        "foul": foul,
        "royalties": bonus,
        "candyland": candy,
        "moon": moon,
    }


def next_fantasy(evaluation, rules, was_fantasy=False):
    if evaluation["foul"] or rules.fantasyland == "off":
        return 0
    if evaluation["candyland"]:
        return 15
    top = evaluation["ranks"]["top"]
    bottom = evaluation["ranks"]["bottom"]
    if was_fantasy:
        qualifies = top[0] == 3 or bottom[0] >= 7
        if rules.variant == "classic":
            qualifies = qualifies or evaluation["ranks"]["middle"][0] >= 6
        return (13 if rules.variant == "classic" else 14) if qualifies else 0
    if top[0] != 3 and not (top[0] == 1 and top[1] >= 12):
        return 0
    if rules.variant == "classic":
        return 13
    if rules.fantasyland == "standard":
        return 14
    return 17 if top[0] == 3 else top[1] + 2


def compare(a, b):
    """score from a's perspective; special awards replace normal settlement."""
    result = {"rows": 0, "scoop": 0, "foul": 0, "royalties": 0, "special": 0}
    if a["candyland"] or b["candyland"]:
        if a["candyland"] != b["candyland"]:
            winner, sign = (a, 1) if a["candyland"] else (b, -1)
            result["special"] = sign * 6
            result["royalties"] = sign * sum(
                winner["royalties"][r] for r in ("middle", "bottom")
            )
    elif a["moon"] or b["moon"]:
        result["special"] = 20 * (int(a["moon"]) - int(b["moon"]))
    elif a["foul"] or b["foul"]:
        if a["foul"] != b["foul"]:
            winner, sign = (b, -1) if a["foul"] else (a, 1)
            result["foul"] = 6 * sign
            result["royalties"] = sign * sum(winner["royalties"].values())
    else:
        wins = [
            (a["ranks"][r] > b["ranks"][r]) - (a["ranks"][r] < b["ranks"][r])
            for r in ROWS
        ]
        result["rows"] = sum(wins)
        result["scoop"] = 3 if wins == [1, 1, 1] else -3 if wins == [-1, -1, -1] else 0
        result["royalties"] = sum(a["royalties"].values()) - sum(
            b["royalties"].values()
        )
    result["total"] = sum(result.values())
    return result


def settle(boards, rules):
    cards = [c for board in boards.values() for row in board.values() for c in row]
    if len(cards) != len(set(cards)):
        raise RuleError("players share cards")
    evaluations = {p: evaluate(b, rules) for p, b in boards.items()}
    balances = dict.fromkeys(boards, 0)
    pairs = []
    for a, b in combinations(boards, 2):
        score = compare(evaluations[a], evaluations[b])
        balances[a] += score["total"]
        balances[b] -= score["total"]
        pairs.append({"a": a, "b": b, **score})
    return {"evaluations": evaluations, "pairs": pairs, "units": balances}
