"""Carregamento assincrono de capas do Spotify."""
from __future__ import annotations

import io
import threading
from concurrent.futures import ThreadPoolExecutor

import pygame

from api import BackendAPI


class ImageLoader:
    def __init__(self, api: BackendAPI, size: tuple[int, int] = (74, 74)) -> None:
        self.api = api
        self.size = size
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="covers")
        self.futures: dict[str, object] = {}
        self.images: dict[str, pygame.Surface] = {}
        self.lock = threading.Lock()

    def request(self, key: str, url: str | None) -> None:
        if not url:
            return
        with self.lock:
            if key in self.futures or key in self.images:
                return
            self.futures[key] = self.executor.submit(self._fetch, url)

    def _fetch(self, url: str) -> bytes | None:
        try:
            return self.api.fetch_image(url)
        except Exception:
            return None

    def poll(self) -> None:
        done: list[tuple[str, object]] = []
        with self.lock:
            for key, future in list(self.futures.items()):
                if future.done():  # type: ignore[attr-defined]
                    done.append((key, future))
        for key, future in done:
            with self.lock:
                self.futures.pop(key, None)
            try:
                raw = future.result()  # type: ignore[attr-defined]
            except Exception:
                raw = None
            if not raw:
                continue
            try:
                surface = pygame.image.load(io.BytesIO(raw)).convert_alpha()
                surface = pygame.transform.smoothscale(surface, self.size)
                with self.lock:
                    self.images[key] = surface
            except Exception:
                continue

    def get(self, key: str) -> pygame.Surface | None:
        with self.lock:
            return self.images.get(key)
