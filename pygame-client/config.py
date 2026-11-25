"""Configuracoes globais do Guitar Clone - PyGame Edition."""
from __future__ import annotations

import os
import sys


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_base_dir() -> str:
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_asset_dir() -> str:
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))


def get_user_data_dir() -> str:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        root = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(root, "GuitarClone")
    os.makedirs(path, exist_ok=True)
    return path


WIDTH = 1280
HEIGHT = 720
FPS = 60
TITLE = "Guitar Clone - PyGame Edition"

BASE_DIR = get_base_dir()
ASSET_DIR = get_asset_dir()
USER_DATA_DIR = get_user_data_dir()
CACHE_DIR = os.path.join(USER_DATA_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

BACKEND_URL = os.environ.get("GUITAR_BACKEND_URL", "http://127.0.0.1:5000").rstrip("/")
OFFLINE_MODE = os.environ.get("GUITAR_OFFLINE", "").strip().lower() in {"1", "true", "yes", "offline"}

LANE_KEYS = ["a", "s", "d", "j", "k"]
LANE_ALT_KEYS = ["1", "2", "3", "4", "5"]
LANE_LABELS = ["A", "S", "D", "J", "K"]
LANE_ALT_LABELS = ["1", "2", "3", "4", "5"]
LANE_COLORS = [
    (34, 197, 94),    # verde
    (239, 68, 68),    # vermelho
    (234, 179, 8),    # amarelo
    (59, 130, 246),   # azul
    (249, 115, 22),   # laranja
]

DIFFICULTIES = ["easy", "medium", "hard", "expert"]
DIFFICULTY_LABELS = {
    "easy": "FACIL",
    "medium": "MEDIO",
    "hard": "DIFICIL",
    "expert": "EXPERT",
}
DIFFICULTY_LANES = {"easy": 3, "medium": 4, "hard": 5, "expert": 5}

# Paleta neon
BG_TOP = (4, 5, 11)
BG_BOTTOM = (13, 8, 26)
PANEL = (13, 14, 23)
PANEL_2 = (20, 21, 34)
BORDER = (42, 44, 68)
TEXT = (242, 242, 255)
MUTED = (142, 145, 176)
ACCENT = (168, 85, 247)
ACCENT_2 = (236, 72, 153)
ACCENT_3 = (34, 211, 238)
GOLD = (250, 204, 21)
RED = (239, 68, 68)
GREEN = (34, 197, 94)
ORANGE = (249, 115, 22)
BLUE = (59, 130, 246)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}
