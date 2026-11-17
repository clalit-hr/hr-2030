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
        ";\nconst TITLES=" + json.dumps(TITLES, ensure_ascii=False) + ";"
    out = tpl.replace("/*__DATA__*/", data)
    (ROOT / "index.html").write_text(out, encoding="utf-8")
    size = (ROOT / "index.html").stat().st_size
    print(f"slides raw {raw // 1024} KB, index.html {size / 1024 / 1024:.2f} MB")
    assert size < 4 * 1024 * 1024, "index.html over 4MB"


if __name__ == "__main__":
    main()
