"""Helpers de desenho e identidade visual."""
from __future__ import annotations

import math
import random
from functools import lru_cache

import pygame

from config import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    BG_BOTTOM,
    BG_TOP,
    BORDER,
    GOLD,
    GREEN,
    MUTED,
    PANEL,
    PANEL_2,
    RED,
    TEXT,
)

FONT_NAMES = "Segoe UI,Trebuchet MS,Arial,Helvetica"
_fonts: dict[tuple[int, bool], pygame.font.Font] = {}


def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (max(8, int(size)), bool(bold))
    cached = _fonts.get(key)
    if cached is None:
        cached = pygame.font.SysFont(FONT_NAMES, key[0], bold=key[1])
        _fonts[key] = cached
    return cached


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return low if value < low else high if value > high else value


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = clamp(t)
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def gradient_color(colors: list[tuple[int, int, int]], t: float) -> tuple[int, int, int]:
    if not colors:
        return (255, 255, 255)
    if len(colors) == 1:
        return colors[0]
    t = clamp(t)
    scaled = t * (len(colors) - 1)
    index = min(int(scaled), len(colors) - 2)
    return mix(colors[index], colors[index + 1], scaled - index)


def text(
    surface: pygame.Surface,
    value: str,
    size: int,
    color: tuple[int, int, int],
    pos: tuple[float, float],
    anchor: str = "topleft",
    bold: bool = False,
    alpha: int = 255,
    shadow: tuple[int, int, int] | None = None,
    shadow_offset: tuple[int, int] = (0, 2),
) -> pygame.Rect:
    rendered = font(size, bold).render(str(value), True, color)
    if alpha < 255:
        rendered = rendered.copy()
        rendered.set_alpha(alpha)
    rect = rendered.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    if shadow is not None:
        shadow_surf = font(size, bold).render(str(value), True, shadow)
        if alpha < 255:
            shadow_surf = shadow_surf.copy()
            shadow_surf.set_alpha(alpha)
        surface.blit(shadow_surf, rect.move(*shadow_offset))
    surface.blit(rendered, rect)
    return rect


def multiline(
    surface: pygame.Surface,
    value: str,
    size: int,
    color: tuple[int, int, int],
    pos: tuple[float, float],
    anchor: str = "topleft",
    bold: bool = False,
    line_gap: int = 4,
    alpha: int = 255,
) -> pygame.Rect:
    lines = str(value).split("\n")
    heights = [font(size, bold).get_height() for _ in lines]
    total = sum(heights) + line_gap * max(0, len(lines) - 1)
    widths = [font(size, bold).size(line)[0] for line in lines]
    width = max(widths) if widths else 0
    rect = pygame.Rect(0, 0, width, total)
    setattr(rect, anchor, (int(pos[0]), int(pos[1])))
    y = rect.top
    for line, height in zip(lines, heights):
        text(surface, line, size, color, (rect.centerx, y), "midtop", bold, alpha)
        y += height + line_gap
    return rect


def truncate(value: str, size: int, max_width: int, bold: bool = False) -> str:
    value = str(value)
    chosen = font(size, bold)
    if chosen.size(value)[0] <= max_width:
        return value
    result = value
    while result and chosen.size(result + "...")[0] > max_width:
        result = result[:-1]
    return result.rstrip() + "..."


def wrap(value: str, size: int, max_width: int, bold: bool = False) -> list[str]:
    chosen = font(size, bold)
    lines: list[str] = []
    for paragraph in str(value).split("\n"):
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            if chosen.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    return lines


def gradient_text(
    surface: pygame.Surface,
    value: str,
    size: int,
    colors: list[tuple[int, int, int]],
    pos: tuple[float, float],
    anchor: str = "center",
    bold: bool = True,
    alpha: int = 255,
) -> pygame.Rect:
    mask = font(size, bold).render(str(value), True, (255, 255, 255))
    width, height = mask.get_size()
    gradient = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(height):
        pygame.draw.line(gradient, gradient_color(colors, y / max(1, height - 1)), (0, y), (width, y))
    gradient.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    if alpha < 255:
        gradient.set_alpha(alpha)
    rect = gradient.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    surface.blit(gradient, rect)
    return rect


def panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int] = PANEL,
    radius: int = 12,
    border: tuple[int, int, int] | None = BORDER,
    border_width: int = 1,
) -> None:
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border is not None:
        pygame.draw.rect(surface, border, rect, width=border_width, border_radius=radius)


@lru_cache(maxsize=128)
def rounded_gradient(
    width: int,
    height: int,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
    radius: int,
) -> pygame.Surface:
    gradient = pygame.Surface((width, height)).convert()
    for y in range(height):
        pygame.draw.line(gradient, mix(top, bottom, y / max(1, height - 1)), (0, y), (width, y))
    mask = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    gradient = gradient.convert_alpha()
    gradient.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return gradient


def gradient_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
    radius: int = 12,
) -> None:
    surface.blit(rounded_gradient(rect.width, rect.height, top, bottom, radius), rect.topleft)


@lru_cache(maxsize=512)
def _glow_surface(color: tuple[int, int, int], radius: int) -> pygame.Surface:
    radius = max(4, int(radius))
    size = radius * 3
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    center = size // 2
    layers = 15
    for i in range(layers, 0, -1):
        r = max(1, int(radius * i / layers))
        alpha = int(6 + 58 * (1.0 - i / layers) ** 1.7)
        pygame.draw.circle(surf, (color[0], color[1], color[2], alpha), (center, center), r)
    return surf


def draw_glow(
    surface: pygame.Surface,
    color: tuple[int, int, int],
    center: tuple[float, float],
    radius: float,
    additive: bool = True,
) -> None:
    cached = _glow_surface((int(color[0]), int(color[1]), int(color[2])), int(radius))
    flags = pygame.BLEND_RGBA_ADD if additive else 0
    surface.blit(cached, cached.get_rect(center=(int(center[0]), int(center[1]))), special_flags=flags)


@lru_cache(maxsize=8)
def _dim_surface(size: tuple[int, int], alpha: int) -> pygame.Surface:
    overlay = pygame.Surface(size, pygame.SRCALPHA)
    overlay.fill((0, 0, 0, alpha))
    return overlay


def dim(surface: pygame.Surface, alpha: int = 160) -> None:
    surface.blit(_dim_surface(surface.get_size(), int(alpha)), (0, 0))


def draw_vinyl(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    angle: float,
    accent: tuple[int, int, int] = ACCENT,
) -> None:
    cx, cy = center
    draw_glow(surface, accent, center, radius * 1.22)
    pygame.draw.circle(surface, (8, 8, 13), center, radius)
    pygame.draw.circle(surface, (34, 34, 46), center, radius, 2)
    for index in range(1, 7):
        pygame.draw.circle(surface, (38, 38, 50), center, int(radius * (0.34 + index * 0.09)), 1)
    radians = math.radians(angle)
    shine = (cx + math.cos(radians) * radius * 0.82, cy + math.sin(radians) * radius * 0.82)
    pygame.draw.line(surface, (96, 96, 124), center, shine, 2)
    pygame.draw.circle(surface, mix(accent, (255, 255, 255), 0.15), center, int(radius * 0.30))
    pygame.draw.circle(surface, (245, 245, 255), center, int(radius * 0.30), 2)
    dot = (
        cx + math.cos(radians) * radius * 0.15,
        cy + math.sin(radians) * radius * 0.15,
    )
    pygame.draw.circle(surface, (18, 18, 28), (int(dot[0]), int(dot[1])), 4)
    pygame.draw.circle(surface, (245, 245, 255), center, 3)


def draw_spinner(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    angle: float,
    color: tuple[int, int, int] = ACCENT_3,
) -> None:
    rect = pygame.Rect(center[0] - radius, center[1] - radius, radius * 2, radius * 2)
    for index in range(3):
        start = math.radians(angle + index * 120)
        pygame.draw.arc(surface, color, rect, start, start + math.radians(62), 4)


def draw_pick(
    surface: pygame.Surface,
    center: tuple[int, int],
    size: int,
    color: tuple[int, int, int] = ACCENT,
    border: tuple[int, int, int] = (255, 255, 255),
) -> None:
    cx, cy = center
    points = [
        (cx - size * 0.46, cy - size * 0.55),
        (cx + size * 0.46, cy - size * 0.55),
        (cx + size * 0.30, cy + size * 0.10),
        (cx, cy + size * 0.62),
        (cx - size * 0.30, cy + size * 0.10),
    ]
    pygame.draw.polygon(surface, color, points)
    pygame.draw.polygon(surface, border, points, 2)


def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def make_background(width: int, height: int) -> pygame.Surface:
    surface = pygame.Surface((width, height)).convert()
    for y in range(height):
        pygame.draw.line(surface, mix(BG_TOP, BG_BOTTOM, y / max(1, height - 1)), (0, y), (width, y))

    glows = pygame.Surface((width, height), pygame.SRCALPHA)
    _blob(glows, (120, 30, 200, 78), (width * 0.13, height * 0.08), 560)
    _blob(glows, (10, 120, 160, 50), (width * 0.90, height * 0.16), 500)
    _blob(glows, (200, 40, 120, 42), (width * 0.78, height * 0.92), 520)
    for offset in range(-height, width, 220):
        pygame.draw.line(glows, (255, 255, 255, 5), (offset, height), (offset + height, 0), 1)
    surface.blit(glows, (0, 0))

    vignette = pygame.Surface((width, height), pygame.SRCALPHA)
    for index in range(18):
        alpha = int(4 + index * 1.6)
        pygame.draw.rect(
            vignette,
            (0, 0, 0, alpha),
            pygame.Rect(-index * 8, -index * 8, width + index * 16, height + index * 16),
            width=16,
        )
    surface.blit(vignette, (0, 0))
    return surface


def _blob(
    surface: pygame.Surface,
    color: tuple[int, int, int, int],
    center: tuple[float, float],
    radius: float,
) -> None:
    layers = 24
    for i in range(layers, 0, -1):
        r = int(radius * i / layers)
        alpha = int(color[3] * (1 - i / layers) ** 1.8)
        if alpha <= 0:
            continue
        pygame.draw.circle(surface, (color[0], color[1], color[2], alpha), (int(center[0]), int(center[1])), r)


class Starfield:
    def __init__(self, count: int = 65) -> None:
        self.stars: list[list[float]] = []
        for _ in range(count):
            color_choice = random.random()
            color = (
                random.randint(70, 120) if color_choice < 0.6 else random.randint(110, 170),
                random.randint(70, 140),
                random.randint(120, 210),
            )
            self.stars.append(
                [
                    random.uniform(0, 1280),
                    random.uniform(0, 720),
                    random.uniform(0.8, 2.4),
                    random.uniform(4, 20),
                    color,
                ]
            )

    def update(self, dt: float) -> None:
        for star in self.stars:
            star[1] += star[3] * dt
            if star[1] > 726:
                star[1] = -4
                star[0] = random.uniform(0, 1280)

    def draw(self, surface: pygame.Surface) -> None:
        for x, y, radius, _speed, color in self.stars:
            pygame.draw.circle(surface, color, (int(x), int(y)), int(radius))


def hover_rect(rect: pygame.Rect, mouse: tuple[int, int]) -> bool:
    return rect.collidepoint(mouse)


def neon_border(surface: pygame.Surface, rect: pygame.Rect, color: tuple[int, int, int], radius: int = 12) -> None:
    pygame.draw.rect(surface, mix(color, (0, 0, 0), 0.35), rect.inflate(6, 6), width=2, border_radius=radius + 3)
    pygame.draw.rect(surface, color, rect, width=2, border_radius=radius)


__all__ = [
    "ACCENT",
    "ACCENT_2",
    "ACCENT_3",
    "BORDER",
    "GOLD",
    "GREEN",
    "MUTED",
    "PANEL",
    "PANEL_2",
    "RED",
    "TEXT",
    "Starfield",
    "clamp",
    "dim",
    "draw_glow",
    "draw_pick",
    "draw_spinner",
    "draw_vinyl",
    "font",
    "format_time",
    "gradient_button",
    "gradient_color",
    "gradient_text",
    "hover_rect",
    "make_background",
    "mix",
    "multiline",
    "neon_border",
    "panel",
    "rounded_gradient",
    "text",
    "truncate",
    "wrap",
]
