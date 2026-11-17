"""Windows Defender Firewall: an inbound rule for the remote's TCP port, open to the local subnet only.
Adding it needs admin rights, so netsh runs elevated (one UAC prompt). Everything is a no-op elsewhere."""
from __future__ import annotations

import subprocess
import sys

IS_WIN = sys.platform == "win32"
RULE = "ArtCore Music Remote"
_NO_WINDOW = 0x08000000                         # CREATE_NO_WINDOW


def rule_ok(port: int) -> bool | None:
    """True: our rule exists and opens `port`; False: it does not; None: not Windows / netsh is not there."""
    if not IS_WIN:
        return None
    try:
        r = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={RULE}"],
                           capture_output=True, timeout=10, creationflags=_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return False
    try:
        text = r.stdout.decode("oem")                       # netsh writes in the console code page
    except (LookupError, UnicodeDecodeError):
        text = r.stdout.decode("utf-8", "replace")
    # the labels are translated (LocalPort / Локальный порт); the value is the port on its own
    return any(line.split(":", 1)[1].strip() == str(port) for line in text.splitlines() if ":" in line)


def allow(port: int, timeout: float = 120.0) -> bool:
    """Ask Windows (UAC) to replace our rule with one for `port`. True when the rule is there afterwards."""
    if not IS_WIN:
        return True
    import ctypes
    from ctypes import wintypes

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                    ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]

    port = int(port)
    params = (f'/c netsh advfirewall firewall delete rule name="{RULE}" >nul 2>&1 & '
              f'netsh advfirewall firewall add rule name="{RULE}" dir=in action=allow protocol=TCP '
              f'localport={port} remoteip=localsubnet profile=any')
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040                                 # SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = "cmd.exe"
    info.lpParameters = params
    info.nShow = 0                                          # SW_HIDE
    try:
        if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
            return False                                    # UAC was declined
        if info.hProcess:
            ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, int(timeout * 1000))
            ctypes.windll.kernel32.CloseHandle(info.hProcess)
    except Exception:
        return False
    return bool(rule_ok(port))
