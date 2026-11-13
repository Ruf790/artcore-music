"""Windows 10 / 11 media controls (SMTC): the card above the volume flyout and on the lock screen with the
cover, title, artist and ⏮ ⏯ ⏭; the keyboard's media keys and Bluetooth headphones reach us through it too.

A desktop app gets its own controls through a Windows.Media.Playback.MediaPlayer that plays nothing: its
CommandManager is switched off, so the buttons only come to us (ButtonPressed) and we say what is on.
Everything WinRT runs in one worker thread (MTA); button presses come back as a Qt signal. Needs the
winrt-* packages (pywinrt); without them, or off Windows, it does nothing."""
from __future__ import annotations

import queue
import sys
import threading
import time
from datetime import timedelta

from PySide6.QtCore import QObject, Signal


class Smtc(QObject):
    button = Signal(str)                 # play | pause | stop | next | prev
    seek = Signal(float)                 # seconds, from the timeline of the card
    ready = Signal(bool, str)            # works, error text

    def __init__(self):
        super().__init__()
        self.ok = False
        self.error = ""
        self.q: queue.Queue = queue.Queue()
        self.alive = True
        self._player = None
        self._smtc = None
        self._last_cover = None
        self.started = threading.Event()
        if sys.platform != "win32":
            self.error = "not Windows"
            self.started.set()
            return
        self.thread = threading.Thread(target=self._run, name="smtc", daemon=True)
        self.thread.start()

    # ── worker ────────────────────────────────────────────────
    def _run(self):
        try:
            try:
                from winrt.runtime import ApartmentType, init_apartment
                init_apartment(ApartmentType.MULTI_THREADED)
            except Exception:
                pass                                        # already initialised in this thread
            from winrt.windows.media import MediaPlaybackStatus, SystemMediaTransportControlsButton as B
            from winrt.windows.media.playback import MediaPlayer
            self._B, self._S = B, MediaPlaybackStatus
            self._player = MediaPlayer()
            self._player.command_manager.is_enabled = False
            s = self._smtc = self._player.system_media_transport_controls
            s.is_enabled = True
            s.is_play_enabled = s.is_pause_enabled = s.is_next_enabled = s.is_previous_enabled = True
            s.is_stop_enabled = True
            s.playback_status = MediaPlaybackStatus.CLOSED
            s.add_button_pressed(self._pressed)
            try:
                s.add_playback_position_change_requested(
                    lambda _s, a: self.seek.emit(a.requested_playback_position.total_seconds()))
            except Exception:
                pass
            self.ok = True
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            self.ok = False
        self.started.set()
        self.ready.emit(self.ok, self.error)
        while self.alive:
            job = self.q.get()
            if job is None:
                break
            if not self.ok:
                continue
            try:
                job()
            except Exception as e:
                self.error = f"{type(e).__name__}: {e}"
        try:
            if self._smtc is not None:
                self._smtc.display_updater.clear_all()
                self._smtc.display_updater.update()
                self._smtc.is_enabled = False
            if self._player is not None:
                self._player.close()
        except Exception:
            pass

    def _pressed(self, _sender, args):
        B = self._B
        name = {B.PLAY: "play", B.PAUSE: "pause", B.STOP: "stop", B.NEXT: "next", B.PREVIOUS: "prev"}.get(args.button)
        if name:
            self.button.emit(name)

    def _thumb(self, data: bytes):
        """Cover bytes → a stream reference (DataWriter into an in-memory stream)."""
        from winrt.windows.foundation import AsyncStatus
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream, RandomAccessStreamReference
        stream = InMemoryRandomAccessStream()
        w = DataWriter(stream)
        w.write_bytes(data)
        op = w.store_async()
        t0 = time.monotonic()
        while op.status == AsyncStatus.STARTED and time.monotonic() - t0 < 5:
            time.sleep(0.005)
        w.flush_async().get()
        w.detach_stream()
        stream.seek(0)
        return RandomAccessStreamReference.create_from_stream(stream)

    def _do_track(self, title: str, artist: str, album: str, cover: bytes | None, track_no: int):
        from winrt.windows.media import MediaPlaybackType
        du = self._smtc.display_updater
        du.type = MediaPlaybackType.MUSIC
        mp = du.music_properties
        mp.title = title or ""
        mp.artist = artist or ""
        mp.album_title = album or ""
        try:
            mp.track_number = max(0, int(track_no or 0))
        except Exception:
            pass
        if cover != self._last_cover:
            self._last_cover = cover
            du.thumbnail = self._thumb(cover) if cover else None
        du.update()

    def _do_status(self, status: str):
        S = self._S
        self._smtc.playback_status = {"playing": S.PLAYING, "paused": S.PAUSED, "stopped": S.STOPPED}.get(
            status, S.CLOSED)

    def _do_timeline(self, pos: float, dur: float):
        from winrt.windows.media import SystemMediaTransportControlsTimelineProperties
        tl = SystemMediaTransportControlsTimelineProperties()
        tl.start_time = timedelta(0)
        tl.min_seek_time = timedelta(0)
        tl.end_time = timedelta(seconds=max(0.0, dur))
        tl.max_seek_time = timedelta(seconds=max(0.0, dur))
        tl.position = timedelta(seconds=max(0.0, min(pos, dur) if dur else 0.0))
        self._smtc.update_timeline_properties(tl)

    def _probe(self, out: dict):
        du = self._smtc.display_updater
        out["title"] = du.music_properties.title
        out["status"] = int(self._smtc.playback_status)
        out["thumb"] = du.thumbnail is not None

    # ── from the GUI thread ───────────────────────────────────
    def set_track(self, title: str, artist: str = "", album: str = "", cover: bytes | None = None,
                  track_no: int = 0):
        self.q.put(lambda: self._do_track(title, artist, album, cover or None, track_no))

    def set_status(self, status: str):
        """playing | paused | stopped | closed"""
        self.q.put(lambda: self._do_status(status))

    def set_timeline(self, pos: float, dur: float):
        self.q.put(lambda: self._do_timeline(pos, dur))

    def probe(self, timeout: float = 5.0) -> dict:
        """What the controls show now (self-test)."""
        out: dict = {}
        done = threading.Event()
        self.q.put(lambda: (self._probe(out), done.set()))
        done.wait(timeout)
        return out

    def stop(self):
        self.alive = False
        self.q.put(None)
        t = getattr(self, "thread", None)
        if t is not None:
            t.join(2.0)
