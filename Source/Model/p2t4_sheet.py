"""Plan 2 Task 4 sheets (Pillow, no Blender).

    python3 Source/Model/p2t4_sheet.py [N]        (N = the task's preview folder, default 4)

Reads preview/p2-task-N/ (dc/preview_trays.py) and writes there:
  * sheet_<piece>.jpg: each piece's 3/4, top and end views side by side;
  * sheet_density_<shape>.jpg: one shape at every built density (3/4 views stacked);
  * contact.jpg: every shot on one sheet (for the visual audit)."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TASK = sys.argv[1] if len(sys.argv) > 1 else "4"
ROOT = os.path.join(HERE, "preview", f"p2-task-{TASK}")


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


def _row(paths, labels, cell, title, out):
    f = _font(24)
    sheet = Image.new("RGB", (len(paths) * (cell[0] + 10) + 10, cell[1] + 90), (12, 12, 14))
    d = ImageDraw.Draw(sheet)
    d.text((12, 10), title, fill=(240, 240, 240), font=_font(30))
    for k, (p, lab) in enumerate(zip(paths, labels)):
        sheet.paste(_fit(p, cell), (10 + k * (cell[0] + 10), 80))
        d.text((14 + k * (cell[0] + 10), 52), lab, fill=(220, 220, 220), font=f)
    sheet.save(out, quality=90)


def pieces():
    names = sorted({n[len("piece_"):].rsplit("_", 1)[0] for n in os.listdir(ROOT) if n.startswith("piece_")})
    for n in names:
        views = [v for v in ("34", "front", "side", "top", "end")
                 if os.path.exists(os.path.join(ROOT, f"piece_{n}_{v}.png"))]
        _row([os.path.join(ROOT, f"piece_{n}_{v}.png") for v in views], [{"34": "3/4 front", "top": "top (ortho)",
             "end": "near end-on, port a", "front": "front (+y, the rack fronts)", "side": "side (port a's end)"}[v]
             for v in views], (700, 480), n, os.path.join(ROOT, f"sheet_{n}.jpg"))
    order = ("Empty", "Low", "Moderate", "Full")
    shapes = sorted({n.rsplit("_", 1)[0] for n in names if n.rsplit("_", 1)[1] in order})
    for sh in shapes:
        ds = [n for n in names if n.rsplit("_", 1)[0] == sh and n.rsplit("_", 1)[1] in order]
        ds.sort(key=lambda n: order.index(n.rsplit("_", 1)[1]))
        _row([os.path.join(ROOT, f"piece_{n}_34.png") for n in ds], [n.rsplit("_", 1)[1] for n in ds], (620, 430),
             f"{sh}: densities", os.path.join(ROOT, f"sheet_density_{sh.replace('DC_Tray_', '')}.jpg"))
    print(f"{len(names)} piece sheets")


def contact():
    names = sorted(n for n in os.listdir(ROOT) if n.endswith(".png"))
    cols = 6
    cw, ch = 460, 300
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cw + 8) + 8, rows * (ch + 32) + 8), (12, 12, 14))
    d = ImageDraw.Draw(sheet)
    f = _font(15)
    for i, n in enumerate(names):
        x, y = 8 + (i % cols) * (cw + 8), 8 + (i // cols) * (ch + 32)
        sheet.paste(_fit(os.path.join(ROOT, n), (cw, ch)), (x, y + 24))
        d.text((x + 2, y + 3), n[:-4], fill=(230, 230, 230), font=f)
    path = os.path.join(ROOT, "contact.jpg")
    sheet.save(path, quality=86)
    print("contact ->", path, len(names), "shots")


def mockup_pair():
    """Task 8: our rack row from the v2 mockup's 05b camera beside the mockup itself."""
    ours = os.path.join(ROOT, "row_mockup05b.png")
    mock = os.path.join(HERE, "..", "..", "..", "..", "docs", "design", "mockups", "data-center", "v2",
                        "05b-reducer-longdrop-closeup.png")
    if os.path.exists(ours) and os.path.exists(mock):
        _row([mock, ours], ["v2 mockup 05b (reducer, long drop to a half rack)", "built: the same lens (22 mm), our row"],
             (960, 560), "05b: mockup | built", os.path.join(ROOT, "pair_mockup05b.jpg"))


if __name__ == "__main__":
    pieces()
    if TASK == "8":
        mockup_pair()
    contact()
