"""Quick match between two plugin files, in colour-swapped pairs from the same opening.

python -m othello.match plugins/a.py plugins/b.py --games 20 --time-ms 200 [--seed 1]
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path

from othello.core import Color
from othello.engines import PluginEngine, PluginLoadError, load_Engine
from othello.engines.duel import play_Game, random_Opening


@dataclass
class Tally:
    label: str
    wins: int = 0
    draws: int = 0
    losses: int = 0
    disc_Difference: int = 0  # summed over games, from this engine's side
    failures: int = 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m othello.match", description=__doc__.split("\n")[0]
    )
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument(
        "--games", type=int, default=20, help="total games, rounded up to even (default 20)"
    )
    parser.add_argument(
        "--time-ms", type=int, default=200, help="time limit per move (default 200)"
    )
    parser.add_argument("--seed", type=int, default=None, help="fix the random openings")
    parser.add_argument(
        "--opening-moves", type=int, default=4, help="random moves before engines take over"
    )
    args = parser.parse_args(argv)

    engines: list[PluginEngine] = []
    try:
        for path in (args.first, args.second):
            try:
                engines.append(load_Engine(path))
            except PluginLoadError as error:
                print(f"Can't load {path}: {error}")
                return 1
        first, second = engines
        same_Name = first.name == second.name
        tallies = {
            id(first): Tally(f"{first.name} ({args.first.name})" if same_Name else first.name),
            id(second): Tally(f"{second.name} ({args.second.name})" if same_Name else second.name),
        }
        rng = random.Random(args.seed)
        pairs = (args.games + 1) // 2
        seed_Text = f", seed {args.seed}" if args.seed is not None else ""
        print(f"{tallies[id(first)].label} vs {tallies[id(second)].label}: {pairs * 2} games, "
              f"{args.time_ms} ms per move{seed_Text}")  # fmt: skip

        for _ in range(pairs):
            opening = random_Opening(args.opening_moves, rng)
            for black, white in ((first, second), (second, first)):
                record = play_Game(black, white, args.time_ms, opening)
                for engine, side in ((black, Color.BLACK), (white, Color.WHITE)):
                    tally = tallies[id(engine)]
                    sign = 1 if side is Color.BLACK else -1
                    tally.disc_Difference += sign * record.disc_Difference
                    if record.winner is None:
                        tally.draws += 1
                    elif record.winner is side:
                        tally.wins += 1
                    else:
                        tally.losses += 1
                    if record.failed_Side is side:
                        tally.failures += 1
                        print(f"  {record.failure}")
    finally:
        for engine in engines:
            engine.close()

    games = pairs * 2
    width = max(len(t.label) for t in tallies.values())
    print(f"{'Engine':<{width}}   W   D   L   avg disc diff   failures")
    for t in tallies.values():
        average = t.disc_Difference / games
        results = f"{t.wins:>3} {t.draws:>3} {t.losses:>3}"
        print(f"{t.label:<{width}} {results}   {average:>+13.1f}   {t.failures:>8}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
