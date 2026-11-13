"""Windows bits: dark title bar, taskbar id, installer mutex, libmpv-2.dll, ⏮ ⏯ ⏭ buttons in the taskbar
preview (ITaskbarList3), global media keys (RegisterHotKey). Everything is a no-op elsewhere."""
from __future__ import annotations

import os
import sys

IS_WIN = sys.platform == "win32"
MUTEX_NAME = "ArtCoreMusicMutex"        # same as AppMutex in setup.iss
_mutex = None

WM_COMMAND = 0x0111
WM_HOTKEY = 0x0312
WM_APPCOMMAND = 0x0319
THBN_CLICKED = 0x1800
# media keys: virtual key → action
VK_MEDIA = {0xB3: "play_pause", 0xB0: "next", 0xB1: "prev", 0xB2: "stop"}
# WM_APPCOMMAND (keyboards/remotes that send commands instead of keys)
APPCOMMANDS = {14: "play_pause", 46: "play", 47: "pause", 11: "next", 12: "prev", 13: "stop"}
HOTKEY_BASE = 0xAC00


def init_process(app_id: str) -> None:
    if not IS_WIN:
        return
    import ctypes
    global _mutex
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass
    try:
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    except Exception:
        pass


def release_mutex() -> None:
    """Let the installer run (it waits for AppMutex) — before a self-update."""
    global _mutex
    if IS_WIN and _mutex:
        import ctypes
        try:
            ctypes.windll.kernel32.CloseHandle(_mutex)
        except Exception:
            pass
        _mutex = None


def dark_title_bar(win_id: int, dark: bool = True) -> None:
    """DWMWA_USE_IMMERSIVE_DARK_MODE (20; 19 on early Windows 10 builds)."""
    if not IS_WIN:
        return
    import ctypes
    val = ctypes.c_int(1 if dark else 0)
    for attr in (20, 19):
        try:
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(win_id, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                break
        except Exception:
            break


def prepare_libmpv() -> list[str]:
    """Make libmpv-2.dll findable: next to the exe, in PyInstaller's _internal, in the source tree."""
    dirs = []
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for d in (os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else "",
              getattr(sys, "_MEIPASS", ""), here, os.path.join(here, "libmpv")):
        if d and os.path.isdir(d) and d not in dirs:
            dirs.append(d)
    if IS_WIN:
        os.environ["PATH"] = os.pathsep.join(dirs + [os.environ.get("PATH", "")])
        for d in dirs:
            try:
                os.add_dll_directory(d)
            except (OSError, AttributeError):
                pass
    return dirs


def show_in_explorer(path: str) -> None:
    import subprocess
    if IS_WIN:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    else:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))


def read_msg(message):
    """(hwnd, msg, wParam, lParam) from the pointer QWidget.nativeEvent gets on Windows."""
    import ctypes
    from ctypes import wintypes
    m = wintypes.MSG.from_address(int(message))
    return m.hWnd, m.message, int(m.wParam or 0), int(m.lParam or 0)


# ── global media keys ────────────────────────────────────────
def register_media_keys(hwnd: int) -> list[int]:
    """RegisterHotKey for ⏯ ⏭ ⏮ ⏹ (works when the window is not focused). Returns the ids that worked;
    a key another program already holds is skipped (WM_APPCOMMAND still brings it while we are focused)."""
    if not IS_WIN:
        return []
    import ctypes
    ok = []
    for i, vk in enumerate(VK_MEDIA):
        try:
            if ctypes.windll.user32.RegisterHotKey(ctypes.c_void_p(hwnd), HOTKEY_BASE + i, 0x4000, vk):  # MOD_NOREPEAT
                ok.append(HOTKEY_BASE + i)
        except Exception:
            pass
    return ok


def unregister_media_keys(hwnd: int, ids: list[int]) -> None:
    if not IS_WIN:
        return
    import ctypes
    for i in ids:
        try:
            ctypes.windll.user32.UnregisterHotKey(ctypes.c_void_p(hwnd), i)
        except Exception:
            pass


def hotkey_action(hotkey_id: int) -> str:
    keys = list(VK_MEDIA.values())
    i = hotkey_id - HOTKEY_BASE
    return keys[i] if 0 <= i < len(keys) else ""


def appcommand_action(lparam: int) -> str:
    return APPCOMMANDS.get((lparam >> 16) & 0x0FFF, "")


# ── taskbar preview buttons ──────────────────────────────────
def hicon_from_qimage(img) -> int:
    """32-bit ARGB QImage → HICON (CreateIconIndirect on a top-down DIB section)."""
    import ctypes
    from ctypes import wintypes
    from PySide6.QtGui import QImage
    img = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    w, h = img.width(), img.height()

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    class ICONINFO(ctypes.Structure):
        _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                    ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]

    gdi, user = ctypes.windll.gdi32, ctypes.windll.user32
    gdi.CreateDIBSection.restype = wintypes.HBITMAP
    gdi.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                     wintypes.HANDLE, wintypes.DWORD]
    gdi.CreateBitmap.restype = wintypes.HBITMAP
    user.CreateIconIndirect.restype = wintypes.HICON
    user.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
    bih = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    bits = ctypes.c_void_p()
    color = gdi.CreateDIBSection(None, ctypes.byref(bih), 0, ctypes.byref(bits), None, 0)
    if not color or not bits.value:
        return 0
    ptr = img.constBits()
    data = bytes(ptr) if not hasattr(ptr, "tobytes") else ptr.tobytes()
    stride = img.bytesPerLine()
    row = w * 4
    buf = b"".join(data[y * stride:y * stride + row] for y in range(h)) if stride != row else data[:row * h]
    ctypes.memmove(bits.value, buf, len(buf))
    mask = gdi.CreateBitmap(w, h, 1, 1, None)
    info = ICONINFO(True, 0, 0, mask, color)
    hicon = user.CreateIconIndirect(ctypes.byref(info))
    gdi.DeleteObject(ctypes.c_void_p(mask))
    gdi.DeleteObject(ctypes.c_void_p(color))
    return int(hicon or 0)


class ThumbBar:
    """ITaskbarList3 thumbnail toolbar: ⏮ ⏯ ⏭ in the window preview of the taskbar.
    Clicks come as WM_COMMAND with HIWORD(wParam) == THBN_CLICKED and LOWORD = button id."""
    IDS = (1, 2, 3)              # prev, play/pause, next

    def __init__(self):
        self.tb = None
        self._vt = None
        self.added = False
        self.msg_created = 0
        if not IS_WIN:
            return
        import ctypes
        try:
            self.msg_created = ctypes.windll.user32.RegisterWindowMessageW("TaskbarButtonCreated")
        except Exception:
            pass

    def _create(self) -> bool:
        if self.tb is not None:
            return True
        import ctypes
        import uuid
        ole = ctypes.windll.ole32
        ole.CoInitialize(None)
        clsid = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID("56FDF344-FD6D-11d0-958A-006097C9A090").bytes_le)
        iid = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID("EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF").bytes_le)
        ptr = ctypes.c_void_p()
        hr = ole.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(ptr))  # CLSCTX_INPROC
        if hr != 0 or not ptr.value:
            return False
        self.tb = ptr
        self._vt = ctypes.cast(ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
        self._call(3, [])                       # HrInit
        return True

    def _call(self, idx: int, args: list, argtypes: list | None = None) -> int:
        import ctypes
        proto = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *(argtypes or []))
        return proto(self._vt[idx])(self.tb, *args)

    @staticmethod
    def _struct():
        import ctypes
        from ctypes import wintypes

        class THUMBBUTTON(ctypes.Structure):
            _fields_ = [("dwMask", wintypes.DWORD), ("iId", wintypes.UINT), ("iBitmap", wintypes.UINT),
                        ("hIcon", wintypes.HICON), ("szTip", wintypes.WCHAR * 260), ("dwFlags", wintypes.DWORD)]
        return THUMBBUTTON

    def _buttons(self, icons: list[int], tips: list[str]):
        import ctypes
        TB = self._struct()
        arr = (TB * 3)()
        for i in range(3):
            arr[i].dwMask = 0x2 | 0x4 | 0x8          # THB_ICON | THB_TOOLTIP | THB_FLAGS
            arr[i].iId = self.IDS[i]
            arr[i].hIcon = icons[i]
            arr[i].szTip = tips[i][:259]
            arr[i].dwFlags = 0                       # THBF_ENABLED
        return arr

    def add(self, hwnd: int, icons: list[int], tips: list[str]) -> bool:
        """Call after the TaskbarButtonCreated message (or right after the window is shown)."""
        if not IS_WIN:
            return False
        import ctypes
        try:
            if not self._create():
                return False
            arr = self._buttons(icons, tips)
            idx = 16 if self.added else 15            # ThumbBarUpdateButtons / ThumbBarAddButtons
            hr = self._call(idx, [ctypes.c_void_p(hwnd), 3, arr], [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p])
            if hr == 0:
                self.added = True
            return hr == 0
        except Exception:
            return False

    def update(self, hwnd: int, icons: list[int], tips: list[str]) -> bool:
        if not self.added:
            return False
        return self.add(hwnd, icons, tips)

    @staticmethod
    def clicked(wparam: int) -> int:
        """Button id if this WM_COMMAND came from the thumbnail toolbar, else 0."""
        return wparam & 0xFFFF if (wparam >> 16) & 0xFFFF == THBN_CLICKED else 0
