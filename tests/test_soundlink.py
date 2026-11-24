"""1.8.2: «Open in ArtCore Sound» — finding ArtCoreSound.exe, starting it with the files, the track menu, the
«not found» question."""
import os

from music import soundlink
from conftest import pump
from music.window import UID


def test_command_exe():
    assert soundlink.command_exe('"C:\\Program Files\\ArtCore Sound\\ArtCoreSound.exe" "%1"') == \
        "C:\\Program Files\\ArtCore Sound\\ArtCoreSound.exe"
    assert soundlink.command_exe("C:\\Tools\\ArtCoreSound.exe %1") == "C:\\Tools\\ArtCoreSound.exe"
    assert soundlink.command_exe("") == ""


def _fake_exe(tmp_path):
    exe = tmp_path / "ArtCore Sound" / "ArtCoreSound.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"MZ")
    return str(exe)


def test_find_exe_order(tmp_path, monkeypatch):
    monkeypatch.delenv("ARTCORE_SOUND_EXE", raising=False)
    monkeypatch.setattr(soundlink, "_registry", lambda: [])
    monkeypatch.setattr(soundlink, "_folders", lambda: [])
    assert soundlink.find_exe({}) == ""
    exe = _fake_exe(tmp_path)
    assert soundlink.find_exe({"sound_exe": exe}) == os.path.abspath(exe)          # the path given
    monkeypatch.setattr(soundlink, "_registry", lambda: [exe])                      # the installer's entry
    assert soundlink.find_exe({"sound_exe": str(tmp_path / "gone.exe")}) == os.path.abspath(exe)
    assert soundlink.is_sound_exe(exe) and not soundlink.is_sound_exe(str(tmp_path))


def test_find_exe_in_the_install_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("ARTCORE_SOUND_EXE", raising=False)
    monkeypatch.setattr(soundlink, "_registry", lambda: [])
    for v in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert soundlink.find_exe({}) == ""
    exe = tmp_path / "local" / "Programs" / "ArtCore Sound" / "ArtCoreSound.exe"     # a «just me» install
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    assert soundlink.find_exe({}) == str(exe)
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    exe2 = _fake_exe(tmp_path)                                                        # for all users: first
    assert soundlink.find_exe({}) == os.path.abspath(exe2)


def test_open_files_starts_it_with_the_paths(tmp_path, monkeypatch):
    exe = _fake_exe(tmp_path)
    monkeypatch.setenv("ARTCORE_SOUND_EXE", exe)
    started = []

    class P:
        def __init__(self, args, **kw):
            started.append((args, kw.get("cwd")))
    monkeypatch.setattr(soundlink.subprocess, "Popen", P)
    assert soundlink.open_files(["a.mkv", str(tmp_path / "b.flac")])
    args, cwd = started[0]
    assert args[0] == os.path.abspath(exe) and cwd == os.path.dirname(os.path.abspath(exe))
    assert args[1:] == [os.path.abspath("a.mkv"), str(tmp_path / "b.flac")]
    monkeypatch.setenv("ARTCORE_SOUND_EXE", str(tmp_path / "none.exe"))
    assert not soundlink.open_files(["a.mkv"])


def test_track_menu_and_not_found(qapp, mpvmod, media, data_dir, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox
    from test_ui import _win
    w = _win(mpvmod)
    w.open_paths([os.path.join(media, "Stereo Album"), os.path.join(media, "CUE Album")], play=False)
    pump(qapp, 1.0)
    menus = []

    class Menu(QMenu):                                   # built, never shown
        def exec(self, *a):
            menus.append(self)
    monkeypatch.setattr("music.window.QMenu", Menu)
    w.view.clearSelection()
    first = w.view.topLevelItem(0)
    w._list_menu(w.view.visualItemRect(first).center())
    acts = {a.text().split("\t")[0]: a for a in menus[-1].actions() if a.text()}
    assert "Открыть в ArtCore Sound" in acts
    # every CUE track selected: the album's file once
    cue = [tr for tr in w.pl.tracks if tr.is_cue]
    assert len(cue) >= 2
    for i in range(w.view.topLevelItemCount()):
        it = w.view.topLevelItem(i)
        tr = w.pl.by_uid(it.data(0, UID))
        it.setSelected(tr is not None and tr.is_cue)
    assert w._sound_files() == [cue[0].path]
    w.view.clearSelection()
    started = []
    monkeypatch.setattr(soundlink.subprocess, "Popen", lambda args, **kw: started.append(args))
    monkeypatch.setenv("ARTCORE_SOUND_EXE", str(tmp_path / "none.exe"))
    monkeypatch.setattr(soundlink, "candidates", lambda cfg=None: [(cfg or {}).get("sound_exe") or ""])
    exe = _fake_exe(tmp_path)
    other = tmp_path / "other.exe"
    other.write_bytes(b"MZ")
    picks = [str(other), exe]
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (picks.pop(0), ""))
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a[2]))
    shown = []

    def fake_exec(box):
        shown.append(box.text())
        box._clicked = next(b for b in box.buttons() if b.text() == "Указать ArtCoreSound.exe…")
        return 0
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda box: box._clicked)
    acts["Открыть в ArtCore Sound"].trigger()
    path = w.pl.by_uid(first.data(0, UID)).path
    assert len(shown) == 2 and "ArtCore Sound не найден" in shown[0]
    assert warned == ["Это не ArtCoreSound.exe"]
    assert w.cfg["sound_exe"] == os.path.normpath(exe)
    assert started == [[os.path.abspath(exe), os.path.abspath(path)]]
    w.open_in_sound([path])                              # found now: no question
    assert len(shown) == 2 and len(started) == 2
    w.close()


def test_version_182():
    from music import VERSION, VERSION_TUPLE
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert VERSION == "1.8.2" and VERSION_TUPLE == (1, 8, 2, 0)
    assert '#define AppVersion   "1.8.2"' in open(os.path.join(root, "setup.iss"), encoding="utf-8-sig").read()
    vi = open(os.path.join(root, "version_info.txt"), encoding="utf-8").read()
    assert "(1, 8, 2, 0)" in vi and "'1.8.2'" in vi


def test_strings():
    from music import i18n
    for k in ("snd_open", "snd_missing", "snd_browse", "snd_download", "snd_not_exe",
              "snd_failed", "snd_sent"):
        ru, en = i18n.STRINGS[k]
        assert ru and en and ru != en
