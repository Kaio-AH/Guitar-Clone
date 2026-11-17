"""Normaliza a chart recebida do backend para deixar a pista legivel.

O backend escolhe um unico lane por instante, mas permite que uma nota longa
(hold) atravesse as notas seguintes do mesmo lane. Isso faz o hold "engolir"
taps e deixa a leitura confusa. Aqui garantimos:

* intervalo minimo entre notas do mesmo lane;
* holds que terminam antes da proxima nota do lane;
* no maximo 2 notas simultaneas (acorde).

A chart nao e alterada no backend: o ajuste acontece so no cliente.
"""
from __future__ import annotations

from config import DIFFICULTY_LANES

# Intervalo minimo entre duas notas do mesmo lane, por dificuldade.
MIN_GAP = {"easy": 0.42, "medium": 0.32, "hard": 0.26, "expert": 0.22}
# Hold menor que isso vira tap (nao da tempo de segurar).
MIN_HOLD = {"easy": 0.46, "medium": 0.36, "hard": 0.32, "expert": 0.28}
# Teto de duracao de um hold e folga antes da proxima nota do lane.
MAX_HOLD = 2.0
HOLD_TAIL_GAP = 0.22
# No maximo duas notas ao mesmo tempo (acorde).
MAX_CHORD = 2
CHORD_WINDOW = 0.03


def prepare_notes(raw_notes: list[dict], difficulty: str) -> list[dict]:
    """Devolve a chart limpa, pronta para virar notas jogaveis."""
    lanes = DIFFICULTY_LANES.get(difficulty, 5)
    gap = MIN_GAP.get(difficulty, MIN_GAP["medium"])
    min_hold = MIN_HOLD.get(difficulty, MIN_HOLD["medium"])

    parsed: list[dict] = []
    for raw in raw_notes or []:
        try:
            note_time = float(raw.get("time", 0.0))
            lane = int(raw.get("lane", 0))
            duration = float(raw.get("duration", 0.0) or 0.0)
        except (TypeError, ValueError, AttributeError):
            continue
        if note_time < 0.0 or not 0 <= lane < lanes:
            continue
        is_hold = raw.get("type") == "hold" or duration > 0.0
        if is_hold and duration < min_hold:
            is_hold = False
            duration = 0.0
        parsed.append(
            {
                "time": round(note_time, 3),
                "lane": lane,
                "duration": duration if is_hold else 0.0,
                "hold": is_hold,
            }
        )

    parsed.sort(key=lambda note: (note["time"], note["lane"]))

    by_lane: dict[int, list[dict]] = {lane: [] for lane in range(lanes)}
    for note in parsed:
        by_lane[note["lane"]].append(note)

    accepted: list[dict] = []
    for lane in range(lanes):
        notes = by_lane[lane]
        free_at = -1.0
        for index, note in enumerate(notes):
            if note["time"] < free_at + gap - 1e-6:
                continue
            duration = 0.0
            if note["hold"]:
                next_time = next(
                    (other["time"] for other in notes[index + 1 :] if other["time"] > note["time"]),
                    None,
                )
                limit = MAX_HOLD
                if next_time is not None:
                    limit = min(limit, next_time - HOLD_TAIL_GAP - note["time"])
                duration = round(min(note["duration"], limit), 3)
                if duration < min_hold - 1e-6:
                    duration = 0.0
            free_at = note["time"] + duration
            accepted.append(
                {
                    "time": note["time"],
                    "lane": lane,
                    "type": "hold" if duration > 0.0 else "tap",
                    "duration": round(duration, 3),
                }
            )

    accepted.sort(key=lambda note: (note["time"], note["lane"]))
    cleaned: list[dict] = []
    group_time = None
    group_count = 0
    for note in accepted:
        if group_time is None or note["time"] - group_time > CHORD_WINDOW:
            group_time = note["time"]
            group_count = 0
        if group_count >= MAX_CHORD:
            continue
        group_count += 1
        cleaned.append(note)

    return [
        {
            "id": index,
            "time": note["time"],
            "lane": note["lane"],
            "type": note["type"],
            "duration": note["duration"],
        }
        for index, note in enumerate(cleaned)
    ]
