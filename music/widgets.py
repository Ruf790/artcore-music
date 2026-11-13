"""Small widgets: seek bar, cover, toast, speaker map, the playlist view."""
from __future__ import annotations

import os

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient)
from PySide6.QtWidgets import (QAbstractItemView, QLabel, QListWidget, QListWidgetItem, QToolButton,
                               QTreeWidget, QWidget)

from . import style


def fmt_time(sec: float | None) -> str:
    if sec is None or sec < 0:
        sec = 0
    s = int(sec)
    h, m, s = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def ctl_button(icon_name: str, tip: str, size: int = 20, slot=None, obj: str = "ctl") -> QToolButton:
    b = QToolButton()
    b.setObjectName(obj)
    b.setIcon(style.icon(icon_name, "#ffffff"))
    b.setIconSize(QSize(size, size))
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.setFocusPolicy(Qt.NoFocus)
    if slot:
        b.clicked.connect(slot)
    return b


class SeekBar(QWidget):
    """Thin bar, grows on hover; click / drag to seek; shows the time under the mouse."""
    seek = Signal(float)

    def __init__(self, parent=None, thin: bool = False):
        super().__init__(parent)
        self.pos_ = 0.0
        self.dur = 0.0
        self.hover = -1.0
        self.drag = False
        self.thin = thin
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(10 if thin else 18)

    def set_state(self, pos: float, dur: float):
        if self.drag:
            return
        self.pos_, self.dur = pos, dur
        self.update()

    def _sec_at(self, x: float) -> float:
        return max(0.0, min(1.0, x / max(1, self.width()))) * self.dur

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = 4 if self.thin else (6 if self.hover >= 0 or self.drag else 4)
        y = (self.height() - h) / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 45))
        p.drawRoundedRect(QRectF(0, y, self.width(), h), h / 2, h / 2)
        frac = self.pos_ / self.dur if self.dur else 0
        if frac > 0:
            g = QLinearGradient(0, 0, self.width(), 0)
            g.setColorAt(0, QColor(style.ACCENT))
            g.setColorAt(1, QColor(style.ACCENT2))
            p.setBrush(g)
            p.drawRoundedRect(QRectF(0, y, self.width() * frac, h), h / 2, h / 2)
        if (self.hover >= 0 or self.drag) and self.dur:
            x = self.width() * frac
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(x, self.height() / 2), 6, 6)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.dur:
            self.drag = True
            self.pos_ = self._sec_at(e.position().x())
            self.update()

    def mouseMoveEvent(self, e):
        self.hover = e.position().x()
        if self.dur:
            self.setToolTip(fmt_time(self._sec_at(self.hover)))
        if self.drag:
            self.pos_ = self._sec_at(e.position().x())
        self.update()

    def mouseReleaseEvent(self, e):
        if self.drag:
            self.drag = False
            self.seek.emit(self._sec_at(e.position().x()))
            self.update()

    def leaveEvent(self, _):
        self.hover = -1
        self.update()


class WaveSeekBar(SeekBar):
    """The seek bar as a waveform: bars above a base line, their dim reflection below; played = bright,
    hover = a lighter preview up to the mouse, a thin line at the position. Without a waveform (still being
    read, a stream) it is the plain bar."""
    HEIGHT = 58
    BAR, GAP = 2, 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.peaks: bytes = b""
        self.loading = False
        self.enabled_wave = True
        self._bars: list[float] = []
        self._bars_w = -1
        self.setFixedHeight(self.HEIGHT)

    def set_wave_enabled(self, on: bool):
        self.enabled_wave = on
        self.update()

    def set_peaks(self, peaks: bytes | None, loading: bool = False):
        self.peaks = peaks or b""
        self.loading = loading and not self.peaks
        self._bars_w = -1
        self.update()

    def _bar_values(self, n: int) -> list[float]:
        if self._bars_w == n:
            return self._bars
        src = self.peaks
        out = []
        for i in range(n):
            a = int(i * len(src) / n)
            b = max(a + 1, int((i + 1) * len(src) / n))
            out.append(max(src[a:b]) / 255.0)
        self._bars, self._bars_w = out, n
        return out

    def paintEvent(self, e):
        if not self.enabled_wave or not (self.peaks or self.loading):
            return super().paintEvent(e)
        p = QPainter(self)
        w, h = self.width(), self.height()
        base = round(h * 0.68)
        step = self.BAR + self.GAP
        n = max(1, w // step)
        frac = self.pos_ / self.dur if self.dur else 0.0
        px = w * frac
        hx = self.hover if self.hover >= 0 and not self.drag else -1
        played, rest = QColor("#ffffff"), QColor(255, 255, 255, 105)
        hovered = QColor(255, 255, 255, 175)
        r_played, r_rest = QColor(255, 255, 255, 80), QColor(255, 255, 255, 34)
        p.setPen(Qt.NoPen)
        if self.loading:                                   # a quiet flat line until the waveform is read
            p.setBrush(QColor(255, 255, 255, 40))
            p.drawRect(QRectF(0, base - 2, w, 2))
            p.setBrush(QColor(255, 255, 255, 140))
            p.drawRect(QRectF(0, base - 2, px, 2))
        else:
            vals = self._bar_values(n)
            for i, v in enumerate(vals):
                x = i * step
                mid = x + self.BAR / 2
                up = max(1.0, v * (base - 3))
                down = max(1.0, v * (h - base - 2) * 0.85)
                if mid <= px:
                    top, ref = played, r_played
                elif hx >= 0 and mid <= hx:
                    top, ref = hovered, r_played
                else:
                    top, ref = rest, r_rest
                p.setBrush(top)
                p.drawRect(QRectF(x, base - up, self.BAR, up))
                p.setBrush(ref)
                p.drawRect(QRectF(x, base + 1, self.BAR, down))
        if self.dur:
            p.setBrush(QColor("#ffffff"))
            p.drawRect(QRectF(min(px, w - 1), 0, 1, h))
            if hx >= 0:
                p.setBrush(QColor(255, 255, 255, 120))
                p.drawRect(QRectF(hx, 0, 1, h))
        p.end()


def placeholder_cover(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor("#1c2230"))
    g.setColorAt(1, QColor("#241c35"))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.06, size * 0.06)
    ic = style.icon("fa6s.music", "#3d4660").pixmap(int(size * 0.36), int(size * 0.36))
    p.drawPixmap(int(size * 0.32), int(size * 0.32), ic)
    p.end()
    return pm


class CoverView(QWidget):
    """Square cover with rounded corners, scaled to the widget (placeholder when there is none)."""
    clicked = Signal()

    def __init__(self, parent=None, radius: float = 0.05):
        super().__init__(parent)
        self.src: QPixmap | None = None
        self.radius = radius
        self._cache: QPixmap | None = None
        self.setMinimumSize(64, 64)

    def set_image(self, data: bytes | QPixmap | None):
        pm = None
        if isinstance(data, QPixmap):
            pm = data
        elif data:
            pm = QPixmap()
            if not pm.loadFromData(data):
                pm = None
        self.src = pm if pm is not None and not pm.isNull() else None
        self._cache = None
        self.update()

    def has_image(self) -> bool:
        return self.src is not None

    def sizeHint(self):
        return QSize(300, 300)

    def heightForWidth(self, w):
        return w

    def hasHeightForWidth(self):
        return True

    def resizeEvent(self, e):
        self._cache = None

    def paintEvent(self, _):
        side = min(self.width(), self.height())
        if side <= 0:
            return
        if self._cache is None or self._cache.width() != side:
            if self.src is None:
                self._cache = placeholder_cover(side)
            else:
                img = self.src.scaled(side, side, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                pm = QPixmap(side, side)
                pm.fill(Qt.transparent)
                p = QPainter(pm)
                p.setRenderHint(QPainter.Antialiasing)
                path = QPainterPath()
                path.addRoundedRect(QRectF(0, 0, side, side), side * self.radius, side * self.radius)
                p.setClipPath(path)
                p.drawPixmap((side - img.width()) // 2, (side - img.height()) // 2, img)
                p.end()
                self._cache = pm
        p = QPainter(self)
        p.drawPixmap((self.width() - side) // 2, (self.height() - side) // 2, self._cache)
        p.end()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()


class Toast(QLabel):
    """Short message at the bottom of its parent."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"background: rgba(23,26,33,235); border: 1px solid {style.BORDER}; border-radius: 10px;"
                           " padding: 8px 16px; color: #ffffff;")
        self.hide()
        self._t = QTimer(self)
        self._t.setSingleShot(True)
        self._t.timeout.connect(self.hide)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def show_text(self, text: str, ms: int = 1600):
        self.setText(text)
        self.adjustSize()
        par = self.parentWidget()
        if par:
            self.move((par.width() - self.width()) // 2, par.height() - self.height() - 110)
        self.show()
        self.raise_()
        self._t.start(ms)


class SpeakerMap(QWidget):
    """Top view of a 5.1 room: click a speaker to hear it; the playing one glows."""
    picked = Signal(str)
    # name → (x, y) as fractions of the widget
    POS = {"FL": (0.2, 0.2), "FC": (0.5, 0.12), "FR": (0.8, 0.2), "BL": (0.14, 0.82), "BR": (0.86, 0.82),
           "LFE": (0.68, 0.36)}

    def __init__(self, labels: dict, parent=None):
        super().__init__(parent)
        self.labels = labels
        self.active = ""
        self.setMinimumSize(420, 300)
        self.setCursor(Qt.PointingHandCursor)

    def set_active(self, name: str):
        self.active = name
        self.update()

    def _rect(self, name: str) -> QRectF:
        x, y = self.POS[name]
        w = 62 if name != "LFE" else 56
        return QRectF(x * self.width() - w / 2, y * self.height() - 26, w, 52)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        room = QRectF(8, 8, self.width() - 16, self.height() - 16)
        p.setPen(QPen(QColor(style.BORDER), 1.5))
        p.setBrush(QColor(style.PANEL))
        p.drawRoundedRect(room, 16, 16)
        # the listener
        c = QPointF(self.width() / 2, self.height() * 0.6)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#3a4152"))
        p.drawEllipse(c, 18, 18)
        p.setPen(QColor(style.MUTED))
        f = QFont(self.font())
        f.setPointSizeF(8.5)
        p.setFont(f)
        p.drawText(QRectF(c.x() - 60, c.y() + 20, 120, 18), Qt.AlignCenter, self.labels.get("you", ""))
        for name in self.POS:
            r = self._rect(name)
            on = name == self.active
            if on:
                g = QLinearGradient(r.topLeft(), r.bottomRight())
                g.setColorAt(0, QColor(style.ACCENT))
                g.setColorAt(1, QColor(style.ACCENT2))
                p.setBrush(g)
                p.setPen(Qt.NoPen)
            else:
                p.setBrush(QColor(style.PANEL2))
                p.setPen(QPen(QColor(style.BORDER), 1.2))
            p.drawRoundedRect(r, 10, 10)
            p.setPen(QColor("#ffffff" if on else style.TEXT))
            f.setPointSizeF(10)
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRectF(r.x(), r.y() + 5, r.width(), 22), Qt.AlignCenter, name if name != "LFE" else "SUB")
            f.setBold(False)
            f.setPointSizeF(7.5)
            p.setFont(f)
            p.setPen(QColor("#ffffff" if on else style.MUTED))
            p.drawText(QRectF(r.x() - 20, r.y() + 26, r.width() + 40, 18), Qt.AlignCenter, self.labels.get(name, ""))
        p.end()

    def mouseReleaseEvent(self, e):
        for name in self.POS:
            if self._rect(name).contains(e.position()):
                self.picked.emit(name)
                return


class PlaylistView(QTreeWidget):
    """Columns #, title, artist, album, length. Rows move by drag; files dropped from Explorer go in at the
    drop point."""
    files_dropped = Signal(list, int)        # paths, row (-1 = end)
    reordered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playlist")
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setAllColumnsShowFocus(True)
        self.setItemsExpandable(False)
        self.setIndentation(0)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and e.source() is None:
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls() and e.source() is None:
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls() and e.source() is None:
            paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
            it = self.itemAt(e.position().toPoint())
            row = self.indexOfTopLevelItem(it) if it is not None else -1
            if it is not None and e.position().y() > self.visualItemRect(it).center().y():
                row += 1
            e.acceptProposedAction()
            self.files_dropped.emit(paths, row)
            return
        super().dropEvent(e)
        # never let an item become a child of another
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            while top.childCount():
                ch = top.takeChild(0)
                self.insertTopLevelItem(i + 1, ch)
        self.reordered.emit()


class LyricsView(QListWidget):
    """The lyrics under the cover: the line being sung is bright and kept in the middle, the rest dim; a click
    on a line of synced lyrics seeks there."""
    seek = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("lyrics")
        self.setFocusPolicy(Qt.NoFocus)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWordWrap(True)
        self.setStyleSheet("QListWidget#lyrics { background: transparent; border: none; }"
                           "QListWidget#lyrics::item { padding: 3px 2px; border: none; }"
                           "QListWidget#lyrics::item:hover { background: rgba(255,255,255,12); border-radius: 6px; }")
        self.lyr = None
        self.cur = -2
        self.user_scrolled_at = 0.0
        self.itemClicked.connect(self._clicked)

    def set_lyrics(self, lyr):
        self.lyr = lyr
        self.cur = -2
        self.clear()
        if lyr is None:
            return
        f = QFont(self.font())
        f.setPointSizeF(max(9.0, f.pointSizeF() + 1.5))
        for line in lyr.lines:
            it = QListWidgetItem(line if line.strip() else "♪" if lyr.synced else "")
            it.setFont(f)
            it.setForeground(QColor(style.TEXT if not lyr.synced else style.MUTED))
            self.addItem(it)
        self.scrollToTop()

    def set_pos(self, sec: float):
        if self.lyr is None or not self.lyr.synced:
            return
        i = self.lyr.index_at(sec)
        if i == self.cur:
            return
        old, self.cur = self.cur, i
        if 0 <= old < self.count():
            it = self.item(old)
            f = it.font()
            f.setBold(False)
            it.setFont(f)
            it.setForeground(QColor(style.MUTED))
        if 0 <= i < self.count():
            it = self.item(i)
            f = it.font()
            f.setBold(True)
            it.setFont(f)
            it.setForeground(QColor("#ffffff"))
            import time
            if time.monotonic() - self.user_scrolled_at > 4:         # don't fight the user's scrolling
                self.scrollToItem(it, QAbstractItemView.PositionAtCenter)

    def wheelEvent(self, e):
        import time
        self.user_scrolled_at = time.monotonic()
        super().wheelEvent(e)

    def _clicked(self, it):
        if self.lyr is not None and self.lyr.synced:
            r = self.row(it)
            if 0 <= r < len(self.lyr.times):
                self.user_scrolled_at = 0.0
                self.seek.emit(self.lyr.times[r])


class ClickLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)


def elide(label: QLabel, text: str, width: int | None = None):
    fm = label.fontMetrics()
    w = width if width is not None else max(40, label.width())
    label.setText(fm.elidedText(text, Qt.ElideRight, w))
    label.setToolTip(text if fm.horizontalAdvance(text) > w else "")


def exists(path: str) -> bool:
    return "://" in path or os.path.exists(path)


# ── channel levels ────────────────────────────────────────────
FLOOR_DB = -48.0
CH_LABEL = {"LFE": "SUB"}


class LevelState:
    """Smoothed levels for the meters: a bar jumps up at once and falls 26 dB/s; the peak stays 1.5 s, then falls."""
    FALL, PEAK_HOLD, PEAK_FALL = 26.0, 1.5, 18.0

    def __init__(self):
        self.ch: list[str] = []
        self.rms: dict[str, float] = {}
        self.peak: dict[str, float] = {}
        self.held: dict[str, float] = {}           # channel → when its peak was set
        self.last = 0.0

    def feed(self, levels: list[tuple[str, float, float]], now: float) -> bool:
        """New readings (or [] = silence); True when something on screen changed."""
        dt = min(0.2, now - self.last) if self.last else 0.03
        self.last = now
        if levels:
            names = [c[0] for c in levels]
            if names != self.ch:
                self.ch = names
                self.rms = {n: self.rms.get(n, FLOOR_DB) for n in names}
                self.peak = {n: self.peak.get(n, FLOOR_DB) for n in names}
        got = {c[0]: (c[1], c[2]) for c in levels}
        changed = False
        for n in self.ch:
            rms, pk = got.get(n, (FLOOR_DB - 10, FLOOR_DB - 10))
            old_r, old_p = self.rms[n], self.peak[n]
            self.rms[n] = max(rms, old_r - self.FALL * dt, FLOOR_DB)
            if pk >= old_p:
                self.peak[n] = pk
                self.held[n] = now
            elif now - self.held.get(n, 0) > self.PEAK_HOLD:
                self.peak[n] = max(FLOOR_DB, old_p - self.PEAK_FALL * dt, self.rms[n])
            changed = changed or abs(self.rms[n] - old_r) > 0.05 or abs(self.peak[n] - old_p) > 0.05
        return changed

    def silent(self) -> bool:
        return all(v <= FLOOR_DB + 0.01 for v in self.rms.values()) and \
            all(v <= FLOOR_DB + 0.01 for v in self.peak.values())

    @staticmethod
    def frac(db: float) -> float:
        return max(0.0, min(1.0, 1.0 - db / FLOOR_DB))


def _meter_gradient(top: float, bottom: float) -> QLinearGradient:
    g = QLinearGradient(0, bottom, 0, top)
    g.setColorAt(0.0, QColor(style.ACCENT))
    g.setColorAt(0.62, QColor(style.ACCENT2))
    g.setColorAt(0.86, QColor("#d63384"))
    g.setColorAt(1.0, QColor("#ff4d4f"))
    return g


class ChannelMeters(QWidget):
    """Bars per channel with a dB grid and peak marks — under the cover. A click opens the room view."""
    clicked = Signal()

    def __init__(self, state: LevelState, parent=None):
        super().__init__(parent)
        self.state = state
        self.caption = ""
        self.setFixedHeight(118)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor(style.BORDER), 1))
        p.setBrush(QColor(style.PANEL))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 10, 10)
        top, bot, x0, x1 = 10.0, h - 24.0, 34.0, w - 10.0
        f = QFont(self.font())
        f.setPointSizeF(7)
        p.setFont(f)
        for db in (0, -12, -24, -36):
            y = top + (bot - top) * (db / FLOOR_DB)
            p.setPen(QColor(style.MUTED))
            p.drawText(QRectF(2, y - 7, x0 - 7, 14), Qt.AlignRight | Qt.AlignVCenter, str(db))
            p.setPen(QPen(QColor(255, 255, 255, 16), 1))
            p.drawLine(QPointF(x0, y), QPointF(x1, y))
        names = self.state.ch or ["FL", "FC", "FR", "LFE", "SL", "SR"]
        slot = (x1 - x0) / len(names)
        bw = min(30.0, slot * 0.5)
        grad = _meter_gradient(top, bot)
        for i, n in enumerate(names):
            x = x0 + slot * i + (slot - bw) / 2
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 12))
            p.drawRoundedRect(QRectF(x, top, bw, bot - top), 3, 3)
            fr = LevelState.frac(self.state.rms.get(n, FLOOR_DB))
            if fr > 0.002:
                y = bot - (bot - top) * fr
                p.setBrush(grad)
                p.drawRoundedRect(QRectF(x, y, bw, bot - y), 3, 3)
            pf = LevelState.frac(self.state.peak.get(n, FLOOR_DB))
            if pf > 0.002:
                y = bot - (bot - top) * pf
                p.setBrush(QColor("#ffffff"))
                p.drawRect(QRectF(x, y - 1, bw, 2))
            f.setPointSizeF(8)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(style.TEXT))
            p.drawText(QRectF(x - 20, bot + 4, bw + 40, 16), Qt.AlignCenter, CH_LABEL.get(n, n))
            f.setBold(False)
        p.end()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()


class RoomMeters(QWidget):
    """Top view of the room: every speaker glows and sends a beam to the listener as loud as it plays."""
    POS = {"FL": (0.2, 0.2), "FC": (0.5, 0.12), "FR": (0.8, 0.2), "LFE": (0.7, 0.4), "SL": (0.12, 0.8),
           "SR": (0.88, 0.8), "BL": (0.3, 0.92), "BR": (0.7, 0.92), "BC": (0.5, 0.92)}

    def __init__(self, state: LevelState, labels: dict, parent=None):
        super().__init__(parent)
        self.state = state
        self.labels = labels
        self.setMinimumSize(460, 330)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor(style.BORDER), 1.2))
        p.setBrush(QColor(style.PANEL))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 16, 16)
        c = QPointF(w / 2, h * 0.6)
        names = [n for n in (self.state.ch or ["FL", "FC", "FR", "LFE", "SL", "SR"]) if n in self.POS]
        lv = {n: LevelState.frac(self.state.rms.get(n, FLOOR_DB)) for n in names}
        for n in names:                                           # beams under everything
            x, y = self.POS[n]
            pt = QPointF(x * w, y * h)
            a = lv[n]
            if a > 0.01:
                g = QLinearGradient(pt, c)
                g.setColorAt(0, QColor(111, 66, 193, int(170 * a)))
                g.setColorAt(1, QColor(111, 66, 193, 0))
                p.setPen(QPen(QBrush(g), 2 + 7 * a, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(pt, c)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#3a4152"))
        p.drawEllipse(c, 16, 16)
        f = QFont(self.font())
        f.setPointSizeF(8.5)
        p.setFont(f)
        p.setPen(QColor(style.MUTED))
        p.drawText(QRectF(c.x() - 60, c.y() + 18, 120, 18), Qt.AlignCenter, self.labels.get("you", ""))
        for n in names:
            x, y = self.POS[n]
            pt = QPointF(x * w, y * h)
            a = lv[n]
            if a > 0.01:
                rad = 30 + 28 * a
                rg = QRadialGradient(pt, rad)
                rg.setColorAt(0, QColor(13, 110, 253, int(180 * a)))
                rg.setColorAt(1, QColor(13, 110, 253, 0))
                p.setPen(Qt.NoPen)
                p.setBrush(rg)
                p.drawEllipse(pt, rad, rad)
            r = QRectF(pt.x() - 34, pt.y() - 26, 68, 52)
            if a > 0.01:
                gg = QLinearGradient(r.topLeft(), r.bottomRight())
                gg.setColorAt(0, QColor(style.ACCENT))
                gg.setColorAt(1, QColor(style.ACCENT2))
                p.setBrush(gg)
                p.setPen(Qt.NoPen)
            else:
                p.setBrush(QColor(style.PANEL2))
                p.setPen(QPen(QColor(style.BORDER), 1.2))
            p.drawRoundedRect(r, 10, 10)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 90))
            p.drawRoundedRect(QRectF(r.x() + 9, r.bottom() - 10, r.width() - 18, 4), 2, 2)
            if a > 0.01:
                p.setBrush(QColor("#ffffff"))
                p.drawRoundedRect(QRectF(r.x() + 9, r.bottom() - 10, (r.width() - 18) * a, 4), 2, 2)
            f.setPointSizeF(10)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("#ffffff"))
            p.drawText(QRectF(r.x(), r.y() + 3, r.width(), 20), Qt.AlignCenter, CH_LABEL.get(n, n))
            f.setBold(False)
            f.setPointSizeF(7.5)
            p.setFont(f)
            db = self.state.rms.get(n, FLOOR_DB)
            p.setPen(QColor(255, 255, 255, 220) if a > 0.01 else QColor(style.MUTED))
            p.drawText(QRectF(r.x() - 10, r.y() + 21, r.width() + 20, 14), Qt.AlignCenter,
                       f"{db:.0f} dB" if db > FLOOR_DB + 0.5 else "—")
        p.end()
