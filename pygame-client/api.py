"""Cliente da API Flask existente (backend.py)."""
from __future__ import annotations

import os
import re
from typing import Callable

import requests

from config import BACKEND_URL, CACHE_DIR, OFFLINE_MODE

StatusCb = Callable[[str], None]
ProgressCb = Callable[[float], None]
CancelCb = Callable[[], bool]


class ApiError(Exception):
    pass


class BackendAPI:
    def __init__(self, base_url: str = BACKEND_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "GuitarClonePyGame/1.0"})
        self.offline = bool(OFFLINE_MODE)

    def _json(self, response: requests.Response) -> dict:
        try:
            data = response.json()
        except ValueError:
            raise ApiError(f"Resposta invalida do backend (HTTP {response.status_code}).")
        if response.status_code >= 400 or not data.get("success", False):
            raise ApiError(data.get("error") or f"Erro HTTP {response.status_code}.")
        return data

    def health(self) -> dict | None:
        if self.offline:
            return None
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=(2.5, 4))
            return response.json()
        except Exception:
            return None

    def search_spotify(self, query: str, limit: int = 12) -> list[dict]:
        response = self.session.get(
            f"{self.base_url}/search/spotify",
            params={"q": query, "limit": limit},
            timeout=(5, 35),
        )
        return self._json(response).get("tracks", [])

    def analyze_youtube(
        self,
        query: str,
        difficulty: str,
        on_status: StatusCb | None = None,
        should_cancel: CancelCb | None = None,
    ) -> dict:
        if on_status:
            on_status("Baixando do YouTube e analisando o audio...\nIsso pode levar alguns minutos na primeira vez.")
        response = self.session.post(
            f"{self.base_url}/analyze/youtube",
            json={"query": query, "difficulty": difficulty},
            timeout=(10, 900),
        )
        if should_cancel and should_cancel():
            raise ApiError("Cancelado.")
        if on_status:
            on_status("Analise concluida. Preparando as notas...")
        return self._json(response)

    def analyze_upload(
        self,
        path: str,
        difficulty: str,
        on_status: StatusCb | None = None,
        should_cancel: CancelCb | None = None,
    ) -> dict:
        if on_status:
            on_status("Enviando arquivo para analise...")
        with open(path, "rb") as handle:
            files = {"file": (os.path.basename(path), handle, "application/octet-stream")}
            response = self.session.post(
                f"{self.base_url}/analyze",
                data={"difficulty": difficulty},
                files=files,
                timeout=(10, 900),
            )
        if should_cancel and should_cancel():
            raise ApiError("Cancelado.")
        if on_status:
            on_status("Analise concluida. Preparando as notas...")
        return self._json(response)

    def download_audio(
        self,
        cache_id: str,
        on_progress: ProgressCb | None = None,
        on_status: StatusCb | None = None,
        should_cancel: CancelCb | None = None,
    ) -> str:
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "", str(cache_id))
        if not safe_id:
            raise ApiError("cache_id invalido.")
        os.makedirs(CACHE_DIR, exist_ok=True)
        destination = os.path.join(CACHE_DIR, f"{safe_id}.mp3")
        if os.path.exists(destination) and os.path.getsize(destination) > 4096:
            if on_progress:
                on_progress(1.0)
            return destination

        if on_status:
            on_status("Baixando o audio para o cache local...")
        temporary = destination + ".part"
        try:
            with self.session.get(
                f"{self.base_url}/stream/{safe_id}", stream=True, timeout=(10, 180)
            ) as response:
                if response.status_code != 200:
                    raise ApiError(f"Nao foi possivel baixar o audio (HTTP {response.status_code}).")
                total = int(response.headers.get("Content-Length", 0) or 0)
                written = 0
                with open(temporary, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if should_cancel and should_cancel():
                            raise ApiError("Cancelado.")
                        if not chunk:
                            continue
                        handle.write(chunk)
                        written += len(chunk)
                        if on_progress and total:
                            on_progress(min(1.0, written / total))
            if os.path.getsize(temporary) < 1024:
                raise ApiError("O audio baixado esta vazio.")
            os.replace(temporary, destination)
            if on_progress:
                on_progress(1.0)
            return destination
        finally:
            if os.path.exists(temporary):
                try:
                    os.remove(temporary)
                except OSError:
                    pass

    def fetch_image(self, url: str) -> bytes:
        response = self.session.get(url, timeout=(5, 15))
        response.raise_for_status()
        return response.content
