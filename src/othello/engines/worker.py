"""Runs one plugin file in its own process: python -m othello.engines.worker <file>.

The server talks to it with one JSON object per line, so if the plugin loops forever
the server can simply kill it."""

from __future__ import annotations

import importlib.util
import inspect
import json
import operator
import sys
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any, TextIO

from othello.core.board_view import BoardView


class ContractError(Exception):
    """The file loaded but doesn't provide what a plugin must provide."""


def load_Module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"othello_plugin_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ContractError(f"can't import {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_Contract(module: ModuleType) -> dict[str, str]:
    name = getattr(module, "ENGINE_NAME", None)
    if name is None:
        raise ContractError("ENGINE_NAME is missing")
    if not isinstance(name, str) or not name.strip():
        raise ContractError("ENGINE_NAME must be a non-empty string")
    if name.strip().lower() == "human":
        raise ContractError('"human" is reserved for people; pick another ENGINE_NAME')

    extras = {}
    for key in ("ENGINE_AUTHOR", "ENGINE_DESCRIPTION"):
        value = getattr(module, key, "")
        if not isinstance(value, str):
            raise ContractError(f"{key} must be a string")
        extras[key] = value.strip()

    choose = getattr(module, "choose_Move", None)
    if choose is None:
        # The capital M is easy to miss, so point at it when it's the likely cause.
        near_Miss = next((n for n in dir(module) if n.lower() == "choose_move"), None)
        hint = f" (found {near_Miss!r}; the name is case-sensitive)" if near_Miss else ""
        raise ContractError(f"choose_Move is missing{hint}")
    if not callable(choose):
        raise ContractError("choose_Move must be a function")
    try:
        inspect.signature(choose).bind(None, 0)
    except TypeError:
        raise ContractError(
            f"choose_Move must take two arguments (board_View, time_Limit_Ms), "
            f"but its signature is {inspect.signature(choose)}"
        ) from None
    except ValueError:
        pass  # builtins without a signature: give them the benefit of the doubt

    return {
        "name": name.strip(),
        "author": extras["ENGINE_AUTHOR"],
        "description": extras["ENGINE_DESCRIPTION"],
    }


def describe_Exception(path: Path) -> str:
    kind, error, tb = sys.exc_info()
    text = traceback.format_exception_only(kind, error)[-1].strip()
    lines_In_Plugin = [f for f in traceback.extract_tb(tb) if Path(f.filename) == path]
    if lines_In_Plugin:
        text += f" ({path.name}, line {lines_In_Plugin[-1].lineno})"
    elif isinstance(error, SyntaxError) and error.lineno:
        text += f" ({path.name}, line {error.lineno})"
    return text


def serve(path: Path, requests: TextIO, replies: TextIO) -> None:
    def send(**message: Any) -> None:
        replies.write(json.dumps(message) + "\n")
        replies.flush()

    try:
        module = load_Module(path)
        info = read_Contract(module)
    except ContractError as error:
        send(status="error", message=str(error))
        return
    except BaseException:  # noqa: BLE001 - anything at import time is the plugin's fault
        send(status="error", message=describe_Exception(path))
        return
    send(status="ready", **info)

    choose_Move = module.choose_Move
    for line in requests:
        request = json.loads(line)
        view = BoardView(request["me"], request["opp"])
        try:
            move = choose_Move(view, request["time_limit_ms"])
        except BaseException:  # noqa: BLE001 - report it, keep serving
            send(status="raised", message=describe_Exception(path))
            continue
        # operator.index accepts real integers (including numpy's) but not 3.0 or "3".
        try:
            if isinstance(move, bool):
                raise TypeError
            square = operator.index(move)
        except TypeError:
            send(status="not_int", message=f"returned {move!r:.60} instead of a square number")
            continue
        send(status="move", square=square)


def main() -> None:
    protocol_Out = sys.stdout
    # A plugin's print() calls go to stderr (the server log) so they can't garble replies.
    sys.stdout = sys.stderr
    serve(Path(sys.argv[1]).resolve(), sys.stdin, protocol_Out)


if __name__ == "__main__":
    main()
