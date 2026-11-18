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
