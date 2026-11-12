"""Games in progress, kept in memory. There's one local user, so nothing is saved to disk."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field

from othello.core import Color, GameState, new_Game
from othello.engines import HUMAN


class NothingToUndoError(ValueError):
    pass


@dataclass
class GameSession:
    id: str
    players: dict[Color, str]  # "human" or an engine's name, per colour
    history: list[GameState] = field(default_factory=lambda: [new_Game()])
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def state(self) -> GameState:
        return self.history[-1]

    @property
    def move_Count(self) -> int:
        return len(self.history) - 1

    def is_Human(self, colour: Color) -> bool:
        return self.players[colour] == HUMAN

    def push(self, state: GameState) -> None:
        self.history.append(state)

    def undo_Point(self) -> int | None:
        """Where undo goes back to (an index into history), or None. Against an engine it
        goes back to the last position where a human was to move."""
        if len(self.history) <= 1:
            return None
        if all(self.is_Human(colour) for colour in Color):
            return len(self.history) - 2
        for index in range(len(self.history) - 2, -1, -1):
            to_Move = self.history[index].to_Move
            if to_Move is not None and self.is_Human(to_Move):
                return index
        return None

    def can_Undo(self) -> bool:
        return self.undo_Point() is not None

    def undo(self) -> None:
        index = self.undo_Point()
        if index is None:
            if len(self.history) <= 1:
                raise NothingToUndoError("there is no move to undo")
            raise NothingToUndoError("no earlier position where a human is to move")
        del self.history[index + 1 :]


class SessionStore:
    def __init__(self) -> None:
        self._games: dict[str, GameSession] = {}
        self._lock = threading.Lock()

    def create(self, black: str, white: str, start: GameState | None = None) -> GameSession:
        session = GameSession(
            id=secrets.token_hex(8),
            players={Color.BLACK: black, Color.WHITE: white},
            history=[start or new_Game()],
        )
        with self._lock:
            self._games[session.id] = session
        return session

    def get(self, game_Id: str) -> GameSession | None:
        with self._lock:
            return self._games.get(game_Id)
