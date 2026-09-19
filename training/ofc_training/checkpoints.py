"""distinct run folders and atomic model checkpoints."""

from pathlib import Path

from stable_baselines3.common.callbacks import BaseCallback


def save_checkpoint(model, directory, kind):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{kind}_{model.num_timesteps:012d}_steps.zip"
    temporary = destination.with_suffix(".tmp.zip")
    try:
        model.save(temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"saved {destination}", flush=True)
    return destination


class PeriodicCheckpoint(BaseCallback):
    """count total transitions across all environments, not callback invocations."""

    def __init__(self, directory, every):
        super().__init__()
        if every < 1:
            raise ValueError("checkpoint interval must be positive")
        self.directory = directory
        self.every = every

    def _on_training_start(self):
        self.next_save = self.model.num_timesteps + self.every

    def _on_step(self):
        if self.num_timesteps >= self.next_save:
            save_checkpoint(self.model, self.directory, "checkpoint")
            self.next_save += (
                (self.num_timesteps - self.next_save) // self.every + 1
            ) * self.every
        return True
