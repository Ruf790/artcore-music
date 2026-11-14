"""Colours, skins, the app icon and the style sheet.

The colours below are module variables that `set_theme()` rewrites, so everything that reads `style.PANEL` etc.
at paint time follows the skin. The palettes live in themes.py."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPalette, QPixmap

from . import themes

# the current skin (set_theme fills these in)
CURRENT = themes.DEFAULT
IS_DARK = True
ACCENT = ACCENT2 = BG = PANEL = PANEL2 = BORDER = TEXT = MUTED = ""
FG = ACCENT_TEXT = STAR = STAR_OFF = ALT = WAVE = SPK = PH1 = PH2 = PH_ICON = ""
HANDLE = HANDLE_EDGE = ""
MINI_COVER = MINI_PLAIN = TOAST = (0, 0, 0, 0)
_hover_rgb, _hover_k = "255,255,255", 1.0


def _rgb(hex_: str) -> str:
    c = QColor(hex_)
    return f"{c.red()},{c.green()},{c.blue()}"


def set_theme(name: str | None) -> str:
    """Switch the colour variables to a skin; returns the name actually used."""
    global CURRENT, IS_DARK, ACCENT, ACCENT2, BG, PANEL, PANEL2, BORDER, TEXT, MUTED
    global FG, ACCENT_TEXT, STAR, STAR_OFF, ALT, WAVE, SPK, PH1, PH2, PH_ICON, HANDLE, HANDLE_EDGE
    global MINI_COVER, MINI_PLAIN, TOAST, SEL_A, _hover_rgb, _hover_k
    CURRENT = themes.valid(name)
    th = themes.THEMES[CURRENT]
    IS_DARK = bool(th["dark"])
    ACCENT, ACCENT2, BG, PANEL, PANEL2 = th["accent"], th["accent2"], th["bg"], th["panel"], th["panel2"]
    BORDER, TEXT, MUTED = th["border"], th["text"], th["muted"]
    FG, ACCENT_TEXT, STAR, STAR_OFF, ALT = th["fg"], th["accent_text"], th["star"], th["star_off"], th["alt"]
    WAVE, SPK, PH1, PH2, PH_ICON = th["wave"], th["spk"], th["ph1"], th["ph2"], th["ph_icon"]
    MINI_COVER, MINI_PLAIN, TOAST = th["mini_cover"], th["mini_plain"], th["toast"]
    # light skins darken on hover, dark ones lighten; a dark overlay needs less alpha to show on white
    _hover_rgb, _hover_k = ("255,255,255", 1.0) if IS_DARK else ("0,0,0", 0.5)
    SEL_A = 95 if IS_DARK else 62
    HANDLE = "#ffffff"
    HANDLE_EDGE = "#ffffff" if IS_DARK else ACCENT
    return CURRENT


SEL_A = 95                                               # opacity of the selected-row tint (set_theme)


def H(alpha: int) -> str:
    """rgba() of the hover / separator tint (white on dark skins, black on light ones)."""
    return f"rgba({_hover_rgb},{max(1, round(alpha * _hover_k))})"


def ac(alpha: int) -> str:
    return f"rgba({_rgb(ACCENT)},{alpha})"


def ac2(alpha: int) -> str:
    return f"rgba({_rgb(ACCENT2)},{alpha})"


def fgc(alpha: int = 255) -> QColor:
    """The foreground colour with an alpha: white on dark skins, the text colour on light ones."""
    c = QColor(FG)
    c.setAlpha(alpha if IS_DARK else min(255, round(alpha * 0.8)))
    return c


def accent_c(alpha: int = 255) -> QColor:
    c = QColor(ACCENT)
    c.setAlpha(alpha)
    return c


def theme_label(key: str) -> str:
    from .i18n import lang
    return themes.THEMES[key]["en" if lang() == "en" else "ru"]


def swatch(key: str, size: int = 20) -> QIcon:
    """A round chip of a skin for menus and the combo box: its background, its panel and its accent."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPen
    th = themes.THEMES[key]
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    r = QRectF(1.5, 1.5, size - 3, size - 3)
    clip = QPainterPath()
    clip.addEllipse(r)
    p.setClipPath(clip)
    p.fillRect(pm.rect(), QColor(th["bg"]))
    p.fillRect(QRectF(0, size * 0.5, size, size * 0.5), QColor(th["panel"]))
    g = QLinearGradient(QPointF(0, 0), QPointF(size, size))
    g.setColorAt(0, QColor(th["accent"]))
    g.setColorAt(1, QColor(th["accent2"]))
    p.setBrush(g)
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(size * 0.42, size * 0.42, size * 0.46, size * 0.46))
    p.setClipping(False)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(th["border"] if not th["dark"] else "#5a6275"), 1.2))
    p.drawEllipse(r)
    p.end()
    return QIcon(pm)


def btn_fg(button=None) -> str:
    """Icon colour for a tool button: white on the accent-coloured play button, the foreground elsewhere."""
    if button is not None and button.objectName() == "play":
        return "#ffffff"
    return FG


def palette() -> QPalette:
    """The Fusion palette for the skin: what the style sheet does not paint (spin arrows, disabled text,
    message boxes, file dialogs, selections in line edits)."""
    p = QPalette()
    for role, col in ((QPalette.Window, BG), (QPalette.WindowText, TEXT), (QPalette.Base, PANEL),
                      (QPalette.AlternateBase, ALT), (QPalette.Text, TEXT), (QPalette.Button, PANEL2),
                      (QPalette.ButtonText, TEXT), (QPalette.ToolTipBase, PANEL2), (QPalette.ToolTipText, TEXT),
                      (QPalette.Highlight, ACCENT), (QPalette.HighlightedText, "#ffffff"),
                      (QPalette.PlaceholderText, MUTED), (QPalette.Link, ACCENT_TEXT), (QPalette.BrightText, "#ffffff"),
                      (QPalette.Mid, BORDER), (QPalette.Midlight, PANEL2), (QPalette.Dark, BORDER),
                      (QPalette.Light, PANEL)):
        p.setColor(role, QColor(col))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(MUTED))
    return p


def apply(app, name: str | None = None) -> None:
    """Make a skin the look of the whole application."""
    if name is not None:
        set_theme(name)
    app.setPalette(palette())
    app.setStyleSheet(stylesheet())


set_theme(themes.DEFAULT)


def _check_png() -> str:
    """White check mark for checked boxes (QSS needs a file)."""
    import os
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "artcore_music_check.png")
    if not os.path.isfile(path):
        try:
            icon("fa6s.check", "#ffffff").pixmap(12, 12).save(path)
        except Exception:
            return ""
    return path.replace("\\", "/")


def _icon_png(name: str, color: str, file: str, px: int = 12) -> str:
    """An icon as a PNG in %TEMP% (QSS images need a file); the colour is part of the file name."""
    import os
    import tempfile
    base, ext = os.path.splitext(file)
    path = os.path.join(tempfile.gettempdir(), f"{base}_{color.lstrip('#')}{ext}")
    if not os.path.isfile(path):
        try:
            icon(name, color).pixmap(px, px).save(path)
        except Exception:
            return ""
    return path.replace("\\", "/")


def stylesheet() -> str:
    return (build_qss().replace("%CHECK%", _check_png())
            .replace("%CLOSE%", _icon_png("fa6s.xmark", MUTED, "artcore_music_close.png"))
            .replace("%CLOSE_HOT%", _icon_png("fa6s.xmark", "#ffffff" if IS_DARK else TEXT,
                                              "artcore_music_close_hot.png")))


_icons: dict = {}


def icon(name: str, color: str | None = None):
    """qtawesome icon, cached (a playlist row asks for two of them; 1000+ rows)."""
    color = color or TEXT
    k = (name, color)
    ic = _icons.get(k)
    if ic is None:
        import qtawesome as qta
        ic = _icons[k] = qta.icon(name, color=color)
    return ic


def app_icon_pixmap(size: int = 256) -> QPixmap:
    """A rounded square, blue → purple → pink with a gloss on top, a white pair of eighth notes with a soft
    shadow and, from 32 px up, a sound wave under it (the seek bar of the player)."""
    from PySide6.QtGui import QPen
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 256.0
    r = QRectF(8 * s, 8 * s, 240 * s, 240 * s)

    def tile(rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(rect, rect.width() * 0.235, rect.height() * 0.235)
        return path

    p.setPen(Qt.NoPen)
    if size >= 32:                                       # a soft shadow under the tile
        for i, a in enumerate((26, 18, 10)):
            p.setBrush(QColor(0, 0, 0, a))
            p.drawPath(tile(r.translated(0, (3 + i * 2) * s)))
    body = tile(r)
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0, QColor("#1f6bff"))
    g.setColorAt(0.55, QColor("#7a3cf0"))
    g.setColorAt(1, QColor("#e83e8c"))
    p.setBrush(g)
    p.drawPath(body)
    p.save()                                             # the gloss
    p.setClipPath(body)
    gl = QLinearGradient(0, r.top(), 0, r.top() + r.height() * 0.55)
    gl.setColorAt(0, QColor(255, 255, 255, 70))
    gl.setColorAt(1, QColor(255, 255, 255, 0))
    p.setBrush(gl)
    p.drawEllipse(QRectF(r.left() - 40 * s, r.top() - 150 * s, r.width() + 80 * s, 260 * s))
    p.restore()
    if size >= 32:
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 50), max(1.0, 2 * s)))
        p.drawPath(tile(r.adjusted(1.5 * s, 1.5 * s, -1.5 * s, -1.5 * s)))
        p.setPen(Qt.NoPen)
    wave = size >= 32
    cx, cy, k = (122, 112, 1.0) if wave else (124, 128, 1.12)

    def notes(color: QColor, dy: float = 0.0):
        p.save()
        p.translate(cx * s, (cy + dy) * s)
        p.scale(k * s, k * s)
        p.setBrush(color)
        for hx, hy in ((-46, 44), (40, 30)):
            p.save()
            p.translate(hx, hy)
            p.rotate(-24)
            p.drawEllipse(QRectF(-24, -17, 48, 34))
            p.restore()
        p.drawRoundedRect(QRectF(-32, -62, 11, 106), 3, 3)
        p.drawRoundedRect(QRectF(54, -76, 11, 106), 3, 3)
        beam = QPainterPath()
        beam.moveTo(-32, -62)
        beam.lineTo(65, -86)
        beam.lineTo(65, -58)
        beam.lineTo(-32, -34)
        beam.closeSubpath()
        p.drawPath(beam)
        p.restore()

    if size >= 24:
        notes(QColor(0, 0, 0, 55), 5)
    notes(QColor("#ffffff"))
    if wave:
        for i, h in enumerate((0.35, 0.6, 0.9, 0.55, 1.0, 0.7, 0.45, 0.8, 0.5, 0.3)):
            hh = 34 * h
            p.setBrush(QColor(255, 255, 255, 200 if i < 5 else 120))
            p.drawRoundedRect(QRectF((62 + i * 14) * s, (208 - hh / 2) * s, 7 * s, hh * s), 3.5 * s, 3.5 * s)
    p.end()
    return pm


def app_icon() -> QIcon:
    ic = QIcon()
    for n in (16, 20, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(app_icon_pixmap(n))
    return ic


def build_qss() -> str:
    """The style sheet of the current skin."""
    return f"""
QWidget {{ color: {TEXT}; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {BG}; }}
QToolTip {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px 7px; border-radius: 6px; }}
QMenu {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT}; color: #ffffff; }}
QMenu::item:disabled {{ color: {MUTED}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}
QMenu::icon {{ padding-left: 8px; }}
QMenu::indicator {{ width: 14px; height: 14px; left: 6px; }}
QPushButton {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 9px; padding: 8px 16px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton#primary {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 {ACCENT2});
                       border: none; color: #ffffff; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACCENT}; }}
QToolButton#ctl {{ background: transparent; border: none; border-radius: 8px; padding: 6px; }}
QToolButton#ctl:hover {{ background: {H(38)}; }}
QToolButton#ctl:pressed {{ background: {H(60)}; }}
QToolButton#ctl::menu-indicator {{ image: none; width: 0; }}
QToolButton#ctlText {{ background: transparent; border: none; border-radius: 8px; padding: 6px 8px;
                       font-weight: 600; }}
QToolButton#ctlText:hover {{ background: {H(38)}; }}
QToolButton#ctlText::menu-indicator {{ image: none; width: 0; }}
QLabel#time {{ font-size: 10pt; color: {FG}; padding: 0 6px; }}
QLabel#title {{ font-size: 13pt; font-weight: 600; color: {FG}; }}
QLabel#badge {{ background: {H(30)}; border: 1px solid {H(60)}; border-radius: 5px;
                padding: 1px 6px; font-size: 8.5pt; font-weight: 700; color: {FG}; }}
QLabel#badgeHdr {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59f00, stop:1 #e8590c);
                   border-radius: 5px; padding: 1px 6px; font-size: 8.5pt; font-weight: 700; color: #ffffff; }}
QSlider#volume::groove:horizontal {{ height: 4px; background: {H(70)}; border-radius: 2px; }}
QSlider#volume::sub-page:horizontal {{ background: {FG}; border-radius: 2px; }}
QSlider#volume::handle:horizontal {{ background: {HANDLE}; width: 10px; height: 10px; margin: -4px 0; border-radius: 6px; border: 1px solid {HANDLE_EDGE}; }}
QListWidget#playlist {{ background: transparent; border: none; outline: none; }}
QListWidget#playlist::item {{ padding: 8px 10px; border-radius: 8px; color: {TEXT}; }}
QListWidget#playlist::item:hover {{ background: {H(22)}; }}
QListWidget#playlist::item:selected {{ background: {ac(SEL_A)}; }}
QListWidget#recent {{ background: transparent; border: none; outline: none; }}
QListWidget#recent::item {{ padding: 9px 12px; border-radius: 9px; }}
QListWidget#recent::item:hover {{ background: {PANEL2}; }}
QListWidget#recent::item:selected {{ background: {PANEL2}; color: {TEXT}; }}
QCheckBox {{ spacing: 9px; }}
QCheckBox::indicator {{ width: 17px; height: 17px; border-radius: 5px; border: 1px solid {BORDER}; background: {PANEL2}; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: url(%CHECK%); }}
QLineEdit, QComboBox {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 9px; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{ background: {PANEL}; border: 1px solid {BORDER}; selection-background-color: {ACCENT}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {H(50)}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QTreeWidget#playlist {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px; outline: none;
                        alternate-background-color: {ALT}; padding: 4px; }}
QTreeWidget#playlist::item {{ padding: 5px 4px; border: none; }}
QTreeWidget#playlist::item:hover {{ background: {H(18)}; }}
QTreeWidget#playlist::item:selected {{ background: {ac(SEL_A)}; color: {FG}; }}
QHeaderView::section {{ background: {PANEL}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
                        padding: 6px 6px; font-size: 9pt; font-weight: 600; }}
QSplitter::handle {{ background: transparent; }}
QWidget#transport {{ background: {PANEL}; border-top: 1px solid {BORDER}; }}
QWidget#nowPanel {{ background: transparent; }}
QWidget#mini {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 14px; }}
QLabel#artist {{ font-size: 11.5pt; color: {TEXT}; }}
QLabel#album {{ font-size: 10pt; color: {MUTED}; }}
QLabel#format {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ac(70)}, stop:1 {ac2(70)});
                 border: 1px solid {H(40)}; border-radius: 7px; padding: 3px 9px; font-size: 9pt;
                 font-weight: 600; color: {FG}; }}
QLabel#hint {{ color: {MUTED}; font-size: 9pt; }}
QToolButton#on {{ background: {ac(70)}; border: none; border-radius: 8px; padding: 6px; }}
QToolButton#on:hover {{ background: {ac(110)}; }}
QToolButton#play {{ border: none; border-radius: 22px; padding: 10px;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT}, stop:1 {ACCENT2}); }}
QToolButton#play:hover {{ background: {ACCENT}; }}
QSlider::groove:horizontal {{ height: 4px; background: {H(50)}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {HANDLE}; width: 10px; height: 10px; margin: -4px 0; border-radius: 6px; border: 1px solid {HANDLE_EDGE}; }}
QDoubleSpinBox, QSpinBox {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px 6px; }}
QGroupBox {{ border: 1px solid {BORDER}; border-radius: 10px; margin-top: 12px; padding: 12px 10px 8px 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; color: {MUTED}; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 10px; top: -1px; }}
QTabBar::tab {{ background: transparent; padding: 7px 14px; color: {MUTED}; border: none; }}
QTabBar::tab:selected {{ color: {FG}; border-bottom: 2px solid {ACCENT}; }}
QTabBar#plTabs::tab {{ padding: 6px 8px 6px 12px; min-width: 60px; max-width: 220px; }}
QTabBar#plTabs::tab:hover:!selected {{ color: {TEXT}; }}
QTabBar#plTabs::close-button {{ image: url(%CLOSE%); subcontrol-position: right; border-radius: 4px;
                               margin-left: 4px; padding: 2px; }}
QTabBar#plTabs::close-button:hover {{ image: url(%CLOSE_HOT%); background: {H(30)}; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {H(50)}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""
