from copy import deepcopy

import torch
from ofc.engine import public_view, transition
from ofc.rules import Rules
from ofc.trained_cpu import TrainedCPU
from sb3_contrib import MaskablePPO

from ofc_training.environment import RULES, PineappleEnv


def test_loaded_cpu_matches_training_policy_and_emits_legal_moves(tmp_path):
    torch.set_num_threads(1)
    env = PineappleEnv("random")
    model = MaskablePPO(
        "MlpPolicy",
        env,
        n_steps=32,
        batch_size=32,
        n_epochs=1,
        seed=5,
        device="cpu",
        policy_kwargs={"net_arch": [16]},
    )
    model.learn(32)
    model.save(tmp_path / "model")
    cpu = TrainedCPU(tmp_path / "model.zip")
    obs, _ = env.reset(seed=33)
    done = False
    while not done:
        view = public_view(env.game, env.actor)
        before = deepcopy(view)
        move = cpu.choose_move(view, env.actor, RULES)
        assert view == before
        expected = transition(env.game, env.actor, move)
        draw_size = len(view["hand"]["draws"][env.actor])
        for _ in range(draw_size):
            action, _ = model.predict(
                obs, action_masks=env.action_masks(), deterministic=True
            )
            obs, _, done, _, _ = env.step(int(action))
        assert (
            env.game["hand"]["boards"][env.actor]
            == expected["hand"]["boards"][env.actor]
        )
    sentinel = {"fallback": True}
    cpu.fallback = lambda *args: sentinel
    assert cpu.choose_move(view, env.actor, Rules()) == sentinel
