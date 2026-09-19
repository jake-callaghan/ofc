"""load a trusted MaskablePPO checkpoint once and produce engine moves."""

from threading import Lock

from ofc.rules import DECK, ROWS
from ofc.search import choose_default_move


class TrainedCPU:
    def __init__(self, model_path, *, fallback=choose_default_move):
        from sb3_contrib import MaskablePPO

        from ofc.policy_inputs import OBSERVATION_SIZE

        self.model = MaskablePPO.load(model_path, device="cpu")
        if (
            self.model.observation_space.shape != (OBSERVATION_SIZE,)
            or getattr(self.model.action_space, "n", None) != 208
        ):
            raise ValueError(
                "checkpoint does not match the OFC v1 observation/action format"
            )
        self.fallback = fallback
        self.lock = Lock()

    def choose_move(self, view, actor, rules):
        from ofc.policy_inputs import DESTINATIONS, action_masks, observation

        hand = view["hand"]
        supported = (
            rules.variant == "pineapple"
            and rules.fantasyland == "off"
            and not rules.moon
            and not rules.candyland
            and len(hand["players"]) == 2
            and len(view["members"]) == 2
            and not any(hand["fantasy"].values())
        )
        if not supported:
            return self.fallback(view, actor, rules)
        if (
            hand["status"] != "playing"
            or not hand["turn"]
            or hand["turn"]["player"] != actor
        ):
            raise ValueError("trained CPU requires its active turn")
        draft = {row: [] for row in ROWS}
        discards = []
        # serialize access to the shared policy; all per-move state stays local.
        with self.lock:
            for _ in hand["draws"][actor]:
                mask = action_masks(view, actor, draft, discards)
                action, _ = self.model.predict(
                    observation(view, actor, draft, discards),
                    action_masks=mask,
                    deterministic=True,
                )
                action = int(action)
                if not 0 <= action < len(mask) or not mask[action]:
                    raise ValueError("trained policy returned an illegal action")
                card_index, destination_index = divmod(action, 4)
                destination = DESTINATIONS[destination_index]
                if destination == "discard":
                    discards.append(DECK[card_index])
                else:
                    draft[destination].append(DECK[card_index])
        return {"type": "place", "placements": draft, "discards": discards}
