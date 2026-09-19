"""joint royalty and foul estimates from public information only."""

import math
from itertools import product
from random import Random
from statistics import mean, stdev

from ofc.cpu import _quality, choose_move
from ofc.rules import DECK, ROWS, evaluate, rank, royalties

CATEGORIES = (
    "high_card",
    "pair",
    "two_pair",
    "trips",
    "straight",
    "flush",
    "full_house",
    "quads",
    "straight_flush",
)


def legal_moves(board, draw, keep):
    """enumerate complete assignments, including both cards in the same row."""
    for destinations in product((*ROWS, "discard"), repeat=len(draw)):
        if destinations.count("discard") != len(draw) - keep:
            continue
        placements = {
            row: [
                card
                for card, destination in zip(draw, destinations, strict=True)
                if destination == row
            ]
            for row in ROWS
        }
        if any(
            len(board[row]) + len(placements[row]) > size for row, size in ROWS.items()
        ):
            continue
        yield {
            "type": "place",
            "placements": placements,
            "discards": [
                card
                for card, destination in zip(draw, destinations, strict=True)
                if destination == "discard"
            ],
        }


def unseen_cards(view, actor):
    hand = view["hand"]
    known = {
        card
        for board in hand["boards"].values()
        for cards in board.values()
        for card in cards
    }
    known.update(hand["draws"][actor])
    known.update(hand["discards"].get(actor, []))
    return [card for card in DECK if card not in known]


def _apply(board, move):
    return {row: board[row] + move["placements"][row] for row in ROWS}


def _complete(board, future, rules):
    # the continuation sees only the current draw, never subsequent sampled cards.
    for offset in range(0, len(future), 3):
        draw = list(future[offset : offset + 3])
        view = {
            "hand": {
                "boards": {"cpu": board},
                "draws": {"cpu": draw},
                "turn": {"keep": 2},
            }
        }
        board = _apply(board, choose_move(view, "cpu", rules))
    return board


def estimate_moves(
    view, actor, rules, *, samples=16, seed=0, foul_penalty=6.0, max_candidates=None
):
    """return candidate features, descending by sampled joint utility.

    utility is valid-board royalties minus a foul penalty, not net winnings.
    future own draws are sampled marginally from the unseen deck; opponent
    strategy, future public reveals and hidden card identities are not modelled.
    """
    if rules.variant != "pineapple" or view["hand"].get("fantasy", {}).get(actor):
        raise ValueError("search requires an ordinary Pineapple turn")
    if type(samples) is not int or samples < 1:
        raise ValueError("samples must be a positive integer")
    if not math.isfinite(foul_penalty) or foul_penalty < 0:
        raise ValueError("foul penalty must be finite and nonnegative")
    hand = view["hand"]
    turn = hand["turn"]
    if hand["status"] != "playing" or not turn or turn["player"] != actor:
        raise ValueError("search requires the actor's active turn")
    board, draw, keep = hand["boards"][actor], hand["draws"][actor], turn["keep"]
    remaining = 13 - sum(map(len, board.values())) - keep
    if remaining < 0 or remaining % 2 or (len(draw), keep) not in {(5, 5), (3, 2)}:
        raise ValueError("invalid ordinary Pineapple turn")
    count = remaining // 2 * 3
    unseen = unseen_cards(view, actor)
    if count > len(unseen):
        raise ValueError("not enough unseen cards for future draws")
    rng = Random(seed)
    # all candidates face the same hypothetical future draws, without replacement.
    futures = [rng.sample(unseen, count) for _ in range(samples)] if count else [[]]
    estimates = []
    candidates = list(legal_moves(board, draw, keep))
    if max_candidates is not None:
        if type(max_candidates) is not int or max_candidates < 1:
            raise ValueError("max_candidates must be a positive integer")
        # bound opening-turn latency; final draws are always evaluated exhaustively.
        if count and len(candidates) > max_candidates:
            candidates = sorted(
                candidates,
                key=lambda move: _quality(_apply(board, move), rules),
                reverse=True,
            )[:max_candidates]
    for move in candidates:
        utilities, valid_royalties = [], []
        row_totals = dict.fromkeys(ROWS, 0.0)
        categories = {row: dict.fromkeys(CATEGORIES, 0) for row in ROWS}
        valid_count = top_inversions = bottom_inversions = 0
        for future in futures:
            final = _complete(_apply(board, move), future, rules)
            result = evaluate(final, rules)
            values = {row: rank(final[row]) for row in ROWS}
            top_inversions += values["top"] > values["middle"]
            bottom_inversions += values["middle"] > values["bottom"]
            total = 0
            for row in ROWS:
                categories[row][CATEGORIES[values[row][0]]] += 1
                row_reward = royalties(row, values[row])
                row_totals[row] += row_reward
                total += row_reward
            valid = not result["foul"]
            valid_count += valid
            if valid:
                valid_royalties.append(total)
            utility = total if valid else -foul_penalty
            if result["moon"]:
                utility = 20
            elif result["candyland"]:
                utility = 6 + sum(
                    result["royalties"][row] for row in ("middle", "bottom")
                )
            utilities.append(utility)
        n = len(futures)
        estimates.append(
            {
                "move": move,
                "utility": float(mean(utilities)),
                "utility_standard_error": stdev(utilities) / math.sqrt(n)
                if n > 1
                else (0.0 if not count else None),
                "samples": n,
                "exact": not bool(count),
                "valid_probability": valid_count / n,
                "foul_probability": 1 - valid_count / n,
                "valid_royalty_contribution": sum(valid_royalties) / n,
                "royalties_given_valid": float(mean(valid_royalties))
                if valid_royalties
                else None,
                "top_over_middle_probability": top_inversions / n,
                "middle_over_bottom_probability": bottom_inversions / n,
                "raw_expected_row_royalties": {
                    row: total / n for row, total in row_totals.items()
                },
                "row_category_probabilities": {
                    row: {category: number / n for category, number in counts.items()}
                    for row, counts in categories.items()
                },
            }
        )
    if not estimates:
        raise ValueError("no legal moves")
    return sorted(estimates, key=lambda estimate: estimate["utility"], reverse=True)


def choose_search_move(view, actor, rules, **kwargs):
    return estimate_moves(view, actor, rules, **kwargs)[0]["move"]


def choose_default_move(view, actor, rules, *, samples=8, seed=0):
    """use bounded search for normal Pineapple, heuristic for classic/fantasy."""
    if rules.variant != "pineapple" or view["hand"].get("fantasy", {}).get(actor):
        return choose_move(view, actor, rules)
    return choose_search_move(
        view, actor, rules, samples=samples, seed=seed, max_candidates=16
    )
