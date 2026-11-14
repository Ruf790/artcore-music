"""Skins: every palette is complete, readable and builds a style sheet; the config keeps only known skins."""
import pytest

from music import config, themes

KEYS = {"dark", "ru", "en", "bg", "panel", "panel2", "border", "text", "muted", "accent", "accent2", "fg",
        "accent_text", "star", "star_off", "alt", "ph1", "ph2", "ph_icon", "wave", "spk", "mini_cover",
        "mini_plain", "toast"}


def _lum(hex_):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def _ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_there_are_light_skins():
    light = [k for k, v in themes.THEMES.items() if not v["dark"]]
    assert len(light) >= 4 and themes.ORDER[0] == themes.DEFAULT == "dark"
    assert set(themes.ORDER) == set(themes.THEMES)


@pytest.mark.parametrize("key", themes.ORDER)
def test_palette_is_complete_and_readable(key):
    th = themes.THEMES[key]
    assert KEYS <= set(th)
    assert _ratio(th["text"], th["bg"]) >= 7 and _ratio(th["text"], th["panel"]) >= 7
    assert _ratio(th["muted"], th["bg"]) >= 3.5 and _ratio(th["muted"], th["panel"]) >= 3.5
    assert _ratio(th["accent_text"], th["panel"]) >= 4.5      # the playing row
    assert _ratio(th["fg"], th["bg"]) >= 7                    # icons on the transport bar
    assert _ratio("#ffffff", th["accent"]) >= 3.5             # white on the play button / primary button
    assert _ratio("#ffffff", th["accent2"]) >= 3.5


@pytest.mark.parametrize("key", themes.ORDER)
def test_style_sheet_builds(qapp, key):
    from music import style
    style.apply(qapp, key)
    try:
        qss = style.stylesheet()
        assert "%CHECK%" not in qss and "%CLOSE" not in qss          # the icon placeholders are filled in
        assert style.CURRENT == key and style.IS_DARK == themes.THEMES[key]["dark"]
        assert themes.THEMES[key]["bg"] in qss and themes.THEMES[key]["panel"] in qss
        assert style.swatch(key).pixmap(20, 20).toImage().pixelColor(10, 10).alpha() > 0
    finally:
        style.apply(qapp, "dark")


def test_config_keeps_known_skins(data_dir):
    assert config.load()["theme"] == "dark"
    cfg = config.load()
    cfg["theme"] = "mint"
    config.save(cfg)
    assert config.load()["theme"] == "mint"
    cfg["theme"] = "no-such-skin"
    config.save(cfg)
    assert config.load()["theme"] == "dark"
