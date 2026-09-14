"""a bounded, deterministic practice strategy using only the player's own view."""

from collections import Counter
from itertools import product

from ofc.rules import ROWS, evaluate, next_fantasy, rank


def _quality(board, rules):
    if all(len(board[row]) == size for row, size in ROWS.items()):
        value = evaluate(board, rules)
        if value["foul"]:
            return -10000
        return (
            1000
            + sum(value["royalties"].values())
            + 8 * bool(next_fantasy(value, rules))
            + sum(rank(board[r])[0] for r in ROWS)
        )
    score = 0.0
    for row, size in ROWS.items():
        cards = board[row]
        if not cards:
            continue
        values = ["23456789TJQKA".index(c[0]) + 2 for c in cards]
        counts = Counter(values)
        weight = {"top": 0.65, "middle": 1.0, "bottom": 1.3}[row]
        score += weight * (
            sum(values) / 25 + sum(n * (n - 1) * 3 for n in counts.values())
        )
        if row != "top":
            suited = max(Counter(c[1] for c in cards).values())
            if len(cards) - suited == 0:
                score += weight * suited * suited / 2
            unique = set(values)
            if 14 in unique:
                unique.add(1)
            connected = max(
                sum(v in unique for v in range(low, low + 5)) for low in range(1, 11)
            )
            score += weight * connected / 2
        if len(cards) == size:
            score += weight * rank(cards)[0] * 5
    # avoid irrevocable inversions between completed rows.
    for weaker, stronger in [("top", "middle"), ("middle", "bottom")]:
        if (
            len(board[weaker]) == ROWS[weaker]
            and len(board[stronger]) == ROWS[stronger]
            and rank(board[weaker]) > rank(board[stronger])
        ):
            score -= 500
    return score


def choose_move(view, actor, rules):
    """enumerate ordinary draws; use a small beam search for fantasyland.

    prefers pairs and suited/connected lower rows, then valid completed boards
    and royalties. it does not inspect opponents' private cards or the deck.
    """
    hand = view["hand"]
    draw = hand["draws"][actor]
    board = hand["boards"][actor]
    keep = hand["turn"]["keep"]
    discard_count = len(draw) - keep
    rows = list(ROWS)
    if len(draw) <= 5:
        best = None
        for destinations in product([*rows, "discard"], repeat=len(draw)):
            if destinations.count("discard") != discard_count:
                continue
            candidate = {
                r: board[r]
                + [c for c, dest in zip(draw, destinations, strict=True) if dest == r]
                for r in rows
            }
            if any(len(candidate[r]) > ROWS[r] for r in rows):
                continue
            score = _quality(candidate, rules)
            if best is None or score > best[0]:
                best = score, destinations
        destinations = best[1]
        return {
            "type": "place",
            "placements": {
                r: [c for c, dest in zip(draw, destinations, strict=True) if dest == r]
                for r in rows
            },
            "discards": [
                c
                for c, dest in zip(draw, destinations, strict=True)
                if dest == "discard"
            ],
        }
    # group equal ranks first so the beam can recognise pairs and trips early.
    counts = Counter(c[0] for c in draw)
    ordered = sorted(
        draw, key=lambda c: (counts[c[0]], "23456789TJQKA".index(c[0])), reverse=True
    )
    beam = [(board, [])]
    for card in ordered:
        candidates = []
        for partial, discarded in beam:
            for row in rows:
                if len(partial[row]) < ROWS[row]:
                    next_board = {r: list(partial[r]) for r in rows}
                    next_board[row].append(card)
                    candidates.append((next_board, discarded))
            if len(discarded) < discard_count:
                candidates.append((partial, [*discarded, card]))
        beam = sorted(
            candidates, key=lambda item: _quality(item[0], rules), reverse=True
        )[:80]
    final, discarded = max(beam, key=lambda item: _quality(item[0], rules))
    return {
        "type": "place",
        "placements": {r: [c for c in final[r] if c not in board[r]] for r in rows},
        "discards": discarded,
    }
