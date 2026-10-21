"""Plan 2 Task 10 sheets (Pillow, no Blender): the visual-pass audit set.

    python3 Source/Model/p2t10_sheet.py contact before|after    every shot of a set on one sheet (contact_<set>.jpg)
    python3 Source/Model/p2t10_sheet.py refs before|after       our run shots beside reference photos 01, 02, 04 and
                                                                the vanilla line-ups (refs_<set>.jpg)
    python3 Source/Model/p2t10_sheet.py pairs                   before | after for every shot in both sets
                                                                (pairs/<shot>.jpg) and pairs/contact_pairs.jpg

Reads and writes preview/p2-task-10/ (dc/preview_trays.py render_audit, DC_PREVIEW_SUB=before|after)."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "preview", "p2-task-10")
REF = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "docs", "ideas", "reference", "datacenter"))
BG = (14, 15, 18)


def _font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def _fit(path, size):
    im = Image.open(path).convert("RGB")
    im.thumbnail(size, Image.LANCZOS)
    out = Image.new("RGB", size, BG)
    out.paste(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2))
    return out


def grid(items, cell, cols, title, out):
    """items = [(path, label)] on a grid of `cols` columns."""
    rows = (len(items) + cols - 1) // cols
    pad, head = 8, 34
    sheet = Image.new("RGB", (cols * (cell[0] + pad) + pad, 60 + rows * (cell[1] + head + pad)), (8, 8, 10))
    d = ImageDraw.Draw(sheet)
    d.text((pad + 4, 14), title, fill=(240, 240, 240), font=_font(28))
    f = _font(max(14, cell[0] // 28))
    for k, (p, lab) in enumerate(items):
        x = pad + (k % cols) * (cell[0] + pad)
        y = 60 + (k // cols) * (cell[1] + head + pad)
        d.text((x + 4, y + 6), lab, fill=(220, 220, 220), font=f)
        sheet.paste(_fit(p, cell), (x, y + head))
    sheet.save(out, quality=88)
    print("WROTE", out)


def shots(sub):
    d = os.path.join(ROOT, sub)
    return sorted(n[:-4] for n in os.listdir(d) if n.endswith(".png"))


def contact(sub):
    names = shots(sub)
    grid([(os.path.join(ROOT, sub, n + ".png"), n) for n in names], (420, 270), 8,
         f"Plan 2 Task 10 audit set: {sub} ({len(names)} shots)", os.path.join(ROOT, f"contact_{sub}.jpg"))


REFS = (("01-aisle-blue-waterfalls.jpg", "photo 01: waterfalls over an aisle"),
        ("02-wire-basket-colour-coded.png", "photo 02: wire basket, colour-coded"),
        ("04-rod-hung-basket-over-racks.jpg", "photo 04: rod-hung basket over racks"))
OURS = (("run_aisle_eye", "ours: aisle, eye level"), ("run_row_34", "ours: mixed run over a rack row"),
        ("run_aisle_worm", "ours: worm's eye"), ("run_mockup05b", "ours: v2 mockup 05b camera"),
        ("vanilla_compare", "ours vs vanilla WallInsertPipes / Catwalk"),
        ("vanilla_junctionT_compare", "ours vs vanilla ConveyorJunctionT"))


def refs(sub):
    items = [(os.path.join(REF, f), lab) for f, lab in REFS]
    items += [(os.path.join(ROOT, sub, n + ".png"), lab) for n, lab in OURS
              if os.path.exists(os.path.join(ROOT, sub, n + ".png"))]
    grid(items, (760, 450), 3, f"References vs ours ({sub})", os.path.join(ROOT, f"refs_{sub}.jpg"))


def pairs():
    out = os.path.join(ROOT, "pairs")
    os.makedirs(out, exist_ok=True)
    both = [n for n in shots("after") if os.path.exists(os.path.join(ROOT, "before", n + ".png"))]
    f = _font(26)
    thumbs = []
    for n in both:
        a, b = (os.path.join(ROOT, s, n + ".png") for s in ("before", "after"))
        cell = (900, 580)
        sheet = Image.new("RGB", (2 * cell[0] + 30, cell[1] + 60), (8, 8, 10))
        d = ImageDraw.Draw(sheet)
        sheet.paste(_fit(a, cell), (10, 50))
        sheet.paste(_fit(b, cell), (20 + cell[0], 50))
        d.text((14, 12), f"{n}: BEFORE", fill=(235, 200, 120), font=f)
        d.text((24 + cell[0], 12), "AFTER", fill=(150, 225, 150), font=f)
        p = os.path.join(out, n + ".jpg")
        sheet.save(p, quality=88)
        thumbs.append((p, n))
    grid(thumbs, (620, 200), 4, f"Plan 2 Task 10: before | after ({len(thumbs)} pairs)",
         os.path.join(out, "contact_pairs.jpg"))
    icons(out)


def icons(out):
    """The tray icons before (preview/p2-task-10/icons_before) and after (UI/), each at 200 px and the 64 px
    toolbar size, on the menu's dark tile."""
    before = os.path.join(ROOT, "icons_before")
    names = sorted(n for n in os.listdir(before) if n.endswith("_Icon.png"))
    cw, ch = 2 * (200 + 64 + 24) + 20, 230
    cols = 3
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cw, 50 + rows * ch), (24, 26, 30, 255))
    d = ImageDraw.Draw(sheet)
    d.text((10, 12), "Tray icons: before | after (200 px and 64 px)", fill=(240, 240, 240), font=_font(24))
    f = _font(14)
    for k, n in enumerate(names):
        x, y = (k % cols) * cw, 50 + (k // cols) * ch
        d.text((x + 6, y), n[:-9], fill=(210, 210, 210), font=f)
        for j, src in enumerate((os.path.join(before, n), os.path.join(HERE, "UI", n))):
            im = Image.open(src).convert("RGBA")
            ox = x + j * (200 + 64 + 24)
            sheet.alpha_composite(im, (ox, y + 20))
            sheet.alpha_composite(im.resize((64, 64), Image.LANCZOS), (ox + 204, y + 20))
    p = os.path.join(out, "icons_before_after.png")
    sheet.convert("RGB").save(p)
    print("WROTE", p)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "contact":
        contact(sys.argv[2])
    elif mode == "refs":
        refs(sys.argv[2])
    else:
        pairs()
