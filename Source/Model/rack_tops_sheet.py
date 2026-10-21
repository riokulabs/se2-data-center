"""Rack top sheets (Pillow, no Blender).

    python3 Source/Model/rack_tops_sheet.py

Reads preview/rack-tops/{before,after}/ (dc/preview_rack_tops.py) and writes, in preview/rack-tops/:
  * pairs/pair_<shot>.jpg: before | after, side by side, for every shot rendered in both sets;
  * contact_after.jpg: every after shot on one sheet (for review at a glance)."""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "preview", "rack-tops")
CELL = (800, 500)


def _font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def _fit(path, size):
    im = Image.open(path).convert("RGB")
    im.thumbnail(size, Image.LANCZOS)
    out = Image.new("RGB", size, (18, 19, 22))
    out.paste(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2))
    return out


def pairs():
    b, a = os.path.join(ROOT, "before"), os.path.join(ROOT, "after")
    out = os.path.join(ROOT, "pairs")
    os.makedirs(out, exist_ok=True)
    f = _font(28)
    n = 0
    for name in sorted(os.listdir(a)):
        if not name.endswith(".png") or not os.path.exists(os.path.join(b, name)):
            continue
        sheet = Image.new("RGB", (CELL[0] * 2 + 30, CELL[1] + 60), (12, 12, 14))
        d = ImageDraw.Draw(sheet)
        for k, (lab, src) in enumerate((("BEFORE", b), ("AFTER", a))):
            sheet.paste(_fit(os.path.join(src, name), CELL), (10 + k * (CELL[0] + 10), 50))
            d.text((14 + k * (CELL[0] + 10), 10), f"{lab}  {name[:-4]}", fill=(235, 235, 235), font=f)
        sheet.save(os.path.join(out, "pair_" + name[:-4] + ".jpg"), quality=90)
        n += 1
    print(f"{n} pairs -> {out}")


def contact():
    a = os.path.join(ROOT, "after")
    names = sorted(n for n in os.listdir(a) if n.endswith(".png"))
    cols = 4
    cw, ch = 560, 380
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cw + 8) + 8, rows * (ch + 36) + 8), (12, 12, 14))
    d = ImageDraw.Draw(sheet)
    f = _font(18)
    for i, n in enumerate(names):
        x, y = 8 + (i % cols) * (cw + 8), 8 + (i // cols) * (ch + 36)
        sheet.paste(_fit(os.path.join(a, n), (cw, ch)), (x, y + 28))
        d.text((x + 2, y + 4), n[:-4], fill=(230, 230, 230), font=f)
    path = os.path.join(ROOT, "contact_after.jpg")
    sheet.save(path, quality=88)
    print("contact ->", path)


if __name__ == "__main__":
    pairs()
    contact()
