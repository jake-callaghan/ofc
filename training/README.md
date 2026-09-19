# OFC training

PyTorch policy/value networks trained with MaskablePPO, using the existing engine directly. No web server or database required.

This first version plays **one two-player Pineapple hand per episode**, with ordinary royalties and Fantasyland, moon and Candyland disabled as a training baseline.
## Run

From the repository root, with Python 3.13+ and UV:

```sh
uv sync --directory training
uv run --directory training pytest
uv run --directory training ofc-train --steps 100000 --output checkpoints/pineapple
uv run --directory training ofc-evaluate --model checkpoints/pineapple-RUN_TIMESTAMP/final_000000100352_steps.zip --deals 100
```

Paths are relative to `training/`. Training completes whole rollout batches, so it may exceed `--steps` slightly. The default opponent is now the shared search CPU, using 8 sampled futures and a 16-candidate shortlist per move. Use `--search-samples` to adjust its sampling budget, or `--opponent heuristic` / `--opponent random` for faster experiments. Search is substantially slower than the old opponent; previous steps-per-second estimates no longer apply. Training runs on CPU, with one PyTorch thread.

## Checkpoints

Each run creates a timestamped folder using `--output` as the prefix. The folder path and every saved filename are printed. Replace the example model path above with an actual saved file.

```sh
uv run --directory training ofc-train --steps 10000000 --save-every 100000 --output checkpoints/pineapple
```

Models save every 100,000 total card assignments by default, with names such as `checkpoint_000000100000_steps.zip`. With multiple environments, saves happen at the first vector step reaching the threshold. The filename records the actual collected step count, not the number of optimiser updates. A checkpoint may include a partially collected rollout; rollout data and active games are not saved.

Normal completion saves `final_..._steps.zip`; Ctrl+C saves `interrupted_..._steps.zip`. Wait for the saved message before closing the terminal. Forced termination cannot trigger an interruption save, but earlier periodic checkpoints remain. Writes use a temporary file followed by an atomic rename. Separate run folders prevent different experiments overwriting each other.

Every ZIP can be loaded by `ofc-evaluate`. Existing processes started with the old trainer do not gain checkpointing automatically. Starting a new training command still creates a fresh model; resume is not implemented yet.

Compare baselines on the same held-out seeds:

```sh
uv run --directory training ofc-evaluate --agent random --deals 100
uv run --directory training ofc-evaluate --agent heuristic --deals 100
```

Evaluation plays each seeded deal twice, swapping seats. It reports units per hand, an approximate 95% interval over paired deal means, foul rate, royalties and decision latency per internal card action. Small samples are only smoke checks. Use separate seeds for tuning and final evaluation; confidence intervals do not account for repeatedly selecting models on the same evaluation set.

## Training settings and evaluation

The revised defaults use 1,024 steps per environment (4,096 per rollout with four environments), minibatches of 256, four optimisation epochs, learning rate `0.0001`, entropy coefficient `0.01`, and target KL `0.02`. The KL check can stop further optimisation passes; it is not a hard bound on policy divergence. These are experimental settings, not a guarantee of beating the CPU. The network and net-unit rewards are unchanged.

```sh
uv run --directory training ofc-train --steps 1000000 --output checkpoints/pineapple-v2
```

At startup the trainer evaluates random play, the heuristic, and the untrained policy on the same validation deals against the heuristic CPU. It evaluates the policy again every 100,000 steps and after the final update. Each evaluation uses 100 deals played in both seats by default. Evaluation is deterministic for the policy, unlike the sampled actions used during training.

Each run folder contains:

- `config.json`: the command's settings.
- `progress.csv`: PPO training statistics and evaluation metrics.
- `evaluation.jsonl`: one JSON record per evaluation, including units, foul rate and uncertainty.
- `best.json`: the filename and metrics of the best validation checkpoint so far.
- `best_..._steps.zip`: models that improved validation units per hand, including the initial model as a baseline.
- Periodic, final and interrupted checkpoints as described above.

Options include `--rollout-steps`, `--batch-size`, `--epochs`, `--learning-rate`, `--entropy-coef`, `--target-kl`, `--eval-every`, `--eval-deals` and `--eval-seed`. Batch size must divide the total rollout size. Checkpoints record collected actions, so a periodic save can precede optimisation on the current rollout.

Validation uses seed 1,000,000 by default; standalone evaluation uses seed 100,000. Keep a separate final test set and repeat experiments with different training seeds. A best validation checkpoint can still lose to the heuristic or reflect sampling noise. Compare units and foul rates to the random baseline before extending a flat training run. Changes only affect newly started runs; they do not modify a running process.

## Representation

- Observation: 52 cards × 8 visible locations (own three rows, opponent's three rows, unassigned draw, own discards), plus five turn/seat features. Draft placements are included in the own-board channels. Unknown cards have zero entries.
- Action: `card_index * 4 + destination_index`, with destinations top, middle, bottom, discard. Unavailable cards, full rows and excess discards are masked.
- A draft is submitted to the engine only when all cards are assigned. The opponent acts between complete moves, never between draft decisions.
- Reward: zero until settlement, then the learner's net units. Fouls remain legal choices. `gamma=1` avoids discounting the 17 internal card assignments in this finite episode.
- Network: separate two-layer 256-neuron ReLU policy/value branches. The policy outputs 208 logits; the value head predicts the return. SB3 handles PPO optimisation and checkpoint serialization.

The encoder uses `public_view`; it never reads future deck order or the opponent's hidden draw/discards. Seeded shuffles and the random opponent use the environment's random generator.

## Monte Carlo placement estimates

The search CPU evaluates every legal complete assignment: up to 27 candidates for a normal three-card draw, and all legal assignments for the opening five. Each candidate receives the same sampled future own draws, without replacement from unseen cards. Known cards include all visible boards, the player's draw and their own discards. Opponents' hidden cards and the simulator's deck are never inspected.

The continuation strategy is the existing heuristic, receiving one draw at a time. It has no access to later sampled draws. The score is:

```text
mean(valid * total royalties - foul * foul_penalty)
```

This is a royalty-and-foul utility proxy, not expected net units against an opponent. The default foul penalty is 6; opponent royalties, row wins, scoops and future opponent reveals are not modelled. Unknown opponent cards are marginalised by sampling from the unseen pool, not identified or excluded using private information. Ordinary Pineapple is supported, including tables with progressive Fantasyland enabled. Actual Fantasyland turns and Classic use the heuristic fallback. Moon and Candyland outcomes use their special awards as utility proxies; future Fantasyland value is not estimated.

Benchmark the search agent against the heuristic (start small; exhaustive rollout search is much slower than neural inference):

```sh
uv run --directory training ofc-evaluate --agent search --samples 16 --deals 10
```

`--samples` controls futures per candidate; `--foul-penalty` adjusts risk aversion. Evaluation still reports actual engine unit scores, not the search utility. More samples reduce sampling noise but do not remove bias from the heuristic continuation. Selecting the maximum estimate also introduces selection bias; a per-candidate standard error is not a guarantee the winning move is best.

For a saved public game view, inspect all candidates and their features:

```sh
uv run --directory training ofc-analyse position.json --actor PLAYER_ID --samples 64
```

The JSON must have the same `rules` and `hand` fields as `public_view`, with an active turn for that actor. `estimate_moves(view, actor, rules, ...)` provides the same report programmatically, sorted by utility. Each candidate includes validity/foul probability, conditional royalties, valid royalty contribution, both row-inversion probabilities, mutually exclusive row-category probabilities, raw row royalties, utility and its Monte Carlo standard error. Raw row royalties include boards that foul; only valid royalties contribute to utility. When no future draws remain, evaluation is exact and needs no sampling.

The implementation lives in `server/ofc/search.py`, with no NumPy/PyTorch runtime dependency. The website now uses `choose_default_move`, which shortlists at most 16 candidates using the heuristic before sampling 8 futures each; final draws are exhaustive. Standalone `--agent search` and `ofc-analyse` remain exhaustive over candidates for analysis. The training environment defaults to the same bounded search as its opponent, with configurable sample count. Validation still uses the fixed heuristic benchmark to keep learning curves comparable. To evaluate against search explicitly, use `ofc-evaluate --model PATH --opponent search --samples 8 --deals 10`.

This trains the RL model **against** search. It does not yet imitate search demonstrations or append search features to the neural observation vector; existing checkpoints retain their original input format. Website changes take effect after restarting/redeploying the backend; no deployment is performed by the training commands.

## Next stages

Measure against the heuristic CPU before adding complexity. Then add multi-hand episodes for Fantasyland, observation/action schema versioning, a pool of frozen opponents, and a production inference adapter using the same encoder and action decoder. The current model is only valid for the fixed rules above; don't apply it to live tables with other rules. Training checkpoints are ignored by Git.
