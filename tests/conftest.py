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
