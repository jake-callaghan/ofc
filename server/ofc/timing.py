"""turn deadlines and random legal placements, independent of persistence."""

from random import SystemRandom

from ofc.rules import ROWS


def random_move(state, rng=None):
    """fill randomly chosen free slots; legality does not guarantee a non-foul board."""
    rng = rng if rng is not None else SystemRandom()
    hand = state["hand"]
    turn = hand["queue"][0]
    player = turn["player"]
    cards = list(hand["draws"][player])
    slots = [
        row
        for row, capacity in ROWS.items()
        for _ in range(capacity - len(hand["boards"][player][row]))
    ]
    rng.shuffle(cards)
    rng.shuffle(slots)
    placements = {row: [] for row in ROWS}
    for card, row in zip(cards[: turn["keep"]], slots, strict=False):
        placements[row].append(card)
    return {
        "type": "place",
        "placements": placements,
        "discards": cards[turn["keep"] :],
    }


def set_deadline(state, now):
    hand = state["hand"]
    if not hand:
        return
    seconds = state["rules"].get("turn_seconds")
    timed = (
        seconds is not None
        and hand["status"] == "playing"
        and not hand["fantasy"][hand["queue"][0]["player"]]
    )
    hand["deadline"] = now + seconds if timed else None


def expired(state, now):
    hand = state["hand"]
    return bool(
        hand
        and hand["status"] == "playing"
        and hand.get("deadline") is not None
        and now >= hand["deadline"]
        and not hand["fantasy"][hand["queue"][0]["player"]]
    )
