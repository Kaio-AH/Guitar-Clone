"""Ponto de entrada do Guitar Clone - PyGame Edition."""
from __future__ import annotations

import argparse
import os


def _enable_dpi_awareness() -> None:
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Guitar Clone - PyGame Edition")
    parser.add_argument("--demo", action="store_true", help="Inicia direto na faixa demo (sem backend).")
    parser.add_argument("--backend", default=None, help="URL do backend Flask (padrao: env GUITAR_BACKEND_URL).")
    parser.add_argument("--offline", action="store_true", help="Força modo offline (mock): sem Spotify/YouTube.")
    parser.add_argument("--headless", action="store_true", help="Modo de teste sem janela (SDL dummy).")
    args = parser.parse_args()

    if args.headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    if args.offline:
        os.environ["GUITAR_OFFLINE"] = "1"

    _enable_dpi_awareness()
    from app import App
    from config import BACKEND_URL

    app = App(demo=args.demo, backend_url=args.backend or BACKEND_URL, headless=args.headless)
    app.run()


if __name__ == "__main__":
    main()
