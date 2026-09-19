"""train a small pytorch actor-critic with masked ppo."""

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.logger import configure

from ofc_training.checkpoints import PeriodicCheckpoint, save_checkpoint
from ofc_training.environment import PineappleEnv
from ofc_training.validation import PolicyValidation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=100_000)
    parser.add_argument("--envs", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--save-every", type=int, default=100_000)
    parser.add_argument("--eval-every", type=int, default=100_000)
    parser.add_argument("--eval-deals", type=int, default=100)
    parser.add_argument("--eval-seed", type=int, default=1_000_000)
    parser.add_argument("--rollout-steps", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=0.0001)
    parser.add_argument("--entropy-coef", type=float, default=0.01)
    parser.add_argument("--target-kl", type=float, default=0.02)
    parser.add_argument(
        "--opponent", choices=["search", "heuristic", "random"], default="search"
    )
    parser.add_argument("--output", type=Path, default=Path("checkpoints/pineapple"))
    parser.add_argument("--search-samples", type=int, default=8)
    args = parser.parse_args()
    if any(
        value < 1
        for value in (
            args.steps,
            args.envs,
            args.save_every,
            args.eval_every,
            args.eval_deals,
            args.rollout_steps,
            args.epochs,
            args.search_samples,
        )
    ):
        parser.error(
            "step counts, intervals, environments, deals and epochs must be positive"
        )
    if args.batch_size < 2 or args.rollout_steps * args.envs % args.batch_size:
        parser.error("batch-size must be at least 2 and divide rollout-steps * envs")
    if any(
        not math.isfinite(value) or value <= 0
        for value in (args.learning_rate, args.target_kl)
    ):
        parser.error("learning-rate and target-kl must be finite and positive")
    if not math.isfinite(args.entropy_coef) or args.entropy_coef < 0:
        parser.error("entropy-coef must be finite and nonnegative")
    prefix = (
        args.output.with_suffix("") if args.output.suffix == ".zip" else args.output
    )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_directory = prefix.parent / f"{prefix.name}-{stamp}"
    run_directory.mkdir(parents=True, exist_ok=False)
    (run_directory / "config.json").write_text(
        json.dumps(vars(args), default=str, indent=2) + "\n"
    )
    print(f"checkpoints: {run_directory}", flush=True)
    torch.set_num_threads(1)
    env = make_vec_env(
        PineappleEnv,
        n_envs=args.envs,
        seed=args.seed,
        env_kwargs={"opponent": args.opponent, "search_samples": args.search_samples},
    )
    try:
        model = MaskablePPO(
            "MlpPolicy",
            env,
            seed=args.seed,
            device="cpu",
            verbose=1,
            n_steps=args.rollout_steps,
            batch_size=args.batch_size,
            n_epochs=args.epochs,
            learning_rate=args.learning_rate,
            ent_coef=args.entropy_coef,
            target_kl=args.target_kl,
            gamma=1.0,
            policy_kwargs={
                "net_arch": {"pi": [256, 256], "vf": [256, 256]},
                "activation_fn": torch.nn.ReLU,
            },
        )
        model.set_logger(configure(str(run_directory), ["stdout", "csv"]))
        try:
            model.learn(
                total_timesteps=args.steps,
                callback=[
                    PeriodicCheckpoint(run_directory, args.save_every),
                    PolicyValidation(
                        run_directory, args.eval_every, args.eval_deals, args.eval_seed
                    ),
                ],
            )
        except KeyboardInterrupt:
            save_checkpoint(model, run_directory, "interrupted")
            print("training interrupted; current model saved", flush=True)
        else:
            save_checkpoint(model, run_directory, "final")
    finally:
        env.close()


if __name__ == "__main__":
    main()
