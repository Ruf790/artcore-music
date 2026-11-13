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
    pump(qapp, 0.3)
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
    assert len(s["tabs"][0]["tracks"]) == 3 and s["current"] == 1 and s["position"] >= 1.0
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


def _visible_rows(w):
    return [i for i in range(w.view.topLevelItemCount()) if not w.view.topLevelItem(i).isHidden()]


def test_search_clear_returns_to_track(qapp, mpvmod, media, data_dir):
    """Find a track far down, play it, clear the search: the list must show that track, not the top."""
    w = _win(mpvmod)
    w.resize(900, 360)
    folders = [os.path.join(media, n) for n in ("Stereo Album", "CUE Album", "Surround")]
    w.open_paths(folders * 6, add=False)                     # a long list (duplicates allowed on replace)
    pump(qapp, 0.6)
    last = w.pl.tracks[-1]
    w.search.setText(last.display_title().split()[0])
    assert pump(qapp, 1, lambda: len(_visible_rows(w)) < w.view.topLevelItemCount())
    it = w.items[last.uid]
    assert not it.isHidden()
    w.view.setCurrentItem(it)
    w._activate(it)
    assert w.engine.cur.uid == last.uid
    w.search.clear()
    pump(qapp, 0.3)
    assert len(_visible_rows(w)) == w.view.topLevelItemCount()
    assert w.view.currentItem() is it
    vr = w.view.visualItemRect(it)
    assert w.view.viewport().rect().intersects(vr), "the played track is not in view after clearing the search"
    w.close()


def test_stop_after_dups_and_settings(qapp, mpvmod, media, data_dir):
    w = _win(mpvmod)
    w.open_paths([os.path.join(media, "Stereo Album")])
    pump(qapp, 0.5)
    n = len(w.pl.tracks)
    w.add_paths([os.path.join(media, "Stereo Album")])            # the same files again: skipped
    assert len(w.pl.tracks) == n
    cur = w.engine.cur
    w.toggle_stop_after()
    assert w.engine.stop_after == cur.uid and w.engine.next_track(cur, auto=True) is None
    assert w.engine.next_track(cur, auto=False) is not None         # ⏭ still works
    w.toggle_stop_after()
    assert w.engine.stop_after is None
    w.set_sleep(15)
    assert 14 * 60 < w._sleep_left() <= 15 * 60
    w.set_sleep(0)
    assert w._sleep_left() == 0
    w._set_column("album", False)
    assert w.view.isColumnHidden(3) and "album" in w.cfg["hidden_cols"]
    w._set_column("album", True)
    assert not w.view.isColumnHidden(3)
    w.toggle_time_remaining()
    w._on_pos(10.0, 70.0)
    assert w.l_dur.text() == "−1:00"
    w.toggle_time_remaining()
    w.clear_playlist(confirm=False)
    assert not w.pl.tracks
    w.close()


def test_fade_pause(qapp, mpvmod, media, data_dir):
    w = _win(mpvmod, fade_pause=200)
    w.open_paths([os.path.join(media, "Stereo Album")])
    assert pump(qapp, 3, lambda: w._last_pos[0] > 0.2)
    w.engine.set_paused(True)
    assert w.engine.paused and w.engine.pfade is not None
    assert pump(qapp, 1, lambda: w.engine.pfade is None)
    assert w.engine.mpv.pause and w.engine.deck.factor == 1.0
    w.engine.set_paused(False)
    assert not w.engine.mpv.pause
    assert pump(qapp, 1, lambda: w.engine.pfade is None)
    assert w.engine.deck.factor == 1.0
    w.close()


def test_settings_dialog_tabs(qapp, data_dir):
    from music.dialogs import SettingsDialog
    cfg = config.load()
    d = SettingsDialog(cfg)
    assert d.tabs.count() == 3
    d.rows.setCurrentIndex(d.rows.findData("compact"))
    d.cols["artist"].setChecked(False)
    d.spins["seek_step"].setValue(10)
    d.checks["tray"].setChecked(True)
    d.accept()
    assert cfg["row_size"] == "compact" and cfg["hidden_cols"] == ["artist"]
    assert cfg["seek_step"] == 10 and cfg["tray"] is True


def test_waveform(qapp, mpvmod, media, data_dir):
    from music.waveform import PEAKS, Waveforms, key_of
    w = _win(mpvmod)
    w.open_paths([os.path.join(media, "Stereo Album")])
    assert pump(qapp, 8, lambda: len(w.seekbar.peaks) == PEAKS)
    first = w.engine.cur
    w.seekbar.grab()                                              # paints without errors
    w.next()
    assert pump(qapp, 8, lambda: w.engine.cur is not first and len(w.seekbar.peaks) == PEAKS)
    w.close()
    wf = Waveforms(mpvmod)                                         # from the disk cache now: at once
    got = []
    wf.ready.connect(lambda k, p: got.append(k))
    k = wf.request(first)
    assert got == [k] and k == key_of(first)
    wf.stop()


def test_internet_radio(qapp, mpvmod, media, data_dir, icy_server, tmp_path):
    url, stop = icy_server
    pls = tmp_path / "test.pls"
    pls.write_text(f"[playlist]\nnumberofentries=1\nFile1={url}\nTitle1=Test FM\nLength1=-1\n", encoding="utf-8")
    w = _win(mpvmod)
    w.open_paths([str(pls)])
    assert len(w.pl.tracks) == 1 and w.pl.tracks[0].title == "Test FM"
    assert w.items[w.pl.tracks[0].uid].text(4) == "эфир"
    assert pump(qapp, 10, lambda: w.engine.icy.startswith("DJ Test"))
    assert w.t_title.text().startswith("DJ Test") and w.t_artist.text() == "Test FM"
    assert w.t_next.text() == "" and not w.seekbar.peaks
    errors = []
    w.engine.error.connect(errors.append)
    stop()                                                         # the station goes off air
    assert pump(qapp, 25, lambda: w.engine.stopped)                 # 3 reconnects, then it stops
    assert any("reconnect 1/3" in e for e in errors)
    w.close()


def test_queue_play_next(qapp, mpvmod, media, data_dir):
    w = _win(mpvmod, confirm_clear=False)
    w.open_paths([os.path.join(media, "Stereo Album"), os.path.join(media, "Misc")])
    pump(qapp, 0.5)
    tr = w.pl.tracks
    assert w.engine.cur is tr[0]
    w.engine.enqueue([tr[4]])
    w.engine.enqueue([tr[2]], front=True)
    assert [x.uid for x in w.engine.queue] == [tr[2].uid, tr[4].uid]
    assert w.items[tr[2].uid].text(0) == "1" and w.items[tr[4].uid].text(0) == "2"
    assert "Далее" in w.t_next.text() and tr[2].display_title() in w.t_next.text()
    w.next()
    assert w.engine.cur is tr[2] and [x.uid for x in w.engine.queue] == [tr[4].uid]
    w.next()
    assert w.engine.cur is tr[4] and not w.engine.queue
    w.next()                                    # the queue is over: the playlist goes on after tr[0]
    assert w.engine.cur is tr[1]
    # queue from the context menu path, then remove a queued track from the playlist
    w.view.clearSelection()
    w.items[tr[3].uid].setSelected(True)
    w.queue_selected(front=True)
    assert w.engine.queue == [tr[3]]
    w.remove_selected()
    assert not w.engine.queue
    w.close()


def test_tabs_favorites_history(qapp, mpvmod, media, data_dir):
    w = _win(mpvmod, confirm_clear=False)
    w.open_paths([os.path.join(media, "Stereo Album")])
    pump(qapp, 0.4)
    first = w.pl
    p2 = w.new_tab("Jungle")
    assert w.pl is p2 and w.tabbar.count() == 2 and w.tabbar.tabText(1) == "Jungle"
    w.add_paths([os.path.join(media, "CUE Album")])                  # into the shown tab; first keeps playing
    assert len(p2.tracks) == 3 and w.engine.pl is first
    w.play_uid(p2.tracks[1].uid)
    assert w.engine.pl is p2 and w.engine.cur is p2.tracks[1]
    w.tabbar.setCurrentIndex(0)                                      # look at another tab: playback stays
    assert w.pl is first and w.engine.pl is p2
    w.next()
    assert w.engine.cur is p2.tracks[2]
    w.jump_to_current()
    assert w.pl is p2
    # favourites
    w.view.clearSelection()
    w.items[p2.tracks[0].uid].setSelected(True)
    w.toggle_fav_selected()
    assert w.favs.has(p2.tracks[0])
    w.open_library_tab("favorites")
    assert w.pl.kind == "favorites" and len(w.pl.tracks) == 1
    assert w.pl.tracks[0].title == p2.tracks[0].title
    w.open_library_tab("history")
    titles = [x.title for x in w.pl.tracks]
    assert titles[:2] == [p2.tracks[2].title, p2.tracks[1].title]     # newest first
    w.close()
    s = config.load_session()
    assert [x["name"] for x in s["tabs"]][:2] == [first.name, "Jungle"] and s["playing_tab"] == 1
    w2 = _win(mpvmod, confirm_clear=False)
    assert w2.restore_session()
    assert w2.tabbar.count() == 4 and w2.engine.pl is w2.pls[1] and w2.engine.cur.title == p2.tracks[2].title
    assert w2.favs.has(w2.pls[1].tracks[0])
    fav_tab = next(p for p in w2.pls if p.kind == "favorites")
    assert len(fav_tab.tracks) == 1                                  # library tabs are filled from the store
    w2.close_tab(1)                                                  # the playing tab: playback stops
    assert w2.tabbar.count() == 3 and w2.engine.cur is None
    w2.close()


def test_lyrics_panel(qapp, mpvmod, media, data_dir, tmp_path):
    import shutil
    d = tmp_path / "Album"
    d.mkdir()
    src = os.path.join(media, "Stereo Album", "01 - Первый трек.mp3")
    shutil.copy(src, d / "01 - Song.mp3")
    (d / "01 - song.LRC").write_text("[00:00.00]Intro\n[00:01.00]Line one\n[00:02.00]Line two\n", encoding="utf-8")
    shutil.copy(src, d / "02 - No lyrics.mp3")
    w = _win(mpvmod)
    w.open_paths([str(d)])
    assert w._lyr is not None and w._lyr.synced and w.lyrics.isVisible() and w.b_lyrics.isVisible()
    assert pump(qapp, 4, lambda: w.lyrics.cur == 1)                  # «Line one» at 1 s
    w.lyrics._clicked(w.lyrics.item(2))                              # click a line: seek there
    assert pump(qapp, 2, lambda: w._last_pos[0] >= 2.0 and w.lyrics.cur == 2)
    w.toggle_lyrics()
    assert not w.lyrics.isVisible()
    w.toggle_lyrics()
    w.next()
    assert w._lyr is None and not w.lyrics.isVisible() and not w.b_lyrics.isVisible()
    w.close()


def test_tag_editor(qapp, mpvmod, media, data_dir, tmp_path):
    import shutil
    import subprocess
    from music import meta
    from music.dialogs import TagEditorDialog
    d = tmp_path / "Untagged"
    d.mkdir()
    for n in ("01 - Ed Solo & Deekline - Hit The Road Jack", "02 - Benny Page - Dangerous"):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=1", "-map_metadata", "-1",
                        str(d / (n + ".mp3"))], check=True)
    shutil.copy(os.path.join(media, "Stereo Album", "01 - Первый трек.mp3"), d / "03 - tagged.mp3")
    w = _win(mpvmod)
    w.open_paths([str(d)])
    pump(qapp, 0.4)
    two = w.pl.tracks[:2]
    dlg = TagEditorDialog(two, w)
    dlg.pattern.setCurrentIndex(dlg.pattern.findData("track_artist_title"))
    dlg._from_name()
    assert len(dlg.guess) == 2
    dlg.edits["album"].setText("Welcome To The Jungle")
    dlg.touched.add("album")
    dlg.accept()
    assert not dlg.errors and len(dlg.changed) == 2
    tg = meta.read(two[0].path)
    assert (tg.track, tg.artist, tg.title, tg.album) == ("1", "Ed Solo & Deekline", "Hit The Road Jack",
                                                        "Welcome To The Jungle")
    assert two[1].artist == "Benny Page" and two[1].album == "Welcome To The Jungle"      # the playlist follows
    one = TagEditorDialog([w.pl.tracks[2]], w)                         # one file: the fields hold its tags
    assert one.edits["artist"].text() == "ArtCore Band"
    one.edits["genre"].setText("Jungle")
    one.touched.add("genre")
    one.accept()
    assert meta.read(w.pl.tracks[2].path).genre == "Jungle" and meta.read(w.pl.tracks[2].path).artist == "ArtCore Band"
    w.close()


def test_channel_meters_and_room(qapp, mpvmod, media, data_dir):
    w = _win(mpvmod, channels="5.1")
    w.open_paths([os.path.join(media, "Surround")])
    assert pump(qapp, 6, lambda: len(w.levels.ch) == 6 and max(w.levels.rms.values()) > -40)
    assert w.levels.ch == ["FL", "FC", "FR", "LFE", "SL", "SR"]
    assert w.meters.isVisible() and w.meter_timer.isActive()
    w.toggle_levels()
    assert w.levels_win.isVisible() and "FLAC" in w.levels_win.head.text()
    w.levels_win.room.grab()
    w.meters.grab()
    w.toggle_levels()
    assert not w.levels_win.isVisible()
    w.engine.set_paused(True)
    pump(qapp, 1.5)
    assert w.engine.levels() == []                                # paused: nothing on the meters
    w.stop()
    pump(qapp, 0.3)
    assert not w.meters.isVisible() and not w.meter_timer.isActive()
    w.cfg["meters"] = False
    w._meters_need()
    assert not w.meters.isVisible()
    w.close()


def test_upmix_meters_reach_the_rears(qapp, mpvmod, media, data_dir):
    w = _win(mpvmod, channels="5.1", upmix=True)
    w.open_paths([os.path.join(media, "Stereo Album")])
    assert pump(qapp, 6, lambda: len(w.levels.ch) == 6 and w.levels.rms.get("LFE", -99) > -60)
    w.close()


def test_mini_looks(qapp, mpvmod, media, data_dir):
    w = _win(mpvmod)
    w.open_paths([os.path.join(media, "Stereo Album")])
    assert pump(qapp, 4, lambda: w.engine.cur is not None and w.seekbar.peaks)
    w.toggle_mini()
    m = w.mini
    assert m.isVisible() and not m.strip and m.title.text()
    assert m.seek.peaks == w.seekbar.peaks                          # the same waveform
    assert m.cover.has_image()
    w.toggle_shuffle()
    assert m.b_shuffle.objectName() == "on"
    w.toggle_shuffle()
    v = w.vol.value()
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    ev = QWheelEvent(QPointF(20, 20), QPointF(20, 20), QPoint(0, 0), QPoint(0, 120), Qt.NoButton, Qt.NoModifier,
                     Qt.NoScrollPhase, False)
    QApplication.sendEvent(m, ev)
    assert w.vol.value() == min(100, v + 5) and m.time.text().endswith("%")
    m.grab()
    w.switch_mini_look()
    assert w.mini is not m and w.mini.strip and w.mini.isVisible() and w.mini.height() < 120
    assert w.mini.seek.peaks == w.seekbar.peaks
    w.mini.grab()
    _close_popup_later(300, pick="85%")
    w.mini_menu(w.mini.mapToGlobal(QPoint(10, 10)))
    _close_popup_later(300)
    w.mini_menu(w.mini.mapToGlobal(QPoint(10, 10)))
    w.mini.toggle_pin()
    assert not w.cfg["mini_on_top"]
    w.mini.toggle_pin()
    w.toggle_mini()
    assert w.isVisible() and not w.mini.isVisible()
    w.cfg["mini_style"] = "card"                                   # changed in the settings while hidden
    w.toggle_mini()
    assert not w.mini.strip
    w.toggle_mini()
    w.close()
