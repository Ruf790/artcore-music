"""CUE sheets: an album image (one FLAC/APE/WAV) split into tracks. Russian sheets are often in cp1251."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass
class CueTrack:
    file: str                # absolute path of the audio file
    number: int
    title: str
    performer: str
    start: float             # seconds (INDEX 01)
    end: float | None        # start of the next track in the same file; None = to the end of the file
    album: str = ""
    album_artist: str = ""
    year: str = ""
    genre: str = ""


def decode(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", "replace")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", "replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("cp1251")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _time(s: str) -> float:
    m = re.match(r"(\d+):(\d+):(\d+)", s.strip())
    if not m:
        return 0.0
    mm, ss, ff = (int(x) for x in m.groups())
    return mm * 60 + ss + ff / 75.0


_TOKEN = re.compile(r'"([^"]*)"?|(\S+)')


def _args(line: str) -> list[str]:
    """Words and "quoted strings" (backslashes kept: Windows paths; apostrophes kept: Don't Stop)."""
    return [m.group(1) if m.group(1) is not None else m.group(2) for m in _TOKEN.finditer(line)]


def _rest(line: str) -> str:
    """Everything after the keyword, without the quotes: TITLE Don't Stop / TITLE "Don't Stop"."""
    rest = line.split(None, 1)[1].strip() if len(line.split(None, 1)) > 1 else ""
    if len(rest) >= 2 and rest[0] == '"' and rest.rfind('"') > 0:
        return rest[1:rest.rfind('"')]
    return rest.strip('"')


def _find_audio(base_dir: str, name: str, cue_path: str) -> str:
    """The FILE line often names a .wav while the folder has the .flac / .ape: try the other extensions."""
    from . import AUDIO_EXT
    p = os.path.join(base_dir, name)
    if os.path.isfile(p):
        return p
    stem = os.path.splitext(name)[0]
    for ext in AUDIO_EXT:
        q = os.path.join(base_dir, stem + ext)
        if os.path.isfile(q):
            return q
    stem2 = os.path.splitext(os.path.basename(cue_path))[0]           # «Album.flac» next to «Album.cue»
    for ext in AUDIO_EXT:
        q = os.path.join(base_dir, stem2 + ext)
        if os.path.isfile(q):
            return q
    return p


def parse_text(text: str, cue_path: str, audio_override: str = "") -> list[CueTrack]:
    base = os.path.dirname(os.path.abspath(cue_path))
    album = album_artist = year = genre = ""
    cur_file = audio_override
    tracks: list[CueTrack] = []
    cur: dict | None = None
    in_track = False

    def flush():
        if cur and cur.get("start") is not None and cur.get("audio", True):
            tracks.append(CueTrack(cur["file"], cur["number"], cur.get("title", ""),
                                   cur.get("performer", "") or album_artist, cur["start"], None,
                                   album, album_artist, year, genre))

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        a = _args(line)
        if not a:
            continue
        kw = a[0].upper()
        if kw == "REM" and len(a) >= 3:
            sub = a[1].upper()
            if sub == "DATE" and not in_track:
                year = a[2]
            elif sub == "GENRE" and not in_track:
                genre = " ".join(a[2:])
        elif kw == "FILE" and len(a) >= 2:
            if not audio_override:
                cur_file = _find_audio(base, a[1], cue_path)
        elif kw == "TRACK" and len(a) >= 2:
            flush()
            in_track = True
            try:
                num = int(a[1])
            except ValueError:
                num = len(tracks) + 1
            cur = {"file": cur_file, "number": num, "start": None,
                   "audio": len(a) < 3 or a[2].upper() == "AUDIO"}
        elif kw == "TITLE" and len(a) >= 2:
            if in_track and cur is not None:
                cur["title"] = _rest(line)
            else:
                album = _rest(line)
        elif kw == "PERFORMER" and len(a) >= 2:
            if in_track and cur is not None:
                cur["performer"] = _rest(line)
            else:
                album_artist = _rest(line)
        elif kw == "INDEX" and len(a) >= 3 and cur is not None:
            if int(a[1]) == 1:
                cur["start"] = _time(a[2])
            elif int(a[1]) == 0 and cur.get("start") is None:
                cur.setdefault("index0", _time(a[2]))
    flush()
    # end = start of the next track in the same file
    for i, tr in enumerate(tracks):
        nxt = tracks[i + 1] if i + 1 < len(tracks) else None
        if nxt and os.path.normcase(nxt.file) == os.path.normcase(tr.file):
            tr.end = nxt.start
        # album info set after the first TRACK line (rare) still applies
        tr.album = tr.album or album
        tr.album_artist = tr.album_artist or album_artist
        tr.performer = tr.performer or album_artist
    return tracks


def parse(cue_path: str) -> list[CueTrack]:
    with open(cue_path, "rb") as f:
        raw = f.read()
    return parse_text(decode(raw), cue_path)
