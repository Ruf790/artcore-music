"""The main window: now playing (cover, tags, format line), the playlist, the transport bar; the mini player."""
from __future__ import annotations

import os
import queue
import threading
import time

from PySide6.QtCore import QByteArray, QObject, QPoint, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QActionGroup, QColor, QFont, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap, QShortcut)
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QMainWindow, QTabBar,
                               QMenu, QMessageBox, QSlider, QSplitter, QSystemTrayIcon, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from . import APP_TITLE, AUDIO_EXT, CUE_EXT, PLAYLIST_EXT, VERSION, audio, config, meta, style, winint
from .engine import Engine
from .library import Favorites, History
from .i18n import t
from .playlist import Playlist, Track, expand, fill_tags, is_url, write_m3u
from .waveform import Waveforms, key_of
from . import lyrics as lyrics_mod
from .widgets import (ChannelMeters, ClickLabel, CoverView, LevelState, LyricsView, PlaylistView, RoomMeters,
                      Toast, WaveSeekBar, ctl_button, elide, fmt_time)

COL_N, COL_TITLE, COL_ARTIST, COL_ALBUM, COL_LEN, COL_FAV = range(6)
NCOLS = 6
COL_KEYS = {"n": COL_N, "artist": COL_ARTIST, "album": COL_ALBUM, "len": COL_LEN, "fav": COL_FAV}
ACCENT_TEXT = "#8fb8ff"
STAR = "#f5c518"
ROW_PAD = {"compact": 2, "normal": 5, "large": 9}
SLEEP_MINUTES = (15, 30, 45, 60, 90, 120)
UID = Qt.UserRole + 1


class Bridge(QObject):
    tagged = Signal(int)                 # uid whose tags were read
    update = Signal(object, str)         # update check: info or None, error text
    cover = Signal(int, bytes)           # uid, image bytes


class TagReader:
    """One background thread reading tags (mutagen) for the playlist; results come back as Bridge.tagged."""

    def __init__(self, bridge: Bridge):
        self.q: queue.Queue = queue.Queue()
        self.bridge = bridge
        self.alive = True
        self.lock = threading.Lock()         # stop() waits for an emit in progress; none after it
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def add(self, tracks: list[Track]):
        for tr in tracks:
            if not tr.tagged:
                self.q.put(tr)

    def _run(self):
        while self.alive:
            tr = self.q.get()
            if tr is None:
                break
            if tr.tagged:
                continue
            try:
                fill_tags(tr)
            except Exception:
                tr.tagged = True
            with self.lock:
                if not self.alive:              # the window is closing: its Bridge may be gone
                    break
                self.bridge.tagged.emit(tr.uid)

    def stop(self):
        with self.lock:
            self.alive = False
        self.q.put(None)
        self.thread.join(1.0)                   # a file being read is finished, not cut


class MiniWindow(QWidget):
    """The mini player: a translucent widget over the windows — the blurred cover as its background, the cover,
    title, waveform, ⏮ ⏯ ⏭, shuffle / repeat, volume. Two looks: a card (cfg mini_style = "card") or a strip
    ("strip"). Drag it anywhere; the wheel = volume; double-click or Esc = the big window."""
    RADIUS = 16

    def __init__(self, win: "MainWindow"):
        flags = Qt.Window | Qt.FramelessWindowHint
        if win.cfg.get("mini_on_top", True):
            flags |= Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.win = win
        self.strip = win.cfg.get("mini_style", "card") == "strip"
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(style.app_icon())
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self._bg: QPixmap | None = None
        self._bg_src: QPixmap | None = None
        self._hover = False
        self._drag = None
        self._vol_until = 0.0

        white = "background: transparent; color: #ffffff;"
        dim = "background: transparent; color: rgba(255,255,255,175); font-size: 8.5pt;"
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 12, 10) if not self.strip else lay.setContentsMargins(12, 10, 10, 8)
        lay.setSpacing(14 if not self.strip else 12)
        self.cover = CoverView(radius=0.1)
        side = 64 if self.strip else 112
        self.cover.setFixedSize(side, side)
        self.cover.clicked.connect(win.toggle_mini)
        self.cover.setToolTip(t("mini_back") + " (Esc)")
        self.cover.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.cover, 0, Qt.AlignTop if not self.strip else Qt.AlignVCenter)

        self.title = QLabel()
        self.title.setStyleSheet(white + "font-weight: 700; font-size: 10.5pt;")
        self.artist = QLabel()
        self.artist.setStyleSheet(dim)
        self.time = QLabel("0:00")
        self.time.setStyleSheet(dim)
        self.seek = WaveSeekBar()
        self.seek.setFixedHeight(32 if self.strip else 40)
        self.seek.seek.connect(win.engine.seek)

        def btn(icon, tip, size, slot):
            b = ctl_button(icon, tip, size, slot)
            b.setStyleSheet("QToolButton { padding: 4px; }")
            return b
        self.b_shuffle = btn("mdi6.shuffle-variant", t("shuffle") + " (S)", 15, win.toggle_shuffle)
        self.b_prev = btn("fa6s.backward-step", t("prev"), 15, win.prev)
        self.b_play = btn("fa6s.play", t("play") + " (Space)", 19, win.toggle_pause)
        self.b_next = btn("fa6s.forward-step", t("next"), 15, win.next)
        self.b_repeat = btn("mdi6.repeat", t("repeat") + " (R)", 15, win.cycle_repeat)
        self.b_mute = btn("fa6s.volume-high", t("mute") + " (M) · " + t("mini_wheel"), 13, win.toggle_mute)
        self.b_pin = btn("fa6s.thumbtack", t("mini_pin"), 12, self.toggle_pin)
        self.b_look = btn("fa6s.table-columns" if not self.strip else "fa6s.square", t("mini_look"), 12,
                          win.switch_mini_look)
        self.b_back = btn("fa6s.up-right-and-down-left-from-center", t("mini_back") + " (Ctrl+M)", 12,
                          win.toggle_mini)
        ctl = QHBoxLayout()
        ctl.setSpacing(0)
        for b in (self.b_shuffle, self.b_prev, self.b_play, self.b_next, self.b_repeat):
            ctl.addWidget(b)
        ctl.addStretch(1)
        ctl.addWidget(self.time)
        ctl.addSpacing(4)
        for b in (self.b_mute, self.b_pin, self.b_look, self.b_back):
            ctl.addWidget(b)
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(self.title)
        text.addWidget(self.artist)
        col = QVBoxLayout()
        col.setSpacing(4 if not self.strip else 2)
        if self.strip:
            top = QHBoxLayout()
            top.addLayout(text, 1)
            top.addLayout(ctl)
            col.addLayout(top)
            col.addWidget(self.seek)
            self.resize(640, 88)
            self._text_w = 230
        else:
            col.addLayout(text)
            col.addStretch(1)
            col.addWidget(self.seek)
            col.addLayout(ctl)
            self.resize(450, 138)
            self._text_w = 290
        lay.addLayout(col, 1)
        self.sync_pin()

    # ── look ─────────────────────────────────────────────────
    def set_cover(self, data: bytes | None):
        self.cover.set_image(data or None)
        self._bg_src = self.cover.src
        self._bg = None
        self.update()

    def opacity(self) -> float:
        if self._hover and self.win.cfg.get("mini_hover_opaque", True):
            return 1.0
        return max(0.3, min(1.0, int(self.win.cfg.get("mini_opacity", 85)) / 100.0))

    def _background(self) -> QPixmap:
        """The cover, blurred (scaled down to 10 px and back) and darkened; the ArtCore gradient without one."""
        if self._bg is not None and self._bg.size() == self.size():
            return self._bg
        pm = QPixmap(self.size())
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self._bg_src is not None:
            small = self._bg_src.scaled(10, 10, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            side = max(self.width(), self.height())
            big = small.scaled(side, side, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap((self.width() - side) // 2, (self.height() - side) // 2, big)
            p.fillRect(pm.rect(), QColor(10, 12, 18, 150))
        else:
            g = QLinearGradient(0, 0, self.width(), self.height())
            g.setColorAt(0, QColor(13, 110, 253, 120))
            g.setColorAt(1, QColor(111, 66, 193, 150))
            p.fillRect(pm.rect(), QColor(style.PANEL))
            p.fillRect(pm.rect(), g)
            p.fillRect(pm.rect(), QColor(10, 12, 18, 90))
        p.end()
        self._bg = pm
        return pm

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, self.RADIUS, self.RADIUS)
        p.setClipPath(path)
        p.setOpacity(self.opacity())
        p.drawPixmap(0, 0, self._background())
        p.setOpacity(1.0)
        p.setClipping(False)
        p.setPen(QPen(QColor(255, 255, 255, 46), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, self.RADIUS, self.RADIUS)
        p.end()

    def resizeEvent(self, e):
        self._bg = None
        super().resizeEvent(e)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    # ── state ────────────────────────────────────────────────
    def set_text(self, title: str, artist: str):
        elide(self.title, title, self._text_w)
        elide(self.artist, artist, self._text_w)

    def set_time(self, text: str):
        if time.monotonic() < self._vol_until:
            return
        self.time.setText(text)

    def show_volume(self, v: int, muted: bool):
        self._vol_until = time.monotonic() + 1.2
        self.time.setText(t("muted") if muted else f"{v}%")

    def set_mode_buttons(self, shuffle: bool, repeat: str):
        self.b_shuffle.setObjectName("on" if shuffle else "ctl")
        self.b_repeat.setObjectName("ctl" if repeat == "off" else "on")
        self.b_repeat.setIcon(style.icon({"off": "mdi6.repeat-off", "all": "mdi6.repeat",
                                          "one": "mdi6.repeat-once"}[repeat], "#ffffff"))
        for b in (self.b_shuffle, self.b_repeat):
            b.style().unpolish(b)
            b.style().polish(b)

    def toggle_pin(self):
        on = not self.win.cfg.get("mini_on_top", True)
        self.win.cfg["mini_on_top"] = on
        vis = self.isVisible()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        if vis:
            self.show()
        self.sync_pin()
        self.win.toast.show_text(t("on_top_on") if on else t("on_top_off"), 1000)

    def sync_pin(self):
        on = bool(self.win.cfg.get("mini_on_top", True))
        self.b_pin.setObjectName("on" if on else "ctl")
        self.b_pin.setToolTip(t("mini_pin") + (" ✓" if on else ""))
        self.b_pin.style().unpolish(self.b_pin)
        self.b_pin.style().polish(self.b_pin)

    # ── mouse / keys ─────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif e.button() == Qt.RightButton:
            self.win.mini_menu(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        self.win.toggle_mini()

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if d:
            step = int(self.win.cfg.get("volume_step", 5)) * (1 if d > 0 else -1)
            self.win.vol.setValue(self.win.vol.value() + step)
            self.show_volume(self.win.vol.value(), bool(self.win.cfg.get("muted")))

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Escape:
            self.win.toggle_mini()
        elif k == Qt.Key_Space:
            self.win.toggle_pause()
        elif k in (Qt.Key_Left, Qt.Key_Right):
            self.win.engine.seek_rel(int(self.win.cfg.get("seek_step", 5)) * (1 if k == Qt.Key_Right else -1))
        elif k in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Plus, Qt.Key_Minus):
            step = int(self.win.cfg.get("volume_step", 5)) * (1 if k in (Qt.Key_Up, Qt.Key_Plus) else -1)
            self.win.vol.setValue(self.win.vol.value() + step)
            self.show_volume(self.win.vol.value(), bool(self.win.cfg.get("muted")))
        elif k == Qt.Key_M:
            self.win.toggle_mute()
            self.show_volume(self.win.vol.value(), bool(self.win.cfg.get("muted")))
        elif k == Qt.Key_S:
            self.win.toggle_shuffle()
        elif k == Qt.Key_R:
            self.win.cycle_repeat()
        else:
            super().keyPressEvent(e)

    def closeEvent(self, e):
        e.ignore()
        self.win.toggle_mini()


class LevelsWindow(QDialog):
    """The room with the channel levels (V): to see that every speaker of the 5.1 gets sound."""

    def __init__(self, win: "MainWindow"):
        super().__init__(win, Qt.Window)
        self.win = win
        self.setWindowTitle(t("levels") + " — " + APP_TITLE)
        self.setWindowIcon(style.app_icon())
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(8)
        self.head = QLabel()
        self.head.setStyleSheet("font-size: 11pt; font-weight: 700;")
        lay.addWidget(self.head)
        labels = {"you": t("spk_you")}
        self.room = RoomMeters(win.levels, labels)
        lay.addWidget(self.room, 1)
        hint = QLabel(t("levels_hint"))
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.resize(560, 470)

    def set_head(self, text: str):
        self.head.setText(t("levels") + (" · " + text if text else ""))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_V:
            self.close()
        else:
            super().keyPressEvent(e)

    def showEvent(self, e):
        winint.dark_title_bar(int(self.winId()))
        super().showEvent(e)
        self.win._meters_need()

    def closeEvent(self, e):
        super().closeEvent(e)
        self.win._meters_need()


class MainWindow(QMainWindow):
    SAVE_EVERY_MS = 15000
    UPDATE_EVERY = 24 * 3600

    def __init__(self, mpv_module, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self.mpvmod = mpv_module
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(style.app_icon())
        self.setAcceptDrops(True)
        self.resize(1180, 720)
        self.setMinimumSize(760, 480)
        self.pls: list[Playlist] = [self._new_pl(t("playlist"))]   # the tabs
        self.pl = self.pls[0]                                          # the one shown
        self.favs = Favorites()
        self.history = History()
        self.engine = Engine(mpv_module, cfg, self.pl)
        self.engine.queue_changed.connect(self._on_queue)
        self.smtc = None
        self._smtc_sent = (0.0, 0.0)                    # (time, position) of the last timeline update
        self._setup_smtc()
        self.engine.track_changed.connect(self._on_track)
        self.engine.position.connect(self._on_pos)
        self.engine.paused_changed.connect(self._on_paused)
        self.engine.format_changed.connect(self._on_format)
        self.engine.finished.connect(self._on_finished)
        self.engine.error.connect(lambda s: self.toast.show_text(t("play_error", s), 3500))
        self.engine.stream_title.connect(self._on_icy)
        self.bridge = Bridge()
        self.bridge.tagged.connect(self._on_tagged)
        self.bridge.update.connect(self._on_update_result)
        self.tags = TagReader(self.bridge)
        self.waves = Waveforms(mpv_module)
        self.waves.ready.connect(self._on_wave)
        self._wave_key = ""
        self.items: dict[int, QTreeWidgetItem] = {}
        self.cur_tags = None
        self.fmt_info: dict = {}
        self.update_info: dict | None = None
        self.mini: MiniWindow | None = None
        self.levels = LevelState()               # the channel meters (under the cover and the room window)
        self.levels_win: LevelsWindow | None = None
        self.meter_timer = QTimer(self)
        self.meter_timer.setInterval(33)
        self.meter_timer.timeout.connect(self._meter_tick)
        self._hotkeys: list[int] = []
        self.thumbbar = winint.ThumbBar()
        self._thumb_icons: dict[str, int] = {}
        self._last_pos = (0.0, 0.0)
        self._dirty = False
        self._searching = False                # the list is filtered right now
        self._search_anchor: int | None = None  # uid to come back to when the search is cleared
        self._quitting = False
        self.tray: QSystemTrayIcon | None = None
        self.sleep_until = 0.0                 # monotonic time of the sleep timer (0 = off)
        self.sleep_timer = QTimer(self)
        self.sleep_timer.setInterval(1000)
        self.sleep_timer.timeout.connect(self._sleep_tick)

        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.split = QSplitter(Qt.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.split.addWidget(self._build_now())
        self.split.addWidget(self._build_list())
        self.split.setStretchFactor(0, 0)
        self.split.setStretchFactor(1, 1)
        v.addWidget(self.split, 1)
        v.addWidget(self._build_transport())
        self.toast = Toast(central)
        self._shortcuts()
        self.engine.set_volume(int(cfg.get("volume", 80)), bool(cfg.get("muted")))
        self._sync_mode_buttons()
        self._sync_mute_icon()
        self._show_track(None)
        self._apply_view_options()
        self._setup_tray()

        self.save_timer = QTimer(self)
        self.save_timer.setInterval(self.SAVE_EVERY_MS)
        self.save_timer.timeout.connect(self.save_session)
        self.save_timer.start()
        self.dirty_timer = QTimer(self)
        self.dirty_timer.setSingleShot(True)
        self.dirty_timer.setInterval(1200)
        self.dirty_timer.timeout.connect(self.save_session)
        if cfg.get("on_top"):
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

    # ── building ──────────────────────────────────────────────
    def _build_now(self) -> QWidget:
        w = QWidget()
        w.setObjectName("nowPanel")
        w.setMinimumWidth(300)
        w.setMaximumWidth(520)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 24, 18, 18)
        lay.setSpacing(6)
        self.cover = CoverView()
        self.cover.setMinimumSize(240, 240)
        self.cover.clicked.connect(self.jump_to_current)
        lay.addWidget(self.cover, 0)
        lay.addSpacing(10)
        self.t_title = QLabel()
        self.t_title.setObjectName("title")
        self.t_title.setWordWrap(True)
        self.t_artist = QLabel()
        self.t_artist.setObjectName("artist")
        self.t_artist.setWordWrap(True)
        self.t_album = QLabel()
        self.t_album.setObjectName("album")
        self.t_album.setWordWrap(True)
        for lab in (self.t_title, self.t_artist, self.t_album):
            lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lay.addWidget(lab)
        lay.addSpacing(6)
        row = QHBoxLayout()
        self.t_format = QLabel()
        self.t_format.setObjectName("format")
        self.t_format.setToolTip(t("format_tip"))
        self.t_format.hide()
        row.addWidget(self.t_format)
        row.addStretch(1)
        self.b_lyrics = ctl_button("fa6s.align-left", t("lyrics") + " (L)", 15, self.toggle_lyrics)
        self.b_lyrics.hide()
        row.addWidget(self.b_lyrics)
        lay.addLayout(row)
        self.meters = ChannelMeters(self.levels)
        self.meters.setToolTip(t("meters_tip") + " (V)")
        self.meters.clicked.connect(self.toggle_levels)
        self.meters.hide()
        lay.addWidget(self.meters)
        self.t_next = QLabel()
        self.t_next.setObjectName("hint")
        self.t_next.setWordWrap(True)
        lay.addWidget(self.t_next)
        self.lyrics = LyricsView()
        self.lyrics.seek.connect(self.engine.seek)
        self.lyrics.hide()
        lay.addWidget(self.lyrics, 1)
        lay.addStretch(1)
        self.now_lay = lay
        self._lyr = None
        return w

    # ── lyrics ────────────────────────────────────────────────
    def _load_lyrics(self, tr: Track | None):
        lyr = lyrics_mod.load(tr) if self.cfg.get("lyrics", True) else None
        self._lyr = lyr
        self.lyrics.set_lyrics(lyr)
        self.b_lyrics.setVisible(lyr is not None)
        if lyr is not None:
            self.b_lyrics.setToolTip(t("lyrics") + (" (LRC)" if lyr.synced else "") + " (L)\n" +
                                     (os.path.basename(lyr.source) if lyr.source != "tags" else t("lyrics_tags")))
        self._apply_lyrics_visible()

    def _apply_lyrics_visible(self):
        on = self._lyr is not None and bool(self.cfg.get("lyrics_show", True))
        self.lyrics.setVisible(on)
        self.b_lyrics.setObjectName("on" if on else "ctl")
        self.b_lyrics.style().unpolish(self.b_lyrics)
        self.b_lyrics.style().polish(self.b_lyrics)
        # the spacer at the end takes the room only when there are no lyrics
        self.now_lay.setStretch(self.now_lay.count() - 1, 0 if on else 1)
        self.cover.setMaximumHeight(220 if on else 16777215)
        if on:
            self.lyrics.set_pos(self._last_pos[0])

    def toggle_lyrics(self):
        self.cfg["lyrics_show"] = not self.cfg.get("lyrics_show", True)
        self._apply_lyrics_visible()

    # ── channel levels ────────────────────────────────────────
    def _meters_need(self):
        """Run the 30 Hz meter timer only while a meter is on screen."""
        playing = self.engine.cur is not None and not self.engine.stopped
        show_bars = bool(self.cfg.get("meters", True)) and playing
        self.meters.setVisible(show_bars)
        room = self.levels_win is not None and self.levels_win.isVisible()
        need = (show_bars and self.isVisible()) or room
        if need and not self.meter_timer.isActive():
            self.meter_timer.start()
        elif not need and self.meter_timer.isActive():
            self.meter_timer.stop()

    def _meter_tick(self):
        if self.levels.feed(self.engine.levels(), time.monotonic()) or not self.levels.ch:
            if self.meters.isVisible():
                self.meters.update()
            if self.levels_win is not None and self.levels_win.isVisible():
                self.levels_win.room.update()

    def toggle_levels(self):
        if self.levels_win is None:
            self.levels_win = LevelsWindow(self)
        if self.levels_win.isVisible():
            self.levels_win.close()
            return
        self.levels_win.set_head(self.t_format.text() if self.t_format.isVisible() else "")
        self.levels_win.show()
        self.levels_win.raise_()
        self.levels_win.activateWindow()

    def _build_list(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 16, 18, 10)
        lay.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(4)
        self.pl_title = QLabel(t("playlist"))
        self.pl_title.setStyleSheet("font-size: 12pt; font-weight: 700;")
        top.addWidget(self.pl_title)
        self.pl_count = QLabel()
        self.pl_count.setObjectName("hint")
        top.addWidget(self.pl_count)
        top.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("search"))
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(220)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(150)
        self.search_timer.timeout.connect(lambda: self._filter(self.search.text()))
        self.search.textChanged.connect(self._search_changed)
        self.search.returnPressed.connect(self._play_first_visible)
        top.addWidget(self.search)
        top.addSpacing(4)
        top.addWidget(ctl_button("fa6s.file-circle-plus", t("add_files") + " (Ctrl+O)", 17, self.add_files_dialog))
        top.addWidget(ctl_button("fa6s.folder-plus", t("add_folder") + " (Ctrl+Shift+O)", 17, self.add_folder_dialog))
        top.addWidget(ctl_button("fa6s.tower-broadcast", t("add_url") + " (Ctrl+U)", 17, self.add_url_dialog))
        top.addWidget(ctl_button("fa6s.folder-open", t("load_pl") + " (Ctrl+L)", 17, self.load_playlist_dialog))
        top.addWidget(ctl_button("fa6s.floppy-disk", t("save_pl") + " (Ctrl+S)", 17, self.save_playlist_dialog))
        top.addWidget(ctl_button("fa6s.trash-can", t("clear_pl"), 17, self.clear_playlist))
        lay.addLayout(top)
        tabs = QHBoxLayout()
        tabs.setSpacing(2)
        self.tabbar = QTabBar()
        self.tabbar.setObjectName("plTabs")
        self.tabbar.setMovable(True)
        self.tabbar.setTabsClosable(True)
        self.tabbar.setExpanding(False)
        self.tabbar.setDocumentMode(True)
        self.tabbar.setElideMode(Qt.ElideRight)
        self.tabbar.setUsesScrollButtons(True)
        self.tabbar.addTab(self.pl.name)
        self.tabbar.currentChanged.connect(self._tab_changed)
        self.tabbar.tabCloseRequested.connect(self.close_tab)
        self.tabbar.tabMoved.connect(self._tab_moved)
        self.tabbar.tabBarDoubleClicked.connect(self.rename_tab)
        self.tabbar.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabbar.customContextMenuRequested.connect(self._tab_menu)
        tabs.addWidget(self.tabbar, 1)
        tabs.addWidget(ctl_button("fa6s.plus", t("new_tab") + " (Ctrl+N)", 14, lambda: self.new_tab()))
        lay.addLayout(tabs)
        self.view = PlaylistView()
        self.view.setHeaderLabels(["#", t("col_title"), t("col_artist"), t("col_album"), t("col_len"), ""])
        self.view.headerItem().setIcon(COL_FAV, style.icon("fa6s.star", style.MUTED))
        self.view.headerItem().setToolTip(COL_FAV, t("fav") + " (Ctrl+D)")
        hdr = self.view.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(COL_N, QHeaderView.Fixed)
        hdr.setSectionResizeMode(COL_TITLE, QHeaderView.Stretch)
        hdr.setSectionResizeMode(COL_ARTIST, QHeaderView.Interactive)
        hdr.setSectionResizeMode(COL_ALBUM, QHeaderView.Interactive)
        hdr.setSectionResizeMode(COL_LEN, QHeaderView.Fixed)
        hdr.setSectionResizeMode(COL_FAV, QHeaderView.Fixed)
        hdr.setSectionsClickable(True)
        hdr.sectionClicked.connect(self._sort_by_column)
        self.view.setColumnWidth(COL_N, 46)
        self.view.setColumnWidth(COL_ARTIST, 170)
        self.view.setColumnWidth(COL_ALBUM, 170)
        self.view.setColumnWidth(COL_LEN, 64)
        self.view.setColumnWidth(COL_FAV, 30)
        self.view.itemClicked.connect(self._item_clicked)
        cols = self.cfg.get("columns") or []
        if len(cols) == 2:
            self.view.setColumnWidth(COL_ARTIST, int(cols[0]))
            self.view.setColumnWidth(COL_ALBUM, int(cols[1]))
        self.view.itemActivated.connect(lambda it, _c: self._activate(it))
        hdr.setContextMenuPolicy(Qt.CustomContextMenu)
        hdr.customContextMenuRequested.connect(self._header_menu)
        self.view.files_dropped.connect(self._dropped_on_list)
        self.view.reordered.connect(self._reordered)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._list_menu)
        lay.addWidget(self.view, 1)
        self.empty = QLabel(t("empty"), self.view.viewport())
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setObjectName("hint")
        self.empty.setStyleSheet(f"color: {style.MUTED}; font-size: 11pt;")
        self.empty.setAttribute(Qt.WA_TransparentForMouseEvents)
        return w

    def _build_transport(self) -> QWidget:
        w = QWidget()
        w.setObjectName("transport")
        w.setAttribute(Qt.WA_StyledBackground)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 8, 20, 10)
        lay.setSpacing(4)
        seek = QHBoxLayout()
        self.l_pos = QLabel("0:00")
        self.l_pos.setObjectName("hint")
        self.l_pos.setMinimumWidth(48)
        self.l_dur = ClickLabel("0:00")
        self.l_dur.setObjectName("hint")
        self.l_dur.setCursor(Qt.PointingHandCursor)
        self.l_dur.setToolTip(t("time_toggle"))
        self.l_dur.clicked.connect(self.toggle_time_remaining)
        self.l_dur.setMinimumWidth(48)
        self.l_dur.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.seekbar = WaveSeekBar()
        self.seekbar.set_wave_enabled(bool(self.cfg.get("waveform", True)))
        self.seekbar.seek.connect(self.engine.seek)
        seek.addWidget(self.l_pos)
        seek.addWidget(self.seekbar, 1)
        seek.addWidget(self.l_dur)
        lay.addLayout(seek)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.b_shuffle = ctl_button("mdi6.shuffle-variant", t("shuffle") + " (S)", 20, self.toggle_shuffle)
        self.b_prev = ctl_button("fa6s.backward-step", t("prev") + " (Ctrl+←)", 20, self.prev)
        self.b_play = ctl_button("fa6s.play", t("play") + " (Space)", 22, self.toggle_pause, "play")
        self.b_play.setFixedSize(46, 46)
        self.b_next = ctl_button("fa6s.forward-step", t("next") + " (Ctrl+→)", 20, self.next)
        self.b_repeat = ctl_button("mdi6.repeat", t("repeat") + " (R)", 20, self.cycle_repeat)
        self.b_stop = ctl_button("fa6s.stop", t("stop"), 18, self.stop)
        left = QHBoxLayout()
        left.addWidget(self.b_stop)
        left.addStretch(1)
        row.addLayout(left, 1)
        for b in (self.b_shuffle, self.b_prev, self.b_play, self.b_next, self.b_repeat):
            row.addWidget(b)
        right = QHBoxLayout()
        right.setSpacing(4)
        right.addStretch(1)
        self.b_mute = ctl_button("fa6s.volume-high", t("mute") + " (M)", 18, self.toggle_mute)
        right.addWidget(self.b_mute)
        self.vol = QSlider(Qt.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setFixedWidth(120)
        self.vol.setFocusPolicy(Qt.NoFocus)
        self.vol.setValue(int(self.cfg.get("volume", 80)))
        self.vol.valueChanged.connect(self.set_volume)
        right.addWidget(self.vol)
        self.l_vol = QLabel()
        self.l_vol.setObjectName("hint")
        self.l_vol.setMinimumWidth(34)
        right.addWidget(self.l_vol)
        right.addSpacing(6)
        right.addWidget(ctl_button("fa6s.sliders", t("equalizer") + " (E)", 18, self.equalizer_dialog))
        right.addWidget(ctl_button("mdi6.surround-sound", t("sound") + " (Ctrl+P)", 20, self.sound_dialog))
        right.addWidget(ctl_button("fa6s.clone", t("mini") + " (Ctrl+M)", 17, self.toggle_mini))
        self.b_menu = ctl_button("fa6s.bars", t("menu"), 18, self._main_menu)
        right.addWidget(self.b_menu)
        row.addLayout(right, 1)
        lay.addLayout(row)
        return w

    def _shortcuts(self):
        def sc(keys, fn):
            for k in (keys if isinstance(keys, (list, tuple)) else [keys]):
                s = QShortcut(QKeySequence(k), self)
                s.setContext(Qt.WindowShortcut)
                s.activated.connect(fn)
        sc("Space", self.toggle_pause)
        step = lambda k: int(self.cfg.get(k, 5))           # noqa: E731
        not_typing = lambda fn: (lambda: None if self.search.hasFocus() else fn())   # noqa: E731
        sc("Left", lambda: self.engine.seek_rel(-step("seek_step")))
        sc("Right", lambda: self.engine.seek_rel(step("seek_step")))
        sc("Shift+Left", lambda: self.engine.seek_rel(-step("seek_step_big")))
        sc("Shift+Right", lambda: self.engine.seek_rel(step("seek_step_big")))
        sc("Ctrl+Left", self.prev)
        sc("Ctrl+Right", self.next)
        sc(["Ctrl+Up", "+", "="], lambda: self.vol.setValue(self.vol.value() + step("volume_step")))
        sc(["Ctrl+Down", "-"], lambda: self.vol.setValue(self.vol.value() - step("volume_step")))
        sc("M", self.toggle_mute)
        sc("S", self.toggle_shuffle)
        sc("R", self.cycle_repeat)
        sc("E", self.equalizer_dialog)
        sc("Ctrl+P", self.sound_dialog)
        sc("Ctrl+T", self.speaker_test)
        sc("Ctrl+M", self.toggle_mini)
        sc("T", self.toggle_on_top)
        sc("Ctrl+F", lambda: (self.search.setFocus(), self.search.selectAll()))
        sc("Ctrl+J", self.jump_to_current)
        sc("Ctrl+Shift+E", self.toggle_stop_after)
        sc("Ctrl+N", lambda: self.new_tab())
        sc("Ctrl+W", lambda: self.close_tab(self.tabbar.currentIndex()))
        sc("Ctrl+Tab", lambda: self.tabbar.setCurrentIndex((self.tabbar.currentIndex() + 1) % self.tabbar.count()))
        sc("Ctrl+Shift+Tab", lambda: self.tabbar.setCurrentIndex((self.tabbar.currentIndex() - 1) % self.tabbar.count()))
        sc("Ctrl+D", self.toggle_fav_selected)
        sc("F2", not_typing(self.edit_tags_selected))
        sc("L", self.toggle_lyrics)
        sc("V", self.toggle_levels)
        sc("Ctrl+Q", lambda: self.queue_selected(front=True))
        sc("Ctrl+Shift+Q", lambda: self.queue_selected(front=False))
        sc("Ctrl+H", lambda: self.open_library_tab("history"))
        sc("Ctrl+B", lambda: self.open_library_tab("favorites"))
        sc("Delete", not_typing(self.remove_selected))
        sc("Ctrl+O", self.add_files_dialog)
        sc("Ctrl+Shift+O", self.add_folder_dialog)
        sc("Ctrl+U", self.add_url_dialog)
        sc("Ctrl+L", self.load_playlist_dialog)
        sc("Ctrl+S", self.save_playlist_dialog)
        sc("Ctrl+,", self.settings_dialog)
        sc("F1", self.keys_dialog)
        sc("Escape", lambda: self.search.clear() if self.search.text() else None)
        # media keys while focused (the global ones come as WM_HOTKEY)
        sc(QKeySequence(Qt.Key_MediaTogglePlayPause), self.toggle_pause)
        sc(QKeySequence(Qt.Key_MediaPlay), self.toggle_pause)
        sc(QKeySequence(Qt.Key_MediaPause), lambda: self.engine.set_paused(True))
        sc(QKeySequence(Qt.Key_MediaNext), self.next)
        sc(QKeySequence(Qt.Key_MediaPrevious), self.prev)
        sc(QKeySequence(Qt.Key_MediaStop), self.stop)

    # ── tabs ──────────────────────────────────────────────────
    def _new_pl(self, name: str, kind: str = "") -> Playlist:
        p = Playlist(name, kind)
        p.repeat = self.cfg.get("repeat", "off")
        p.shuffle = bool(self.cfg.get("shuffle"))
        return p

    def _set_tabs(self, pls: list[Playlist], view: int = 0):
        """Replace all tabs (session restore)."""
        self.pls = pls
        self.tabbar.blockSignals(True)
        while self.tabbar.count():
            self.tabbar.removeTab(0)
        for p in pls:
            self.tabbar.addTab(p.name)
        self.tabbar.setCurrentIndex(view)
        self.tabbar.blockSignals(False)
        self.pl = pls[view]
        if self.engine.pl not in pls:
            self.engine.pl = self.pl
        self._rebuild_list()
        self._restore_scroll()
        self._tab_icons()

    def _set_playing_pl(self, p: Playlist, first: Track | None = None):
        """`p` becomes the playlist the player goes through (repeat / shuffle follow the settings)."""
        p.repeat = self.cfg.get("repeat", "off")
        p.shuffle = bool(self.cfg.get("shuffle"))
        if p.shuffle:
            p.reshuffle(first)
        self.engine.pl = p
        self.engine.ctx = first
        self._tab_icons()

    def _tab_icons(self):
        for i, p in enumerate(self.pls):
            if p is self.engine.pl and self.engine.cur is not None:
                self.tabbar.setTabIcon(i, style.icon("fa6s.volume-high", ACCENT_TEXT))
            elif p.kind == "favorites":
                self.tabbar.setTabIcon(i, style.icon("fa6s.star", STAR))
            elif p.kind == "history":
                self.tabbar.setTabIcon(i, style.icon("fa6s.clock-rotate-left", style.MUTED))
            else:
                self.tabbar.setTabIcon(i, style.icon("fa6s.music", "#00000000"))
            self.tabbar.setTabToolTip(i, f"{p.name} — {t('pl_count', len(p.tracks), fmt_time(sum(x.duration() for x in p.tracks)))}")

    def _tab_changed(self, i: int):
        if not 0 <= i < len(self.pls) or self.pls[i] is self.pl:
            return
        self.pl.scroll = self.view.verticalScrollBar().value()
        self.pl = self.pls[i]
        self._searching = False
        self._rebuild_list()
        self._restore_scroll()
        self._dirty = True

    def _restore_scroll(self):
        sc = self.pl.scroll
        QTimer.singleShot(0, lambda: self.view.verticalScrollBar().setValue(sc))

    def _tab_moved(self, a: int, b: int):
        self.pls.insert(b, self.pls.pop(a))
        self._dirty = True
        self.dirty_timer.start()

    def new_tab(self, name: str = "", kind: str = "", switch: bool = True) -> Playlist:
        if not name:
            n = len(self.pls) + 1
            names = {p.name for p in self.pls}
            while t("playlist_n", n) in names:
                n += 1
            name = t("playlist_n", n)
        p = self._new_pl(name, kind)
        self.pls.append(p)
        self.tabbar.addTab(name)
        self._tab_icons()
        if switch:
            self.tabbar.setCurrentIndex(len(self.pls) - 1)
        self.dirty_timer.start()
        return p

    def rename_tab(self, i: int):
        if not 0 <= i < len(self.pls):
            return
        p = self.pls[i]
        name, ok = QInputDialog.getText(self, t("rename_tab"), t("tab_name"), QLineEdit.Normal, p.name)
        name = (name or "").strip()
        if ok and name:
            p.name = name
            self.tabbar.setTabText(i, name)
            if p is self.pl:
                self.pl_title.setText(name)
            self._tab_icons()
            self.dirty_timer.start()

    def close_tab(self, i: int):
        if not 0 <= i < len(self.pls):
            return
        p = self.pls[i]
        if p.tracks and not p.kind and self.cfg.get("confirm_clear", True):
            r = QMessageBox.question(self, APP_TITLE, t("close_tab_q", p.name, len(p.tracks)),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                return
        if self.engine.queue:
            self.engine.dequeue([tr for tr in p.tracks if self.engine.queue_pos(tr)])
        if len(self.pls) == 1:                         # the last tab is cleared, not closed
            self.clear_playlist(confirm=False)
            return
        if p is self.engine.pl:
            self.engine.stop()
            self.engine.cur = None
            self.engine.stop_after = None
            self._show_track(None)
        self.pls.pop(i)
        self.tabbar.removeTab(i)                       # currentChanged switches the view
        if self.engine.pl not in self.pls:
            self.engine.pl = self.pl
        self._tab_icons()
        self._dirty = True
        self.dirty_timer.start()

    def _tab_menu(self, pos):
        i = self.tabbar.tabAt(pos)
        m = QMenu(self)
        m.addAction(style.icon("fa6s.plus"), t("new_tab") + "\tCtrl+N", lambda: self.new_tab())
        if i >= 0:
            m.addAction(style.icon("fa6s.pen"), t("rename_tab"), lambda: self.rename_tab(i))
            m.addAction(style.icon("fa6s.floppy-disk"), t("save_pl"), lambda: (self.tabbar.setCurrentIndex(i),
                                                                                self.save_playlist_dialog()))
            m.addSeparator()
            m.addAction(style.icon("fa6s.xmark"), t("close_tab") + "\tCtrl+W", lambda: self.close_tab(i))
        m.exec(self.tabbar.mapToGlobal(pos))

    # ── favourites, history, queue ────────────────────────────
    def _fill_library(self, p: Playlist):
        tracks = self.favs.tracks() if p.kind == "favorites" else self.history.tracks()
        p.clear()
        p.add(tracks)
        self.tags.add([x for x in tracks if not x.tagged])

    def open_library_tab(self, kind: str):
        """★ Favourites / Recently played as a tab, filled afresh (left alone while it is playing)."""
        i = next((k for k, p in enumerate(self.pls) if p.kind == kind), -1)
        if i < 0:
            p = self.new_tab(t("favorites") if kind == "favorites" else t("history"), kind, switch=False)
            i = len(self.pls) - 1
        p = self.pls[i]
        if p is not self.engine.pl or self.engine.cur is None:
            self._fill_library(p)
        if self.tabbar.currentIndex() == i:
            self._rebuild_list()
        else:
            self.tabbar.setCurrentIndex(i)
        self._tab_icons()
        self.view.scrollToTop()

    def _selected_tracks(self) -> list[Track]:
        out = []
        for i in range(self.view.topLevelItemCount()):        # in list order, not click order
            it = self.view.topLevelItem(i)
            if it.isSelected():
                tr = self.pl.by_uid(it.data(0, UID))
                if tr is not None:
                    out.append(tr)
        return out

    def toggle_fav_selected(self):
        sel = self._selected_tracks() or ([self.engine.cur] if self.engine.cur is not None else [])
        if not sel:
            return
        on = not all(self.favs.has(x) for x in sel)
        for x in sel:
            self.favs.set(x, on)
        self._refresh_all()
        self.toast.show_text(t("fav_on") if on else t("fav_off"), 1100)

    def _item_clicked(self, it: QTreeWidgetItem, col: int):
        if col != COL_FAV:
            return
        tr = self.pl.by_uid(it.data(0, UID))
        if tr is not None:
            self.favs.toggle(tr)
            self._fill_item(it, tr)

    def queue_selected(self, front: bool = True):
        sel = self._selected_tracks()
        if not sel:
            return
        self.engine.enqueue(sel, front=front)
        self.toast.show_text(t("queued_next", len(sel)) if front else t("queued_end", len(sel)), 1300)

    def _on_queue(self):
        shown = getattr(self, "_queued_shown", set())
        now = {x.uid for x in self.engine.queue}
        for uid in shown | now:
            self._refresh_item(uid)
        self._queued_shown = now
        self._update_next_label()
        if self.engine.cur is not None:
            self.waves.prefetch(self.engine.next_track(self.engine.cur, auto=True))

    def _play_track(self, tr: Track):
        """Play a track of any tab (from the queue menu)."""
        p = next((p for p in self.pls if p.by_uid(tr.uid) is tr), None)
        if p is not None and p is not self.engine.pl:
            self._set_playing_pl(p, tr)
        self.engine.play(tr)

    def edit_tags_selected(self):
        from .dialogs import TagEditorDialog
        sel = [x for x in self._selected_tracks() if not x.is_stream and not x.is_cue]
        if not sel:
            if any(x.is_cue or x.is_stream for x in self._selected_tracks()):
                self.toast.show_text(t("tags_not_here"), 2200)
            return
        d = TagEditorDialog(sel, self)
        if d.exec():
            for x in d.changed:
                self._refresh_item(x.uid)
                if self.engine.cur is x:
                    self._tags_path = ""
                    self._show_track(x)
            self._list_changed()
            if d.errors:
                QMessageBox.warning(self, APP_TITLE, t("tags_failed", "\n".join(d.errors[:8])))
        d.deleteLater()

    def _refresh_all(self):
        for uid, it in self.items.items():
            tr = self.pl.by_uid(uid)
            if tr is not None:
                self._fill_item(it, tr)

    # ── playlist view ─────────────────────────────────────────
    def _make_item(self, tr: Track) -> QTreeWidgetItem:
        it = QTreeWidgetItem()
        it.setData(0, UID, tr.uid)
        it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)
        it.setTextAlignment(COL_N, Qt.AlignRight | Qt.AlignVCenter)
        it.setTextAlignment(COL_LEN, Qt.AlignRight | Qt.AlignVCenter)
        self._fill_item(it, tr)
        return it

    def _fill_item(self, it: QTreeWidgetItem, tr: Track):
        qpos = self.engine.queue_pos(tr)
        it.setText(COL_N, str(qpos) if qpos else (tr.number or ""))
        it.setText(COL_TITLE, tr.display_title())
        it.setText(COL_ARTIST, tr.artist or tr.albumartist)
        it.setText(COL_ALBUM, tr.album + (f" ({tr.year})" if tr.year and tr.album else "") if not tr.is_stream
                   else t("radio"))
        d = tr.duration()
        it.setText(COL_LEN, t("live") if tr.is_stream else fmt_time(d) if d else "")
        it.setToolTip(COL_TITLE, tr.path + (f"\n{t('cue_track')} {fmt_time(tr.start)}" if tr.is_cue else ""))
        playing = self.engine.cur is not None and tr.uid == self.engine.cur.uid
        f = QFont(self.view.font())
        f.setBold(playing)
        for c in range(NCOLS):
            it.setFont(c, f)
            it.setForeground(c, QColor(ACCENT_TEXT) if playing or (c == COL_N and qpos) else
                             QColor(style.TEXT if c != COL_N else style.MUTED))
        if playing and not self.engine.stopped:
            icon = style.icon("fa6s.volume-high" if not self.engine.paused else "fa6s.pause", ACCENT_TEXT)
        elif qpos:
            icon = style.icon("fa6s.angles-right", ACCENT_TEXT)
        else:
            icon = style.icon("fa6s.music", "#00000000")
        it.setIcon(COL_N, icon)
        if qpos:
            it.setToolTip(COL_N, t("queued_n", qpos))
        fav = self.favs.has(tr)
        it.setIcon(COL_FAV, style.icon("fa6s.star", STAR) if fav else style.icon("mdi6.star-outline", "#3a4152"))
        it.setToolTip(COL_FAV, t("unfav") if fav else t("fav"))

    def _rebuild_list(self):
        self.view.setUpdatesEnabled(False)
        self.view.clear()
        self.items = {}
        items = []
        for tr in self.pl.tracks:
            it = self._make_item(tr)
            self.items[tr.uid] = it
            items.append(it)
        self.view.addTopLevelItems(items)
        self.view.setUpdatesEnabled(True)
        if self.search.text().strip():
            self._filter(self.search.text())
        self._list_changed()

    def _list_changed(self):
        n = len(self.pl.tracks)
        total = sum(tr.duration() for tr in self.pl.tracks)
        self.pl_count.setText(t("pl_count", n, fmt_time(total)) if n else "")
        self.pl_title.setText(self.pl.name)
        self.empty.setVisible(n == 0)
        self.empty.resize(self.view.viewport().size())
        self._fit_number_column()
        self._update_next_label()
        self._dirty = True
        self.dirty_timer.start()

    def _refresh_item(self, uid: int):
        it = self.items.get(uid)
        tr = self.pl.by_uid(uid)
        if it is not None and tr is not None:
            self._fill_item(it, tr)

    def _on_tagged(self, uid: int):
        self._refresh_item(uid)
        cur = self.engine.cur
        if cur is not None and cur.uid == uid:
            self._show_track(cur)
        if self.tags.q.empty():
            self._list_changed()

    def _search_changed(self, text: str):
        if not text.strip():                       # cleared: at once, no waiting
            self.search_timer.stop()
            self._filter(text)
        else:
            self.search_timer.start()

    def _filter(self, text: str):
        words = text.lower().split()
        if not words:
            if not self._searching:
                return
            self._searching = False
            self.view.setUpdatesEnabled(False)
            for it in self.items.values():
                it.setHidden(False)
            self.view.setUpdatesEnabled(True)
            self._after_search()
            return
        if not self._searching:
            self._searching = True
            self._search_anchor = None
        in_path = bool(self.cfg.get("search_path", True))
        self.view.setUpdatesEnabled(False)
        for uid, it in self.items.items():
            tr = self.pl.by_uid(uid)
            if tr is None:
                it.setHidden(True)
                continue
            where = tr.path if in_path else os.path.basename(tr.path)
            hay = " ".join((tr.display_title(), tr.artist, tr.album, tr.albumartist, tr.year, tr.genre,
                            where)).lower()
            it.setHidden(not all(w in hay for w in words))
        self.view.setUpdatesEnabled(True)
        cur = self.view.currentItem()
        if cur is not None and not cur.isHidden():
            self.view.scrollToItem(cur)
        else:
            self.view.scrollToTop()

    def _after_search(self):
        """The search was cleared: show the track picked or played from the results, else the playing one —
        not the top of the list."""
        uid = self._search_anchor
        if uid is None:
            cur = self.view.currentItem()
            if cur is not None and cur.isSelected():
                uid = cur.data(0, UID)
        if uid is None and self.engine.cur is not None:
            uid = self.engine.cur.uid
        self._search_anchor = None
        it = self.items.get(uid) if uid is not None else None
        if it is None:
            return
        self.view.setCurrentItem(it)
        # the rows have just come back: scroll once the view has laid them out again
        QTimer.singleShot(0, lambda: self.view.scrollToItem(it, PlaylistView.PositionAtCenter)
                          if self.items.get(uid) is it else None)

    def _activate(self, it: QTreeWidgetItem):
        uid = it.data(0, UID)
        if self._searching:
            self._search_anchor = uid
        self.play_uid(uid)
        if self._searching and self.cfg.get("search_clear_on_play"):
            self.search.clear()

    def _play_first_visible(self):
        cur = self.view.currentItem()
        if cur is not None and not cur.isHidden() and cur.isSelected():
            self._activate(cur)
            return
        for i in range(self.view.topLevelItemCount()):
            it = self.view.topLevelItem(i)
            if not it.isHidden():
                self.view.setCurrentItem(it)
                self._activate(it)
                return

    def _fit_number_column(self):
        """Wide enough for the playing icon and the longest track number (it showed «…» from 10 on)."""
        longest = max((len(tr.number or "") for tr in self.pl.tracks), default=1)
        fm = self.view.fontMetrics()
        w = 16 + 10 + fm.horizontalAdvance("8" * max(2, min(longest, 7))) + 14
        if self.view.columnWidth(COL_N) != w:
            self.view.setColumnWidth(COL_N, w)

    def _apply_view_options(self):
        pad = ROW_PAD.get(self.cfg.get("row_size", "normal"), 5)
        self.view.setStyleSheet(f"QTreeWidget#playlist::item {{ padding: {pad}px 4px; border: none; }}")
        hidden = set(self.cfg.get("hidden_cols") or [])
        for key, col in COL_KEYS.items():
            self.view.setColumnHidden(col, key in hidden)
        if self._searching:
            self._filter(self.search.text())

    def _header_menu(self, pos):
        m = QMenu(self)
        hidden = set(self.cfg.get("hidden_cols") or [])
        names = {"n": "#", "artist": t("col_artist"), "album": t("col_album"), "len": t("col_len"), "fav": "★"}
        for key, name in names.items():
            a = m.addAction(name)
            a.setCheckable(True)
            a.setChecked(key not in hidden)
            a.triggered.connect(lambda on, k=key: self._set_column(k, on))
        m.exec(self.view.header().mapToGlobal(pos))

    def _set_column(self, key: str, on: bool):
        hidden = [c for c in (self.cfg.get("hidden_cols") or []) if c != key]
        if not on:
            hidden.append(key)
        self.cfg["hidden_cols"] = hidden
        self._apply_view_options()
        config.save(self.cfg)

    def _reordered(self):
        uids = [self.view.topLevelItem(i).data(0, UID) for i in range(self.view.topLevelItemCount())]
        self.items = {self.view.topLevelItem(i).data(0, UID): self.view.topLevelItem(i)
                      for i in range(self.view.topLevelItemCount())}
        self.pl.reorder(uids)
        self.engine.requeue()
        self._list_changed()

    def _sort_by_column(self, col: int):
        key = {COL_N: "path", COL_TITLE: "title", COL_ARTIST: "artist", COL_ALBUM: "album", COL_LEN: "length"}[col]
        self.sort_playlist(key)

    def sort_playlist(self, key: str):
        self.pl.sort(key)
        self._rebuild_list()
        self.engine.requeue()

    def _selected_uids(self) -> list[int]:
        return [it.data(0, UID) for it in self.view.selectedItems()]

    def remove_selected(self):
        uids = set(self._selected_uids())
        if not uids:
            return
        row = min(self.view.indexOfTopLevelItem(self.items[u]) for u in uids if u in self.items)
        gone = [tr for tr in self.pl.tracks if tr.uid in uids]
        self.pl.remove(uids, self.engine.cur)
        if any(self.engine.queue_pos(tr) for tr in gone):
            self.engine.dequeue(gone)
        for u in uids:
            it = self.items.pop(u, None)
            if it is not None:
                self.view.takeTopLevelItem(self.view.indexOfTopLevelItem(it))
        if self.view.topLevelItemCount():
            it = self.view.topLevelItem(min(row, self.view.topLevelItemCount() - 1))
            self.view.setCurrentItem(it)
        self.engine.requeue()
        self._list_changed()

    def remove_missing(self):
        gone = {tr.uid for tr in self.pl.tracks if "://" not in tr.path and not os.path.isfile(tr.path)}
        if gone:
            self.pl.remove(gone, self.engine.cur)
            self._rebuild_list()
            self.engine.requeue()
        self.toast.show_text(t("removed_n", len(gone)))

    def clear_playlist(self, confirm: bool = True):
        if confirm and self.pl.tracks and self.cfg.get("confirm_clear", True):
            r = QMessageBox.question(self, APP_TITLE, t("clear_confirm", len(self.pl.tracks)),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                return
        if self.engine.queue:
            self.engine.dequeue([tr for tr in self.pl.tracks if self.engine.queue_pos(tr)])
        if self.engine.pl is self.pl:
            self.engine.stop()
            self.engine.cur = None
            self.engine.stop_after = None
            self._show_track(None)
        self.pl.clear()
        self._rebuild_list()

    def jump_to_current(self):
        cur = self.engine.cur
        if cur is not None and self.engine.pl is not self.pl and self.engine.pl in self.pls:
            self.tabbar.setCurrentIndex(self.pls.index(self.engine.pl))
        it = self.items.get(cur.uid) if cur else None
        if it is not None:
            if it.isHidden():
                self._search_anchor = cur.uid
                self.search.clear()
            self.view.setCurrentItem(it)
            self.view.scrollToItem(it, PlaylistView.PositionAtCenter)

    def _list_menu(self, pos):
        it = self.view.itemAt(pos)
        m = QMenu(self)
        if it is not None:
            uid = it.data(0, UID)
            m.addAction(style.icon("fa6s.play"), t("play") + "\tEnter", lambda: self.play_uid(uid))
            m.addAction(style.icon("fa6s.angles-right"), t("play_next") + "\tCtrl+Q",
                        lambda: self.queue_selected(front=True))
            m.addAction(style.icon("fa6s.list-ol"), t("add_queue") + "\tCtrl+Shift+Q",
                        lambda: self.queue_selected(front=False))
            sel_q = [tr for tr in self._selected_tracks() if self.engine.queue_pos(tr)]
            if sel_q:
                m.addAction(style.icon("fa6s.xmark"), t("unqueue"), lambda q=sel_q: self.engine.dequeue(q))
            trk = self.pl.by_uid(uid)
            fav = trk is not None and self.favs.has(trk)
            m.addAction(style.icon("fa6s.star", STAR if not fav else style.MUTED),
                        (t("unfav") if fav else t("fav")) + "\tCtrl+D", self.toggle_fav_selected)
            m.addAction(style.icon("fa6s.pen"), t("edit_tags") + "\tF2", self.edit_tags_selected)
            m.addSeparator()
            m.addAction(style.icon("fa6s.trash-can"), t("remove") + "\tDel", self.remove_selected)
            tr = self.pl.by_uid(uid)
            if tr is not None and os.path.exists(tr.path):
                m.addAction(style.icon("fa6s.folder-open"), t("show_in_folder"),
                            lambda p=tr.path: winint.show_in_explorer(p))
            m.addSeparator()
        m.addAction(style.icon("fa6s.crosshairs"), t("jump") + "\tCtrl+J", self.jump_to_current)
        if it is not None:
            uid = it.data(0, UID)
            a = m.addAction(style.icon("fa6s.circle-stop"), t("stop_after_this"),
                            lambda u=uid: self.set_stop_after(None if self.engine.stop_after == u else u))
            a.setCheckable(True)
            a.setChecked(self.engine.stop_after == uid)
        sm = m.addMenu(style.icon("fa6s.arrow-down-a-z"), t("sort"))
        for key in ("path", "artist", "album", "title", "length"):
            sm.addAction(t("sort_" + key), lambda k=key: self.sort_playlist(k))
        m.addAction(style.icon("fa6s.broom"), t("remove_missing"), self.remove_missing)
        m.addAction(style.icon("fa6s.trash-can"), t("clear_pl"), self.clear_playlist)
        cm = m.addMenu(style.icon("fa6s.table-columns"), t("columns"))
        hidden = set(self.cfg.get("hidden_cols") or [])
        for key, name in (("n", "#"), ("artist", t("col_artist")), ("album", t("col_album")), ("len", t("col_len")),
                          ("fav", "★")):
            a = cm.addAction(name)
            a.setCheckable(True)
            a.setChecked(key not in hidden)
            a.triggered.connect(lambda on, k=key: self._set_column(k, on))
        m.exec(self.view.viewport().mapToGlobal(pos))

    # ── adding ────────────────────────────────────────────────
    def open_paths(self, paths: list[str], add: bool = False, play: bool = True):
        """From Explorer / the command line: replace the playlist and play (add=True: append)."""
        tracks = expand(paths)
        if not tracks:
            self.toast.show_text(t("nothing_to_play"), 2500)
            return
        if not add:
            self.engine.stop()
            self.pl.clear()
        elif self.cfg.get("skip_dups", True):
            tracks = self.pl.without_dups(tracks)
            if not tracks:
                self.toast.show_text(t("already_in"), 2000)
                return
        self.pl.add(tracks, current=self.engine.cur)
        if self.pl.shuffle and not add:
            self.pl.reshuffle(tracks[0])
        self.tags.add(tracks)
        self._rebuild_list()
        if play and (not add or self.engine.stopped):
            self.play_uid(tracks[0].uid)
        else:
            self.engine.requeue()
            self.toast.show_text(t("added_n", len(tracks)))
        self._remember_dir(paths[0])

    def add_paths(self, paths: list[str], row: int = -1):
        tracks = expand(paths)
        if tracks and self.cfg.get("skip_dups", True):
            tracks = self.pl.without_dups(tracks)
            if not tracks:
                self.toast.show_text(t("already_in"), 2000)
                return
        if not tracks:
            return
        self.pl.add(tracks, at=row, current=self.engine.cur)
        self.tags.add(tracks)
        self._rebuild_list()
        if self.engine.stopped and self.engine.cur is None:
            self.play_uid(tracks[0].uid)
        else:
            self.engine.requeue()
            self.toast.show_text(t("added_n", len(tracks)))

    def _dropped_on_list(self, paths: list[str], row: int):
        self.add_paths(paths, row)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() if u.isLocalFile() else u.toString() for u in e.mimeData().urls()
                 if u.isLocalFile() or u.scheme() in ("http", "https")]
        if paths:
            self.open_paths(paths, add=False)

    def add_url_dialog(self):
        clip = (QApplication.clipboard().text() or "").strip()
        url, ok = QInputDialog.getText(self, t("add_url"), t("add_url_hint"), QLineEdit.Normal,
                                       clip if is_url(clip) else "")
        url = (url or "").strip()
        if not ok or not url:
            return
        if not is_url(url):
            url = "http://" + url
        self.add_paths([url])

    def _remember_dir(self, p: str):
        if is_url(p):
            return
        d = p if os.path.isdir(p) else os.path.dirname(p)
        if d:
            self.cfg["last_dir"] = d

    def _filters(self) -> str:
        audio_ = " ".join("*" + e for e in AUDIO_EXT)
        lists = " ".join("*" + e for e in PLAYLIST_EXT + CUE_EXT)
        return f"{t('music_files')} ({audio_} {lists});;{t('playlists')} ({lists});;{t('all_files')} (*)"

    def add_files_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, t("add_files"), self.cfg.get("last_dir", ""), self._filters())
        if paths:
            self._remember_dir(paths[0])
            self.add_paths(paths)

    def add_folder_dialog(self):
        d = QFileDialog.getExistingDirectory(self, t("add_folder"), self.cfg.get("last_dir", ""))
        if d:
            self._remember_dir(d)
            self.add_paths([d])

    def load_playlist_dialog(self):
        p, _ = QFileDialog.getOpenFileName(self, t("load_pl"), self.cfg.get("last_dir", ""),
                                           f"{t('playlists')} (*.m3u *.m3u8 *.pls *.cue)")
        if p:
            self.open_paths([p], add=False)

    def save_playlist_dialog(self):
        if not self.pl.tracks:
            return
        start = os.path.join(self.cfg.get("last_dir", ""), "playlist.m3u8")
        p, _ = QFileDialog.getSaveFileName(self, t("save_pl"), start, "M3U8 (*.m3u8);;M3U (*.m3u)")
        if not p:
            return
        if not p.lower().endswith((".m3u", ".m3u8")):
            p += ".m3u8"
        try:
            write_m3u(p, self.pl.tracks)
            self.toast.show_text(t("pl_saved", os.path.basename(p)))
        except OSError as e:
            QMessageBox.warning(self, APP_TITLE, t("pl_save_fail", e))

    # ── playback ──────────────────────────────────────────────
    def play_uid(self, uid, offset: float = 0.0, paused: bool = False):
        tr = self.pl.by_uid(uid) if uid is not None else None
        if tr is None:
            return
        if self.engine.pl is not self.pl:                  # another tab starts playing
            self._set_playing_pl(self.pl, tr)
        elif self.pl.shuffle and self.engine.cur is None:
            self.pl.reshuffle(tr)
        self.engine.play(tr, offset, paused)

    def toggle_pause(self):
        if self.engine.cur is None:
            sel = self._selected_uids()
            if sel:
                self.play_uid(sel[0])
            elif self.pl.tracks:
                first = self.pl.next_after(None, auto=False) if self.pl.shuffle else self.pl.tracks[0]
                self.play_uid(first.uid if first else self.pl.tracks[0].uid)
            return
        self.engine.toggle_pause()

    def stop(self):
        self.engine.stop()
        self._refresh_item(self.engine.cur.uid) if self.engine.cur else None
        self._thumb_update()
        self._meters_need()

    def next(self):
        nxt = self.engine.next_track(self.engine.cur, auto=False)
        if nxt is not None:
            self.engine.play(nxt)

    def prev(self):
        pos, _ = self._last_pos
        limit = int(self.cfg.get("prev_restart", 3))
        if limit and pos > limit and self.engine.cur is not None and not self.engine.stopped \
                and not self.engine.cur.is_stream:
            self.engine.seek(0)
            return
        prv = self.engine.prev_track(self.engine.cur)
        if prv is not None:
            self.engine.play(prv)

    def set_volume(self, v: int):
        self.cfg["volume"] = int(v)
        self.engine.set_volume(int(v), bool(self.cfg.get("muted")))
        self.l_vol.setText(f"{int(v)}%")
        self._sync_mute_icon()

    def toggle_mute(self):
        self.cfg["muted"] = not self.cfg.get("muted")
        self.engine.set_volume(self.vol.value(), self.cfg["muted"])
        self._sync_mute_icon()
        self.toast.show_text(t("muted") if self.cfg["muted"] else t("unmuted", self.vol.value()), 1000)

    def _sync_mute_icon(self):
        v = self.vol.value()
        name = "fa6s.volume-xmark" if self.cfg.get("muted") or v == 0 else \
            "fa6s.volume-low" if v < 40 else "fa6s.volume-high"
        self.b_mute.setIcon(style.icon(name, "#ffffff"))
        self.l_vol.setText(f"{v}%")
        if self.mini is not None:
            self.mini.b_mute.setIcon(style.icon(name, "#ffffff"))

    def toggle_shuffle(self):
        on = not self.engine.pl.shuffle
        for p in self.pls:
            p.set_shuffle(on, self.engine.cur if p is self.engine.pl else None)
        self.cfg["shuffle"] = on
        self._sync_mode_buttons()
        self.engine.requeue()
        self._update_next_label()
        self.toast.show_text(t("shuffle_on") if on else t("shuffle_off"), 1100)

    def cycle_repeat(self):
        nxt = {"off": "all", "all": "one", "one": "off"}[self.engine.pl.repeat]
        for p in self.pls:
            p.repeat = nxt
        self.cfg["repeat"] = nxt
        self._sync_mode_buttons()
        self.engine.requeue()
        self._update_next_label()
        self.toast.show_text(t("repeat_" + nxt), 1100)

    def _sync_mode_buttons(self):
        self.b_shuffle.setObjectName("on" if self.engine.pl.shuffle else "ctl")
        rep = self.engine.pl.repeat
        self.b_repeat.setObjectName("ctl" if rep == "off" else "on")
        self.b_repeat.setIcon(style.icon({"off": "mdi6.repeat-off", "all": "mdi6.repeat",
                                          "one": "mdi6.repeat-once"}[rep], "#ffffff"))
        self.b_repeat.setToolTip(t("repeat_" + rep) + " (R)")
        for b in (self.b_shuffle, self.b_repeat):
            b.style().unpolish(b)
            b.style().polish(b)
        if self.mini is not None:
            self.mini.set_mode_buttons(self.engine.pl.shuffle, rep)

    # ── engine signals ────────────────────────────────────────
    def _on_track(self, tr: Track | None):
        prev_uid = getattr(self, "_shown_uid", None)
        self._shown_uid = tr.uid if tr else None
        if prev_uid is not None:
            self._refresh_item(prev_uid)
        if tr is not None:
            if not tr.tagged:
                try:
                    fill_tags(tr)
                except Exception:
                    tr.tagged = True
            self._refresh_item(tr.uid)
            it = self.items.get(tr.uid)
            if it is not None and not it.isHidden() and not self.view.underMouse() \
                    and self.cfg.get("follow_playing", True):
                self.view.scrollToItem(it)
            if prev_uid != tr.uid:
                self._notify(tr)
                self._load_wave(tr)
                self._load_lyrics(tr)
                self.history.add(tr)
                self._tab_icons()
        self._show_track(tr)
        self._dirty = True

    def _mini_wave(self):
        if self.mini is not None:
            self.mini.seek.set_wave_enabled(bool(self.cfg.get("waveform", True)))
            self.mini.seek.set_peaks(self.seekbar.peaks or None, self.seekbar.loading)

    def _load_wave(self, tr: Track | None):
        if tr is None or tr.is_stream or not self.cfg.get("waveform", True):
            self._wave_key = ""
            self.seekbar.set_peaks(None)
            self._mini_wave()
            return
        key = key_of(tr)
        if key == self._wave_key and self.seekbar.peaks:
            return
        self._wave_key = key
        self.seekbar.set_peaks(None, loading=True)
        self._mini_wave()
        self.waves.request(tr)
        self.waves.prefetch(self.engine.next_track(tr, auto=True))         # ready when it starts

    def _on_wave(self, key: str, peaks: bytes):
        if key == self._wave_key:
            self.seekbar.set_peaks(peaks)
            self._mini_wave()

    def _show_track(self, tr: Track | None):
        self._meters_need()
        if tr is None:
            self._load_wave(None)
            self._load_lyrics(None)
            self.t_title.setText(APP_TITLE)
            self.t_artist.setText(t("idle_sub"))
            self.t_album.setText("")
            self.t_format.hide()
            self.cover.set_image(None)
            self._set_mini(None)
            self.setWindowTitle(APP_TITLE)
            self.l_pos.setText("0:00")
            self.l_dur.setText("0:00")
            self.seekbar.set_state(0, 0)
            self._update_next_label()
            return
        if tr.is_stream:
            self._show_stream(tr)
            return
        self.t_title.setText(tr.display_title())
        self.t_artist.setText(tr.artist or tr.albumartist or "")
        bits = [b for b in (tr.album, tr.year) if b]
        if tr.number:
            bits.append(t("track_n", tr.number))
        self.t_album.setText(" · ".join(bits))
        self.setWindowTitle(f"{tr.display()} — {APP_TITLE}")
        key = (tr.path, tr.cue)
        if getattr(self, "_cover_key", None) != key:
            self._cover_key = key
            data = meta.cover_bytes(tr.path)
            self.cover.set_image(data or None)
            self._cover_data = data
        self.cur_tags = meta.read(tr.path) if getattr(self, "_tags_path", "") != tr.path else self.cur_tags
        self._tags_path = tr.path
        self._render_format()
        self._set_mini(tr)
        self._update_next_label()
        if self.smtc is not None:
            try:
                no = int(tr.number or 0)
            except ValueError:
                no = 0
            self.smtc.set_track(tr.display_title(), tr.artist or tr.albumartist, tr.album,
                                getattr(self, "_cover_data", b"") or None, no)
            self._smtc_timeline(force=True)

    def _show_stream(self, tr: Track):
        """Internet radio: the song on air (ICY) as the title, the station below."""
        icy = self.engine.icy
        self.t_title.setText(icy or tr.display_title())
        self.t_artist.setText(tr.display_title() if icy else t("radio"))
        from .playlist import stream_title
        self.t_album.setText(t("radio") + " · " + stream_title(tr.path) if icy else stream_title(tr.path))
        self.setWindowTitle(f"{icy or tr.display_title()} — {APP_TITLE}")
        if getattr(self, "_cover_key", None) != (tr.path, ""):
            self._cover_key = (tr.path, "")
            self._cover_data = b""
            self.cover.set_image(None)
        self.cur_tags = None
        self._tags_path = ""
        self._render_format()
        self._set_mini(tr)
        if self.mini is not None and icy:
            self.mini.set_text(icy, tr.display_title())
        self.l_dur.setText(t("live"))
        self._update_next_label()
        if self.smtc is not None:
            self.smtc.set_track(icy or tr.display_title(), tr.display_title() if icy else t("radio"), t("radio"))

    def _on_icy(self, title: str):
        cur = self.engine.cur
        if cur is None or not cur.is_stream:
            return
        self._show_stream(cur)
        if title:
            if self.tray is not None:
                self.tray.setToolTip(f"{title} — {cur.display_title()}"[:120])
            if self.cfg.get("notify") and self.tray is not None and not self.isActiveWindow():
                self.tray.showMessage(title, cur.display_title(), style.app_icon(), 3500)

    def _update_next_label(self):
        cur = self.engine.cur
        if cur is not None and cur.is_stream:
            self.t_next.setText("")
            return
        if cur is not None and not self.engine.stopped and self.engine.stop_after == cur.uid:
            self.t_next.setText(t("up_next_stop"))
            return
        nxt = self.engine.next_track(cur, auto=True) if cur is not None and not self.engine.stopped else None
        self.t_next.setText(t("up_next", nxt.display()) if nxt is not None and nxt.uid != cur.uid else
                            (t("up_next_repeat") if nxt is not None else ""))

    def _on_pos(self, pos: float, dur: float):
        self._last_pos = (pos, dur)
        cur = self.engine.cur
        if cur is not None and cur.is_stream:
            self.seekbar.set_state(0, 0)
            self.l_pos.setText(fmt_time(pos))
            self.l_dur.setText(t("live"))
            if self.mini is not None and self.mini.isVisible():
                self.mini.seek.set_state(0, 0)
                self.mini.set_time(f"{fmt_time(pos)} · {t('live')}")
            return
        if cur is not None and dur and not cur.duration():          # DTS / TrueHD: mutagen does not know the length
            cur.length = cur.start + dur
            self._refresh_item(cur.uid)
            self.dirty_timer.start()
        self.seekbar.set_state(pos, dur)
        if self.smtc is not None:
            self._smtc_timeline()
        if self.lyrics.isVisible():
            self.lyrics.set_pos(pos)
        self.l_pos.setText(fmt_time(pos))
        self.l_dur.setText("−" + fmt_time(max(0.0, dur - pos)) if self.cfg.get("time_remaining") and dur
                           else fmt_time(dur))
        if self.mini is not None and self.mini.isVisible():
            self.mini.seek.set_state(pos, dur)
            self.mini.set_time(f"{fmt_time(pos)} / {fmt_time(dur)}")

    def _on_paused(self, paused: bool):
        icon = "fa6s.play" if paused else "fa6s.pause"
        self.b_play.setIcon(style.icon(icon, "#ffffff"))
        self.b_play.setToolTip((t("play") if paused else t("pause")) + " (Space)")
        if self.mini is not None:
            self.mini.b_play.setIcon(style.icon(icon, "#ffffff"))
        self._meters_need()
        if self.engine.cur is not None:
            self._refresh_item(self.engine.cur.uid)
        self._thumb_update()
        self._update_next_label()
        self._smtc_status()

    # ── Windows media controls (the card over the volume flyout / on the lock screen) ──
    def _setup_smtc(self):
        want = bool(self.cfg.get("smtc", True)) and winint.IS_WIN
        if want and self.smtc is None:
            from .smtc import Smtc
            self.smtc = Smtc()
            self.smtc.button.connect(self._smtc_button)
            self.smtc.seek.connect(self.engine.seek)
            if self.engine.cur is not None:
                self._show_track(self.engine.cur)
                self._smtc_status()
        elif not want and self.smtc is not None:
            self.smtc.stop()
            self.smtc = None

    def _smtc_button(self, name: str):
        if name == "play":
            if self.engine.cur is None or self.engine.stopped or self.engine.paused:
                self.toggle_pause()
        elif name == "pause":
            self.engine.set_paused(True)
        else:
            self.media_action(name)

    def _smtc_status(self):
        if self.smtc is None:
            return
        e = self.engine
        self.smtc.set_status("closed" if e.cur is None else "stopped" if e.stopped else
                             "paused" if e.paused else "playing")
        self._smtc_timeline(force=True)

    def _smtc_timeline(self, force: bool = False):
        """The position on the card: on every change of state, else every 5 s (as Windows asks)."""
        if self.smtc is None or self.engine.cur is None or self.engine.cur.is_stream:
            return
        pos, dur = self._last_pos
        now = time.monotonic()
        t0, p0 = self._smtc_sent
        expect = p0 + (now - t0 if not self.engine.paused else 0)
        if force or now - t0 > 5 or abs(pos - expect) > 2:
            self._smtc_sent = (now, pos)
            self.smtc.set_timeline(pos, dur or self.engine.cur.duration())

    def _on_format(self, info: dict):
        self.fmt_info = info
        self._render_format()

    def _render_format(self):
        info = self.fmt_info
        tr = self.engine.cur
        if not info or tr is None or not info.get("codec"):
            self.t_format.hide()
            return
        tg = self.cur_tags
        bits = tg.bits if tg is not None else 0
        codec = info["codec"]
        if not bits and codec.startswith("pcm_"):
            import re
            m = re.search(r"(\d+)", codec[4:])
            bits = int(m.group(1)) if m else 0
        if not bits and codec in ("truehd", "mlp"):
            bits = 24
        text = audio.describe(codec, info.get("profile", ""), bits, info.get("rate", 0), info.get("channels", 0),
                              info.get("layout", ""), info.get("out_channels", 0),
                              info.get("kbps", 0) or (tg.bitrate if tg is not None else 0),
                              bool(self.cfg.get("upmix")) and self.cfg.get("channels") != "stereo", t("ch_word"))
        self.t_format.setText(text)
        tip = [t("format_tip")]
        if info.get("out_layout"):
            tip.append(t("fmt_out", info["out_layout"], audio.rate_label(info.get("out_rate", 0))))
        rg = self.cfg.get("replaygain", "album")
        tip.append("ReplayGain: " + t("rg_" + rg))
        self.t_format.setToolTip("\n".join(tip))
        self.t_format.show()
        if self.levels_win is not None:
            self.levels_win.set_head(text)

    def _on_finished(self):
        self._smtc_status()
        if self.engine.stop_after is not None:
            self.engine.stop_after = None
            self.toast.show_text(t("stopped_after"), 2000)
        if self.engine.cur is not None:
            self._refresh_item(self.engine.cur.uid)
        self._update_next_label()
        self._thumb_update()
        self._meters_need()

    # ── stop after, sleep timer, time label ───────────────────
    def set_stop_after(self, uid: int | None):
        self.engine.stop_after = uid
        self.engine.requeue()
        self._update_next_label()
        tr = self.pl.by_uid(uid) if uid is not None else None
        self.toast.show_text(t("stop_after_on", tr.display_title()) if tr else t("stop_after_off"), 1600)

    def toggle_stop_after(self):
        cur = self.engine.cur
        if cur is None:
            return
        self.set_stop_after(None if self.engine.stop_after == cur.uid else cur.uid)

    def set_sleep(self, minutes: int):
        """0 = off; the music fades out and pauses when the time is up."""
        if minutes <= 0:
            self._sleep_off()
            self.toast.show_text(t("sleep_off"), 1300)
            return
        self.sleep_until = time.monotonic() + minutes * 60
        self.sleep_timer.start()
        self.toast.show_text(t("sleep_on", minutes), 1600)

    def _sleep_off(self):
        self.sleep_until = 0.0
        self.sleep_timer.stop()

    def _sleep_left(self) -> int:
        return max(0, int(self.sleep_until - time.monotonic())) if self.sleep_until else 0

    def _sleep_tick(self):
        if not self.sleep_until:
            self.sleep_timer.stop()
            return
        if time.monotonic() >= self.sleep_until:
            self._sleep_off()
            if not self.engine.stopped and not self.engine.paused:
                keep = self.cfg.get("fade_pause", 0)
                self.cfg["fade_pause"] = max(int(keep or 0), 3000)      # a long, gentle fade for the night
                self.engine.set_paused(True)
                self.cfg["fade_pause"] = keep
            self.toast.show_text(t("sleep_done"), 2500)

    def toggle_time_remaining(self):
        self.cfg["time_remaining"] = not self.cfg.get("time_remaining")
        self._on_pos(*self._last_pos)

    # ── tray ──────────────────────────────────────────────────
    def _setup_tray(self):
        want = bool(self.cfg.get("tray")) and QSystemTrayIcon.isSystemTrayAvailable()
        if want and self.tray is None:
            self.tray = QSystemTrayIcon(style.app_icon(), self)
            self.tray.setToolTip(APP_TITLE)
            m = QMenu(self)
            m.addAction(style.icon("fa6s.play"), t("play") + " / " + t("pause"), self.toggle_pause)
            m.addAction(style.icon("fa6s.forward-step"), t("next"), self.next)
            m.addAction(style.icon("fa6s.backward-step"), t("prev"), self.prev)
            m.addAction(style.icon("fa6s.stop"), t("stop"), self.stop)
            m.addSeparator()
            m.addAction(style.icon("fa6s.window-maximize"), t("tray_show"), self.show_from_tray)
            m.addAction(style.icon("fa6s.power-off"), t("quit"), self.quit)
            self.tray.setContextMenu(m)
            self.tray.activated.connect(self._tray_click)
            self.tray.show()
        elif not want and self.tray is not None:
            self.tray.hide()
            self.tray.deleteLater()
            self.tray = None

    def _tray_click(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible() and not self.isMinimized() and self.isActiveWindow():
                self.hide()
            else:
                self.show_from_tray()
        elif reason == QSystemTrayIcon.MiddleClick:
            self.toggle_pause()

    def show_from_tray(self):
        if self.mini is not None and self.mini.isVisible():
            self.mini.raise_()
            return
        self.showNormal() if self.isMinimized() else self.show()
        self.raise_()
        self.activateWindow()

    def _notify(self, tr: Track):
        if self.tray is not None:
            self.tray.setToolTip(f"{tr.display()} — {APP_TITLE}"[:120])
        if not self.cfg.get("notify") or self.tray is None or self.isActiveWindow():
            return
        sub = " · ".join(b for b in (tr.artist or tr.albumartist, tr.album) if b)
        self.tray.showMessage(tr.display_title(), sub or APP_TITLE, style.app_icon(), 3500)

    def quit(self):
        self._quitting = True
        if self.mini is not None and self.mini.isVisible():
            self.mini.hide()
        self.close()

    # ── sound ─────────────────────────────────────────────────
    def apply_audio(self):
        err = self.engine.apply_audio()
        if err:
            self.toast.show_text(t("af_fail", err), 2500)
        self._render_format()

    def equalizer_dialog(self):
        from .dialogs import EqualizerDialog
        d = EqualizerDialog(self.cfg, self)
        d.changed.connect(self.apply_audio)
        d.exec()
        config.save(self.cfg)

    def sound_dialog(self):
        from .dialogs import SoundDialog
        d = SoundDialog(self.cfg, self.engine.audio_devices(), self)
        d.changed.connect(lambda reopen: self.engine.apply_options() if reopen else self.apply_audio())
        d.speaker_test.connect(lambda: self.speaker_test(d))
        d.exec()
        self.engine.requeue()
        config.save(self.cfg)

    def speaker_test(self, sound_dlg=None):
        from .dialogs import SpeakerTestDialog
        was_playing = not self.engine.stopped and not self.engine.paused
        if was_playing:
            self.engine.set_paused(True)
        d = SpeakerTestDialog(self.mpvmod, self.cfg, sound_dlg or self)
        d.levels_changed.connect(lambda c, l: self.apply_audio())
        if sound_dlg is not None:
            d.levels_changed.connect(sound_dlg.set_levels)
        d.exec()
        config.save(self.cfg)
        if was_playing:
            self.engine.set_paused(False)

    def set_channels(self, mode: str):
        self.cfg["channels"] = mode
        self.engine.apply_options()
        config.save(self.cfg)
        self.toast.show_text(t("ch_" + mode.replace(".", "")), 1300)

    def set_replaygain(self, mode: str):
        self.cfg["replaygain"] = mode
        self.engine.apply_options()
        config.save(self.cfg)

    def set_crossfade(self, sec: int):
        self.cfg["crossfade"] = sec
        self.engine.requeue()
        config.save(self.cfg)
        self._render_format()

    def toggle_upmix(self):
        self.cfg["upmix"] = not self.cfg.get("upmix")
        self.apply_audio()
        config.save(self.cfg)

    # ── menu ──────────────────────────────────────────────────
    def _main_menu(self):
        m = QMenu(self)
        m.addAction(style.icon("fa6s.file-circle-plus"), t("add_files") + "\tCtrl+O", self.add_files_dialog)
        m.addAction(style.icon("fa6s.folder-plus"), t("add_folder") + "\tCtrl+Shift+O", self.add_folder_dialog)
        m.addAction(style.icon("fa6s.tower-broadcast"), t("add_url") + "\tCtrl+U", self.add_url_dialog)
        m.addAction(style.icon("fa6s.folder-open"), t("load_pl") + "\tCtrl+L", self.load_playlist_dialog)
        m.addAction(style.icon("fa6s.floppy-disk"), t("save_pl") + "\tCtrl+S", self.save_playlist_dialog)
        m.addAction(style.icon("fa6s.plus"), t("new_tab") + "\tCtrl+N", lambda: self.new_tab())
        m.addSeparator()
        m.addAction(style.icon("fa6s.star", STAR), t("favorites") + "\tCtrl+B",
                    lambda: self.open_library_tab("favorites"))
        m.addAction(style.icon("fa6s.clock-rotate-left"), t("history") + "\tCtrl+H",
                    lambda: self.open_library_tab("history"))
        if self.engine.queue:
            qm = m.addMenu(style.icon("fa6s.list-ol"), t("queue_n", len(self.engine.queue)))
            for i, tr in enumerate(self.engine.queue[:15]):
                qm.addAction(f"{i + 1}. {tr.display()}"[:80], lambda x=tr: self._play_track(x))
            qm.addSeparator()
            qm.addAction(style.icon("fa6s.xmark"), t("queue_clear"), lambda: self.engine.dequeue(None))
        m.addSeparator()
        snd = m.addMenu(style.icon("mdi6.surround-sound"), t("sound"))
        g = QActionGroup(snd)
        for key in ("auto", "5.1", "stereo"):
            a = snd.addAction(t("ch_" + key.replace(".", "")))
            a.setCheckable(True)
            a.setChecked(self.cfg.get("channels") == key)
            a.triggered.connect(lambda _=False, k=key: self.set_channels(k))
            g.addAction(a)
        snd.addSeparator()
        a = snd.addAction(t("upmix"))
        a.setCheckable(True)
        a.setChecked(bool(self.cfg.get("upmix")))
        a.triggered.connect(self.toggle_upmix)
        snd.addAction(style.icon("fa6s.volume-high"), t("speaker_test") + "\tCtrl+T", self.speaker_test)
        snd.addAction(style.icon("fa6s.chart-simple"), t("levels") + "\tV", self.toggle_levels)
        snd.addAction(style.icon("fa6s.gear"), t("sound_more") + "\tCtrl+P", self.sound_dialog)
        rg = m.addMenu(style.icon("fa6s.scale-balanced"), "ReplayGain")
        g2 = QActionGroup(rg)
        for key in ("album", "track", "off"):
            a = rg.addAction(t("rg_" + key))
            a.setCheckable(True)
            a.setChecked(self.cfg.get("replaygain") == key)
            a.triggered.connect(lambda _=False, k=key: self.set_replaygain(k))
            g2.addAction(a)
        xf = m.addMenu(style.icon("fa6s.shuffle"), t("crossfade"))
        g3 = QActionGroup(xf)
        for sec in (0, 2, 4, 6, 8):
            a = xf.addAction(t("xf_off") + " (gapless)" if sec == 0 else f"{sec} {t('sec')}")
            a.setCheckable(True)
            a.setChecked(int(self.cfg.get("crossfade", 0)) == sec)
            a.triggered.connect(lambda _=False, s=sec: self.set_crossfade(s))
            g3.addAction(a)
        m.addAction(style.icon("fa6s.sliders"), t("equalizer") + "\tE", self.equalizer_dialog)
        m.addSeparator()
        cur = self.engine.cur
        a = m.addAction(style.icon("fa6s.circle-stop"), t("stop_after_cur") + "\tCtrl+Shift+E", self.toggle_stop_after)
        a.setCheckable(True)
        a.setChecked(cur is not None and self.engine.stop_after == cur.uid)
        a.setEnabled(cur is not None)
        left = self._sleep_left()
        sl = m.addMenu(style.icon("fa6s.moon"), t("sleep") + (f"  ({fmt_time(left)})" if left else ""))
        g4 = QActionGroup(sl)
        a = sl.addAction(t("sleep_none"))
        a.setCheckable(True)
        a.setChecked(not left)
        a.triggered.connect(lambda: self.set_sleep(0))
        g4.addAction(a)
        for mins in SLEEP_MINUTES:
            a = sl.addAction(t("sleep_min", mins))
            a.setCheckable(True)
            a.triggered.connect(lambda _=False, n=mins: self.set_sleep(n))
            g4.addAction(a)
        m.addSeparator()
        a = m.addAction(style.icon("fa6s.clone"), t("mini") + "\tCtrl+M", self.toggle_mini)
        a = m.addAction(style.icon("fa6s.thumbtack"), t("on_top") + "\tT", self.toggle_on_top)
        a.setCheckable(True)
        a.setChecked(bool(self.cfg.get("on_top")))
        m.addSeparator()
        m.addAction(style.icon("fa6s.gear"), t("settings") + "\tCtrl+,", self.settings_dialog)
        m.addAction(style.icon("fa6s.keyboard"), t("keys") + "\tF1", self.keys_dialog)
        m.addAction(style.icon("fa6s.circle-arrow-up"), t("upd_check_now"), lambda: self.check_updates(True))
        m.addAction(style.icon("fa6s.circle-info"), t("about"), self.about)
        if self.tray is not None:
            m.addSeparator()
            m.addAction(style.icon("fa6s.power-off"), t("quit"), self.quit)
        btn = self.b_menu
        sh = m.sizeHint()
        p = btn.mapToGlobal(btn.rect().topRight())
        m.exec(QPoint(p.x() - sh.width(), p.y() - sh.height() - 4))

    def toggle_on_top(self):
        self.cfg["on_top"] = not self.cfg.get("on_top")
        geo = self.saveGeometry()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(self.cfg["on_top"]))
        self.show()
        self.restoreGeometry(geo)
        self.toast.show_text(t("on_top_on") if self.cfg["on_top"] else t("on_top_off"), 1100)

    def settings_dialog(self):
        from .dialogs import SettingsDialog
        lang = self.cfg.get("language")
        keys = self.cfg.get("media_keys")
        top = self.cfg.get("on_top")
        d = SettingsDialog(self.cfg, self)
        if d.exec():
            config.save(self.cfg)
            self._apply_view_options()
            self._setup_tray()
            self._setup_smtc()
            self.seekbar.set_wave_enabled(bool(self.cfg.get("waveform", True)))
            self._load_lyrics(self.engine.cur)
            self._meters_need()
            self._wave_key = ""
            self._load_wave(self.engine.cur)
            self._on_pos(*self._last_pos)
            if keys != self.cfg.get("media_keys"):
                self._media_keys(bool(self.cfg.get("media_keys")))
            if top != self.cfg.get("on_top"):
                self.cfg["on_top"] = top
                self.toggle_on_top()
            if lang != self.cfg.get("language"):
                QMessageBox.information(self, APP_TITLE, t("lang_restart"))

    def keys_dialog(self):
        from .dialogs import KeysDialog
        KeysDialog(self).exec()

    def about(self):
        try:
            mv = str(self.engine.mpv.mpv_version or "")
            ff = str(self.engine.mpv.ffmpeg_version or "")
        except Exception:
            mv = ff = ""
        QMessageBox.about(self, t("about"), t("about_text", VERSION, mv, ff))

    # ── mini player ───────────────────────────────────────────
    def toggle_mini(self):
        if self.mini is not None and not self.mini.isVisible() and \
                self.mini.strip != (self.cfg.get("mini_style", "card") == "strip"):   # the look was changed in settings
            self.mini.deleteLater()
            self.mini = None
        if self.mini is None:
            self.mini = MiniWindow(self)
        if self.mini.isVisible():
            self.cfg["mini_geometry"] = [self.mini.x(), self.mini.y()]
            self.mini.hide()
            self.show()
            self.raise_()
            self.activateWindow()
            self._meters_need()
            return
        self._fill_mini()
        geo = self.cfg.get("mini_geometry") or []
        scr = self.screen().availableGeometry()
        if len(geo) >= 2 and scr.adjusted(-40, -40, 40, 40).contains(QPoint(int(geo[0]) + 40, int(geo[1]) + 20)):
            self.mini.move(int(geo[0]), int(geo[1]))
        else:
            self.mini.move(scr.right() - self.mini.width() - 24, scr.bottom() - self.mini.height() - 24)
        self.hide()
        self.mini.show()
        self._meters_need()

    def _fill_mini(self):
        """Everything the mini player shows, from the big window's state."""
        m = self.mini
        self._set_mini(self.engine.cur)
        m.b_play.setIcon(style.icon("fa6s.play" if self.engine.paused else "fa6s.pause", "#ffffff"))
        m.set_mode_buttons(self.engine.pl.shuffle, self.engine.pl.repeat)
        self._sync_mute_icon()
        self._mini_wave()
        self._on_pos(*self._last_pos)
        cur = self.engine.cur
        if cur is not None and cur.is_stream and self.engine.icy:
            m.set_text(self.engine.icy, cur.display_title())

    def switch_mini_look(self):
        """Card ⇄ strip: the mini player is built again in the other look, at the same place."""
        self.cfg["mini_style"] = "strip" if self.cfg.get("mini_style", "card") == "card" else "card"
        old = self.mini
        if old is None:
            return
        vis = old.isVisible()
        pos = old.pos()
        h = old.height()
        old.hide()
        old.deleteLater()
        self.mini = MiniWindow(self)
        self._fill_mini()
        self.mini.move(pos.x(), pos.y() + h - self.mini.height())      # keep the bottom edge where it was
        if vis:
            self.mini.show()

    def set_mini_opacity(self, v: int):
        self.cfg["mini_opacity"] = int(v)
        if self.mini is not None:
            self.mini.update()

    def mini_menu(self, at: QPoint):
        m = QMenu(self.mini)
        strip = self.cfg.get("mini_style", "card") == "strip"
        grp = QActionGroup(m)
        for key in ("card", "strip"):
            a = m.addAction(t("mini_" + key))
            a.setCheckable(True)
            a.setChecked((key == "strip") == strip)
            a.setActionGroup(grp)
            a.triggered.connect(lambda _=False, k=key: self.switch_mini_look()
                                if self.cfg.get("mini_style", "card") != k else None)
        m.addSeparator()
        op = m.addMenu(t("mini_opacity"))
        g2 = QActionGroup(op)
        cur = int(self.cfg.get("mini_opacity", 85))
        for v in (100, 90, 85, 75, 60, 50):
            a = op.addAction(f"{v}%")
            a.setCheckable(True)
            a.setChecked(v == cur)
            a.setActionGroup(g2)
            a.triggered.connect(lambda _=False, x=v: self.set_mini_opacity(x))
        a = m.addAction(t("mini_hover_opaque"))
        a.setCheckable(True)
        a.setChecked(bool(self.cfg.get("mini_hover_opaque", True)))
        a.triggered.connect(lambda on: self.cfg.__setitem__("mini_hover_opaque", bool(on)))
        a = m.addAction(t("mini_pin"))
        a.setCheckable(True)
        a.setChecked(bool(self.cfg.get("mini_on_top", True)))
        a.triggered.connect(lambda _=False: self.mini.toggle_pin())
        m.addSeparator()
        m.addAction(t("levels") + "\tV", self.toggle_levels)
        m.addAction(t("mini_back") + "\tEsc", self.toggle_mini)
        m.exec(at)

    def _set_mini(self, tr: Track | None):
        if self.mini is None:
            return
        if tr is None:
            self.mini.set_text(APP_TITLE, "")
            self.mini.set_cover(None)
            return
        self.mini.set_text(tr.display_title(), tr.artist or tr.album or (t("radio") if tr.is_stream else ""))
        self.mini.set_cover(getattr(self, "_cover_data", b"") or None)

    # ── session ───────────────────────────────────────────────
    def save_session(self):
        cur = self.engine.cur
        pos, _ = self._last_pos
        self.pl.scroll = self.view.verticalScrollBar().value()
        play_pl = self.engine.pl if self.engine.pl in self.pls else self.pl
        s = {"tabs": [{"name": p.name, "kind": p.kind, "scroll": p.scroll,
                       "tracks": [tr.to_dict() for tr in p.tracks] if not p.kind else []} for p in self.pls],
             "view": self.pls.index(self.pl),
             "playing_tab": self.pls.index(play_pl),
             "current": play_pl.index_of(cur),
             "position": round(pos, 1) if cur is not None and not self.engine.stopped and not cur.is_stream else 0.0,
             "playing": cur is not None and not self.engine.stopped and not self.engine.paused}
        config.save_session(s)
        self._dirty = False

    def restore_session(self) -> bool:
        if not self.cfg.get("resume", True):
            return False
        s = config.load_session()
        tabs = s.get("tabs")
        if not isinstance(tabs, list) or not tabs:                     # 1.0–1.3: one playlist
            tabs = [{"name": t("playlist"), "tracks": s.get("tracks", [])}]
            s["playing_tab"] = s["view"] = 0
        pls = []
        for d in tabs:
            if not isinstance(d, dict):
                continue
            p = self._new_pl(str(d.get("name") or t("playlist")), str(d.get("kind") or ""))
            p.scroll = int(d.get("scroll", 0) or 0)
            if p.kind:
                self._fill_library(p)
            else:
                p.add([Track.from_dict(x) for x in d.get("tracks", []) if isinstance(x, dict) and x.get("path")])
            pls.append(p)
        if not pls or not any(p.tracks for p in pls) and len(pls) == 1:
            return False
        self._set_tabs(pls, max(0, min(int(s.get("view", 0) or 0), len(pls) - 1)))
        play_pl = pls[max(0, min(int(s.get("playing_tab", 0) or 0), len(pls) - 1))]
        tracks = play_pl.tracks
        i = int(s.get("current", -1))
        self._set_playing_pl(play_pl, tracks[i] if 0 <= i < len(tracks) else None)
        for p in pls:
            self.tags.add(p.tracks)
        if 0 <= i < len(tracks) and (tracks[i].is_stream or os.path.exists(tracks[i].path)):
            play = bool(self.cfg.get("resume_play")) and bool(s.get("playing"))
            self.engine.play(tracks[i], float(s.get("position", 0) or 0), paused=not play)
            if play_pl is self.pl:
                self.jump_to_current()
        return True

    def restore_geometry(self):
        g = self.cfg.get("geometry") or ""
        if g:
            self.restoreGeometry(QByteArray.fromBase64(g.encode()))
        sp = self.cfg.get("splitter") or []
        if len(sp) == 2:
            self.split.setSizes([int(x) for x in sp])
        else:
            self.split.setSizes([380, 800])

    # ── updates ───────────────────────────────────────────────
    def maybe_check_updates(self):
        from . import updater
        if self.cfg.get("check_updates", True) and updater.can_self_update() \
                and time.time() - float(self.cfg.get("last_update_check", 0)) > self.UPDATE_EVERY:
            self.check_updates()

    def check_updates(self, manual: bool = False):
        from . import updater
        self._update_manual = manual
        self.cfg["last_update_check"] = int(time.time())
        config.save(self.cfg)

        def work():
            try:
                self.bridge.update.emit(updater.check(), "")
            except Exception as e:
                self.bridge.update.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_update_result(self, info, err: str):
        manual = getattr(self, "_update_manual", False)
        if err:
            if manual:
                QMessageBox.warning(self, APP_TITLE, t("upd_error", err))
            return
        if not info:
            if manual:
                QMessageBox.information(self, APP_TITLE, t("upd_none", VERSION))
            return
        self.update_info = info
        if manual or self.cfg.get("update_notified") != info["version"]:
            self.cfg["update_notified"] = info["version"]
            config.save(self.cfg)
            self.show_update()

    def show_update(self):
        info = self.update_info
        if not info:
            return
        from . import updater
        if not updater.can_self_update() or not info.get("url"):
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(info["page"]))
            return
        from .dialogs import UpdateDialog
        d = UpdateDialog(info, self)
        if d.exec() and d.path:
            self._installer = d.path
            self.quit()

    # ── Windows: media keys, taskbar buttons ──────────────────
    def _media_keys(self, on: bool):
        hwnd = int(self.winId())
        winint.unregister_media_keys(hwnd, self._hotkeys)
        self._hotkeys = winint.register_media_keys(hwnd) if on else []

    def _thumb_icons_for(self) -> list[int]:
        if not winint.IS_WIN:
            return [0, 0, 0]
        names = ("fa6s.backward-step", "fa6s.play" if self.engine.paused else "fa6s.pause", "fa6s.forward-step")
        out = []
        for n in names:
            if n not in self._thumb_icons:
                img = style.icon(n, "#ffffff").pixmap(20, 20).toImage()
                self._thumb_icons[n] = winint.hicon_from_qimage(img)
            out.append(self._thumb_icons[n])
        return out

    def _thumb_tips(self) -> list[str]:
        return [t("prev"), t("play") if self.engine.paused else t("pause"), t("next")]

    def _thumb_update(self):
        if winint.IS_WIN and self.thumbbar.added:
            self.thumbbar.update(int(self.winId()), self._thumb_icons_for(), self._thumb_tips())

    def media_action(self, action: str):
        {"play_pause": self.toggle_pause, "play": self.toggle_pause, "pause": lambda: self.engine.set_paused(True),
         "next": self.next, "prev": self.prev, "stop": self.stop}.get(action, lambda: None)()

    def nativeEvent(self, event_type, message):
        if winint.IS_WIN:
            try:
                _hwnd, msg, wparam, lparam = winint.read_msg(message)
                if msg == winint.WM_HOTKEY:
                    self.media_action(winint.hotkey_action(wparam))
                    return True, 0
                if msg == winint.WM_COMMAND:
                    bid = winint.ThumbBar.clicked(wparam)
                    if bid:
                        {1: self.prev, 2: self.toggle_pause, 3: self.next}[bid]()
                        return True, 0
                if self.thumbbar.msg_created and msg == self.thumbbar.msg_created:
                    self.thumbbar.added = False
                    self.thumbbar.add(int(self.winId()), self._thumb_icons_for(), self._thumb_tips())
            except Exception:
                pass
        return super().nativeEvent(event_type, message)

    # ── window ────────────────────────────────────────────────
    def showEvent(self, e):
        super().showEvent(e)
        winint.dark_title_bar(int(self.winId()))
        if not getattr(self, "_shown_once", False):
            self._shown_once = True
            if self.cfg.get("media_keys", True):
                self._media_keys(True)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.empty.resize(self.view.viewport().size())

    def closeEvent(self, e):
        if self.tray is not None and self.cfg.get("close_to_tray") and not self._quitting \
                and not getattr(self, "_installer", ""):
            e.ignore()
            self.hide()
            self.save_session()
            if not self.cfg.get("tray_hint_shown"):
                self.cfg["tray_hint_shown"] = True
                self.tray.showMessage(APP_TITLE, t("tray_hint"), style.app_icon(), 3000)
            return
        self.save_session()
        if not self.isFullScreen():
            self.cfg["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.cfg["splitter"] = self.split.sizes()
        self.cfg["columns"] = [self.view.columnWidth(COL_ARTIST), self.view.columnWidth(COL_ALBUM)]
        if self.mini is not None and self.mini.isVisible():
            self.cfg["mini_geometry"] = [self.mini.x(), self.mini.y()]
        config.save(self.cfg)
        self.save_timer.stop()
        self.tags.stop()
        if self.smtc is not None:
            self.smtc.stop()
        self.waves.stop()
        winint.unregister_media_keys(int(self.winId()), self._hotkeys)
        self.engine.shutdown()
        self.sleep_timer.stop()
        if self.tray is not None:
            self.tray.hide()
        if self.mini is not None:
            self.mini.deleteLater()
        installer = getattr(self, "_installer", "")
        if installer:                         # self-update: settings saved, let the installer in
            from . import updater
            winint.release_mutex()
            updater.run_installer(installer)
        super().closeEvent(e)
        QApplication.instance().quit()
