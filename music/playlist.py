"""Playlist entries: plain files and CUE tracks; folders (recursive), .cue, .m3u/.m3u8 in and out."""
from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field

from . import AUDIO_EXT, CUE_EXT, PLAYLIST_EXT, cue, meta


@dataclass
class Track:
    path: str
    start: float = 0.0                 # CUE track: offset in the file
    end: float | None = None           # CUE track: end in the file (None = end of file)
    cue: str = ""                      # the .cue it came from
    number: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    albumartist: str = ""
    year: str = ""
    genre: str = ""
    length: float = 0.0                # seconds (0 = not known yet)
    tagged: bool = False               # tags were read
    uid: int = field(default=0, compare=False)

    @property
    def is_cue(self) -> bool:
        return bool(self.cue)

    @property
    def is_stream(self) -> bool:
        return is_url(self.path)

    @property
    def album_key(self) -> str:
        """Same album = same folder + same album tag (or the same CUE image)."""
        if self.cue:
            return "cue:" + os.path.normcase(self.cue)
        return os.path.normcase(os.path.dirname(self.path)) + "|" + (self.album or "").lower()

    def display_title(self) -> str:
        return self.title or os.path.splitext(os.path.basename(self.path))[0]

    def display(self) -> str:
        return f"{self.artist} — {self.display_title()}" if self.artist else self.display_title()

    def duration(self) -> float:
        if self.end is not None:
            return max(0.0, self.end - self.start)
        if self.length:
            return max(0.0, self.length - self.start)
        return 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("uid", None)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Track":
        ok = {k: v for k, v in d.items() if k in cls.__dataclass_fields__ and k != "uid"}
        return cls(**ok)


_uid = 0


def _new_uid() -> int:
    global _uid
    _uid += 1
    return _uid


def stamp(tracks: list[Track]) -> list[Track]:
    for t in tracks:
        if not t.uid:
            t.uid = _new_uid()
    return tracks


def natural_key(s: str):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s)]


def is_url(path: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9+.-]*://", path or "", re.I))


def stream_title(url: str) -> str:
    """A name for a stream without one: host + path («radio.example.com/live»)."""
    m = re.match(r"^[a-z][a-z0-9+.-]*://([^/?#]+)([^?#]*)", url, re.I)
    if not m:
        return url
    host, path = m.group(1), m.group(2).strip("/")
    return host + ("/" + path if path else "")


def is_audio(path: str) -> bool:
    return path.lower().endswith(AUDIO_EXT)


def fill_tags(t: Track) -> Track:
    """Read the tags of a plain file (CUE tracks have theirs from the sheet; only the length is read)."""
    if t.is_stream:                          # an internet radio: the name from the playlist stays
        t.tagged = True
        return t
    tg = meta.read(t.path)
    if t.is_cue:
        t.length = tg.length or t.length
        t.genre = t.genre or tg.genre
        t.year = t.year or tg.year
    else:
        t.title, t.artist, t.album = tg.title, tg.artist, tg.album
        t.albumartist, t.year, t.number, t.genre = tg.albumartist, tg.year, tg.track, tg.genre
        t.length = tg.length
    t.tagged = True
    return t


def from_cue(path: str) -> list[Track]:
    out = []
    try:
        cts = cue.parse(path)
    except OSError:
        return out
    for ct in cts:
        out.append(Track(path=ct.file, start=ct.start, end=ct.end, cue=os.path.abspath(path), number=str(ct.number),
                         title=ct.title, artist=ct.performer, album=ct.album, albumartist=ct.album_artist,
                         year=ct.year, genre=ct.genre))
    return out


def from_embedded_cue(path: str, sheet: str) -> list[Track]:
    out = []
    for ct in cue.parse_text(sheet, path, audio_override=path):
        out.append(Track(path=path, start=ct.start, end=ct.end, cue=path, number=str(ct.number), title=ct.title,
                         artist=ct.performer, album=ct.album, albumartist=ct.album_artist, year=ct.year, genre=ct.genre))
    return out


def _folder(folder: str) -> list[Track]:
    """A folder in name order, sub-folders after the files; an album image with a .cue becomes its tracks."""
    try:
        names = sorted(os.listdir(folder), key=natural_key)
    except OSError:
        return []
    out: list[Track] = []
    covered: set[str] = set()                  # audio files a .cue already splits
    for n in names:
        p = os.path.join(folder, n)
        if n.lower().endswith(CUE_EXT) and os.path.isfile(p):
            tr = from_cue(p)
            if tr and all(os.path.isfile(t.path) for t in tr):
                out.extend(tr)
                covered.update(os.path.normcase(t.path) for t in tr)
    for n in names:
        p = os.path.join(folder, n)
        if os.path.isfile(p) and is_audio(p) and os.path.normcase(p) not in covered:
            out.append(Track(path=p))
    for n in names:
        p = os.path.join(folder, n)
        if os.path.isdir(p) and not n.startswith("."):
            out.extend(_folder(p))
    return out


def read_m3u(path: str) -> list[Track]:
    with open(path, "rb") as f:
        raw = f.read()
    text = cue.decode(raw) if not path.lower().endswith(".m3u8") else raw.decode("utf-8-sig", "replace")
    base = os.path.dirname(os.path.abspath(path))
    out: list[Track] = []
    title = ""
    length = 0.0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            m = re.match(r"#EXTINF:(-?\d+(?:\.\d+)?)\s*(?:[^,]*),(.*)", line)
            if m:
                length = max(0.0, float(m.group(1)))
                title = m.group(2).strip()
            continue
        if line.startswith("#"):
            continue
        p = line if os.path.isabs(line) or is_url(line) else os.path.join(base, line)
        p = os.path.normpath(p) if not is_url(p) else p
        if not is_url(p) and p.lower().endswith(CUE_EXT):
            out.extend(from_cue(p))
        else:
            t = Track(path=p, length=length)
            if is_url(p):
                t.title = title or stream_title(p)
                t.length = 0.0
            elif " - " in title:
                t.artist, t.title = (s.strip() for s in title.split(" - ", 1))
            elif title:
                t.title = title
            out.append(t)
        title, length = "", 0.0
    return _one_per_stream(out)


def read_pls(path: str) -> list[Track]:
    """[playlist] File1= / Title1= / Length1= (Winamp / SHOUTcast); keys in any case."""
    with open(path, "rb") as f:
        text = cue.decode(f.read())
    base = os.path.dirname(os.path.abspath(path))
    files: dict[int, str] = {}
    titles: dict[int, str] = {}
    lengths: dict[int, float] = {}
    for line in text.splitlines():
        m = re.match(r"\s*(file|title|length)(\d+)\s*=\s*(.*)$", line, re.I)
        if not m:
            continue
        kind, n, val = m.group(1).lower(), int(m.group(2)), m.group(3).strip()
        if kind == "file":
            files[n] = val
        elif kind == "title":
            titles[n] = val
        else:
            try:
                lengths[n] = max(0.0, float(val))
            except ValueError:
                pass
    out: list[Track] = []
    for n in sorted(files):
        p = files[n]
        if not is_url(p):
            p = os.path.normpath(p if os.path.isabs(p) else os.path.join(base, p))
        title = titles.get(n, "")
        if is_url(p):
            out.append(Track(path=p, title=title or stream_title(p)))
        else:
            t = Track(path=p, length=lengths.get(n, 0.0))
            if " - " in title:
                t.artist, t.title = (s.strip() for s in title.split(" - ", 1))
            elif title:
                t.title = title
            out.append(t)
    return _one_per_stream(out)


def _one_per_stream(tracks: list[Track]) -> list[Track]:
    """Radio playlists repeat the same URL as fallbacks: keep it once (the first, it has the name)."""
    seen: set[str] = set()
    out = []
    for t in tracks:
        if is_url(t.path):
            if t.path in seen:
                continue
            seen.add(t.path)
        out.append(t)
    return out


def write_m3u(path: str, tracks: list[Track]) -> None:
    """Extended M3U in UTF-8; paths relative to the playlist when they are on the same drive.
    CUE tracks are written as their .cue (once)."""
    base = os.path.dirname(os.path.abspath(path))
    lines = ["#EXTM3U"]
    done_cues: set[str] = set()
    for t in tracks:
        if t.is_stream:
            lines.append(f"#EXTINF:-1,{t.display_title()}")
            lines.append(t.path)
            continue
        if t.is_cue:
            key = os.path.normcase(t.cue)
            if key in done_cues:
                continue
            done_cues.add(key)
            target, title, secs = t.cue, t.album or os.path.basename(t.cue), -1
        else:
            target = t.path
            title = f"{t.artist} - {t.display_title()}" if t.artist else t.display_title()
            secs = int(round(t.length)) if t.length else -1
        try:
            rel = os.path.relpath(target, base)
            if not rel.startswith(".." + os.sep + ".." + os.sep + ".."):
                target = rel
        except ValueError:                                   # another drive
            pass
        lines.append(f"#EXTINF:{secs},{title}")
        lines.append(target)
    enc = "utf-8" if path.lower().endswith(".m3u8") else "utf-8-sig"
    with open(path, "w", encoding=enc, newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")


def expand(paths: list[str]) -> list[Track]:
    """Whatever was opened or dropped → playlist entries (in that order)."""
    out: list[Track] = []
    for p in paths:
        if is_url(p):                                   # a link to a radio / a stream
            out.append(Track(path=p.strip(), title=stream_title(p.strip())))
            continue
        if os.path.isdir(p):
            out.extend(_folder(p))
            continue
        low = p.lower()
        if low.endswith(CUE_EXT):
            out.extend(from_cue(p))
        elif low.endswith(".pls"):
            try:
                out.extend(read_pls(p))
            except OSError:
                pass
        elif low.endswith(PLAYLIST_EXT):
            try:
                out.extend(read_m3u(p))
            except OSError:
                pass
        elif os.path.isfile(p):
            if is_audio(p):
                sheet = meta.read(p).cuesheet if low.endswith((".flac", ".ape", ".wv")) else ""
                if sheet:
                    tr = from_embedded_cue(p, sheet)
                    if tr:
                        out.extend(tr)
                        continue
                out.append(Track(path=p))
    return stamp(out)


class Playlist:
    """The list plus the play order: repeat off / all / one, shuffle (a shuffled order of uids)."""

    def __init__(self, name: str = "", kind: str = ""):
        self.name = name
        self.kind = kind                     # "" | "favorites" | "history" (filled from the library)
        self.scroll = 0                      # where the list was scrolled (when its tab is shown again)
        self.tracks: list[Track] = []
        self.repeat = "off"
        self.shuffle = False
        self._order: list[int] = []          # uids, shuffled; used when shuffle is on
        self._gone_at = 0                    # where the playing track was when it got removed
        self._map: dict[int, Track] = {}     # uid → track

    # ── lookups
    def index_of(self, t: Track | None) -> int:
        if t is None:
            return -1
        for i, x in enumerate(self.tracks):
            if x.uid == t.uid:
                return i
        return -1

    def by_uid(self, uid: int) -> Track | None:
        return self._map.get(uid)

    def _reindex(self):
        self._map = {t.uid: t for t in self.tracks}

    def without_dups(self, new: list[Track]) -> list[Track]:
        have = {(os.path.normcase(x.path), round(x.start, 2)) for x in self.tracks}
        out = []
        for t in new:
            key = (os.path.normcase(t.path), round(t.start, 2))
            if key not in have:
                have.add(key)
                out.append(t)
        return out

    def _seq(self) -> list[Track]:
        if not self.shuffle:
            return self.tracks
        m = {t.uid: t for t in self.tracks}
        return [m[u] for u in self._order if u in m]

    # ── order
    def next_after(self, t: Track | None, auto: bool = True) -> Track | None:
        seq = self._seq()
        if not seq:
            return None
        if t is not None and auto and self.repeat == "one" and self.index_of(t) >= 0:
            return t
        i = next((k for k, x in enumerate(seq) if t is not None and x.uid == t.uid), -1)
        if i < 0:                                 # the playing track was removed: whatever took its place
            if not self.shuffle and 0 <= self._gone_at < len(self.tracks):
                return self.tracks[self._gone_at]
            return seq[0] if self.repeat != "off" or t is None else None
        if i + 1 < len(seq):
            return seq[i + 1]
        if self.repeat != "off":
            if self.shuffle and len(seq) > 2:      # a fresh order for the next round
                self.reshuffle(first=None)
                seq = self._seq()
                if seq[0].uid == t.uid:
                    return seq[1]
            return seq[0]
        return None

    def prev_before(self, t: Track | None) -> Track | None:
        seq = self._seq()
        if not seq:
            return None
        i = next((k for k, x in enumerate(seq) if t is not None and x.uid == t.uid), -1)
        if i > 0:
            return seq[i - 1]
        if i == 0 and self.repeat != "off":
            return seq[-1]
        return seq[0] if i < 0 else None

    def reshuffle(self, first: Track | None):
        import random
        uids = [t.uid for t in self.tracks]
        random.shuffle(uids)
        if first is not None and first.uid in uids:
            uids.remove(first.uid)
            uids.insert(0, first.uid)
        self._order = uids

    def set_shuffle(self, on: bool, current: Track | None):
        self.shuffle = on
        if on:
            self.reshuffle(current)

    # ── edits
    def add(self, new: list[Track], at: int | None = None, current: Track | None = None):
        stamp(new)
        if at is None or at < 0 or at > len(self.tracks):
            self.tracks.extend(new)
        else:
            self.tracks[at:at] = new
        self._map.update({t.uid: t for t in new})
        if self.shuffle:                          # new tracks go to random places after the current one
            import random
            cur = self._order.index(current.uid) + 1 if current is not None and current.uid in self._order else 0
            for t in new:
                self._order.insert(random.randint(cur, len(self._order)), t.uid)

    def remove(self, uids: set[int], current: Track | None = None):
        if current is not None and current.uid in uids:
            self._gone_at = self.index_of(current)
            self._gone_at -= sum(1 for t in self.tracks[:self._gone_at] if t.uid in uids)
        self.tracks = [t for t in self.tracks if t.uid not in uids]
        self._reindex()
        self._order = [u for u in self._order if u not in uids]

    def reorder(self, uids: list[int]):
        m = {t.uid: t for t in self.tracks}
        keep = set(uids)
        self.tracks = [m[u] for u in uids if u in m] + [t for t in self.tracks if t.uid not in keep]

    def clear(self):
        self.tracks = []
        self._order = []
        self._gone_at = 0
        self._map = {}

    def sort(self, key: str):
        keys = {
            "path": lambda t: (natural_key(t.path), t.start),
            "title": lambda t: natural_key(t.display_title()),
            "artist": lambda t: (natural_key(t.artist or t.albumartist), natural_key(t.album), _tn(t)),
            "album": lambda t: (natural_key(t.album), _tn(t)),
            "length": lambda t: t.duration(),
        }
        self.tracks.sort(key=keys.get(key, keys["path"]))


def _tn(t: Track):
    try:
        return (int(t.number or 0), t.start)
    except ValueError:
        return (0, t.start)
