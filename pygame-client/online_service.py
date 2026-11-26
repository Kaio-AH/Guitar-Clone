"""Serviços online embutidos (v3): Spotify + YouTube + análise local."""
from __future__ import annotations

import hashlib
import os
import shutil
import threading
import time
from typing import Callable

import config
from config import CACHE_DIR, get_ffmpeg_location

StatusCb = Callable[[str], None]
CancelCb = Callable[[], bool]


class OnlineServiceError(Exception):
    pass


_download_locks: dict[str, threading.Lock] = {}
_download_locks_guard = threading.Lock()


def _download_lock(cache_id: str) -> threading.Lock:
    with _download_locks_guard:
        lock = _download_locks.get(cache_id)
        if lock is None:
            lock = threading.Lock()
            _download_locks[cache_id] = lock
        return lock


def _ensure_not_cancelled(should_cancel: CancelCb | None) -> None:
    if should_cancel and should_cancel():
        raise OnlineServiceError("Cancelado.")


def _valid_cached_audio(path: str) -> bool:
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 64 * 1024
    except OSError:
        return False


def spotify_enabled() -> bool:
    return config.spotify_configured()


def _spotify_client():
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials

    if not spotify_enabled():
        raise OnlineServiceError(
            "Spotify não configurado. Abra CONFIG no jogo e informe Client ID e Client Secret, "
            "ou defina-os em %LOCALAPPDATA%\\GuitarClone\\.env."
        )
    mgr = SpotifyClientCredentials(
        client_id=config.SPOTIFY_CLIENT_ID,
        client_secret=config.SPOTIFY_CLIENT_SECRET,
        requests_timeout=10,
    )
    return spotipy.Spotify(client_credentials_manager=mgr, requests_timeout=10)


def search_spotify(query: str, limit: int = 12) -> list[dict]:
    import requests
    import spotipy

    sp = _spotify_client()
    last_error = None
    results = None
    for attempt in range(1, 4):
        try:
            results = sp.search(q=query, limit=limit, type="track")
            break
        except (requests.exceptions.RequestException, spotipy.SpotifyException) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(0.5)
    if results is None:
        raise OnlineServiceError(f"Falha ao buscar no Spotify: {last_error}")

    tracks = []
    for item in results.get("tracks", {}).get("items", []):
        tracks.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "artist": ", ".join([artist.get("name", "") for artist in item.get("artists", [])]),
                "album": (item.get("album") or {}).get("name"),
                "image": ((item.get("album") or {}).get("images") or [{}])[0].get("url"),
                "preview_url": item.get("preview_url"),
                "duration_ms": item.get("duration_ms"),
                "spotify_url": (item.get("external_urls") or {}).get("spotify"),
            }
        )
    return tracks


def _cleanup_partial_files(cache_id: str) -> None:
    try:
        for name in os.listdir(CACHE_DIR):
            if name.startswith(cache_id) and not name.endswith(".mp3"):
                os.remove(os.path.join(CACHE_DIR, name))
    except Exception:
        pass


def _build_ydl_opts(outtmpl: str, player_clients, fmt: str) -> dict:
    opts = {
        "format": fmt,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 20,
        "http_chunk_size": 10 * 1024 * 1024,
    }
    ffmpeg_location = get_ffmpeg_location()
    if ffmpeg_location:
        opts["ffmpeg_location"] = ffmpeg_location
    if player_clients:
        opts["extractor_args"] = {"youtube": {"player_client": player_clients}}

    cookies_file = os.environ.get("YT_COOKIES_FILE")
    cookies_browser = os.environ.get("YT_COOKIES_BROWSER")
    if cookies_file and os.path.exists(cookies_file):
        opts["cookiefile"] = cookies_file
    elif cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)
    return opts


def search_youtube_and_download(query: str, on_status: StatusCb | None = None, should_cancel: CancelCb | None = None) -> tuple[str, str]:
    import yt_dlp

    _ensure_not_cancelled(should_cancel)
    cache_id = hashlib.md5(query.encode()).hexdigest()
    cached_path = os.path.join(CACHE_DIR, f"{cache_id}.mp3")
    if _valid_cached_audio(cached_path):
        return cached_path, cache_id

    with _download_lock(cache_id):
        if _valid_cached_audio(cached_path):
            return cached_path, cache_id

        outtmpl = cached_path.replace(".mp3", ".%(ext)s")
        if on_status:
            on_status("Buscando no YouTube...")
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True, "noplaylist": True}) as ydl:
                result = ydl.extract_info(f"ytsearch1:{query}", download=False)
            entries = (result or {}).get("entries") or []
            if not entries:
                raise OnlineServiceError("Nenhum resultado encontrado no YouTube.")
            video_url = entries[0].get("url") or f"https://www.youtube.com/watch?v={entries[0]['id']}"
        except OnlineServiceError:
            raise
        except Exception as exc:
            raise OnlineServiceError(f"Erro na busca do YouTube: {exc}") from exc

        attempts = [
            (None, "bestaudio[ext=m4a]/bestaudio/best"),
            (["android_vr"], "bestaudio[ext=m4a]/bestaudio/best"),
            (["tv"], "bestaudio/best"),
            (["android_vr", "tv"], "best"),
        ]
        last_error = None
        for i, (clients, fmt) in enumerate(attempts, 1):
            _ensure_not_cancelled(should_cancel)
            try:
                if on_status:
                    on_status(f"Baixando áudio do YouTube (tentativa {i}/{len(attempts)})...")
                with yt_dlp.YoutubeDL(_build_ydl_opts(outtmpl, clients, fmt)) as ydl:
                    ydl.extract_info(video_url, download=True)
                if _valid_cached_audio(cached_path):
                    return cached_path, cache_id
                raise RuntimeError("Arquivo mp3 não foi criado")
            except Exception as exc:
                last_error = exc
                _cleanup_partial_files(cache_id)
                if _valid_cached_audio(cached_path):
                    return cached_path, cache_id
                time.sleep(1)

        if _valid_cached_audio(cached_path):
            return cached_path, cache_id

        ffmpeg_location = get_ffmpeg_location()
        ffmpeg_hint = "" if ffmpeg_location else " ffmpeg não encontrado; instale ffmpeg ou use a versão com ffmpeg embutido."
        raise OnlineServiceError(f"Falha ao baixar áudio do YouTube: {last_error}.{ffmpeg_hint}")


def analyze_youtube(query: str, difficulty: str, on_status: StatusCb | None = None, should_cancel: CancelCb | None = None) -> dict:
    from analysis import analyze_audio_file

    filepath, cache_id = search_youtube_and_download(query, on_status=on_status, should_cancel=should_cancel)
    _ensure_not_cancelled(should_cancel)
    result = analyze_audio_file(filepath, difficulty, on_status=on_status, should_cancel=should_cancel)
    result["cache_id"] = cache_id
    result["audio_path"] = filepath
    return result
