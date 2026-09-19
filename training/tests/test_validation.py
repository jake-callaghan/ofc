import json
import sys

from sb3_contrib import MaskablePPO

from ofc_training.train import main


def test_training_records_baselines_evaluations_and_best_checkpoint(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ofc-train",
            "--steps",
            "64",
            "--envs",
            "1",
            "--rollout-steps",
            "32",
            "--batch-size",
            "32",
            "--epochs",
            "1",
            "--eval-every",
            "32",
            "--eval-deals",
            "2",
            "--save-every",
            "32",
            "--opponent",
            "random",
            "--output",
            str(tmp_path / "validation"),
        ],
    )
    main()
    directory = next(tmp_path.glob("validation-*"))
    records = [
        json.loads(line)
        for line in (directory / "evaluation.jsonl").read_text().splitlines()
    ]
    assert [record["agent"] for record in records[:3]] == [
        "random",
        "heuristic",
        "policy",
    ]
    assert [record["steps"] for record in records[2:]] == [0, 32, 64, 64]
    assert all(record["hands"] == 4 for record in records)
    assert all(record["opponent"] == "heuristic" for record in records)
    best = json.loads((directory / "best.json").read_text())
    assert best["mean_units_per_hand"] == max(
        record["mean_units_per_hand"] for record in records[2:]
    )
    model = MaskablePPO.load(directory / best["model"], device="cpu")
    assert model.num_timesteps == best["steps"]
    assert model.target_kl == 0.02
    assert model.ent_coef == 0.01
    assert model.learning_rate == 0.0001
    assert (directory / "final_000000000064_steps.zip").exists()
    assert (directory / "progress.csv").exists()
    assert json.loads((directory / "config.json").read_text())["eval_seed"] == 1_000_000
