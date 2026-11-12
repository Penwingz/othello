"""FastAPI app: JSON API under /api and the static web UI at /."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from othello.core import Color, IllegalMoveError, apply
from othello.engines import HUMAN, EngineCatalog, EngineError
from othello.server.schemas import (
    EngineInfoOut,
    EngineMoveRequest,
    EnginesReloaded,
    GameView,
    LoadErrorOut,
    MoveRequest,
    NewGameRequest,
    PlayersRequest,
)
from othello.server.sessions import GameSession, NothingToUndoError, SessionStore

# the web UI lives in the repo's web/ folder
WEB_DIR = Path(__file__).resolve().parents[3] / "web"


def create_App(
    store: SessionStore | None = None,
    web_Dir: Path = WEB_DIR,
    catalog: EngineCatalog | None = None,
) -> FastAPI:
    # no Swagger/ReDoc pages: they load scripts from a CDN
    app = FastAPI(title="Othello", docs_url=None, redoc_url=None, openapi_url="/api/openapi.json")
    app.state.store = store or SessionStore()
    games: SessionStore = app.state.store
    app.state.catalog = catalog or EngineCatalog()
    plugins: EngineCatalog = app.state.catalog

    @app.exception_handler(RequestValidationError)
    async def bad_Request(_: Request, exc: RequestValidationError) -> JSONResponse:
        # malformed bodies are 400s, like illegal moves
        parts = []
        for error in exc.errors():
            field = ".".join(str(part) for part in error["loc"] if part != "body") or "body"
            parts.append(f"{field}: {error['msg']}")
        return JSONResponse({"detail": "; ".join(parts)}, status_code=400)

    def get_Session(game_Id: str) -> GameSession:
        session = games.get(game_Id)
        if session is None:
            raise HTTPException(404, f"no game with id {game_Id!r}")
        return session

    def check_Player(name: str) -> None:
        if name != HUMAN and plugins.get(name) is None:
            known = ", ".join(e.name for e in plugins.engines()) or "none loaded"
            raise HTTPException(400, f"unknown player {name!r}: use 'human' or an engine ({known})")

    def engine_List() -> list[EngineInfoOut]:
        return [
            EngineInfoOut(name=e.name, author=e.author, description=e.description)
            for e in plugins.engines()
        ]

    def error_List() -> list[LoadErrorOut]:
        return [LoadErrorOut(file=e.file, message=e.message) for e in plugins.errors()]

    @app.get("/api/engines", response_model=list[EngineInfoOut])
    def engines() -> list[EngineInfoOut]:
        return engine_List()

    @app.get("/api/engines/errors", response_model=list[LoadErrorOut])
    def engine_Errors() -> list[LoadErrorOut]:
        return error_List()

    @app.post("/api/engines/reload", response_model=EnginesReloaded)
    def reload_Engines() -> EnginesReloaded:
        plugins.reload()
        return EnginesReloaded(engines=engine_List(), errors=error_List())

    @app.post("/api/games", response_model=GameView, status_code=201)
    def create_Game(req: NewGameRequest) -> GameView:
        check_Player(req.black)
        check_Player(req.white)
        return GameView.of(games.create(req.black, req.white))

    @app.post("/api/games/{game_Id}/players", response_model=GameView)
    def set_Players(game_Id: str, req: PlayersRequest) -> GameView:
        session = get_Session(game_Id)
        check_Player(req.black)
        check_Player(req.white)
        with session.lock:
            session.players = {Color.BLACK: req.black, Color.WHITE: req.white}
            return GameView.of(session)

    @app.get("/api/games/{game_Id}", response_model=GameView)
    def get_Game(game_Id: str) -> GameView:
        session = get_Session(game_Id)
        with session.lock:  # never return a view torn between two states
            return GameView.of(session)

    @app.post("/api/games/{game_Id}/move", response_model=GameView)
    def move(game_Id: str, req: MoveRequest) -> GameView:
        session = get_Session(game_Id)
        with session.lock:
            state = session.state
            if state.to_Move is not None and not session.is_Human(state.to_Move):
                raise HTTPException(
                    400, f"it is the engine's turn ({state.to_Move.value}); use engine-move"
                )
            try:
                session.push(apply(state, req.square))
            except IllegalMoveError as exc:
                raise HTTPException(400, str(exc)) from None
            return GameView.of(session)

    @app.post("/api/games/{game_Id}/engine-move", response_model=GameView)
    def engine_Move(game_Id: str, req: EngineMoveRequest | None = None) -> GameView | JSONResponse:
        session = get_Session(game_Id)
        time_Limit_Ms = (req or EngineMoveRequest()).time_limit_ms
        with session.lock:
            state = session.state
            if state.to_Move is None:
                raise HTTPException(400, "the game is over")
            if session.is_Human(state.to_Move):
                raise HTTPException(400, f"{state.to_Move.value} is a human player")
            name = session.players[state.to_Move]
            moves_Before = session.move_Count

        # think without holding the lock so a slow engine doesn't block reads or undo
        engine = plugins.get(name)
        try:
            if engine is None:
                raise EngineError(
                    name, "not_loaded", "isn't loaded any more (removed or failed to reload)"
                )
            view = state.board_View()
            square = engine.choose_Move(view.my_Discs, view.opp_Discs, time_Limit_Ms)
        except EngineError as error:
            # 502: the game server is fine, the engine it relies on failed.
            return JSONResponse(
                {"detail": str(error), "engine": error.engine_Name, "kind": error.kind},
                status_code=502,
            )

        with session.lock:
            if session.move_Count != moves_Before or session.state is not state:
                raise HTTPException(409, "the game changed while the engine was thinking")
            session.push(apply(state, square))
            return GameView.of(session)

    @app.post("/api/games/{game_Id}/undo", response_model=GameView)
    def undo(game_Id: str) -> GameView:
        session = get_Session(game_Id)
        with session.lock:
            try:
                session.undo()
            except NothingToUndoError as exc:
                raise HTTPException(400, str(exc)) from None
            return GameView.of(session)

    if web_Dir.is_dir():
        app.mount("/", StaticFiles(directory=web_Dir, html=True), name="web")
    return app
