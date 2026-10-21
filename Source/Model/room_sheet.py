"""The reference room's layout sheets (Pillow, no Blender): plan and section of dc/room.reference_room().

    python3 Source/Model/room_sheet.py [FOLDER]        (default room: writes preview/room/)

Per aisle width and hot / cold: layout_<w>_<aisle>.png, the plan (top view: tiles, the rows, the containment, the
tray run and its rod hangers, the signs) over the section across the aisle at rack A2 (STACK heights dimensioned,
the end door projected dashed). Also contact.jpg: every room render of the folder on one sheet."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "tools")))   # se2model (dc.rack)

from dc import dims as DM  # noqa: E402
from dc import room  # noqa: E402

PX = 92                                    # pixels per metre
BG, INK, DIM = (17, 18, 21), (226, 228, 232), (150, 154, 162)
FILL = {   # family -> (fill, outline)
    "floor": ((44, 46, 50), (64, 66, 72)), "rack": ((58, 62, 70), (190, 196, 206)),
    "crac": ((30, 70, 110), (90, 170, 255)), "pdu_cabinet": ((95, 62, 18), (255, 160, 40)),
    "pdu_strip": ((150, 95, 25), (255, 170, 60)), "contain_roof": ((120, 135, 150), (210, 225, 240)),
    "contain_door": ((90, 120, 150), (190, 220, 255)), "sign": ((20, 20, 22), (240, 240, 240)),
    "tray": ((20, 45, 110), (70, 130, 255)), "trayrods": ((60, 60, 64), (170, 170, 176)),
}


def _font(size, bold=True):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for d in ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/TTF"):
        if os.path.exists(os.path.join(d, name)):
            return ImageFont.truetype(os.path.join(d, name), size)
    return ImageFont.load_default()


class View:
    """World (a, b) metres -> image pixels: a to the right, b up, origin at (ox, oy) pixels."""

    def __init__(self, d, a0, b1, ox, oy):
        self.d, self.a0, self.b1, self.ox, self.oy = d, a0, b1, ox, oy

    def p(self, a, b):
        return (self.ox + (a - self.a0) * PX, self.oy + (self.b1 - b) * PX)

    def rect(self, a0, b0, a1, b1, fill=None, outline=None, width=1):
        x0, y0 = self.p(a0, b1)
        x1, y1 = self.p(a1, b0)
        self.d.rectangle((x0, y0, x1, y1), fill=fill, outline=outline, width=width)

    def line(self, a0, b0, a1, b1, fill, width=1, dash=None):
        x0, y0 = self.p(a0, b0)
        x1, y1 = self.p(a1, b1)
        if not dash:
            self.d.line((x0, y0, x1, y1), fill=fill, width=width)
            return
        n = max(1, int(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 / dash))
        for k in range(0, n, 2):
            t0, t1 = k / n, min(1.0, (k + 1) / n)
            self.d.line((x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0, x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1),
                        fill=fill, width=width)

    def text(self, a, b, s, font, fill=INK, anchor="mm"):
        self.d.text(self.p(a, b), s, fill=fill, font=font, anchor=anchor)


def _fam(p):
    return room.spec(p).family


def plan(img, d, placed, w, aisle, oy):
    x0, x1, y0, y1 = room.floor_extent(w)
    v = View(d, x0, y1, 60, oy)
    f, fs = _font(15), _font(12, False)
    for p in placed:                                   # the tiles (0.5 m), perforated ones dotted
        if _fam(p) != "floor":
            continue
        (a0, b0, _), (a1, b1, _) = room.box(p)
        fill, out = FILL["floor"]
        perf = room.spec(p).variant == "Perf"
        n = room.spec(p).cells[0] // 2
        for i in range(n):
            for j in range(n):
                ta, tb = a0 + 0.5 * i, b0 + 0.5 * j
                v.rect(ta, tb, ta + 0.5, tb + 0.5, fill=(52, 58, 66) if perf else fill, outline=out)
                if perf:
                    for u in range(1, 5):
                        for t in range(1, 5):
                            cx, cy = v.p(ta + 0.1 * u, tb + 0.1 * t)
                            d.ellipse((cx - 1.5, cy - 1.5, cx + 1.5, cy + 1.5), fill=(20, 22, 26))
    order = ("rack", "crac", "pdu_cabinet", "pdu_strip", "contain_door", "contain_roof", "tray", "trayrods", "sign")
    for fam in order:
        for p in placed:
            if _fam(p) != fam:
                continue
            (a0, b0, _), (a1, b1, _) = room.box(p)
            fill, out = FILL[fam]
            if fam == "contain_roof":
                v.rect(a0, b0, a1, b1, outline=out, width=1)
                for k in range(1, 4):
                    v.line(a0 + 0.25 * k, b0, a0 + 0.25 * k, b1, (90, 100, 112))
                continue
            if fam in ("tray", "trayrods"):
                v.rect(a0, b0, a1, b1, outline=out, width=2 if fam == "tray" else 1)
                continue
            v.rect(a0, b0, a1, b1, fill=fill, outline=out, width=2 if fam in ("rack", "crac", "pdu_cabinet") else 1)
            if fam in ("rack", "crac", "pdu_cabinet"):      # the front face: a bright bar
                fy = room.rot((0, 1, 0), p.yaw)[1]
                bf = b1 if fy > 0 else b0
                v.line(a0 + 0.05, bf - 0.03 * fy, a1 - 0.05, bf - 0.03 * fy, (120, 220, 140), 3)
                lab = p.tag if fam == "rack" else ("CRAC" if fam == "crac" else "PDU")
                v.text((a0 + a1) / 2, (b0 + b1) / 2, lab, f)
            if fam == "contain_door":
                lw = room.aisle_width(room.spec(p)) / 2
                xm = (a0 + a1) / 2
                for sg in (-1, 1):
                    v.line(xm, 0.0, xm, sg * lw, (230, 240, 255), 3)                   # a closed leaf
                    v.line(xm, sg * lw, xm, sg * 2 * lw, (120, 140, 170), 2, dash=5)   # its open pocket
    # dimensions: the aisle and the rows
    xa = x1 - 1.2
    v.line(xa, -w / 2, xa, w / 2, INK, 1)
    v.text(xa + 0.08, 0, f"aisle {w:.1f} m ({aisle})", fs, INK, "lm")
    v.text((x0 + x1) / 2, y1 - 0.25, f"reference room: {w:.1f} m {aisle} aisle -- plan (x along the rows, "
                                     f"0.5 m tile grid; green = unit fronts)", f)
    hang = next((p for p in placed if p.name == "DC_Sign_AisleHang"), None)
    if hang:
        v.text(hang.origin[0], hang.origin[1] - 0.68, "hanging sign", fs, INK)
    for p in placed:
        if p.name == "DC_Sign_Aisle":
            v.text(p.origin[0] + (-0.45 if p.tag.startswith("west") else 0.45), 0.0, "sign", fs, INK)
    # the legend
    lx = x0 + 0.2
    for fam in ("rack", "crac", "pdu_cabinet", "pdu_strip", "contain_door", "contain_roof", "tray", "trayrods",
                "sign"):
        fill, out = FILL[fam]
        v.rect(lx, y0 - 0.45, lx + 0.25, y0 - 0.2, fill=fill if fam not in ("tray", "trayrods") else None,
               outline=out, width=2)
        v.text(lx + 0.32, y0 - 0.325, fam, fs, INK, "lm")
        lx += 1.3
    return v


def section(img, d, placed, w, aisle, oy, xs=1.5):
    """Across the aisle (y to the right, z up) at x = xs, the west door projected (dashed)."""
    S = room.STACK
    _, _, y0, y1 = room.floor_extent(w)
    v = View(d, y0, S["ceiling"] + 0.4, 250, oy)
    f, fs = _font(15), _font(12, False)
    v.rect(y0, 0, y1, S["floor_top"], fill=(40, 42, 46), outline=(80, 82, 88))
    v.rect(y0, S["ceiling"], y1, S["ceiling"] + 0.15, fill=(36, 38, 42), outline=(80, 82, 88))
    for p in placed:
        (a0, b0, z0), (a1, b1, z1) = room.box(p)
        fam = _fam(p)
        if fam == "contain_door" and p.tag.startswith("west"):
            for yy in (b0, b1, -w / 2, w / 2):
                v.line(yy, z0, yy, z1 - DM.CELL, (160, 190, 230), 1, dash=6)
            v.line(b0, z1 - DM.CELL, b1, z1 - DM.CELL, (160, 190, 230), 1, dash=6)
            v.line(b0, z1, b1, z1, (160, 190, 230), 1, dash=6)
            continue
        if fam == "sign" and p.tag.startswith("west"):
            v.rect(b0, z0, b1, z1, outline=(240, 240, 240))
            continue
        if not (a0 < xs < a1) or fam == "floor":
            continue
        fill, out = FILL.get(fam, ((60, 60, 60), (200, 200, 200)))
        if fam in ("tray", "trayrods", "contain_roof"):
            v.rect(b0, z0, b1, z1, outline=out, width=2)
        else:
            v.rect(b0, z0, b1, z1, fill=fill, outline=out, width=2)
        if fam == "rack":
            fy = room.rot((0, 1, 0), p.yaw)[1]
            bf = b1 if fy > 0 else b0
            v.line(bf - 0.03 * fy, z0 + 0.1, bf - 0.03 * fy, z1 - 0.3, (120, 220, 140), 3)
            v.text((b0 + b1) / 2, (z0 + z1) / 2, p.tag, f)
    # the STACK, dimensioned on the left
    for k, z in (("floor_top", S["floor_top"]), ("roof", S["roof"][0]), ("rack_top = door_top", S["rack_top"]),
                 ("tray_bottom", S["tray_bottom"]), ("tray_top", S["tray_top"]), ("ceiling", S["ceiling"])):
        v.line(y0 - 0.15, z, y1, z, (70, 74, 82), 1, dash=4)
        v.text(y0 - 0.2, z, f"{k} {z:.2f} m", fs, INK, "rm")
    v.text(0, S["ceiling"] + 0.3, f"section across the aisle at x = {xs:.1f} m (rack A2); west door projected", f)
    return v


def sheet(w, aisle, out):
    placed = room.reference_room(w, aisle)
    x0, x1, y0, y1 = room.floor_extent(w)
    W = int((x1 - x0) * PX) + 120
    H1 = int((y1 - y0) * PX) + 110
    H2 = int((room.STACK["ceiling"] + 0.6) * PX) + 40
    img = Image.new("RGB", (max(W, int((y1 - y0) * PX) + 300), H1 + H2 + 40), BG)
    d = ImageDraw.Draw(img)
    plan(img, d, placed, w, aisle, 40)
    section(img, d, placed, w, aisle, H1 + 60)
    path = os.path.join(out, f"layout_{round(w * 100):03d}_{aisle}.png")
    img.save(path)
    return path


def contact(out):
    names = sorted(n for n in os.listdir(out) if n.startswith(("room_", "vanilla_")) and n.endswith(".png"))
    if not names:
        return None
    cols, cw, ch = 4, 640, 360
    rows = (len(names) + cols - 1) // cols
    img = Image.new("RGB", (cols * (cw + 8) + 8, rows * (ch + 34) + 8), (12, 12, 14))
    d = ImageDraw.Draw(img)
    f = _font(17)
    for i, n in enumerate(names):
        x, y = 8 + (i % cols) * (cw + 8), 8 + (i // cols) * (ch + 34)
        im = Image.open(os.path.join(out, n)).convert("RGB")
        im.thumbnail((cw, ch), Image.LANCZOS)
        img.paste(im, (x + (cw - im.width) // 2, y + 28))
        d.text((x + 2, y + 4), n[:-4], fill=(230, 230, 230), font=f)
    path = os.path.join(out, "contact.jpg")
    img.save(path, quality=88)
    return path


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "room"
    out = os.path.join(HERE, "preview", folder)
    os.makedirs(out, exist_ok=True)
    for w in DM.AISLE_WIDTHS:
        for aisle in ("cold", "hot"):
            print("wrote", sheet(w, aisle, out))
    print("contact ->", contact(out))
