"""Tags (artist, album, title, year, track number), stream info (bits, rate, channels, length) and cover art.
mutagen reads all of it; covers also come from cover.jpg / folder.jpg / front.jpg next to the file."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from . import COVER_NAMES

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")


@dataclass
class Tags:
    title: str = ""
    artist: str = ""
    album: str = ""
    albumartist: str = ""
    year: str = ""
    track: str = ""
    disc: str = ""
    genre: str = ""
    length: float = 0.0
    bits: int = 0
    rate: int = 0
    channels: int = 0
    bitrate: int = 0             # kbps
    cuesheet: str = ""           # embedded CUESHEET (FLAC / APE / WavPack)
    has_picture: bool = False
    extra: dict = field(default_factory=dict)


def _first(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        v = v[0] if v else ""
    if hasattr(v, "text"):                       # ID3 frames
        t = v.text
        v = t[0] if isinstance(t, list) and t else t
    if isinstance(v, tuple):                     # MP4 trkn (n, total)
        v = v[0]
    return str(v).strip()


def _num(s: str) -> str:
    """'03/12' → '3'."""
    m = re.match(r"\s*(\d+)", s or "")
    return str(int(m.group(1))) if m else ""


def _year(s: str) -> str:
    m = re.search(r"(\d{4})", s or "")
    return m.group(1) if m else ""


ID3_MAP = {"title": "TIT2", "artist": "TPE1", "album": "TALB", "albumartist": "TPE2", "year": "TDRC",
           "track": "TRCK", "disc": "TPOS", "genre": "TCON"}
MP4_MAP = {"title": "\xa9nam", "artist": "\xa9ART", "album": "\xa9alb", "albumartist": "aART", "year": "\xa9day",
           "track": "trkn", "disc": "disk", "genre": "\xa9gen"}
VORBIS_MAP = {"title": "title", "artist": "artist", "album": "album", "albumartist": "albumartist", "year": "date",
              "track": "tracknumber", "disc": "discnumber", "genre": "genre"}
ASF_MAP = {"title": "Title", "artist": "Author", "album": "WM/AlbumTitle", "albumartist": "WM/AlbumArtist",
           "year": "WM/Year", "track": "WM/TrackNumber", "genre": "WM/Genre"}
APE_MAP = {"title": "Title", "artist": "Artist", "album": "Album", "albumartist": "Album Artist", "year": "Year",
           "track": "Track", "disc": "Disc", "genre": "Genre"}


def read(path: str) -> Tags:
    tg = Tags()
    try:
        import mutagen
        f = mutagen.File(path)
    except Exception:
        f = None
    if f is None:
        return tg
    info = getattr(f, "info", None)
    if info is not None:
        tg.length = float(getattr(info, "length", 0) or 0)
        tg.rate = int(getattr(info, "sample_rate", 0) or 0)
        tg.channels = int(getattr(info, "channels", 0) or 0)
        tg.bits = int(getattr(info, "bits_per_sample", 0) or getattr(info, "bits_per_raw_sample", 0) or 0)
        br = int(getattr(info, "bitrate", 0) or 0)
        tg.bitrate = br // 1000 if br > 10000 else br
    tags = f.tags
    if tags is None:
        return tg
    keys = set()
    try:
        keys = set(tags.keys())
    except Exception:
        pass
    cls = type(tags).__name__
    if cls == "ID3" or any(k[:4] in ("TIT2", "TPE1", "TALB", "APIC") for k in keys):
        for attr, frame in ID3_MAP.items():
            setattr(tg, attr, _first(tags.get(frame)))
        tg.has_picture = any(k.startswith("APIC") for k in keys)
    elif cls == "MP4Tags":
        for attr, k in MP4_MAP.items():
            setattr(tg, attr, _first(tags.get(k)))
        tg.has_picture = "covr" in keys
    elif cls == "APEv2":
        low = {k.lower(): k for k in keys}
        for attr, k in APE_MAP.items():
            real = low.get(k.lower())
            setattr(tg, attr, _first(tags.get(real)) if real else "")
        tg.cuesheet = _first(tags.get(low["cuesheet"])) if "cuesheet" in low else ""
        tg.has_picture = "cover art (front)" in low
    elif cls == "ASFTags":                       # WMA
        for attr, k in ASF_MAP.items():
            setattr(tg, attr, _first(tags.get(k)))
        tg.has_picture = "WM/Picture" in keys
    else:                                        # Vorbis comments: FLAC, Ogg, Opus
        get = lambda k: _first(tags.get(k) or tags.get(k.upper()))
        for attr, k in VORBIS_MAP.items():
            setattr(tg, attr, get(k))
        if not tg.year:
            tg.year = get("year")
        if not tg.albumartist:
            tg.albumartist = get("album artist")
        tg.cuesheet = get("cuesheet")
        tg.has_picture = bool(getattr(f, "pictures", None)) or "metadata_block_picture" in {k.lower() for k in keys}
    tg.track = _num(tg.track)
    tg.disc = _num(tg.disc)
    tg.year = _year(tg.year)
    return tg


def embedded_picture(path: str) -> bytes:
    """The front cover (or the first picture) stored in the file's tags."""
    try:
        import mutagen
        f = mutagen.File(path)
    except Exception:
        return b""
    if f is None:
        return b""
    pics = []
    try:
        for p in getattr(f, "pictures", None) or []:          # FLAC
            pics.append((getattr(p, "type", 0), p.data))
        tags = f.tags
        if tags is not None:
            keys = list(tags.keys())
            for k in keys:
                if str(k).startswith("APIC"):                    # ID3
                    fr = tags[k]
                    pics.append((getattr(fr, "type", 0), fr.data))
            if "covr" in keys:                                   # MP4
                for c in tags["covr"]:
                    pics.append((3, bytes(c)))
            for k in keys:
                lk = str(k).lower()
                if lk == "metadata_block_picture":               # Ogg / Opus
                    import base64
                    from mutagen.flac import Picture
                    for b64 in tags[k]:
                        try:
                            pic = Picture(base64.b64decode(b64))
                            pics.append((pic.type, pic.data))
                        except Exception:
                            pass
                elif lk.startswith("cover art"):                 # APEv2: "name\0data"
                    raw = bytes(tags[k].value)
                    pics.append((3 if "front" in lk else 0, raw.split(b"\x00", 1)[-1]))
    except Exception:
        pass
    if not pics:
        return b""
    pics.sort(key=lambda p: 0 if p[0] == 3 else 1)                # 3 = front cover
    return pics[0][1]


def folder_cover(path: str) -> str:
    """cover.jpg / folder.jpg / front.png … next to the file (also one level up for CD1/CD2 folders)."""
    d = os.path.dirname(path)
    for folder in (d, os.path.dirname(d)):
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        imgs = [n for n in names if n.lower().endswith(IMAGE_EXT)]
        for want in COVER_NAMES:
            for n in imgs:
                if os.path.splitext(n)[0].lower() == want:
                    return os.path.join(folder, n)
        if folder == d:
            for n in imgs:                               # «Artist - Album (front).jpg», «AlbumArt_{…}_Large.jpg»
                low = n.lower()
                if "front" in low or "cover" in low or "albumart" in low and "large" in low:
                    return os.path.join(folder, n)
            if len(imgs) == 1:
                return os.path.join(folder, imgs[0])
    return ""


def cover_bytes(path: str) -> bytes:
    data = embedded_picture(path)
    if data:
        return data
    p = folder_cover(path)
    if p:
        try:
            with open(p, "rb") as f:
                return f.read()
        except OSError:
            pass
    return b""


# ── writing ──────────────────────────────────────────────────
EDITABLE = ("title", "artist", "album", "albumartist", "year", "track", "genre")


def write(path: str, values: dict) -> None:
    """Write tags: {"title": "…", "artist": "…", …} (keys of EDITABLE); "" removes the tag. Raises on failure.
    MP3 / WAV / AIFF / DSF get ID3v2.3 (read by every player and by Windows), FLAC / Ogg / Opus Vorbis comments,
    M4A MP4 atoms, APE / WavPack / TAK / MPC APEv2, WMA ASF."""
    import mutagen
    f = mutagen.File(path)
    if f is None:
        raise ValueError("unsupported file")
    if f.tags is None:
        f.add_tags()
    tags = f.tags
    cls = type(tags).__name__
    vals = {k: (str(v) if v is not None else "").strip() for k, v in values.items() if k in EDITABLE}
    from mutagen.id3 import ID3
    if isinstance(tags, ID3):                                # MP3, and the ID3 chunk of WAV / AIFF / DSF
        from mutagen import id3
        for attr, v in vals.items():
            fid = ID3_MAP[attr]
            tags.delall(fid)
            if fid == "TDRC":
                tags.delall("TYER")
            if v:
                tags.add(getattr(id3, fid)(encoding=3, text=[v]))
        try:
            f.save(v2_version=3)
        except TypeError:
            f.save()
        return
    if cls == "MP4Tags":
        for attr, v in vals.items():
            k = MP4_MAP[attr]
            if attr == "track":
                old = tags.get("trkn") or [(0, 0)]
                n = int(_num(v) or 0)
                if n:
                    tags["trkn"] = [(n, old[0][1] if old and len(old[0]) > 1 else 0)]
                else:
                    tags.pop("trkn", None)
            elif v:
                tags[k] = [v]
            else:
                tags.pop(k, None)
    elif cls == "APEv2":
        low = {k.lower(): k for k in tags.keys()}
        for attr, v in vals.items():
            k = APE_MAP[attr]
            if k.lower() in low:
                del tags[low[k.lower()]]
            if v:
                tags[k] = v
    elif cls == "ASFTags":
        for attr, v in vals.items():
            k = ASF_MAP[attr]
            if k in tags:
                del tags[k]
            if v:
                tags[k] = [v]
    else:                                                    # Vorbis comments
        for attr, v in vals.items():
            k = VORBIS_MAP[attr]
            for old in [x for x in tags.keys() if x.lower() == k or (attr == "year" and x.lower() == "year")]:
                del tags[old]
            if v:
                tags[k] = [v]
    f.save()


FILENAME_PATTERNS = {
    "artist_title":       r"^(?P<artist>.+?)\s+[-–—]\s+(?P<title>.+)$",
    "track_artist_title": r"^(?P<track>\d{1,3})[\s.\-_)]*\s*(?P<artist>.+?)\s+[-–—]\s+(?P<title>.+)$",
    "track_title":        r"^(?P<track>\d{1,3})[\s.\-_)]+\s*(?P<title>.+)$",
    "artist_album_track_title": r"^(?P<artist>.+?)\s+[-–—]\s+(?P<album>.+?)\s+[-–—]\s+(?P<track>\d{1,3})\s+[-–—]\s+"
                                r"(?P<title>.+)$",
    "title":              r"^(?P<title>.+)$",
}


def from_filename(path: str, pattern: str) -> dict:
    """Tags guessed from «05 - DJ X - Track Y.mp3» by a FILENAME_PATTERNS key ({} if it does not fit)."""
    stem = os.path.splitext(os.path.basename(path))[0].replace("_", " ").strip()
    m = re.match(FILENAME_PATTERNS[pattern], stem)
    if not m:
        return {}
    out = {k: re.sub(r"\s+", " ", v).strip() for k, v in m.groupdict().items() if v}
    if "track" in out:
        out["track"] = _num(out["track"])
    return out
