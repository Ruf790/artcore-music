"""The waveform for the seek bar (SoundCloud style).

A separate, silent mpv instance decodes the track as fast as it can (ao=pcm, untimed) to 16-bit mono at a low
sample rate; the loudness (RMS) of PEAKS equal slices of it, scaled to 0..255, is the waveform. One background
thread; results are kept in memory and on disk (Data/waveforms/<hash>.bin, PEAKS bytes), so a track is decoded
only once. CUE tracks get the range of their image."""
from __future__ import annotations

import hashlib
import math
import os
import tempfile
import threading
from array import array
from collections import OrderedDict

from PySide6.QtCore import QObject, Signal

from . import config
from .playlist import Track

PEAKS = 600
RATE = 3000                # Hz: plenty for the outline, fast to decode and to sum up
MAX_SECONDS = 4 * 3600     # longer recordings are not drawn


def key_of(tr: Track) -> str:
    """Changes when the file changes (size / time) or for another CUE range of it."""
    try:
        st = os.stat(tr.path)
        stamp = f"{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        stamp = "?"
    raw = f"{os.path.normcase(os.path.abspath(tr.path))}|{stamp}|{tr.start:.2f}|{tr.end if tr.end is not None else ''}"
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()


def _cache_path(key: str) -> str:
    d = os.path.join(config.data_dir(), "waveforms")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, key + ".bin")


def peaks_from_pcm(raw: bytes, n: int = PEAKS) -> bytes:
    """16-bit mono PCM → n loudness values 0..255 (RMS per slice, the loudest slice = 255)."""
    a = array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    if not a:
        return b""
    step = len(a) / n
    vals = []
    for i in range(n):
        s = a[int(i * step): max(int((i + 1) * step), int(i * step) + 1)]
        vals.append(math.sqrt(sum(x * x for x in s) / len(s)) if s else 0.0)
    top = max(vals) or 1.0
    return bytes(min(255, int(round(255 * v / top))) for v in vals)


def decode(mpvmod, tr: Track) -> bytes:
    """Decode `tr` silently with its own mpv and return the waveform ("" if it could not be read)."""
    fd, out = tempfile.mkstemp(prefix="artcore_wave_", suffix=".pcm")
    os.close(fd)
    m = None
    try:
        m = mpvmod.MPV(vo="null", vid="no", ao="pcm", ao_pcm_file=out, ao_pcm_waveheader=False, untimed=True,
                       audio_format="s16", audio_samplerate=RATE, audio_channels="mono", config=False,
                       terminal=False, load_scripts=False, ytdl=False, idle="yes", replaygain="no", cache="no",
                       audio_display="no", cover_art_auto="no", sub_auto="no", audio_file_auto="no", volume=100)
        if tr.start > 0.001:
            m["start"] = f"{tr.start:.3f}"
        if tr.end is not None:
            m["end"] = f"{tr.end:.3f}"
        else:
            m["end"] = f"{tr.start + MAX_SECONDS:.0f}"
        m.play(tr.path)
        m.wait_for_playback()
    except Exception:
        pass
    finally:
        if m is not None:
            try:
                m.terminate()
            except Exception:
                pass
    try:
        with open(out, "rb") as f:
            raw = f.read()
    except OSError:
        raw = b""
    finally:
        try:
            os.remove(out)
        except OSError:
            pass
    return peaks_from_pcm(raw) if len(raw) >= RATE // 2 else b""   # under 0.25 s: nothing worth drawing


class Waveforms(QObject):
    """ready(key, peaks) comes in the GUI thread. request() puts a track first in line (the playing one);
    prefetch() adds one at the end (up next)."""
    ready = Signal(str, bytes)

    def __init__(self, mpvmod):
        super().__init__()
        self.mpvmod = mpvmod
        self.mem: OrderedDict[str, bytes] = OrderedDict()
        self.jobs: list[tuple[str, Track]] = []
        self.cond = threading.Condition()
        self.alive = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def cached(self, key: str) -> bytes | None:
        with self.cond:                            # an RLock: shared with the worker thread
            if key in self.mem:
                self.mem.move_to_end(key)
                return self.mem[key]
        try:
            with open(_cache_path(key), "rb") as f:
                data = f.read()
        except OSError:
            return None
        self._remember(key, data)
        return data

    def _remember(self, key: str, data: bytes):
        with self.cond:
            self.mem[key] = data
            self.mem.move_to_end(key)
            while len(self.mem) > 64:
                self.mem.popitem(last=False)

    def request(self, tr: Track, front: bool = True) -> str:
        """The key; the waveform comes as ready() (at once from the cache)."""
        key = key_of(tr)
        data = self.cached(key)
        if data is not None:
            self.ready.emit(key, data)
            return key
        if "://" in tr.path or not os.path.isfile(tr.path):
            return key
        with self.cond:
            self.jobs = [j for j in self.jobs if j[0] != key]
            if front:
                self.jobs.insert(0, (key, tr))
            else:
                self.jobs.append((key, tr))
            del self.jobs[3:]                      # skipping through the list: only the latest few matter
            self.cond.notify()
        return key

    def prefetch(self, tr: Track | None):
        if tr is not None and self.cached(key_of(tr)) is None:
            self.request(tr, front=False)

    def _run(self):
        while True:
            with self.cond:
                while self.alive and not self.jobs:
                    self.cond.wait()
                if not self.alive:
                    return
                key, tr = self.jobs.pop(0)
            data = decode(self.mpvmod, tr)
            if data:
                try:
                    with open(_cache_path(key), "wb") as f:
                        f.write(data)
                except OSError:
                    pass
            with self.cond:
                if not self.alive:
                    return
                if data:
                    self._remember(key, data)
                    self.ready.emit(key, data)

    def stop(self):
        with self.cond:
            self.alive = False
            self.jobs = []
            self.cond.notify()
        self.thread.join(2.0)
