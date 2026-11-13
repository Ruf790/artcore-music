"""Settings, sound, speaker test, equalizer, keyboard shortcuts, update."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSlider,
                               QSpinBox, QTabWidget, QTextBrowser, QVBoxLayout, QWidget, QLineEdit)

from . import APP_TITLE, VERSION, audio, style
from .i18n import t


def _buttons(dlg, ok=True):
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel if ok else QDialogButtonBox.Close)
    for b in bb.buttons():
        b.setIcon(QIcon())                     # Fusion puts odd stock icons on these
    if ok:
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    return bb


def _head(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setStyleSheet("font-size: 14pt; font-weight: 700; padding-bottom: 6px;")
    return lab


def _hint(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("hint")
    lab.setWordWrap(True)
    return lab


class SettingsDialog(QDialog):
    """General / playlist / controls. Sound has its own dialog (Ctrl+P)."""
    CHECKS = {
        "general":  [("grp_start", ("resume", "resume_play", "single_window", "check_updates")),
                     ("grp_window", ("on_top", "media_keys", "tray", "close_to_tray", "notify"))],
        "playlist": [("grp_search", ("search_path", "search_clear_on_play")),
                     ("tab_playlist", ("follow_playing", "skip_dups", "confirm_clear"))],
        "playback": [("grp_look", ("waveform", "time_remaining", "lyrics"))],
    }

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle(t("settings") + " — " + APP_TITLE)
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.addWidget(_head(t("settings")))
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        self.checks: dict[str, QCheckBox] = {}

        # general
        g = self._page("tab_general")
        form = QFormLayout()
        self.lang = QComboBox()
        self.lang.addItem("Русский", "ru")
        self.lang.addItem("English", "en")
        self.lang.setCurrentIndex(0 if cfg.get("language") == "ru" else 1)
        form.addRow(t("language"), self.lang)
        g.addLayout(form)
        self._groups(g, "general")
        self.checks["resume_play"].setEnabled(self.checks["resume"].isChecked())
        self.checks["resume"].toggled.connect(self.checks["resume_play"].setEnabled)
        for k in ("close_to_tray", "notify"):
            self.checks[k].setEnabled(self.checks["tray"].isChecked())
            self.checks["tray"].toggled.connect(self.checks[k].setEnabled)
        g.addWidget(_hint(t("lang_restart")))
        from . import config
        g.addWidget(_hint(t("data_in", config.data_dir())))
        g.addStretch(1)

        # playlist
        p = self._page("tab_playlist")
        self._groups(p, "playlist")
        box = QGroupBox(t("grp_look"))
        f = QFormLayout(box)
        self.rows = QComboBox()
        for key in ("compact", "normal", "large"):
            self.rows.addItem(t("row_" + key), key)
        self.rows.setCurrentIndex(max(0, self.rows.findData(cfg.get("row_size", "normal"))))
        f.addRow(t("row_size"), self.rows)
        cols = QHBoxLayout()
        self.cols: dict[str, QCheckBox] = {}
        hidden = set(cfg.get("hidden_cols") or [])
        for key, name in (("n", "#"), ("artist", t("col_artist")), ("album", t("col_album")), ("len", t("col_len")),
                          ("fav", "★")):
            cb = QCheckBox(name)
            cb.setChecked(key not in hidden)
            self.cols[key] = cb
            cols.addWidget(cb)
        cols.addStretch(1)
        f.addRow(t("show_cols"), cols)
        p.addWidget(box)
        p.addStretch(1)

        # controls
        c = self._page("tab_playback")
        box = QGroupBox(t("grp_steps"))
        f = QFormLayout(box)
        f.setVerticalSpacing(9)
        self.spins: dict[str, QSpinBox] = {}
        for key, lo, hi, suffix in (("seek_step", 1, 60, t("sec")), ("seek_step_big", 5, 600, t("sec")),
                                    ("volume_step", 1, 20, "%"), ("prev_restart", 0, 30, t("sec"))):
            sp = QSpinBox()
            sp.setRange(lo, hi)
            sp.setSuffix(" " + suffix)
            sp.setValue(int(cfg.get(key, lo)))
            if key == "prev_restart":
                sp.setSpecialValueText(t("prev_always"))
            self.spins[key] = sp
            f.addRow(t(key), sp)
        f.addRow("", _hint(t("prev_hint")))
        c.addWidget(box)
        self._groups(c, "playback")
        c.addStretch(1)
        lay.addWidget(_buttons(self))

    def _page(self, title_key: str) -> QVBoxLayout:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 12)
        v.setSpacing(10)
        self.tabs.addTab(w, t(title_key))
        return v

    def _groups(self, lay: QVBoxLayout, page: str):
        for title, keys in self.CHECKS[page]:
            box = QGroupBox(t(title))
            v = QVBoxLayout(box)
            v.setSpacing(6)
            for key in keys:
                cb = QCheckBox(t("opt_" + key))
                cb.setChecked(bool(self.cfg.get(key)))
                self.checks[key] = cb
                v.addWidget(cb)
            lay.addWidget(box)

    def accept(self):
        self.cfg["language"] = self.lang.currentData()
        for k, cb in self.checks.items():
            self.cfg[k] = cb.isChecked()
        self.cfg["row_size"] = self.rows.currentData()
        self.cfg["hidden_cols"] = [k for k, cb in self.cols.items() if not cb.isChecked()]
        for k, sp in self.spins.items():
            self.cfg[k] = int(sp.value())
        super().accept()


class _DbSlider(QHBoxLayout):
    """−12 … +12 dB in 0.5 dB steps, with a value label."""
    moved = None

    def __init__(self, value: float, on_change):
        super().__init__()
        self.sl = QSlider(Qt.Horizontal)
        self.sl.setRange(-24, 24)
        self.sl.setValue(int(round(float(value) * 2)))
        self.sl.setMinimumWidth(220)
        self.lab = QLabel()
        self.lab.setMinimumWidth(64)
        self.addWidget(self.sl, 1)
        self.addWidget(self.lab)
        self.reset = QPushButton("0")
        self.reset.setFixedWidth(40)
        self.reset.setToolTip(t("reset"))
        self.reset.clicked.connect(lambda: self.sl.setValue(0))
        self.addWidget(self.reset)
        self._cb = on_change
        self.sl.valueChanged.connect(self._ch)
        self._ch(self.sl.value(), notify=False)

    def value(self) -> float:
        return self.sl.value() / 2.0

    def set_value(self, v: float):
        self.sl.setValue(int(round(v * 2)))

    def _ch(self, v, notify=True):
        db = v / 2.0
        self.lab.setText(f"{db:+.1f} dB" if db else "0 dB")
        if notify:
            self._cb(db)


class SoundDialog(QDialog):
    """Output channels, centre / subwoofer, upmix, ReplayGain, crossfade, device. Changes are heard at once;
    Cancel puts the old values back (restore → changed)."""
    changed = Signal(bool)             # True: options that need the output reopened (layout, device, RG)
    speaker_test = Signal()

    KEYS = ("channels", "upmix", "center_db", "lfe_db", "replaygain", "rg_preamp", "rg_clip", "crossfade",
            "xfade_album", "audio_device", "audio_exclusive", "samplerate", "fade_pause")
    REOPEN = ("channels", "audio_device", "replaygain", "rg_preamp", "rg_clip", "audio_exclusive", "samplerate")
    RATES = (0, 44100, 48000, 88200, 96000, 176400, 192000)

    def __init__(self, cfg: dict, devices: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.saved = {k: cfg.get(k) for k in self.KEYS}
        self.setWindowTitle(t("sound") + " — " + APP_TITLE)
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.addWidget(_head(t("sound")))

        g1 = QGroupBox(t("grp_output"))
        f1 = QFormLayout(g1)
        f1.setVerticalSpacing(9)
        self.dev = QComboBox()
        self.dev.addItem(t("dev_default"), "auto")
        for name, desc in devices:
            if name and name != "auto":
                self.dev.addItem(desc or name, name)
        i = self.dev.findData(cfg.get("audio_device") or "auto")
        self.dev.setCurrentIndex(max(0, i))
        f1.addRow(t("device"), self.dev)
        self.ch = QComboBox()
        for key in ("auto", "5.1", "stereo"):
            self.ch.addItem(t("ch_" + key.replace(".", "")), key)
        self.ch.setCurrentIndex(max(0, self.ch.findData(cfg.get("channels", "auto"))))
        f1.addRow(t("channels"), self.ch)
        self.sr = QComboBox()
        for r in self.RATES:
            self.sr.addItem(t("sr_auto") if not r else f"{audio.rate_label(r)} {t('khz')}", r)
        self.sr.setCurrentIndex(max(0, self.sr.findData(int(cfg.get("samplerate", 0) or 0))))
        f1.addRow(t("samplerate"), self.sr)
        f1.addRow("", _hint(t("sr_hint")))
        self.excl = QCheckBox(t("exclusive"))
        self.excl.setChecked(bool(cfg.get("audio_exclusive")))
        f1.addRow("", self.excl)
        f1.addRow("", _hint(t("exclusive_hint")))
        self.upmix = QCheckBox(t("upmix"))
        self.upmix.setChecked(bool(cfg.get("upmix")))
        f1.addRow("", self.upmix)
        f1.addRow("", _hint(t("upmix_hint")))
        self.center = _DbSlider(cfg.get("center_db", 0), lambda v: self._set("center_db", v, False))
        f1.addRow(t("center"), self.center)
        self.lfe = _DbSlider(cfg.get("lfe_db", 0), lambda v: self._set("lfe_db", v, False))
        f1.addRow(t("lfe"), self.lfe)
        test = QPushButton(style.icon("fa6s.volume-high"), "  " + t("speaker_test"))
        test.clicked.connect(self.speaker_test.emit)
        f1.addRow("", test)
        lay.addWidget(g1)

        g2 = QGroupBox(t("grp_playback"))
        f2 = QFormLayout(g2)
        f2.setVerticalSpacing(9)
        self.rg = QComboBox()
        for key in ("album", "track", "off"):
            self.rg.addItem(t("rg_" + key), key)
        self.rg.setCurrentIndex(max(0, self.rg.findData(cfg.get("replaygain", "album"))))
        f2.addRow("ReplayGain", self.rg)
        self.pre = QDoubleSpinBox()
        self.pre.setRange(-15, 15)
        self.pre.setSingleStep(0.5)
        self.pre.setSuffix(" dB")
        self.pre.setValue(float(cfg.get("rg_preamp", 0)))
        f2.addRow(t("rg_preamp"), self.pre)
        self.clip = QCheckBox(t("rg_clip"))
        self.clip.setChecked(bool(cfg.get("rg_clip", True)))
        f2.addRow("", self.clip)
        self.xf = QSpinBox()
        self.xf.setRange(0, 12)
        self.xf.setSuffix(" " + t("sec"))
        self.xf.setSpecialValueText(t("xf_off"))
        self.xf.setValue(int(cfg.get("crossfade", 0)))
        f2.addRow(t("crossfade"), self.xf)
        self.xfa = QCheckBox(t("xfade_album"))
        self.xfa.setChecked(bool(cfg.get("xfade_album", True)))
        f2.addRow("", self.xfa)
        self.fp = QSpinBox()
        self.fp.setRange(0, 2000)
        self.fp.setSingleStep(50)
        self.fp.setSuffix(" " + t("ms"))
        self.fp.setSpecialValueText(t("xf_off"))
        self.fp.setValue(int(cfg.get("fade_pause", 0) or 0))
        f2.addRow("", _hint(t("gapless_hint")))
        f2.addRow(t("fade_pause"), self.fp)
        lay.addWidget(g2)
        lay.addWidget(_buttons(self))

        self.dev.currentIndexChanged.connect(lambda _i: self._set("audio_device", self.dev.currentData(), True))
        self.ch.currentIndexChanged.connect(lambda _i: self._set("channels", self.ch.currentData(), True))
        self.upmix.toggled.connect(lambda v: self._set("upmix", v, False))
        self.rg.currentIndexChanged.connect(lambda _i: self._set("replaygain", self.rg.currentData(), True))
        self.pre.valueChanged.connect(lambda v: self._set("rg_preamp", float(v), True))
        self.clip.toggled.connect(lambda v: self._set("rg_clip", v, True))
        self.xf.valueChanged.connect(lambda v: self._set("crossfade", int(v), False))
        self.xfa.toggled.connect(lambda v: self._set("xfade_album", v, False))
        self.sr.currentIndexChanged.connect(lambda _i: self._set("samplerate", int(self.sr.currentData()), True))
        self.excl.toggled.connect(lambda v: self._set("audio_exclusive", v, True))
        self.fp.valueChanged.connect(lambda v: self._set("fade_pause", int(v), False))

    def set_levels(self, center: float, lfe: float):
        """The speaker test moved them."""
        self.center.set_value(center)
        self.lfe.set_value(lfe)

    def _set(self, key, value, reopen):
        if self.cfg.get(key) == value:
            return
        self.cfg[key] = value
        self.changed.emit(reopen)

    def reject(self):
        reopen = any(self.cfg.get(k) != self.saved[k] for k in self.REOPEN)
        self.cfg.update(self.saved)
        self.changed.emit(reopen)
        super().reject()


class SpeakerTestDialog(QDialog):
    """Pink noise speaker by speaker (FL → FC → FR → BR → BL → SUB), always as 6-channel PCM, through the same
    centre / subwoofer levels as the music. Click a speaker to hear only it."""
    levels_changed = Signal(float, float)

    def __init__(self, mpvmod, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.mpvmod = mpvmod
        self.setWindowTitle(t("speaker_test") + " — " + APP_TITLE)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.addWidget(_head(t("speaker_test")))
        lay.addWidget(_hint(t("test_hint")))
        from .widgets import SpeakerMap
        labels = {k: t("spk_" + k) for k in ("FL", "FC", "FR", "BL", "BR", "LFE")}
        labels["you"] = t("spk_you")
        self.map = SpeakerMap(labels)
        self.map.picked.connect(self.play_one)
        lay.addWidget(self.map, 1)
        self.now = QLabel(" ")
        self.now.setAlignment(Qt.AlignCenter)
        self.now.setStyleSheet("font-size: 12pt; font-weight: 600;")
        lay.addWidget(self.now)
        form = QFormLayout()
        self.center = _DbSlider(cfg.get("center_db", 0), lambda v: self._levels())
        self.lfe = _DbSlider(cfg.get("lfe_db", 0), lambda v: self._levels())
        form.addRow(t("center"), self.center)
        form.addRow(t("lfe"), self.lfe)
        lay.addLayout(form)
        row = QHBoxLayout()
        self.auto = QPushButton(style.icon("fa6s.rotate", "#ffffff"), "  " + t("test_cycle"))
        self.auto.setObjectName("primary")
        self.auto.clicked.connect(self.toggle_cycle)
        row.addWidget(self.auto)
        stop = QPushButton(style.icon("fa6s.stop"), "  " + t("stop"))
        stop.clicked.connect(self.stop)
        row.addWidget(stop)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(_buttons(self, ok=False))
        self.m = None
        self.cycle = False
        self.i = 0
        self.timer = QTimer(self)
        self.timer.setInterval(2400)
        self.timer.timeout.connect(self._next)
        self.error = ""
        try:
            opts = dict(vo="null", vid="no", idle="yes", keep_open="no", config=False, terminal=False,
                        input_default_bindings=False, osc=False, ytdl=False, load_scripts=False,
                        audio_channels="5.1", volume=100, audio_client_name="ArtCore Music test",
                        replaygain="no", loop_file="inf")
            ao = os.environ.get("ARTCORE_MUSIC_AO")
            if ao:
                opts["ao"] = ao
            if (cfg.get("audio_device") or "auto") != "auto":
                opts["audio_device"] = cfg["audio_device"]
            self.m = mpvmod.MPV(**opts)
        except Exception as e:
            self.error = str(e)
            self.now.setText(t("test_fail", e))

    def _af(self) -> str:
        return audio.levels_filter(6, "5.1", self.center.value(), self.lfe.value())

    def _levels(self):
        self.cfg["center_db"] = self.center.value()
        self.cfg["lfe_db"] = self.lfe.value()
        if self.m is not None:
            try:
                self.m.af = self._af()
            except Exception:
                pass
        self.levels_changed.emit(self.center.value(), self.lfe.value())

    def play_one(self, name: str, keep_cycle: bool = False):
        if not keep_cycle:
            self.cycle = False
            self.timer.stop()
            self.auto.setText("  " + t("test_cycle"))
        if self.m is None:
            return
        from . import testtone
        try:
            path = testtone.signal_file(name)
            self.m.af = self._af()
            self.m.loop_file = "no" if keep_cycle else "inf"
            self.m.play(path)
            self.m.pause = False
        except Exception as e:
            self.now.setText(t("test_fail", e))
            return
        self.map.set_active(name)
        self.now.setText(t("test_now", t("spk_" + name)))

    def toggle_cycle(self):
        if self.cycle:
            self.stop()
            return
        self.cycle = True
        self.auto.setText("  " + t("test_pause"))
        self.i = 0
        self._next()
        self.timer.start()

    def _next(self):
        from . import testtone
        name = testtone.SEQUENCE[self.i % len(testtone.SEQUENCE)]
        self.i += 1
        self.play_one(name, keep_cycle=True)

    def stop(self):
        self.cycle = False
        self.timer.stop()
        self.auto.setText("  " + t("test_cycle"))
        self.map.set_active("")
        self.now.setText(" ")
        if self.m is not None:
            try:
                self.m.command("stop")
            except Exception:
                pass

    def done(self, r):
        self.timer.stop()
        if self.m is not None:
            try:
                self.m.terminate()
            except Exception:
                pass
            self.m = None
        super().done(r)


KEYS = [
    ("Space", "k_play"), ("Enter", "k_play_sel"), ("← / →", "k_seek5"), ("Shift + ← / →", "k_seek30"),
    ("Ctrl + ← / →", "k_prevnext"), ("Ctrl + ↑ / ↓,  + / −", "k_volume"), ("M", "k_mute"), ("S", "k_shuffle"),
    ("R", "k_repeat"), ("E", "k_eq"), ("Ctrl + P", "k_sound"), ("Ctrl + T", "k_test"), ("Ctrl + M", "k_mini"),
    ("T", "k_ontop"), ("Ctrl + F", "k_find"), ("Ctrl + J", "k_jump"), ("Ctrl + Shift + E", "k_stop_after"), ("Del", "k_delete"),
    ("Ctrl + O", "k_open"), ("Ctrl + Shift + O", "k_open_folder"), ("Ctrl + U", "k_url"),
    ("Ctrl + N / W / Tab", "k_tabs"), ("Ctrl + Q / Shift + Q", "k_queue"), ("Ctrl + D", "k_fav"),
    ("Ctrl + B / H", "k_library"), ("F2", "k_tags"), ("L", "k_lyrics"), ("Ctrl + L", "k_load_pl"),
    ("Ctrl + S", "k_save_pl"), ("Ctrl + ,", "k_settings"), ("⏮ ⏯ ⏭ ⏹", "k_media"), ("F1", "k_keys"),
]


class KeysDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("keys") + " — " + APP_TITLE)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.addWidget(_head(t("keys")))
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        half = (len(KEYS) + 1) // 2
        for i, (key, desc) in enumerate(KEYS):
            k = QLabel(key)
            k.setStyleSheet(f"background: {style.PANEL2}; border: 1px solid {style.BORDER}; border-radius: 6px;"
                            " padding: 3px 8px; font-weight: 600;")
            d = QLabel(t(desc))
            col = 0 if i < half else 2
            r = i if i < half else i - half
            grid.addWidget(k, r, col, Qt.AlignLeft)
            grid.addWidget(d, r, col + 1)
        lay.addLayout(grid)
        lay.addWidget(_buttons(self, ok=False))


class EqualizerDialog(QDialog):
    """10 bands ±12 dB with presets; every move is heard at once (changed → apply_audio)."""
    changed = Signal()

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.saved = (list(cfg.get("eq", [0] * 10)), cfg.get("eq_preset", "flat"))
        self.setWindowTitle(t("equalizer") + " — " + APP_TITLE)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.addWidget(_head(t("equalizer")))
        top = QHBoxLayout()
        top.addWidget(QLabel(t("eq_preset")))
        self.preset = QComboBox()
        for key in audio.PRESETS:
            self.preset.addItem(t("eqp_" + key), key)
        self.preset.addItem(t("eqp_custom"), "custom")
        top.addWidget(self.preset, 1)
        reset = QPushButton(t("reset"))
        reset.clicked.connect(lambda: self._load(audio.PRESETS["flat"], "flat"))
        top.addWidget(reset)
        lay.addLayout(top)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        self.sliders: list[QSlider] = []
        self.vals: list[QLabel] = []
        for i, f in enumerate(audio.BANDS):
            v = QLabel("0")
            v.setAlignment(Qt.AlignCenter)
            v.setStyleSheet(f"color: {style.MUTED}; font-size: 8.5pt;")
            sl = QSlider(Qt.Vertical)
            sl.setRange(-12, 12)
            sl.setFixedHeight(170)
            sl.setTickPosition(QSlider.TicksBothSides)
            sl.setTickInterval(6)
            sl.valueChanged.connect(lambda _v, i=i: self._moved(i))
            lab = QLabel(f"{f // 1000}k" if f >= 1000 else str(f))
            lab.setAlignment(Qt.AlignCenter)
            grid.addWidget(v, 0, i, Qt.AlignHCenter)
            grid.addWidget(sl, 1, i, Qt.AlignHCenter)
            grid.addWidget(lab, 2, i, Qt.AlignHCenter)
            self.sliders.append(sl)
            self.vals.append(v)
        lay.addLayout(grid)
        lay.addWidget(_hint(t("eq_hint")))
        lay.addWidget(_buttons(self))
        self._loading = False
        gains = [int(g) for g in cfg.get("eq", [0] * 10)]
        self._load(gains, next((k for k, v in audio.PRESETS.items() if list(v) == gains), "custom"))
        self.preset.currentIndexChanged.connect(self._pick)

    def _load(self, gains, preset: str):
        self._loading = True
        for sl, g in zip(self.sliders, gains):
            sl.setValue(int(g))
        self.preset.setCurrentIndex(max(0, self.preset.findData(preset)))
        self._loading = False
        self._store(preset)

    def _pick(self, _i):
        key = self.preset.currentData()
        if key in audio.PRESETS and not self._loading:
            self._load(audio.PRESETS[key], key)

    def _moved(self, i: int):
        self.vals[i].setText(f"{self.sliders[i].value():+d}" if self.sliders[i].value() else "0")
        if self._loading:
            return
        gains = [sl.value() for sl in self.sliders]
        match = next((k for k, v in audio.PRESETS.items() if list(v) == gains), "custom")
        self._loading = True
        self.preset.setCurrentIndex(self.preset.findData(match))
        self._loading = False
        self._store(match)

    def _store(self, preset: str):
        for i, sl in enumerate(self.sliders):
            self.vals[i].setText(f"{sl.value():+d}" if sl.value() else "0")
        self.cfg["eq"] = [sl.value() for sl in self.sliders]
        self.cfg["eq_preset"] = preset
        self.changed.emit()

    def reject(self):
        self.cfg["eq"], self.cfg["eq_preset"] = self.saved
        self.changed.emit()
        super().reject()


class UpdateDialog(QDialog):
    """Release notes + download and silent install of the new Setup.exe."""
    progress = Signal(int, int)
    done_ = Signal(str, str)               # path, error

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        from . import updater
        self.info, self.updater, self.path = info, updater, ""
        self.setWindowTitle(t("upd_title"))
        self.resize(600, 440)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.addWidget(_head(t("upd_available", info["version"])))
        sub = QLabel(t("upd_text", info["version"], VERSION))
        sub.setStyleSheet(f"color: {style.MUTED};")
        lay.addWidget(sub)
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setMarkdown(info.get("notes") or "")
        notes.setStyleSheet(f"background: {style.PANEL}; border: 1px solid {style.BORDER}; border-radius: 8px; padding: 6px;")
        lay.addWidget(notes, 1)
        self.bar = QProgressBar()
        self.bar.hide()
        lay.addWidget(self.bar)
        lay.addWidget(_hint(t("upd_restart")))
        bb = QDialogButtonBox()
        self.go = bb.addButton(t("upd_install"), QDialogButtonBox.AcceptRole)
        self.go.setObjectName("primary")
        bb.addButton(t("upd_later"), QDialogButtonBox.RejectRole)
        bb.accepted.connect(self._go)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.progress.connect(self._on_progress)
        self.done_.connect(self._on_done)

    def _go(self):
        import threading
        self.go.setEnabled(False)
        self.bar.setRange(0, max(1, self.info.get("size", 0)))
        self.bar.show()

        def work():
            try:
                p = self.updater.download(self.info["url"], self.info.get("size", 0),
                                          lambda d, n: self.progress.emit(d, n))
                self.done_.emit(p, "")
            except Exception as e:
                self.done_.emit("", str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_progress(self, d: int, n: int):
        if n:
            self.bar.setMaximum(n)
        self.bar.setValue(min(d, self.bar.maximum()))
        self.bar.setFormat(t("upd_downloading", f"{d / 1048576:.1f}", f"{(n or d) / 1048576:.1f}"))

    def _on_done(self, path: str, err: str):
        from PySide6.QtWidgets import QMessageBox
        if err:
            self.go.setEnabled(True)
            QMessageBox.warning(self, t("upd_title"), t("upd_error", err))
            return
        self.path = path
        self.accept()


class TagEditorDialog(QDialog):
    """Tags of one or many files. With many: a field shows the common value, or stays empty with «different»
    and is written only if you type in it. «From the file name» fills the tags of every file from its name;
    «Number in order» numbers the files 1, 2, 3… in the order of the list."""
    FIELDS = ("title", "artist", "album", "albumartist", "year", "track", "genre")

    def __init__(self, tracks: list, parent=None):
        super().__init__(parent)
        from . import meta
        self.tracks = tracks
        self.changed: list = []
        self.errors: list[str] = []
        self.guess: dict[int, dict] = {}            # uid → tags from the file name
        self.setWindowTitle(t("edit_tags").rstrip("…") + " — " + APP_TITLE)
        self.setMinimumWidth(580)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.addWidget(_head(t("edit_tags").rstrip("…")))
        many = len(tracks) > 1
        what = QLabel(t("tags_files", len(tracks)) if many else tracks[0].path)
        what.setObjectName("hint")
        what.setWordWrap(True)
        what.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(what)
        self.cur = {}
        for tr in tracks:
            try:
                tg = meta.read(tr.path)
            except Exception:
                tg = meta.Tags()
            self.cur[tr.uid] = {f: getattr(tg, f if f != "track" else "track") or "" for f in self.FIELDS}
        form = QFormLayout()
        form.setVerticalSpacing(8)
        self.edits: dict[str, QLineEdit] = {}
        self.touched: set[str] = set()
        for f in self.FIELDS:
            e = QLineEdit()
            vals = {self.cur[tr.uid][f] for tr in tracks}
            if len(vals) == 1:
                e.setText(vals.pop())
            else:
                e.setPlaceholderText(t("tags_different"))
            if f in ("year", "track"):
                e.setMaximumWidth(120)
            e.textEdited.connect(lambda _s, k=f: self.touched.add(k))
            self.edits[f] = e
            form.addRow(t("tag_" + f), e)
        lay.addLayout(form)

        box = QGroupBox(t("tags_from_name"))
        h = QHBoxLayout(box)
        self.pattern = QComboBox()
        for key in meta.FILENAME_PATTERNS:
            self.pattern.addItem(t("pat_" + key), key)
        h.addWidget(self.pattern, 1)
        b = QPushButton(t("tags_fill"))
        b.clicked.connect(self._from_name)
        h.addWidget(b)
        lay.addWidget(box)
        self.number = QCheckBox(t("tags_number"))
        self.number.setVisible(many)
        lay.addWidget(self.number)
        self.preview = QLabel()
        self.preview.setObjectName("hint")
        self.preview.setWordWrap(True)
        lay.addWidget(self.preview)
        lay.addWidget(_hint(t("tags_hint")))
        lay.addWidget(_buttons(self))

    def _from_name(self):
        from . import meta
        key = self.pattern.currentData()
        self.guess = {}
        for tr in self.tracks:
            g = meta.from_filename(tr.path, key)
            if g:
                self.guess[tr.uid] = g
        n = len(self.guess)
        if len(self.tracks) == 1 and self.guess:
            for f, v in self.guess[self.tracks[0].uid].items():
                self.edits[f].setText(v)
                self.touched.add(f)
            self.guess = {}
        first = next(iter(self.guess.values()), None)
        sample = " · ".join(f"{t('tag_' + k)}: {v}" for k, v in first.items()) if first else ""
        self.preview.setText(t("tags_guessed", n, len(self.tracks)) + (f"\n{sample}" if sample else ""))

    def values_for(self, i: int, tr) -> dict:
        vals = dict(self.guess.get(tr.uid, {}))
        for f in self.touched:
            vals[f] = self.edits[f].text()
        if self.number.isChecked():
            vals["track"] = str(i + 1)
        return vals

    def accept(self):
        from . import meta
        from .playlist import fill_tags
        for i, tr in enumerate(self.tracks):
            vals = self.values_for(i, tr)
            vals = {k: v for k, v in vals.items() if v != self.cur[tr.uid].get(k, "")}
            if not vals:
                continue
            try:
                meta.write(tr.path, vals)
            except Exception as e:
                self.errors.append(f"{os.path.basename(tr.path)}: {e}")
                continue
            tr.tagged = False
            try:
                fill_tags(tr)
            except Exception:
                tr.tagged = True
            self.changed.append(tr)
        super().accept()
