"""Engine plugins: one Python file per engine in ``plugins/``, each run in its own worker
process so a runaway engine can be killed without taking the server down."""

from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from othello.core import bitboard as bb

PLUGINS_DIR = Path(
    os.environ.get("OTHELLO_PLUGINS_DIR", Path(__file__).resolve().parents[3] / "plugins")
)
LOAD_TIMEOUT_S = 10.0  # importing a plugin file should take well under a second
MIN_HARD_TIMEOUT_MS = (
    3000  # an engine is killed after 3x its time limit, but never sooner than this
)


class PluginLoadError(Exception):
    """A plugin file couldn't be loaded; the message says why, in plain words."""


class EngineError(Exception):
    """An engine failed while choosing a move. ``kind`` says how."""

    def __init__(self, engine_Name: str, kind: str, reason: str) -> None:
        super().__init__(f"{engine_Name} {reason}")
        self.engine_Name = engine_Name
        self.kind = kind


class PluginEngine:
    def __init__(self, path: Path, min_Hard_Timeout_Ms: int = MIN_HARD_TIMEOUT_MS) -> None:
        self.path = path.resolve()
        self.min_Hard_Timeout_Ms = min_Hard_Timeout_Ms
        self.name = self.path.stem
        self.author = ""
        self.description = ""
        self._process: subprocess.Popen[str] | None = None
        self._replies: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()  # one question at a time per worker

    def start(self) -> None:
        self.close()
        self._process = subprocess.Popen(
            [sys.executable, "-m", "othello.engines.worker", str(self.path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._replies = queue.Queue()
        threading.Thread(
            target=self._read_Replies, args=(self._process, self._replies), daemon=True
        ).start()
        reply = self._next_Reply(LOAD_TIMEOUT_S)
        if reply is None:
            self.close()
            raise PluginLoadError(
                "didn't finish loading within 10 s (is there a loop at the top level?)"
            )
        if reply["status"] != "ready":
            self.close()
            raise PluginLoadError(reply.get("message", "failed to load"))
        self.name, self.author, self.description = (
            reply["name"],
            reply["author"],
            reply["description"],
        )

    @staticmethod
    def _read_Replies(process: subprocess.Popen[str], replies: queue.Queue[str | None]) -> None:
        # reader thread, so waiting for a reply can always time out
        assert process.stdout is not None
        for line in process.stdout:
            replies.put(line)
        replies.put(None)  # end of file: the worker exited

    def _next_Reply(self, timeout_S: float) -> dict | None:
        try:
            line = self._replies.get(timeout=timeout_S)
        except queue.Empty:
            return None
        if line is None:
            return {"status": "crashed"}
        return json.loads(line)

    def is_Running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def close(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.kill()
        self._process.wait()
        self._process = None

    def choose_Move(self, my_Discs: int, opp_Discs: int, time_Limit_Ms: int) -> int:
        with self._lock:
            if not self.is_Running():
                try:
                    self.start()  # it was killed after a timeout, or crashed: try a fresh one
                except (PluginLoadError, OSError) as error:
                    raise EngineError(
                        self.name, "not_loaded", f"can't be restarted: {error}"
                    ) from None
            assert self._process is not None and self._process.stdin is not None
            hard_Timeout_Ms = max(3 * time_Limit_Ms, self.min_Hard_Timeout_Ms)
            request = {"me": my_Discs, "opp": opp_Discs, "time_limit_ms": time_Limit_Ms}
            try:
                self._process.stdin.write(json.dumps(request) + "\n")
                self._process.stdin.flush()
            except OSError:
                self.close()
                raise EngineError(self.name, "crashed", "has stopped running") from None
            reply = self._next_Reply(hard_Timeout_Ms / 1000)

            if reply is None:
                self.close()
                seconds = hard_Timeout_Ms / 1000
                reason = (
                    f"took longer than {seconds:g} s (limit {time_Limit_Ms} ms) and was stopped"
                )
                raise EngineError(self.name, "timeout", reason)
            status = reply["status"]
            if status == "crashed":
                self.close()
                raise EngineError(self.name, "crashed", "has stopped running (the process exited)")
            if status == "raised":
                raise EngineError(self.name, "raised", f"raised {reply['message']}")
            if status == "not_int":
                raise EngineError(self.name, "not_int", reply["message"])

        square = reply["square"]
        legal = bb.squares(bb.legal_Moves(my_Discs, opp_Discs))
        if square not in legal:
            shown = bb.square_Name(square) if 0 <= square < 64 else str(square)
            choices = ", ".join(bb.square_Name(s) for s in legal)
            raise EngineError(
                self.name, "illegal", f"played {shown}, which isn't legal here (legal: {choices})"
            )
        return square


def load_Engine(path: Path, min_Hard_Timeout_Ms: int = MIN_HARD_TIMEOUT_MS) -> PluginEngine:
    if not path.is_file():
        raise PluginLoadError(f"{path} doesn't exist")
    engine = PluginEngine(path, min_Hard_Timeout_Ms)
    engine.start()
    return engine


@dataclass(frozen=True)
class LoadError:
    file: str
    message: str


class EngineCatalog:
    def __init__(
        self, folder: Path = PLUGINS_DIR, min_Hard_Timeout_Ms: int = MIN_HARD_TIMEOUT_MS
    ) -> None:
        self.folder = Path(folder)
        self.min_Hard_Timeout_Ms = min_Hard_Timeout_Ms
        self._engines: dict[str, PluginEngine] = {}
        self._errors: list[LoadError] = []
        self._loaded = False
        self._lock = threading.RLock()
        atexit.register(self.close)

    def reload(self) -> None:
        with self._lock:
            self.close()
            self._errors = []
            files = sorted(self.folder.glob("*.py")) if self.folder.is_dir() else []
            # Files starting with "_" are templates and helpers, not engines.
            for path in (f for f in files if not f.name.startswith("_")):
                started = time.monotonic()
                try:
                    engine = load_Engine(path, self.min_Hard_Timeout_Ms)
                except PluginLoadError as error:
                    self._report(path, str(error))
                    continue
                if engine.name in self._engines:
                    engine.close()
                    first = self._engines[engine.name].path.name
                    self._report(path, f'ENGINE_NAME "{engine.name}" is already used by {first}')
                    continue
                self._engines[engine.name] = engine
                took = time.monotonic() - started
                print(f"[plugins] loaded {path.name} as {engine.name!r} ({took:.2f} s)", flush=True)
            self._loaded = True

    def _report(self, path: Path, message: str) -> None:
        self._errors.append(LoadError(path.name, message))
        print(f"[plugins] could not load {path.name}: {message}", file=sys.stderr, flush=True)

    def _ensure_Loaded(self) -> None:
        with self._lock:
            if not self._loaded:
                self.reload()

    def engines(self) -> list[PluginEngine]:
        self._ensure_Loaded()
        return list(self._engines.values())

    def errors(self) -> list[LoadError]:
        self._ensure_Loaded()
        return list(self._errors)

    def get(self, name: str) -> PluginEngine | None:
        self._ensure_Loaded()
        return self._engines.get(name)

    def close(self) -> None:
        with self._lock:
            for engine in self._engines.values():
                engine.close()
            self._engines = {}
            self._loaded = False
