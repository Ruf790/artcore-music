"""The phone remote: who may connect, the code and the token, the protocol, commands through a QWebSocket client."""
import base64
import json
import os
import sys

import pytest
from conftest import ROOT, pump

sys.path.insert(0, os.path.join(ROOT, "tools"))

from music import remote                                       # noqa: E402
from music.playlist import Playlist, Track, stamp               # noqa: E402


# ── who may connect ──────────────────────────────────────────
@pytest.mark.parametrize("ip", ["192.168.1.23", "10.0.0.5", "172.16.0.1", "172.31.255.254", "127.0.0.1", "::1",
                                "::ffff:192.168.0.10", "[::ffff:10.1.2.3]"])
def test_local_addresses_get_in(ip):
    assert remote.is_local(ip)


@pytest.mark.parametrize("ip", ["8.8.8.8", "172.15.0.1", "172.32.0.1", "100.64.0.1", "169.254.1.1", "11.0.0.1",
                                "2a00:1450::1", "fe80::1", "::ffff:8.8.8.8", "", "nonsense", "192.168.1"])
def test_outside_addresses_stay_out(ip):
    assert not remote.is_local(ip)


# ── the code and the token ───────────────────────────────────
class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_code_is_four_digits_and_kept():
    cfg = {}
    p = remote.Pairing(cfg)
    assert len(p.code) == 4 and p.code.isdigit() and cfg["remote_code"] == p.code
    assert remote.Pairing(cfg).code == p.code                   # the same code after a restart
    old = p.code
    codes = {p.renew_code() for _ in range(20)}
    assert all(len(c) == 4 and c.isdigit() for c in codes) and (len(codes) > 1 or old not in codes)


def test_wrong_codes_are_limited_per_address():
    cfg = {"remote_code": "4821"}
    clock = Clock()
    p = remote.Pairing(cfg, clock=clock)
    for _ in range(4):
        assert p.try_code("192.168.1.50", "0000") == "bad_code"
    assert p.try_code("192.168.1.50", "1111") == "too_many"      # the 5th wrong one closes the door
    assert p.try_code("192.168.1.50", "4821") == "too_many"      # even the right code, for a minute
    assert p.try_code("192.168.1.51", "4821") == "ok"            # another phone is not punished
    clock.t += 61
    assert p.try_code("192.168.1.50", "4821") == "ok"


def test_token_replaces_the_code_and_can_be_forgotten():
    cfg = {"remote_code": "1234"}
    p = remote.Pairing(cfg)
    tok = p.pair("phone-a", "Pixel 7", "192.168.1.5")
    assert len(tok) >= 32 and tok not in json.dumps(cfg)          # only a hash is kept
    assert p.check_token(tok)["name"] == "Pixel 7"
    assert p.check_token("x" + tok) is None and p.check_token("") is None
    tok2 = p.pair("phone-a", "Pixel 7", "192.168.1.5")           # pairing again: the old token stops working
    assert p.check_token(tok) is None and p.check_token(tok2) is not None
    assert len(p.devices()) == 1
    p.forget("phone-a")
    assert p.check_token(tok2) is None and p.devices() == []


# ── the protocol, against a stand-in player ──────────────────
class FakeEngine:
    def __init__(self, pl):
        self.pl = pl
        self.cur = None
        self.stopped = True
        self.paused = True
        self.icy = ""
        self.queue = []
        self.ctx = None
        self.stop_after = None


class FakeHost(remote.WindowHost):
    def __init__(self):
        self.calls = []
        a = Playlist("Rock")
        a.add(stamp([Track(path=f"/m/Album/{i}.flac", title=f"Song {i}", artist="Band", album="Album", year="2001",
                           length=100.0 + i) for i in range(1, 4)]))
        a.add(stamp([Track(path="/m/loose.mp3", title="Loose", length=60.0)]))
        b = Playlist("Radio")
        b.add(stamp([Track(path="http://radio.example/live", title="Example FM")]))
        self.pls = [a, b]
        self._engine = FakeEngine(a)
        self.vol = 70
        self.muted = False

    @property
    def engine(self):
        return self._engine

    def playlists(self):
        return self.pls

    def playing_index(self):
        return self.pls.index(self.engine.pl)

    def position(self):
        return (12.5, self.engine.cur.duration()) if self.engine.cur else (0.0, 0.0)

    def volume(self):
        return self.vol, self.muted

    def format_line(self):
        return "FLAC · 24 bit · 96 kHz" if self.engine.cur else ""

    def play(self, pl_index, uid):
        p, tr = self.find(pl_index, uid)
        self.calls.append(("play", tr.title if tr else None))
        if tr is not None:
            e = self.engine
            e.pl, e.cur, e.stopped, e.paused = p, tr, False, False

    def pause(self):
        self.calls.append(("pause",))
        self.engine.paused = True

    def resume(self):
        self.calls.append(("resume",))
        self.engine.paused = False

    def toggle(self):
        self.engine.paused = not self.engine.paused

    def stop(self):
        self.calls.append(("stop",))
        self.engine.stopped = True
        self.engine.paused = True

    def next(self):
        self.calls.append(("next",))
        e = self.engine
        i = e.pl.index_of(e.cur)
        if 0 <= i < len(e.pl.tracks) - 1:
            e.cur = e.pl.tracks[i + 1]

    def prev(self):
        self.calls.append(("prev",))

    def seek(self, sec):
        self.calls.append(("seek", sec))

    def set_volume(self, v):
        self.vol = max(0, min(100, int(v)))

    def set_muted(self, on):
        self.muted = bool(on)

    def set_repeat(self, mode):
        for p in self.pls:
            p.repeat = mode or "all"

    def set_shuffle(self, on):
        self.engine.pl.shuffle = (not self.engine.pl.shuffle) if on is None else bool(on)


@pytest.fixture()
def server(qapp):
    cfg = {"remote": True, "remote_code": "4821"}
    host = FakeHost()
    srv = remote.RemoteServer(host, cfg)
    assert srv.start(0), srv.error
    yield srv, host, cfg
    srv.shutdown()


def _client(qapp, srv):
    from remote_client import RemoteClient
    c = RemoteClient(qapp)
    assert c.open("127.0.0.1", srv.port)
    return c


def test_pairing_then_token(qapp, server):
    srv, host, cfg = server
    c = _client(qapp, srv)
    c.hello(code="0000")
    err = c.wait("error")
    assert err["error"] == "bad_code"
    assert c.pump(2, lambda: c.closed)

    c = _client(qapp, srv)
    c.hello(code="4821", device="Pixel 7", dev_id="p7")
    w = c.wait("welcome")
    assert w and w["proto"] == 1 and w["token"] and w["version"] and w["pc"]
    pls = c.wait("playlists") or c.last("playlists")
    st = c.wait("state") or c.last("state")
    assert [p["name"] for p in pls["items"]] == ["Rock", "Radio"]
    rock = pls["items"][0]
    assert [g["kind"] for g in rock["groups"]] == ["album", "singles"]
    alb = rock["groups"][0]
    assert alb["title"] == "Album" and alb["artist"] == "Band" and alb["year"] == "2001"
    assert [x["title"] for x in alb["tracks"]] == ["Song 1", "Song 2", "Song 3"]
    assert alb["tracks"][0]["duration"] == 101.0 and alb["tracks"][0]["cover"]
    assert pls["items"][1]["groups"][0]["kind"] == "radio" and pls["items"][1]["groups"][0]["tracks"][0]["stream"]
    assert st["status"] == "stop" and st["volume"] == 70 and st["track"] is None
    assert cfg["remote_devices"][0]["name"] == "Pixel 7" and srv.is_online("p7")
    token = w["token"]
    c.close()

    c = _client(qapp, srv)                                       # next time: the token, no code
    c.hello(token=token, dev_id="p7")
    w = c.wait("welcome")
    assert w and "token" not in w
    c.close()

    c = _client(qapp, srv)
    c.hello(token="forged", dev_id="p7")
    assert c.wait("error")["error"] == "bad_token"


def test_too_many_wrong_codes(qapp, server):
    srv, host, cfg = server
    for i in range(5):
        c = _client(qapp, srv)
        c.hello(code="%04d" % i)
        err = c.wait("error")
        assert err["error"] == ("too_many" if i == 4 else "bad_code")
    c = _client(qapp, srv)
    c.hello(code="4821")
    assert c.wait("error")["error"] == "too_many"


def test_commands_before_hello_are_refused(qapp, server):
    srv, host, cfg = server
    c = _client(qapp, srv)
    c.send("play", playlist=0, track=1)
    assert c.wait("error")["error"] == "hello_first"
    assert host.calls == []


def test_outside_address_is_dropped(qapp, server, monkeypatch):
    srv, host, cfg = server
    monkeypatch.setattr(remote, "is_local", lambda ip: False)    # as if 127.0.0.1 were somewhere on the internet
    c = _client(qapp, srv)
    c.hello(code="4821")
    assert c.pump(3, lambda: c.closed)
    assert c.last("welcome") is None and srv.online() == []


def test_commands_and_state(qapp, server):
    srv, host, cfg = server
    c = _client(qapp, srv)
    c.hello(code="4821")
    pls = c.wait("playlists")
    tid = pls["items"][0]["groups"][0]["tracks"][1]["id"]
    c.send("play", playlist=0, track=tid)
    st = c.wait("state", check=lambda m: m["status"] == "play")
    assert st and st["track"]["title"] == "Song 2" and st["index"] == 2 and st["count"] == 4
    assert st["next"]["title"] == "Song 3" and st["format"] == "FLAC · 24 bit · 96 kHz"
    assert st["position"] == 12.5 and st["duration"] == 102.0
    pos = c.wait("position", 3)
    assert pos and pos["status"] == "play"
    c.send("pause")
    assert c.wait("state", check=lambda m: m["status"] == "pause")
    c.send("resume")
    assert c.wait("state", check=lambda m: m["status"] == "play")
    c.send("next")
    assert c.wait("state", check=lambda m: m["track"]["title"] == "Song 3")
    c.send("volume", value=35)
    assert c.wait("state", check=lambda m: m["volume"] == 35)
    c.send("volume", delta=-5)
    assert c.wait("state", check=lambda m: m["volume"] == 30)
    c.send("repeat", mode="one")
    assert c.wait("state", check=lambda m: m["repeat"] == "one")
    c.send("shuffle", on=True)
    assert c.wait("state", check=lambda m: m["shuffle"] is True)
    c.send("seek", position=42)
    c.send("stop")
    assert c.wait("state", check=lambda m: m["status"] == "stop")
    radio = pls["items"][1]["groups"][0]["tracks"][0]["id"]
    c.send("play", playlist=1, track=radio)
    st = c.wait("state", check=lambda m: m["playlist"] == 1)
    assert st["track"]["stream"] and st["track"]["title"] == "Example FM"
    c.send("play", playlist=0, track=999999)                        # a track that is not there: nothing happens
    pump(qapp, 0.3)
    assert ("play", None) in host.calls and ("seek", 42.0) in host.calls


def test_playlist_changes_are_pushed(qapp, server):
    srv, host, cfg = server
    c = _client(qapp, srv)
    c.hello(code="4821")
    first = c.wait("playlists")
    host.pls[0].add(stamp([Track(path="/m/new.mp3", title="New one", length=10.0)]))
    srv.touch()
    nxt = c.wait("playlists", 4)
    assert nxt and nxt["rev"] > first["rev"]
    titles = [x["title"] for g in nxt["items"][0]["groups"] for x in g["tracks"]]
    assert "New one" in titles


def test_forget_drops_the_phone(qapp, server):
    srv, host, cfg = server
    c = _client(qapp, srv)
    c.hello(code="4821", dev_id="gone")
    tok = c.wait("welcome")["token"]
    srv.disconnect_device("gone")
    assert c.wait("error")["error"] == "forgotten"
    assert c.pump(2, lambda: c.closed)
    c = _client(qapp, srv)
    c.hello(token=tok, dev_id="gone")
    assert c.wait("error")["error"] == "bad_token"


def test_hello_timeout(qapp, server, monkeypatch):
    srv, host, cfg = server
    monkeypatch.setattr(remote, "HELLO_TIMEOUT_MS", 300)
    c = _client(qapp, srv)
    assert c.pump(3, lambda: c.closed)


def test_beacon():
    srv = remote.RemoteServer(FakeHost(), {"remote_code": "1111"})
    srv.port = 47870
    info = json.loads(srv.beacon_bytes())
    assert info["app"] == "artcore-music" and info["port"] == 47870 and info["name"] and info["version"]
    assert info["id"] == srv.cfg["remote_id"]
    srv.shutdown()


def test_cover_scaled_jpeg():
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (1200, 900), (200, 30, 50)).save(buf, "PNG")
    out = remote.scale_jpeg(buf.getvalue(), 512)
    im = Image.open(io.BytesIO(out))
    assert im.format == "JPEG" and max(im.size) == 512


# ── the real player ──────────────────────────────────────────
def test_window_remote_play_pause_stop(qapp, mpvmod, media, data_dir):
    from music import config
    from music.window import MainWindow
    from remote_client import RemoteClient
    cfg = config.load()
    cfg.update(media_keys=False, check_updates=False, remote=False)
    w = MainWindow(mpvmod, cfg)
    w.show()
    w.open_paths([os.path.join(media, "Stereo Album"), os.path.join(media, "Surround")], play=False)
    pump(qapp, 1.5, lambda: all(x.tagged for x in w.pl.tracks))
    assert w.remote.start(0)
    c = RemoteClient(qapp)
    assert c.open("127.0.0.1", w.remote.port)
    c.hello(code=cfg["remote_code"], device="CI phone")
    assert c.wait("welcome")
    pls = c.wait("playlists") or c.last("playlists")
    groups = pls["items"][0]["groups"]
    album = next(g for g in groups if g["title"] == "Test Album")
    assert [x["title"] for x in album["tracks"]] == ["Первый трек", "Second Song", "Третий"]
    assert album["artist"] == "ArtCore Band" and album["year"] == "2024"
    second = album["tracks"][1]
    c.send("play", playlist=0, track=second["id"])
    st = c.wait("state", 6, check=lambda m: m["status"] == "play" and m["track"] and m["track"]["id"] == second["id"])
    assert st and w.engine.cur.uid == second["id"] and not w.engine.paused
    assert pump(qapp, 4, lambda: w.remote.host.format_line().startswith("MP3"))
    c.send("pause")
    assert c.wait("state", 4, check=lambda m: m["status"] == "pause") and w.engine.paused
    c.send("resume")
    assert c.wait("state", 4, check=lambda m: m["status"] == "play") and not w.engine.paused
    c.send("next")
    assert c.wait("state", 4, check=lambda m: m["track"]["title"] == "Третий")
    c.send("stop")
    assert c.wait("state", 4, check=lambda m: m["status"] == "stop") and w.engine.stopped
    c.send("volume", value=33)
    assert c.wait("state", 3, check=lambda m: m["volume"] == 33) and w.vol.value() == 33
    # the cover of the album with folder.jpg
    surround = next(g for g in groups if g["title"] == "Multichannel" or any(x["title"] == "FLAC 5.1" for x in g["tracks"]))
    cid = next(x["cover"] for x in surround["tracks"] if x["title"] == "FLAC 5.1")
    c.send("get_cover", id=cid, size=256)
    cov = c.wait("cover", 5)
    assert cov and cov["id"] == cid and cov["data"]
    assert base64.b64decode(cov["data"])[:2] == b"\xff\xd8"
    c.close()
    w.close()


def test_discovery_broadcast(qapp, server):
    """The phone's side: a UDP socket on 47871 hears the PC within a couple of seconds."""
    from PySide6.QtNetwork import QHostAddress, QUdpSocket
    srv, host, cfg = server
    udp = QUdpSocket()
    if not udp.bind(QHostAddress.AnyIPv4, remote.DISCOVERY_PORT, QUdpSocket.ShareAddress | QUdpSocket.ReuseAddressHint):
        pytest.skip("UDP 47871 is taken here: " + udp.errorString())
    got = []

    def read():
        while udp.hasPendingDatagrams():
            got.append(json.loads(bytes(udp.receiveDatagram().data())))
        return any(g.get("port") == srv.port for g in got)
    assert pump(qapp, 6, read), got
    info = next(g for g in got if g.get("port") == srv.port)
    assert info["app"] == "artcore-music" and info["proto"] == 1 and info["version"]
    udp.close()
