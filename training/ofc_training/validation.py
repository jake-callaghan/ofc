"""fixed validation deals track policy quality separately from training rewards."""

import json
from pathlib import Path

from stable_baselines3.common.callbacks import BaseCallback

from ofc_training.checkpoints import save_checkpoint
from ofc_training.evaluate import evaluate


class PolicyValidation(BaseCallback):
    def __init__(self, directory, every=100_000, deals=100, seed=1_000_000):
        super().__init__()
        self.directory = Path(directory)
        self.every = every
        self.deals = deals
        self.seed = seed
        self.best = float("-inf")

    def _record(self, label, result):
        record = {**result, "agent": label, "steps": self.model.num_timesteps}
        with (self.directory / "evaluation.jsonl").open("a") as stream:
            stream.write(json.dumps(record) + "\n")
        print(
            f"evaluation {label} at {self.model.num_timesteps:,}: "
            f"{result['mean_units_per_hand']:+.3f} units/hand, "
            f"{result['foul_rate']:.1%} fouls",
            flush=True,
        )

    def _evaluate(self):
        result = evaluate(model=self.model, deals=self.deals, seed=self.seed)
        self._record("policy", result)
        for key in ("mean_units_per_hand", "foul_rate", "royalties_per_hand"):
            self.logger.record(f"eval/{key}", result[key])
        self.logger.dump(self.model.num_timesteps)
        if result["mean_units_per_hand"] > self.best:
            self.best = result["mean_units_per_hand"]
            path = save_checkpoint(self.model, self.directory, "best")
            (self.directory / "best.json").write_text(
                json.dumps(
                    {
                        "model": path.name,
                        "steps": self.model.num_timesteps,
                        **result,
                    },
                    indent=2,
                )
                + "\n"
            )

    def _on_training_start(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        for agent in ("random", "heuristic"):
            self._record(agent, evaluate(agent=agent, deals=self.deals, seed=self.seed))
        self._evaluate()
        self.next_evaluation = self.model.num_timesteps + self.every

    def _on_step(self):
        if self.num_timesteps >= self.next_evaluation:
            self._evaluate()
            self.next_evaluation += (
                (self.num_timesteps - self.next_evaluation) // self.every + 1
            ) * self.every
        return True

    def _on_training_end(self):
        # the final optimisation can change weights without collecting more steps.
        self._evaluate()
