"""Start the local server and open the game in a browser."""

from __future__ import annotations

import argparse
import socket
import threading
import webbrowser

import uvicorn

from othello.engines import EngineCatalog
from othello.server.app import create_App

HOST = "127.0.0.1"
BROWSER_DELAY_S = 0.8


def find_Free_Port(preferred: int, attempts: int = 20) -> int:
    """First free port, starting from ``preferred``."""
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((HOST, port))
            except OSError:
                continue
            return port
    raise SystemExit(f"no free port in {preferred}-{preferred + attempts - 1}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="othello", description="Play Othello in your browser.")
    parser.add_argument("--port", type=int, default=8000, help="preferred port (default 8000)")
    parser.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    args = parser.parse_args(argv)

    port = find_Free_Port(args.port)
    url = f"http://{HOST}:{port}/"
    # load plugins now so their errors show up in this terminal
    catalog = EngineCatalog()
    catalog.reload()
    print(f"Othello is running at {url}  (Ctrl+C to stop)", flush=True)
    if not args.no_browser:
        # give uvicorn a moment to start before the browser asks for the page
        threading.Timer(BROWSER_DELAY_S, webbrowser.open, args=(url,)).start()
    uvicorn.run(create_App(catalog=catalog), host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
