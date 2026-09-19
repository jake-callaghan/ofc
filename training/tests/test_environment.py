from copy import deepcopy

import numpy as np
import pytest

from ofc_training.environment import PineappleEnv, encode_action


@pytest.mark.parametrize("opponent", ["random", "heuristic", "search"])
def test_masked_rollouts_finish_and_match_engine_scores(opponent):
    env = PineappleEnv(opponent, search_samples=1)
    rng = np.random.default_rng(42)
    for seed in range(8):
        observation, _ = env.reset(seed=seed)
        done = False
        steps = 0
        while not done:
            assert env.observation_space.contains(observation)
            legal = np.flatnonzero(env.action_masks())
            assert len(legal)
            observation, reward, done, truncated, info = env.step(
                int(rng.choice(legal))
            )
            steps += 1
            assert not truncated
            if not done:
                assert reward == 0
        assert steps == 17
        hand = env.game["hand"]
        assert reward == hand["result"]["units"][env.actor] == info["units"]
        assert sum(hand["result"]["units"].values()) == 0
        assert sum(map(len, hand["boards"][env.actor].values())) == 13
        assert len(hand["discards"][env.actor]) == 4
        assert not env.action_masks().any()
        assert env.observation_space.contains(observation)


def test_seeded_games_are_reproducible():
    a, b = PineappleEnv("random"), PineappleEnv("random")
    np.testing.assert_array_equal(a.reset(seed=42)[0], b.reset(seed=42)[0])
    done = False
    while not done:
        action = int(np.flatnonzero(a.action_masks())[0])
        left = a.step(action)
        right = b.step(action)
        np.testing.assert_array_equal(left[0], right[0])
        assert left[1:] == right[1:]
        done = left[2]


def test_hidden_information_does_not_change_observation_or_mask():
    env = PineappleEnv("random")
    env.reset(seed=10, options={"seat": 1})
    before = env._observation()
    mask = env.action_masks()
    hand = env.game["hand"]
    hand["deck"].reverse()
    hand["draws"][env.other] = hand["deck"][:5]
    hand["discards"][env.other] = hand["deck"][5:8]
    np.testing.assert_array_equal(before, env._observation())
    np.testing.assert_array_equal(mask, env.action_masks())


def test_partial_moves_stay_local_and_mask_full_rows():
    env = PineappleEnv("random")
    env.reset(seed=1, options={"seat": 1})
    initial = deepcopy(env.game)
    cards = env.game["hand"]["draws"][env.actor]
    for card in cards[:3]:
        env.step(encode_action(card, "top"))
    assert env.game == initial
    assert not env.action_masks().reshape(52, 4)[:, 0].any()
    assert not env.action_masks().reshape(52, 4)[:, 3].any()
    with pytest.raises(ValueError):
        env.step(encode_action(cards[3], "top"))
    assert env.game == initial


def test_training_checkpoint_round_trip(tmp_path):
    import torch
    from sb3_contrib import MaskablePPO

    torch.set_num_threads(1)
    env = PineappleEnv("random")
    model = MaskablePPO(
        "MlpPolicy",
        env,
        n_steps=32,
        batch_size=32,
        n_epochs=1,
        gamma=1,
        seed=7,
        device="cpu",
        policy_kwargs={"net_arch": [16]},
    )
    model.learn(64)
    model.save(tmp_path / "smoke")
    loaded = MaskablePPO.load(tmp_path / "smoke", device="cpu")
    observation, _ = env.reset(seed=900)
    done = False
    while not done:
        kwargs = {"action_masks": env.action_masks(), "deterministic": True}
        action, _ = loaded.predict(observation, **kwargs)
        original, _ = model.predict(observation, **kwargs)
        assert int(action) == int(original)
        observation, _, done, _, _ = env.step(int(action))


def test_paired_heuristic_baseline_is_symmetric():
    from ofc_training.evaluate import evaluate

    result = evaluate(agent="heuristic", deals=3)
    assert result["hands"] == 6
    assert result["mean_units_per_hand"] == 0
    assert result["approx_95_percent_interval"] == [0, 0]
