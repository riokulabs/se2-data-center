"""Rack placement diagrams (Pillow, no Blender): what the block placer sees in a rack slot.

    python3 Source/Model/rack_placement_sheet.py [before|after]

Reads build_report.json and dc/rack.py collision() of THIS checkout (run it from a checkout of an older commit for
"before") and writes preview/rack-placement/<set>/ (or $DC_RACK_PLACEMENT_OUT):
  * cells_<rack>.png: a side section through the left slot column (depth across, height up; the rack's front on the
    left) and a plan at one slot: the occupied cells by what claims them, the free cells, the slot cells, the
    physics boxes, and the inner mount faces (rails, slot floor / ceiling);
  * aim_<rack>.png: the same section with placer aims from the aisle (dc/placer_emu.py): the physics ray to its
    first hit, the segment to hit + 0.25 m, the first occupied cell it crosses with the face normal, and the ghost
    the placer then builds (green: valid in the designed seat; red: refused; orange: valid elsewhere);
  * ../pairs/<file>: before | after side by side, once both sets exist (also the render_*.png of dc/preview_rack_placement.py).
Previews stay out of git (memory: preview git policy)."""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "tools")))

from dc import catalog, config, rack  # noqa: E402
from dc import placer_emu as E  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "after"
OUT = os.environ.get("DC_RACK_PLACEMENT_OUT") or os.path.join(HERE, "preview", "rack-placement", SET)
BG, INK, GRID = (250, 250, 247), (30, 32, 36), (200, 200, 196)
KIND = {"plinth": (120, 124, 132), "column_left": (150, 154, 162), "column_right": (150, 154, 162),
        "tray": (120, 124, 132), "rear_stop": (196, 120, 40), "front_zone": (214, 80, 80), "rear_zone": (214, 120, 120),
        "other": (90, 90, 90)}
LABEL = {"plinth": "plinth (physics)", "column_left": "side column (physics)", "tray": "top tray (physics)",
         "rear_stop": "rear stop (physics, new)", "front_zone": "front-zone occupancy hint (old)",
         "rear_zone": "rear-zone occupancy hint (old)"}


def font(size, bold=False):
    for f in (f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
              f"/usr/share/fonts/TTF/DejaVuSans{'-Bold' if bold else ''}.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def report():
    with open(config.REPORT_PATH) as f:
        return json.load(f)["blocks"]


def claims(spec, entry):
    """cell -> the collision box (regular or occupancy hint) whose overlap occupies it (the generator's query box)."""
    col = rack.collision(spec)
    shift = entry["placement"]["shift"]
    boxes = []
    for kind in ("regular", "occupancy"):
        for nm, a, b in col[kind]:
            ga, gb = (a[0], a[2], -a[1]), (b[0], b[2], -b[1])
            lo = tuple(min(x, y) + s for x, y, s in zip(ga, gb, shift))
            hi = tuple(max(x, y) + s for x, y, s in zip(ga, gb, shift))
            boxes.append((nm, lo, hi))
    lo, hi = catalog.bounds(spec)
    free = {tuple(c) for c in entry["placement"]["free_cells"]}
    out = {}
    for c in E.box_cells(lo, hi) - free:
        p = [0.25 * v for v in c]
        q = 0.124
        hit = [nm for nm, a, b in boxes if all(p[i] + q > a[i] and p[i] - q < b[i] for i in range(3))]
        order = ["rear_stop", "front_zone", "rear_zone", "plinth", "tray", "column_left", "column_right"]
        out[c] = next((k for k in order if k in hit), hit[0] if hit else "other")
    return out, boxes, free


class Canvas:
    def __init__(self, w, h, origin, scale):
        self.im = Image.new("RGB", (w, h), BG)
        self.d = ImageDraw.Draw(self.im)
        self.o, self.s = origin, scale

    def p(self, u, v):           # (u across, v up) metres -> pixels
        return (self.o[0] + u * self.s, self.o[1] - v * self.s)

    def rect(self, u0, v0, u1, v1, fill=None, outline=None, width=1):
        a, b = self.p(u0, v1), self.p(u1, v0)
        self.d.rectangle([a, b], fill=fill, outline=outline, width=width)

    def line(self, pts, fill, width=2):
        self.d.line([self.p(*q) for q in pts], fill=fill, width=width)

    def text(self, u, v, s, size=14, fill=INK, bold=False, anchor="la"):
        self.d.text(self.p(u, v), s, fill=fill, font=font(size, bold), anchor=anchor)


def section(cv, spec, entry, xcell, show_mounts=True):
    """Side section through the cell column x = xcell: u = depth z (front left), v = height y."""
    cl, boxes, free = claims(spec, entry)
    lo, hi = catalog.bounds(spec)
    slots = {tuple(c) for c in rack.SLOT_CELLS(spec)}
    inner = {d: {tuple(c) for c in cs} for d, cs in entry["placement"]["inner_mounts"].items()}
    for y in range(lo[1], hi[1] + 1):
        for z in range(lo[2], hi[2] + 1):
            c = (xcell, y, z)
            u0, v0 = 0.25 * z - 0.125, 0.25 * y - 0.125
            if c in cl:
                cv.rect(u0, v0, u0 + 0.25, v0 + 0.25, fill=KIND.get(cl[c], KIND["other"]), outline=GRID)
            else:
                cv.rect(u0, v0, u0 + 0.25, v0 + 0.25, fill=(232, 246, 232) if c in slots else (255, 255, 255),
                        outline=GRID)
    for nm, a, b in boxes:      # physics / hint boxes cut by the section plane
        x = 0.25 * xcell
        if a[0] <= x <= b[0]:
            cv.rect(a[2], a[1], b[2], b[1], outline=(20, 20, 20) if nm not in ("front_zone", "rear_zone")
                    else (170, 30, 30), width=2)
    if show_mounts:
        for (x, y, z) in inner.get("Up", ()):
            if x == xcell:
                cv.line([(0.25 * z - 0.12, 0.25 * y + 0.125), (0.25 * z + 0.12, 0.25 * y + 0.125)], (30, 110, 220), 6)
        for (x, y, z) in inner.get("Down", ()):
            if x == xcell:
                cv.line([(0.25 * z - 0.12, 0.25 * y - 0.125), (0.25 * z + 0.12, 0.25 * y - 0.125)], (30, 110, 220), 6)
        rails = inner.get("Right", set())   # the left rail (column x = xcell - 1) faces the slot column xcell
        for (x, y, z) in rails:
            if x == xcell - 1:
                u, v = 0.25 * z, 0.25 * y
                cv.d.ellipse([cv.p(u - 0.035, v + 0.035), cv.p(u + 0.035, v - 0.035)], fill=(30, 110, 220))
    zf = 0.25 * lo[2] - 0.125
    cv.text(zf, 0.25 * hi[1] + 0.2, "FRONT (aisle, doors)", 14, bold=True)
    cv.text(0.25 * hi[2] + 0.125, 0.25 * hi[1] + 0.2, "REAR", 14, bold=True, anchor="ra")


def legend(cv, x, y, rows):
    for i, (col, s, kind) in enumerate(rows):
        yy = y + 24 * i
        if kind == "box":
            cv.d.rectangle([x, yy, x + 18, yy + 16], fill=col, outline=GRID)
        elif kind == "line":
            cv.d.line([x, yy + 8, x + 18, yy + 8], fill=col, width=6)
        elif kind == "dot":
            cv.d.ellipse([x + 3, yy + 2, x + 15, yy + 14], fill=col)
        elif kind == "outline":
            cv.d.rectangle([x, yy, x + 18, yy + 16], outline=col, width=2)
        cv.d.text((x + 26, yy), s, fill=INK, font=font(14))


def cells_sheet(name):
    spec = catalog.BY_NAME[name]
    e = report()[name]
    lo, hi = catalog.bounds(spec)
    h = 0.25 * (hi[1] - lo[1] + 1)
    cv = Canvas(1500, max(int(h * 300) + 260, 1000), (0, 0), 300)
    cv.o = (420, 140 + (0.25 * hi[1] + 0.125) * 300)
    section(cv, spec, e, 0)
    cv.d.text((20, 20), f"{name} ({SET}): side section through the left slot column (x = 0)", fill=INK,
              font=font(20, True))
    p = e["placement"]
    cv.d.text((20, 50), f"occupied {p['occupied']}/{p['total']} cells, {len(p['free_cells'])} free; "
              f"inner mounts: rails {len(p['inner_mounts']['Right'])}+{len(p['inner_mounts']['Left'])}, "
              f"floor {len(p['inner_mounts']['Up'])}, ceiling/under {len(p['inner_mounts']['Down'])}",
              fill=INK, font=font(15))
    rows = [(KIND[k], LABEL[k], "box") for k in ("plinth", "column_left", "rear_stop", "front_zone", "rear_zone")]
    rows += [((232, 246, 232), "slot cell (free)", "box"), ((255, 255, 255), "other free cell", "box"),
             ((20, 20, 20), "physics box cut by the section", "outline"), ((170, 30, 30), "occupancy hint box", "outline"),
             ((30, 110, 220), "mount face: slot floor (top) / ceiling (bottom)", "line"),
             ((30, 110, 220), "mount: left rail face toward this cell", "dot")]
    legend(cv, 1000, 120, rows)
    # plan at slot 4: x across, z down the page (front at the top)
    ys = sorted({c[1] for c in rack.SLOT_CELLS(spec)})
    yk = ys[min(3, len(ys) - 1)]
    cl, _, free = claims(spec, e)
    inner = {d: {tuple(c) for c in cs} for d, cs in p["inner_mounts"].items()}
    ox, oy, s = 1000, 520, 70
    cv.d.text((ox, oy - 40), f"plan at slot {ys.index(yk) + 1} (front at the top)", fill=INK, font=font(15, True))
    for x in range(lo[0], hi[0] + 1):
        for z in range(lo[2], hi[2] + 1):
            c = (x, yk, z)
            a = (ox + (x - lo[0]) * s, oy + (z - lo[2]) * s)
            col = KIND.get(cl[c], KIND["other"]) if c in cl else ((232, 246, 232) if c in
                                                                   {tuple(q) for q in rack.SLOT_CELLS(spec)} else BG)
            cv.d.rectangle([a, (a[0] + s, a[1] + s)], fill=col, outline=GRID)
            if (x, yk, z) in inner.get("Right", ()):
                cv.d.line([(a[0] + s - 3, a[1] + 6), (a[0] + s - 3, a[1] + s - 6)], fill=(30, 110, 220), width=6)
            if (x, yk, z) in inner.get("Left", ()):
                cv.d.line([(a[0] + 3, a[1] + 6), (a[0] + 3, a[1] + s - 6)], fill=(30, 110, 220), width=6)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"cells_{name}.png")
    cv.im.save(path)
    return path


def aim_sheet(name):
    spec = catalog.BY_NAME[name]
    e = report()[name]
    lo, hi = catalog.bounds(spec)
    from dc import integration
    srv = E.server_prefab(catalog.BY_NAME["DC_Srv_Compute"], integration.SERVER_MOUNTS)
    slots = {tuple(c) for c in rack.SLOT_CELLS(spec)}
    seats = {k: E.slot_seat(slots, srv, k, 1) for k in range(1, len({c[1] for c in slots}) + 1)}
    g = E.Grid([E.rack_block(spec, e)])
    g.add(E.placed(srv, E.ROT_ID, E.mounted_for(srv, E.ROT_ID, seats[2]), "server in slot 2"))
    h = 0.25 * (hi[1] - lo[1] + 1)
    cv = Canvas(1800, int(h * 300) + 330, (0, 0), 300)
    cv.o = (1000, 230 + (0.25 * hi[1] + 0.125) * 300)
    section(cv, spec, e, 0)
    for c in seats[2]:
        if c[0] == 0:
            cv.rect(0.25 * c[2] - 0.125, 0.25 * c[1] - 0.125, 0.25 * c[2] + 0.125, 0.25 * c[1] + 0.125,
                    fill=(110, 140, 190), outline=GRID)
    zf = 0.25 * lo[2] - 0.125
    k_top = max(seats)
    aims = [("A rear stop, slot 4", seats[min(4, k_top)], "back"),
            ("B rail, front row, slot 5", seats[min(5, k_top)], "front_rail"),
            ("C server 2's top, front third", seats[3], "floor_front"),
            ("D slot 1 floor, rear row", seats[1], "floor_rear"),
            (f"E rear stop, top slot {k_top}", seats[k_top], "back")]
    rows = []
    colours = [(200, 40, 140), (230, 140, 20), (40, 150, 60), (40, 90, 200), (120, 60, 200)]
    for i, (lab, seat, how) in enumerate(aims):
        ys = [c[1] for c in seat]
        zs = [c[2] for c in seat]
        yv = 0.25 * min(ys)
        if how == "back":
            look = (0.06, yv, 0.25 * max(zs) + 0.126)
        elif how == "front_rail":
            look = (-0.124, yv + 0.06, 0.25 * min(zs))
        elif how == "floor_front":
            look = (0.06, yv - 0.124, 0.25 * min(zs))
        else:
            look = (0.06, yv - 0.124, 0.25 * max(zs))
        eye = (0.06, yv + (0.3 if how.startswith("floor") else 0.12), zf - 1.5)
        t = g.target(eye, E.sub(look, eye))
        col = colours[i]
        if t is None:
            cv.line([(eye[2], eye[1]), (look[2] + 0.8, look[1] - 0.8 * (eye[1] - look[1]) / (look[2] - eye[2]))],
                    col, 2)
            rows.append(f"{lab}: no physics hit -> no target")
            continue
        hit, nrm, pp, dist = t
        r = g.aim(srv, E.ROT_ID, eye, look)
        d = E.sub(look, eye)
        n = sum(v * v for v in d) ** 0.5
        tp = None
        for b in g.blocks:
            for a, bb in b.boxes:
                tt = E.slab(eye, tuple(v / n for v in d), a, bb)
                if tt is not None and (tp is None or tt < tp):
                    tp = tt
        hp = tuple(eye[j] + d[j] / n * tp for j in range(3))
        ep = tuple(eye[j] + d[j] / n * (tp + 0.25) for j in range(3))
        cv.line([(eye[2], eye[1]), (hp[2], hp[1])], col, 3)
        cv.line([(hp[2], hp[1]), (ep[2], ep[1])], col, 1)
        cv.d.ellipse([cv.p(eye[2] - 0.03, eye[1] + 0.03), cv.p(eye[2] + 0.03, eye[1] - 0.03)], fill=col)
        cv.text(eye[2] - 0.05, eye[1], lab[0], 16, fill=col, bold=True, anchor="rm")
        u, v = 0.25 * hit[2], 0.25 * hit[1]
        cv.rect(u - 0.125, v - 0.125, u + 0.125, v + 0.125, outline=col, width=4)
        cv.line([(u, v), (u + 0.2 * nrm[2], v + 0.2 * nrm[1])], col, 4)
        okseat = r["valid"] and r["cells"] in seats.values()
        gc = (40, 170, 70) if okseat else (230, 140, 20) if r["valid"] else (220, 40, 40)
        for c in r["cells"]:
            if c[0] == min(q[0] for q in r["cells"]):
                cv.rect(0.25 * c[2] - 0.11, 0.25 * c[1] - 0.11, 0.25 * c[2] + 0.11, 0.25 * c[1] + 0.11, outline=gc,
                        width=3)
        state = ("VALID, exactly a slot seat" if okseat else "valid, NOT a seat" if r["valid"]
                 else "REFUSED (" + ("no mount point" if not r["mount"] else "occupied") + ")")
        zs_ = sorted({c[2] for c in r["cells"]})
        rows.append(f"{lab}: hits {r['hit_block']} cell z={hit[2]}, normal {nrm}; ghost z {zs_[0]}..{zs_[-1]}, "
                    f"y {min(c[1] for c in r['cells'])}: {state}")
    cv.d.text((20, 20), f"{name} ({SET}): placer aims from the aisle (side section x = 0; eyes 1.5 m out)", fill=INK,
              font=font(20, True))
    for i, s in enumerate(rows):
        cv.d.text((20, 54 + 22 * i), s, fill=colours[i], font=font(15))
    legend(cv, 1400, 260, [((40, 170, 70), "ghost: valid, in its seat", "outline"),
                           ((230, 140, 20), "ghost: valid elsewhere", "outline"),
                           ((220, 40, 40), "ghost: refused", "outline"),
                           ((110, 140, 190), "server seated in slot 2", "box"),
                           ((30, 30, 30), "thick: physics ray; thin: +0.25 m", "line")])
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"aim_{name}.png")
    cv.im.save(path)
    return path


def pairs():
    """preview/rack-placement/pairs/<file>: before | after, for every file both sets have."""
    root = os.path.dirname(OUT)
    b, a = os.path.join(root, "before"), os.path.join(root, "after")
    if not (os.path.isdir(a) and os.path.isdir(b)):
        return []
    out = []
    os.makedirs(os.path.join(root, "pairs"), exist_ok=True)
    for f in sorted(set(os.listdir(a)) & set(os.listdir(b))):
        ia, ib = Image.open(os.path.join(b, f)).convert("RGB"), Image.open(os.path.join(a, f)).convert("RGB")
        h = max(ia.height, ib.height)
        im = Image.new("RGB", (ia.width + ib.width + 20, h + 40), BG)
        im.paste(ia, (0, 40))
        im.paste(ib, (ia.width + 20, 40))
        d = ImageDraw.Draw(im)
        d.text((10, 8), "BEFORE (HEAD 85cfdc8b)", fill=(180, 30, 30), font=font(22, True))
        d.text((ia.width + 30, 8), "AFTER (placement fix)", fill=(30, 130, 50), font=font(22, True))
        path = os.path.join(root, "pairs", f)
        im.save(path)
        out.append(path)
    return out


if __name__ == "__main__":
    for nm in ("DC_Rack42_Open", "DC_Rack24_Open"):
        print(cells_sheet(nm))
        print(aim_sheet(nm))
    for p_ in pairs():
        print(p_)
