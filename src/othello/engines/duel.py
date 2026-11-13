"""Play one game between two plugin engines (used by check and match)."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from othello.core import Color, GameState, apply, legal_Squares, new_Game, score
from othello.engines.plugins import EngineError, PluginEngine


@dataclass
class GameRecord:
    black: PluginEngine
    white: PluginEngine
    winner: Color | None = None  # None = draw
    disc_Difference: int = 0  # black discs minus white discs
    failure: EngineError | None = None  # set if an engine broke the contract
    failed_Side: Color | None = None
    slowest_Ms: dict[Color, float] = field(
        default_factory=lambda: {Color.BLACK: 0.0, Color.WHITE: 0.0}
    )


def random_Opening(plies: int, rng: random.Random) -> GameState:
    state = new_Game()
    for _ in range(plies):
        if state.to_Move is None:
            break
        state = apply(state, rng.choice(legal_Squares(state)))
    return state


def play_Game(
    black: PluginEngine,
    white: PluginEngine,
    time_Limit_Ms: int,
    start: GameState | None = None,
) -> GameRecord:
    record = GameRecord(black, white)
    state = start or new_Game()
    players = {Color.BLACK: black, Color.WHITE: white}
    while state.to_Move is not None:
        side = state.to_Move
        view = state.board_View()
        started = time.perf_counter()
        try:
            square = players[side].choose_Move(view.my_Discs, view.opp_Discs, time_Limit_Ms)
        except EngineError as error:
            # Breaking the contract loses the game on the spot.
            record.failure, record.failed_Side, record.winner = error, side, side.other
            return record
        took_Ms = (time.perf_counter() - started) * 1000
        record.slowest_Ms[side] = max(record.slowest_Ms[side], took_Ms)
        state = apply(state, square)

    counts = score(state)
    record.disc_Difference = counts[Color.BLACK] - counts[Color.WHITE]
    if record.disc_Difference:
        record.winner = Color.BLACK if record.disc_Difference > 0 else Color.WHITE
    return record
