"""evaluate on seeded deal pairs, swapping the learner's seat."""

import argparse
import json
import time

import numpy as np
import torch
from ofc.cpu import choose_move
from ofc.engine import public_view
from sb3_contrib import MaskablePPO

from ofc_training.environment import RULES, PineappleEnv, encode_action
from ofc_training.search import choose_search_move


def evaluate(
    agent="random",
    model=None,
    deals=100,
    seed=100_000,
    opponent="heuristic",
    samples=16,
    foul_penalty=6.0,
):
    env = PineappleEnv(opponent=opponent, search_samples=samples)
    rng = np.random.default_rng(seed)
    results, pair_units, latencies = [], [], []
    try:
        for deal in range(deals):
            scores = []
            for seat in (0, 1):
                observation, _ = env.reset(seed=seed + deal, options={"seat": seat})
                pending = []
                done = False
                while not done:
                    started = time.perf_counter()
                    if model is not None:
                        action, _ = model.predict(
                            observation,
                            action_masks=env.action_masks(),
                            deterministic=True,
                        )
                        action = int(action)
                    elif agent in {"heuristic", "search"}:
                        if not pending:
                            view = public_view(env.game, env.actor)
                            move = (
                                choose_search_move(
                                    view,
                                    env.actor,
                                    RULES,
                                    samples=samples,
                                    seed=seed + deal,
                                    foul_penalty=foul_penalty,
                                )
                                if agent == "search"
                                else choose_move(view, env.actor, RULES)
                            )
                            pending = [
                                encode_action(card, row)
                                for row, cards in move["placements"].items()
                                for card in cards
                            ]
                            pending += [
                                encode_action(card, "discard")
                                for card in move["discards"]
                            ]
                        action = pending.pop(0)
                    else:
                        action = int(rng.choice(np.flatnonzero(env.action_masks())))
                    latencies.append(time.perf_counter() - started)
                    observation, _, done, _, info = env.step(action)
                results.append(info)
                scores.append(info["units"])
            pair_units.append(np.mean(scores))
    finally:
        env.close()
    mean = float(np.mean(pair_units))
    error = (
        float(1.96 * np.std(pair_units, ddof=1) / np.sqrt(deals)) if deals > 1 else None
    )
    return {
        "hands": len(results),
        "agent": "model" if model is not None else agent,
        "search_samples": samples if agent == "search" and model is None else None,
        "foul_penalty": foul_penalty if agent == "search" and model is None else None,
        "seed": seed,
        "opponent": opponent,
        "mean_units_per_hand": mean,
        "approx_95_percent_interval": [mean - error, mean + error]
        if error is not None
        else None,
        "foul_rate": float(np.mean([r["foul"] for r in results])),
        "royalties_per_hand": float(np.mean([r["royalties"] for r in results])),
        "mean_action_ms": float(np.mean(latencies) * 1000),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model")
    parser.add_argument(
        "--agent", choices=["random", "heuristic", "search"], default="random"
    )
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--foul-penalty", type=float, default=6.0)
    parser.add_argument(
        "--opponent", choices=["random", "heuristic", "search"], default="heuristic"
    )
    parser.add_argument("--deals", type=int, default=100)
    parser.add_argument("--seed", type=int, default=100_000)
    args = parser.parse_args()
    if args.deals < 1:
        parser.error("deals must be positive")
    torch.set_num_threads(1)
    model = MaskablePPO.load(args.model, device="cpu") if args.model else None
    print(
        json.dumps(
            evaluate(
                args.agent,
                model,
                args.deals,
                args.seed,
                args.opponent,
                args.samples,
                args.foul_penalty,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
