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
        raise MockApiError(
            "Busca no Spotify indisponível no modo offline. "
            "Conecte-se à internet e inicie o backend para buscar músicas, "
            "ou use F2 (demo) / U (arquivo local já analisado em cache)."
        )

    def analyze_youtube(self, query: str, difficulty: str, on_status=None, should_cancel=None) -> dict:
        raise MockApiError(
            "Download/análise do YouTube indisponível no modo offline. "
            "Use F2 para jogar a demo ou conecte o backend online."
        )

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
