"""Test media made with ffmpeg: stereo MP3 with tags + cover, FLAC 24/96 5.1, AC-3 5.1, DTS 5.1, TrueHD 5.1,
FLAC 7.1, Opus, AAC, a CUE album image (cp1251, FILE names a .wav while the image is .flac).

Usage: python tests/make_media.py OUT_DIR"""
import os
import subprocess
import sys


def ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def tone(freq: int, secs: float, layout: str = "stereo", rate: int = 48000) -> list[str]:
    n = {"mono": 1, "stereo": 2, "5.1": 6, "7.1": 8}[layout]
    exprs = "|".join(f"0.3*sin({2 * (k + 1)}*PI*{freq}*t)" for k in range(n))
    return ["-f", "lavfi", "-i", f"aevalsrc={exprs}:c={layout}:s={rate}:d={secs}"]


def main(out: str) -> int:
    os.makedirs(out, exist_ok=True)
    cover = os.path.join(out, "cover_src.png")
    ff("-f", "lavfi", "-i", "gradients=s=600x600:c0=0x0d6efd:c1=0x6f42c1:d=1", "-frames:v", "1", cover)

    a = os.path.join(out, "Stereo Album")
    os.makedirs(a, exist_ok=True)
    for i, (title, f) in enumerate((("Первый трек", 440), ("Second Song", 550), ("Третий", 660)), 1):
        ff(*tone(f, 4), "-i", cover, "-map", "0:a", "-map", "1:v", "-c:a", "libmp3lame", "-b:a", "192k",
           "-c:v", "png", "-disposition:v", "attached_pic", "-id3v2_version", "3",
           "-metadata", f"title={title}", "-metadata", "artist=ArtCore Band", "-metadata", "album=Test Album",
           "-metadata", "date=2024", "-metadata", f"track={i}/3", "-metadata", "genre=Electronic",
           "-metadata", "REPLAYGAIN_TRACK_GAIN=-6.00 dB",
           os.path.join(a, f"{i:02d} - {title}.mp3"))

    s = os.path.join(out, "Surround")
    os.makedirs(s, exist_ok=True)
    ff(*tone(300, 4, "5.1", 96000), "-c:a", "flac", "-sample_fmt", "s32", "-bits_per_raw_sample", "24",
       "-metadata", "title=FLAC 5.1", "-metadata", "artist=Surround Test", "-metadata", "album=Multichannel",
       "-metadata", "tracknumber=1", os.path.join(s, "01 flac51.flac"))
    ff(*tone(300, 4, "5.1"), "-c:a", "ac3", "-b:a", "448k", os.path.join(s, "02 ac3.ac3"))
    ff(*tone(300, 4, "5.1"), "-c:a", "dca", "-strict", "-2", os.path.join(s, "03 dts.dts"))
    try:
        ff(*tone(300, 4, "5.1"), "-c:a", "truehd", "-strict", "-2", os.path.join(s, "04 truehd.thd"))
    except subprocess.CalledProcessError:
        print("no truehd encoder, skipped")
    ff(*tone(300, 4, "7.1"), "-c:a", "flac", "-metadata", "title=FLAC 7.1", os.path.join(s, "05 flac71.flac"))
    ff("-i", cover, "-vf", "scale=300:300", os.path.join(s, "folder.jpg"))

    o = os.path.join(out, "Misc")
    os.makedirs(o, exist_ok=True)
    ff(*tone(500, 3), "-c:a", "libopus", "-b:a", "128k", "-metadata", "title=Opus tone", "-metadata", "artist=Misc",
       os.path.join(o, "opus.opus"))
    ff(*tone(500, 3, rate=44100), "-c:a", "aac", "-b:a", "192k", "-metadata", "title=AAC tone", os.path.join(o, "aac.m4a"))
    ff(*tone(500, 3, rate=44100), "-c:a", "pcm_s16le", os.path.join(o, "plain.wav"))

    c = os.path.join(out, "CUE Album")
    os.makedirs(c, exist_ok=True)
    parts = []
    for i, f in enumerate((330, 440, 550), 1):
        p = os.path.join(c, f"part{i}.wav")
        ff(*tone(f, 3, rate=44100), "-c:a", "pcm_s16le", p)
        parts.append(p)
    lst = os.path.join(c, "list.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{p}'\n" for p in parts)
    ff("-f", "concat", "-safe", "0", "-i", lst, "-c:a", "flac", os.path.join(c, "Image.flac"))
    for p in parts + [lst]:
        os.remove(p)
    sheet = ('REM GENRE Rock\nREM DATE 1999\nPERFORMER "Кино"\nTITLE "Альбом образом"\nFILE "Image.wav" WAVE\n'
             '  TRACK 01 AUDIO\n    TITLE "Группа крови"\n    INDEX 01 00:00:00\n'
             '  TRACK 02 AUDIO\n    TITLE "Звезда по имени Солнце"\n    INDEX 00 00:02:70\n    INDEX 01 00:03:00\n'
             '  TRACK 03 AUDIO\n    TITLE "Кукушка"\n    PERFORMER "Виктор Цой"\n    INDEX 01 00:06:00\n')
    with open(os.path.join(c, "Image.cue"), "wb") as fh:
        fh.write(sheet.encode("cp1251"))
    os.remove(cover)
    print("media in", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/acm_media"))
