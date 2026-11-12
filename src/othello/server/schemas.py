"""Request and response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, StrictInt

from othello.core import Color, GameState, bitboard, legal_Squares, score, winner
from othello.server.sessions import GameSession

ColorName = Literal["black", "white"]


class NewGameRequest(BaseModel):
    black: str = "human"
    white: str = "human"


class MoveRequest(BaseModel):
    square: StrictInt = Field(ge=0, le=63)


class EngineMoveRequest(BaseModel):
    time_limit_ms: StrictInt = Field(default=1000, ge=1, le=60_000)


class Score(BaseModel):
    black: int
    white: int


class Players(BaseModel):
    black: str
    white: str


class PlayersRequest(BaseModel):
    black: str
    white: str


class EngineInfoOut(BaseModel):
    name: str
    author: str
    description: str


class LoadErrorOut(BaseModel):
    file: str
    message: str


class EnginesReloaded(BaseModel):
    engines: list[EngineInfoOut]
    errors: list[LoadErrorOut]


class GameView(BaseModel):
    id: str
    board: str = Field(description="64 chars, square 0 (a1) first: '.', 'B' or 'W'")
    to_move: ColorName | None
    legal_moves: list[int]
    score: Score
    last_move: int | None
    last_flips: list[int]
    passed: ColorName | None
    is_over: bool
    winner: Literal["black", "white", "draw"] | None
    players: Players
    move_count: int
    can_undo: bool = Field(description="whether POST /undo would succeed now")

    @classmethod
    def of(cls, session: GameSession) -> GameView:
        s: GameState = session.state
        sc = score(s)
        w = winner(s)
        return cls(
            id=session.id,
            board=s.board_String(),
            to_move=s.to_Move.value if s.to_Move else None,
            legal_moves=legal_Squares(s),
            score=Score(black=sc[Color.BLACK], white=sc[Color.WHITE]),
            last_move=s.last_Move,
            last_flips=bitboard.squares(s.last_Flips),
            passed=s.passed.value if s.passed else None,
            is_over=s.to_Move is None,
            winner=w.value if isinstance(w, Color) else w,
            players=Players(black=session.players[Color.BLACK], white=session.players[Color.WHITE]),
            move_count=session.move_Count,
            can_undo=session.can_Undo(),
        )
