"""Colours taken from the album cover: the window's accent follows the album.

pick(data, dark) → (accent, accent2, accent_text) as #rrggbb, or None for a grey / missing cover
(then the skin keeps its own colours). The colours are moved in lightness until they are readable:
white on accent and accent2 (the play button), accent_text on the panel (the playing row).
"""
from __future__ import annotations

import colorsys

BINS = 24                         # hue buckets of 15°


def _lum(rgb) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ratio(a, b) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def hex_rgb(h: str):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in rgb)


def _hls(h: float, l: float, s: float):
    r, g, b = colorsys.hls_to_rgb(h, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return r * 255, g * 255, b * 255


def _fit(h: float, s: float, l: float, ok, step: float) -> str:
    """Move lightness by step until ok(rgb) — or as far as it goes."""
    for _ in range(60):
        rgb = _hls(h, l, s)
        if ok(rgb):
            return rgb_hex(rgb)
        l += step
        if l <= 0.02 or l >= 0.98:
            break
    return rgb_hex(_hls(h, max(0.02, min(0.98, l)), s))


def hues(data: bytes) -> list[tuple[float, float, float, float]]:
    """Weighted hue buckets of the cover: [(weight, hue, sat, light)] strongest first."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    img = QImage.fromData(data)
    if img.isNull():
        return []
    img = img.scaled(48, 48, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGB32)
    acc = [[0.0, 0.0, 0.0, 0.0, 0.0] for _ in range(BINS)]       # weight, sum cos, sum sin, sat, light
    import math
    total = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            h, l, s = colorsys.rgb_to_hls(c.redF(), c.greenF(), c.blueF())
            total += 1
            if s < 0.28 or l < 0.12 or l > 0.92:
                continue
            w = s * (1.0 - abs(l - 0.5) * 1.4)
            b = acc[int(h * BINS) % BINS]
            b[0] += w
            b[1] += w * math.cos(h * 2 * math.pi)
            b[2] += w * math.sin(h * 2 * math.pi)
            b[3] += w * s
            b[4] += w * l
    out = []
    for b in acc:
        if b[0] <= 0:
            continue
        h = (math.atan2(b[2], b[1]) / (2 * math.pi)) % 1.0
        out.append((b[0] / max(1, total), h, b[3] / b[0], b[4] / b[0]))
    out.sort(reverse=True)
    return out


def _dist(a: float, b: float) -> float:
    d = abs(a - b) % 1.0
    return min(d, 1.0 - d)


def pick(data: bytes | None, dark: bool, panel: str) -> tuple[str, str, str] | None:
    if not data:
        return None
    try:
        hs = hues(data)
    except Exception:
        return None
    if not hs or hs[0][0] < 0.035:                         # a grey / black-and-white cover
        return None
    w1, h1, s1, _ = hs[0]
    second = next((x for x in hs[1:] if _dist(x[1], h1) >= 1 / 9 and x[0] >= w1 * 0.18), None)
    h2, s2 = (second[1], second[2]) if second else ((h1 + 1 / 12) % 1.0, s1)
    s1, s2 = max(0.5, min(0.9, s1 + 0.1)), max(0.45, min(0.88, s2 + 0.1))
    white = (255, 255, 255)
    # the play button / gradients carry white icons: dark enough for white, not muddy
    accent = _fit(h1, s1, 0.56, lambda rgb: ratio(white, rgb) >= 3.6, -0.02)
    accent2 = _fit(h2, s2, 0.52, lambda rgb: ratio(white, rgb) >= 3.6, -0.02)
    pr = hex_rgb(panel)
    if dark:     # the playing row on a dark panel: a light tint of the accent
        text = _fit(h1, min(0.85, s1), 0.62, lambda rgb: ratio(rgb, pr) >= 4.8, +0.02)
    else:
        text = _fit(h1, min(0.85, s1), 0.42, lambda rgb: ratio(rgb, pr) >= 4.8, -0.02)
    return accent, accent2, text
