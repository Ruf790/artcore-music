"""The main window: now playing (cover, tags, format line), the playlist, the transport bar; the mini player."""
from __future__ import annotations

import os
import queue
import threading
import time

from PySide6.QtCore import QByteArray, QObject, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QActionGroup, QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
                               QMenu, QMessageBox, QSlider, QSplitter, QSystemTrayIcon, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from . import APP_TITLE, AUDIO_EXT, CUE_EXT, PLAYLIST_EXT, VERSION, audio, config, meta, style, winint
from .engine import Engine
from .i18n import t
from .playlist import Playlist, Track, expand, fill_tags, write_m3u
from .widgets import ClickLabel, CoverView, PlaylistView, SeekBar, Toast, ctl_button, elide, fmt_time

COL_N, COL_TITLE, COL_ARTIST, COL_ALBUM, COL_LEN = range(5)
COL_KEYS = {"n": COL_N, "artist": COL_ARTIST, "album": COL_ALBUM, "len": COL_LEN}
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
        threading.Thread(target=self._run, daemon=True).start()

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
            self.bridge.tagged.emit(tr.uid)

    def stop(self):
        self.alive = False
        self.q.put(None)


class MiniWindow(QWidget):
    """Small always-on-top player: cover, title, ⏮ ⏯ ⏭, seek bar. Drag it anywhere; double-click = big window."""

    def __init__(self, win: "MainWindow"):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.win = win
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(style.app_icon())
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(440, 104)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = QWidget()
        box.setObjectName("mini")
        outer.addWidget(box)
        lay = QHBoxLayout(box)
        lay.setContentsMargins(10, 10, 10, 8)
        lay.setSpacing(10)
        self.cover = CoverView(radius=0.08)
        self.cover.setFixedSize(84, 84)
        lay.addWidget(self.cover)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title = QLabel()
        self.title.setStyleSheet("font-weight: 600; font-size: 10.5pt;")
        self.artist = QLabel()
        self.artist.setObjectName("album")
        col.addWidget(self.title)
        col.addWidget(self.artist)
        row = QHBoxLayout()
        row.setSpacing(2)
        self.b_prev = ctl_button("fa6s.backward-step", t("prev"), 16, win.prev)
        self.b_play = ctl_button("fa6s.play", t("play"), 18, win.toggle_pause)
        self.b_next = ctl_button("fa6s.forward-step", t("next"), 16, win.next)
        self.time = QLabel("0:00")
        self.time.setObjectName("hint")
        for w in (self.b_prev, self.b_play, self.b_next):
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(self.time)
        row.addWidget(ctl_button("fa6s.up-right-and-down-left-from-center", t("mini_back") + " (Ctrl+M)", 14,
                                 win.toggle_mini))
        col.addLayout(row)
        self.seek = SeekBar(thin=True)
        self.seek.seek.connect(win.engine.seek)
        col.addWidget(self.seek)
        lay.addLayout(col, 1)
        self._drag = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        self.win.toggle_mini()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.win.toggle_mini()
        elif e.key() == Qt.Key_Space:
            self.win.toggle_pause()
        else:
            super().keyPressEvent(e)

    def closeEvent(self, e):
        e.ignore()
        self.win.toggle_mini()


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
        self.pl = Playlist()
        self.pl.repeat = cfg.get("repeat", "off")
        self.pl.shuffle = bool(cfg.get("shuffle"))
        self.engine = Engine(mpv_module, cfg, self.pl)
        self.engine.track_changed.connect(self._on_track)
        self.engine.position.connect(self._on_pos)
        self.engine.paused_changed.connect(self._on_paused)
        self.engine.format_changed.connect(self._on_format)
        self.engine.finished.connect(self._on_finished)
        self.engine.error.connect(lambda s: self.toast.show_text(t("play_error", s), 3500))
        self.bridge = Bridge()
        self.bridge.tagged.connect(self._on_tagged)
        self.bridge.update.connect(self._on_update_result)
        self.tags = TagReader(self.bridge)
        self.items: dict[int, QTreeWidgetItem] = {}
        self.cur_tags = None
        self.fmt_info: dict = {}
        self.update_info: dict | None = None
        self.mini: MiniWindow | None = None
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
        lay.addLayout(row)
        self.t_next = QLabel()
        self.t_next.setObjectName("hint")
        self.t_next.setWordWrap(True)
        lay.addWidget(self.t_next)
        lay.addStretch(1)
        return w

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
        top.addWidget(ctl_button("fa6s.folder-open", t("load_pl") + " (Ctrl+L)", 17, self.load_playlist_dialog))
        top.addWidget(ctl_button("fa6s.floppy-disk", t("save_pl") + " (Ctrl+S)", 17, self.save_playlist_dialog))
        top.addWidget(ctl_button("fa6s.trash-can", t("clear_pl"), 17, self.clear_playlist))
        lay.addLayout(top)
        self.view = PlaylistView()
        self.view.setHeaderLabels(["#", t("col_title"), t("col_artist"), t("col_album"), t("col_len")])
        hdr = self.view.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(COL_N, QHeaderView.Fixed)
        hdr.setSectionResizeMode(COL_TITLE, QHeaderView.Stretch)
        hdr.setSectionResizeMode(COL_ARTIST, QHeaderView.Interactive)
        hdr.setSectionResizeMode(COL_ALBUM, QHeaderView.Interactive)
        hdr.setSectionResizeMode(COL_LEN, QHeaderView.Fixed)
        hdr.setSectionsClickable(True)
        hdr.sectionClicked.connect(self._sort_by_column)
        self.view.setColumnWidth(COL_N, 46)
        self.view.setColumnWidth(COL_ARTIST, 170)
        self.view.setColumnWidth(COL_ALBUM, 170)
        self.view.setColumnWidth(COL_LEN, 64)
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
        self.seekbar = SeekBar()
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
        sc("Delete", self.remove_selected)
        sc("Ctrl+O", self.add_files_dialog)
        sc("Ctrl+Shift+O", self.add_folder_dialog)
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
        it.setText(COL_N, tr.number or "")
        it.setText(COL_TITLE, tr.display_title())
        it.setText(COL_ARTIST, tr.artist or tr.albumartist)
        it.setText(COL_ALBUM, tr.album + (f" ({tr.year})" if tr.year and tr.album else ""))
        d = tr.duration()
        it.setText(COL_LEN, fmt_time(d) if d else "")
        it.setToolTip(COL_TITLE, tr.path + (f"\n{t('cue_track')} {fmt_time(tr.start)}" if tr.is_cue else ""))
        playing = self.engine.cur is not None and tr.uid == self.engine.cur.uid
        f = QFont(self.view.font())
        f.setBold(playing)
        for c in range(5):
            it.setFont(c, f)
            it.setForeground(c, QColor("#8fb8ff") if playing else QColor(style.TEXT if c != COL_N else style.MUTED))
        it.setIcon(COL_N, style.icon("fa6s.volume-high" if not self.engine.paused else "fa6s.pause", "#8fb8ff")
                   if playing and not self.engine.stopped else style.icon("fa6s.music", "#00000000"))

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
        names = {"n": "#", "artist": t("col_artist"), "album": t("col_album"), "len": t("col_len")}
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
        if self.search.hasFocus():
            return
        uids = set(self._selected_uids())
        if not uids:
            return
        row = min(self.view.indexOfTopLevelItem(self.items[u]) for u in uids if u in self.items)
        self.pl.remove(uids, self.engine.cur)
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
        self.engine.stop()
        self.engine.cur = None
        self.pl.clear()
        self._rebuild_list()
        self._show_track(None)

    def jump_to_current(self):
        cur = self.engine.cur
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
                            lambda u=uid: self.set_stop_after(None if self.pl.stop_after == u else u))
            a.setCheckable(True)
            a.setChecked(self.pl.stop_after == uid)
        sm = m.addMenu(style.icon("fa6s.arrow-down-a-z"), t("sort"))
        for key in ("path", "artist", "album", "title", "length"):
            sm.addAction(t("sort_" + key), lambda k=key: self.sort_playlist(k))
        m.addAction(style.icon("fa6s.broom"), t("remove_missing"), self.remove_missing)
        m.addAction(style.icon("fa6s.trash-can"), t("clear_pl"), self.clear_playlist)
        cm = m.addMenu(style.icon("fa6s.table-columns"), t("columns"))
        hidden = set(self.cfg.get("hidden_cols") or [])
        for key, name in (("n", "#"), ("artist", t("col_artist")), ("album", t("col_album")), ("len", t("col_len"))):
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
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.open_paths(paths, add=False)

    def _remember_dir(self, p: str):
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
                                           f"{t('playlists')} (*.m3u *.m3u8 *.cue)")
        if p:
            self.open_paths([p], add=False)

    def save_playlist_dialog(self):
        if not self.pl.tracks:
            return
        start = os.path.join(self.cfg.get("last_dir", ""), "playlist.m3u8")
        p, _ = QFileDialog.getSaveFileName(self, t("save_pl"), start, "M3U8 (*.m3u8);;M3U (*.m3u)")
        if not p:
            return
        if not p.lower().endswith(PLAYLIST_EXT):
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
        if self.pl.shuffle and self.engine.cur is None:
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

    def next(self):
        nxt = self.pl.next_after(self.engine.cur, auto=False)
        if nxt is not None:
            self.engine.play(nxt)

    def prev(self):
        pos, _ = self._last_pos
        limit = int(self.cfg.get("prev_restart", 3))
        if limit and pos > limit and self.engine.cur is not None and not self.engine.stopped:
            self.engine.seek(0)
            return
        prv = self.pl.prev_before(self.engine.cur)
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

    def toggle_shuffle(self):
        on = not self.pl.shuffle
        self.pl.set_shuffle(on, self.engine.cur)
        self.cfg["shuffle"] = on
        self._sync_mode_buttons()
        self.engine.requeue()
        self._update_next_label()
        self.toast.show_text(t("shuffle_on") if on else t("shuffle_off"), 1100)

    def cycle_repeat(self):
        nxt = {"off": "all", "all": "one", "one": "off"}[self.pl.repeat]
        self.pl.repeat = nxt
        self.cfg["repeat"] = nxt
        self._sync_mode_buttons()
        self.engine.requeue()
        self._update_next_label()
        self.toast.show_text(t("repeat_" + nxt), 1100)

    def _sync_mode_buttons(self):
        self.b_shuffle.setObjectName("on" if self.pl.shuffle else "ctl")
        rep = self.pl.repeat
        self.b_repeat.setObjectName("ctl" if rep == "off" else "on")
        self.b_repeat.setIcon(style.icon({"off": "mdi6.repeat-off", "all": "mdi6.repeat",
                                          "one": "mdi6.repeat-once"}[rep], "#ffffff"))
        self.b_repeat.setToolTip(t("repeat_" + rep) + " (R)")
        for b in (self.b_shuffle, self.b_repeat):
            b.style().unpolish(b)
            b.style().polish(b)

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
        self._show_track(tr)
        self._dirty = True

    def _show_track(self, tr: Track | None):
        if tr is None:
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

    def _update_next_label(self):
        cur = self.engine.cur
        if cur is not None and not self.engine.stopped and self.pl.stop_after == cur.uid:
            self.t_next.setText(t("up_next_stop"))
            return
        nxt = self.pl.next_after(cur, auto=True) if cur is not None and not self.engine.stopped else None
        self.t_next.setText(t("up_next", nxt.display()) if nxt is not None and nxt.uid != cur.uid else
                            (t("up_next_repeat") if nxt is not None else ""))

    def _on_pos(self, pos: float, dur: float):
        self._last_pos = (pos, dur)
        cur = self.engine.cur
        if cur is not None and dur and not cur.duration():          # DTS / TrueHD: mutagen does not know the length
            cur.length = cur.start + dur
            self._refresh_item(cur.uid)
            self.dirty_timer.start()
        self.seekbar.set_state(pos, dur)
        self.l_pos.setText(fmt_time(pos))
        self.l_dur.setText("−" + fmt_time(max(0.0, dur - pos)) if self.cfg.get("time_remaining") and dur
                           else fmt_time(dur))
        if self.mini is not None and self.mini.isVisible():
            self.mini.seek.set_state(pos, dur)
            self.mini.time.setText(f"{fmt_time(pos)} / {fmt_time(dur)}")

    def _on_paused(self, paused: bool):
        icon = "fa6s.play" if paused else "fa6s.pause"
        self.b_play.setIcon(style.icon(icon, "#ffffff"))
        self.b_play.setToolTip((t("play") if paused else t("pause")) + " (Space)")
        if self.mini is not None:
            self.mini.b_play.setIcon(style.icon(icon, "#ffffff"))
        if self.engine.cur is not None:
            self._refresh_item(self.engine.cur.uid)
        self._thumb_update()
        self._update_next_label()

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

    def _on_finished(self):
        if self.pl.stop_after is not None:
            self.pl.stop_after = None
            self.toast.show_text(t("stopped_after"), 2000)
        if self.engine.cur is not None:
            self._refresh_item(self.engine.cur.uid)
        self._update_next_label()
        self._thumb_update()

    # ── stop after, sleep timer, time label ───────────────────
    def set_stop_after(self, uid: int | None):
        self.pl.stop_after = uid
        self.engine.requeue()
        self._update_next_label()
        tr = self.pl.by_uid(uid) if uid is not None else None
        self.toast.show_text(t("stop_after_on", tr.display_title()) if tr else t("stop_after_off"), 1600)

    def toggle_stop_after(self):
        cur = self.engine.cur
        if cur is None:
            return
        self.set_stop_after(None if self.pl.stop_after == cur.uid else cur.uid)

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
        m.addAction(style.icon("fa6s.folder-open"), t("load_pl") + "\tCtrl+L", self.load_playlist_dialog)
        m.addAction(style.icon("fa6s.floppy-disk"), t("save_pl") + "\tCtrl+S", self.save_playlist_dialog)
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
        a.setChecked(cur is not None and self.pl.stop_after == cur.uid)
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
        if self.mini is None:
            self.mini = MiniWindow(self)
        if self.mini.isVisible():
            self.cfg["mini_geometry"] = [self.mini.x(), self.mini.y()]
            self.mini.hide()
            self.show()
            self.raise_()
            self.activateWindow()
            return
        self._set_mini(self.engine.cur)
        self.mini.b_play.setIcon(style.icon("fa6s.play" if self.engine.paused else "fa6s.pause", "#ffffff"))
        pos, dur = self._last_pos
        self.mini.seek.set_state(pos, dur)
        self.mini.time.setText(f"{fmt_time(pos)} / {fmt_time(dur)}")
        geo = self.cfg.get("mini_geometry") or []
        if len(geo) >= 2:
            self.mini.move(int(geo[0]), int(geo[1]))
        else:
            scr = self.screen().availableGeometry()
            self.mini.move(scr.right() - self.mini.width() - 24, scr.bottom() - self.mini.height() - 24)
        self.hide()
        self.mini.show()
        winint.dark_title_bar(int(self.mini.winId()))

    def _set_mini(self, tr: Track | None):
        if self.mini is None:
            return
        if tr is None:
            elide(self.mini.title, APP_TITLE, 300)
            self.mini.artist.setText("")
            self.mini.cover.set_image(None)
            return
        elide(self.mini.title, tr.display_title(), 300)
        elide(self.mini.artist, tr.artist or tr.album, 300)
        self.mini.cover.set_image(getattr(self, "_cover_data", b"") or None)

    # ── session ───────────────────────────────────────────────
    def save_session(self):
        cur = self.engine.cur
        pos, _ = self._last_pos
        s = {"tracks": [tr.to_dict() for tr in self.pl.tracks],
             "current": self.pl.index_of(cur),
             "position": round(pos, 1) if cur is not None and not self.engine.stopped else 0.0,
             "playing": cur is not None and not self.engine.stopped and not self.engine.paused}
        config.save_session(s)
        self._dirty = False

    def restore_session(self) -> bool:
        if not self.cfg.get("resume", True):
            return False
        s = config.load_session()
        tracks = [Track.from_dict(d) for d in s.get("tracks", []) if isinstance(d, dict) and d.get("path")]
        if not tracks:
            return False
        self.pl.add(tracks)
        if self.pl.shuffle:
            i = int(s.get("current", -1))
            self.pl.reshuffle(tracks[i] if 0 <= i < len(tracks) else None)
        self.tags.add(tracks)
        self._rebuild_list()
        i = int(s.get("current", -1))
        if 0 <= i < len(tracks) and os.path.exists(tracks[i].path):
            play = bool(self.cfg.get("resume_play")) and bool(s.get("playing"))
            self.engine.play(tracks[i], float(s.get("position", 0) or 0), paused=not play)
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
