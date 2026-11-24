"""Build the single-file digital book (index.html) from the PDF.

Run: python build.py
Outputs: index.html (all slides embedded), og.jpg, icon-180.png, icon-512.png
"""
import base64
import io
import json
import pathlib

import pypdfium2 as pdfium
from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).parent
PDF = next(ROOT.glob("*.pdf"))
SCALE = 2.6        # 2496x1404, sharp at 2.5x zoom on retina screens
QUALITY = 82
THUMB_W = 360
import os
SCRATCH = pathlib.Path(os.environ["BOOK_SCRATCH"]) if os.environ.get("BOOK_SCRATCH") else None

TITLES = [
    "אסטרטגיית מש״א 2030",
    "חזון כללית וחזון משאבי אנוש",
    "ניתוח הסביבה העסקית והארגונית",
    "המגמות המרכזיות בבריאות",
    "ההשפעות על ניהול ההון האנושי",
    "HR SWOT",
    "האתגרים האסטרטגיים המרכזיים",
    "אסטרטגיית כללית",
    "אסטרטגיית מש״א",
    "מש״א, המהלכים",
    "מהאתגרים אל היעד",
    "בהצלחה לכולנו!",
]


def webp_uri(im, quality):
    b = io.BytesIO()
    im.save(b, "WEBP", quality=quality, method=6)
    return "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode(), len(b.getvalue())


# Slide 11 build-up: pieces revealed one after another (x0, y0, x1, y1 as fractions)
BUILD_INDEX = 10
BUILD = [
    ((.515, .025, .86, .205), "rise", 0),
    ((.145, .025, .485, .205), "rise", 1800),
    ((.30, .205, .70, .30), "wipeDown", 3600),
    ((.275, .305, .71, .43), "rise", 4400),
    ((.515, .435, .68, .527), "pop", 6400),
    ((.275, .435, .482, .527), "pop", 7300),
    ((.515, .527, .70, .627), "pop", 8200),
    ((.24, .527, .482, .627), "pop", 9100),
    ((.486, .43, .514, .66), "wipeDown", 10200),
    ((.69, .335, .86, .68), "wipeUp", 10900),
    ((.14, .335, .30, .68), "wipeUp", 10900),
    ((.17, .665, .84, .755), "rise", 12000),
    ((.486, .75, .514, .868), "wipeDown", 14200),
    ((.12, .87, .88, .99), "glow", 15000),
]


def build_layers(im):
    import numpy as np
    import cv2
    W, H = im.size
    a = np.asarray(im).astype(np.float32)
    mask = np.zeros((H, W), np.float32)
    px = lambda r: (round(r[0] * W), round(r[1] * H), round(r[2] * W), round(r[3] * H))
    # The two curved arrows: exact pixel masks, so the arrowheads (which reach into the
    # "excellent results" box) belong only to the arrow layers and appear with them.
    arrows = np.zeros((H, W), np.float32)
    white = (a.min(axis=2) > 200).astype(np.uint8)
    for r, fx, _ in BUILD:
        if fx != "wipeUp":
            continue
        X0, Y0, X1, Y1 = px(r)
        n_, lab, st, _ = cv2.connectedComponentsWithStats(white[Y0:Y1, X0:X1], connectivity=8)
        big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        arrows[Y0:Y1, X0:X1] = np.maximum(arrows[Y0:Y1, X0:X1], (lab == big).astype(np.float32))
    arrows = cv2.GaussianBlur(cv2.dilate(arrows, np.ones((5, 5), np.uint8)), (0, 0), 1)
    layers = []
    for (x0, y0, x1, y1), fx, at in BUILD:
        X0, Y0, X1, Y1 = px((x0, y0, x1, y1))
        mask[Y0:Y1, X0:X1] = 1
        crop = im.crop((X0, Y0, X1, Y1)).convert("RGBA")
        f = max(4, W // 250)
        al = Image.new("L", crop.size, 0)
        al.paste(255, (f, f, crop.width - f, crop.height - f))
        if x0 == .14:  # left arc: keep clear of the pill next to it
            cut = round((.235 - x0) * W)
            al.paste(0, (cut, round((.43 - y0) * H), crop.width, crop.height))
        al = al.filter(ImageFilter.GaussianBlur(f / 2))
        A = np.asarray(al).astype(np.float32) / 255
        arr = arrows[Y0:Y1, X0:X1]
        if fx == "wipeUp":
            # outside the arrow, stay out of the boxes this crop overlaps; the arrow itself is whole
            over = np.zeros_like(A)
            for r2, fx2, _ in BUILD:
                if fx2 == "wipeUp":
                    continue
                a0, b0, a1, b1 = px(r2)
                over[max(b0, Y0) - Y0:max(min(b1, Y1) - Y0, 0), max(a0, X0) - X0:max(min(a1, X1) - X0, 0)] = 1
            over = cv2.GaussianBlur(over, (0, 0), f / 2)
            A = np.maximum(A * (1 - over), arr)
        elif arr.max() > 0:
            # paint the arrow tip out of this box with the box's own colour
            hole = cv2.dilate((arr > 0.01).astype(np.uint8), np.ones((3, 3), np.uint8))
            rgb = cv2.inpaint(np.asarray(crop.convert("RGB")), hole, 5, cv2.INPAINT_TELEA)
            crop = Image.fromarray(rgb).convert("RGBA")
        crop.putalpha(Image.fromarray(np.clip(A * 255, 0, 255).astype("uint8")))
        b = io.BytesIO()
        crop.save(b, "WEBP", quality=QUALITY, method=6)
        layers.append({"u": "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode(),
                       "r": [x0, y0, x1 - x0, y1 - y0], "fx": fx, "at": at})
    # clean background plate: fill masked areas from their surroundings
    mask = cv2.dilate(mask, np.ones((W // 90, W // 90), np.uint8))
    sm = 4
    small = cv2.resize(a, (W // sm, H // sm), interpolation=cv2.INTER_AREA)
    ms = cv2.resize(mask, (W // sm, H // sm), interpolation=cv2.INTER_AREA)
    keep = (1 - ms)[..., None]
    k = (0, 0)
    num = cv2.GaussianBlur(small * keep, k, 30)
    den = cv2.GaussianBlur(keep, k, 30)
    if den.ndim == 2:
        den = den[..., None]
    fill = num / np.maximum(den, 1e-3)
    fill = cv2.resize(fill, (W, H), interpolation=cv2.INTER_CUBIC)
    mf = cv2.GaussianBlur(mask, (0, 0), 6)[..., None]
    plate = a * (1 - mf) + fill * mf
    pim = Image.fromarray(np.clip(plate, 0, 255).astype("uint8"))
    b = io.BytesIO()
    pim.save(b, "WEBP", quality=75, method=6)
    return {"index": BUILD_INDEX, "plate": "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode(),
            "layers": layers}, pim


def main():
    doc = pdfium.PdfDocument(str(PDF))
    assert len(doc) == len(TITLES), f"PDF has {len(doc)} pages, TITLES has {len(TITLES)}"
    slides, thumbs, raw = [], [], 0
    cover = None
    for i in range(len(doc)):
        im = doc[i].render(scale=SCALE).to_pil().convert("RGB")
        uri, n = webp_uri(im, QUALITY)
        raw += n
        slides.append(uri)
        th = im.resize((THUMB_W, round(im.height * THUMB_W / im.width)), Image.LANCZOS)
        thumbs.append(webp_uri(th, 70)[0])
        if i == 0:
            cover = im
        if i == BUILD_INDEX:
            build, plate = build_layers(im)

    # Share preview (WhatsApp / social) 1200x630
    og = Image.new("RGB", (1200, 630), (11, 19, 43))
    c = cover.resize((1120, 630), Image.LANCZOS)
    og.paste(c, (40, 0))
    og.save(ROOT / "og.jpg", quality=85)

    # Home-screen icon: Clalit logo above "2030", both cropped from the cover
    w, h = cover.size
    logo = cover.crop((int(w * .105), int(h * .06), int(w * .25), int(h * .175)))
    year = cover.crop((int(w * .415), int(h * .445), int(w * .585), int(h * .575)))
    side = int(max(logo.width, year.width) * 1.35)
    bg = cover.crop((int(w * .30), int(h * .30), int(w * .32), int(h * .32))).resize((1, 1)).getpixel((0, 0))
    sq = Image.new("RGB", (side, side), bg)
    gap = int(side * .04)
    top = (side - logo.height - year.height - gap) // 2

    def feather(im):
        m = Image.new("L", im.size, 0)
        pad = int(min(im.size) * .12)
        m.paste(255, (pad, pad, im.width - pad, im.height - pad))
        return m.filter(ImageFilter.GaussianBlur(pad / 2))

    sq.paste(logo, ((side - logo.width) // 2, top), feather(logo))
    sq.paste(year, ((side - year.width) // 2, top + logo.height + gap), feather(year))
    for size in (180, 512):
        sq.resize((size, size), Image.LANCZOS).save(ROOT / f"icon-{size}.png")

    tpl = (ROOT / "src" / "template.html").read_text(encoding="utf-8")
    data = "const SLIDES=" + json.dumps(slides) + ";\nconst THUMBS=" + json.dumps(thumbs) + \
        ";\nconst BUILD=" + json.dumps(build) + \
        ";\nconst TITLES=" + json.dumps(TITLES, ensure_ascii=False) + ";"
    out = tpl.replace("/*__DATA__*/", data)
    (ROOT / "index.html").write_text(out, encoding="utf-8")
    size = (ROOT / "index.html").stat().st_size
    if SCRATCH:
        plate.save(SCRATCH / "plate.jpg", quality=80)
    print(f"slides raw {raw // 1024} KB, index.html {size / 1024 / 1024:.2f} MB")
    assert size < 4 * 1024 * 1024, "index.html over 4MB"


if __name__ == "__main__":
    main()
