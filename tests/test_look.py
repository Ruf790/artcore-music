"""1.7: playlist groups, colours from the cover, the new light skins, the row tooltip, up next, the transport."""
import os

from conftest import pump
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage

from music import config, covercolor, style, themes
from music.playlist import Track, groups, stamp


def _win(mpvmod, **over):
    from music.window import MainWindow
    cfg = config.load()
    cfg.update(media_keys=False, check_updates=False)
    cfg.update(over)
    w = MainWindow(mpvmod, cfg)
    w.show()
    return w


def _png(color: str, size: int = 64, second: str | None = None) -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    img = QImage(size, size, QImage.Format_RGB32)
    img.fill(QColor(color))
    if second:
        for y in range(size // 3):
            for x in range(size):
                img.setPixelColor(x, y, QColor(second))
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


# ── groups ─────────────────────────────────────────────────────────────────
def test_groups_split_the_list():
    tr = stamp([
        Track("http://radio.one/stream"), Track("http://radio.two/stream"),
        Track("/m/loose/a.mp3", title="A"), Track("/m/loose/b.mp3", title="B"),
        Track("/m/Album/01.flac", album="Album", number="1"), Track("/m/Album/02.flac", album="Album", number="2"),
        Track("/m/Other/01.flac", album="Other"),                 # one track of an album: a loose track
        Track("/m/c.mp3", title="C"),
    ])
    gs = groups(tr)
    assert [(g.kind, len(g.tracks)) for g in gs] == [("radio", 2), ("singles", 2), ("album", 2), ("singles", 2)]
    assert sum(len(g.tracks) for g in gs) == len(tr)
    assert gs[2].album() == "Album" and gs[2].first is tr[4]
    assert len({g.key for g in gs}) == len(gs)
    assert groups([]) == []


def test_group_artist_and_year():
    tr = stamp([Track("/m/X/1.flac", album="X", artist="A1", albumartist="VA", year="2014"),
                Track("/m/X/2.flac", album="X", artist="A2", albumartist="VA")])
    g = groups(tr)[0]
    assert g.artist() == "VA" and g.year() == "2014"
    tr = stamp([Track("/m/Y/1.flac", album="Y", artist="Same"), Track("/m/Y/2.flac", album="Y", artist="Same")])
    assert groups(tr)[0].artist() == "Same"


def test_groups_in_the_window(qapp, mpvmod, media, data_dir):
    w = _win(mpvmod)
    w.open_paths([os.path.join(media, "Misc"), os.path.join(media, "Stereo Album")])
    pump(qapp, 4, lambda: any(hd.kind == "album" for hd in w.view.heads.values()))
    kinds = sorted(hd.kind for hd in w.view.heads.values())
    assert "album" in kinds and "singles" in kinds
    assert w.view.isColumnHidden(3)                                 # the album is in the heads
    album = next(g for g in w._groups if g.kind == "album")
    hd = w.view.heads[album.first.uid]
    assert hd.title == "Test Album" and "2024" in hd.sub and "MP3" in hd.sub
    # a click on the head folds the group: only its first row stays, as the head
    first = w.items[album.first.uid]
    r = w.view.visualItemRect(first)
    assert w.view.head_at(QPoint(r.left() + 30, r.top() + 10)) is hd
    assert w.view.head_at(QPoint(r.left() + 30, r.bottom() - 2)) is None     # the row under the head
    w.toggle_group(hd.key)
    assert all(w.items[x.uid].isHidden() for x in album.tracks[1:]) and not first.isHidden()
    assert w.view.heads[album.first.uid].folded
    w.toggle_group(hd.key)
    assert not any(w.items[x.uid].isHidden() for x in album.tracks)
    # searching shows a plain list; clearing it brings the groups back
    w._filter("first")
    assert not w.view.heads
    w._filter("")
    assert w.view.heads
    # the playing track of a folded group unfolds it
    w.toggle_group(hd.key, True)
    w.engine.play(album.tracks[1])
    pump(qapp, 1.0, lambda: not w.items[album.tracks[1].uid].isHidden())
    assert not w.items[album.tracks[1].uid].isHidden()
    # groups off: no heads, the album column is back
    w.cfg["groups"] = False
    w._apply_view_options()
    assert not w.view.heads and not w.view.isColumnHidden(3)
    w.close()


# ── colours from the cover ─────────────────────────────────────────────────
def test_cover_colours_follow_the_cover():
    data = _png("#e8590c", second="#0ca678")                      # orange with a green band
    for key in themes.ORDER:
        th = themes.THEMES[key]
        got = covercolor.pick(data, th["dark"], th["panel"])
        assert got is not None
        a, a2, text = got
        assert covercolor.ratio((255, 255, 255), covercolor.hex_rgb(a)) >= 3.5
        assert covercolor.ratio((255, 255, 255), covercolor.hex_rgb(a2)) >= 3.5
        assert covercolor.ratio(covercolor.hex_rgb(text), covercolor.hex_rgb(th["panel"])) >= 4.5
        h1 = QColor(a).hueF()
        assert 0.0 <= h1 <= 0.12                                    # orange stays orange
        assert 0.35 <= QColor(a2).hueF() <= 0.55                    # and the second colour is the green
    assert covercolor.pick(_png("#808080"), True, "#171a21") is None      # grey cover: the skin's own colours
    assert covercolor.pick(b"", True, "#171a21") is None
    assert covercolor.pick(b"not an image", True, "#171a21") is None


def test_cover_colours_in_the_window(qapp, mpvmod, media, data_dir):
    w = _win(mpvmod, channels="5.1")
    try:
        w._cover_colors(_png("#1971c2", second="#e64980"))
        assert style.COVER is not None and style.ACCENT == style.COVER[0]
        assert style.COVER[0] in qapp.styleSheet()
        assert w.now_panel.glow
        w._cover_colors(None)
        assert style.COVER is None and style.ACCENT == themes.THEMES["dark"]["accent"]
        assert not w.now_panel.glow
        w.cfg["cover_colors"] = False
        w._cover_colors(_png("#1971c2", second="#e64980"))
        assert style.COVER is None
        # a skin switch recomputes the colours for the new skin
        w.cfg["cover_colors"] = True
        w.open_paths([os.path.join(media, "Surround")])          # folder.jpg: a purple → blue picture
        pump(qapp, 4, lambda: style.COVER is not None)
        assert style.COVER is not None
        w.set_theme("snow")
        assert style.CURRENT == "snow" and style.COVER is not None
        assert covercolor.ratio(covercolor.hex_rgb(style.ACCENT_TEXT), covercolor.hex_rgb(style.PANEL)) >= 4.5
    finally:
        w.set_theme("dark")
        style.set_cover(None)
        w.close()


def test_new_light_skins():
    for key, ru, en in (("sky", "Небо", "Sky"), ("lavender", "Лаванда", "Lavender"),
                        ("peach", "Персик", "Peach"), ("snow", "Снег", "Snow")):
        th = themes.THEMES[key]
        assert not th["dark"] and th["ru"] == ru and th["en"] == en and key in themes.ORDER
    assert len([k for k in themes.ORDER if not themes.THEMES[k]["dark"]]) == 8


# ── small things ───────────────────────────────────────────────────────────
def test_row_tooltip_wraps_the_path():
    from music.window import path_tip
    tip = path_tip(Track(r"D:/mp3/HipHop/Drum'N Bass/VA Ed Solo and Deekline/Welcome To The Jungle Vol. 2/04. Dj Nut Nut.flac"))
    assert "<br>" in tip and "<b>04. Dj Nut Nut.flac</b>" in tip and "max-width" in tip
    assert "/\u200b" in tip                                         # it may break at the folders
    assert "&#x27;" in tip or "&#39;" in tip                         # escaped
    assert path_tip(Track("http://radio.one/stream")) == "http://radio.one/stream"


def test_transport_title_and_up_next(qapp, mpvmod, media, data_dir):
    w = _win(mpvmod, confirm_clear=False)
    try:
        row = [w.b_shuffle, w.b_stop, w.b_prev, w.b_play, w.b_next, w.b_repeat]
        xs = [b.mapTo(w, b.rect().center()).x() for b in row]
        assert xs == sorted(xs)                                     # ⏹ sits with the other buttons
        assert abs(w.b_play.mapTo(w, w.b_play.rect().center()).x() - w.width() / 2) < 80
        long = "A very long title " * 8
        w.t_title.setText(long)
        assert w.t_title.text() == long and w.t_title.toolTip() == long
        assert QLabelText(w.t_title).endswith("…")
        w.open_paths([os.path.join(media, "Stereo Album"), os.path.join(media, "Misc")])
        pump(qapp, 1.0)
        tr = w.pl.tracks
        assert w.engine.cur is tr[0]
        txt = w.t_next.text()
        assert "Далее" in txt and all(tr[i].display_title() in txt for i in (1, 2, 3))
        assert tr[4].display_title() not in txt                     # three, not more
    finally:
        w.close()


def QLabelText(label):
    from PySide6.QtWidgets import QLabel
    return QLabel.text(label)


def test_meters_rows_follow_the_channels(qapp):
    from music.widgets import ChannelMeters, LevelState
    st = LevelState()
    m = ChannelMeters(st)
    m.resize(300, m.height())
    h6 = m.height()
    st.ch = ["FL", "FR"]
    m.grab()
    assert m.height() < h6
    st.ch = ["FL", "FR", "FC", "LFE", "BL", "BR", "SL", "SR"]
    m.grab()
    assert m.height() > h6
