"""Cena de gameplay estilo Guitar Hero / Guitar Flash."""
from __future__ import annotations

import math

import pygame

from config import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    BORDER,
    DIFFICULTY_LABELS,
    GOLD,
    LANE_ALT_KEYS,
    LANE_COLORS,
    LANE_KEYS,
    LANE_LABELS,
    MUTED,
    ORANGE,
    PANEL,
    RED,
    TEXT,
    WIDTH,
)
from highway import (
    APPROACH,
    BOTTOM_Y,
    BOTTOM_WIDTH,
    CX,
    HORIZON_Y,
    RECEPTOR_Y,
    TOP_WIDTH,
    depth_at_y,
    lane_center_x,
    note_radius_at,
    width_at_y,
    y_for_time,
)
from ui import (
    clamp,
    dim,
    gradient_button,
    mix,
    panel,
    text,
    truncate,
)

READY_BTN = pygame.Rect(520, 486, 240, 48)
PAUSE_RESUME = pygame.Rect(490, 330, 300, 46)
PAUSE_RESTART = pygame.Rect(490, 388, 300, 46)
PAUSE_MENU = pygame.Rect(490, 446, 300, 46)

_KEY_TO_LANE = {getattr(pygame, f"K_{k}"): i for i, k in enumerate(LANE_KEYS)}
_KEY_TO_LANE.update({getattr(pygame, f"K_{k}"): i for i, k in enumerate(LANE_ALT_KEYS)})


def _lane_for_key(key: int) -> int | None:
    return _KEY_TO_LANE.get(key)


# ------------------------------------------------------------------ desenho
def draw_game(surface: pygame.Surface, app, now: int) -> None:
    session = app.game
    surface.blit(app.background, (0, 0))

    layer = app.track_layer
    layer.fill((0, 0, 0, 0))
    shake_x = 0
    if session.shake > 0:
        shake_x = int(math.sin(now * 0.085) * 14 * (session.shake / 0.18))

    _draw_highway(layer, session)
    _draw_notes(layer, session)
    _draw_particles(layer, session)
    _draw_popups(layer, session)
    _draw_receptors(layer, session, now)
    surface.blit(layer, (shake_x, 0))

    _draw_hud(surface, session)
    _draw_combo_banner(surface, session)
    _draw_overlays(surface, app, session, now)


def _draw_highway(layer: pygame.Surface, session) -> None:
    lanes = session.lanes
    top_left = CX - TOP_WIDTH / 2
    bottom_left = CX - BOTTOM_WIDTH / 2
    base = [
        (top_left, HORIZON_Y),
        (CX + TOP_WIDTH / 2, HORIZON_Y),
        (CX + BOTTOM_WIDTH / 2, BOTTOM_Y),
        (bottom_left, BOTTOM_Y),
    ]
    pygame.draw.polygon(layer, (26, 26, 36), base)

    top_lane = TOP_WIDTH / lanes
    bottom_lane = BOTTOM_WIDTH / lanes
    for lane in range(lanes):
        points = [
            (top_left + lane * top_lane, HORIZON_Y),
            (top_left + (lane + 1) * top_lane, HORIZON_Y),
            (bottom_left + (lane + 1) * bottom_lane, BOTTOM_Y),
            (bottom_left + lane * bottom_lane, BOTTOM_Y),
        ]
        pygame.draw.polygon(layer, (36, 36, 48) if lane % 2 == 0 else (31, 31, 42), points)
        pygame.draw.line(layer, (54, 54, 72), points[0], points[3], 1)
    pygame.draw.line(layer, (86, 86, 112), (top_left, HORIZON_Y), (bottom_left, BOTTOM_Y), 2)
    pygame.draw.line(
        layer,
        (86, 86, 112),
        (CX + TOP_WIDTH / 2, HORIZON_Y),
        (CX + BOTTOM_WIDTH / 2, BOTTOM_Y),
        2,
    )

    beat = 60.0 / session.tempo if session.tempo > 20 else 0.5
    first = max(0, int(math.ceil(session.song_time / beat)))
    for index in range(first, first + 8):
        beat_time = index * beat
        y = y_for_time(beat_time, session.song_time)
        if y <= HORIZON_Y or y > RECEPTOR_Y + 1:
            continue
        width = width_at_y(y)
        strong = index % 4 == 0
        color = (100, 100, 128) if strong else (52, 52, 70)
        pygame.draw.line(layer, color, (CX - width / 2 + 2, y), (CX + width / 2 - 2, y), 2 if strong else 1)

    width = width_at_y(RECEPTOR_Y)
    pygame.draw.line(layer, (200, 200, 226), (CX - width / 2, RECEPTOR_Y), (CX + width / 2, RECEPTOR_Y), 2)


def _draw_notes(layer: pygame.Surface, session) -> None:
    lanes = session.lanes
    visible = [
        note
        for note in session.notes
        if not note.hit
        and not note.missed
        and note.lane < lanes
        and note.time - session.song_time <= APPROACH + 0.1
    ]
    visible.sort(key=lambda note: y_for_time(note.time, session.song_time))

    for note in visible:
        color = LANE_COLORS[note.lane]
        head_y = RECEPTOR_Y if note.holding else y_for_time(note.time, session.song_time)
        if head_y < HORIZON_Y - 40:
            continue
        head_x = lane_center_x(note.lane, head_y, lanes)

        if note.kind == "hold":
            tail_y = y_for_time(note.time + note.duration, session.song_time)
            tail_y = max(HORIZON_Y, tail_y)
            if note.holding:
                head_y = RECEPTOR_Y
                head_x = lane_center_x(note.lane, head_y, lanes)
            if tail_y < head_y - 2:
                tail_x = lane_center_x(note.lane, tail_y, lanes)
                width_top = note_radius_at(tail_y) * 0.56
                width_bottom = note_radius_at(head_y) * 0.70
                body = [
                    (tail_x - width_top, tail_y),
                    (tail_x + width_top, tail_y),
                    (head_x + width_bottom, head_y),
                    (head_x - width_bottom, head_y),
                ]
                pygame.draw.polygon(layer, mix((12, 12, 20), color, 0.48), body)
                pygame.draw.line(layer, color, body[0], body[3], 2)
                pygame.draw.line(layer, color, body[1], body[2], 2)

        radius = note_radius_at(head_y)
        pygame.draw.circle(layer, (6, 6, 12), (int(head_x), int(head_y)), int(radius + 3))
        pygame.draw.circle(layer, color, (int(head_x), int(head_y)), int(radius))
        pygame.draw.circle(
            layer,
            mix(color, (255, 255, 255), 0.18),
            (int(head_x), int(head_y)),
            max(2, int(radius * 0.58)),
        )
        pygame.draw.circle(layer, (250, 250, 255), (int(head_x), int(head_y)), int(radius), 2)
        if note.kind == "hold":
            pygame.draw.circle(
                layer, (255, 255, 255), (int(head_x), int(head_y)), max(2, int(radius * 0.34)), 2
            )
        highlight = pygame.Rect(
            int(head_x - radius * 0.40),
            int(head_y - radius * 0.52),
            max(2, int(radius * 0.68)),
            max(1, int(radius * 0.32)),
        )
        pygame.draw.ellipse(layer, (255, 255, 255), highlight)

        if note.holding and note.duration > 0:
            progress = clamp((session.song_time - note.time) / note.duration)
            arc_rect = pygame.Rect(
                int(head_x - radius - 10),
                int(head_y - radius - 10),
                int((radius + 10) * 2),
                int((radius + 10) * 2),
            )
            pygame.draw.arc(layer, (255, 255, 255), arc_rect, -math.pi / 2, -math.pi / 2 + math.pi * 2 * progress, 3)


def _draw_receptors(layer: pygame.Surface, session, now: int) -> None:
    lanes = session.lanes
    radius = 31
    for lane in range(lanes):
        color = LANE_COLORS[lane]
        x = lane_center_x(lane, RECEPTOR_Y, lanes)
        pressed = lane in session.pressed
        pygame.draw.circle(layer, (7, 7, 12), (int(x), RECEPTOR_Y), radius + 3)
        if pressed:
            pygame.draw.circle(layer, mix((8, 8, 14), color, 0.55), (int(x), RECEPTOR_Y), radius)
        pygame.draw.circle(layer, color, (int(x), RECEPTOR_Y), radius, 4)
        if pressed:
            pygame.draw.circle(layer, (255, 255, 255), (int(x), RECEPTOR_Y), radius - 6, 2)
        flash = session.lane_flash[lane]
        if flash > 0:
            progress = 1.0 - flash / 0.10
            pygame.draw.circle(
                layer,
                mix(color, (255, 255, 255), 0.35),
                (int(x), RECEPTOR_Y),
                int(radius + 6 + progress * 26),
                max(1, int(3 * (1 - progress))),
            )

        text(
            layer,
            LANE_LABELS[lane],
            13,
            (255, 255, 255) if pressed else color,
            (x, 662),
            "center",
            bold=True,
        )


def _draw_particles(layer: pygame.Surface, session) -> None:
    for particle in session.particles:
        fraction = clamp(particle.life / particle.max_life)
        color = mix((8, 8, 15), particle.color, fraction)
        pygame.draw.circle(
            layer,
            color,
            (int(particle.x), int(particle.y)),
            max(1, int(particle.radius * (0.4 + fraction * 0.8))),
        )


def _draw_popups(layer: pygame.Surface, session) -> None:
    for popup in session.popups:
        fraction = clamp(popup.life / popup.max_life)
        alpha = int(255 * min(1.0, fraction * 1.8))
        text(
            layer,
            popup.text,
            popup.size,
            popup.color,
            (popup.x, popup.y),
            "center",
            bold=True,
            alpha=alpha,
            shadow=(0, 0, 0),
        )


# ------------------------------------------------------------------ HUD
def _draw_hud(surface: pygame.Surface, session) -> None:
    pygame.draw.rect(surface, (8, 9, 15), (0, 0, WIDTH, 78))
    pygame.draw.line(surface, (30, 32, 50), (0, 78), (WIDTH, 78), 1)
    progress = clamp(session.progress)
    if progress > 0:
        gradient_button(surface, pygame.Rect(0, 0, int(WIDTH * progress), 4), (34, 197, 94), (236, 72, 153), 0)

    text(surface, "PONTOS", 9, MUTED, (44, 8), bold=True)
    text(surface, f"{session.score:,}".replace(",", "."), 27, GOLD, (44, 21), bold=True)
    text(surface, f"{session.notes_hit} acertos  ·  {session.notes_missed} erros", 9, MUTED, (44, 58), bold=True)

    title = truncate(session.title, 18, 460, True)
    text(surface, title, 18, TEXT, (WIDTH // 2, 12), "midtop", bold=True)
    subtitle = f"{session.artist}  ·  {DIFFICULTY_LABELS.get(session.difficulty, session.difficulty.upper())}  ·  {session.total_notes} notas"
    text(surface, truncate(subtitle, 10, 560), 10, MUTED, (WIDTH // 2, 38), "midtop")

    text(surface, "COMBO", 9, MUTED, (952, 8), "topright", bold=True)
    combo_color = ACCENT_2 if session.combo > 0 else MUTED
    text(surface, f"{session.combo}x", 27, combo_color, (952, 21), "topright", bold=True)

    panel(surface, pygame.Rect(972, 14, 82, 46), (18, 15, 28), 9, mix(ORANGE, (20, 20, 30), 0.55))
    text(surface, "MULT", 8, MUTED, (1013, 27), "center", bold=True)
    text(surface, f"{session.multiplier}x", 19, ORANGE, (1013, 43), "center", bold=True)
    text(surface, "ESC pausa", 9, (99, 102, 130), (WIDTH - 24, 62), "topright", bold=True)


def _draw_combo_banner(surface: pygame.Surface, session) -> None:
    if session.combo_banner_time <= 0 or session.combo_banner <= 0:
        return
    fraction = clamp(session.combo_banner_time / 1.15)
    alpha = int(255 * min(1.0, fraction * 2.2))
    scale = 1.0 + (1.0 - fraction) * 0.12
    size = int(46 * scale)
    text(
        surface,
        f"{session.combo_banner} COMBO!",
        size,
        (255, 255, 255),
        (WIDTH // 2, 196),
        "center",
        bold=True,
        alpha=alpha,
        shadow=(70, 0, 50),
    )


# ------------------------------------------------------------------ overlays
def _draw_overlays(surface: pygame.Surface, app, session, now: int) -> None:
    if session.go_flash > 0:
        alpha = int(230 * clamp(session.go_flash / 0.7))
        text(surface, "VAI!", 120, (255, 255, 255), (WIDTH // 2, 300), "center", bold=True, alpha=alpha)

    if session.phase == "ready":
        dim(surface, 150)
        box = pygame.Rect(350, 160, 580, 420)
        panel(surface, box, (10, 10, 18), 18, (52, 52, 80), 1)
        pygame.draw.rect(surface, ACCENT, (box.x + 24, box.y, box.width - 48, 3), border_radius=2)
        text(surface, "PRONTO PARA TOCAR?", 24, TEXT, (WIDTH // 2, box.y + 28), "center", bold=True)
        text(surface, truncate(session.title, 17, 500, True), 17, ACCENT_3, (WIDTH // 2, box.y + 64), "center", bold=True)
        text(surface, f"{DIFFICULTY_LABELS.get(session.difficulty, session.difficulty.upper())}  ·  {session.total_notes} notas", 11, MUTED, (WIDTH // 2, box.y + 88), "center")

        text(surface, "TECLAS", 9, MUTED, (WIDTH // 2, box.y + 120), "center", bold=True)
        total_width = session.lanes * 74
        start_x = WIDTH // 2 - total_width // 2 + 37
        for lane in range(session.lanes):
            x = start_x + lane * 74
            color = LANE_COLORS[lane]
            pygame.draw.circle(surface, (8, 8, 14), (x, box.y + 158), 24)
            pygame.draw.circle(surface, color, (x, box.y + 158), 24, 4)
            text(surface, LANE_LABELS[lane], 16, (255, 255, 255), (x, box.y + 158), "center", bold=True)

        text(surface, "A S D J K   ou   1 2 3 4 5", 11, (108, 111, 140), (WIDTH // 2, box.y + 192), "center", bold=True)
        text(surface, "Segure as notas compridas para completar os holds.", 11, MUTED, (WIDTH // 2, box.y + 214), "center")
        if app.audio_error:
            text(surface, "Audio indisponivel: o jogo segue sem som.", 10, RED, (WIDTH // 2, box.y + 238), "center", bold=True)
        hovered = getattr(app, "hover_ready", False)
        gradient_button(surface, READY_BTN, (34, 197, 94) if not hovered else (54, 217, 114), (22, 163, 74), 13)
        text(surface, "COMECAR  [ESPACO]", 14, (255, 255, 255), READY_BTN.center, "center", bold=True)
        text(surface, "ESPACO ou clique no botao", 9, (120, 130, 150), (WIDTH // 2, box.y + 392), "center")
        text(surface, "ESC volta ao menu", 9, (96, 100, 126), (WIDTH // 2, box.y + 406), "center")

    elif session.phase == "countdown":
        dim(surface, 70)
        number = max(1, int(math.ceil(session.countdown)))
        fraction = session.countdown - math.floor(session.countdown)
        size = int(150 + 35 * fraction)
        text(surface, str(number), size, (255, 255, 255), (WIDTH // 2, 340), "center", bold=True, shadow=(0, 40, 70))
        text(surface, "PREPARE-SE", 14, ACCENT_3, (WIDTH // 2, 470), "center", bold=True)

    elif session.phase == "paused":
        dim(surface, 200)
        box = pygame.Rect(430, 180, 420, 340)
        panel(surface, box, (10, 10, 18), 18, (52, 52, 80), 1)
        text(surface, "PAUSA", 30, TEXT, (WIDTH // 2, box.y + 26), "center", bold=True)
        text(surface, truncate(session.title, 13, 350), 13, MUTED, (WIDTH // 2, box.y + 66), "center")
        _pause_button(surface, PAUSE_RESUME, "CONTINUAR  [ESC]", app, "hover_pause_resume", True)
        _pause_button(surface, PAUSE_RESTART, "REINICIAR  [R]", app, "hover_pause_restart")
        _pause_button(surface, PAUSE_MENU, "NOVA MUSICA  [M]", app, "hover_pause_menu")
        text(surface, f"PONTOS {session.score:,}".replace(",", "."), 10, MUTED, (WIDTH // 2, box.y + 314), "center", bold=True)


def _pause_button(surface: pygame.Surface, rect: pygame.Rect, label: str, app, hover_attr: str, primary: bool = False) -> None:
    hovered = getattr(app, hover_attr, False)
    if primary:
        gradient_button(surface, rect, (168, 85, 247), (219, 39, 119), 12)
        color = (255, 255, 255)
    else:
        panel(surface, rect, (27, 22, 40) if hovered else PANEL, 12, ACCENT if hovered else BORDER, 2)
        color = TEXT if hovered else MUTED
    text(surface, label, 13, color, rect.center, "center", bold=True)


# ------------------------------------------------------------------ input
def handle_game_event(app, event: pygame.event.Event) -> None:
    session = app.game
    if session is None:
        return

    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
            if session.phase in ("playing", "paused"):
                app.toggle_pause()
            else:
                app.back_to_search()
            return
        if event.key == pygame.K_p:
            if session.phase in ("playing", "paused"):
                app.toggle_pause()
            return
        if event.key == pygame.K_SPACE and session.phase == "ready":
            session.start_countdown()
            return
        if event.key == pygame.K_r and session.phase in ("paused", "finished"):
            app.restart_game()
            return
        if event.key == pygame.K_m and session.phase == "paused":
            app.back_to_search()
            return
        lane = _lane_for_key(event.key)
        if lane is None:
            return
        if lane < session.lanes and session.phase == "playing":
            session.key_down(lane, pygame.time.get_ticks())
        return

    if event.type == pygame.KEYUP:
        lane = _lane_for_key(event.key)
        if lane is None:
            return
        if lane < session.lanes:
            session.key_up(lane, pygame.time.get_ticks())
        return

    if event.type == pygame.MOUSEMOTION:
        app.hover_ready = READY_BTN.collidepoint(event.pos)
        app.hover_pause_resume = PAUSE_RESUME.collidepoint(event.pos)
        app.hover_pause_restart = PAUSE_RESTART.collidepoint(event.pos)
        app.hover_pause_menu = PAUSE_MENU.collidepoint(event.pos)
        return

    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        if session.phase == "ready" and READY_BTN.collidepoint(event.pos):
            session.start_countdown()
        elif session.phase == "paused":
            if PAUSE_RESUME.collidepoint(event.pos):
                app.toggle_pause()
            elif PAUSE_RESTART.collidepoint(event.pos):
                app.restart_game()
            elif PAUSE_MENU.collidepoint(event.pos):
                app.back_to_search()
