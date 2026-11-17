"""The remote control for the phone (ArtCore Music Remote for Android).

A WebSocket server (QtWebSockets) speaks JSON with the phone; a UDP broadcast every 2 s lets the phone find
this PC without typing its address. Only the local network gets in (private IPv4 ranges and this PC);
a phone pairs once with the 4-digit code shown in Settings → Remote, then uses the token it got.

Protocol (version 1), every message is a JSON object with "type":
  phone → PC   hello {proto, device, id, code | token}
               play {playlist, track} · pause · resume · toggle · stop · next · prev · seek {position}
               volume {value | delta} · mute {on?} · repeat {mode?} · shuffle {on?}
               get_cover {id, size?} · get_playlists · get_state
  PC → phone   welcome {proto, pc, version, id, token?} · error {error}
               playlists {rev, playing, items: [{id, name, kind, count, duration, groups: [{kind, title, artist,
                          year, tracks: [track]}]}]}
               state {status, playlist, track, position, duration, volume, muted, repeat, shuffle, index, count,
                      next, format, on_air}
               position {position, duration, status}            (once a second while something plays)
               cover {id, size, mime, data}                       (data = base64 JPEG, "" = no cover)
  track = {id, title, artist, album, year, genre, n, duration, stream, cover, has_cover}
Discovery (UDP, port 47871): {"app": "artcore-music", "proto", "name", "version", "port", "id"}.
"""
from __future__ import annotations

import base64
import collections
import hashlib
import hmac
import ipaddress
import json
import os
import queue
import secrets
import socket
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QAbstractSocket, QHostAddress, QNetworkInterface, QUdpSocket

from . import VERSION, meta

PROTO = 1
DEFAULT_PORT = 47870
DISCOVERY_PORT = 47871
DISCOVERY_EVERY_MS = 2000
APP_KEY = "artcore-music"
BAD_CODES_PER_MINUTE = 5
HELLO_TIMEOUT_MS = 10000
MAX_MESSAGE = 64 * 1024
COVER_SIZES = (128, 256, 512)
MAX_DEVICES = 20


# ── who may connect ──────────────────────────────────────────
_PRIVATE = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8")]


def is_local(addr: str) -> bool:
    """192.168.*, 10.*, 172.16–31.* and this PC (127.*, ::1); IPv4 written as IPv6 (::ffff:192.168.1.5) too."""
    a = (addr or "").strip()
    if a.startswith("[") and a.endswith("]"):
        a = a[1:-1]
    a = a.split("%", 1)[0]
    try:
        ip = ipaddress.ip_address(a)
    except ValueError:
        return False
    if ip.version == 6:
        if ip == ipaddress.ip_address("::1"):
            return True
        if ip.ipv4_mapped is None:
            return False
        ip = ip.ipv4_mapped
    return any(ip in n for n in _PRIVATE)


def pc_name() -> str:
    return os.environ.get("COMPUTERNAME") or socket.gethostname().split(".")[0].upper() or "PC"


def new_code() -> str:
    return "%04d" % secrets.randbelow(10000)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Pairing:
    """The 4-digit code, the paired phones (cfg["remote_devices"]: id, name, token hash, dates, last address)
    and the limit on wrong codes: no more than 5 a minute from one address."""

    def __init__(self, cfg: dict, clock=time.monotonic):
        self.cfg = cfg
        self.clock = clock
        self._bad: dict[str, collections.deque] = {}
        if not (isinstance(cfg.get("remote_code"), str) and len(cfg["remote_code"]) == 4
                and cfg["remote_code"].isdigit()):
            cfg["remote_code"] = new_code()
        if not isinstance(cfg.get("remote_devices"), list):
            cfg["remote_devices"] = []

    @property
    def code(self) -> str:
        return self.cfg["remote_code"]

    def renew_code(self) -> str:
        self.cfg["remote_code"] = new_code()
        return self.code

    def devices(self) -> list[dict]:
        return [d for d in self.cfg.get("remote_devices", []) if isinstance(d, dict) and d.get("hash")]

    def blocked(self, ip: str) -> bool:
        q = self._bad.get(ip)
        if not q:
            return False
        now = self.clock()
        while q and now - q[0] >= 60.0:
            q.popleft()
        return len(q) >= BAD_CODES_PER_MINUTE

    def try_code(self, ip: str, code: str) -> str:
        """"ok" | "bad_code" | "too_many"."""
        if self.blocked(ip):
            return "too_many"
        if isinstance(code, str) and hmac.compare_digest(code.strip().encode(), self.code.encode()):
            self._bad.pop(ip, None)
            return "ok"
        self._bad.setdefault(ip, collections.deque()).append(self.clock())
        return "too_many" if self.blocked(ip) else "bad_code"

    def pair(self, device_id: str, name: str, ip: str) -> str:
        """A new token for the phone (the old one of the same phone stops working)."""
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        devs = [d for d in self.devices() if d.get("id") != device_id]
        devs.append({"id": device_id, "name": name, "hash": _hash(token), "added": now, "seen": now, "ip": ip})
        self.cfg["remote_devices"] = devs[-MAX_DEVICES:]
        return token

    def check_token(self, token: str) -> dict | None:
        if not isinstance(token, str) or not token:
            return None
        h = _hash(token)
        for d in self.devices():
            if hmac.compare_digest(d["hash"], h):
                return d
        return None

    def forget(self, device_id: str) -> None:
        self.cfg["remote_devices"] = [d for d in self.devices() if d.get("id") != device_id]


# ── album covers for the phone ───────────────────────────────
def cover_id(tr) -> str:
    """One id per album (the folder + the album tag, or the CUE sheet), per file for loose tracks."""
    if tr.is_stream:
        return ""
    if tr.cue:
        key = "cue:" + tr.cue
    elif tr.album:
        key = os.path.dirname(tr.path) + "|" + tr.album.lower()
    else:
        key = tr.path
    return hashlib.sha1(os.path.normcase(key).encode("utf-8", "replace")).hexdigest()[:16]


def scale_jpeg(data: bytes, size: int) -> bytes:
    """The cover as a JPEG that fits size×size (never larger than the original)."""
    import io
    from PIL import Image
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        im.thumbnail((size, size), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, "JPEG", quality=85 if size > 200 else 80, optimize=True)
        return out.getvalue()


class CoverStore(QObject):
    """Finds out which albums have a cover and makes the JPEGs, in a thread (the files may be on a slow disk)."""
    scanned = Signal()                        # new "has a cover" answers are known
    ready = Signal(str, int, str)             # id, size, base64 JPEG ("" = none)
    CACHE = 240

    def __init__(self):
        super().__init__()
        self.known: dict[str, bool] = {}
        self.paths: dict[str, str] = {}
        self._cache: "collections.OrderedDict[tuple, str]" = collections.OrderedDict()
        self._lock = threading.Lock()
        self._q: queue.Queue = queue.Queue()
        self._pending: set = set()
        self._stop = False
        self._thread = threading.Thread(target=self._run, name="remote-covers", daemon=True)
        self._thread.start()

    def note(self, tr) -> str:
        cid = cover_id(tr)
        if cid and cid not in self.paths:
            self.paths[cid] = tr.path
            self._q.put(("scan", cid, tr.path))
        return cid

    def has(self, cid: str):
        return self.known.get(cid) if cid else False

    def get(self, cid: str, size: int) -> str | None:
        """The base64 JPEG when it is cached; otherwise None (and `ready` comes later)."""
        size = min(COVER_SIZES, key=lambda s: abs(s - int(size or 512)))
        with self._lock:
            hit = self._cache.get((cid, size))
            if hit is not None:
                self._cache.move_to_end((cid, size))
                return hit
        path = self.paths.get(cid)
        if path is None or self.known.get(cid) is False:
            return ""
        if (cid, size) not in self._pending:
            self._pending.add((cid, size))
            self._q.put(("get", cid, path, size))
        return None

    def _run(self):
        while not self._stop:
            item = self._q.get()
            if item is None:
                return
            news = False
            try:
                if item[0] == "scan":
                    _, cid, path = item
                    if cid not in self.known:
                        self.known[cid] = bool(meta.folder_cover(path) or meta.embedded_picture(path))
                        news = True
                else:
                    _, cid, path, size = item
                    data = meta.cover_bytes(path)
                    b64 = ""
                    if data:
                        try:
                            b64 = base64.b64encode(scale_jpeg(data, size)).decode("ascii")
                        except Exception:
                            b64 = ""
                    self.known[cid] = bool(b64)
                    with self._lock:
                        self._cache[(cid, size)] = b64
                        while len(self._cache) > self.CACHE:
                            self._cache.popitem(last=False)
                    self._pending.discard((cid, size))
                    if not self._stop:
                        self.ready.emit(cid, size, b64)
            except Exception:
                self._pending.discard(tuple(item[1:2]) + tuple(item[3:4]))
            if news and self._q.empty() and not self._stop:
                self.scanned.emit()

    def stop(self):
        self._stop = True
        self._q.put(None)
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(3.0)


# ── what the server asks of the player ───────────────────────
class WindowHost:
    """The bridge between the server and the main window: what is in the playlists, what plays, and the buttons."""

    def __init__(self, win):
        self.w = win

    @property
    def engine(self):
        return self.w.engine

    def playlists(self) -> list:
        return self.w.pls

    def playing_index(self) -> int:
        try:
            return self.w.pls.index(self.engine.pl)
        except ValueError:
            return -1

    def status(self) -> str:
        e = self.engine
        if e.cur is None or e.stopped:
            return "stop"
        return "pause" if e.paused else "play"

    def position(self) -> tuple[float, float]:
        e = self.engine
        if e.cur is None:
            return 0.0, 0.0
        if e.stopped:
            return 0.0, e.cur.duration()
        pos, dur = self.w._last_pos
        return float(pos or 0.0), float(dur or e.cur.duration() or 0.0)

    def volume(self) -> tuple[int, bool]:
        return int(self.w.vol.value()), bool(self.w.cfg.get("muted"))

    def modes(self) -> tuple[str, bool]:
        return self.engine.pl.repeat, bool(self.engine.pl.shuffle)

    def upcoming(self):
        """The next track without asking the playlist (that may shuffle anew at the end of the list)."""
        e = self.engine
        cur = e.cur
        if cur is None or e.stopped or cur.is_stream:
            return None
        if e.stop_after == cur.uid:
            return None
        if e.queue:
            return e.queue[0]
        pl = e.pl
        if pl.repeat == "one":
            return cur
        seq = pl._seq()
        base = e.ctx or cur
        i = next((k for k, x in enumerate(seq) if x.uid == base.uid), -1)
        if 0 <= i < len(seq) - 1:
            return seq[i + 1]
        if seq and pl.repeat == "all":
            return seq[0]
        return None

    def format_line(self) -> str:
        """«FLAC · 24 bit · 96 kHz», «MP3 · 320 kbps · 44.1 kHz»."""
        from . import audio
        info = self.w.fmt_info or {}
        cur = self.engine.cur
        if cur is None or not info.get("codec"):
            return ""
        name = audio.codec_label(info["codec"], info.get("profile", ""))
        tg = self.w.cur_tags
        bits = tg.bits if tg is not None else 0
        codec = info["codec"]
        if not bits and codec.startswith("pcm_"):
            import re
            m = re.search(r"(\d+)", codec[4:])
            bits = int(m.group(1)) if m else 0
        rate = int(info.get("rate", 0) or 0)
        parts = [name]
        if name == "DSD":
            parts = [audio.dsd_label(rate)]
        elif name in audio.LOSSLESS:
            if bits:
                parts.append(f"{bits} bit")
            if rate:
                parts.append(f"{audio.rate_label(rate)} kHz")
        else:
            kbps = int(info.get("kbps", 0) or (tg.bitrate if tg is not None else 0) or 0)
            if kbps:
                parts.append(f"{kbps} kbps")
            if rate:
                parts.append(f"{audio.rate_label(rate)} kHz")
        ch = int(info.get("channels", 0) or 0)
        if ch > 2:
            parts.append(audio.layout_label(ch, info.get("layout", "")))
        return " · ".join(parts)

    def on_air(self) -> str:
        return self.engine.icy or ""

    def find(self, pl_index, uid):
        pls = self.playlists()
        try:
            uid = int(uid)
        except (TypeError, ValueError):
            return None, None
        if isinstance(pl_index, int) and 0 <= pl_index < len(pls):
            tr = pls[pl_index].by_uid(uid)
            if tr is not None:
                return pls[pl_index], tr
        for p in pls:                                    # the tabs moved: the uid is the same everywhere
            tr = p.by_uid(uid)
            if tr is not None:
                return p, tr
        return None, None

    # the buttons
    def play(self, pl_index, uid) -> bool:
        p, tr = self.find(pl_index, uid)
        if tr is None:
            return False
        e = self.engine
        if p is not e.pl:
            self.w._set_playing_pl(p, tr)
        elif p.shuffle and e.cur is None:
            p.reshuffle(tr)
        e.play(tr)
        return True

    def pause(self):
        if self.engine.cur is not None and not self.engine.stopped:
            self.engine.set_paused(True)

    def resume(self):
        e = self.engine
        if e.cur is None or e.stopped:
            self.w.toggle_pause()                        # starts the current (or the first) track
        else:
            e.set_paused(False)

    def toggle(self):
        self.w.toggle_pause()

    def stop(self):
        self.w.stop()

    def next(self):
        self.w.next()

    def prev(self):
        self.w.prev()

    def seek(self, sec: float):
        self.engine.seek(float(sec))

    def set_volume(self, v: int):
        self.w.vol.setValue(max(0, min(100, int(v))))

    def set_muted(self, on: bool):
        if bool(self.w.cfg.get("muted")) != bool(on):
            self.w.toggle_mute()

    def set_repeat(self, mode: str | None):
        if mode not in ("off", "all", "one"):
            self.w.cycle_repeat()
            return
        for _ in range(3):
            if self.engine.pl.repeat == mode:
                return
            self.w.cycle_repeat()

    def set_shuffle(self, on: bool | None):
        if on is None or bool(on) != bool(self.engine.pl.shuffle):
            self.w.toggle_shuffle()


# ── the server ───────────────────────────────────────────────
class Client:
    def __init__(self, sock, ip: str):
        self.sock = sock
        self.ip = ip
        self.device: dict | None = None             # set once the phone is in
        self.covers: set = set()                   # (id, size) it waits for


class RemoteServer(QObject):
    clients_changed = Signal()
    phone_connected = Signal(str)                # its name

    def __init__(self, host, cfg: dict, parent=None):
        super().__init__(parent)
        self.host = host
        self.cfg = cfg
        self.pairing = Pairing(cfg)
        if not cfg.get("remote_id"):
            cfg["remote_id"] = secrets.token_hex(8)
        self.server = None
        self.udp: QUdpSocket | None = None
        self.clients: list[Client] = []
        self.error = ""
        self.port = 0
        self.covers = CoverStore()
        self.covers.scanned.connect(self.touch)
        self.covers.ready.connect(self._cover_ready)
        self._pl_json = ""
        self._pl_sig = None
        self._pl_rev = 0
        self._pl_dirty = True
        self._state_last = None
        self._sent_pos = 0.0
        self.tick = QTimer(self)                    # state changes, playlists
        self.tick.setInterval(500)
        self.tick.timeout.connect(self._tick)
        self.pos_timer = QTimer(self)               # the position, once a second
        self.pos_timer.setInterval(1000)
        self.pos_timer.timeout.connect(self._send_position)
        self.beacon = QTimer(self)
        self.beacon.setInterval(DISCOVERY_EVERY_MS)
        self.beacon.timeout.connect(self._broadcast)
        self.pl_timer = QTimer(self)                # several list changes in a row → one message
        self.pl_timer.setSingleShot(True)
        self.pl_timer.setInterval(600)
        self.pl_timer.timeout.connect(self._send_playlists_if_changed)

    # ── start / stop
    @property
    def running(self) -> bool:
        return self.server is not None and self.server.isListening()

    def start(self, port: int | None = None) -> bool:
        from PySide6.QtWebSockets import QWebSocketServer
        self.stop()
        port = int(self.cfg.get("remote_port") or DEFAULT_PORT) if port is None else int(port)   # 0 = any free
        srv = QWebSocketServer("ArtCore Music", QWebSocketServer.NonSecureMode, self)
        if not srv.listen(QHostAddress.AnyIPv4, port):
            self.error = srv.errorString() or "listen failed"
            srv.deleteLater()
            return False
        self.error = ""
        self.server = srv
        self.port = srv.serverPort()
        srv.newConnection.connect(self._new_connection)
        self.udp = QUdpSocket(self)
        self.tick.start()
        self.pos_timer.start()
        self.beacon.start()
        self._broadcast()
        return True

    def stop(self):
        for c in list(self.clients):
            c.sock.close()
        self.clients = []
        if self.server is not None:
            self.server.close()
            self.server.deleteLater()
            self.server = None
        if self.udp is not None:
            self.udp.close()
            self.udp.deleteLater()
            self.udp = None
        self.tick.stop()
        self.pos_timer.stop()
        self.beacon.stop()
        self.port = 0
        self.clients_changed.emit()

    def shutdown(self):
        self.stop()
        self.covers.stop()

    def apply(self) -> bool:
        """After the settings: on / off / another port."""
        want = bool(self.cfg.get("remote"))
        port = int(self.cfg.get("remote_port") or DEFAULT_PORT)
        if not want:
            if self.server is not None:
                self.stop()
            self.error = ""
            return True
        if self.running and self.port == port:
            return True
        return self.start(port)

    # ── what the settings show
    def online(self) -> list[Client]:
        return [c for c in self.clients if c.device is not None]

    def is_online(self, device_id: str) -> bool:
        return any(c.device.get("id") == device_id for c in self.online())

    def disconnect_device(self, device_id: str):
        """Forget the phone: its token stops working; it is dropped if connected now."""
        self.pairing.forget(device_id)
        for c in list(self.clients):
            if c.device is not None and c.device.get("id") == device_id:
                self._send(c, {"type": "error", "error": "forgotten"})
                c.sock.close()
        self.clients_changed.emit()

    def renew_code(self) -> str:
        return self.pairing.renew_code()

    @staticmethod
    def addresses() -> list[str]:
        """This PC's addresses in the local network (for typing in by hand)."""
        out = []
        for iface in QNetworkInterface.allInterfaces():
            fl = iface.flags()
            if not (fl & QNetworkInterface.IsUp) or fl & QNetworkInterface.IsLoopBack:
                continue
            for e in iface.addressEntries():
                ip = e.ip()
                if ip.protocol() == QAbstractSocket.IPv4Protocol and is_local(ip.toString()) \
                        and not ip.toString().startswith("127."):
                    out.append(ip.toString())
        return sorted(set(out))

    # ── connections
    def _new_connection(self):
        while self.server is not None and self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            ip = sock.peerAddress().toString()
            if not is_local(ip):
                sock.close()                       # the internet stays outside
                sock.deleteLater()
                continue
            c = Client(sock, ip)
            self.clients.append(c)
            sock.textMessageReceived.connect(lambda m, c=c: self._on_text(c, m))
            sock.disconnected.connect(lambda c=c: self._gone(c))
            QTimer.singleShot(HELLO_TIMEOUT_MS, lambda c=c: self._hello_timeout(c))

    def _hello_timeout(self, c: Client):
        if c in self.clients and c.device is None:
            self._send(c, {"type": "error", "error": "timeout"})
            c.sock.close()

    def _gone(self, c: Client):
        if c in self.clients:
            self.clients.remove(c)
            if c.device is not None:
                self.clients_changed.emit()
        try:
            c.sock.deleteLater()
        except RuntimeError:
            pass

    def _send(self, c: Client, obj) -> None:
        try:
            c.sock.sendTextMessage(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False))
        except RuntimeError:                         # the socket is already gone
            pass

    def _send_all(self, obj) -> None:
        text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
        for c in self.online():
            self._send(c, text)

    def _on_text(self, c: Client, text: str):
        if len(text) > MAX_MESSAGE:
            return
        try:
            msg = json.loads(text)
        except ValueError:
            return
        if not isinstance(msg, dict):
            return
        kind = msg.get("type")
        if c.device is None:
            if kind == "hello":
                self._hello(c, msg)
            else:
                self._send(c, {"type": "error", "error": "hello_first"})
                c.sock.close()
            return
        self._command(c, kind, msg)

    def _hello(self, c: Client, msg: dict):
        def refuse(err):
            self._send(c, {"type": "error", "error": err})
            c.sock.close()
        if int(msg.get("proto") or 0) != PROTO:
            return refuse("proto")
        name = str(msg.get("device") or "Android")[:60]
        dev_id = str(msg.get("id") or "")[:80] or secrets.token_hex(8)
        token = None
        dev = self.pairing.check_token(msg.get("token") or "") if msg.get("token") else None
        if dev is None:
            if not msg.get("code"):
                return refuse("bad_token" if msg.get("token") else "code_needed")
            r = self.pairing.try_code(c.ip, str(msg.get("code")))
            if r != "ok":
                return refuse(r)
            token = self.pairing.pair(dev_id, name, c.ip)
            dev = self.pairing.check_token(token)
        dev["name"] = name
        dev["seen"] = int(time.time())
        dev["ip"] = c.ip
        c.device = dev
        hello = {"type": "welcome", "proto": PROTO, "pc": pc_name(), "version": VERSION, "id": self.cfg["remote_id"]}
        if token:
            hello["token"] = token
        self._send(c, hello)
        self._send(c, self._playlists_json())
        st = self._state()
        self._send(c, st)
        self.clients_changed.emit()
        self.phone_connected.emit(name)

    def _command(self, c: Client, kind: str, msg: dict):
        h = self.host
        try:
            if kind == "play":
                h.play(msg.get("playlist"), msg.get("track"))
            elif kind == "pause":
                h.pause()
            elif kind == "resume":
                h.resume()
            elif kind == "toggle":
                h.toggle()
            elif kind == "stop":
                h.stop()
            elif kind == "next":
                h.next()
            elif kind == "prev":
                h.prev()
            elif kind == "seek":
                h.seek(float(msg.get("position", 0)))
            elif kind == "volume":
                if "delta" in msg:
                    h.set_volume(h.volume()[0] + int(msg["delta"]))
                else:
                    h.set_volume(int(msg.get("value", 0)))
            elif kind == "mute":
                h.set_muted(msg["on"] if "on" in msg else not h.volume()[1])
            elif kind == "repeat":
                h.set_repeat(msg.get("mode"))
            elif kind == "shuffle":
                h.set_shuffle(msg.get("on"))
            elif kind == "get_cover":
                self._get_cover(c, str(msg.get("id") or ""), int(msg.get("size") or 512))
                return
            elif kind == "get_playlists":
                self._send(c, self._playlists_json())
                return
            elif kind == "get_state":
                self._send(c, self._state())
                return
            else:
                return
        except (TypeError, ValueError, KeyError):
            return
        except Exception:                            # a command must never take the server down
            import traceback
            traceback.print_exc()
            return
        self.poke(force=kind == "seek")

    # ── covers
    def _get_cover(self, c: Client, cid: str, size: int):
        size = min(COVER_SIZES, key=lambda s: abs(s - size))
        data = self.covers.get(cid, size)
        if data is None:
            c.covers.add((cid, size))
            return
        self._send(c, {"type": "cover", "id": cid, "size": size, "mime": "image/jpeg", "data": data})

    def _cover_ready(self, cid: str, size: int, data: str):
        msg = None
        for c in self.online():
            if (cid, size) in c.covers:
                c.covers.discard((cid, size))
                if msg is None:
                    msg = json.dumps({"type": "cover", "id": cid, "size": size, "mime": "image/jpeg", "data": data})
                self._send(c, msg)

    # ── what the phone sees
    def _track(self, tr) -> dict:
        cid = self.covers.note(tr)
        return {"id": tr.uid, "title": tr.display_title(), "artist": tr.artist or tr.albumartist or "",
                "album": tr.album or "", "year": tr.year or "", "genre": tr.genre or "", "n": tr.number or "",
                "duration": round(tr.duration(), 2), "stream": tr.is_stream, "cover": cid,
                "has_cover": self.covers.has(cid) if cid else False}

    def _signature(self):
        sig = []
        for p in self.host.playlists():
            trs = p.tracks
            sig.append((id(p), p.name, p.kind, len(trs), hash(tuple(x.uid for x in trs)),
                        sum(1 for x in trs if x.tagged), sum(x.duration() for x in trs)))
        return tuple(sig), self.host.playing_index(), len(self.covers.known)

    def _playlists_json(self) -> str:
        sig = self._signature()
        if sig != self._pl_sig or not self._pl_json:
            from .playlist import groups
            items = []
            for i, p in enumerate(self.host.playlists()):
                gs = []
                for g in groups(p.tracks):
                    gs.append({"kind": g.kind, "title": g.album() if g.kind == "album" else "",
                               "artist": g.artist() if g.kind == "album" else "",
                               "year": g.year() if g.kind == "album" else "",
                               "tracks": [self._track(x) for x in g.tracks]})
                items.append({"id": i, "name": p.name, "kind": p.kind, "count": len(p.tracks),
                              "duration": round(sum(x.duration() for x in p.tracks), 1), "groups": gs})
            self._pl_rev += 1
            self._pl_json = json.dumps({"type": "playlists", "rev": self._pl_rev,
                                        "playing": self.host.playing_index(), "items": items}, ensure_ascii=False)
            self._pl_sig = self._signature()          # after _track: the covers it noted are in it
        return self._pl_json

    def _state(self, with_pos: bool = True) -> dict:
        h = self.host
        e = h.engine
        cur = e.cur
        pos, dur = h.position()
        vol, muted = h.volume()
        rep, shuf = h.modes()
        st = {"type": "state", "status": h.status(), "playlist": h.playing_index(),
              "track": self._track(cur) if cur is not None else None,
              "volume": vol, "muted": muted, "repeat": rep, "shuffle": shuf, "index": 0, "count": len(e.pl.tracks),
              "next": None, "format": h.format_line(), "on_air": h.on_air() if cur is not None and cur.is_stream else ""}
        if cur is not None:
            st["index"] = e.pl.index_of(cur) + 1
            nxt = h.upcoming()
            if nxt is not None:
                st["next"] = self._track(nxt)
        if with_pos:
            st["position"] = round(pos, 2)
            st["duration"] = round(dur, 2)
        return st

    # ── pushing changes
    def touch(self):
        """The playlists changed (tracks added, tags read, a tab renamed …)."""
        self._pl_dirty = True
        if self.online():
            self.pl_timer.start()

    def poke(self, force: bool = False):
        """Something about the playing track changed: send the state now (if it did change, or always: force)."""
        if self.online():
            QTimer.singleShot(0, lambda: self._tick_state(force))

    def _tick(self):
        if not self.online():
            return
        self._tick_state()
        if self._pl_dirty and not self.pl_timer.isActive():
            self.pl_timer.start()

    def _tick_state(self, force: bool = False):
        if not self.online():
            return
        st = self._state(with_pos=False)
        if force or st != self._state_last:
            self._state_last = st
            full = self._state()
            self._sent_pos = full.get("position", 0.0)
            self._send_all(full)

    def _send_playlists_if_changed(self):
        self._pl_dirty = False
        if not self.online():
            return
        old = self._pl_rev
        text = self._playlists_json()
        if self._pl_rev != old:
            self._send_all(text)

    def _send_position(self):
        if not self.online() or self.host.status() != "play":
            return
        pos, dur = self.host.position()
        self._send_all({"type": "position", "position": round(pos, 2), "duration": round(dur, 2),
                        "status": "play"})
        # the signature check also runs here: a cheap safety net for changes nobody announced
        if self._signature() != self._pl_sig:
            self.touch()

    # ── discovery
    def beacon_bytes(self) -> bytes:
        return json.dumps({"app": APP_KEY, "proto": PROTO, "name": pc_name(), "version": VERSION,
                           "port": self.port, "id": self.cfg.get("remote_id", "")}).encode("utf-8")

    def _broadcast(self):
        if self.udp is None or not self.running:
            return
        data = self.beacon_bytes()
        sent = False
        for iface in QNetworkInterface.allInterfaces():
            fl = iface.flags()
            if not (fl & QNetworkInterface.IsUp) or not (fl & QNetworkInterface.CanBroadcast) \
                    or fl & QNetworkInterface.IsLoopBack:
                continue
            for e in iface.addressEntries():
                ip, bc = e.ip(), e.broadcast()
                if ip.protocol() != QAbstractSocket.IPv4Protocol or bc.isNull() or not is_local(ip.toString()):
                    continue
                self.udp.writeDatagram(data, bc, DISCOVERY_PORT)
                sent = True
        if not sent:
            self.udp.writeDatagram(data, QHostAddress(QHostAddress.Broadcast), DISCOVERY_PORT)
