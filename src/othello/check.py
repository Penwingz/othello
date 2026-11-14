"""Check a plugin file before sharing it: python -m othello.check plugins/my_engine.py"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from othello.core import Color
from othello.engines import PLUGINS_DIR, PluginLoadError, load_Engine
from othello.engines.duel import play_Game

FAILURE_LABELS = {
    "illegal": "Illegal moves",
    "raised": "Exceptions",
    "not_int": "Non-integers",
    "timeout": "Timeouts",  # so slow the worker had to be killed
    "crashed": "Crashes",
    "not_loaded": "Restart fails",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m othello.check", description=__doc__.split("\n")[0]
    )
    parser.add_argument("plugin", type=Path, help="the plugin file to check")
    parser.add_argument("--games", type=int, default=20, help="games to play (default 20)")
    parser.add_argument(
        "--time-ms", type=int, default=200, help="time limit per move (default 200)"
    )
    parser.add_argument(
        "--opponent", type=Path, default=PLUGINS_DIR / "random_engine.py",
        help="plugin to play against (default: the Random plugin)",
    )  # fmt: skip
    args = parser.parse_args(argv)

    print(f"Checking {args.plugin}")
    try:
        engine = load_Engine(args.plugin)
    except PluginLoadError as error:
        print(f"  Loaded OK:      no\n  Problem:        {error}\nFAIL: the file doesn't load.")
        return 1
    try:
        opponent = load_Engine(args.opponent)
    except PluginLoadError as error:
        engine.close()
        print(f"  Can't load the opponent {args.opponent}: {error}")
        return 2

    try:
        by = f" by {engine.author}" if engine.author else ""
        print(f'  Loaded OK:      yes, "{engine.name}"{by}')
        terms = f"colours swapped, {args.time_ms} ms per move"
        print(f"  Playing {args.games} games against {opponent.name} ({terms})")

        failures: Counter[str] = Counter()
        examples: list[str] = []
        results: Counter[str] = Counter()
        slowest_Ms = 0.0
        for game in range(args.games):
            mine = Color.BLACK if game % 2 == 0 else Color.WHITE
            black, white = (engine, opponent) if mine is Color.BLACK else (opponent, engine)
            record = play_Game(black, white, args.time_ms)
            slowest_Ms = max(slowest_Ms, record.slowest_Ms[mine])
            if record.failure is not None and record.failed_Side is mine:
                failures[record.failure.kind] += 1
                if len(examples) < 3:
                    examples.append(f"game {game + 1}: {record.failure}")
            results[
                "draw" if record.winner is None else "win" if record.winner is mine else "loss"
            ] += 1
    finally:
        engine.close()
        opponent.close()

    for kind, label in FAILURE_LABELS.items():
        if kind in ("crashed", "not_loaded") and not failures[kind]:
            continue
        print(f"  {label + ':':<16}{failures[kind]}")
    over = "  (over the limit: keep an eye on the clock)" if slowest_Ms > args.time_ms else ""
    print(f"  {'Slowest move:':<16}{slowest_Ms:.0f} ms (limit {args.time_ms} ms){over}")
    print(f"  {'Results:':<16}W {results['win']} / D {results['draw']} / L {results['loss']}")
    for line in examples:
        print(f"    {line}")

    if failures:
        print("FAIL: the engine broke the contract (see above).")
        return 1
    print("PASS: the engine follows the contract.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
