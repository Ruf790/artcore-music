"""The window under Xvfb/offscreen: opening, playing, mini player, menus, playlist editing, session."""
import os

from conftest import pump
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from music import config


def _win(mpvmod, **over):
    from music.window import MainWindow
    cfg = config.load()
    cfg.update(media_keys=False, check_updates=False)
    cfg.update(over)
    w = MainWindow(mpvmod, cfg)
    w.show()
    return w


def _close_popup_later(ms=300, pick=None):
    """QMenu.exec can't be patched: close the open menu from a timer (optionally trigger an action first)."""
    def go():
        m = QApplication.activePopupWidget()
        if m is not None:
            if pick:
                for a in m.actions():
                    if pick in a.text():
                        a.trigger()
                        break
            m.close()
    QTimer.singleShot(ms, go)


def test_open_play_and_format(qapp, mpvmod, media, data_dir):
    w = _win(mpvmod, channels="5.1")
    w.open_paths([os.path.join(media, "Surround")])
    assert pump(qapp, 6, lambda: w.t_format.isVisible() and "→" in w.t_format.text())
    assert w.t_format.text().startswith("FLAC 24/96 5.1 → PCM 6")
    assert w.t_title.text() == "FLAC 5.1" and w.t_artist.text() == "Surround Test"
    assert w.cover.has_image()                                   # folder.jpg
    assert w.view.topLevelItemCount() == len(w.pl.tracks) == 5
    w.close()


def test_menus_mini_and_edit(qapp, mpvmod, media, data_dir):
    w = _win(mpvmod)
    w.open_paths([os.path.join(media, "Stereo Album"), os.path.join(media, "CUE Album")])
    pump(qapp, 1.0)
    _close_popup_later()
    w._main_menu()
    _close_popup_later()
    w._list_menu(w.view.visualItemRect(w.view.topLevelItem(0)).center())
    w.cycle_repeat()
    assert w.pl.repeat == "all"
    w.toggle_shuffle()
    assert w.pl.shuffle
    w.toggle_shuffle()
    w.toggle_mini()
    assert w.mini.isVisible() and not w.isVisible()
    w.toggle_mini()
    assert w.isVisible() and not w.mini.isVisible()
    # remove the playing track: playback goes on, the list shrinks
    w.view.clearSelection()
    w.items[w.engine.cur.uid].setSelected(True)
    w.remove_selected()
    assert len(w.pl.tracks) == 5
    w.search.setText("кукушка")
    visible = [i for i in range(w.view.topLevelItemCount()) if not w.view.topLevelItem(i).isHidden()]
    assert len(visible) == 1
    w.close()


def test_session_resume(qapp, mpvmod, media, data_dir):
    w = _win(mpvmod)
    w.open_paths([os.path.join(media, "CUE Album")])
    pump(qapp, 0.6)
    w.next()
    pump(qapp, 0.8)
    w.engine.seek(1.5)
    pump(qapp, 0.3)
    w.close()
    s = config.load_session()
    assert len(s["tracks"]) == 3 and s["current"] == 1 and s["position"] >= 1.0
    w2 = _win(mpvmod)
    assert w2.restore_session()
    assert pump(qapp, 3, lambda: w2.engine.cur is not None and w2._last_pos[0] >= 1.0)
    assert w2.engine.cur.title == "Звезда по имени Солнце" and w2.engine.paused
    w2.close()


def test_dialogs_build(qapp, mpvmod, data_dir):
    from music.dialogs import EqualizerDialog, KeysDialog, SettingsDialog, SoundDialog, SpeakerTestDialog
    cfg = config.load()
    for d in (SoundDialog(cfg, [("auto", "Auto"), ("wasapi/{x}", "Speakers (Sound Blaster Z)")]),
              EqualizerDialog(cfg), KeysDialog(), SettingsDialog(cfg)):
        d.show()
        pump(qapp, 0.05)
        d.reject()
    t = SpeakerTestDialog(mpvmod, cfg)
    t.show()
    t.play_one("LFE")
    assert pump(qapp, 2, lambda: (t.m.audio_params or {}).get("channel-count") == 6)
    t.center.set_value(3.0)
    assert cfg["center_db"] == 3.0
    t.done(0)
