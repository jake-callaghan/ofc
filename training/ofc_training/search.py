"""command-line access to the shared backend search evaluator."""

import argparse
import json
from pathlib import Path

from ofc.rules import Rules
from ofc.search import choose_search_move, estimate_moves, legal_moves, unseen_cards

__all__ = ["choose_search_move", "estimate_moves", "legal_moves", "unseen_cards"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "position", type=Path, help="JSON containing a public game view"
    )
    parser.add_argument("--actor", required=True)
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--foul-penalty", type=float, default=6)
    args = parser.parse_args()
    view = json.loads(args.position.read_text())
    estimates = estimate_moves(
        view,
        args.actor,
        Rules(**view["rules"]),
        samples=args.samples,
        seed=args.seed,
        foul_penalty=args.foul_penalty,
    )
    print(json.dumps(estimates, indent=2))


if __name__ == "__main__":
    main()
