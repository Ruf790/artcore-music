"""Song lyrics: a .lrc (synced) or .txt next to the track, or the lyrics stored in its tags.

LRC: «[mm:ss.xx] line», several time stamps on one line, [offset:±ms], word stamps <mm:ss.xx> (dropped);
[ar:] / [ti:] and the like are skipped. Text without time stamps is shown as plain (not synced) lyrics."""
from __future__ import annotations

import bisect
import os
import re
from dataclasses import dataclass, field

from . import cue
from .playlist import Track

STAMP = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
WORD = re.compile(r"<\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?>")
OFFSET = re.compile(r"\[offset:\s*([+-]?\d+)\s*\]", re.I)
META = re.compile(r"^\[[a-z#]+:.*\]$", re.I)


@dataclass
class Lyrics:
    lines: list[str] = field(default_factory=list)
    times: list[float] = field(default_factory=list)    # seconds, one per line (synced only)
    source: str = ""

    @property
    def synced(self) -> bool:
        return bool(self.times)

    def index_at(self, sec: float) -> int:
        """The line being sung at `sec` (-1: before the first)."""
        if not self.times:
            return -1
        return bisect.bisect_right(self.times, sec + 0.05) - 1


def parse(text: str, source: str = "") -> Lyrics | None:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    if not text.strip():
        return None
    off = 0.0
    m = OFFSET.search(text)
    if m:
        off = int(m.group(1)) / 1000.0           # positive: the lyrics come earlier
    timed: list[tuple[float, str]] = []
    plain: list[str] = []
    for raw in text.split("\n"):
        line = raw.strip()
        stamps = []
        while True:
            m = STAMP.match(line)
            if not m:
                break
            mm, ss, frac = int(m.group(1)), int(m.group(2)), m.group(3) or "0"
            stamps.append(mm * 60 + ss + int(frac) / (10 ** len(frac)))
            line = line[m.end():].lstrip()
        if stamps:
            words = WORD.sub("", line).strip()
            for s in stamps:
                timed.append((max(0.0, s - off), words))
        elif not META.match(line):
            plain.append(raw.rstrip())
    if timed:
        timed.sort(key=lambda x: x[0])
        return Lyrics([w for _, w in timed], [s for s, _ in timed], source)
    while plain and not plain[0].strip():
        plain.pop(0)
    while plain and not plain[-1].strip():
        plain.pop()
    return Lyrics(plain, [], source) if any(x.strip() for x in plain) else None


def _read(path: str) -> str:
    try:
        with open(path, "rb") as f:
            raw = f.read(512 * 1024)
    except OSError:
        return ""
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", "replace")
    return cue.decode(raw)


def _sidecar(path: str) -> str:
    """«Song.lrc» (any case), then «Song.txt», in the folder of the track or its Lyrics sub-folder."""
    folder, base = os.path.split(path)
    stem = os.path.splitext(base)[0].lower()
    for d in (folder, os.path.join(folder, "Lyrics"), os.path.join(folder, "lyrics")):
        try:
            names = os.listdir(d)
        except OSError:
            continue
        low = {n.lower(): n for n in names}
        for ext in (".lrc", ".txt"):
            if stem + ext in low:
                return os.path.join(d, low[stem + ext])
    return ""


def embedded(path: str) -> str:
    """Lyrics stored in the tags: ID3 USLT, Vorbis LYRICS / UNSYNCEDLYRICS, MP4 ©lyr, APEv2 Lyrics."""
    try:
        import mutagen
        f = mutagen.File(path)
    except Exception:
        return ""
    tags = getattr(f, "tags", None) if f is not None else None
    if tags is None:
        return ""
    try:
        keys = list(tags.keys())
    except Exception:
        return ""
    for k in keys:
        ks = str(k)
        if ks.startswith("USLT"):
            return str(tags[k].text or "")
    for k in keys:
        lk = str(k).lower()
        if lk in ("lyrics", "unsyncedlyrics", "\xa9lyr", "unsynced lyrics"):
            v = tags[k]
            if isinstance(v, list):
                v = v[0] if v else ""
            v = getattr(v, "value", v)
            return str(v or "")
    return ""


def load(tr: Track | None) -> Lyrics | None:
    if tr is None or tr.is_stream or tr.is_cue:
        return None
    side = _sidecar(tr.path)
    if side:
        lyr = parse(_read(side), side)
        if lyr is not None:
            return lyr
    text = embedded(tr.path)
    return parse(text, "tags") if text else None
