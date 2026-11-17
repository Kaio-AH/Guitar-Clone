"""Faixa e chart de demonstracao gerados localmente (funciona sem backend)."""
from __future__ import annotations

import math
import os
import random
import sys
import wave
from array import array

from config import CACHE_DIR

SAMPLE_RATE = 44100
BPM = 128
DURATION = 42.0
BEAT = 60.0 / BPM
BARS = 22
DEMO_TITLE = "Neon Drive"
DEMO_ARTIST = "Demo original"
DEMO_FILE = "demo_neon_drive_v1.wav"


def _clamp(value: int) -> int:
    return -32768 if value < -32768 else 32767 if value > 32767 else value


def _add(buf: array, start: int, sample: int, gain: float = 1.0) -> None:
    if 0 <= start < len(buf):
        buf[start] = _clamp(buf[start] + int(sample * gain))


def _kick(buf: array, start: int) -> None:
    length = min(int(0.22 * SAMPLE_RATE), len(buf) - start)
    for i in range(max(0, length)):
        t = i / SAMPLE_RATE
        phase = 2 * math.pi * (45 * t + (110 / 28) * (1 - math.exp(-28 * t)))
        value = math.sin(phase) * math.exp(-t * 15) * 30000
        _add(buf, start + i, int(value))


def _snare(buf: array, start: int) -> None:
    length = min(int(0.16 * SAMPLE_RATE), len(buf) - start)
    for i in range(max(0, length)):
        t = i / SAMPLE_RATE
        noise = (random.random() * 2 - 1) * 0.72
        body = math.sin(2 * math.pi * 190 * t) * 0.28
        value = (noise + body) * math.exp(-t * 34) * 22000
        _add(buf, start + i, int(value))


def _hat(buf: array, start: int) -> None:
    length = min(int(0.055 * SAMPLE_RATE), len(buf) - start)
    for i in range(max(0, length)):
        t = i / SAMPLE_RATE
        value = (random.random() * 2 - 1) * math.exp(-t * 120) * 5200
        _add(buf, start + i, int(value))


def _crash(buf: array, start: int) -> None:
    length = min(int(0.75 * SAMPLE_RATE), len(buf) - start)
    for i in range(max(0, length)):
        t = i / SAMPLE_RATE
        value = (random.random() * 2 - 1) * math.exp(-t * 7.5) * 9000
        _add(buf, start + i, int(value))


def _tone(buf: array, start: int, frequency: float, duration: float, volume: float, lead: bool = False) -> None:
    length = min(int(duration * SAMPLE_RATE), len(buf) - start)
    for i in range(max(0, length)):
        t = i / SAMPLE_RATE
        attack = min(1.0, t / 0.008)
        envelope = attack * max(0.0, 1.0 - t / duration) ** 2.2
        vibrato = 1.0 + (0.004 * math.sin(2 * math.pi * 5.2 * t) if lead else 0.0)
        sample = math.sin(2 * math.pi * frequency * vibrato * t)
        if not lead:
            sample += 0.34 * math.sin(4 * math.pi * frequency * t)
        _add(buf, start + i, int(sample * envelope * volume * 32767))


def _pad(buf: array, start: int, duration: float, root: float, volume: float) -> None:
    length = min(int(duration * SAMPLE_RATE), len(buf) - start)
    for i in range(max(0, length)):
        t = i / SAMPLE_RATE
        attack = min(1.0, t / 0.22)
        release = max(0.0, 1.0 - max(0.0, t - duration + 0.3) / 0.3)
        envelope = attack * release
        sample = (
            math.sin(2 * math.pi * root * t)
            + 0.55 * math.sin(2 * math.pi * root * 1.5 * t)
            + 0.35 * math.sin(2 * math.pi * root * 2.0 * t)
        ) / 1.9
        _add(buf, start + i, int(sample * envelope * volume * 32767))


def build_demo_audio(path: str) -> None:
    total_samples = int(DURATION * SAMPLE_RATE)
    buffer = array("h", [0]) * total_samples
    chords = [110.0, 87.31, 130.81, 98.0]
    scale = [2.0, 2.5, 3.0, 4.0, 3.0, 2.5]

    for bar in range(BARS):
        bar_start = bar * 4 * BEAT
        root = chords[bar % len(chords)]
        for beat_index in range(4):
            beat_start = bar_start + beat_index * BEAT
            start = int(beat_start * SAMPLE_RATE)
            _kick(buffer, start)
            if beat_index in (1, 3):
                _snare(buffer, start)
            if beat_index == 0 and bar % 2 == 0:
                _crash(buffer, start)
            for half in range(2):
                _hat(buffer, int((beat_start + half * BEAT / 2) * SAMPLE_RATE))
        for eighth in range(8):
            frequency = root if eighth % 4 in (0, 2) else root * 1.5
            _tone(buffer, int((bar_start + eighth * BEAT / 2) * SAMPLE_RATE), frequency, BEAT * 0.42, 0.32)
        if bar >= 4:
            for eighth in (0, 1, 2, 4, 5, 6):
                frequency = root * scale[(eighth + bar) % len(scale)]
                _tone(
                    buffer,
                    int((bar_start + eighth * BEAT / 2) * SAMPLE_RATE),
                    frequency,
                    BEAT * 0.36,
                    0.13,
                    lead=True,
                )
        _pad(buffer, int(bar_start * SAMPLE_RATE), 4 * BEAT, root, 0.09)

    fade_start = int((DURATION - 2.4) * SAMPLE_RATE)
    for i in range(max(0, len(buffer) - fade_start)):
        buffer[fade_start + i] = int(buffer[fade_start + i] * max(0.0, 1.0 - i / (2.4 * SAMPLE_RATE)))

    peak = max((abs(value) for value in buffer), default=0)
    if peak > 30000:
        factor = 30000 / peak
        for i in range(len(buffer)):
            buffer[i] = int(buffer[i] * factor)

    if sys.byteorder == "big":
        buffer.byteswap()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(buffer.tobytes())


def build_demo_chart() -> list[dict]:
    patterns = [
        [0.0, 0.5, 1.0, 2.0, 2.5, 3.0],
        [0.0, 0.5, 1.5, 2.0, 3.0, 3.5],
        [0.0, 1.0, 1.5, 2.5, 3.0, 3.5],
        [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
    ]
    lane_patterns = [
        [0, 2, 1, 3, 2, 0, 3, 1],
        [0, 1, 2, 3, 2, 1, 3, 2],
        [1, 3, 2, 0, 2, 3, 1, 0],
        [0, 2, 3, 1, 2, 0, 3, 1],
    ]
    notes: list[dict] = []
    lane_busy = [0.0, 0.0, 0.0, 0.0]
    note_id = 0

    for bar in range(1, BARS - 1):
        bar_start = bar * 4 * BEAT
        pattern = patterns[bar % len(patterns)]
        lanes = lane_patterns[bar % len(lane_patterns)]
        for index, offset in enumerate(pattern):
            note_time = bar_start + offset * BEAT
            if note_time < 1.2 or note_time > DURATION - 2.0:
                continue
            preferred = lanes[index % len(lanes)]
            lane = preferred
            for shift in range(4):
                candidate = (preferred + shift) % 4
                if lane_busy[candidate] <= note_time:
                    lane = candidate
                    break
            else:
                continue
            is_hold = bar % 4 == 0 and index == len(pattern) - 1
            duration = BEAT * 1.6 if is_hold else 0.0
            notes.append(
                {
                    "id": note_id,
                    "time": round(note_time, 3),
                    "lane": lane,
                    "type": "hold" if is_hold else "tap",
                    "duration": round(duration, 3),
                }
            )
            note_id += 1
            if is_hold:
                lane_busy[lane] = note_time + duration + 0.18
    return notes


def ensure_demo() -> tuple[str, list[dict], str, str, float, float]:
    path = os.path.join(CACHE_DIR, DEMO_FILE)
    if not os.path.exists(path) or os.path.getsize(path) < 500_000:
        build_demo_audio(path)
    return path, build_demo_chart(), DEMO_TITLE, DEMO_ARTIST, DURATION, float(BPM)
