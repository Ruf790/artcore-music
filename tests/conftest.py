import locale
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("ARTCORE_MUSIC_AO", "null")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def media(tmp_path_factory):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is needed for the test media")
    out = str(tmp_path_factory.mktemp("media"))
    subprocess.run([sys.executable, os.path.join(ROOT, "tests", "make_media.py"), out], check=True)
    return out


@pytest.fixture(scope="session")
def mpvmod():
    try:
        locale.setlocale(locale.LC_NUMERIC, "C")
        import mpv
        return mpv
    except Exception as e:                          # no libmpv here
        pytest.skip(f"libmpv: {e}")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from music.main import gui_thread_gc
    gui_thread_gc(app)
    locale.setlocale(locale.LC_NUMERIC, "C")
    from music import style
    app.setStyle("Fusion")
    app.setStyleSheet(style.stylesheet())
    yield app
    # tear the windows of all tests down in the GUI thread, before Python takes Qt apart at exit
    import gc
    from PySide6.QtCore import QCoreApplication, QEvent
    for w in app.topLevelWidgets():
        w.hide()
        w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    gc.collect()


@pytest.fixture()
def icy_server(media):
    """A tiny SHOUTcast-like radio on localhost: ICY 200, icy-metaint, StreamTitle changing every 2 s.
    Yields (url, stop) — stop() drops every listener and refuses new ones (a station going off air)."""
    import socket
    import threading
    import time
    song = open(os.path.join(media, "Stereo Album", "01 - Первый трек.mp3"), "rb").read()
    meta_int = 4096
    state = {"on": True, "conns": []}
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)

    def meta(title):
        s = f"StreamTitle='{title}';".encode()
        n = (len(s) + 15) // 16
        return bytes([n]) + s.ljust(n * 16, b"\0")

    def handle(c):
        req = c.recv(4096).decode("latin1").lower()
        want = "icy-metadata: 1" in req
        hdr = "ICY 200 OK\r\nicy-name: Test FM\r\ncontent-type: audio/mpeg\r\n"
        if want:
            hdr += f"icy-metaint: {meta_int}\r\n"
        try:
            c.sendall((hdr + "\r\n").encode())
            pos, t0, sent = 0, time.time(), 0
            while state["on"]:
                chunk = song[pos:pos + meta_int]
                if len(chunk) < meta_int:
                    chunk += song[:meta_int - len(chunk)]
                pos = (pos + meta_int) % len(song)
                c.sendall(chunk)
                if want:
                    c.sendall(meta(f"DJ Test - Track {int((time.time() - t0) // 2) + 1}"))
                sent += len(chunk)
                time.sleep(max(0.0, sent / 24000 - (time.time() - t0)))
        except OSError:
            pass
        c.close()

    def accept():
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            if not state["on"]:
                c.close()
                continue
            state["conns"].append(c)
            threading.Thread(target=handle, args=(c,), daemon=True).start()
    threading.Thread(target=accept, daemon=True).start()

    def stop():
        state["on"] = False
        srv.close()
    yield f"http://127.0.0.1:{srv.getsockname()[1]}/", stop
    stop()


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTCORE_MUSIC_DATA", str(tmp_path / "data"))
    return str(tmp_path / "data")


def pump(app, secs: float, until=None):
    import gc
    import time
    gc.collect()                                     # here, in the GUI thread (see main.gui_thread_gc)
    t0 = time.monotonic()
    while time.monotonic() - t0 < secs:
        app.processEvents()
        if until is not None and until():
            return True
        time.sleep(0.01)
    return until() if until is not None else True
