"""Geometria compartilhada da pista em perspectiva."""
from __future__ import annotations

from config import WIDTH

CX = WIDTH / 2
HORIZON_Y = 150
RECEPTOR_Y = 596
BOTTOM_Y = 674
TOP_WIDTH = 300
BOTTOM_WIDTH = 860
APPROACH = 2.4


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return low if value < low else high if value > high else value


def ease(progress: float) -> float:
    """Movimento praticamente linear: cada nota mantem seu espaco na pista."""
    return clamp(progress)


def y_for_time(note_time: float, song_time: float) -> float:
    """Y na tela para um instante musical (perspectiva)."""
    remaining = note_time - song_time
    progress = clamp(1.0 - remaining / APPROACH)
    return HORIZON_Y + (RECEPTOR_Y - HORIZON_Y) * ease(progress)


def depth_at_y(y: float) -> float:
    return clamp((y - HORIZON_Y) / (RECEPTOR_Y - HORIZON_Y))


def width_at_y(y: float) -> float:
    return TOP_WIDTH + (BOTTOM_WIDTH - TOP_WIDTH) * depth_at_y(y)


def lane_edges(lane: int, y: float, lanes: int) -> tuple[float, float]:
    width = width_at_y(y)
    left = CX - width / 2.0
    lane_width = width / lanes
    return left + lane * lane_width, left + (lane + 1) * lane_width


def lane_center_x(lane: int, y: float, lanes: int) -> float:
    left, right = lane_edges(lane, y, lanes)
    return (left + right) / 2.0


def note_radius_at(y: float) -> float:
    return 9.5 + 15.5 * depth_at_y(y)
