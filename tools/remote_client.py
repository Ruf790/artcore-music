"""A test client for the ArtCore Music remote (what the Android app does, in Python, on QWebSocket).

    python tools/remote_client.py 192.168.1.10 --code 1234            pair, list the playlists, play / pause / stop
    python tools/remote_client.py 192.168.1.10 --token TOKEN --play 2  play the 2nd track of the first playlist
    python tools/remote_client.py --find                               listen for the PCs on the network (UDP 47871)

The tests import RemoteClient from here."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QCoreApplication, QUrl                   # noqa: E402
from PySide6.QtNetwork import QAbstractSocket, QHostAddress, QUdpSocket  # noqa: E402
from PySide6.QtWebSockets import QWebSocket                         # noqa: E402


class RemoteClient:
    """Connects, collects every message the PC sends (self.got), sends commands."""

    def __init__(self, app=None):
        self.app = app or QCoreApplication.instance() or QCoreApplication(sys.argv)
        self.ws = QWebSocket()
        self.got: list[dict] = []
        self.closed = False
        self.ws.textMessageReceived.connect(self._on_text)
        self.ws.disconnected.connect(self._on_closed)

    def _on_text(self, text: str):
        try:
            self.got.append(json.loads(text))
        except ValueError:
            pass

    def _on_closed(self):
        self.closed = True

    def pump(self, secs: float, until=None) -> bool:
        t0 = time.monotonic()
        while time.monotonic() - t0 < secs:
            self.app.processEvents()
            if until is not None and until():
                return True
            time.sleep(0.01)
        return bool(until()) if until is not None else True

    def open(self, host: str, port: int, secs: float = 5.0) -> bool:
        self.ws.open(QUrl(f"ws://{host}:{port}"))
        return self.pump(secs, lambda: self.ws.state() == QAbstractSocket.ConnectedState or self.closed)

    def send(self, kind: str, **kw):
        self.ws.sendTextMessage(json.dumps({"type": kind, **kw}))

    def hello(self, code: str = "", token: str = "", device: str = "Test phone", dev_id: str = "test-1"):
        msg = {"proto": 1, "device": device, "id": dev_id}
        if code:
            msg["code"] = code
        if token:
            msg["token"] = token
        self.send("hello", **msg)

    def last(self, kind: str) -> dict | None:
        return next((m for m in reversed(self.got) if m.get("type") == kind), None)

    def wait(self, kind: str, secs: float = 5.0, check=None) -> dict | None:
        start = len(self.got)

        def found():
            return next((m for m in self.got[start:] if m.get("type") == kind and (check is None or check(m))), None)
        self.pump(secs, lambda: found() is not None or self.closed)
        return found()

    def close(self):
        self.ws.close()
        self.pump(0.3)


def find(secs: float = 6.0) -> list[dict]:
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    udp = QUdpSocket()
    if not udp.bind(QHostAddress.AnyIPv4, 47871, QUdpSocket.ShareAddress | QUdpSocket.ReuseAddressHint):
        print("cannot listen on UDP 47871:", udp.errorString())
        return []
    seen = {}
    t0 = time.monotonic()
    while time.monotonic() - t0 < secs:
        app.processEvents()
        while udp.hasPendingDatagrams():
            dg = udp.receiveDatagram()
            try:
                info = json.loads(bytes(dg.data()).decode("utf-8"))
            except ValueError:
                continue
            if info.get("app") == "artcore-music":
                info["ip"] = dg.senderAddress().toString().replace("::ffff:", "")
                seen[info.get("id")] = info
        time.sleep(0.02)
    return list(seen.values())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host", nargs="?")
    ap.add_argument("--port", type=int, default=47870)
    ap.add_argument("--code", default="")
    ap.add_argument("--token", default="")
    ap.add_argument("--play", type=int, default=1, help="track number in the first playlist (1 = the first)")
    ap.add_argument("--find", action="store_true")
    a = ap.parse_args()
    if a.find or not a.host:
        for pc in find():
            print(f"{pc['name']}  {pc['ip']}:{pc['port']}  ArtCore Music {pc['version']}")
        return 0
    c = RemoteClient()
    if not c.open(a.host, a.port):
        print("no connection")
        return 1
    c.hello(code=a.code, token=a.token)
    w = c.wait("welcome")
    if w is None:
        print("refused:", c.last("error"))
        return 1
    print(f"connected to {w['pc']} (ArtCore Music {w['version']})")
    if w.get("token"):
        print("token (use --token next time):", w["token"])
    pls = c.wait("playlists") or c.last("playlists")
    first = None
    for p in pls["items"]:
        print(f"\n[{p['id']}] {p['name']} — {p['count']} tracks")
        for g in p["groups"]:
            if g["kind"] == "album":
                print(f"  {g['title'].upper()} — {g['artist']} {g['year']}")
            for tr in g["tracks"]:
                print(f"    {tr['id']:>5}  {tr['artist']} — {tr['title']}  ({int(tr['duration']) // 60}:{int(tr['duration']) % 60:02d})")
                if first is None and p["id"] == 0:
                    first = []
                if p["id"] == 0:
                    first.append(tr["id"])
    if first:
        tid = first[min(len(first), max(1, a.play)) - 1]
        for cmd, kw in (("play", {"playlist": 0, "track": tid}), ("pause", {}), ("resume", {}), ("stop", {})):
            c.send(cmd, **kw)
            st = c.wait("state", 3)
            print(f"{cmd:>7} → {st['status'] if st else '?'}"
                  + (f"  {st['track']['title']}" if st and st.get("track") else ""))
            c.pump(1.0)
    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
