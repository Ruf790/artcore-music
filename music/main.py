"""Entry point: one player window; files opened from Explorer go to the running copy.
ArtCoreMusic.exe [--add] [files / folders / .cue / .m3u …]   --add appends instead of replacing the playlist."""
from __future__ import annotations

import locale
import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_ID, APP_TITLE, VERSION, config, winint
from .i18n import set_lang, t

SERVER_NAME = "ArtCoreMusic-" + (os.environ.get("USERNAME") or os.environ.get("USER") or "user")


def _send_to_running(paths: list[str], add: bool) -> bool:
    s = QLocalSocket()
    s.connectToServer(SERVER_NAME)
    if not s.waitForConnected(400):
        return False
    lines = (["--add"] if add else []) + [os.path.abspath(p) for p in paths]
    s.write(("\n".join(lines) if paths else "--show").encode("utf-8"))
    s.waitForBytesWritten(1000)
    s.disconnectFromServer()
    return True


def load_mpv():
    winint.prepare_libmpv()
    locale.setlocale(locale.LC_NUMERIC, "C")        # libmpv refuses to start with a non-C LC_NUMERIC
    import mpv
    return mpv


def selftest() -> int:
    """CI: the built exe imports everything, finds libmpv, builds the window and pushes test signals
    (stereo and 5.1 WAV) through every audio filter we use (upmix, levels, 7.1 → 5.1, EQ). Result in %TEMP%."""
    import tempfile
    import time
    import traceback
    out = os.path.join(tempfile.gettempdir(), "artcore_music_selftest.txt")
    lines = []
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("ARTCORE_MUSIC_AO", "null")
        os.environ.setdefault("ARTCORE_MUSIC_DATA", os.path.join(tempfile.gettempdir(), "artcore_music_selftest"))
        app = QApplication(sys.argv)
        mpvmod = load_mpv()
        locale.setlocale(locale.LC_NUMERIC, "C")
        cfg = config.load()
        cfg.update(resume=False, media_keys=False, check_updates=False, channels="5.1", upmix=True,
                   center_db=2.0, lfe_db=-2.0, eq=[3, 2, 1, 0, 0, 0, 0, 1, 2, 3])
        from . import testtone
        from .window import MainWindow
        win = MainWindow(mpvmod, cfg)
        win.show()
        for _ in range(10):
            app.processEvents()
        lines.append(f"OK {VERSION} {win.engine.mpv.mpv_version} ffmpeg {win.engine.mpv.ffmpeg_version}")
        folder = os.path.join(tempfile.gettempdir(), "artcore_music_selftest_media")
        os.makedirs(folder, exist_ok=True)
        stereo = os.path.join(folder, "stereo.wav")
        n = testtone.RATE * 3 // 2
        testtone.write_wav(stereo, [[0.2] * n, [-0.2] * n], mask=0x3)
        six = testtone.signal_file("FC", folder)
        eight = os.path.join(folder, "eight.wav")
        testtone.write_wav(eight, [[0.1] * n for _ in range(8)], mask=0x63F)        # 7.1
        win.open_paths([stereo, six, eight])
        seen = {}
        t0 = time.monotonic()
        while time.monotonic() - t0 < 12 and len(seen) < 3:
            app.processEvents()
            d = win.engine.deck
            ap, op = d.get("audio-params", {}) or {}, d.get("audio-out-params", {}) or {}
            name = os.path.basename(str(d.get("path", "") or ""))
            if name and name not in seen and op.get("channel-count") and d.af and d.get("time-pos", 0):
                seen[name] = (int(ap.get("channel-count") or 0), int(op["channel-count"]), d.af)
            time.sleep(0.02)
        for k, v in seen.items():
            lines.append(f"{k}: {v[0]} ch → {v[1]} ch, af={v[2]}")
        want = {"stereo.wav": (2, "surround"), "test_FC.wav": (6, "pan="), "eight.wav": (8, "aformat")}
        if len(seen) < 3 or any(v[1] != 6 for v in seen.values()) or \
                any(seen.get(k, (0, 0, ""))[0] != c or f not in seen.get(k, (0, 0, ""))[2] for k, (c, f) in want.items()):
            raise RuntimeError("audio chain check failed: " + repr(seen))
        if winint.IS_WIN:                        # Windows media controls: the card shows what we set
            sm = win.smtc
            if sm is None or not sm.started.wait(10) or not sm.ok:
                raise RuntimeError(f"SMTC failed: {getattr(sm, 'error', 'off')}")
            from PySide6.QtCore import QBuffer, QIODevice
            from .widgets import placeholder_cover
            buf = QBuffer()
            buf.open(QIODevice.WriteOnly)
            placeholder_cover(256).save(buf, "PNG")
            cover = bytes(buf.data())
            sm.set_track("Selftest title", "ArtCore", "Selftest album", cover, 3)
            sm.set_status("playing")
            sm.set_timeline(12.0, 180.0)
            got = sm.probe(10)
            lines.append(f"SMTC: {got} {sm.error}".strip())
            if got.get("title") != "Selftest title" or not got.get("thumb") or got.get("status") != 3:
                raise RuntimeError(f"SMTC did not take the track: {got} {sm.error}")
        tb = winint.ThumbBar()
        if winint.IS_WIN:
            ok = tb._create()
            icon = win._thumb_icons_for()
            lines.append(f"taskbar list: {ok}, icons: {all(icon)}")
            if not ok or not all(icon):
                raise RuntimeError("ITaskbarList3 / HICON failed")
        win.close()
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return 0
    except Exception:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\nFAIL\n" + traceback.format_exc())
        return 1


def gui_thread_gc(app) -> None:
    """Python's cyclic GC runs in whatever thread allocates — mpv's event thread or the tag reader too. If it
    frees a closed dialog or window there, Qt destroys a widget outside the GUI thread and corrupts memory
    (rare random crashes). So: automatic GC off, collected by a timer in the GUI thread instead."""
    import gc
    gc.disable()
    timer = QTimer(app)
    timer.setInterval(2000)
    timer.timeout.connect(lambda: gc.collect(0) if gc.get_count()[0] > 700 else None)
    timer.start()
    full = QTimer(app)
    full.setInterval(30000)
    full.timeout.connect(gc.collect)
    full.start()


def main() -> int:
    args = sys.argv[1:]
    if "--selftest" in args:
        return selftest()
    add = "--add" in args
    paths = [a for a in args if not a.startswith("--")]
    cfg = config.load()
    set_lang(cfg.get("language", "ru"))
    winint.init_process(APP_ID)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setStyle("Fusion")
    from . import style
    app.setStyleSheet(style.stylesheet())
    app.setWindowIcon(style.app_icon())
    gui_thread_gc(app)
    if cfg.get("language", "ru") == "ru":
        from PySide6.QtCore import QLibraryInfo, QTranslator
        tr = QTranslator(app)
        if tr.load("qtbase_ru", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
            app.installTranslator(tr)

    if cfg.get("single_window", True) and _send_to_running(paths, add):
        return 0

    # listen before the slow part (libmpv, the window): Explorer starts one process per selected file
    server = QLocalServer()
    QLocalServer.removeServer(SERVER_NAME)
    server.listen(SERVER_NAME)
    pending: list[tuple[list[str], bool]] = []
    state = {"win": None, "last": 0.0}

    def deliver(got: list[str], add_: bool):
        import time as _t
        win_ = state["win"]
        if win_ is None:
            pending.append((got, add_))
            return
        target = win_.mini if win_.mini is not None and win_.mini.isVisible() else win_
        if target.isMinimized():
            target.showNormal()
        target.raise_()
        target.activateWindow()
        if got:
            now = _t.monotonic()
            if now - state["last"] < 2.0:          # several files opened at once in Explorer: one playlist
                add_ = True
            state["last"] = now
            win_.open_paths(got, add=add_)

    def on_conn():
        s = server.nextPendingConnection()

        def read():
            data = bytes(s.readAll()).decode("utf-8", "replace")
            lines = [ln for ln in data.splitlines() if ln]
            deliver([ln for ln in lines if not ln.startswith("--")], "--add" in lines)
        s.readyRead.connect(read)
    server.newConnection.connect(on_conn)

    try:
        mpvmod = load_mpv()
    except Exception as e:
        QMessageBox.critical(None, APP_TITLE, t("mpv_missing", e))
        return 1
    locale.setlocale(locale.LC_NUMERIC, "C")         # QApplication may have changed it

    from .window import MainWindow
    win = MainWindow(mpvmod, cfg)
    win.restore_geometry()
    win.show()

    def start():
        import time as _t
        if not paths or add:              # --add from Explorer: the old playlist comes back, then gets the files
            win.restore_session()
        if paths:
            win.open_paths(paths, add=add)
            state["last"] = _t.monotonic()
        state["win"] = win
        for got, add_ in pending:
            deliver(got, add_)
        pending.clear()
    QTimer.singleShot(0, start)
    QTimer.singleShot(4000, win.maybe_check_updates)
    code = app.exec()
    server.close()
    return code
