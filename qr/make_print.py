"""Print-quality QR (vector) for a roll-up banner.
Run: python qr/make_print.py
Outputs in qr/print/: hr-2030-qr.svg, hr-2030-qr.pdf, hr-2030-qr-8000.png
Same design as make_qr.py, but every shape is a vector, including the Clalit symbol.
"""
import pathlib

import cv2
import numpy as np
import segno
from PIL import Image

HERE = pathlib.Path(__file__).parent
OUT = HERE / "print"
OUT.mkdir(exist_ok=True)
URL = "https://clalit-hr.github.io/hr-2030/"
NAVY = "#0B132B"

qr = segno.make(URL, error="h", boost_error=False)
m = [list(r) for r in qr.matrix]
n = len(m)
Q = 4                      # quiet zone in modules
S = n + 2 * Q              # canvas size in module units

def finder(r, c):
    return (r < 7 and c < 7) or (r < 7 and c >= n - 7) or (r >= n - 7 and c < 7)

hole = int(n * 0.25) | 1
h0 = (n - hole) // 2
def in_hole(r, c):
    return h0 - 1 <= r <= h0 + hole and h0 - 1 <= c <= h0 + hole

parts = []
# data modules: one path, horizontal runs merged so there are no hairline seams in print
d = []
for r in range(n):
    c = 0
    while c < n:
        if m[r][c] and not finder(r, c) and not in_hole(r, c):
            c0 = c
            while c < n and m[r][c] and not finder(r, c) and not in_hole(r, c):
                c += 1
            d.append(f"M{c0 + Q} {r + Q}h{c - c0}v1h{c0 - c}z")
        else:
            c += 1
parts.append(f'<path fill="{NAVY}" d="{"".join(d)}"/>')

# finder eyes (rounded, as in the screen version)
for (r, c) in [(0, 0), (0, n - 7), (n - 7, 0)]:
    x, y = c + Q, r + Q
    parts.append(f'<rect x="{x}" y="{y}" width="7" height="7" rx="0.9" fill="{NAVY}"/>')
    parts.append(f'<rect x="{x + 1}" y="{y + 1}" width="5" height="5" rx="0.5" fill="#fff"/>')
    parts.append(f'<rect x="{x + 2}" y="{y + 2}" width="3" height="3" rx="0.5" fill="{NAVY}"/>')

# white tile + vectorised Clalit symbol
tile = hole + 1
tx = ty = h0 + Q - 0.5
parts.append(f'<rect x="{tx}" y="{ty}" width="{tile}" height="{tile}" rx="{tile * .22:.3f}" fill="#fff"/>')

logo = Image.open(HERE / "clalit-symbol.png").convert("RGBA")
logo = logo.crop(logo.getchannel("A").getbbox())
UP = 6
big = np.asarray(logo.resize((logo.width * UP, logo.height * UP), Image.LANCZOS)).astype(np.float32)
alpha = big[..., 3] / 255
lw = tile * .84
scale = lw / big.shape[1]
lx = tx + (tile - lw) / 2
ly = ty + (tile - big.shape[0] * scale) / 2
for name, rgb in (("blue", (0, 170, 238)), ("green", (0, 166, 81))):
    dist = np.linalg.norm(big[..., :3] - np.array(rgb, np.float32), axis=2)
    mask = ((dist < 90) & (alpha > .5)).astype(np.uint8) * 255
    mask = cv2.GaussianBlur(mask, (0, 0), UP * .6)
    _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnts = [c for c in cnts if cv2.contourArea(c) > mask.size * .01]
    # sample the real colour of this shape from the source
    sel = mask > 0
    col = big[..., :3][sel].mean(axis=0) if sel.any() else np.array(rgb)
    hexcol = "#%02X%02X%02X" % tuple(int(round(v)) for v in col)
    for c in cnts:
        c = cv2.approxPolyDP(c, UP * .12, True)[:, 0, :]
        pts = " ".join(f"{lx + x * scale:.4f},{ly + y * scale:.4f}" for x, y in c)
        parts.append(f'<polygon fill="{hexcol}" points="{pts}"/>')

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="{S * 10}mm" height="{S * 10}mm" '
       f'shape-rendering="geometricPrecision">\n<rect width="{S}" height="{S}" fill="#fff"/>\n'
       + "\n".join(parts) + "\n</svg>\n")
(OUT / "hr-2030-qr.svg").write_text(svg, encoding="utf-8")

# high-res PNG drawn from the very same vector shapes
import re  # noqa: E402
from PIL import ImageDraw  # noqa: E402
PX = 8000
k = PX / S
SS = 2                                   # supersample for smooth edges
img = Image.new("RGB", (PX * SS, PX * SS), "white")
dr = ImageDraw.Draw(img)
K = k * SS
for seg in re.findall(r"M(\d+) (\d+)h(-?\d+)", "".join(d)):
    x, y, w = map(int, seg)
    dr.rectangle([x * K, y * K, (x + w) * K - 1, (y + 1) * K - 1], fill=NAVY)
for el in parts[1:]:
    if el.startswith("<rect"):
        v = dict(re.findall(r'(\w+)="([^"]+)"', el))
        x, y, w, h, rx = (float(v[q]) for q in ("x", "y", "width", "height", "rx"))
        dr.rounded_rectangle([x * K, y * K, (x + w) * K, (y + h) * K], radius=rx * K, fill=v["fill"])
    else:
        v = dict(re.findall(r'(\w+)="([^"]+)"', el))
        pts = [tuple(float(t) * K for t in pr.split(",")) for pr in v["points"].split()]
        dr.polygon(pts, fill=v["fill"])
img = img.resize((PX, PX), Image.LANCZOS)
img.save(OUT / "hr-2030-qr-8000.png", dpi=(600, 600))

# PDF: hand-written vector PDF (no extra software needed). One module = 10 mm (page 45 x 45 cm);
# printers scale vectors to any size without loss.
MM = 72 / 25.4
U = 10 * MM
H = S * U
NL = "\n"


def col(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return " ".join(f"{int(h[i:i + 2], 16) / 255:.4f}" for i in (0, 2, 4))


def rr(x, y, w, h, r):  # rounded rect, PDF coords (origin bottom-left)
    k = .5523 * r
    return (f"{x + r:.3f} {y:.3f} m {x + w - r:.3f} {y:.3f} l "
            f"{x + w - r + k:.3f} {y:.3f} {x + w:.3f} {y + r - k:.3f} {x + w:.3f} {y + r:.3f} c "
            f"{x + w:.3f} {y + h - r:.3f} l "
            f"{x + w:.3f} {y + h - r + k:.3f} {x + w - r + k:.3f} {y + h:.3f} {x + w - r:.3f} {y + h:.3f} c "
            f"{x + r:.3f} {y + h:.3f} l "
            f"{x + r - k:.3f} {y + h:.3f} {x:.3f} {y + h - r + k:.3f} {x:.3f} {y + h - r:.3f} c "
            f"{x:.3f} {y + r:.3f} l "
            f"{x:.3f} {y + r - k:.3f} {x + r - k:.3f} {y:.3f} {x + r:.3f} {y:.3f} c h f" + NL)


ops = [f"1 1 1 rg 0 0 {H:.3f} {H:.3f} re f" + NL, f"{col(NAVY)} rg" + NL]
for seg in re.findall(r"M(\d+) (\d+)h(-?\d+)", "".join(d)):
    x, y, w = map(int, seg)
    ops.append(f"{x * U:.3f} {H - (y + 1) * U:.3f} {w * U:.3f} {U:.3f} re f" + NL)
for el in parts[1:]:
    v = dict(re.findall(r'(\w+)="([^"]+)"', el))
    ops.append(f"{col(v['fill'])} rg" + NL)
    if el.startswith("<rect"):
        x, y, w, h, rx = (float(v[q]) for q in ("x", "y", "width", "height", "rx"))
        ops.append(rr(x * U, H - (y + h) * U, w * U, h * U, rx * U))
    else:
        pts = [tuple(float(t) for t in pr.split(",")) for pr in v["points"].split()]
        ops.append(f"{pts[0][0] * U:.3f} {H - pts[0][1] * U:.3f} m " +
                   " ".join(f"{x * U:.3f} {H - y * U:.3f} l" for x, y in pts[1:]) + " h f" + NL)
stream = "".join(ops).encode()
objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {H:.3f} {H:.3f}] /Contents 4 0 R >>".encode(),
        b"<< /Length " + str(len(stream)).encode() + b" >>" + NL.encode() + b"stream" + NL.encode()
        + stream + NL.encode() + b"endstream"]
pdf = bytearray(b"%PDF-1.4" + NL.encode())
offs = []
for i, o in enumerate(objs, 1):
    offs.append(len(pdf))
    pdf += f"{i} 0 obj{NL}".encode() + o + f"{NL}endobj{NL}".encode()
xref = len(pdf)
pdf += f"xref{NL}0 {len(objs) + 1}{NL}0000000000 65535 f {NL}".encode()
for o in offs:
    pdf += f"{o:010d} 00000 n {NL}".encode()
pdf += f"trailer{NL}<< /Size {len(objs) + 1} /Root 1 0 R >>{NL}startxref{NL}{xref}{NL}%%EOF{NL}".encode()
(OUT / "hr-2030-qr.pdf").write_bytes(bytes(pdf))
print("modules", n, "canvas", S, "pdf ok")
