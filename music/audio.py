"""Sound: the 10-band equalizer, centre / subwoofer levels, stereo → 5.1 upmix, 7.1 → 5.1 downmix,
the output channel layout for WASAPI and the format line («FLAC 24/96 5.1 → PCM 6 кан.»)."""
from __future__ import annotations

BANDS = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
PRESETS = {                          # dB per band
    "flat":       (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    "bass":       (6, 5, 4, 2, 0, 0, 0, 0, 0, 0),
    "treble":     (0, 0, 0, 0, 0, 0, 2, 4, 5, 6),
    "vocal":      (-3, -2, -1, 1, 3, 4, 4, 3, 1, 0),
    "rock":       (5, 4, 2, -1, -2, -1, 1, 3, 4, 5),
    "pop":        (-1, 1, 3, 4, 3, 0, -1, -1, 1, 2),
    "jazz":       (3, 2, 1, 2, -1, -1, 0, 1, 2, 3),
    "classical":  (4, 3, 2, 1, -1, -1, 0, 2, 3, 4),
    "electronic": (6, 5, 2, 0, -2, 1, 0, 2, 4, 5),
    "loudness":   (5, 4, 2, 0, -1, 0, 1, 2, 4, 5),
}

# output layouts for audio-channels (mpv): "auto" follows the Speakers setup in Windows
CHANNEL_MODES = {"auto": "auto-safe", "5.1": "5.1", "stereo": "stereo"}

# speaker order of the ffmpeg "5.1" layout: what c0..c5 of a pan filter mean
SPEAKERS_51 = ("FL", "FR", "FC", "LFE", "BL", "BR")


def eq_filter(gains) -> str:
    if not any(gains):
        return ""
    entries = ";".join(f"entry({f},{g:g})" for f, g in zip(BANDS, gains))
    return f"lavfi=[firequalizer=gain_entry='{entries}']"


def db_to_gain(db: float) -> float:
    return 10 ** (float(db) / 20.0)


def levels_filter(channels: int, layout: str, center_db: float, lfe_db: float) -> str:
    """Centre (c2) and LFE (c3) gains; the same index in 5.1, 5.1(side), 6.1 and 7.1."""
    if channels < 6 or (not center_db and not lfe_db):
        return ""
    lay = layout if layout and not layout.startswith("unknown") else f"{channels}c"
    parts = []
    for i in range(channels):
        g = db_to_gain(center_db) if i == 2 else db_to_gain(lfe_db) if i == 3 else 1.0
        parts.append(f"c{i}={g:.4f}*c{i}")
    return "lavfi=[pan=" + lay + "|" + "|".join(parts) + "]"


def out_layout(mode: str, src_channels: int, upmix: bool) -> tuple[int, str]:
    """(channels, layout) after our own filters — what levels_filter works on."""
    if mode == "stereo":
        return min(src_channels, 2), ""
    if src_channels == 2 and upmix:
        return 6, "5.1"
    if mode == "5.1" and src_channels > 6:
        return 6, "5.1"
    return src_channels, ""


METER = "@meter:lavfi=[astats=metadata=1:reset=1:measure_overall=none:measure_perchannel=Peak_level+RMS_level]"
# channel names of what the meter sees, in ffmpeg's order (the rears of 5.1 are SL / SR: the Z906's surrounds)
METER_NAMES = {1: ["FC"], 2: ["FL", "FR"], 3: ["FL", "FR", "FC"], 4: ["FL", "FR", "SL", "SR"],
               5: ["FL", "FR", "FC", "SL", "SR"], 6: ["FL", "FR", "FC", "LFE", "SL", "SR"],
               7: ["FL", "FR", "FC", "LFE", "BC", "SL", "SR"], 8: ["FL", "FR", "FC", "LFE", "BL", "BR", "SL", "SR"]}
# how the meters lay them out: left to right as the speakers stand
METER_ORDER = ["FL", "FC", "FR", "LFE", "SL", "BL", "BC", "BR", "SR"]


def parse_meter(md: dict | None) -> list[tuple[str, float, float]]:
    """af-metadata/meter → [(channel, rms dB, peak dB)] in METER_ORDER; -inf → -120."""
    if not md:
        return []
    vals: dict[int, list[float]] = {}
    for k, v in md.items():
        bits = str(k).split(".")                  # lavfi.astats.<n>.RMS_level
        if len(bits) != 4 or bits[1] != "astats" or not bits[2].isdigit():
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if x != x or x < -120:                    # nan / -inf
            x = -120.0
        slot = vals.setdefault(int(bits[2]), [-120.0, -120.0])
        slot[0 if bits[3] == "RMS_level" else 1] = x
    names = METER_NAMES.get(len(vals)) or [f"{i}" for i in sorted(vals)]
    out = [(names[i] if i < len(names) else str(i + 1), *vals[n]) for i, n in enumerate(sorted(vals))]
    return sorted(out, key=lambda c: METER_ORDER.index(c[0]) if c[0] in METER_ORDER else 99)


def build(cfg: dict, src_channels: int, src_layout: str = "", meter: bool = False) -> str:
    """The whole af chain for a file with src_channels channels (+ the level meter at its end)."""
    mode = cfg.get("channels", "auto")
    parts = []
    ch, lay = src_channels, src_layout
    if mode != "stereo":
        if src_channels == 2 and cfg.get("upmix"):
            parts.append("lavfi=[surround=chl_out=5.1:lfe=1]")
            ch, lay = 6, "5.1"
        elif mode == "5.1" and src_channels > 6:            # 7.1 → 5.1 before the level filter
            parts.append("lavfi=[aformat=channel_layouts=5.1]")
            ch, lay = 6, "5.1"
        parts.append(levels_filter(ch, lay, cfg.get("center_db", 0), cfg.get("lfe_db", 0)))
    parts.append(eq_filter(cfg.get("eq", [0] * 10)))
    if meter:
        parts.append(METER)
    return ",".join(p for p in parts if p)


# ── the format line ──────────────────────────────────────────
CODEC_NAMES = {
    "flac": "FLAC", "alac": "ALAC", "aac": "AAC", "aac_latm": "AAC", "opus": "Opus", "vorbis": "Vorbis",
    "mp3": "MP3", "mp3float": "MP3", "mp2": "MP2", "ape": "APE", "wavpack": "WavPack", "tak": "TAK", "tta": "TTA",
    "ac3": "AC-3", "eac3": "E-AC-3", "dts": "DTS", "truehd": "TrueHD", "mlp": "MLP", "wmav2": "WMA",
    "wmapro": "WMA Pro", "wmalossless": "WMA Lossless", "musepack7": "Musepack", "musepack8": "Musepack",
    "speex": "Speex",
}
LOSSLESS = {"FLAC", "ALAC", "APE", "WavPack", "TAK", "TTA", "PCM", "WMA Lossless", "TrueHD", "MLP", "DTS-HD MA", "DSD"}


def codec_label(codec: str, profile: str = "") -> str:
    c = (codec or "").lower()
    if c.startswith("pcm_"):
        return "PCM"
    if c.startswith("dsd_"):
        return "DSD"
    if c == "dts":
        p = (profile or "").lower()
        if "ma" in p or "master" in p:
            return "DTS-HD MA"
        if "hra" in p or "high res" in p or "hd hra" in p:
            return "DTS-HD HRA"
        if "x" in p and "96" in p:
            return "DTS 96/24"
        if "es" in p:
            return "DTS-ES"
        return "DTS"
    if c == "eac3" and "atmos" in (profile or "").lower():
        return "E-AC-3 Atmos"
    if c == "truehd" and "atmos" in (profile or "").lower():
        return "TrueHD Atmos"
    return CODEC_NAMES.get(c, (codec or "?").upper())


def layout_label(channels: int, layout: str = "") -> str:
    lay = (layout or "").lower()
    if channels == 1:
        return "mono"
    if channels == 2:
        return "2.0"
    for name in ("7.1", "6.1", "5.1", "5.0", "4.1", "4.0", "3.1", "3.0", "2.1"):
        if lay.startswith(name):
            return name
    return {3: "2.1", 4: "4.0", 5: "5.0", 6: "5.1", 7: "6.1", 8: "7.1"}.get(channels, f"{channels} ch")


def rate_label(rate: int) -> str:
    if not rate:
        return ""
    k = rate / 1000.0
    return f"{k:g}" if abs(k - round(k, 1)) < 1e-6 else f"{k:.1f}"


def dsd_label(rate: int) -> str:
    """DSD64 = 2.8224 MHz (the demuxer reports the bit rate / 8 or the true rate, depending on the build)."""
    for base in (2822400, 352800):
        if rate and rate % base == 0:
            return f"DSD{64 * rate // base}"
    return "DSD"


def describe(codec: str, profile: str, bits: int, rate: int, channels: int, layout: str,
             out_channels: int, kbps: int = 0, upmix: bool = False, out_word: str = "ch") -> str:
    """«FLAC 24/96 5.1 → PCM 6 ch» — source format, then what goes to Windows."""
    name = codec_label(codec, profile)
    if name == "DSD":
        src = f"{dsd_label(rate)} {layout_label(channels, layout)}"
    else:
        head = name
        if name in LOSSLESS and bits:
            head += f" {bits}/{rate_label(rate)}"
        elif rate:
            head += (f" {kbps} kbps" if kbps else "") + f" {rate_label(rate)} kHz"
        src = f"{head} {layout_label(channels, layout)}"
    if not out_channels:
        return src
    tail = f"PCM {out_channels} {out_word}"
    if upmix and channels == 2 and out_channels >= 6:
        tail += " (upmix)"
    return f"{src} → {tail}"
