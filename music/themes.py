"""Skins (colour schemes). Pure data, no Qt: config.py validates the saved name against it, style.py builds the
style sheet and the palette from it.

Keys of a skin
    dark          dark skin (window title bar, scroll bars, how translucent overlays are drawn)
    ru / en       the name in the settings and in the menu
    bg            window background                      panel / panel2   cards, fields, buttons
    border        thin lines                             text / muted     main and secondary text
    accent/accent2  the ArtCore gradient (play button, progress, meters)
    fg            icons and text on the window chrome (the transport bar, the mini player)
    accent_text   the playing row, the lyric line being sung
    star / star_off  favourite mark on / off             alt            alternate row of the playlist
    ph1 / ph2 / ph_icon  the cover placeholder (gradient and note)
    wave          the played part of the waveform        spk            the listener / speaker body in the room view
    mini_cover    (r, g, b, a) laid over the blurred cover in the mini player
    mini_plain    the same when there is no cover
    toast         (r, g, b, a) background of the pop-up message
"""
from __future__ import annotations

DEFAULT = "dark"

THEMES: dict[str, dict] = {
    # ── the original skin ────────────────────────────────────
    "dark": dict(
        dark=True, ru="Тёмный (ArtCore)", en="Dark (ArtCore)",
        bg="#0f1115", panel="#171a21", panel2="#1f232c", border="#2b303b", text="#e9ecef", muted="#9aa3b2",
        accent="#0d6efd", accent2="#6f42c1",
        fg="#ffffff", accent_text="#8fb8ff", star="#f5c518", star_off="#3a4152", alt="#1a1d25",
        ph1="#1c2230", ph2="#241c35", ph_icon="#3d4660", wave="#ffffff", spk="#3a4152",
        mini_cover=(10, 12, 18, 150), mini_plain=(10, 12, 18, 90), toast=(23, 26, 33, 235),
    ),
    # ── light skins ──────────────────────────────────────────
    "light": dict(                                   # cool white, the ArtCore blue → purple
        dark=False, ru="Светлый", en="Light",
        bg="#f3f5fa", panel="#ffffff", panel2="#eceff6", border="#d8deea", text="#1c2230", muted="#667085",
        accent="#0d6efd", accent2="#6f42c1",
        fg="#1c2230", accent_text="#0b5ed7", star="#f59f00", star_off="#c5cce0", alt="#f7f9fd",
        ph1="#dde5f4", ph2="#e6dcf3", ph_icon="#9aa8c8", wave="#0d6efd", spk="#b9c2d8",
        mini_cover=(255, 255, 255, 168), mini_plain=(255, 255, 255, 70), toast=(255, 255, 255, 240),
    ),
    "paper": dict(                                   # warm paper, terracotta → raspberry
        dark=False, ru="Бумага", en="Paper",
        bg="#f5efe3", panel="#fffcf5", panel2="#eee6d5", border="#dccfb4", text="#2b241a", muted="#7b6f5a",
        accent="#d9480f", accent2="#c2255c",
        fg="#2b241a", accent_text="#b8400b", star="#e8a317", star_off="#cfc3a8", alt="#faf5e9",
        ph1="#eadfc6", ph2="#efd9d0", ph_icon="#b9a982", wave="#d9480f", spk="#c9bb9c",
        mini_cover=(255, 250, 238, 170), mini_plain=(255, 250, 238, 80), toast=(255, 252, 245, 242),
    ),
    "mint": dict(                                    # fresh mint, green → teal
        dark=False, ru="Мята", en="Mint",
        bg="#eaf5f1", panel="#ffffff", panel2="#dfefe9", border="#c8e0d6", text="#12302a", muted="#58786f",
        accent="#0e9272", accent2="#0b6e8a",
        fg="#12302a", accent_text="#0a7a5e", star="#f2a60d", star_off="#bcd5cb", alt="#f4faf8",
        ph1="#d3eadf", ph2="#cfe4ee", ph_icon="#8bb3a4", wave="#0e9272", spk="#b4cfc4",
        mini_cover=(244, 252, 249, 168), mini_plain=(244, 252, 249, 70), toast=(255, 255, 255, 240),
    ),
    "sakura": dict(                                  # soft pink, raspberry → violet
        dark=False, ru="Сакура", en="Sakura",
        bg="#fbeff4", panel="#ffffff", panel2="#f6e2ea", border="#ebcdd9", text="#33202a", muted="#876778",
        accent="#d6336c", accent2="#9c36b5",
        fg="#33202a", accent_text="#b0245a", star="#f08c00", star_off="#e0c3cf", alt="#fdf6f9",
        ph1="#f5dde7", ph2="#eadcf3", ph_icon="#c9a0b4", wave="#d6336c", spk="#dcbfcc",
        mini_cover=(255, 246, 250, 170), mini_plain=(255, 246, 250, 75), toast=(255, 255, 255, 242),
    ),
    "sky": dict(                                     # pale sky, blue → turquoise
        dark=False, ru="Небо", en="Sky",
        bg="#eef5fc", panel="#ffffff", panel2="#e2edf9", border="#cddcef", text="#14263d", muted="#55698a",
        accent="#1971c2", accent2="#0c8599",
        fg="#14263d", accent_text="#1864ab", star="#f59f00", star_off="#c3d2e6", alt="#f5f9fe",
        ph1="#d8e7f7", ph2="#d3eef2", ph_icon="#8fa9c9", wave="#1971c2", spk="#b8cbe3",
        mini_cover=(244, 249, 255, 168), mini_plain=(244, 249, 255, 70), toast=(255, 255, 255, 240),
    ),
    "lavender": dict(                                # lavender, violet → raspberry
        dark=False, ru="Лаванда", en="Lavender",
        bg="#f3f0fb", panel="#ffffff", panel2="#e9e3f7", border="#d9d0ef", text="#241b3d", muted="#665c8a",
        accent="#7048e8", accent2="#c2255c",
        fg="#241b3d", accent_text="#5f3dc4", star="#f08c00", star_off="#d3cae9", alt="#f9f7fe",
        ph1="#e6def7", ph2="#f3dcea", ph_icon="#a99bd0", wave="#7048e8", spk="#cfc4ea",
        mini_cover=(249, 246, 255, 170), mini_plain=(249, 246, 255, 72), toast=(255, 255, 255, 242),
    ),
    "peach": dict(                                   # warm peach, orange → pink
        dark=False, ru="Персик", en="Peach",
        bg="#fdf1ea", panel="#fffaf6", panel2="#f9e3d6", border="#efcfbd", text="#3a2218", muted="#80594a",
        accent="#d9480f", accent2="#c2255c",
        fg="#3a2218", accent_text="#b8400b", star="#e8a317", star_off="#ebcbbb", alt="#fff7f2",
        ph1="#f8dccb", ph2="#f6d5df", ph_icon="#c99a85", wave="#e8590c", spk="#e8c6b4",
        mini_cover=(255, 247, 241, 170), mini_plain=(255, 247, 241, 76), toast=(255, 252, 248, 242),
    ),
    "snow": dict(                                    # neutral white, graphite (colour comes from the covers)
        dark=False, ru="Снег", en="Snow",
        bg="#f6f6f4", panel="#ffffff", panel2="#ececea", border="#dadad6", text="#16171a", muted="#5f6168",
        accent="#25262b", accent2="#495057",
        fg="#16171a", accent_text="#16171a", star="#f59f00", star_off="#d0d0cc", alt="#fafaf9",
        ph1="#e6e6e3", ph2="#dededb", ph_icon="#a3a3a0", wave="#25262b", spk="#cfcfcb",
        mini_cover=(250, 250, 248, 172), mini_plain=(250, 250, 248, 74), toast=(255, 255, 255, 242),
    ),
}

ORDER = ["dark", "light", "paper", "mint", "sakura", "sky", "lavender", "peach", "snow"]


def valid(name) -> str:
    return name if name in THEMES else DEFAULT
