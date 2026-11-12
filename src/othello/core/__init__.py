"""Rules core."""

from othello.core.bitboard import parse_Square, square_Name
from othello.core.board_view import BoardView
from othello.core.game import (
    Color,
    GameState,
    IllegalMoveError,
    apply,
    auto_Pass,
    is_Over,
    legal_Squares,
    new_Game,
    score,
    winner,
)

__all__ = [
    "BoardView",
    "Color",
    "GameState",
    "IllegalMoveError",
    "apply",
    "auto_Pass",
    "is_Over",
    "legal_Squares",
    "new_Game",
    "parse_Square",
    "score",
    "square_Name",
    "winner",
]
