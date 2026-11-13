"""Playback on libmpv without video (vo=null, vid=no: the cover is drawn by Qt).

Two decks (two mpv instances) for crossfade; without crossfade only one is used and the next track is
queued in mpv's own playlist, so mpv plays it gapless (gapless-audio=weak: seamless when the formats
match). CUE tracks are ranges of one file: crossing a boundary inside the same image is just the next
track (no reload, no gap). Output: PCM through WASAPI (shared mode) to the default device, in the layout
Windows has for it (or forced 5.1 / stereo); mpv mixes 7.1 down to 5.1 itself.

mpv calls back from its own thread: every callback becomes a Qt signal (queued into the GUI thread)."""
from __future__ import annotations

import math
import os
import re
import time

from PySide6.QtCore import QObject, QTimer, Signal

from . import audio
from .playlist import Playlist, Track

OBSERVED = ("time-pos", "duration", "pause", "audio-params", "audio-out-params", "audio-codec-name",
            "audio-bitrate", "idle-active", "current-tracks/audio")


def _mpv_version(m) -> tuple[int, int]:
    try:
        v = re.search(r"(\d+)\.(\d+)", str(m.mpv_version or ""))
        return (int(v.group(1)), int(v.group(2))) if v else (0, 40)
    except Exception:
        return (0, 40)


def fmt_num(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".") or "0"


class Deck(QObject):
    """One mpv instance."""
    prop = Signal(object, str, object)       # deck, property, value
    loaded = Signal(object)                  # deck
    ended = Signal(object, str, int)         # deck, reason (eof|stop|error|quit|redirect), error code

    def __init__(self, mpvmod, cfg: dict, name: str):
        super().__init__()
        self.name = name
        self.mpvmod = mpvmod
        opts = dict(
            vo="null", vid="no", audio_display="no", cover_art_auto="no", sub_auto="no", audio_file_auto="no",
            idle="yes", keep_open="no", osc=False, input_default_bindings=False, input_vo_keyboard=False,
            config=False, terminal=False, ytdl=False, load_scripts=False,
            gapless_audio="weak", prefetch_playlist="yes", volume_max=100, volume=100,
            audio_client_name="ArtCore Music", demuxer_max_bytes="64MiB", cache="no",
            audio_channels=audio.CHANNEL_MODES.get(cfg.get("channels", "auto"), "auto-safe"),
            replaygain=cfg.get("replaygain", "album") if cfg.get("replaygain") != "off" else "no",
            replaygain_preamp=float(cfg.get("rg_preamp", 0)),
            replaygain_clip="yes" if cfg.get("rg_clip", True) else "no",
        )
        ao = os.environ.get("ARTCORE_MUSIC_AO")
        if ao:
            opts["ao"] = ao
        dev = cfg.get("audio_device") or "auto"
        if dev != "auto":
            opts["audio_device"] = dev
        if cfg.get("audio_exclusive"):
            opts["audio_exclusive"] = "yes"
        if int(cfg.get("samplerate", 0) or 0):
            opts["audio_samplerate"] = int(cfg["samplerate"])
        self.m = mpvmod.MPV(**opts)
        self.alive = True                    # False after terminate(): the mpv handle is gone
        self.version = _mpv_version(self.m)
        self.track: Track | None = None      # what this deck plays (or loads)
        self.queued: Track | None = None     # what mpv will play after it (gapless)
        self.pending = False                 # a loadfile replace is in flight
        self.af = None
        self.factor = 1.0                    # crossfade gain (linear amplitude)
        self.loaded_at = 0.0
        for name_ in OBSERVED:
            self.m.observe_property(name_, lambda n, v: self.alive and self.prop.emit(self, n, v))
        self.m.event_callback("file-loaded")(lambda _e: self.alive and self.loaded.emit(self))

        def end_file(ev):
            if not self.alive:
                return
            try:
                d = ev.data
                reason = {0: "eof", 2: "stop", 3: "quit", 4: "error", 5: "redirect"}.get(int(d.reason), "eof")
                self.ended.emit(self, reason, int(getattr(d, "error", 0) or 0))
            except Exception:
                pass
        self.m.event_callback("end-file")(end_file)

    def get(self, name: str, default=None):
        """A property (python-mpv's mpv["x"] would read the *option* x)."""
        if not self.alive:
            return default
        try:
            v = getattr(self.m, name.replace("-", "_").replace("/", "_"))
            return default if v is None else v
        except Exception:
            return default

    def node(self, name: str, default=None):
        if not self.alive:
            return default
        try:
            v = self.m._get_property(name)
            return default if v is None else v
        except Exception:
            return default

    def _opts(self, start: float) -> str:
        return f"start={fmt_num(start)}" if start > 0.001 else ""

    def loadfile(self, path: str, mode: str, start: float = 0.0):
        if not self.alive:
            return
        opts = self._opts(start)
        args = [path, mode]
        if opts:
            if self.version >= (0, 38):          # loadfile <url> <flags> <index> <options>
                args += ["-1", opts]
            else:                                # loadfile <url> <flags> <options>
                args += [opts]
        self.m.command("loadfile", *args)

    def load(self, track: Track, offset: float = 0.0, paused: bool = False):
        if not self.alive:
            return
        self.track = track
        self.queued = None
        self.pending = True
        self.af = None if self.af is None else self.af
        self.m.pause = paused
        self.loadfile(track.path, "replace", track.start + offset)

    def queue(self, track: Track | None):
        """Make `track` the only entry after the current one in mpv's playlist (None = nothing after)."""
        if not self.alive:
            return
        try:
            self.m.command("playlist-clear")
        except Exception:
            pass
        self.queued = track
        if track is not None:
            try:
                self.loadfile(track.path, "append", track.start)
            except Exception:
                self.queued = None

    def stop(self):
        self.track = None
        self.queued = None
        self.pending = False
        if not self.alive:
            return
        try:
            self.m.command("stop")
        except Exception:
            pass

    def set_volume(self, master: float, muted: bool):
        """mpv's volume is cubic (gain = (v/100)^3): scale the amplitude by `factor` in that space."""
        v = max(0.0, master) * (max(0.0, self.factor) ** (1.0 / 3.0))
        if not self.alive:
            return
        try:
            self.m.volume = min(100.0, v)
            self.m.mute = bool(muted)
        except Exception:
            pass

    def apply_af(self, cfg: dict, quiet: bool = True) -> str:
        if not self.alive:
            return ""
        ap = self.get("audio-params", {}) or {}
        ch = int(ap.get("channel-count") or 0)
        if not ch:
            return ""
        af = audio.build(cfg, ch, str(ap.get("channels") or ""))
        if af == self.af:
            return ""
        try:
            self.m.af = af
            self.af = af
            return ""
        except Exception as e:
            self.af = None
            try:
                self.m.af = ""
            except Exception:
                pass
            return str(e)

    def terminate(self):
        if not self.alive:
            return
        self.alive = False
        for sig in (self.prop, self.loaded, self.ended):
            try:
                sig.disconnect()
            except (RuntimeError, TypeError):
                pass
        try:
            self.m.terminate()
        except Exception:
            pass


class Engine(QObject):
    track_changed = Signal(object)            # Track (or None when stopped)
    position = Signal(float, float)           # seconds in the track, track length
    paused_changed = Signal(bool)
    format_changed = Signal(dict)             # source / output stream info
    finished = Signal()                       # the end of the playlist
    error = Signal(str)

    TICK_MS = 40

    def __init__(self, mpvmod, cfg: dict, playlist: Playlist):
        super().__init__()
        self.mpvmod = mpvmod
        self.cfg = cfg
        self.pl = playlist
        self.decks = [Deck(mpvmod, cfg, "A")]
        self.active = 0
        self.cur: Track | None = None
        self.paused = True
        self.stopped = True
        self.fade: dict | None = None         # {"old": Deck, "t0": time, "len": seconds}
        self.dead = False                     # shut down: late mpv events are ignored
        self._errors = 0
        self._last_pos = (0.0, 0.0)
        self._seek_guard = 0.0
        self._wire(self.decks[0])
        self.fade_timer = QTimer(self)
        self.fade_timer.setInterval(self.TICK_MS)
        self.fade_timer.timeout.connect(self._fade_tick)
        self.pfade: dict | None = None        # fade on pause / resume: {"deck", "t0", "len", "out"}
        self.pfade_timer = QTimer(self)
        self.pfade_timer.setInterval(15)
        self.pfade_timer.timeout.connect(self._pfade_tick)
        self.set_volume(int(cfg.get("volume", 80)), bool(cfg.get("muted")))

    # ── decks ─────────────────────────────────────────────────
    @property
    def deck(self) -> Deck:
        return self.decks[self.active]

    @property
    def mpv(self):
        return self.deck.m

    def _wire(self, d: Deck):
        d.prop.connect(self._on_prop)
        d.loaded.connect(self._on_loaded)
        d.ended.connect(self._on_ended)

    def _other(self) -> Deck:
        if len(self.decks) < 2:
            d = Deck(self.mpvmod, self.cfg, "B")
            self._wire(d)
            self.decks.append(d)
        return self.decks[1 - self.active]

    # ── commands ──────────────────────────────────────────────
    def play(self, track: Track, offset: float = 0.0, paused: bool = False):
        if self.dead:
            return
        self._pfade_cancel()
        self._end_fade()
        self.cur = track
        self.stopped = False
        self.paused = paused
        self._seek_guard = time.monotonic() + 0.4
        self.deck.factor = 1.0
        self.deck.set_volume(self.volume, self.muted)
        self.deck.load(track, offset, paused)
        self.track_changed.emit(track)
        self.paused_changed.emit(paused)

    def toggle_pause(self):
        if self.stopped or self.cur is None:
            if self.cur is not None:
                self.play(self.cur)
            return
        self.set_paused(not self.paused)

    def set_paused(self, p: bool):
        if self.dead:
            return
        if self.stopped:
            return
        if p and self.fade:
            self._end_fade()
        was_fading_out = self.pfade is not None and self.pfade["out"]
        self._pfade_cancel()
        if p == self.paused and not was_fading_out:
            return
        self.paused = p
        ms = int(self.cfg.get("fade_pause", 0) or 0)
        d = self.deck
        if ms > 0 and not self.muted and not d.pending:
            self.pfade = {"deck": d, "t0": time.monotonic(), "len": ms / 1000.0, "out": p}
            if not p:                                    # resume from silence
                d.factor = 0.0
                d.set_volume(self.volume, self.muted)
                try:
                    d.m.pause = False
                except Exception:
                    pass
            self.pfade_timer.start()
        else:
            try:
                self.mpv.pause = p
            except Exception:
                pass
        self.paused_changed.emit(p)

    def _pfade_tick(self):
        f = self.pfade
        if not f:
            self.pfade_timer.stop()
            return
        k = min(1.0, (time.monotonic() - f["t0"]) / max(0.01, f["len"]))
        f["deck"].factor = (1.0 - k) if f["out"] else k
        f["deck"].set_volume(self.volume, self.muted)
        if k >= 1.0:
            self._pfade_cancel(finish=True)

    def _pfade_cancel(self, finish: bool = False):
        """Stop the pause fade; finish=True: a fade-out has reached silence, pause mpv now."""
        f = self.pfade
        if not f:
            return
        self.pfade = None
        self.pfade_timer.stop()
        d = f["deck"]
        if f["out"] and finish:
            try:
                d.m.pause = True
            except Exception:
                pass
        d.factor = 1.0
        d.set_volume(self.volume, self.muted)

    def stop(self):
        self._pfade_cancel()
        self._end_fade()
        for d in self.decks:
            d.stop()
        self.stopped = True
        self.paused = True
        self.position.emit(0.0, self.cur.duration() if self.cur else 0.0)
        self.paused_changed.emit(True)

    def seek(self, sec: float):
        """Seek to `sec` inside the current track."""
        if self.dead:
            return
        if self.stopped or self.cur is None:
            return
        self._end_fade()
        dur = self.track_length()
        sec = max(0.0, min(sec, dur - 0.05)) if dur else max(0.0, sec)
        self._seek_guard = time.monotonic() + 0.3
        try:
            self.mpv.seek(self.cur.start + sec, "absolute+exact")
        except Exception:
            pass
        self.position.emit(sec, dur)

    def seek_rel(self, delta: float):
        pos, _ = self._last_pos
        self.seek(pos + delta)

    def set_volume(self, v: int, muted: bool):
        self.volume = max(0, min(100, int(v)))
        self.muted = bool(muted)
        for d in self.decks:
            d.set_volume(self.volume, self.muted)

    def track_length(self) -> float:
        t = self.cur
        if t is None:
            return 0.0
        if t.end is not None:
            return t.end - t.start
        dur = float(self.deck.get("duration", 0) or 0)
        if dur:
            return max(0.0, dur - t.start)
        return t.duration()

    def apply_audio(self) -> str:
        err = ""
        for d in self.decks:
            err = d.apply_af(self.cfg) or err
        return err

    def apply_options(self):
        """ReplayGain / channel layout / device changed in the settings."""
        if self.dead:
            return
        rg = self.cfg.get("replaygain", "album")
        for d in self.decks:
            for k, v in (("replaygain", rg if rg != "off" else "no"),
                         ("replaygain_preamp", float(self.cfg.get("rg_preamp", 0))),
                         ("replaygain_clip", "yes" if self.cfg.get("rg_clip", True) else "no"),
                         ("audio_channels", audio.CHANNEL_MODES.get(self.cfg.get("channels", "auto"), "auto-safe")),
                         ("audio_device", self.cfg.get("audio_device") or "auto"),
                         ("audio_exclusive", "yes" if self.cfg.get("audio_exclusive") else "no"),
                         ("audio_samplerate", int(self.cfg.get("samplerate", 0) or 0))):
                try:
                    setattr(d.m, k, v)
                except Exception:
                    pass
        self.apply_audio()
        if self.cur is not None and not self.stopped:        # the output is opened again with the new layout
            try:
                self.mpv.command("ao-reload")
            except Exception:
                pass
        self.requeue()

    def requeue(self):
        """The playlist, repeat or shuffle changed: queue the right next track for gapless."""
        if self.dead:
            return
        d = self.deck
        if self.stopped or d.pending or self.fade or self.cur is None:
            return
        want = self._gapless_next()
        if (want is None) != (d.queued is None) or (want is not None and d.queued is not None and want.uid != d.queued.uid):
            d.queue(want)

    def audio_devices(self) -> list[tuple[str, str]]:
        try:
            return [(x.get("name", ""), x.get("description", "")) for x in (self.mpv.audio_device_list or [])]
        except Exception:
            return []

    def shutdown(self):
        self.dead = True
        self.fade_timer.stop()
        self.pfade_timer.stop()
        for d in self.decks:
            d.terminate()

    # ── gapless / crossfade decisions ─────────────────────────
    def _xfade_len(self, a: Track, b: Track | None) -> float:
        x = float(self.cfg.get("crossfade", 0) or 0)
        if x <= 0 or b is None:
            return 0.0
        if self.cfg.get("xfade_album", True) and a.album_key == b.album_key:
            return 0.0
        return x

    def _gapless_next(self) -> Track | None:
        """What to queue in mpv after the current file (None: nothing, or crossfade / CUE takes care of it)."""
        t = self.cur
        if t is None or t.end is not None:            # a CUE range: the boundary is handled in _on_pos
            return None
        nxt = self.pl.next_after(t, auto=True)
        if nxt is None or self._xfade_len(t, nxt) > 0:
            return None
        return nxt

    def _advance_virtual(self, nxt: Track):
        """The next CUE track of the same image: nothing to load."""
        self.cur = nxt
        self.track_changed.emit(nxt)
        self.requeue()

    def _start_crossfade(self, nxt: Track, length: float):
        old = self.deck
        new = self._other()
        self.active = 1 - self.active
        self.cur = nxt
        new.factor = 0.0
        new.set_volume(self.volume, self.muted)
        new.load(nxt)
        self.fade = {"old": old, "t0": time.monotonic(), "len": length}
        self.fade_timer.start()
        self.track_changed.emit(nxt)

    def _fade_tick(self):
        f = self.fade
        if not f:
            self.fade_timer.stop()
            return
        p = min(1.0, (time.monotonic() - f["t0"]) / max(0.1, f["len"]))
        f["old"].factor = math.cos(p * math.pi / 2)            # equal power
        self.deck.factor = math.sin(p * math.pi / 2)
        f["old"].set_volume(self.volume, self.muted)
        self.deck.set_volume(self.volume, self.muted)
        if p >= 1.0:
            self._end_fade()

    def _end_fade(self):
        f = self.fade
        if not f:
            return
        self.fade = None
        self.fade_timer.stop()
        f["old"].stop()
        f["old"].factor = 1.0
        self.deck.factor = 1.0
        self.deck.set_volume(self.volume, self.muted)
        self.requeue()

    # ── mpv events ────────────────────────────────────────────
    def _on_loaded(self, d: Deck):
        if self.dead or not d.alive:
            return
        if d.pending:
            d.pending = False
        elif d.queued is not None:                     # mpv went on to the queued track by itself (gapless)
            d.track = d.queued
            d.queued = None
            if d is self.deck:
                self.cur = d.track
                self.track_changed.emit(self.cur)
        d.loaded_at = time.monotonic()
        if d is self.deck:
            self._errors = 0
            d.apply_af(self.cfg)
            self.requeue()
            self._emit_format()

    def _on_ended(self, d: Deck, reason: str, err: int):
        if self.dead or not d.alive:
            return
        if d is not self.deck or reason in ("stop", "redirect", "quit"):
            return
        if d.pending and reason != "error":
            return
        if reason == "error":
            d.pending = False
            self._errors += 1
            name = os.path.basename(d.track.path) if d.track else ""
            self.error.emit(f"{name}: mpv error {err}")
            nxt = self.pl.next_after(self.cur, auto=False) if self.cur else None
            if nxt is not None and self._errors < max(3, len(self.pl.tracks)):
                QTimer.singleShot(150, lambda: self.play(nxt))
            else:
                self.stop()
            return
        if d.queued is not None:                       # gapless: mpv loads the queued one now
            return
        if self.fade:
            return
        nxt = self.pl.next_after(self.cur, auto=True) if self.cur else None
        if nxt is not None:
            self.play(nxt)
        else:
            self.stopped = True
            self.paused = True
            self.paused_changed.emit(True)
            self.position.emit(0.0, self.cur.duration() if self.cur else 0.0)
            self.finished.emit()

    def _on_prop(self, d: Deck, name: str, val):
        if self.dead or not d.alive:
            return
        if d is not self.deck:
            return
        if name == "time-pos":
            if val is None or self.cur is None or d.pending:
                return
            self._on_pos(float(val))
        elif name == "pause":
            if val is not None and not self.stopped and bool(val) != self.paused and not d.pending:
                self.paused = bool(val)
                self.paused_changed.emit(self.paused)
        elif name in ("audio-params", "audio-out-params", "audio-codec-name", "current-tracks/audio"):
            if name == "audio-params":
                err = d.apply_af(self.cfg)
                if err:
                    self.error.emit(err)
            self._emit_format()
        elif name == "duration" and val:
            self._on_pos(float(self.deck.get("time-pos", 0) or 0))

    def _on_pos(self, p: float):
        t = self.cur
        if t is None:
            return
        rel = p - t.start
        dur = self.track_length()
        self._last_pos = (max(0.0, rel), dur)
        self.position.emit(max(0.0, rel), dur)
        if self.stopped or self.fade or time.monotonic() < self._seek_guard:
            return
        # the end of a CUE range
        if t.end is not None and p >= t.end - 0.02:
            nxt = self.pl.next_after(t, auto=True)
            if nxt is None:
                self.stop()
                self.finished.emit()
            elif nxt.uid != t.uid and os.path.normcase(nxt.path) == os.path.normcase(t.path) \
                    and abs(nxt.start - t.end) < 0.05:
                self._advance_virtual(nxt)
            else:
                self.play(nxt)
            return
        # crossfade into the next track
        if self.deck.queued is None and dur and not self.paused:
            nxt = self.pl.next_after(t, auto=True)
            x = self._xfade_len(t, nxt)
            if x > 0 and nxt is not None and dur > 2 * x and (nxt.duration() == 0 or nxt.duration() > x) \
                    and dur - rel <= x:
                self._start_crossfade(nxt, x)

    def _emit_format(self):
        d = self.deck
        ap = d.get("audio-params", {}) or {}
        op = d.get("audio-out-params", {}) or {}
        tr = d.node("current-tracks/audio", {}) or {}
        info = {
            "codec": str(d.get("audio-codec-name", "") or tr.get("codec", "") or ""),
            "profile": str(tr.get("codec-profile", "") or ""),
            "rate": int(tr.get("demux-samplerate") or ap.get("samplerate") or 0),
            "channels": int(tr.get("demux-channel-count") or ap.get("channel-count") or 0),
            "layout": str(tr.get("demux-channels") or ap.get("channels") or ""),
            "out_channels": int(op.get("channel-count") or 0),
            "out_layout": str(op.get("channels") or ""),
            "out_rate": int(op.get("samplerate") or 0),
            "kbps": int((d.get("audio-bitrate", 0) or 0) // 1000),
            "af": d.af or "",
        }
        self.format_changed.emit(info)
