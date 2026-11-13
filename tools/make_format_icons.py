"""File-type icons for the formats ArtCore Music opens: assets/formats/<ext>.ico (+ a preview sheet).

A page with a folded corner in the colour of the format's family, the format name in big letters, a small
glyph on top (sound wave / 5.1 / list) and a tag at the bottom (LOSSLESS, SURROUND, PLAYLIST…). Every size of
the .ico is drawn on its own (no blurry downscaling): 16–24 px show the page, the glyph and a stripe only,
32 px and up carry the name.

    python tools/make_format_icons.py [font.ttf/otf] [--preview sheet.png]   # Inter / Poppins Bold if found
The .ico files are committed; this script is only needed to change them."""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "formats")
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
SS = 4                                     # supersampling

# family: (top colour, bottom colour, tag, glyph)
FAMILIES = {
    "lossless": ("#2fb36b", "#16774a", "LOSSLESS", "wave"),
    "apple":    ("#b9bcc6", "#6f7380", "LOSSLESS", "wave"),
    "rare":     ("#8f6ad8", "#5a3aa6", "LOSSLESS", "wave"),
    "pcm":      ("#a8a03a", "#6f6a1d", "PCM", "wave"),
    "dsd":      ("#2bb3c6", "#167a8c", "HI-RES", "wave"),
    "mp3":      ("#3d8bfd", "#1d4fbf", "", "wave"),
    "aac":      ("#f08a3c", "#c0551a", "", "wave"),
    "xiph":     ("#e0507a", "#a72a52", "", "wave"),
    "wma":      ("#4a6fa5", "#2c4670", "", "wave"),
    "other":    ("#7d8797", "#4b5363", "", "wave"),
    "dolby":    ("#2b2f3a", "#0e1016", "SURROUND", "51"),
    "dts":      ("#e04848", "#9c1f26", "SURROUND", "51"),
    "truehd":   ("#d9a52b", "#94680f", "SURROUND", "51"),
    "list":     ("#5a6475", "#343b48", "PLAYLIST", "list"),
    "cue":      ("#6f42c1", "#0d6efd", "CUE SHEET", "list"),
}

# extension → (label on the icon, family)
FORMATS = {
    "flac": ("FLAC", "lossless"),
    "alac": ("ALAC", "apple"), "m4a": ("M4A", "aac"), "m4b": ("M4B", "aac"), "aac": ("AAC", "aac"),
    "caf": ("CAF", "apple"),
    "ape": ("APE", "rare"), "wv": ("WV", "rare"), "tak": ("TAK", "rare"), "tta": ("TTA", "rare"),
    "wav": ("WAV", "pcm"), "w64": ("W64", "pcm"), "aif": ("AIFF", "pcm"), "aiff": ("AIFF", "pcm"),
    "aifc": ("AIFC", "pcm"),
    "dsf": ("DSF", "dsd"), "dff": ("DFF", "dsd"),
    "mp3": ("MP3", "mp3"), "mp2": ("MP2", "mp3"), "mpc": ("MPC", "other"),
    "ogg": ("OGG", "xiph"), "oga": ("OGA", "xiph"), "opus": ("OPUS", "xiph"), "spx": ("SPX", "xiph"),
    "wma": ("WMA", "wma"), "mka": ("MKA", "other"),
    "ac3": ("AC3", "dolby"), "eac3": ("EAC3", "dolby"), "ec3": ("EC3", "dolby"),
    "dts": ("DTS", "dts"), "dtshd": ("DTS-HD", "dts"),
    "thd": ("THD", "truehd"), "truehd": ("TrueHD", "truehd"), "mlp": ("MLP", "truehd"),
    "m3u": ("M3U", "list"), "m3u8": ("M3U8", "list"), "pls": ("PLS", "list"),
    "cue": ("CUE", "cue"),
}


def _font(path: str | None, px: int):
    for p in ([path] if path else []) + ["/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf",
                                         "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
                                         "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
                                         "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"]:
        if p and os.path.isfile(p):
            return ImageFont.truetype(p, px)
    return ImageFont.load_default()


def _rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _fit(draw, text, font_path, max_w, max_h):
    px = max_h
    while px > 4:
        f = _font(font_path, px)
        b = draw.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= max_w and b[3] - b[1] <= max_h:
            return f, b
        px -= 1
    f = _font(font_path, 5)
    return f, draw.textbbox((0, 0), text, font=f)


def draw_icon(size: int, label: str, family: str, font_path: str | None = None) -> Image.Image:
    c1, c2, tag, glyph = FAMILIES[family]
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    small = size < 32
    # the page: a bit narrower than tall, a folded top-right corner
    pad_x, pad_y = (0.10 if small else 0.13) * S, 0.04 * S
    x0, y0, x1, y1 = pad_x, pad_y, S - pad_x, S - pad_y
    fold = (x1 - x0) * 0.30
    r = max(SS, 0.07 * S)
    # gradient body
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    a, b = _rgb(c1), _rgb(c2)
    for y in range(S):
        k = max(0.0, min(1.0, (y - y0) / max(1, y1 - y0)))
        gd.line([(0, y), (S, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3)) + (255,))
    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=255)
    md.rectangle([x1 - fold, y0 - 1, x1 + 1, y0 + fold], fill=0)                        # the corner goes
    md.polygon([(x1 - fold, y0), (x1 - fold, y0 + fold), (x1, y0 + fold)], fill=255)   # under the flap
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    # the folded flap: lighter triangle with a soft shadow line
    flap = tuple(min(255, int(v * 0.55 + 255 * 0.45)) for v in a) + (255,)
    d.polygon([(x1 - fold, y0), (x1, y0 + fold), (x1 - fold, y0 + fold)], fill=flap)
    d.line([(x1 - fold, y0 + fold), (x1, y0 + fold)], fill=(0, 0, 0, 60), width=max(1, SS // 2))
    white = (255, 255, 255, 255)
    soft = (255, 255, 255, 215)
    W = x1 - x0
    # glyph, top-left
    gx, gy = x0 + W * 0.13, y0 + (y1 - y0) * (0.12 if not small else 0.20)
    gh = (y1 - y0) * (0.17 if not small else 0.30)
    if glyph == "wave":
        bars = (0.35, 0.75, 1.0, 0.55, 0.85, 0.4) if not small else (0.45, 1.0, 0.7, 0.9)
        bw = W * (0.045 if not small else 0.10)
        for i, h in enumerate(bars):
            bx = gx + i * bw * 1.75
            hh = gh * h
            d.rounded_rectangle([bx, gy + (gh - hh) / 2, bx + bw, gy + (gh + hh) / 2], radius=bw / 2, fill=soft)
    elif glyph == "list":
        lw = W * (0.36 if not small else 0.55)
        for i in range(3):
            ly = gy + i * gh * 0.42
            dot = gh * 0.22
            d.ellipse([gx, ly, gx + dot, ly + dot], fill=soft)
            d.rounded_rectangle([gx + dot * 1.7, ly + dot * 0.2, gx + dot * 1.7 + lw * (1 - i * 0.18),
                                 ly + dot * 0.8], radius=dot * 0.3, fill=soft)
    elif glyph == "51":
        f, bb = _fit(d, "5.1", font_path, W * (0.40 if not small else 0.75), gh)
        d.text((gx - bb[0], gy - bb[1]), "5.1", font=f, fill=soft)
    if small:
        # no text at 16–24 px: a light stripe says "this is a file of that family"
        d.rounded_rectangle([x0 + W * 0.13, y1 - (y1 - y0) * 0.30, x1 - W * 0.13, y1 - (y1 - y0) * 0.16],
                            radius=SS, fill=(255, 255, 255, 200))
    else:
        # the name, as big as it fits
        f, bb = _fit(d, label, font_path, W * 0.80, (y1 - y0) * 0.30)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        ty = y0 + (y1 - y0) * (0.50 if tag else 0.55) - th / 2
        d.text((x0 + (W - tw) / 2 - bb[0], ty - bb[1]), label, font=f, fill=white)
        if tag and size >= 48:
            f2, b2 = _fit(d, tag, font_path, W * 0.72, (y1 - y0) * 0.085)
            tw2, th2 = b2[2] - b2[0], b2[3] - b2[1]
            px_, py_ = W * 0.05, (y1 - y0) * 0.035
            bx0 = x0 + (W - tw2) / 2 - px_
            by0 = y1 - (y1 - y0) * 0.20
            d.rounded_rectangle([bx0, by0, bx0 + tw2 + 2 * px_, by0 + th2 + 2 * py_], radius=(th2 + 2 * py_) / 2,
                                fill=(0, 0, 0, 70))
            d.text((bx0 + px_ - b2[0], by0 + py_ - b2[1]), tag, font=f2, fill=(255, 255, 255, 235))
        elif tag:
            d.rounded_rectangle([x0 + W * 0.25, y1 - (y1 - y0) * 0.17, x1 - W * 0.25, y1 - (y1 - y0) * 0.11],
                                radius=SS, fill=(255, 255, 255, 150))
    return img.resize((size, size), Image.LANCZOS)


def build(font_path: str | None = None, out: str = OUT) -> list[str]:
    os.makedirs(out, exist_ok=True)
    done = []
    for ext, (label, fam) in FORMATS.items():
        frames = [draw_icon(s, label, fam, font_path) for s in SIZES]
        path = os.path.join(out, ext + ".ico")
        frames[-1].save(path, format="ICO", sizes=[(s, s) for s in SIZES], append_images=frames[:-1])
        done.append(path)
    return done


def preview(path: str, font_path: str | None = None):
    """A sheet: every format at 96 px with its extension, and one row of sizes."""
    exts = list(FORMATS)
    cols, cell = 9, 128
    rows = (len(exts) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell, rows * (cell + 26) + 150), (245, 246, 248, 255))
    d = ImageDraw.Draw(sheet)
    f = _font(font_path, 15)
    for i, ext in enumerate(exts):
        label, fam = FORMATS[ext]
        x, y = (i % cols) * cell, (i // cols) * (cell + 26)
        sheet.alpha_composite(draw_icon(96, label, fam, font_path), (x + 16, y + 12))
        tb = d.textbbox((0, 0), "." + ext, font=f)
        d.text((x + (cell - tb[2]) / 2, y + 112), "." + ext, font=f, fill=(60, 64, 72))
    y = rows * (cell + 26) + 20
    x = 16
    for s in (16, 24, 32, 48, 64, 128):
        sheet.alpha_composite(draw_icon(s, "FLAC", "lossless", font_path), (x, y + (128 - s)))
        sheet.alpha_composite(draw_icon(s, "DTS", "dts", font_path), (x, y + (128 - s) - 0) if False else
                              (x + s + 8, y + (128 - s)))
        x += 2 * s + 40
    sheet.convert("RGB").save(path)


if __name__ == "__main__":
    args = sys.argv[1:]
    sheet = ""
    if "--preview" in args:
        i = args.index("--preview")
        sheet = args[i + 1]
        del args[i:i + 2]
    fp = args[0] if args else None
    files = build(fp)
    if sheet:
        preview(sheet, fp)
    print(len(files), "icons in", OUT)
