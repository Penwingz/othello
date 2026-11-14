# Othello

Othello (Reversi) that runs on your own machine: a Python rules core and local server, with a browser front-end. Play a friend, play an engine, or watch two engines play each other.

## Run it
Needs Python 3.11 or newer.

```bash
python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .
python -m othello
```

That starts the server and opens http://127.0.0.1:8000. Use `--port 9000` for another port or `--no-browser` to skip opening a tab. It only listens on 127.0.0.1 and makes no network requests.

## Add your own engine
An engine is one Python file in `plugins/`.

```bash
cp plugins/_template.py plugins/my_engine.py      # edit ENGINE_NAME and choose_Move
python -m othello.check plugins/my_engine.py      # plays 20 games vs Random and checks the rules
python -m othello.match plugins/my_engine.py plugins/random_engine.py --games 20
```

Press **Reload engines** in the game and it shows up in the Black and White menus. The full guide is in [`plugins/README.md`](plugins/README.md). Plugins run with your permissions, so only use files from people you trust.

## Playing
Black moves first. Place a disc so it traps a line of the other player's discs against one of yours and they flip. Legal squares show a dot. If you can't move you pass; when neither player can, most discs wins.

Keyboard: Tab to the board, arrows to move, Enter or Space to place, U to undo.

## Layout
| Path | What it is |
|---|---|
| `src/othello/core/` | bitboards, rules, game state |
| `src/othello/engines/` | plugin loader and worker process |
| `src/othello/server/` | local API and static file server |
| `plugins/` | engines, one file each |
| `web/` | the browser UI (plain HTML, CSS and JS, works offline) |
