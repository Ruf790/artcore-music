"""Small widgets: seek bar, cover, toast, speaker map, the playlist view."""
from __future__ import annotations

import os

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient)
from PySide6.QtWidgets import (QAbstractItemView, QLabel, QListWidget, QListWidgetItem, QStyledItemDelegate,
                               QStyleOptionViewItem, QToolButton, QTreeWidget, QWidget)

from . import style


def fmt_time(sec: float | None) -> str:
    if sec is None or sec < 0:
        sec = 0
    s = int(sec)
    h, m, s = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def set_btn_icon(b: QToolButton, icon_name: str) -> None:
    """The icon of a tool button in the colour of the current skin (remembered, so a skin change can redo it)."""
    b.setProperty("ico", icon_name)
    b.setIcon(style.icon(icon_name, style.btn_fg(b)))


def recolor_buttons(root: QWidget) -> None:
    """After a skin change: every tool button below root gets its icon again in the new colour."""
    for b in root.findChildren(QToolButton):
        name = b.property("ico")
        if name:
            b.setIcon(style.icon(name, style.btn_fg(b)))


def ctl_button(icon_name: str, tip: str, size: int = 20, slot=None, obj: str = "ctl") -> QToolButton:
    b = QToolButton()
    b.setObjectName(obj)
    set_btn_icon(b, icon_name)
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
        p.setBrush(style.fgc(45))
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
            p.setBrush(QColor("#ffffff") if style.IS_DARK else QColor(style.ACCENT))
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
    HEIGHT = 72
    TOP = 16                         # room above the bars for the time bubble under the mouse
    BAR, GAP = 3, 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.peaks: bytes = b""
        self.loading = False
        self.enabled_wave = True
        self.live = False                    # internet radio: a wave of what plays now, moving right → left
        self.live_vals: list[float] = []
        self._live_tick = 0
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

    LIVE_KEEP = 900                       # values kept (more than the widest window shows)

    def set_live(self, on: bool):
        if on != self.live:
            self.live = on
            self.live_vals = []
            self.update()

    def push(self, v: float):
        """A new level (0…1) of what plays — every meter tick; every 2nd one becomes a bar (~15 per second)."""
        self._live_tick += 1
        if self._live_tick % 2:
            return
        self.live_vals.append(max(0.0, min(1.0, v)))
        if len(self.live_vals) > self.LIVE_KEEP:
            del self.live_vals[:len(self.live_vals) - self.LIVE_KEEP]
        self.update()

    def _wave_on(self) -> bool:
        return self.enabled_wave and (self.live or bool(self.peaks or self.loading))

    def _paint_live(self, p: QPainter, w: int, h: int, base: int):
        """Newest bar at the right edge; older ones move left and fade."""
        step = self.BAR + self.GAP
        n = max(1, w // step)
        vals = self.live_vals[-n:]
        g = QLinearGradient(0, 0, w, 0)
        c0 = QColor(style.ACCENT2)
        c0.setAlpha(60)
        g.setColorAt(0, c0)
        g.setColorAt(0.35, QColor(style.ACCENT2))
        g.setColorAt(1, QColor(style.ACCENT))
        top = QBrush(g)
        rg = QLinearGradient(0, 0, w, 0)
        r0, r1 = QColor(style.ACCENT2), QColor(style.ACCENT)
        r0.setAlpha(15)
        r1.setAlpha(80)
        rg.setColorAt(0, r0)
        rg.setColorAt(1, r1)
        ref = QBrush(rg)
        p.setPen(Qt.NoPen)
        p.setBrush(style.fgc(30))
        p.drawRect(QRectF(0, base - 1, w, 1))                    # the base line where there is nothing yet
        # loud, compressed radio would be a flat wall: stretch what the last seconds span to the full height
        if vals:
            lo, hi = min(vals), max(vals)
            if hi - lo > 0.04:
                vals = [0.12 + 0.88 * (v - lo) / (hi - lo) for v in vals]
        x0 = w - len(vals) * step
        for i, v in enumerate(vals):
            x = x0 + i * step
            up = max(1.0, v * (base - 3))
            down = max(1.0, v * (h - base - 2) * 0.85)
            p.setBrush(top)
            p.drawRoundedRect(QRectF(x, base - up, self.BAR, up), 1.2, 1.2)
            p.setBrush(ref)
            p.drawRoundedRect(QRectF(x, base + 1, self.BAR, down), 1.2, 1.2)

    def mouseMoveEvent(self, e):
        super().mouseMoveEvent(e)
        if self._wave_on():
            self.setToolTip("")                            # the time is drawn above the bars instead

    def paintEvent(self, e):
        if not self._wave_on():
            return super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h0 = self.width(), self.height()
        top0 = self.TOP
        p.translate(0, top0)
        h = h0 - top0
        base = round(h * 0.68)
        if self.live:
            self._paint_live(p, w, h, base)
            p.end()
            return
        step = self.BAR + self.GAP
        n = max(1, w // step)
        frac = self.pos_ / self.dur if self.dur else 0.0
        px = w * frac
        hx = self.hover if self.hover >= 0 and not self.drag else -1
        played = QLinearGradient(0, 0, w, 0)                   # the played part: the accent gradient
        played.setColorAt(0, QColor(style.ACCENT2))
        played.setColorAt(1, QColor(style.ACCENT))
        played = QBrush(played)
        rest, hovered = style.fgc(70), style.fgc(140)
        r_played = QLinearGradient(0, 0, w, 0)
        c1, c2 = QColor(style.ACCENT2), QColor(style.ACCENT)
        c1.setAlpha(80)
        c2.setAlpha(80)
        r_played.setColorAt(0, c1)
        r_played.setColorAt(1, c2)
        r_played = QBrush(r_played)
        r_rest = style.fgc(30)
        p.setPen(Qt.NoPen)
        if self.loading:                                   # a quiet flat line until the waveform is read
            p.setBrush(style.fgc(40))
            p.drawRect(QRectF(0, base - 2, w, 2))
            p.setBrush(style.fgc(140))
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
                p.drawRoundedRect(QRectF(x, base - up, self.BAR, up), 1.2, 1.2)
                p.setBrush(ref)
                p.drawRoundedRect(QRectF(x, base + 1, self.BAR, down), 1.2, 1.2)
        if self.dur:
            p.setBrush(style.fgc(230))
            p.drawRect(QRectF(min(px, w - 2), 0, 2, h))
            if hx >= 0:
                p.setBrush(style.fgc(120))
                p.drawRect(QRectF(hx, 0, 1, h))
        p.resetTransform()
        if self.dur and hx >= 0:                             # the time under the mouse, in a bubble
            txt = fmt_time(self._sec_at(hx))
            f = QFont(self.font())
            f.setPointSizeF(8)
            f.setBold(True)
            p.setFont(f)
            tw = p.fontMetrics().horizontalAdvance(txt) + 12
            r = QRectF(max(0.0, min(w - tw, hx - tw / 2)), 0, tw, top0 - 1)
            p.setPen(Qt.NoPen)
            p.setBrush(style.fgc(235) if style.IS_DARK else QColor(style.TEXT))
            p.drawRoundedRect(r, 4, 4)
            p.setPen(QColor(style.BG) if style.IS_DARK else QColor("#ffffff"))
            p.drawText(r, Qt.AlignCenter, txt)
        p.end()


def placeholder_cover(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor(style.PH1))
    g.setColorAt(1, QColor(style.PH2))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.06, size * 0.06)
    ic = style.icon("fa6s.music", style.PH_ICON).pixmap(int(size * 0.36), int(size * 0.36))
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
        self.restyle()
        self.hide()
        self._t = QTimer(self)
        self._t.setSingleShot(True)
        self._t.timeout.connect(self.hide)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def restyle(self):
        r, g, b, a = style.TOAST
        self.setStyleSheet(f"background: rgba({r},{g},{b},{a}); border: 1px solid {style.BORDER}; border-radius: 10px;"
                           f" padding: 8px 16px; color: {style.TEXT};")

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
        p.setBrush(QColor(style.SPK))
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


class GroupHead:
    """What the view draws above the first track of a group (filled in by the window)."""
    __slots__ = ("key", "kind", "title", "sub", "cover", "folded", "count")

    def __init__(self, key: str, kind: str, title: str, sub: str, cover=None, folded: bool = False, count: int = 1):
        self.key, self.kind, self.title, self.sub = key, kind, title, sub
        self.cover = cover               # QPixmap | None | callable returning one (read when first drawn)
        self.folded = folded
        self.count = count


class GroupDelegate(QStyledItemDelegate):
    """Rows as usual; the first row of a group is taller and carries the group's head above it."""
    HEAD = 62
    ICONS = {"radio": "fa6s.tower-broadcast", "singles": "fa6s.music", "album": "fa6s.compact-disc"}

    def __init__(self, view: "PlaylistView"):
        super().__init__(view)
        self.view = view

    def _head(self, index):
        return self.view.heads.get(index.siblingAtColumn(0).data(self.view.uid_role))

    def sizeHint(self, option, index):
        sz = super().sizeHint(option, index)
        hd = self._head(index)
        if hd is None:
            return sz
        return QSize(sz.width(), self.HEAD + (0 if hd.folded else sz.height()))

    def _tint(self, painter, rect, index):
        """The playing row's tint (the style sheet would ignore the item's own background)."""
        b = index.data(Qt.BackgroundRole)
        if isinstance(b, QBrush) and b.style() != Qt.NoBrush:
            painter.fillRect(rect, b)

    def paint(self, painter, option, index):
        hd = self._head(index)
        if hd is None:
            self._tint(painter, option.rect, index)
            return super().paint(painter, option, index)
        row = QStyleOptionViewItem(option)
        row.rect.setTop(option.rect.top() + self.HEAD)
        if not hd.folded:
            self._tint(painter, row.rect, index)
            super().paint(painter, row, index)
        # the head goes over the whole width, drawn with the last visible column (after the row panels)
        if index.column() == self.view.last_column():
            r = QRectF(0, option.rect.top(), self.view.viewport().width(), self.HEAD)
            self.paint_head(painter, r, hd)

    def paint_head(self, p: QPainter, r: QRectF, hd: GroupHead):
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(style.PANEL))
        p.drawRect(r)
        if r.top() > 1:
            p.setBrush(QColor(style.BORDER))
            p.drawRect(QRectF(r.left() + 8, r.top(), r.width() - 16, 1))
        side = 44.0
        art = QRectF(r.left() + 10, r.top() + (r.height() - side) / 2 + 2, side, side)
        pm = hd.cover() if callable(hd.cover) else hd.cover
        if callable(hd.cover):
            hd.cover = pm
        if pm is not None and not pm.isNull():
            path = QPainterPath()
            path.addRoundedRect(art, 7, 7)
            p.setClipPath(path)
            p.drawPixmap(art.toRect(), pm.scaled(int(side * 2), int(side * 2), Qt.KeepAspectRatioByExpanding,
                                                Qt.SmoothTransformation))
            p.setClipping(False)
        else:
            p.setBrush(QColor(style.PANEL2))
            p.drawRoundedRect(art, 7, 7)
            ic = style.icon(self.ICONS.get(hd.kind, "fa6s.music"), style.MUTED).pixmap(20, 20)
            p.drawPixmap(int(art.center().x() - 10), int(art.center().y() - 10), ic)
        tx = art.right() + 14
        tw = r.right() - tx - 40
        f = QFont(self.view.font())
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() + 1.5)
        p.setFont(f)
        p.setPen(QColor(style.TEXT))
        fm = p.fontMetrics()
        p.drawText(QRectF(tx, art.top() + 1, tw, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   fm.elidedText(hd.title, Qt.ElideRight, int(tw)))
        f.setBold(False)
        f.setPointSizeF(f.pointSizeF() - 2.5)
        p.setFont(f)
        p.setPen(QColor(style.MUTED))
        p.drawText(QRectF(tx, art.top() + 23, tw, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(hd.sub, Qt.ElideRight, int(tw)))
        chev = style.icon("fa6s.chevron-right" if hd.folded else "fa6s.chevron-down", style.MUTED).pixmap(12, 12)
        p.drawPixmap(int(r.right() - 30), int(r.center().y() - 4), chev)
        p.restore()


class PlaylistView(QTreeWidget):
    """Columns #, title, artist, album, length. Rows move by drag; files dropped from Explorer go in at the
    drop point. With groups on, an album / the radio stations / loose tracks get a head above their first row;
    a click on a head folds the group."""
    files_dropped = Signal(list, int)        # paths, row (-1 = end)
    reordered = Signal()
    head_clicked = Signal(str)               # group key

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playlist")
        self.uid_role = Qt.UserRole + 1
        self.heads: dict[int, GroupHead] = {}            # uid of a group's first track → its head
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
        self.setMouseTracking(True)
        self.setItemDelegate(GroupDelegate(self))

    def set_heads(self, heads: dict):
        self.heads = heads
        self.setUniformRowHeights(not heads)               # uniform heights are faster when there are none
        self.scheduleDelayedItemsLayout()
        self.viewport().update()

    def last_column(self) -> int:
        hdr = self.header()
        for v in range(hdr.count() - 1, -1, -1):
            c = hdr.logicalIndex(v)
            if not hdr.isSectionHidden(c):
                return c
        return 0

    def head_at(self, pos) -> GroupHead | None:
        it = self.itemAt(pos)
        if it is None:
            return None
        hd = self.heads.get(it.data(0, self.uid_role))
        if hd is None:
            return None
        return hd if pos.y() < self.visualItemRect(it).top() + GroupDelegate.HEAD else None

    def mousePressEvent(self, e):
        hd = self.head_at(e.position().toPoint()) if e.button() == Qt.LeftButton else None
        if hd is not None:
            self.head_clicked.emit(hd.key)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if self.head_at(e.position().toPoint()) is not None:
            e.accept()
            return
        super().mouseDoubleClickEvent(e)

    def mouseMoveEvent(self, e):
        on_head = self.head_at(e.position().toPoint()) is not None
        self.viewport().setCursor(Qt.PointingHandCursor if on_head else Qt.ArrowCursor)
        super().mouseMoveEvent(e)

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


class NowPanel(QWidget):
    """The left column: a soft glow of the album's colours behind the cover (when colours follow the cover)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.glow = False

    def paintEvent(self, _):
        if not self.glow:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rad = max(self.width(), 300) * 1.15
        c = QPointF(self.width() * 0.35, self.width() * 0.3)
        g = QRadialGradient(c, rad)
        c1 = QColor(style.ACCENT2)
        c1.setAlpha(100 if style.IS_DARK else 46)
        c2 = QColor(style.ACCENT)
        c2.setAlpha(34 if style.IS_DARK else 16)
        c3 = QColor(style.ACCENT)
        c3.setAlpha(0)
        g.setColorAt(0, c1)
        g.setColorAt(0.45, c2)
        g.setColorAt(1, c3)
        p.fillRect(self.rect(), g)
        p.end()


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
        self.restyle(redraw=False)
        self.lyr = None
        self.cur = -2
        self.user_scrolled_at = 0.0
        self.itemClicked.connect(self._clicked)

    def restyle(self, redraw: bool = True):
        """The colours of the skin; the lines are filled again (their colours were set per item)."""
        self.setStyleSheet("QListWidget#lyrics { background: transparent; border: none; }"
                           "QListWidget#lyrics::item { padding: 3px 2px; border: none; }"
                           f"QListWidget#lyrics::item:hover {{ background: {style.H(12)}; border-radius: 6px; }}")
        if redraw and self.lyr is not None:
            pos = self.cur
            self.set_lyrics(self.lyr)
            if pos >= 0 and self.lyr.synced and pos < self.count():
                self.cur = -2
                self.set_pos(self.lyr.times[pos])

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
            it.setForeground(QColor(style.FG))
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


class ElideLabel(QLabel):
    """One line; text that does not fit ends with … and the whole of it is in the tooltip. text() is the full text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full = ""
        self.setMinimumWidth(10)

    def setText(self, text: str):
        self._full = text or ""
        self._fit()

    def text(self) -> str:
        return self._full

    def _fit(self):
        fm = self.fontMetrics()
        w = max(40, self.width())
        QLabel.setText(self, fm.elidedText(self._full, Qt.ElideRight, w))
        self.setToolTip(self._full if fm.horizontalAdvance(self._full) > w else "")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()

    def minimumSizeHint(self):
        return QSize(10, super().minimumSizeHint().height())

    def sizeHint(self):
        return QSize(10, super().sizeHint().height())


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
    """A row per channel (FL, FC, FR, SUB, SL, SR…) with the level as a bar and a peak mark — under the cover.
    A click opens the room view."""
    clicked = Signal()
    ROW = 17

    def __init__(self, state: LevelState, parent=None):
        super().__init__(parent)
        self.state = state
        self.caption = ""
        self._n = 6
        self.setFixedHeight(self._height(6))
        self.setCursor(Qt.PointingHandCursor)

    def _height(self, n: int) -> int:
        return 16 + self.ROW * n

    def paintEvent(self, _):
        names = self.state.ch or ["FL", "FC", "FR", "LFE", "SL", "SR"]
        if len(names) != self._n:                          # 2.0 / 5.1 / 7.1
            self._n = len(names)
            self.setFixedHeight(self._height(self._n))
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor(style.BORDER), 1))
        p.setBrush(QColor(style.PANEL))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 10, 10)
        x0, x1 = 46.0, w - 14.0
        f = QFont(self.font())
        f.setPointSizeF(7.5)
        f.setBold(True)
        p.setFont(f)
        grad = QLinearGradient(x0, 0, x1, 0)
        grad.setColorAt(0.0, QColor(style.ACCENT2))
        grad.setColorAt(0.75, QColor(style.ACCENT))
        grad.setColorAt(0.93, QColor("#ff6b6b"))
        for i, n in enumerate(names):
            cy = 8 + self.ROW * i + self.ROW / 2
            p.setPen(QColor(style.MUTED))
            p.drawText(QRectF(10, cy - 8, x0 - 14, 16), Qt.AlignLeft | Qt.AlignVCenter, CH_LABEL.get(n, n))
            bar = QRectF(x0, cy - 3, x1 - x0, 6)
            p.setPen(Qt.NoPen)
            p.setBrush(style.fgc(18))
            p.drawRoundedRect(bar, 3, 3)
            fr = LevelState.frac(self.state.rms.get(n, FLOOR_DB))
            if fr > 0.002:
                p.setBrush(grad)
                p.drawRoundedRect(QRectF(x0, cy - 3, (x1 - x0) * fr, 6), 3, 3)
            pf = LevelState.frac(self.state.peak.get(n, FLOOR_DB))
            if pf > 0.002:
                p.setBrush(style.fgc(220))
                p.drawRect(QRectF(x0 + (x1 - x0) * pf - 1, cy - 5, 2, 10))
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
                c0 = QColor(style.ACCENT2)
                c0.setAlpha(int(170 * a))
                c1 = QColor(style.ACCENT2)
                c1.setAlpha(0)
                g.setColorAt(0, c0)
                g.setColorAt(1, c1)
                p.setPen(QPen(QBrush(g), 2 + 7 * a, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(pt, c)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(style.SPK))
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
                c0 = QColor(style.ACCENT)
                c0.setAlpha(int(180 * a))
                c1 = QColor(style.ACCENT)
                c1.setAlpha(0)
                rg.setColorAt(0, c0)
                rg.setColorAt(1, c1)
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
