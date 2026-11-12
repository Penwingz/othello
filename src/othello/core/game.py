"""Game state on top of the bitboards: whose turn it is, passes and the end of the game."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Literal

from othello.core import bitboard as bb
from othello.core.board_view import BoardView


class Color(StrEnum):
    BLACK = "black"
    WHITE = "white"

    @property
    def other(self) -> Color:
        return Color.WHITE if self is Color.BLACK else Color.BLACK


class IllegalMoveError(ValueError):
    """The move isn't allowed here; the message says why."""


@dataclass(frozen=True, slots=True)
class GameState:
    """One moment in a game. to_Move is None once it's over; passed is set when the move
    that led here left the other side with nothing to play, so to_Move goes again."""

    black: int = bb.START_BLACK
    white: int = bb.START_WHITE
    to_Move: Color | None = Color.BLACK
    last_Move: int | None = None
    last_Flips: int = 0
    passed: Color | None = None

    def __post_init__(self) -> None:
        if self.black & self.white:
            raise ValueError("black and white overlap")
        if (self.black | self.white) & ~bb.ALL_SQUARES:
            raise ValueError("bitboards must fit in 64 bits")

    def discs(self, color: Color) -> int:
        return self.black if color is Color.BLACK else self.white

    def board_View(self) -> BoardView:
        if self.to_Move is None:
            raise IllegalMoveError("the game is over")
        return BoardView(self.discs(self.to_Move), self.discs(self.to_Move.other))

    def board_String(self) -> str:
        return "".join(
            "B" if self.black >> i & 1 else "W" if self.white >> i & 1 else "." for i in range(64)
        )

    @classmethod
    def from_Board(cls, board: str, to_Move: Color) -> GameState:
        """Build a position by hand: 64 cells of B/X, W/O or ".", spaces ignored."""
        cells = "".join(board.split()).upper()
        if len(cells) != 64:
            raise ValueError(f"board needs 64 cells, got {len(cells)}")
        black = white = 0
        for square, cell in enumerate(cells):
            if cell in "BX":
                black |= 1 << square
            elif cell in "WO":
                white |= 1 << square
            elif cell != ".":
                raise ValueError(f"bad cell {cell!r} at {square}")
        return hand_Turn_To(cls(black=black, white=white, to_Move=to_Move), to_Move)


def new_Game() -> GameState:
    return GameState()


def legal_Moves_Mask(state: GameState) -> int:
    if state.to_Move is None:
        return 0
    return bb.legal_Moves(state.discs(state.to_Move), state.discs(state.to_Move.other))


def legal_Squares(state: GameState) -> list[int]:
    return bb.squares(legal_Moves_Mask(state))


def hand_Turn_To(state: GameState, player: Color) -> GameState:
    """Give the turn to ``player``. If they can't move the other side goes again,
    and if neither can the game is over."""
    if bb.legal_Moves(state.discs(player), state.discs(player.other)):
        return replace(state, to_Move=player, passed=None)
    if bb.legal_Moves(state.discs(player.other), state.discs(player)):
        return replace(state, to_Move=player.other, passed=player)
    return replace(state, to_Move=None, passed=None)


def auto_Pass(state: GameState) -> GameState:
    if state.to_Move is None or legal_Moves_Mask(state):
        return state
    return hand_Turn_To(state, state.to_Move)


def apply(state: GameState, square: int, color: Color | None = None) -> GameState:
    """Play ``square`` for the side to move and return the next state."""
    mover = state.to_Move
    if mover is None:
        raise IllegalMoveError("the game is over")
    if color is not None and color is not mover:
        raise IllegalMoveError(f"it is {mover.value}'s turn, not {color.value}'s")
    if not isinstance(square, int) or not 0 <= square < 64:
        raise IllegalMoveError(f"square must be 0-63, got {square!r}")

    me, opp = state.discs(mover), state.discs(mover.other)
    move_Bit = 1 << square
    if (me | opp) & move_Bit:
        raise IllegalMoveError(f"{bb.square_Name(square)} is occupied")
    if not bb.legal_Moves(me, opp) & move_Bit:
        raise IllegalMoveError(f"{bb.square_Name(square)} flips nothing for {mover.value}")

    flips = bb.flips_For_Move(me, opp, move_Bit)
    me, opp = me | move_Bit | flips, opp & ~flips
    black, white = (me, opp) if mover is Color.BLACK else (opp, me)
    after = GameState(black=black, white=white, last_Move=square, last_Flips=flips)
    return hand_Turn_To(after, mover.other)


def is_Over(state: GameState) -> bool:
    return state.to_Move is None


def score(state: GameState) -> dict[Color, int]:
    return {Color.BLACK: state.black.bit_count(), Color.WHITE: state.white.bit_count()}


def winner(state: GameState) -> Color | Literal["draw"] | None:
    if not is_Over(state):
        return None
    counts = score(state)
    if counts[Color.BLACK] == counts[Color.WHITE]:
        return "draw"
    return Color.BLACK if counts[Color.BLACK] > counts[Color.WHITE] else Color.WHITE
