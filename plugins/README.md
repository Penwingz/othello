# Writing an Othello engine

An engine is **one Python file** in this folder. Drop it in, press **Reload engines** in the game (or restart it), and it appears in the Black/White menus. You can play it, or set it against another engine.

## The quickest start
```bash
cp plugins/_template.py plugins/my_engine.py      # files starting with "_" are ignored
# edit ENGINE_NAME and choose_Move in my_engine.py
python -m othello.check plugins/my_engine.py      # must say PASS before you share it
```

## What your file must contain
```python
ENGINE_NAME = "Short Name"  # required, unique, shown in the menu
ENGINE_AUTHOR = "Who wrote it"  # optional
ENGINE_DESCRIPTION = "One line."  # optional, shown as a tooltip


def choose_Move(board_View, time_Limit_Ms):
    """Return the square (0-63) to play. Must be one of board_View.legal_Moves()."""
```
- You're only asked when you have a legal move. Passes happen automatically.
- `time_Limit_Ms` is how long you should take, roughly. Go past **3×** that (or 3 seconds, whichever is longer) and your engine is stopped and the move counts as a failure.
- Module-level variables survive between moves of the same game run, so you can keep a cache. Don't rely on that across reloads.

## Squares
`index = row*8 + col`, starting at the top-left: `0` = a1, `7` = h1, `19` = d3, `63` = h8.

## `board_View` reference
Everything is from **your** side: "me" is the player to move.

| Call | Gives you |
|---|---|
| `legal_Moves()` | list of square indices you may play |
| `is_Legal(square)` | `True`/`False` |
| `play_Move(square)` | a new `BoardView` after that move, **seen by the other player** (so recursion just works) |
| `pass_Turn()` | same discs, other player to move |
| `is_Game_Over()` | neither side can move |
| `disc_Counts()` | `(mine, theirs)` |
| `empty_Count()` | empty squares left |
| `grid()` | 8 lists of 8: `"me"`, `"opp"` or `"."`; `grid()[row][col]` |
| `square_Name(square)` | `"d3"` and so on |
| `my_Discs`, `opp_Discs` | the raw 64-bit bitboards (bit *i* set = disc on square *i*) if you want speed |

The board never changes under you: `play_Move` returns a new board and leaves the old one alone.

## Testing
- `python -m othello.check plugins/my_engine.py` loads your file, plays 20 games against Random (colours swapped) and reports illegal moves, exceptions, non-integer answers, timeouts, your slowest move and W/D/L. Exit code 0 means PASS. Options: `--games`, `--time-ms`, `--opponent`.
- `python -m othello.match plugins/mine.py plugins/yours.py --games 20 --time-ms 200 --seed 1` plays a quick match: each random opening is played twice with colours swapped. It prints W/D/L and the average disc difference.
- `print()` works. The output goes to the server's terminal, which is handy for debugging.

## Common mistakes
- `choose_move` instead of `choose_Move`. The capital M matters (the checker will point this out).
- Returning `"d3"` or `19.0`. Return the integer `19`.
- Returning a move that isn't in `legal_Moves()`.
- Searching with no clock. Check `time.monotonic()` against `time_Limit_Ms` inside your loop.
- Two files with the same `ENGINE_NAME`. The second one is refused.
- Treating a pass as a move in your search. When `legal_Moves()` is empty, call `pass_Turn()` without using up depth.

## Trust
Your file is imported and **run on this machine** with the same permissions as the game. Each engine runs in its own process so a crash or an endless loop can't take the game down, but that is not a security sandbox. **Only drop in files from people you trust.**
