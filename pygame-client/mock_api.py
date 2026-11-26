"""Backend mockado para o executável v1.

Permite rodar o jogo sem backend Flask. Recursos online (Spotify/YouTube)
ficam indisponíveis, mas a demo local e arquivos já em cache continuam
funcionando.
"""
from __future__ import annotations

import os
import re

from config import CACHE_DIR


class MockApiError(Exception):
    pass


class MockBackendAPI:
    """Implementa a mesma interface de BackendAPI, mas sem rede."""

    def __init__(self, reason: str = "offline") -> None:
        self.base_url = "mock://local"
        self.reason = reason

    def health(self) -> dict | None:
        return {
            "status": "offline",
            "message": "Guitar Clone v1 - modo offline (demo e cache local)",
            "version": "1.0-mock",
            "spotify_enabled": False,
            "mock": True,
        }

    def search_spotify(self, query: str, limit: int = 12) -> list[dict]:
        import config

        if not config.spotify_configured():
            raise MockApiError(
                "Spotify não configurado. Abra CONFIG no jogo e salve seu Client ID e Client Secret. "
                "O arquivo será criado em %LOCALAPPDATA%\\GuitarClone\\.env."
            )
        try:
            from online_service import OnlineServiceError, search_spotify

            return search_spotify(query, limit)
        except OnlineServiceError as exc:
            raise MockApiError(str(exc)) from exc

    def analyze_youtube(self, query: str, difficulty: str, on_status=None, should_cancel=None) -> dict:
        try:
            from online_service import OnlineServiceError, analyze_youtube

            return analyze_youtube(query, difficulty, on_status=on_status, should_cancel=should_cancel)
        except OnlineServiceError as exc:
            raise MockApiError(str(exc)) from exc

    def analyze_upload(self, path: str, difficulty: str, on_status=None, should_cancel=None) -> dict:
        from analysis import LocalAnalysisError, analyze_audio_file

        try:
            return analyze_audio_file(path, difficulty, on_status=on_status, should_cancel=should_cancel)
        except LocalAnalysisError as exc:
            raise MockApiError(str(exc)) from exc
        except Exception as exc:
            raise MockApiError(f"Falha ao analisar áudio local: {exc}") from exc

    def download_audio(self, cache_id: str, on_progress=None, on_status=None, should_cancel=None) -> str:
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "", str(cache_id))
        if not safe_id:
            raise MockApiError("cache_id invalido.")
        destination = os.path.join(CACHE_DIR, f"{safe_id}.mp3")
        if os.path.exists(destination) and os.path.getsize(destination) > 4096:
            if on_progress:
                on_progress(1.0)
            return destination
        raise MockApiError(
            "Áudio não encontrado no cache local. No modo offline, apenas áudios já baixados anteriormente podem ser reproduzidos."
        )

    def fetch_image(self, url: str) -> bytes:
        raise MockApiError("Capas indisponíveis no modo offline.")
