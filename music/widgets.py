"""Small widgets: seek bar, cover, toast, speaker map, the playlist view."""
from __future__ import annotations

import os

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QLabel, QToolButton, QTreeWidget, QWidget

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
