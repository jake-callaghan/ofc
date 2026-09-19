import sys

import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.env_util import make_vec_env

from ofc_training.checkpoints import PeriodicCheckpoint
from ofc_training.environment import PineappleEnv
from ofc_training.train import main


def test_periodic_saves_count_all_environments_and_load(tmp_path):
    torch.set_num_threads(1)
    env = make_vec_env(PineappleEnv, n_envs=2, env_kwargs={"opponent": "random"})
    try:
        model = MaskablePPO(
            "MlpPolicy",
            env,
            n_steps=16,
            batch_size=32,
            n_epochs=1,
            policy_kwargs={"net_arch": [16]},
            device="cpu",
        )
        model.learn(32, callback=PeriodicCheckpoint(tmp_path, 15))
        paths = sorted(tmp_path.glob("*.zip"))
        assert [path.name for path in paths] == [
            "checkpoint_000000000016_steps.zip",
            "checkpoint_000000000030_steps.zip",
        ]
        assert MaskablePPO.load(paths[-1], device="cpu").num_timesteps == 30
        assert not list(tmp_path.glob("*.tmp.zip"))
    finally:
        env.close()


def test_ctrl_c_saves_and_runs_have_distinct_folders(tmp_path, monkeypatch):
    def interrupt(model, *args, **kwargs):
        model.num_timesteps = 42
        raise KeyboardInterrupt

    monkeypatch.setattr(MaskablePPO, "learn", interrupt)
    monkeypatch.setattr(
        sys, "argv", ["ofc-train", "--output", str(tmp_path / "practice")]
    )
    main()
    main()
    paths = list(tmp_path.glob("practice-*/interrupted_000000000042_steps.zip"))
    assert len(paths) == 2
    assert MaskablePPO.load(paths[0], device="cpu").num_timesteps == 42
