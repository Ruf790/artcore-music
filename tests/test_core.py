"""No mpv, no Qt windows: CUE, M3U, playlist order, format line, filters, tags, test signals."""
import os
import struct

from music import audio, cue, meta, playlist, testtone
from music.playlist import Playlist, Track


def test_cue_cp1251_and_ranges(media):
    tr = playlist.expand([os.path.join(media, "CUE Album", "Image.cue")])
    assert [t.title for t in tr] == ["Группа крови", "Звезда по имени Солнце", "Кукушка"]
    assert [t.artist for t in tr] == ["Кино", "Кино", "Виктор Цой"]
    assert tr[0].album == "Альбом образом" and tr[0].year == "1999" and tr[0].genre == "Rock"
    assert tr[0].path.endswith("Image.flac")                       # FILE says .wav, the folder has .flac
    assert (tr[0].start, tr[0].end) == (0.0, 3.0)
    assert (tr[1].start, tr[1].end) == (3.0, 6.0)                  # INDEX 01, not INDEX 00
    assert tr[2].end is None


def test_folder_uses_cue_instead_of_image(media):
    tr = playlist.expand([os.path.join(media, "CUE Album")])
    assert len(tr) == 3 and all(t.is_cue for t in tr)


def test_cue_quoting():
    text = 'PERFORMER Unquoted Artist\nFILE "C:\\Music\\a b.flac" WAVE\nTRACK 01 AUDIO\nTITLE Don\'t Stop\nINDEX 01 01:02:37\n'
    tr = cue.parse_text(text, "/x/a.cue")
    assert tr[0].title == "Don't Stop" and tr[0].performer == "Unquoted Artist"
    assert abs(tr[0].start - (62 + 37 / 75)) < 1e-6


def test_m3u_roundtrip(media, tmp_path):
    tracks = playlist.expand([os.path.join(media, "Stereo Album"), os.path.join(media, "CUE Album")])
    for t in tracks:
        playlist.fill_tags(t)
    p = str(tmp_path / "list.m3u8")
    playlist.write_m3u(p, tracks)
    text = open(p, encoding="utf-8").read()
    assert text.startswith("#EXTM3U") and text.count("Image.cue") == 1
    back = playlist.read_m3u(p)
    assert [os.path.basename(t.path) for t in back][:3] == [os.path.basename(t.path) for t in tracks[:3]]
    assert len(back) == 6 and back[3].title == "Группа крови"
    assert back[0].artist == "ArtCore Band"


def test_tags_and_cover(media):
    f = os.path.join(media, "Stereo Album", "01 - Первый трек.mp3")
    tg = meta.read(f)
    assert (tg.title, tg.artist, tg.album, tg.year, tg.track) == ("Первый трек", "ArtCore Band", "Test Album", "2024", "1")
    assert meta.embedded_picture(f)[:4] == b"\x89PNG"
    flac = os.path.join(media, "Surround", "01 flac51.flac")
    tg = meta.read(flac)
    assert (tg.bits, tg.rate, tg.channels) == (24, 96000, 6)
    assert meta.folder_cover(flac).endswith("folder.jpg")
    assert meta.cover_bytes(flac)[:2] == b"\xff\xd8"


def _pl(n):
    pl = Playlist()
    pl.add([Track(path=f"/m/{i}.flac", title=str(i)) for i in range(n)])
    return pl


def test_order_repeat():
    pl = _pl(3)
    a, b, c = pl.tracks
    assert pl.next_after(a).uid == b.uid and pl.next_after(c) is None
    pl.repeat = "all"
    assert pl.next_after(c).uid == a.uid and pl.prev_before(a).uid == c.uid
    pl.repeat = "one"
    assert pl.next_after(b, auto=True).uid == b.uid             # track ends: again
    assert pl.next_after(b, auto=False).uid == c.uid            # ⏭: the next one


def test_order_shuffle_and_remove():
    pl = _pl(20)
    first = pl.tracks[5]
    pl.set_shuffle(True, first)
    seen, t = [first.uid], first
    while True:
        t = pl.next_after(t)
        if t is None:
            break
        seen.append(t.uid)
    assert sorted(seen) == sorted(x.uid for x in pl.tracks) and seen != [x.uid for x in pl.tracks]
    pl.set_shuffle(False, None)
    cur = pl.tracks[3]
    pl.remove({cur.uid}, cur)
    assert pl.next_after(cur).uid == pl.tracks[3].uid           # what took its place


def test_format_line():
    assert audio.describe("flac", "", 24, 96000, 6, "5.1", 6, out_word="кан.") == "FLAC 24/96 5.1 → PCM 6 кан."
    assert audio.describe("dts", "DTS-HD MA", 24, 48000, 8, "7.1", 6) == "DTS-HD MA 24/48 7.1 → PCM 6 ch"
    assert audio.describe("ac3", "", 0, 48000, 6, "5.1(side)", 6, kbps=448) == "AC-3 448 kbps 48 kHz 5.1 → PCM 6 ch"
    assert audio.describe("flac", "", 16, 44100, 2, "stereo", 6, upmix=True) == "FLAC 16/44.1 2.0 → PCM 6 ch (upmix)"
    assert audio.describe("dsd_lsbf_planar", "", 1, 2822400, 6, "5.1", 6).startswith("DSD64 5.1")
    assert audio.describe("truehd", "", 24, 48000, 6, "5.1(side)", 6).startswith("TrueHD 24/48 5.1")


def test_filters():
    cfg = {"channels": "auto", "upmix": True, "center_db": 6.0, "lfe_db": 0, "eq": [0] * 10}
    af = audio.build(cfg, 2, "stereo")
    assert af.startswith("lavfi=[surround=chl_out=5.1") and "c2=1.9953*c2" in af
    cfg.update(channels="5.1", upmix=False)
    assert audio.build(cfg, 8, "7.1").startswith("lavfi=[aformat=channel_layouts=5.1],lavfi=[pan=5.1|")
    cfg.update(channels="stereo")
    assert audio.build(cfg, 6, "5.1") == ""                     # mpv mixes down, no level filter
    cfg.update(eq=[1] + [0] * 9)
    assert "firequalizer" in audio.build(cfg, 2, "stereo")


def test_testtone_header(tmp_path):
    p = testtone.signal_file("LFE", str(tmp_path))
    raw = open(p, "rb").read(80)
    assert raw[:4] == b"RIFF" and raw[8:12] == b"WAVE"
    fmt_tag, nch, rate = struct.unpack("<HHI", raw[20:28])
    mask = struct.unpack("<I", raw[40:44])[0]
    assert (fmt_tag, nch, rate, mask) == (0xFFFE, 6, 48000, 0x3F)


def test_waveform_peaks():
    from array import array
    from music.waveform import peaks_from_pcm
    quiet, loud = array("h", [100, -100] * 500), array("h", [20000, -20000] * 500)
    p = peaks_from_pcm((quiet + loud).tobytes(), 10)
    assert len(p) == 10 and max(p) == 255
    assert all(v < 5 for v in p[:5]) and all(v > 250 for v in p[5:])
    assert peaks_from_pcm(b"") == b""
