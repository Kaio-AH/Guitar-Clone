"""Aplicacao PyGame: estados, integracao com backend, audio e loop principal."""
from __future__ import annotations

import os
import shutil
import subprocess
import traceback
from dataclasses import dataclass, field

import pygame
import requests

from api import ApiError, BackendAPI
from mock_api import MockApiError, MockBackendAPI
from config import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    BACKEND_URL,
    BASE_DIR,
    CACHE_DIR,
    FPS,
    GOLD,
    HEIGHT,
    MUTED,
    OFFLINE_MODE,
    RED,
    TEXT,
    TITLE,
    USER_DATA_DIR,
    WIDTH,
)
from demo import DEMO_TITLE, ensure_demo
from gameplay import GameplaySession
from highway import RECEPTOR_Y, lane_center_x
from images import ImageLoader
from screens import (
    draw_loading,
    draw_results,
    draw_search,
    handle_loading_event,
    handle_results_event,
    handle_search_event,
)
from scene_game import draw_game, handle_game_event
from sound import Sfx
from tasks import ThreadTask
from ui import (
    Starfield,
    dim,
    draw_glow,
    draw_pick,
    make_background,
    panel,
    text,
    wrap,
)


@dataclass
class SearchState:
    query: str = ""
    focused: bool = False
    results: list[dict] = field(default_factory=list)
    selected: int = 0
    difficulty: str = "medium"
    searching: bool = False
    error: str | None = None


@dataclass
class LoadingState:
    title: str = ""
    status: str = ""
    progress: float | None = None
    task: ThreadTask | None = None
    cancelled: bool = False


@dataclass
class ToastState:
    message: str = ""
    color: tuple[int, int, int] = TEXT
    time: float = 0.0


@dataclass
class TrackData:
    title: str
    artist: str
    audio_path: str
    notes: list[dict]
    duration: float
    difficulty: str
    source: str = ""
    tempo: float = 0.0


def friendly_error(exc: BaseException, offline: bool = False) -> str:
    if isinstance(exc, MockApiError):
        return str(exc)
    if isinstance(exc, requests.exceptions.ConnectionError):
        if offline:
            return "Modo offline: recursos online indisponíveis. Use F2 (demo) ou arquivos em cache."
        return "Backend indisponível. Verifique sua conexão ou inicie o backend local."
    if isinstance(exc, requests.exceptions.Timeout):
        return "O backend demorou demais para responder. Tente novamente."
    return str(exc) or exc.__class__.__name__


def _make_icon() -> pygame.Surface:
    icon = pygame.Surface((64, 64), pygame.SRCALPHA)
    pygame.draw.circle(icon, (24, 16, 38), (32, 32), 31)
    pygame.draw.circle(icon, ACCENT, (32, 32), 30, 2)
    draw_pick(icon, (32, 32), 42, ACCENT, (245, 245, 255))
    return icon


def _ensure_playable(path: str) -> str:
    """Converte formatos que o SDL_mixer pode nao abrir (m4a, flac...)."""
    extension = os.path.splitext(path)[1].lower()
    if extension in {".mp3", ".ogg", ".wav"}:
        return path
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return path
    os.makedirs(CACHE_DIR, exist_ok=True)
    destination = os.path.join(CACHE_DIR, os.path.splitext(os.path.basename(path))[0] + "_play.wav")
    if os.path.exists(destination) and os.path.getsize(destination) > 4096:
        return destination
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", path, "-vn", "-acodec", "pcm_s16le", destination],
            check=True,
            capture_output=True,
            timeout=180,
        )
        if os.path.exists(destination) and os.path.getsize(destination) > 4096:
            return destination
    except Exception:
        pass
    return path


class App:
    def __init__(self, demo: bool = False, backend_url: str = BACKEND_URL, headless: bool = False) -> None:
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
        except Exception:
            pass
        pygame.init()
        pygame.display.set_caption(TITLE)
        flags = pygame.RESIZABLE
        if not headless:
            flags |= pygame.SCALED
        try:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        except pygame.error:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        try:
            pygame.display.set_icon(_make_icon())
        except Exception:
            pass
        pygame.key.set_repeat(0)
        pygame.key.start_text_input()

        self.clock = pygame.time.Clock()
        self.running = True
        self.now = 0
        self.headless = headless

        self.offline_mode = bool(OFFLINE_MODE)
        self.api = MockBackendAPI() if self.offline_mode else BackendAPI(backend_url)
        self.images = ImageLoader(self.api)
        self.sfx = Sfx()
        self.background = make_background(WIDTH, HEIGHT)
        self.starfield = Starfield()
        self.track_layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA).convert_alpha()

        self.search = SearchState()
        self.loading = LoadingState()
        self.toast = ToastState()
        self.state = "search"
        self.game: GameplaySession | None = None
        self.last_track: TrackData | None = None
        self.search_task: ThreadTask | None = None
        self.health_task = None if self.offline_mode else ThreadTask(self.api.health)

        self.backend_status = "offline" if self.offline_mode else "checking"
        self.music_available = pygame.mixer.get_init() is not None
        self.music_loaded = False
        self.music_started = False
        self.audio_error: str | None = None

        self.hover_demo = False
        self.hover_difficulty = -1
        self.hover_card = -1
        self.hover_cancel = False
        self.hover_ready = False
        self.hover_pause_resume = False
        self.hover_pause_restart = False
        self.hover_pause_menu = False
        self.hover_retry = False
        self.hover_new = False

        self.demo_on_start = demo
        self.demo_title = DEMO_TITLE

    # ------------------------------------------------------------------ loop
    def run(self) -> None:
        try:
            self._run_loop()
        except Exception as exc:  # noqa: BLE001 - queremos registrar qualquer falha
            self._report_crash(exc)
        finally:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            pygame.quit()

    def _run_loop(self) -> None:
        if self.demo_on_start:
            self.start_demo()
        while self.running:
            dt = min(0.05, self.clock.tick(FPS) / 1000.0)
            self.now = pygame.time.get_ticks()
            self._pump()
            self._handle_events()
            self._update(dt, self.now)
            self._draw(self.now)
            pygame.display.flip()

    def _report_crash(self, exc: BaseException) -> None:
        traceback.print_exc()
        path = os.path.join(USER_DATA_DIR, "crash.log")
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(traceback.format_exc())
        except OSError:
            path = "crash.log (nao foi possivel gravar)"
        if self.headless:
            return
        try:
            self.screen.blit(self.background, (0, 0))
            dim(self.screen, 225)
            text(self.screen, "ERRO INESPERADO", 34, RED, (WIDTH // 2, 200), "center", bold=True)
            text(
                self.screen,
                "O jogo encontrou um problema e precisou parar.",
                15,
                TEXT,
                (WIDTH // 2, 252),
                "center",
            )
            text(self.screen, f"Detalhes salvos em: {path}", 11, MUTED, (WIDTH // 2, 282), "center")
            lines = wrap(f"{exc.__class__.__name__}: {exc}", 12, 760)
            for index, line in enumerate(lines[:5]):
                text(self.screen, line, 12, (220, 200, 210), (WIDTH // 2, 336 + index * 20), "center")
            text(self.screen, "Pressione ESC para sair", 12, MUTED, (WIDTH // 2, 500), "center", bold=True)
            pygame.display.flip()
            clock = pygame.time.Clock()
            deadline = pygame.time.get_ticks() + 15000
            while pygame.time.get_ticks() < deadline:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        return
                clock.tick(30)
        except Exception:
            pass

    def _pump(self) -> None:
        self.images.poll()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                try:
                    pygame.display.toggle_fullscreen()
                except pygame.error:
                    pass
                continue
            if event.type == pygame.DROPFILE:
                path = getattr(event, "file", "")
                if self.state == "search" and os.path.splitext(path)[1].lower() in {".mp3", ".wav", ".ogg", ".flac", ".m4a"}:
                    self.choose_upload(path)
                continue
            if self.state == "search":
                handle_search_event(self, event)
            elif self.state == "loading":
                handle_loading_event(self, event)
            elif self.state == "game":
                handle_game_event(self, event)
            elif self.state == "results":
                handle_results_event(self, event)

    def _update(self, dt: float, now: int) -> None:
        self.starfield.update(dt)
        self.toast.time = max(0.0, self.toast.time - dt)
        if self.health_task is not None and self.health_task.done:
            if self.health_task.result and not self.health_task.error:
                self.backend_status = "online"
            else:
                self.backend_status = "offline"
                # v1: cai para mock local quando o backend online não responde
                if not self.offline_mode:
                    self.offline_mode = True
                    self.api = MockBackendAPI(reason="backend-unreachable")
            self.health_task = None
        if self.search_task is not None and self.search_task.done:
            task = self.search_task
            self.search_task = None
            self.search.searching = False
            if task.error is not None:
                self.search.error = friendly_error(task.error, self.offline_mode)
            else:
                self.search.results = task.result or []
                self.search.selected = 0
                self.search.error = None
                for track in self.search.results:
                    self.images.request(str(track.get("id", "")), track.get("image"))
        if self.state == "loading" and self.loading.task is not None and self.loading.task.done:
            state = self.loading
            task = state.task
            state.task = None
            if not state.cancelled:
                if task.error is not None:
                    self.state = "search"
                    self.search.error = friendly_error(task.error, self.offline_mode)
                    self.search.focused = False
                    pygame.key.stop_text_input()
                elif task.result is not None:
                    self.enter_game(task.result)
        if self.state == "game" and self.game is not None:
            self._update_game(dt, now)

    def _update_game(self, dt: float, now: int) -> None:
        session = self.game
        assert session is not None
        session.update(dt, now)
        if session.started_event:
            session.started_event = False
            self._play_music()
        for event in session.drain_events():
            self._on_game_event(event, session)
        if session.finished_event:
            session.finished_event = False
            self.finish_game()
            return
        if (
            session.phase == "playing"
            and self.music_started
            and not self.audio_error
            and session.song_time > 3.0
            and not pygame.mixer.music.get_busy()
        ):
            session.phase = "finished"
            self.finish_game()

    def _draw(self, now: int) -> None:
        if self.state == "search":
            draw_search(self.screen, self, now)
        elif self.state == "loading":
            draw_loading(self.screen, self, now)
        elif self.state == "game":
            draw_game(self.screen, self, now)
        elif self.state == "results":
            draw_results(self.screen, self, now)
        self._draw_toast()

    def _draw_toast(self) -> None:
        if self.toast.time <= 0:
            return
        alpha = int(255 * min(1.0, self.toast.time / 0.5))
        chosen = text(self.screen, self.toast.message, 12, self.toast.color, (WIDTH // 2 + 2, HEIGHT - 52 + 2), "center", bold=True, alpha=alpha, shadow=(0, 0, 0))
        box = chosen.inflate(30, 16)
        surface = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(surface, (12, 12, 20, 225), surface.get_rect(), border_radius=10)
        pygame.draw.rect(surface, (*self.toast.color, 180), surface.get_rect(), width=1, border_radius=10)
        self.screen.blit(surface, box.topleft)
        text(self.screen, self.toast.message, 12, self.toast.color, box.center, "center", bold=True, alpha=alpha)

    # ------------------------------------------------------------------ acoes
    def toast_message(self, message: str, color: tuple[int, int, int] = TEXT) -> None:
        self.toast = ToastState(message=message, color=color, time=3.4)

    def do_search(self) -> None:
        query = self.search.query.strip()
        if not query or self.search.searching:
            return
        self.search.searching = True
        self.search.error = None
        self.search.results = []
        self.search.selected = 0
        self.search_task = ThreadTask(lambda: self.api.search_spotify(query, 12))

    def start_track(self, track: dict) -> None:
        if self.state == "loading":
            return
        query = f"{track.get('artist', '')} - {track.get('name', '')}".strip(" -")
        difficulty = self.search.difficulty
        title = str(track.get("name", "Faixa"))
        artist = str(track.get("artist", ""))
        state = LoadingState(
            title=f"{artist} - {title}" if artist else title,
            status="Conectando ao backend...",
        )
        self.loading = state
        self.state = "loading"
        self.search.focused = False
        pygame.key.stop_text_input()
        self.sfx.play("click", 0.5)

        def work() -> TrackData:
            def on_status(message: str) -> None:
                state.status = message

            def on_progress(value: float) -> None:
                state.progress = value

            def cancelled() -> bool:
                return state.cancelled

            result = self.api.analyze_youtube(query, difficulty, on_status, cancelled)
            cache_id = result.get("cache_id")
            if not cache_id:
                raise ApiError("O backend nao retornou o cache_id do audio.")
            on_status("Baixando o audio para o cache local...")
            path = self.api.download_audio(cache_id, on_progress, on_status, cancelled)
            info = result.get("audio_info", {}) or {}
            return TrackData(
                title=title,
                artist=artist,
                audio_path=path,
                notes=result.get("notes", []),
                duration=float(info.get("duration", 0.0) or 0.0),
                difficulty=difficulty,
                source="Spotify / YouTube",
                tempo=float(info.get("tempo", 0.0) or 0.0),
            )

        state.task = ThreadTask(work)

    def choose_upload(self, path: str | None = None) -> None:
        if self.state == "loading":
            return
        if path is None:
            path = self._ask_file()
        if not path:
            return
        extension = os.path.splitext(path)[1].lower()
        if extension not in {".mp3", ".wav", ".ogg", ".flac", ".m4a"}:
            self.toast_message("Formato nao suportado. Use mp3, wav, ogg, flac ou m4a.", RED)
            return
        difficulty = self.search.difficulty
        title = os.path.splitext(os.path.basename(path))[0]
        state = LoadingState(title=title, status="Analisando arquivo local...")
        self.loading = state
        self.state = "loading"
        self.search.focused = False
        pygame.key.stop_text_input()
        self.sfx.play("click", 0.5)

        def work() -> TrackData:
            def on_status(message: str) -> None:
                state.status = message

            def cancelled() -> bool:
                return state.cancelled

            if self.offline_mode:
                from analysis import analyze_audio_file

                result = analyze_audio_file(path, difficulty, on_status=on_status, should_cancel=cancelled)
                source = "Arquivo local (análise offline)"
            else:
                try:
                    result = self.api.analyze_upload(path, difficulty, on_status, cancelled)
                    source = "Upload (backend)"
                except Exception:
                    # fallback local quando backend online falha
                    from analysis import analyze_audio_file

                    on_status("Backend indisponível. Analisando localmente com librosa...")
                    result = analyze_audio_file(path, difficulty, on_status=on_status, should_cancel=cancelled)
                    source = "Arquivo local (análise offline)"

            info = result.get("audio_info", {}) or {}
            playable = _ensure_playable(path)
            return TrackData(
                title=title,
                artist="Arquivo local",
                audio_path=playable,
                notes=result.get("notes", []),
                duration=float(info.get("duration", 0.0) or 0.0),
                difficulty=difficulty,
                source=source,
                tempo=float(info.get("tempo", 0.0) or 0.0),
            )

        state.task = ThreadTask(work)

    def _ask_file(self) -> str | None:
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Escolha um audio",
                filetypes=[
                    ("Audio", "*.mp3 *.wav *.ogg *.flac *.m4a"),
                    ("Todos os arquivos", "*.*"),
                ],
            )
            root.destroy()
            return path or None
        except Exception as exc:
            self.toast_message(f"Nao foi possivel abrir o seletor: {exc}", RED)
            return None

    def start_demo(self) -> None:
        if self.state == "loading":
            return
        state = LoadingState(title=f"{DEMO_TITLE} - faixa demo", status="Sintetizando faixa demo local...")
        self.loading = state
        self.state = "loading"
        self.search.focused = False
        pygame.key.stop_text_input()
        self.sfx.play("click", 0.5)

        def work() -> TrackData:
            state.status = "Gerando bateria, baixo e melodia..."
            path, notes, title, artist, duration, tempo = ensure_demo()
            return TrackData(
                title=title,
                artist=artist,
                audio_path=path,
                notes=notes,
                duration=duration,
                difficulty="medium",
                source="Demo local",
                tempo=tempo,
            )

        state.task = ThreadTask(work)

    def cancel_loading(self) -> None:
        if self.state != "loading":
            return
        self.loading.cancelled = True
        self.loading.task = None
        self.state = "search"
        self.search.focused = False
        self.toast_message("Carregamento cancelado.", MUTED)

    def enter_game(self, data: TrackData) -> None:
        self.last_track = data
        self.game = GameplaySession(
            title=data.title,
            artist=data.artist,
            notes_data=data.notes,
            duration=data.duration,
            difficulty=data.difficulty,
            source=data.source,
            tempo=data.tempo,
        )
        if not self.game.notes:
            self.game = None
            self.state = "search"
            self.search.error = "A analise nao gerou notas jogaveis. Tente outra musica ou dificuldade."
            self.toast_message("Chart vazia. Tente outra faixa.", RED)
            return
        self.game.track_data = data
        self.state = "game"
        self.audio_error = None
        self.music_loaded = False
        self.music_started = False
        self.hover_ready = False
        self._load_music(data.audio_path)

    def _load_music(self, path: str) -> None:
        if not self.music_available:
            self.audio_error = "Mixer de audio indisponivel."
            return
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.72)
            self.music_loaded = True
        except pygame.error:
            converted = _ensure_playable(path)
            if converted != path:
                try:
                    pygame.mixer.music.load(converted)
                    pygame.mixer.music.set_volume(0.72)
                    self.music_loaded = True
                    return
                except pygame.error:
                    pass
            self.audio_error = "Falha ao carregar o audio. O jogo continua sem som."
            self.music_loaded = False

    def _play_music(self) -> None:
        if not self.music_available or not self.music_loaded or self.audio_error:
            return
        try:
            pygame.mixer.music.play()
            self.music_started = True
        except pygame.error as exc:
            self.audio_error = f"Falha ao tocar o audio: {exc}"
            self.music_started = False

    def toggle_pause(self) -> None:
        if self.game is None:
            return
        session = self.game
        if session.phase == "playing":
            session.pause()
            try:
                pygame.mixer.music.pause()
            except pygame.error:
                pass
            self.sfx.play("click", 0.4)
        elif session.phase == "paused":
            session.resume(pygame.time.get_ticks())
            try:
                pygame.mixer.music.unpause()
            except pygame.error:
                pass
            self.sfx.play("click", 0.4)

    def restart_game(self) -> None:
        if self.last_track is None:
            self.back_to_search()
            return
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        self.sfx.play("click", 0.5)
        self.enter_game(self.last_track)

    def finish_game(self) -> None:
        if self.game is None:
            return
        self.game.phase = "finished"
        self.state = "results"
        self.hover_retry = False
        self.hover_new = False
        try:
            pygame.mixer.music.fadeout(900)
        except pygame.error:
            pass
        self.sfx.play("finish", 0.5)

    def back_to_search(self) -> None:
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        self.state = "search"
        self.game = None
        self.music_started = False
        self.search.focused = False
        self.sfx.play("click", 0.4)

    def _on_game_event(self, event, session: GameplaySession) -> None:
        x = lane_center_x(event.lane, RECEPTOR_Y, session.lanes)
        session.spawn_visual(event, x, RECEPTOR_Y)
