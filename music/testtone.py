"""Speaker test signals: 6-channel WAV files (WAVE_FORMAT_EXTENSIBLE, mask FL FR FC LFE BL BR) with pink noise
in one channel and silence in the rest; the subwoofer gets band-limited noise (≈ 30–90 Hz)."""
from __future__ import annotations

import math
import os
import random
import struct
import tempfile

from .audio import SPEAKERS_51

RATE = 48000
SECONDS = 2.0
MASK_51 = 0x1 | 0x2 | 0x4 | 0x8 | 0x10 | 0x20          # FL FR FC LFE BL BR
KSDATAFORMAT_SUBTYPE_PCM = bytes.fromhex("0100000000001000800000aa00389b71")
_cache: dict[str, str] = {}


def _pink(n: int, seed: int = 7) -> list[float]:
    """Paul Kellet's pink noise filter, with a short fade in / out (no clicks)."""
    rnd = random.Random(seed)
    b0 = b1 = b2 = b3 = b4 = b5 = b6 = 0.0
    out = []
    for _ in range(n):
        w = rnd.uniform(-1, 1)
        b0 = 0.99886 * b0 + w * 0.0555179
        b1 = 0.99332 * b1 + w * 0.0750759
        b2 = 0.96900 * b2 + w * 0.1538520
        b3 = 0.86650 * b3 + w * 0.3104856
        b4 = 0.55000 * b4 + w * 0.5329522
        b5 = -0.7616 * b5 - w * 0.0168980
        out.append((b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.11)
        b6 = w * 0.115926
    return out


def _lowpass(x: list[float], fc: float, passes: int = 4) -> list[float]:
    a = 1 - math.exp(-2 * math.pi * fc / RATE)
    for _ in range(passes):
        y, acc = [], 0.0
        for v in x:
            acc += a * (v - acc)
            y.append(acc)
        x = y
    return x


def _highpass(x: list[float], fc: float) -> list[float]:
    lo = _lowpass(x, fc, 1)
    return [a - b for a, b in zip(x, lo)]


def _normalize(x: list[float], peak: float) -> list[float]:
    m = max(1e-9, max(abs(v) for v in x))
    n = len(x)
    fade = int(RATE * 0.03)
    out = []
    for i, v in enumerate(x):
        g = min(1.0, i / fade, (n - 1 - i) / fade)
        out.append(v / m * peak * g)
    return out


def write_wav(path: str, channels: list[list[float]], mask: int = MASK_51) -> None:
    nch = len(channels)
    n = len(channels[0])
    frames = bytearray()
    for i in range(n):
        for c in range(nch):
            frames += struct.pack("<h", int(max(-1.0, min(1.0, channels[c][i])) * 32767))
    fmt = struct.pack("<HHIIHHHHI16s", 0xFFFE, nch, RATE, RATE * nch * 2, nch * 2, 16, 22, 16, mask,
                      KSDATAFORMAT_SUBTYPE_PCM)
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt) + 8 + len(frames)) + b"WAVE")
        f.write(b"fmt " + struct.pack("<I", len(fmt)) + fmt)
        f.write(b"data" + struct.pack("<I", len(frames)) + bytes(frames))


def signal_file(speaker: str, folder: str | None = None) -> str:
    """The test WAV for one speaker of 5.1 (FL FR FC LFE BL BR); made once per run."""
    if speaker in _cache and os.path.isfile(_cache[speaker]):
        return _cache[speaker]
    folder = folder or os.path.join(tempfile.gettempdir(), "artcore_music_test")
    os.makedirs(folder, exist_ok=True)
    n = int(RATE * SECONDS)
    if speaker == "LFE":
        sig = _normalize(_highpass(_lowpass(_pink(n, 3), 90), 30), 0.32)
    else:
        sig = _normalize(_pink(n), 0.35)                     # full-range pink noise
    chans = [[0.0] * n for _ in SPEAKERS_51]
    chans[SPEAKERS_51.index(speaker)] = sig
    path = os.path.join(folder, f"test_{speaker}.wav")
    write_wav(path, chans)
    _cache[speaker] = path
    return path


# the order an AV receiver walks the room in
SEQUENCE = ("FL", "FC", "FR", "BR", "BL", "LFE")
