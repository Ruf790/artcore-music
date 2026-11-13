"""libmpv with ao=null: gapless order, CUE boundaries without reloads, 5.1 output, crossfade."""
import os
import time

from conftest import pump

from music import config, playlist
from music.engine import Engine


def _engine(mpvmod, media, folders, **cfg_over):
    cfg = config.load()
    cfg.update(cfg_over)
    pl = playlist.Playlist()
    pl.add(playlist.expand([os.path.join(media, f) for f in folders]))
    for t in pl.tracks:
        playlist.fill_tags(t)
    e = Engine(mpvmod, cfg, pl)
    return e, pl


def test_gapless_and_cue(qapp, mpvmod, media, data_dir):
    e, pl = _engine(mpvmod, media, ["CUE Album", "Stereo Album"], channels="5.1")
    for d in e.decks:
        d.m.speed = 4
    log, fmts, done = [], [], []
    e.track_changed.connect(lambda t: log.append(t.display_title()))
    e.format_changed.connect(lambda f: fmts.append((f["channels"], f["out_channels"])))
    e.finished.connect(lambda: done.append(1))
    loads = []
    e.decks[0].loaded.connect(lambda d: loads.append(d.m.path))
    e.play(pl.tracks[0])
    assert pump(qapp, 20, lambda: done)
    assert log == ["Группа крови", "Звезда по имени Солнце", "Кукушка", "Первый трек", "Second Song", "Третий"]
    assert len(loads) == 4                                       # the CUE image loaded once
    assert (2, 6) in fmts                                        # stereo → 6-channel output in 5.1 mode
    e.shutdown()


def test_surround_formats(qapp, mpvmod, media, data_dir):
    e, pl = _engine(mpvmod, media, ["Surround"], channels="5.1", center_db=3)
    for d in e.decks:
        d.m.speed = 4
    infos, done = {}, []
    e.format_changed.connect(lambda f: infos.__setitem__(f["codec"], f) if f["codec"] else None)
    e.finished.connect(lambda: done.append(1))
    e.play(pl.tracks[0])
    assert pump(qapp, 25, lambda: done)
    for codec in ("flac", "ac3", "dts", "truehd"):
        assert infos[codec]["out_channels"] == 6, codec
        assert "pan=" in infos[codec]["af"], codec
    assert infos["flac"]["rate"] in (96000, 48000)
    e.shutdown()


def test_crossfade(qapp, mpvmod, media, data_dir):
    e, pl = _engine(mpvmod, media, ["Stereo Album"], crossfade=1.5, xfade_album=False)
    both = []

    def tick():
        if len(e.decks) == 2 and all(d.track is not None for d in e.decks):
            both.append((round(float(e.decks[0].m.volume), 1), round(float(e.decks[1].m.volume), 1)))
    from PySide6.QtCore import QTimer
    tm = QTimer()
    tm.timeout.connect(tick)
    tm.start(100)
    log, done = [], []
    e.track_changed.connect(lambda t: log.append((time.monotonic(), t.display_title())))
    e.finished.connect(lambda: done.append(1))
    e.play(pl.tracks[0])
    assert pump(qapp, 15, lambda: done)
    tm.stop()
    assert [x[1] for x in log] == ["Первый трек", "Second Song", "Третий"]
    assert 2.0 < log[1][0] - log[0][0] < 3.2                     # 4 s track, 1.5 s overlap
    assert both and any(0 < a < 80 and 0 < b < 80 for a, b in both)   # both decks heard at once
    e.shutdown()


def test_xfade_off_within_album(qapp, mpvmod, media, data_dir):
    e, pl = _engine(mpvmod, media, ["Stereo Album"], crossfade=2, xfade_album=True)
    for d in e.decks:
        d.m.speed = 4
    done = []
    e.finished.connect(lambda: done.append(1))
    e.play(pl.tracks[0])
    assert pump(qapp, 10, lambda: done)
    assert len(e.decks) == 1                                     # one album: gapless, the second deck never made
    e.shutdown()


def test_late_events_after_shutdown(qapp, mpvmod, media, data_dir):
    """Queued mpv events that arrive after the window closed must not touch the destroyed handle."""
    import os
    from conftest import pump
    from music import config
    from music.engine import Engine
    from music.playlist import Playlist, expand
    cfg = config.load()
    pl = Playlist()
    pl.add(expand([os.path.join(media, "Stereo Album")]))
    e = Engine(mpvmod, cfg, pl)
    e.play(pl.tracks[0])
    pump(qapp, 0.3)
    d = e.deck
    e.shutdown()
    assert not d.alive
    e._on_loaded(d)                       # what a queued file-loaded would do
    e._on_ended(d, "eof", 0)
    e._on_prop(d, "audio-params", {"channel-count": 2})
    e.requeue()
    e.play(pl.tracks[1])
    e.set_paused(True)
    e.seek(1.0)
    d.queue(pl.tracks[1])
    pump(qapp, 0.3)
