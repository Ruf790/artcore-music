"""Settings in %APPDATA%\\ArtCoreMusic\\config.json, the playlist session in session.json.
A portable.ini next to the exe keeps everything in .\\Data instead."""
from __future__ import annotations

import copy
import json
import os
import sys

DEFAULTS = {
    "language":      "ru",
    "volume":        80,
    "muted":         False,
    "single_window": True,          # files opened from Explorer go to the running player
    "on_top":        False,
    "resume":        True,          # playlist, track and position come back on the next start
    "repeat":        "off",         # off | all | one
    "shuffle":       False,
    # sound
    "eq":            [0] * 10,      # equalizer, dB per band (audio.BANDS)
    "eq_preset":     "flat",
    "channels":      "auto",        # auto (as set in Windows) | 5.1 (7.1 is mixed down) | stereo
    "upmix":         False,         # stereo → 5.1 (ffmpeg surround)
    "center_db":     0.0,           # centre level, dB
    "lfe_db":        0.0,           # subwoofer level, dB
    "replaygain":    "album",       # album | track | off
    "rg_preamp":     0.0,
    "rg_clip":       True,          # lower the gain instead of clipping
    "crossfade":     0,             # seconds, 0 = gapless
    "xfade_album":   True,          # no crossfade between tracks of the same album (keep it gapless)
    "audio_device":  "auto",
    # window
    "media_keys":    True,          # global ⏮ ⏯ ⏭ keys of the keyboard
    "check_updates": True,
    "last_update_check": 0,
    "update_notified": "",
    "geometry":      "",
    "splitter":      [],
    "mini_geometry": [],
    "last_dir":      "",
    "columns":       [],            # playlist column widths
}


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_portable() -> bool:
    return os.path.isfile(os.path.join(app_dir(), "portable.ini"))


def data_dir() -> str:
    override = os.environ.get("ARTCORE_MUSIC_DATA")          # tests
    if override:
        path = override
    elif is_portable():
        path = os.path.join(app_dir(), "Data")
    else:
        base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
        path = os.path.join(base, "ArtCoreMusic")
    os.makedirs(path, exist_ok=True)
    return path


def _path(name: str = "config.json") -> str:
    return os.path.join(data_dir(), name)


def _read(name: str):
    try:
        with open(_path(name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write(name: str, data) -> None:
    path = _path(name)
    try:
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def load() -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    saved = _read("config.json")
    if isinstance(saved, dict):
        cfg.update({k: v for k, v in saved.items() if k in DEFAULTS})
    if cfg.get("language") not in ("ru", "en"):
        cfg["language"] = "ru"
    if cfg.get("repeat") not in ("off", "all", "one"):
        cfg["repeat"] = "off"
    if cfg.get("channels") not in ("auto", "5.1", "stereo"):
        cfg["channels"] = "auto"
    if cfg.get("replaygain") not in ("album", "track", "off"):
        cfg["replaygain"] = "album"
    if not isinstance(cfg.get("eq"), list) or len(cfg["eq"]) != 10:
        cfg["eq"] = [0] * 10
    return cfg


def save(cfg: dict) -> None:
    _write("config.json", cfg)


def load_session() -> dict:
    s = _read("session.json")
    return s if isinstance(s, dict) else {}


def save_session(session: dict) -> None:
    _write("session.json", session)
