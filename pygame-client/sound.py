"""Efeitos sonoros sintetizados (sem arquivos externos)."""
from __future__ import annotations

import array
import math
import random

import pygame


class Sfx:
    def __init__(self) -> None:
        self.available = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        try:
            info = pygame.mixer.get_init()
            if not info:
                return
            self.frequency, _fmt, self.channels = info
            pygame.mixer.set_num_channels(24)
            self.available = True
            self._build()
        except Exception:
            self.available = False

    def _make(
        self,
        duration: float,
        partials: list[tuple[float, float]],
        volume: float = 0.45,
        noise: float = 0.0,
    ) -> pygame.mixer.Sound:
        length = max(1, int(self.frequency * duration))
        buffer = array.array("h")
        for index in range(length):
            t = index / self.frequency
            envelope = (1.0 - index / length) ** 2.0
            sample = 0.0
            for frequency, gain in partials:
                sample += gain * math.sin(2.0 * math.pi * frequency * t)
            if noise:
                sample += noise * (random.random() * 2.0 - 1.0)
            value = int(max(-1.0, min(1.0, sample * envelope * volume)) * 32767)
            for _ in range(self.channels):
                buffer.append(value)
        return pygame.mixer.Sound(buffer=buffer.tobytes())

    def _build(self) -> None:
        # Somente feedback de interface: o gameplay roda so com a musica.
        self.sounds["click"] = self._make(0.05, [(660.0, 0.45)], 0.24)
        self.sounds["finish"] = self._make(0.55, [(523.2, 0.25), (659.2, 0.24), (783.9, 0.24), (1046.5, 0.26)], 0.40)
        # Aplausos e gritos de plateia para o fim do show.
        self.sounds["crowd"] = self._make_crowd(4.6, 0.60)

    def _make_crowd(self, duration: float = 4.6, volume: float = 0.60) -> pygame.mixer.Sound:
        """Aplausos densos + rugido de plateia, normalizados (sem estourar)."""
        rate = self.frequency
        length = max(1, int(rate * duration))
        channels = max(1, min(2, self.channels))
        rng = random.Random(20261116)

        # Ruido branco continuo por canal: cada palma usa um trecho diferente dele.
        white_l = [rng.random() * 2.0 - 1.0 for _ in range(length)]
        white_r = [rng.random() * 2.0 - 1.0 for _ in range(length)]
        left = [0.0] * length
        right = [0.0] * length

        # Palmas: muitos eventos curtos sobrepostos viram a "chuva" da plateia.
        moment = 0.02
        while moment < duration - 0.7:
            density = 120.0 * (1.0 - math.exp(-moment / 0.25))
            moment += rng.expovariate(density)
            if moment >= duration - 0.7:
                break
            start = int(moment * rate)
            span = max(2, int(rng.uniform(0.008, 0.030) * rate))
            gain = 0.08 + 0.20 * rng.random()
            pan = rng.uniform(0.10, 0.90)
            gain_l = gain * (1.0 - pan) * 2.0
            gain_r = gain * pan * 2.0
            for offset in range(span):
                index = start + offset
                if index >= length:
                    break
                envelope = (1.0 - offset / span) ** 2.5
                left[index] += white_l[index] * envelope * gain_l
                right[index] += white_r[index] * envelope * gain_r

        # Rugido: ruido filtrado (grave + banda media) com respiracao lenta.
        low_l = low_r = mid_l = mid_r = 0.0
        for index in range(length):
            t = index / rate
            swell = (
                0.60
                + 0.22 * math.sin(2.0 * math.pi * 0.33 * t + 0.6)
                + 0.10 * math.sin(2.0 * math.pi * 2.3 * t + 1.7)
            )
            low_l += (white_l[index] - low_l) * 0.055
            low_r += (white_r[index] - low_r) * 0.055
            mid_l += (white_l[index] - mid_l) * 0.32
            mid_r += (white_r[index] - mid_r) * 0.32
            left[index] += (low_l * 0.55 + (mid_l - low_l) * 0.20) * swell
            right[index] += (low_r * 0.55 + (mid_r - low_r) * 0.20) * swell

        # Assobios curtos e discretos.
        for start_s, span_s, f0, f1, gain in (
            (0.60, 0.35, 1900.0, 2500.0, 0.040),
            (1.90, 0.30, 2100.0, 2700.0, 0.035),
            (3.10, 0.32, 1800.0, 2400.0, 0.035),
        ):
            start = int(start_s * rate)
            span = max(2, int(span_s * rate))
            for offset in range(span):
                index = start + offset
                if index >= length:
                    break
                progress = offset / span
                frequency = f0 + (f1 - f0) * progress
                value = gain * math.sin(2.0 * math.pi * frequency * (offset / rate)) * math.sin(math.pi * progress)
                left[index] += value * 0.7
                right[index] += value * 0.5

        # Soft clip + normalizacao: pico controlado, nada de estouro.
        peak = 0.0
        for index in range(length):
            fade = min(1.0, (index / rate) / 0.20) * min(1.0, max(0.0, (duration - index / rate) / 0.80))
            left[index] = math.tanh(left[index] * 1.1) * fade
            right[index] = math.tanh(right[index] * 1.1) * fade
            peak = max(peak, abs(left[index]), abs(right[index]))
        scale = (0.82 / peak) if peak > 1e-6 else 0.0

        buffer = array.array("h")
        for index in range(length):
            value = int(max(-1.0, min(1.0, left[index] * scale * volume)) * 32767)
            buffer.append(value)
            if channels > 1:
                value_r = int(max(-1.0, min(1.0, right[index] * scale * volume)) * 32767)
                buffer.append(value_r)
        return pygame.mixer.Sound(buffer=buffer.tobytes())

    def play(self, name: str, volume: float = 0.6) -> None:
        if not self.available:
            return
        sound = self.sounds.get(name)
        if sound is None:
            return
        try:
            sound.set_volume(max(0.0, min(1.0, volume)))
            sound.play()
        except Exception:
            pass

    def stop(self, name: str) -> None:
        if not self.available:
            return
        sound = self.sounds.get(name)
        if sound is None:
            return
        try:
            for index in range(pygame.mixer.get_num_channels()):
                channel = pygame.mixer.Channel(index)
                if channel.get_sound() == sound:
                    channel.stop()
        except Exception:
            pass
