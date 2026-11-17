"""Regras de gameplay: notas, acertos, holds, combo e pontuacao."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from chart import prepare_notes
from config import DIFFICULTY_LANES

PERFECT_WINDOW = 0.07
GREAT_WINDOW = 0.14
GOOD_WINDOW = 0.25
HIT_WINDOW = 0.26
COUNTDOWN_SECONDS = 3.0
HOLD_MIN_PROGRESS = 0.90

JUDGEMENT_COLORS = {
    "PERFECT": (250, 204, 21),
    "GREAT": (34, 197, 94),
    "GOOD": (34, 211, 238),
    "HOLD": (168, 85, 247),
    "BROKEN": (249, 115, 22),
    "MISS": (239, 68, 68),
}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return low if value < low else high if value > high else value


@dataclass
class Note:
    id: int
    time: float
    lane: int
    kind: str = "tap"
    duration: float = 0.0
    hit: bool = False
    missed: bool = False
    holding: bool = False
    hold_progress: float = 0.0

    @classmethod
    def from_dict(cls, raw: dict, index: int) -> "Note":
        return cls(
            id=int(raw.get("id", index)),
            time=float(raw.get("time", 0.0)),
            lane=int(raw.get("lane", 0)),
            kind="hold" if raw.get("type") == "hold" or float(raw.get("duration", 0) or 0) > 0 else "tap",
            duration=float(raw.get("duration", 0.0) or 0.0),
        )


@dataclass
class GameEvent:
    kind: str
    lane: int
    note: Note | None = None
    points: int = 0
    judgement: str = ""
    offset: float = 0.0


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: tuple[int, int, int]
    radius: float


@dataclass
class Popup:
    x: float
    y: float
    text: str
    color: tuple[int, int, int]
    life: float = 0.9
    max_life: float = 0.9
    size: int = 22


@dataclass
class SessionStats:
    score: int = 0
    combo: int = 0
    max_combo: int = 0
    multiplier: int = 1
    max_multiplier: int = 1
    notes_hit: int = 0
    notes_missed: int = 0
    judgements: dict[str, int] = field(
        default_factory=lambda: {
            "PERFECT": 0,
            "GREAT": 0,
            "GOOD": 0,
            "HOLD": 0,
            "BROKEN": 0,
            "MISS": 0,
        }
    )


class GameplaySession:
    def __init__(
        self,
        title: str,
        notes_data: list[dict],
        duration: float,
        difficulty: str,
        source: str = "",
        tempo: float = 0.0,
        artist: str = "",
    ) -> None:
        self.title = title
        self.artist = artist
        self.duration = max(1.0, float(duration or 0.0))
        self.difficulty = difficulty
        self.source = source
        self.tempo = float(tempo or 0.0)
        self.lanes = DIFFICULTY_LANES.get(difficulty, 5)
        self.base_notes = [
            Note.from_dict(raw, i)
            for i, raw in enumerate(prepare_notes(notes_data, difficulty))
            if 0 <= int(raw.get("lane", 0)) < self.lanes
        ]
        self.track_data = None
        self.reset()

    # ------------------------------------------------------------------ estado
    def reset(self) -> None:
        self.notes = [
            Note(n.id, n.time, n.lane, n.kind, n.duration) for n in self.base_notes
        ]
        self.total_notes = len(self.notes)
        self.phase = "ready"  # ready | countdown | playing | paused | finished
        self.song_time = 0.0
        self.played_before = 0.0
        self.start_ticks = 0
        self.countdown = 0.0
        self.stats = SessionStats()
        self.pressed: set[int] = set()
        self.active_holds: dict[int, Note] = {}
        self.events: list[GameEvent] = []
        self.particles: list[Particle] = []
        self.popups: list[Popup] = []
        self.lane_flash = [0.0] * 5
        self.shake = 0.0
        self.go_flash = 0.0
        self.combo_banner = 0
        self.combo_banner_time = 0.0
        self.started_event = False
        self.finished_event = False

    @property
    def score(self) -> int:
        return self.stats.score

    @property
    def combo(self) -> int:
        return self.stats.combo

    @property
    def max_combo(self) -> int:
        return self.stats.max_combo

    @property
    def multiplier(self) -> int:
        return self.stats.multiplier

    @property
    def notes_hit(self) -> int:
        return self.stats.notes_hit

    @property
    def notes_missed(self) -> int:
        return self.stats.notes_missed

    @property
    def accuracy(self) -> float:
        if self.total_notes <= 0:
            return 100.0
        j = self.stats.judgements
        units = (
            j["PERFECT"] * 1.0
            + j["GREAT"] * 0.80
            + j["GOOD"] * 0.60
            + j["HOLD"] * 1.0
            + j["BROKEN"] * 0.15
        )
        return clamp(units / self.total_notes * 100.0, 0.0, 100.0)

    @property
    def progress(self) -> float:
        return clamp(self.song_time / self.duration, 0.0, 1.0)

    @property
    def grade(self) -> str:
        acc = self.accuracy
        if acc >= 95:
            return "S"
        if acc >= 90:
            return "A"
        if acc >= 80:
            return "B"
        if acc >= 70:
            return "C"
        if acc >= 60:
            return "D"
        return "F"

    def start_countdown(self) -> None:
        if self.phase == "ready":
            self.phase = "countdown"
            self.countdown = COUNTDOWN_SECONDS

    def pause(self) -> bool:
        if self.phase == "playing":
            self.played_before = self.song_time
            self.phase = "paused"
            return True
        return False

    def resume(self, now_ticks: int) -> None:
        if self.phase == "paused":
            self.start_ticks = now_ticks
            self.phase = "playing"
            for lane, note in list(self.active_holds.items()):
                if lane not in self.pressed:
                    self.active_holds.pop(lane, None)
                    self._finish_hold(note, self.song_time)

    def update(self, dt: float, now_ticks: int) -> None:
        if self.phase == "countdown":
            self.countdown -= dt
            if self.countdown <= 0:
                self.phase = "playing"
                self.song_time = 0.0
                self.played_before = 0.0
                self.start_ticks = now_ticks
                self.started_event = True
                self.go_flash = 0.7
        elif self.phase == "playing":
            self.song_time = self.played_before + max(0, now_ticks - self.start_ticks) / 1000.0
            self._process_notes()
            if self.song_time >= self.duration + 0.6:
                self.phase = "finished"
                self.finished_event = True
            self.go_flash = max(0.0, self.go_flash - dt)

        self.shake = max(0.0, self.shake - dt)
        for i in range(5):
            self.lane_flash[i] = max(0.0, self.lane_flash[i] - dt)
        self.combo_banner_time = max(0.0, self.combo_banner_time - dt)
        self._update_visuals(dt)

    # ------------------------------------------------------------------ input
    def key_down(self, lane: int, now_ticks: int) -> GameEvent | None:
        if self.phase != "playing" or not (0 <= lane < self.lanes):
            return None
        self.pressed.add(lane)
        self.lane_flash[lane] = max(self.lane_flash[lane], 0.10)

        candidates = [
            note
            for note in self.notes
            if note.lane == lane
            and not note.hit
            and not note.missed
            and not note.holding
            and abs(self.song_time - note.time) <= HIT_WINDOW
        ]
        if not candidates:
            return None

        note = min(candidates, key=lambda item: abs(self.song_time - item.time))
        if note.kind == "hold":
            note.holding = True
            self.active_holds[lane] = note
            event = GameEvent("hold_start", lane, note, 1, "HOLD", self.song_time - note.time)
            self.events.append(event)
            return event

        offset = abs(self.song_time - note.time)
        judgement, precision = self._judge(offset)
        points = int(100 * precision * self.stats.multiplier)
        note.hit = True
        self.stats.notes_hit += 1
        self.stats.judgements[judgement] += 1
        self.stats.score += points
        self._add_combo(1)
        event = GameEvent("tap_hit", lane, note, points, judgement, self.song_time - note.time)
        self.events.append(event)
        return event

    def key_up(self, lane: int, now_ticks: int) -> GameEvent | None:
        self.pressed.discard(lane)
        if self.phase != "playing":
            return None
        note = self.active_holds.pop(lane, None)
        if note is not None and note.holding:
            return self._finish_hold(note, self.song_time)
        return None

    def _judge(self, offset: float) -> tuple[str, float]:
        if offset <= PERFECT_WINDOW:
            return "PERFECT", 2.0
        if offset <= GREAT_WINDOW:
            return "GREAT", 1.5
        return "GOOD", 1.2

    # ------------------------------------------------------------------ notas
    def _process_notes(self) -> None:
        for note in self.notes:
            if note.hit or note.missed:
                continue
            if note.holding:
                if note.lane not in self.pressed:
                    if self.active_holds.get(note.lane) is note:
                        self.active_holds.pop(note.lane, None)
                    self._finish_hold(note, self.song_time)
                    continue
                if self.song_time >= note.time + note.duration:
                    if self.active_holds.get(note.lane) is note:
                        self.active_holds.pop(note.lane, None)
                    self._complete_hold(note)
                continue
            if self.song_time > note.time + HIT_WINDOW:
                self._miss(note)

    def _miss(self, note: Note) -> None:
        note.missed = True
        self.stats.notes_missed += 1
        self.stats.judgements["MISS"] += 1
        self._break_combo()
        self.shake = 0.18
        self.events.append(GameEvent("miss", note.lane, note, 0, "MISS", 0.0))

    def _complete_hold(self, note: Note) -> None:
        note.holding = False
        note.hit = True
        note.hold_progress = 1.0
        points = int(200 * self.stats.multiplier)
        self.stats.score += points
        self.stats.notes_hit += 1
        self.stats.judgements["HOLD"] += 1
        self._add_combo(2)
        self.events.append(GameEvent("hold_complete", note.lane, note, points, "HOLD", 0.0))

    def _finish_hold(self, note: Note, at_time: float) -> GameEvent:
        note.holding = False
        progress = clamp((at_time - note.time) / max(0.01, note.duration))
        note.hold_progress = progress
        note.hit = True
        points = int(200 * progress * self.stats.multiplier)
        self.stats.score += points
        if progress >= HOLD_MIN_PROGRESS:
            self.stats.notes_hit += 1
            self.stats.judgements["HOLD"] += 1
            self._add_combo(2)
            event = GameEvent("hold_complete", note.lane, note, points, "HOLD", 0.0)
        else:
            self.stats.notes_missed += 1
            self.stats.judgements["BROKEN"] += 1
            self._break_combo()
            self.shake = 0.12
            event = GameEvent("hold_broken", note.lane, note, points, "BROKEN", 0.0)
        self.events.append(event)
        return event

    def _add_combo(self, amount: int) -> None:
        old = self.stats.combo
        self.stats.combo += amount
        if self.stats.combo > self.stats.max_combo:
            self.stats.max_combo = self.stats.combo
        for milestone in (10, 20, 30, 40, 50, 75, 100, 150, 200, 300):
            if old < milestone <= self.stats.combo:
                self.combo_banner = milestone
                self.combo_banner_time = 1.15
                break
        if self.stats.combo >= 50:
            self.stats.multiplier = 4
        elif self.stats.combo >= 30:
            self.stats.multiplier = 3
        elif self.stats.combo >= 10:
            self.stats.multiplier = 2
        else:
            self.stats.multiplier = 1
        self.stats.max_multiplier = max(self.stats.max_multiplier, self.stats.multiplier)

    def _break_combo(self) -> None:
        self.stats.combo = 0
        self.stats.multiplier = 1

    # ------------------------------------------------------------------ visual
    def spawn_visual(self, event: GameEvent, x: float, y: float) -> None:
        color = JUDGEMENT_COLORS.get(event.judgement, (255, 255, 255))
        if event.kind == "miss":
            self.popups.append(Popup(x, y - 50, "MISS", color, 0.8, 0.8, 24))
            count = 5
        elif event.kind == "hold_broken":
            self.popups.append(Popup(x, y - 50, f"QUEBRADO +{event.points}", color, 0.9, 0.9, 20))
            count = 8
        elif event.kind == "hold_start":
            self.popups.append(Popup(x, y - 46, "HOLD!", color, 0.55, 0.55, 18))
            count = 5
        else:
            self.popups.append(
                Popup(x, y - 54, f"{event.judgement} +{event.points}", color, 0.85, 0.85, 22)
            )
            count = 16 if event.judgement == "PERFECT" else 11 if event.judgement == "GREAT" else 7

        for _ in range(count):
            angle = random.uniform(-math.pi, math.pi)
            speed = random.uniform(50, 250)
            life = random.uniform(0.30, 0.75)
            self.particles.append(
                Particle(
                    x=x + random.uniform(-8, 8),
                    y=y + random.uniform(-6, 6),
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed - 60,
                    life=life,
                    max_life=life,
                    color=color,
                    radius=random.uniform(1.8, 4.6),
                )
            )
        if len(self.particles) > 700:
            self.particles = self.particles[-700:]
        if len(self.popups) > 40:
            self.popups = self.popups[-40:]

    def _update_visuals(self, dt: float) -> None:
        for particle in self.particles:
            particle.life -= dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.vy += 430 * dt
        self.particles = [p for p in self.particles if p.life > 0]
        for popup in self.popups:
            popup.life -= dt
            popup.y -= 48 * dt
        self.popups = [p for p in self.popups if p.life > 0]

    def drain_events(self) -> list[GameEvent]:
        events = self.events
        self.events = []
        return events
