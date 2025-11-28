from __future__ import annotations

import time
from typing import List

import numpy as np

try:
    import sounddevice as sd  # type: ignore

    _HAS_SOUNDDEVICE = True
except Exception:
    _HAS_SOUNDDEVICE = False

DEFAULT_SAMPLE_RATE = 44100


def generate_sine_wave(freq_hz: float, duration_ms: int, sample_rate: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    duration_s = duration_ms / 1000.0
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), False)
    tone = np.sin(freq_hz * t * 2 * np.pi)
    return (tone * 0.8).astype(np.float32)


def play_wave(wave: np.ndarray, sample_rate: int = DEFAULT_SAMPLE_RATE) -> None:
    if not _HAS_SOUNDDEVICE:
        return
    try:
        sd.play(wave, samplerate=sample_rate, blocking=False)
    except Exception:
        pass


def play_beep(frequency_hz: float, duration_ms: int) -> None:
    wave = generate_sine_wave(frequency_hz, duration_ms)
    play_wave(wave)


def play_notification_sound(sound_type: str) -> None:
    if sound_type == "start_sequence":
        freqs: List[int] = [800, 1000, 1200]
        durs: List[int] = [180, 180, 180]
        gaps: List[int] = [80, 80]
    elif sound_type == "end_sequence":
        freqs = [900, 700, 500]
        durs = [200, 200, 400]
        gaps = [150, 250]
    elif sound_type == "high_beep":
        freqs = [1000]
        durs = [300]
        gaps = []
    else:
        freqs = [500]
        durs = [300]
        gaps = []
    for i, (f, d) in enumerate(zip(freqs, durs)):
        play_beep(f, d)
        if i < len(gaps):
            time.sleep(gaps[i] / 1000.0)
