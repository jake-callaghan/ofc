"""one hand per episode; draft actions commit through the existing engine."""

from typing import ClassVar

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from ofc.cpu import choose_move
from ofc.engine import new_game, place, public_view, start_hand
from ofc.policy_inputs import (
    DESTINATIONS,
    OBSERVATION_SIZE,
    action_masks,
    encode_action,
    observation,
)
from ofc.rules import DECK, ROWS, Rules
from ofc.search import choose_default_move

RULES = Rules(variant="pineapple", fantasyland="off")


__all__ = ["PineappleEnv", "encode_action"]


class PineappleEnv(gym.Env):
    """the learner sees only its public view, including its own private cards.

    an action selects a card and destination. partial placements remain local
    until every card in the draw is assigned. fouling is legal and scores normally.
    """

    metadata: ClassVar[dict] = {"render_modes": []}

    def __init__(self, opponent="search", search_samples=8):
        if opponent not in {"heuristic", "random", "search"}:
            raise ValueError("opponent must be search, heuristic or random")
        if type(search_samples) is not int or search_samples < 1:
            raise ValueError("search_samples must be positive")
        self.search_samples = search_samples
        self.opponent = opponent
        self.action_space = spaces.Discrete(52 * 4)
        self.observation_space = spaces.Box(0, 1, (OBSERVATION_SIZE,), np.float32)
        self.game = None
        self.actor = "learner"
        self.other = "opponent"
        self._clear_draft()

    def _clear_draft(self):
        self.draft = {row: [] for row in ROWS}
        self.discards = []

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        seat = (options or {}).get("seat", int(self.np_random.integers(2)))
        if seat not in (0, 1):
            raise ValueError("seat must be 0 or 1")
        self.game = new_game(self.actor, "Practice", RULES)
        self.game["members"] = (
            [self.actor, self.other] if seat == 0 else [self.other, self.actor]
        )
        self._clear_draft()
        deck = list(self.np_random.permutation(DECK))
        start_hand(self.game, self.actor, self.game["members"], deck=deck)
        self._advance_opponent()
        return self._observation(), {}

    def _advance_opponent(self):
        hand = self.game["hand"]
        while hand["status"] == "playing" and hand["queue"][0]["player"] == self.other:
            view = public_view(self.game, self.other)
            if self.opponent == "search":
                move = choose_default_move(
                    view,
                    self.other,
                    RULES,
                    samples=self.search_samples,
                    seed=int(self.np_random.integers(2**32)),
                )
            elif self.opponent == "heuristic":
                move = choose_move(view, self.other, RULES)
            else:
                draw = list(self.np_random.permutation(hand["draws"][self.other]))
                keep = hand["queue"][0]["keep"]
                placements = {row: [] for row in ROWS}
                for card in draw[:keep]:
                    available = [
                        row
                        for row, size in ROWS.items()
                        if len(hand["boards"][self.other][row]) + len(placements[row])
                        < size
                    ]
                    row = str(self.np_random.choice(available))
                    placements[row].append(card)
                move = {"placements": placements, "discards": draw[keep:]}
            place(self.game, self.other, move["placements"], move["discards"])

    def action_masks(self):
        view = public_view(self.game, self.actor) if self.game else None
        return action_masks(view, self.actor, self.draft, self.discards)

    def _observation(self):
        return observation(
            public_view(self.game, self.actor), self.actor, self.draft, self.discards
        )

    def step(self, action):
        if not self.action_space.contains(action) or not self.action_masks()[action]:
            raise ValueError(
                "action is unavailable; reset or choose a masked legal action"
            )
        card_index, destination_index = divmod(int(action), 4)
        card, destination = DECK[card_index], DESTINATIONS[destination_index]
        if destination == "discard":
            self.discards.append(card)
        else:
            self.draft[destination].append(card)
        hand = self.game["hand"]
        assigned = sum(map(len, self.draft.values())) + len(self.discards)
        if assigned == len(hand["draws"][self.actor]):
            place(self.game, self.actor, self.draft, self.discards)
            self._clear_draft()
            self._advance_opponent()
        done = hand["status"] == "complete"
        reward = float(hand["result"]["units"][self.actor]) if done else 0.0
        info = {}
        if done:
            evaluation = hand["result"]["evaluations"][self.actor]
            info = {
                "units": reward,
                "foul": evaluation["foul"],
                "royalties": sum(evaluation["royalties"].values()),
            }
        return self._observation(), reward, done, False, info
