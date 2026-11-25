"""Telas de busca, loading e resultados."""
from __future__ import annotations

import math
import os

import pygame

from config import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    BORDER,
    DIFFICULTIES,
    DIFFICULTY_LABELS,
    GOLD,
    GREEN,
    HEIGHT,
    MUTED,
    ORANGE,
    PANEL,
    PANEL_2,
    RED,
    TEXT,
    WIDTH,
)
from ui import (
    Starfield,
    clamp,
    dim,
    draw_glow,
    draw_pick,
    draw_spinner,
    draw_vinyl,
    font,
    format_time,
    gradient_button,
    gradient_text,
    multiline,
    neon_border,
    panel,
    text,
    truncate,
    wrap,
)

# ------------------------------------------------------------------ layout
SEARCH_PANEL = pygame.Rect(184, 118, 904, 84)
SEARCH_BOX = pygame.Rect(200, 136, 620, 48)
SEARCH_BTN = pygame.Rect(832, 136, 112, 48)
UPLOAD_BTN = pygame.Rect(956, 136, 116, 48)
STATUS_PILL = pygame.Rect(976, 30, 150, 30)
DEMO_BTN = pygame.Rect(1140, 30, 92, 30)
DIFF_RECTS = [pygame.Rect(390 + i * 124, 224, 116, 32) for i in range(4)]
CARD_X, CARD_Y = 60, 300
CARD_W, CARD_H = 373, 84
CARD_GAP_X, CARD_GAP_Y = 20, 8
COLUMNS = 3

GRADE_COLORS = {
    "S": (250, 204, 21),
    "A": (34, 197, 94),
    "B": (34, 211, 238),
    "C": (59, 130, 246),
    "D": (249, 115, 22),
    "F": (239, 68, 68),
}

RESULT_RETRY = pygame.Rect(390, 650, 240, 46)
RESULT_NEW = pygame.Rect(650, 650, 240, 46)
CANCEL_BTN = pygame.Rect(540, 620, 200, 46)


def card_rect(index: int) -> pygame.Rect:
    row, column = divmod(index, COLUMNS)
    return pygame.Rect(
        CARD_X + column * (CARD_W + CARD_GAP_X),
        CARD_Y + row * (CARD_H + CARD_GAP_Y),
        CARD_W,
        CARD_H,
    )


def _draw_background(surface: pygame.Surface, app) -> None:
    surface.blit(app.background, (0, 0))
    app.starfield.draw(surface)


def _draw_brand(surface: pygame.Surface) -> None:
    gradient_text(
        surface,
        "GUITAR CLONE",
        34,
        [(34, 197, 94), (34, 211, 238), (168, 85, 247), (236, 72, 153)],
        (52, 42),
        "midleft",
    )
    text(surface, "PYGAME EDITION", 10, MUTED, (54, 76), "midleft", bold=True)


def _draw_topbar(surface: pygame.Surface, app) -> None:
    _draw_brand(surface)
    _draw_status(surface, app)
    _draw_demo_button(surface, app)
    pygame.draw.line(surface, (34, 36, 54), (0, 100), (WIDTH, 100), 1)


def _draw_header(surface: pygame.Surface, app, title: str, subtitle: str) -> None:
    _draw_brand(surface)
    text(surface, title, 20, TEXT, (WIDTH // 2, 34), "center", bold=True)
    text(surface, subtitle, 10, MUTED, (WIDTH // 2, 58), "center", bold=True)
    pygame.draw.line(surface, (34, 36, 54), (0, 100), (WIDTH, 100), 1)


def _draw_status(surface: pygame.Surface, app) -> None:
    status = app.backend_status
    color = GREEN if status == "online" else RED if status == "offline" else GOLD
    label = "ONLINE" if status == "online" else "OFFLINE" if status == "offline" else "CONECTANDO"
    # Sem pill/borda: fica so o "ping" colorido e o texto.
    draw_glow(surface, color, (STATUS_PILL.x + 15, STATUS_PILL.centery), 14)
    pygame.draw.circle(surface, color, (STATUS_PILL.x + 15, STATUS_PILL.centery), 5)
    text(surface, label, 9, MUTED, (STATUS_PILL.x + 28, STATUS_PILL.centery), "midleft", bold=True)


def _draw_demo_button(surface: pygame.Surface, app) -> None:
    selected = APP_HOVER_DEMO(app)
    panel(surface, DEMO_BTN, mix_panel(selected), 15, ACCENT if selected else BORDER)
    text(surface, "DEMO", 11, ACCENT if selected else MUTED, DEMO_BTN.center, "center", bold=True)


def APP_HOVER_DEMO(app) -> bool:
    return getattr(app, "hover_demo", False)


def mix_panel(hover: bool) -> tuple[int, int, int]:
    return (28, 18, 40) if hover else PANEL


def _draw_search_box(surface: pygame.Surface, app, now: int) -> None:
    state = app.search
    panel(surface, SEARCH_PANEL, (11, 12, 21), 16, BORDER)
    color = ACCENT if state.focused else BORDER
    panel(surface, SEARCH_BOX, (9, 10, 18), 12, color, 2)
    pygame.draw.circle(surface, MUTED, (SEARCH_BOX.x + 26, SEARCH_BOX.y + 22), 8, 2)
    pygame.draw.line(
        surface, MUTED, (SEARCH_BOX.x + 32, SEARCH_BOX.y + 28), (SEARCH_BOX.x + 39, SEARCH_BOX.y + 35), 2
    )
    max_width = SEARCH_BOX.width - 86
    display = state.query
    if not display:
        text(surface, "Buscar no Spotify: artista ou musica", 16, (92, 95, 120), (SEARCH_BOX.x + 52, SEARCH_BOX.centery), "midleft")
    else:
        chosen = font(16)
        while display and chosen.size(display)[0] > max_width:
            display = display[1:]
        text(surface, display, 16, TEXT, (SEARCH_BOX.x + 52, SEARCH_BOX.centery), "midleft")
    if state.focused and (now // 480) % 2 == 0:
        caret_x = SEARCH_BOX.x + 52 + font(16).size(display)[0] + 2
        caret_x = min(caret_x, SEARCH_BOX.right - 16)
        pygame.draw.line(surface, ACCENT_3, (caret_x, SEARCH_BOX.y + 12), (caret_x, SEARCH_BOX.bottom - 12), 2)

    gradient_button(surface, SEARCH_BTN, (168, 85, 247), (219, 39, 119), 12)
    text(surface, "BUSCAR", 13, (255, 255, 255), SEARCH_BTN.center, "center", bold=True)
    panel(surface, UPLOAD_BTN, PANEL_2, 12, BORDER)
    draw_pick(surface, (UPLOAD_BTN.x + 22, UPLOAD_BTN.centery), 20, ACCENT, (230, 230, 250))
    text(surface, "ARQUIVO", 12, TEXT, (UPLOAD_BTN.x + 40, UPLOAD_BTN.centery), "midleft", bold=True)
    text(surface, "U", 9, MUTED, (UPLOAD_BTN.right - 12, UPLOAD_BTN.centery), "center", bold=True)


def _draw_difficulty(surface: pygame.Surface, app) -> None:
    state = app.search
    text(surface, "DIFICULDADE", 9, MUTED, (372, DIFF_RECTS[0].centery), "midright", bold=True)
    for index, (rect, difficulty) in enumerate(zip(DIFF_RECTS, DIFFICULTIES)):
        selected = state.difficulty == difficulty
        hovered = getattr(app, "hover_difficulty", -1) == index
        if selected:
            gradient_button(surface, rect, (147, 51, 234), (219, 39, 119), 16)
            color = (255, 255, 255)
        else:
            panel(surface, rect, (24, 20, 36) if hovered else PANEL, 16, ACCENT if hovered else BORDER)
            color = TEXT if hovered else MUTED
        text(surface, DIFFICULTY_LABELS[difficulty], 10, color, rect.center, "center", bold=True)


def _draw_empty(surface: pygame.Surface, app) -> None:
    box = pygame.Rect(300, 306, 680, 310)
    panel(surface, box, (10, 11, 20), 18, None)
    draw_pick(surface, (box.centerx, box.y + 92), 84, ACCENT, (230, 230, 250))
    text(surface, "PROCURE UMA MUSICA PARA COMECAR", 19, TEXT, (box.centerx, box.y + 168), "center", bold=True)
    if app.offline_mode:
        msg = "Modo offline: busca Spotify/YouTube indisponível, mas upload local funciona."
        msg2 = "Pressione U para analisar um arquivo local, ou F2 para a demo."
        msg3 = "A análise local usa librosa embutido nesta v2."
    else:
        msg = "O backend baixa o audio do YouTube e gera a chart automaticamente."
        msg2 = "Sem backend? Pressione U para análise local ou F2 para demo."
        msg3 = "Uploads usam backend quando disponível e caem para análise local se necessário."
    text(surface, msg, 13, MUTED, (box.centerx, box.y + 202), "center")
    text(surface, msg2, 12, ACCENT_3, (box.centerx, box.y + 234), "center", bold=True)
    text(surface, msg3, 11, (105, 108, 136), (box.centerx, box.y + 262), "center")


def _draw_error(surface: pygame.Surface, app) -> None:
    box = pygame.Rect(260, 318, 760, 200)
    panel(surface, box, (28, 12, 20), 16, RED)
    pygame.draw.circle(surface, RED, (box.x + 36, box.y + 34), 12)
    text(surface, "!", 18, (255, 255, 255), (box.x + 36, box.y + 34), "center", bold=True)
    text(surface, "NAO FOI POSSIVEL COMPLETAR", 16, (255, 170, 170), (box.x + 62, box.y + 24), "midleft", bold=True)
    lines = wrap(app.search.error or "Erro desconhecido.", 13, box.width - 110)
    for index, line in enumerate(lines[:5]):
        text(surface, line, 13, (235, 205, 215), (box.x + 62, box.y + 62 + index * 22))
    hint = "Modo offline: use U (arquivo local) ou F2 (demo)." if app.offline_mode else "Se estiver online, verifique o backend Flask em 127.0.0.1:5000"
    text(surface, hint, 11, MUTED, (box.x + 62, box.bottom - 26))


def _draw_results_grid(surface: pygame.Surface, app) -> None:
    state = app.search
    for index, track in enumerate(state.results[:12]):
        rect = card_rect(index)
        selected = index == state.selected
        hovered = getattr(app, "hover_card", -1) == index
        color = (27, 22, 43) if selected else ((20, 21, 34) if hovered else PANEL)
        panel(surface, rect, color, 11, ACCENT if selected or hovered else BORDER, 2 if selected else 1)
        if selected:
            pygame.draw.rect(surface, ACCENT, (rect.x, rect.y + 14, 4, rect.height - 28), border_radius=2)

        art_rect = pygame.Rect(rect.x + 10, rect.y + 10, 64, 64)
        image = app.images.get(str(track.get("id", "")))
        if image is not None:
            surface.blit(image, art_rect.topleft)
            pygame.draw.rect(surface, (60, 60, 82), art_rect, width=1)
        else:
            panel(surface, art_rect, (19, 16, 30), 8, BORDER)
            draw_pick(surface, art_rect.center, 30, ACCENT, (220, 220, 240))

        title = truncate(track.get("name", "?"), 14, rect.width - 150, True)
        artist = truncate(track.get("artist", ""), 11, rect.width - 150)
        text(surface, title, 14, TEXT, (rect.x + 86, rect.y + 9), bold=True)
        text(surface, artist, 11, MUTED, (rect.x + 86, rect.y + 30))
        duration_ms = int(track.get("duration_ms", 0) or 0)
        text(surface, format_time(duration_ms / 1000.0), 10, (120, 124, 150), (rect.x + 86, rect.y + 52), bold=True)
        text(surface, "SPOTIFY", 8, GREEN, (rect.x + 146, rect.y + 54), bold=True)

        play_center = (rect.right - 28, rect.centery)
        pygame.draw.circle(surface, (32, 25, 50) if not (selected or hovered) else ACCENT, play_center, 16)
        pygame.draw.polygon(
            surface,
            (255, 255, 255),
            [(play_center[0] - 4, play_center[1] - 7), (play_center[0] + 8, play_center[1]), (play_center[0] - 4, play_center[1] + 7)],
        )


def draw_search(surface: pygame.Surface, app, now: int) -> None:
    _draw_background(surface, app)
    _draw_topbar(surface, app)
    _draw_search_box(surface, app, now)
    _draw_difficulty(surface, app)

    state = app.search
    text(surface, "SUAS FAIXAS", 9, MUTED, (60, 282), "midleft", bold=True)
    if state.results:
        text(surface, f"{len(state.results)} resultados  ·  setas para navegar  ·  ENTER para jogar", 9, (105, 108, 136), (150, 282), "midleft")
    elif state.searching:
        text(surface, "BUSCANDO...", 9, ACCENT_3, (150, 282), "midleft", bold=True)
    else:
        text(surface, "DIGITE E APERTE ENTER", 9, (105, 108, 136), (150, 282), "midleft", bold=True)

    if state.searching:
        draw_spinner(surface, (WIDTH // 2, 420), 34, now * 0.25, ACCENT_3)
        text(surface, "Buscando no Spotify...", 15, MUTED, (WIDTH // 2, 474), "center")
    elif state.error:
        _draw_error(surface, app)
    elif not state.results:
        _draw_empty(surface, app)
    else:
        _draw_results_grid(surface, app)

    text(
        surface,
        "ENTER jogar  ·  setas navegar  ·  U upload  ·  F2 demo  ·  F11 tela cheia",
        9,
        (90, 94, 120),
        (WIDTH // 2, 702),
        "center",
        bold=True,
    )


def mix_bg() -> tuple[int, int, int]:
    return (11, 8, 22)


def handle_search_event(app, event: pygame.event.Event) -> None:
    state = app.search
    if event.type == pygame.MOUSEMOTION:
        pos = event.pos
        app.hover_demo = DEMO_BTN.collidepoint(pos)
        app.hover_difficulty = next((i for i, rect in enumerate(DIFF_RECTS) if rect.collidepoint(pos)), -1)
        app.hover_card = next(
            (i for i in range(len(state.results[:12])) if card_rect(i).collidepoint(pos)),
            -1,
        )
        return

    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        pos = event.pos
        if SEARCH_BOX.collidepoint(pos):
            state.focused = True
            pygame.key.start_text_input()
        elif SEARCH_BTN.collidepoint(pos):
            state.focused = False
            pygame.key.stop_text_input()
            app.do_search()
        elif UPLOAD_BTN.collidepoint(pos):
            app.choose_upload()
        elif DEMO_BTN.collidepoint(pos):
            app.start_demo()
        elif any(rect.collidepoint(pos) for rect in DIFF_RECTS):
            index = next(i for i, rect in enumerate(DIFF_RECTS) if rect.collidepoint(pos))
            state.difficulty = DIFFICULTIES[index]
            app.sfx.play("click", 0.5)
        elif state.results:
            index = next((i for i in range(len(state.results[:12])) if card_rect(i).collidepoint(pos)), -1)
            if index >= 0:
                state.selected = index
                app.start_track(state.results[index])
        else:
            state.focused = False
            pygame.key.stop_text_input()
        return

    if event.type == pygame.TEXTINPUT and state.focused:
        addition = "".join(ch for ch in event.text if ch.isprintable())
        if addition and len(state.query) < 90:
            state.query += addition
        return

    if event.type != pygame.KEYDOWN:
        return

    if event.key == pygame.K_ESCAPE:
        if state.focused:
            state.focused = False
            pygame.key.stop_text_input()
        return

    if state.focused:
        if event.key == pygame.K_BACKSPACE:
            state.query = state.query[:-1]
        elif event.key == pygame.K_RETURN:
            state.focused = False
            pygame.key.stop_text_input()
            app.do_search()
        return

    if event.key == pygame.K_RETURN:
        if state.results:
            app.start_track(state.results[state.selected])
        else:
            state.focused = True
            pygame.key.start_text_input()
    elif event.key == pygame.K_TAB:
        state.focused = True
        pygame.key.start_text_input()
    elif event.key == pygame.K_u:
        app.choose_upload()
    elif event.key == pygame.K_F2:
        app.start_demo()
    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
        state.difficulty = DIFFICULTIES[event.key - pygame.K_1]
        app.sfx.play("click", 0.5)
    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
        if state.results:
            count = len(state.results[:12])
            if event.key == pygame.K_LEFT:
                state.selected = (state.selected - 1) % count
            elif event.key == pygame.K_RIGHT:
                state.selected = (state.selected + 1) % count
            elif event.key == pygame.K_UP:
                state.selected = (state.selected - COLUMNS) % count
            else:
                state.selected = (state.selected + COLUMNS) % count
            app.sfx.play("click", 0.35)


# ------------------------------------------------------------------ loading
def draw_loading(surface: pygame.Surface, app, now: int) -> None:
    _draw_background(surface, app)
    loading = app.loading
    angle = now * 0.09
    draw_vinyl(surface, (WIDTH // 2, 244), 84, angle, ACCENT)
    draw_spinner(surface, (WIDTH // 2, 244), 112, -now * 0.32, ACCENT_3)
    text(surface, "PREPARANDO A FAIXA", 26, TEXT, (WIDTH // 2, 58), "center", bold=True)
    text(surface, "O backend baixa, analisa e gera a chart", 12, MUTED, (WIDTH // 2, 92), "center")
    text(surface, truncate(loading.title or "Carregando...", 21, 820, True), 21, ACCENT_3, (WIDTH // 2, 406), "center", bold=True)
    lines = wrap(loading.status or "Aguarde...", 13, 760)
    for index, line in enumerate(lines[:4]):
        text(surface, line, 13, MUTED, (WIDTH // 2, 444 + index * 22), "center")

    bar = pygame.Rect(WIDTH // 2 - 270, 548, 540, 12)
    panel(surface, bar, (18, 18, 30), 6, BORDER)
    if loading.progress is not None:
        fill_width = int(bar.width * clamp(loading.progress))
        if fill_width > 2:
            gradient_button(surface, pygame.Rect(bar.x, bar.y, fill_width, bar.height), (34, 197, 94), (34, 211, 238), 6)
        text(surface, f"{int(clamp(loading.progress) * 100)}%", 10, MUTED, (bar.centerx, bar.y - 18), "center", bold=True)
    else:
        segment = int(bar.width * 0.24)
        travel = math.sin(now * 0.004) * 0.5 + 0.5
        x = bar.x + int((bar.width - segment) * travel)
        gradient_button(surface, pygame.Rect(x, bar.y, segment, bar.height), (168, 85, 247), (236, 72, 153), 6)

    text(
        surface,
        "Primeira execucao baixa o audio e analisa com librosa. Pode levar alguns minutos.",
        11,
        (105, 108, 136),
        (WIDTH // 2, 592),
        "center",
    )
    hovered = getattr(app, "hover_cancel", False)
    panel(surface, CANCEL_BTN, (30, 16, 30) if hovered else PANEL, 12, RED if hovered else BORDER)
    text(surface, "CANCELAR  [ESC]", 12, RED if hovered else MUTED, CANCEL_BTN.center, "center", bold=True)


def handle_loading_event(app, event: pygame.event.Event) -> None:
    if event.type == pygame.MOUSEMOTION:
        app.hover_cancel = CANCEL_BTN.collidepoint(event.pos)
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and CANCEL_BTN.collidepoint(event.pos):
        app.cancel_loading()
    elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        app.cancel_loading()


# ------------------------------------------------------------------ results
def draw_results(surface: pygame.Surface, app, now: int) -> None:
    _draw_background(surface, app)
    session = app.game
    grade = session.grade
    grade_color = GRADE_COLORS.get(grade, MUTED)
    _draw_header(surface, app, "RESULTADOS", "FIM DA MUSICA")

    box = pygame.Rect(170, 108, 940, 520)
    panel(surface, box, (10, 11, 20), 22, BORDER, 2)
    pygame.draw.rect(surface, grade_color, (box.x + 20, box.y, box.width - 40, 3), border_radius=2)

    song_title = truncate(session.title, 26, 600, True)
    text(surface, song_title, 26, TEXT, (box.x + 40, box.y + 34), bold=True)
    text(surface, truncate(session.artist, 14, 520), 14, MUTED, (box.x + 40, box.y + 66))
    text(surface, DIFFICULTY_LABELS.get(session.difficulty, session.difficulty.upper()), 11, ACCENT_3, (box.x + 40, box.y + 88), bold=True)
    text(surface, f"{session.total_notes} notas", 11, MUTED, (box.x + 180, box.y + 88), bold=True)

    # Nota final: apenas a letra, sem circulo ou glow em volta.
    grade_x = box.x + 190
    text(surface, grade, 170, grade_color, (grade_x, box.y + 232), "center", bold=True)
    text(surface, "PRECISAO", 11, MUTED, (grade_x, box.y + 330), "center", bold=True)
    text(surface, f"{session.accuracy:.1f}%", 26, TEXT, (grade_x, box.y + 356), "center", bold=True)
    if session.notes_missed == 0 and session.total_notes > 0:
        badge = pygame.Rect(grade_x - 64, box.y + 130, 128, 26)
        panel(surface, badge, (40, 28, 12), 13, GOLD)
        text(surface, "FULL COMBO!", 11, GOLD, badge.center, "center", bold=True)

    # Metricas: bloco centralizado na metade direita do painel.
    right_x = box.x + 390
    right_center = right_x + 240
    text(surface, "PONTUACAO", 11, MUTED, (right_center, box.y + 112), "center", bold=True)
    text(surface, f"{session.score:,}".replace(",", "."), 46, GOLD, (right_center, box.y + 156), "center", bold=True)

    stats = [
        ("MAX COMBO", f"{session.max_combo}x"),
        ("ACERTOS", str(session.notes_hit)),
        ("ERROS", str(session.notes_missed)),
        ("MULTIPLICADOR", f"{session.stats.max_multiplier}x"),
        ("PERFEITAS", str(session.stats.judgements["PERFECT"])),
        ("HOLDS", str(session.stats.judgements["HOLD"])),
    ]
    for index, (label, value) in enumerate(stats):
        column = index % 2
        row = index // 2
        x = right_x + column * 250
        y = box.y + 230 + row * 66
        panel(surface, pygame.Rect(x, y, 230, 54), (16, 17, 28), 10, (32, 34, 54))
        text(surface, label, 10, MUTED, (x + 115, y + 13), "center", bold=True)
        text(surface, value, 21, TEXT, (x + 115, y + 33), "center", bold=True)

    bar = pygame.Rect(right_x, box.y + 438, 480, 14)
    panel(surface, bar, (18, 18, 30), 7, BORDER)
    judgements = session.stats.judgements
    total = max(1, session.total_notes)
    segments = [
        ("PERFECT", (250, 204, 21)),
        ("GREAT", (34, 197, 94)),
        ("GOOD", (34, 211, 238)),
        ("HOLD", (168, 85, 247)),
        ("BROKEN", (249, 115, 22)),
        ("MISS", (239, 68, 68)),
    ]
    x = bar.x
    for key, color in segments:
        width = int(bar.width * judgements[key] / total)
        if width > 0:
            pygame.draw.rect(surface, color, (x, bar.y, width, bar.height), border_radius=4)
            x += width
    legend_y = bar.bottom + 14
    legend_x = right_x + 12
    for key, color in segments:
        pygame.draw.circle(surface, color, (legend_x + 4, legend_y + 5), 4)
        label = f"{judgements[key]}"
        text(surface, label, 10, MUTED, (legend_x + 13, legend_y), bold=True)
        legend_x += 76

    hover_retry = getattr(app, "hover_retry", False)
    hover_new = getattr(app, "hover_new", False)
    gradient_button(surface, RESULT_RETRY, (168, 85, 247), (219, 39, 119), 13)
    if hover_retry:
        neon_border(surface, RESULT_RETRY, (255, 255, 255), 13)
    text(surface, "JOGAR DE NOVO  [R]", 14, (255, 255, 255), RESULT_RETRY.center, "center", bold=True)
    panel(surface, RESULT_NEW, (28, 22, 42) if hover_new else PANEL, 13, ACCENT if hover_new else BORDER, 2)
    text(surface, "NOVA MUSICA  [N]", 14, TEXT if hover_new else MUTED, RESULT_NEW.center, "center", bold=True)


def handle_results_event(app, event: pygame.event.Event) -> None:
    if event.type == pygame.MOUSEMOTION:
        app.hover_retry = RESULT_RETRY.collidepoint(event.pos)
        app.hover_new = RESULT_NEW.collidepoint(event.pos)
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        if RESULT_RETRY.collidepoint(event.pos):
            app.restart_game()
        elif RESULT_NEW.collidepoint(event.pos):
            app.back_to_search()
    elif event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_r, pygame.K_RETURN):
            app.restart_game()
        elif event.key in (pygame.K_n, pygame.K_ESCAPE):
            app.back_to_search()
