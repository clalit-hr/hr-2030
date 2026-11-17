"""QR code to the digital book with the Clalit symbol in the centre.
Run: python qr/make_qr.py  ->  qr/hr-2030-qr.png (print size) + qr/hr-2030-qr-small.png
"""
import pathlib
import segno
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).parent
URL = "https://clalit-hr.github.io/hr-2030/"
NAVY, GREEN, BLUE = (11, 19, 43), (0, 166, 81), (0, 170, 238)

qr = segno.make(URL, error="h", boost_error=False)
m = [list(r) for r in qr.matrix]
n = len(m)
QUIET, CELL = 4, 60
size = (n + 2 * QUIET) * CELL
img = Image.new("RGB", (size, size), "white")
d = ImageDraw.Draw(img)

def finder(r, c):
    return (r < 7 and c < 7) or (r < 7 and c >= n - 7) or (r >= n - 7 and c < 7)

# logo hole in the centre (about 21% of the code width, well inside level H)
hole = int(n * 0.25) | 1
h0 = (n - hole) // 2
def in_hole(r, c):
    return h0 - 1 <= r <= h0 + hole and h0 - 1 <= c <= h0 + hole

for r in range(n):
    for c in range(n):
        if m[r][c] and not finder(r, c) and not in_hole(r, c):
            x, y = (c + QUIET) * CELL, (r + QUIET) * CELL
            d.rectangle([x, y, x + CELL - 1, y + CELL - 1], fill=NAVY)

# rounded finder eyes: navy frame, green centre
for (r, c) in [(0, 0), (0, n - 7), (n - 7, 0)]:
    x, y = (c + QUIET) * CELL, (r + QUIET) * CELL
    d.rounded_rectangle([x, y, x + 7 * CELL, y + 7 * CELL], radius=CELL * .9, fill=NAVY)
    d.rounded_rectangle([x + CELL, y + CELL, x + 6 * CELL, y + 6 * CELL], radius=CELL * .5, fill="white")
    d.rounded_rectangle([x + 2 * CELL, y + 2 * CELL, x + 5 * CELL, y + 5 * CELL], radius=CELL * .5, fill=NAVY)

# Clalit symbol on a white rounded tile
logo = Image.open(HERE / "clalit-symbol.png").convert("RGBA")
logo = logo.crop(logo.getchannel("A").getbbox())
tile = (hole + 1) * CELL
tx = ty = (h0 + QUIET) * CELL - CELL // 2
d.rounded_rectangle([tx, ty, tx + tile, ty + tile], radius=tile * .22, fill="white")
ls = int(tile * .84)
logo = logo.resize((ls, round(ls * logo.height / logo.width)), Image.LANCZOS)
img.paste(logo, (tx + (tile - logo.width) // 2, ty + (tile - logo.height) // 2), logo)

img.save(HERE / "hr-2030-qr.png", dpi=(600, 600))
img.resize((800, 800), Image.LANCZOS).save(HERE / "hr-2030-qr-small.png")
print("modules", n, "px", size)
