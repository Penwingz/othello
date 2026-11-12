"""Othello rules on bitboards.

A board is two 64-bit ints: the discs of the player to move ("me") and of the other
player ("opp"). Bit i is square i, counted row by row from a1 (bit 0) to h8 (bit 63).
A step in a direction is a shift; sideways steps are masked so discs can't wrap around
the edge of the board.
"""

from __future__ import annotations

from collections.abc import Iterator

ALL_SQUARES = 0xFFFF_FFFF_FFFF_FFFF
NOT_COL_A = 0xFEFE_FEFE_FEFE_FEFE  # every square except column a
NOT_COL_H = 0x7F7F_7F7F_7F7F_7F7F  # every square except column h

# (shift, mask to apply after shifting) for each of the eight directions.
DIRECTIONS: tuple[tuple[int, int], ...] = (
    (+1, NOT_COL_A),  # east
    (-1, NOT_COL_H),  # west
    (+8, ALL_SQUARES),  # south
    (-8, ALL_SQUARES),  # north
    (+9, NOT_COL_A),  # south-east
    (+7, NOT_COL_H),  # south-west
    (-7, NOT_COL_A),  # north-east
    (-9, NOT_COL_H),  # north-west
)

START_BLACK = (1 << 28) | (1 << 35)  # e4, d5 (Black moves first)
START_WHITE = (1 << 27) | (1 << 36)  # d4, e5

COLUMNS = "abcdefgh"

# a run of opponent discs is at most six long, so six steps reach its end
MAX_RUN = 6


def step(discs: int, shift: int, mask: int) -> int:
    if shift > 0:
        return (discs << shift) & ALL_SQUARES & mask
    return (discs >> -shift) & mask


def legal_Moves(me: int, opp: int) -> int:
    """All squares where ``me`` may play, as a bitmask."""
    empty_Squares = ~(me | opp) & ALL_SQUARES
    moves = 0
    for shift, mask in DIRECTIONS:
        # grow a run of opponent discs; an empty square just past it is a legal move
        opponent_Run = step(me, shift, mask) & opp
        for _ in range(MAX_RUN - 1):
            opponent_Run |= step(opponent_Run, shift, mask) & opp
        moves |= step(opponent_Run, shift, mask) & empty_Squares
    return moves


def flips_For_Move(me: int, opp: int, move_Bit: int) -> int:
    """The opponent discs that flip if ``me`` plays ``move_Bit``."""
    flips = 0
    for shift, mask in DIRECTIONS:
        opponent_Run = step(move_Bit, shift, mask) & opp
        for _ in range(MAX_RUN - 1):
            opponent_Run |= step(opponent_Run, shift, mask) & opp
        # the run only flips if one of my discs closes it off at the far end
        if step(opponent_Run, shift, mask) & me:
            flips |= opponent_Run
    return flips


def play(me: int, opp: int, move_Bit: int) -> tuple[int, int]:
    """Play a legal move; returns (my discs, their discs), roles not swapped."""
    flips = flips_For_Move(me, opp, move_Bit)
    return me | move_Bit | flips, opp & ~flips


def iter_Bits(discs: int) -> Iterator[int]:
    while discs:
        lowest = discs & -discs  # isolates the lowest set bit
        yield lowest
        discs ^= lowest


def squares(discs: int) -> list[int]:
    return [bit.bit_length() - 1 for bit in iter_Bits(discs)]


def perft(me: int, opp: int, depth: int) -> int:
    """Count positions reachable in exactly ``depth`` moves; a pass doesn't use up depth."""
    if depth == 0:
        return 1
    moves = legal_Moves(me, opp)
    if not moves:
        if not legal_Moves(opp, me):
            return 1
        return perft(opp, me, depth)
    total = 0
    for move_Bit in iter_Bits(moves):
        my_After, their_After = play(me, opp, move_Bit)
        total += perft(their_After, my_After, depth - 1)
    return total


def square_Name(square: int) -> str:
    if not 0 <= square < 64:
        raise ValueError(f"square out of range: {square}")
    return f"{COLUMNS[square % 8]}{square // 8 + 1}"


def parse_Square(name: str) -> int:
    text = name.strip().lower()
    if len(text) != 2 or text[0] not in COLUMNS or text[1] not in "12345678":
        raise ValueError(f"not a square name: {name!r}")
    return (int(text[1]) - 1) * 8 + COLUMNS.index(text[0])
