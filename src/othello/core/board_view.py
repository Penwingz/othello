"""The read-only board an engine sees, from the point of view of the side to move.

Squares are numbered row by row from the top-left: index = row*8 + col, so a1 is 0,
d3 is 19 and h8 is 63.
"""

from __future__ import annotations

from othello.core import bitboard as bb


class BoardView:
    __slots__ = ("_me", "_opp")

    def __init__(self, my_Discs: int, opp_Discs: int) -> None:
        if my_Discs & opp_Discs:
            raise ValueError("a square can't hold both colours")
        if (my_Discs | opp_Discs) & ~bb.ALL_SQUARES:
            raise ValueError("bitboards must fit in 64 bits")
        self._me = my_Discs
        self._opp = opp_Discs

    # raw bitboards: bit i set = a disc on square i
    @property
    def my_Discs(self) -> int:
        return self._me

    @property
    def opp_Discs(self) -> int:
        return self._opp

    def legal_Moves(self) -> list[int]:
        return bb.squares(bb.legal_Moves(self._me, self._opp))

    def is_Legal(self, square: int) -> bool:
        return 0 <= square < 64 and bool(bb.legal_Moves(self._me, self._opp) >> square & 1)

    def play_Move(self, square: int) -> BoardView:
        """Play ``square`` and hand the board to the other player (the view flips sides)."""
        if not self.is_Legal(square):
            raise ValueError(
                f"{bb.square_Name(square) if 0 <= square < 64 else square} is not legal"
            )
        me, opp = bb.play(self._me, self._opp, 1 << square)
        return BoardView(opp, me)

    def pass_Turn(self) -> BoardView:
        """Same discs, other player to move."""
        return BoardView(self._opp, self._me)

    def is_Game_Over(self) -> bool:
        return not bb.legal_Moves(self._me, self._opp) and not bb.legal_Moves(self._opp, self._me)

    def disc_Counts(self) -> tuple[int, int]:
        """(mine, theirs)."""
        return self._me.bit_count(), self._opp.bit_count()

    def empty_Count(self) -> int:
        return 64 - (self._me | self._opp).bit_count()

    def grid(self) -> list[list[str]]:
        """8 rows of 8 cells: "me", "opp" or "."."""

        def cell(square: int) -> str:
            if self._me >> square & 1:
                return "me"
            return "opp" if self._opp >> square & 1 else "."

        return [[cell(row * 8 + col) for col in range(8)] for row in range(8)]

    @staticmethod
    def square_Name(square: int) -> str:
        return bb.square_Name(square)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BoardView):
            return NotImplemented
        return (self._me, self._opp) == (other._me, other._opp)

    def __hash__(self) -> int:
        return hash((self._me, self._opp))

    def __repr__(self) -> str:
        return f"BoardView(my_Discs={self._me:#x}, opp_Discs={self._opp:#x})"
