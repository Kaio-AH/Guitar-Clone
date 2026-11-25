"""Análise de áudio local com librosa (usada no exe v2 e no dev)."""
from __future__ import annotations

from typing import Callable

StatusCb = Callable[[str], None]
CancelCb = Callable[[], bool]


class LocalAnalysisError(Exception):
    pass


def _ensure_not_cancelled(should_cancel: CancelCb | None) -> None:
    if should_cancel and should_cancel():
        raise LocalAnalysisError("Cancelado.")


def detect_note_duration(y, sr, onset_time, max_duration=2.0):
    import librosa

    onset_frame = librosa.time_to_frames(onset_time, sr=sr)
    max_frames = int(max_duration * sr / 512)
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]

    start_idx = onset_frame
    end_idx = min(start_idx + max_frames, len(rms))
    if start_idx >= len(rms):
        return 0.1

    initial_energy = rms[start_idx]
    threshold = initial_energy * 0.3
    duration_frames = 1
    for i in range(start_idx + 1, end_idx):
        if rms[i] < threshold:
            break
        duration_frames += 1

    duration = librosa.frames_to_time(duration_frames, sr=sr)
    return float(max(0.1, min(duration, max_duration)))


def generate_notes_with_duration(y, sr, beat_times, onset_times, spectral_centroids, chroma, difficulty, total_duration):
    import numpy as np

    notes = []
    note_id = 0

    difficulty_config = {
        "easy": {"use_beats": True, "use_onsets": False, "density": 0.7, "lanes": 3, "hold_probability": 0.12, "min_hold_duration": 0.5, "min_time_gap": 0.4},
        "medium": {"use_beats": True, "use_onsets": True, "density": 0.6, "lanes": 4, "hold_probability": 0.25, "min_hold_duration": 0.35, "min_time_gap": 0.25},
        "hard": {"use_beats": True, "use_onsets": True, "density": 0.75, "lanes": 5, "hold_probability": 0.3, "min_hold_duration": 0.3, "min_time_gap": 0.2},
        "expert": {"use_beats": True, "use_onsets": True, "density": 0.9, "lanes": 5, "hold_probability": 0.35, "min_hold_duration": 0.25, "min_time_gap": 0.15},
    }

    config = difficulty_config.get(difficulty, difficulty_config["medium"])
    num_lanes = config["lanes"]
    min_time_gap = config["min_time_gap"]

    all_times = []
    if config["use_beats"]:
        all_times.extend(beat_times)
    if config["use_onsets"]:
        all_times.extend(onset_times)

    all_times = sorted(list(set([round(float(t), 3) for t in all_times])))
    filtered_times = []
    last_time = -999
    for time in all_times:
        if time - last_time >= min_time_gap:
            filtered_times.append(time)
            last_time = time

    step = max(1, int(1 / config["density"]))
    selected_times = filtered_times[::step]

    lane_counts = [0] * num_lanes
    centroid_max = float(np.max(spectral_centroids)) if len(spectral_centroids) else 1.0
    if centroid_max <= 0:
        centroid_max = 1.0

    for time in selected_times:
        if time < 1.0 or time > total_duration - 2.0:
            continue

        chroma_index = min(int((time / total_duration) * chroma.shape[1]), chroma.shape[1] - 1)
        chroma_frame = chroma[:, chroma_index]
        top_pitches = np.argsort(chroma_frame)[-3:]
        dominant_pitch = top_pitches[-1]
        lane = dominant_pitch % num_lanes

        if lane_counts[lane] > np.mean(lane_counts) + 2:
            lane = int(np.argmin(lane_counts))

        spectral_index = min(int((time / total_duration) * len(spectral_centroids)), len(spectral_centroids) - 1)
        normalized_centroid = spectral_centroids[spectral_index] / centroid_max
        if np.random.random() < 0.3:
            lane = int(normalized_centroid * (num_lanes - 1))

        lane = max(0, min(lane, num_lanes - 1))
        lane_counts[lane] += 1

        is_hold_note = np.random.random() < config["hold_probability"]
        note_duration = 0.0
        note_type = "tap"
        if is_hold_note:
            note_duration = detect_note_duration(y, sr, time, max_duration=2.5)
            if note_duration >= config["min_hold_duration"]:
                note_type = "hold"
            else:
                note_duration = 0.0

        notes.append(
            {
                "id": note_id,
                "time": round(float(time), 3),
                "lane": int(lane),
                "type": note_type,
                "duration": round(float(note_duration), 3) if note_type == "hold" else 0.0,
            }
        )
        note_id += 1

    return notes


def analyze_audio_file(file_path: str, difficulty: str = "medium", on_status: StatusCb | None = None, should_cancel: CancelCb | None = None) -> dict:
    """Analisa arquivo local e retorna payload compatível com o backend."""
    try:
        import librosa
    except Exception as exc:  # pragma: no cover - depende do ambiente empacotado
        raise LocalAnalysisError(
            "Análise local indisponível: librosa não está instalado neste build. "
            "Use a v2 completa ou rode pelo código-fonte com dependências instaladas."
        ) from exc

    _ensure_not_cancelled(should_cancel)
    if on_status:
        on_status("Carregando áudio local...")
    y, sr = librosa.load(file_path, sr=22050)
    duration = float(librosa.get_duration(y=y, sr=sr))

    _ensure_not_cancelled(should_cancel)
    if on_status:
        on_status("Detectando batidas e BPM...")
    tempo_result, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(tempo_result.item()) if hasattr(tempo_result, "item") else float(tempo_result)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    _ensure_not_cancelled(should_cancel)
    if on_status:
        on_status("Detectando onsets e características...")
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, backtrack=True, units="frames")
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

    _ensure_not_cancelled(should_cancel)
    if on_status:
        on_status("Gerando chart...")
    notes = generate_notes_with_duration(y, sr, beat_times, onset_times, spectral_centroids, chroma, difficulty, duration)

    return {
        "success": True,
        "audio_info": {
            "duration": duration,
            "tempo": tempo,
            "beats_count": int(len(beat_times)),
            "onsets_count": int(len(onset_times)),
            "notes_count": int(len(notes)),
            "hold_notes_count": int(sum(1 for n in notes if n.get("duration", 0) > 0.3)),
            "difficulty": difficulty,
            "sample_rate": int(sr),
        },
        "notes": notes,
    }
