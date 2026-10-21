"""Containment door contact sheet (Pillow, no Blender).

    python3 Source/Model/contain_doors_sheet.py

Reads every render in preview/contain-doors/ (dc/preview_contain_doors.py) and writes preview/contain-doors/contact.jpg, grouped:
each width (closed, open, three animation frames, the aisle side, LODs, collision), the plan sweeps, the close-ups,
the fracture pieces, the paints, the room shots and the vanilla comparison."""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "preview", "contain-doors")
ORDER = ("DC_Contain_Door_100", "DC_Contain_Door_150", "DC_Contain_Door_200", "plan_sweep", "closeup", "fracture",
         "paints", "room_150_cold", "room_150_hot", "room_100", "room_200", "vanilla")


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


def _key(n):
    return (next((i for i, p in enumerate(ORDER) if n.startswith(p)), len(ORDER)), n)


def contact():
    names = sorted((n for n in os.listdir(ROOT) if n.endswith(".png")), key=_key)
    cols, cw, ch = 5, 520, 340
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cw + 8) + 8, rows * (ch + 34) + 60), (12, 12, 14))
    d = ImageDraw.Draw(sheet)
    d.text((10, 12), f"Containment sliding doors ({len(names)} renders)", fill=(240, 240, 240), font=_font(30))
    f = _font(17)
    for i, n in enumerate(names):
        x, y = 8 + (i % cols) * (cw + 8), 60 + (i // cols) * (ch + 34)
        sheet.paste(_fit(os.path.join(ROOT, n), (cw, ch)), (x, y + 26))
        d.text((x + 2, y + 4), n[:-4], fill=(230, 230, 230), font=f)
    path = os.path.join(ROOT, "contact.jpg")
    sheet.save(path, quality=86)
    print("contact ->", path)


if __name__ == "__main__":
    contact()
