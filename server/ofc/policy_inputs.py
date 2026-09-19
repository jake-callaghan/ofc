"""shared version-one card encoding and legal action masks."""

import numpy as np

from ofc.rules import DECK, ROWS

CARDS = {card: index for index, card in enumerate(DECK)}
DESTINATIONS = (*ROWS, "discard")
OBSERVATION_SIZE = 52 * 8 + 5


def encode_action(card, destination):
    return CARDS[card] * 4 + DESTINATIONS.index(destination)


def action_masks(view, actor, draft, discards):
    mask = np.zeros((52, 4), dtype=bool)
    if view is None or view["hand"]["status"] == "complete":
        return mask.ravel()
    hand = view["hand"]
    placed = sum(map(len, draft.values()))
    assigned = {card for cards in draft.values() for card in cards} | set(discards)
    draw = hand["draws"][actor]
    keep = hand["turn"]["keep"]
    for card in draw:
        if card in assigned:
            continue
        for index, (row, size) in enumerate(ROWS.items()):
            mask[CARDS[card], index] = (
                placed < keep
                and len(hand["boards"][actor][row]) + len(draft[row]) < size
            )
        mask[CARDS[card], 3] = len(discards) < len(draw) - keep
    return mask.ravel()


def observation(view, actor, draft, discards):
    # encode the filtered view, never the simulator's deck or private opponent data.
    hand = view["hand"]
    other = next(player for player in hand["players"] if player != actor)
    cards = np.zeros((52, 8), dtype=np.float32)
    assigned = set(discards)
    for index, row in enumerate(ROWS):
        assigned.update(draft[row])
        for card in hand["boards"][actor][row] + draft[row]:
            cards[CARDS[card], index] = 1
        for card in hand["boards"][other][row]:
            cards[CARDS[card], index + 3] = 1
    for card in hand["draws"][actor]:
        if card not in assigned:
            cards[CARDS[card], 6] = 1
    for card in hand["discards"][actor] + discards:
        cards[CARDS[card], 7] = 1
    turn = hand["turn"]
    keep = turn["keep"] - sum(map(len, draft.values())) if turn else 0
    discard = len(hand["draws"][actor]) - turn["keep"] - len(discards) if turn else 0
    extras = np.array(
        [
            keep / 5,
            discard,
            sum(map(len, hand["boards"][actor].values())) / 13,
            hand["dealer"] == actor,
            view["members"][0] == actor,
        ],
        dtype=np.float32,
    )
    return np.concatenate((cards.ravel(), extras))
