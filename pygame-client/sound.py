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
        self.sounds["crowd"] = self._make_crowd(4.6, 0.85)

    def _make_crowd(self, duration: float = 4.6, volume: float = 0.60) -> pygame.mixer.Sound:
        """Aplausos de plateia: palmas curtas e filtradas + murmúrio grave.

        O chiado anterior vinha de ruído branco contínuo e claps de banda larga.
        Aqui cada palma é um transiente de banda estreita (~1-3 kHz) com corpo
        grave, e o fundo é um murmúrio filtrado (sem hiss) com cauda de sala.
        """
        rate = self.frequency
        length = max(1, int(rate * duration))
        channels = max(1, min(2, self.channels))
        rng = random.Random(20261118)

        def make_clap(seed: int) -> list[float]:
            """Uma palma: dois bandpass (corpo/estalo) + thump grave."""
            r = random.Random(seed)
            n = max(16, int(rate * r.uniform(0.032, 0.048)))
            f_body = r.uniform(220.0, 300.0)
            f_mid = r.uniform(1150.0, 1750.0)
            q_mid = r.uniform(1.0, 1.5)
            f_high = r.uniform(2600.0, 3300.0)
            q_high = r.uniform(1.2, 1.8)
            f_top = r.uniform(4000.0, 5200.0)
            q_top = r.uniform(1.3, 1.8)
            tau = r.uniform(0.009, 0.015)
            second = r.uniform(0.005, 0.008)
            attack = max(1.0, 0.0008 * rate)

            # Coeficientes dos bandpass (RBJ cookbook), já normalizados por a0.
            bands = []
            for f0, q in ((f_mid, q_mid), (f_high, q_high), (f_top, q_top)):
                w0 = 2.0 * math.pi * f0 / rate
                alpha = math.sin(w0) / (2.0 * q)
                a0 = 1.0 + alpha
                bands.append((
                    alpha / a0,
                    0.0,
                    -alpha / a0,
                    -2.0 * math.cos(w0) / a0,
                    (1.0 - alpha) / a0,
                ))

            out = [0.0] * n
            x1 = [0.0, 0.0, 0.0]
            x2 = [0.0, 0.0, 0.0]
            y1 = [0.0, 0.0, 0.0]
            y2 = [0.0, 0.0, 0.0]
            body_phase = 0.0
            for i in range(n):
                x = r.random() * 2.0 - 1.0
                t = i / rate
                mid = high = top = 0.0
                for b, (b0, b1, b2, a1, a2) in enumerate(bands):
                    y = b0 * x + b1 * x1[b] + b2 * x2[b] - a1 * y1[b] - a2 * y2[b]
                    x2[b], x1[b] = x1[b], x
                    y2[b], y1[b] = y1[b], y
                    if b == 0:
                        mid = y
                    elif b == 1:
                        high = y
                    else:
                        top = y
                envelope = math.exp(-t / tau)
                if t >= second:
                    envelope += 0.45 * math.exp(-(t - second) / (tau * 0.8))
                envelope *= 1.0 - math.exp(-i / attack)
                body_phase += 2.0 * math.pi * f_body / rate
                body = math.sin(body_phase) * math.exp(-t / 0.014)
                out[i] = (
                    mid * envelope
                    + high * 0.38 * envelope
                    + top * 0.10 * envelope
                    + body * 0.12
                )
            peak = max(abs(value) for value in out)
            return [value / peak for value in out] if peak > 1e-6 else out

        left = [0.0] * length
        right = [0.0] * length

        def place(start: int, gain: float, pan: float, kernel: list[float]) -> None:
            if start >= length:
                return
            gain_l = gain * math.sqrt(1.0 - pan) * 1.15
            gain_r = gain * math.sqrt(pan) * 1.15
            limit = min(len(kernel), length - start)
            for offset in range(limit):
                value = kernel[offset]
                left[start + offset] += value * gain_l
                right[start + offset] += value * gain_r

        kernels = [make_clap(7000 + index) for index in range(12)]

        # Base densa: muitas palmas baixas, sem buracos (o "chuá" do aplauso).
        moment = 0.03
        while moment < duration - 0.60:
            swell = 1.0 - math.exp(-moment / 0.28)
            tail = min(1.0, max(0.0, (duration - 0.60 - moment) / 0.80))
            density = 95.0 * swell * (0.30 + 0.70 * tail)
            moment += rng.expovariate(max(1.0, density))
            if moment >= duration - 0.60:
                break
            gain = 0.09 + 0.20 * rng.random() ** 1.6
            place(int(moment * rate), gain, rng.uniform(0.12, 0.88), rng.choice(kernels))

        # Palmas em destaque, às vezes em pequenas salvas (plateia em sincronia).
        moment = 0.08
        while moment < duration - 0.65:
            tail = min(1.0, max(0.0, (duration - 0.65 - moment) / 0.85))
            density = 22.0 * (0.30 + 0.70 * tail)
            moment += rng.expovariate(max(1.0, density))
            if moment >= duration - 0.65:
                break
            count = rng.randint(2, 4) if rng.random() < 0.10 else 1
            when = moment
            for _ in range(count):
                gain = 0.30 + 0.55 * rng.random() ** 1.4
                place(int(when * rate), gain, rng.uniform(0.10, 0.90), rng.choice(kernels))
                when += rng.uniform(0.045, 0.095)

        # Murmúrio da plateia: ruído filtrado em grave/médio (não é hiss).
        low_l = low_r = band_l = band_r = 0.0
        for index in range(length):
            t = index / rate
            noise_l = rng.random() * 2.0 - 1.0
            noise_r = rng.random() * 2.0 - 1.0
            low_l += (noise_l - low_l) * 0.030
            low_r += (noise_r - low_r) * 0.030
            band_l += (noise_l - band_l) * 0.110
            band_r += (noise_r - band_r) * 0.110
            swell = (
                0.55
                + 0.25 * math.sin(2.0 * math.pi * 0.27 * t + 0.4)
                + 0.10 * math.sin(2.0 * math.pi * 1.9 * t + 1.2)
            )
            value = (low_l * 0.05 + (band_l - low_l) * 0.26) * swell
            left[index] += value
            right[index] += value * 0.92

        # Assobios curtos, com vibrato aplicado na frequência (não na fase).
        for start_s, span_s, f0, f1, gain in (
            (0.70, 0.32, 1800.0, 2400.0, 0.030),
            (2.10, 0.28, 2000.0, 2600.0, 0.026),
        ):
            start = int(start_s * rate)
            span = max(2, int(span_s * rate))
            phase = 0.0
            for offset in range(span):
                index = start + offset
                if index >= length:
                    break
                progress = offset / span
                frequency = f0 + (f1 - f0) * progress
                vibrato = 1.0 + 0.02 * math.sin(2.0 * math.pi * 6.0 * (offset / rate))
                phase += 2.0 * math.pi * frequency * vibrato / rate
                value = gain * math.sin(phase) * math.sin(math.pi * progress)
                left[index] += value * 0.80
                right[index] += value * 0.50

        # Cauda curta de sala: cópias atrasadas e baixas (sem realimentação).
        for delay_s, gain in ((0.024, 0.12), (0.057, 0.07), (0.101, 0.04)):
            delay = int(delay_s * rate)
            for index in range(length - 1, delay - 1, -1):
                left[index] += left[index - delay] * gain
                right[index] += right[index - delay] * gain

        # Filtro final: corta agudos (chiado) e rumble, comprime e normaliza.
        lp1_l = lp1_r = lp2_l = lp2_r = 0.0
        hp_l = hp_r = 0.0
        a_lp = 1.0 - math.exp(-2.0 * math.pi * 6000.0 / rate)
        a_hp = 1.0 - math.exp(-2.0 * math.pi * 160.0 / rate)
        peak = 0.0
        for index in range(length):
            t = index / rate
            lp1_l += (left[index] - lp1_l) * a_lp
            lp1_r += (right[index] - lp1_r) * a_lp
            lp2_l += (lp1_l - lp2_l) * a_lp
            lp2_r += (lp1_r - lp2_r) * a_lp
            hp_l += (lp2_l - hp_l) * a_hp
            hp_r += (lp2_r - hp_r) * a_hp
            value_l = math.tanh((lp2_l - hp_l) * 1.15)
            value_r = math.tanh((lp2_r - hp_r) * 1.15)
            fade = min(1.0, t / 0.18) * min(1.0, max(0.0, (duration - t) / 0.75))
            left[index] = value_l * fade
            right[index] = value_r * fade
            peak = max(peak, abs(left[index]), abs(right[index]))
        scale = (0.80 / peak) if peak > 1e-6 else 0.0

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
