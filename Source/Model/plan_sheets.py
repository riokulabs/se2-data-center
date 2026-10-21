"""Cable-plan diagrams (Pillow, no Blender): orthographic drawings of the tray plans (dc/tray_plan.py).

    python3 Source/Model/plan_sheets.py [--task 2|3] [--out <folder>]

Writes, into the output folder (default preview/p2-task-2/):
  * 01_lanes_<Density>.png, 01_lanes_ladder.png: the end-on port diagram per density (basket, lanes, lane rings
    of the lanes a denser tray adds, trapeze rods), and 02_nesting.png (every lane by the density that adds it);
  * 10_<block>.png: each linear piece in top, side and end view plus both port faces with their lane rings;
  * 20_density_ladder.png, 21_mixed_joint.png, 22_reducer_chain.png, 23_run_rhythm.png: the joints;
  * 30_drop_over_rack.png, 31_drop_chute_half_rack.png: the Drop and the Chute over stand-in rack boxes;
  * contact.png: everything on one sheet.
With --task 3 (into preview/p2-task-3/): 10_<block>.png for every bend and junction at every density (top, side,
end and every port), 20_strap_radials.png, 30_tee_cross_detail.png, 31_junction_run_densities.png,
32_junction_run_full.png, 40_offset_up_down.png and contact.png.
Drawn from the plans only; colours are the preview stand-ins of the vanilla materials (data = blue)."""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dc import catalog, config, dims as DM, tray_lanes as TL, tray_plan as P  # noqa: E402

SS = 3                                   # supersampling
BG = (247, 247, 244)
INK = (40, 42, 46)
FAINT = (205, 207, 210)
GRIDC = (225, 226, 228)
MAT = {"PaintedMetalColorable": (47, 111, 214), "PaintedMetalYellow": (232, 190, 26),
       "PaintedMetalGrey": (138, 143, 150), "Rubber": (38, 38, 40), "PaintedMetalDarker": (70, 74, 82),
       "BrushedMetal": (160, 166, 174), "MetalDull": (120, 124, 130)}
STEEL = (150, 156, 164)
DARK = (70, 74, 82)
ENTRYC = (226, 120, 30)
DENS_C = {"Low": (47, 111, 214), "Moderate": (40, 150, 90), "Full": (190, 60, 60)}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(px, bold=False):
    try:
        return ImageFont.truetype(FONT_B if bold else FONT, px * SS)
    except OSError:
        return ImageFont.load_default()


def shade(c, k):
    return tuple(int(max(0, min(255, v * k))) for v in c)


def hull(pts):
    pts = sorted(set(map(tuple, pts)))
    if len(pts) < 3:
        return pts

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) -
                                     (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out
    lo, hi = half(pts), half(reversed(pts))
    return lo[:-1] + hi[:-1]


# ---------------------------------------------------------------------------------------------------- a view
VIEWS = {   # name: (right, up); the viewer sits at right x up
    "top": ((1, 0, 0), (0, 1, 0)),
    "side": ((1, 0, 0), (0, 0, 1)),        # from -y
    "front": ((-1, 0, 0), (0, 0, 1)),      # from +y (the rack's front)
    "end": ((0, 1, 0), (0, 0, 1)),         # from +x
    "end_a": ((0, -1, 0), (0, 0, 1)),      # from -x
}


class Panel:
    """One orthographic view of a world box, drawn at `scale` px per metre."""

    def __init__(self, title, view, lo, hi, scale, pad=46, note=None):
        self.title, self.note = title, note
        r, u = (np.asarray(v, float) for v in (VIEWS[view] if isinstance(view, str) else view))   # or (right, up)
        self.r, self.u, self.d = r, u, np.cross(r, u)
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        self.u0, self.u1 = (corners @ r).min(), (corners @ r).max()
        self.v0, self.v1 = (corners @ u).min(), (corners @ u).max()
        self.k = scale * SS
        self.pad = pad * SS
        self.top = 34 * SS
        w = int((self.u1 - self.u0) * self.k + 2 * self.pad)
        h = int((self.v1 - self.v0) * self.k + 2 * self.pad + self.top)
        self.im = Image.new("RGB", (w, h), BG)
        self.g = ImageDraw.Draw(self.im, "RGBA")
        self.items = []

    def px(self, p):
        p = np.asarray(p, float)
        return (self.pad + (p @ self.r - self.u0) * self.k, self.top + self.pad + (self.v1 - p @ self.u) * self.k)

    def depth(self, p):
        return float(np.asarray(p, float) @ self.d)

    # queued drawables, painted far to near
    def add(self, depth, fn):
        self.items.append((depth, len(self.items), fn))

    def flush(self):
        for _, _, fn in sorted(self.items, key=lambda t: (t[0], t[1])):
            fn()
        self.items = []

    # immediate primitives
    def line(self, pts, col, w_px=1.0, w_m=None):
        q = [self.px(p) for p in pts]
        w = max(1, int(round(w_m * self.k if w_m else w_px * SS)))
        if len(q) >= 2:
            self.g.line(q, fill=col, width=w, joint="curve")
        return w

    def tube(self, pts, col, r, caps=(True, True)):
        """A bundle seen from the side: a dark-edged band of width 2r with round ends (where it really ends)."""
        q = [self.px(p) for p in pts]
        ends = [a for a, c in zip((q[0], q[-1]), caps) if c]
        w = max(2, int(round(2 * r * self.k)))
        edge = shade(col, 0.55)
        self.g.line(q, fill=edge, width=w + 2 * SS, joint="curve")
        for a in ends:
            self.g.ellipse([a[0] - w / 2 - SS, a[1] - w / 2 - SS, a[0] + w / 2 + SS, a[1] + w / 2 + SS], fill=edge)
        self.g.line(q, fill=col, width=w, joint="curve")
        for a in ends:
            self.g.ellipse([a[0] - w / 2, a[1] - w / 2, a[0] + w / 2, a[1] + w / 2], fill=col)
        hl = shade(col, 1.25) if sum(col) < 600 else shade(col, 1.06)
        self.g.line(q, fill=hl + (110,), width=max(1, w // 4), joint="curve")

    def circle(self, p, r_m, fill=None, outline=None, w_px=1.0, dash=False):
        x, y = self.px(p)
        r = r_m * self.k
        box = [x - r, y - r, x + r, y + r]
        if dash and outline:
            n = 24
            for i in range(0, n, 2):
                self.g.arc(box, 360 * i / n, 360 * (i + 1) / n, fill=outline, width=max(1, int(w_px * SS)))
            return
        self.g.ellipse(box, fill=fill, outline=outline, width=max(1, int(w_px * SS)))

    def poly(self, pts, fill=None, outline=None, w_px=1.0):
        q = hull([self.px(p) for p in pts])
        if len(q) >= 3:
            self.g.polygon(q, fill=fill, outline=outline, width=max(1, int(w_px * SS)))

    def text(self, p, s, size=11, col=INK, anchor="mm", bold=False, px=False):
        xy = p if px else self.px(p)
        if px:
            xy = (xy[0] * SS, xy[1] * SS)
        self.g.text(xy, s, fill=col, font=font(size, bold), anchor=anchor)

    def dashed(self, a, b, col, w_px=1.0, dash=0.012):
        a, b = np.asarray(a, float), np.asarray(b, float)
        L = np.linalg.norm(b - a)
        n = max(1, int(L / dash))
        for i in range(0, n, 2):
            self.line([a + (b - a) * i / n, a + (b - a) * min(n, i + 1) / n], col, w_px)

    def grid(self, lo, hi, step=TL.CELL, col=GRIDC):
        """The 0.25 m grid planes of a box, seen edge-on."""
        lo, hi = np.asarray(lo, float), np.asarray(hi, float)
        for axis in (self.r, self.u):
            k = int(np.argmax(np.abs(axis)))
            for v in np.arange(lo[k], hi[k] + 1e-9, step):
                a, b = lo.copy(), hi.copy()
                a[k] = b[k] = v
                self.line([a, b], col, 1)

    def box_outline(self, lo, hi, col=(150, 152, 156), w_px=1.5):
        lo, hi = np.asarray(lo, float), np.asarray(hi, float)
        c = [np.array([x, y, z]) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        q = hull([self.px(p) for p in c])
        self.g.polygon(q, outline=col, width=max(1, int(w_px * SS)))

    def scale_bar(self, metres=0.25):
        x0, y0 = self.pad, self.im.height - self.pad * 0.45
        self.g.line([(x0, y0), (x0 + metres * self.k, y0)], fill=INK, width=2 * SS)
        for x in (x0, x0 + metres * self.k):
            self.g.line([(x, y0 - 4 * SS), (x, y0 + 4 * SS)], fill=INK, width=SS)
        self.g.text((x0 + metres * self.k + 8 * SS, y0), f"{metres:g} m", fill=INK, font=font(10), anchor="lm")

    def finish(self):
        self.flush()
        self.g.text((self.pad * 0.5, 10 * SS), self.title, fill=INK, font=font(13, True), anchor="lt")
        if self.note:
            self.g.text((self.pad * 0.5, 26 * SS), self.note, fill=(90, 92, 96), font=font(10), anchor="lt")
        self.scale_bar()
        return self.im.resize((self.im.width // SS, self.im.height // SS), Image.LANCZOS)


# ---------------------------------------------------------------------------------------------------- drawing plans
def draw_profile(pn, o, ss, nn, wall_h=TL.WALL_H, depth=None):
    """The basket's U profile with every wire, seen end-on at o (across ss, floor normal nn)."""
    bottom = P.BASKET_BOTTOM - TL.FLOOR_Z
    dep = pn.depth(o) - 0.3 if depth is None else depth
    prof = [o - TL.WALL_S * ss + wall_h * nn, o - TL.WALL_S * ss + bottom * nn,
            o + TL.WALL_S * ss + bottom * nn, o + TL.WALL_S * ss + wall_h * nn]
    pn.add(dep, lambda: pn.line(prof, STEEL, w_m=2 * TL.WIRE_R))
    for k in np.arange(-0.20, 0.2001, 0.05):
        q = o + k * ss - TL.WIRE_R * nn
        pn.add(dep + 0.01, lambda q=q: pn.circle(q, TL.WIRE_R, fill=shade(STEEL, 0.9)))
    for k in (-1, 1):
        for h, r in ((0.05, TL.WIRE_R), (wall_h, TL.EDGE_WIRE_R)):
            q = o + k * TL.WALL_S * ss + h * nn
            pn.add(dep + 0.01, lambda q=q, r=r: pn.circle(q, r, fill=shade(STEEL, 0.8), outline=INK, w_px=0.6))


def _runs(mask):
    """Index runs [i0, i1] where mask is true."""
    out, i = [], 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j + 1 < len(mask) and mask[j + 1]:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def draw_basket(pn, path, wall_col=STEEL):
    """A basket path (floor strip, walls where they stand, U-wires every 0.1 m) or a "wall" path (a fillet)."""
    p, n = path.points, path.normals
    bottom = P.BASKET_BOTTOM - TL.FLOOR_Z
    if path.kind == "wall":
        for h, w in ((path.wall_h, TL.EDGE_WIRE_R), (0.05, TL.WIRE_R), (bottom, TL.WIRE_R)):
            q = p + h * n
            pn.add(float(np.mean(q @ pn.d)) - 0.001, lambda q=q, w=w: pn.line(q, wall_col, w_m=2 * w))
        for i in range(0, len(p), 4):
            q = [p[i] + bottom * n[i], p[i] + path.wall_h * n[i]]
            pn.add(pn.depth(p[i]) - 0.0015, lambda q=q: pn.line(q, (170, 175, 182), w_m=2 * TL.WIRE_R))
        return
    t = np.gradient(p, axis=0)
    t /= np.linalg.norm(t, axis=1)[:, None]
    s = np.cross(n, t)
    straight = np.allclose(t, t[0], atol=1e-9)
    if straight and abs(pn.d @ t[0]) > 0.9:     # end-on: the U profile
        draw_profile(pn, p[0], s[0], n[0], path.wall_h)
        return
    for k in (-1, 1):
        on = path.wall_mask((k + 1) // 2)
        for i0, i1 in _runs(on):
            for h, w in ((path.wall_h, TL.EDGE_WIRE_R), (0.05, TL.WIRE_R)):
                q = p[i0:i1 + 1] + k * TL.WALL_S * s[i0:i1 + 1] + h * n[i0:i1 + 1]
                pn.add(float(np.mean(q @ pn.d)) - 0.001, lambda q=q, w=w: pn.line(q, wall_col, w_m=2 * w))
    # the floor: a strip across (seen from above) and its depth (seen from the side), quad by quad
    for i in range(len(p) - 1):
        quad = [p[i] - TL.WALL_S * s[i], p[i] + TL.WALL_S * s[i], p[i + 1] + TL.WALL_S * s[i + 1],
                p[i + 1] - TL.WALL_S * s[i + 1]]
        pn.add(-9, lambda quad=quad: pn.poly(quad, fill=(214, 218, 222, 150)))
        dep = [p[i], p[i] + bottom * n[i], p[i + 1] + bottom * n[i + 1], p[i + 1]]
        pn.add(float(np.mean(np.array(dep) @ pn.d)) - 0.2, lambda dep=dep: pn.poly(dep, fill=(200, 204, 208, 120)))
    for k in np.arange(-0.20, 0.2001, 0.05):
        q = p + k * s
        pn.add(-8.9, lambda q=q: pn.line(q, (190, 194, 198), 0.8))
    # U-wires every 0.1 m from 0.05 m (only the uncut sides rise)
    L = path.lengths()
    on = [path.wall_mask(0), path.wall_mask(1)]
    for dpos in np.arange(0.05, L[-1], 0.1):
        i = min(int(np.searchsorted(L, dpos)), len(p) - 1)
        o, ss, nn = p[i], s[i], n[i]
        hw = [path.wall_h if on[k][i] else bottom for k in (0, 1)]
        prof = [o - TL.WALL_S * ss + hw[0] * nn, o - TL.WALL_S * ss + bottom * nn,
                o + TL.WALL_S * ss + bottom * nn, o + TL.WALL_S * ss + hw[1] * nn]
        pn.add(pn.depth(o) - 0.002, lambda prof=prof: pn.line(prof, (170, 175, 182), w_m=2 * TL.WIRE_R))


def draw_bundle(pn, b):
    col = MAT[b.material]
    tangent_depth = abs(pn.d @ (b.points[-1] - b.points[0])) / max(1e-9, np.linalg.norm(b.points[-1] - b.points[0]))
    if tangent_depth > 0.98 and np.allclose(np.cross(np.diff(b.points, axis=0), pn.d), 0, atol=1e-9):
        # seen end-on: the 7 cables
        p = b.points[0] if b.points[0] @ pn.d > b.points[-1] @ pn.d else b.points[-1]
        pn.add(pn.depth(p), lambda: draw_cables(pn, p, b.radius, col))
        return
    # split into runs by depth so the painter's order is right where a bundle passes over another
    seg, n = 12, len(b.points) - 1
    for i in range(0, n, seg):
        q = b.points[i:i + seg + 1]
        caps = (i == 0, i + seg >= n)
        pn.add(float(np.mean(q @ pn.d)), lambda q=q, caps=caps: pn.tube(q, col, b.radius, caps))


def draw_cables(pn, p, R, col):
    r = R / 3
    edge = shade(col, 0.5)
    pn.circle(p, R + 0.0008, fill=shade(col, 0.6))
    for k in range(7):
        c = np.asarray(p, float) + (0 if k == 0 else 2 * r) * (math.cos(k * math.pi / 3) * pn.r +
                                                                  math.sin(k * math.pi / 3) * pn.u)
        pn.circle(c, r * 0.96, fill=col, outline=edge, w_px=0.6)


def draw_fitting(pn, f):
    pts = P.fitting_points(f)
    dep = float(np.mean(pts @ pn.d))
    col = MAT.get(f.params.get("material", "PaintedMetalDarker"), DARK)
    if f.kind == "strap":
        col = (58, 60, 64)
        pn.add(dep + 0.0005, lambda: pn.poly(pts, fill=col + (235,)))
    elif f.kind == "waterfall_guide":
        c0, (a0, a1) = f.params["centre"], f.params["angles"]
        arc = [c0 + (f.params["r_top"] - f.params["thickness"] / 2) * (math.sin(t) * f.frame.s + math.cos(t) *
                                                                        f.frame.u) for t in np.linspace(a0, a1, 24)]
        if abs(pn.d @ f.frame.t) > 0.9:
            pn.add(dep, lambda: pn.line(arc, col, w_m=f.params["thickness"]))
        else:
            pn.add(dep, lambda: pn.poly(pts, fill=col + (220,), outline=INK, w_px=0.6))
    elif f.kind == "tag":
        pn.add(dep + 0.001, lambda: (pn.poly(pts, fill=MAT["PaintedMetalYellow"] + (255,), outline=INK, w_px=0.6),
                                     pn.text(f.frame.o, f.params["text"], 8, INK, bold=True)
                                     if abs(pn.d @ f.frame.s) > 0.9 else None))
    elif f.kind == "saddle_clamp":
        pn.add(dep + 0.0006, lambda: pn.poly(pts, fill=col + (235,), outline=INK, w_px=0.6))
    elif f.kind == "crossover_saddle":
        for part, fr, size in P.saddle_parts(f):
            c = fr.corners(size)
            m = MAT[f.params["leg_material"]] if part == "leg" else MAT[f.params["material"]]
            pn.add(float(np.mean(c @ pn.d)), lambda c=c, m=m: pn.poly(c, fill=m + (245,), outline=INK, w_px=0.6))
    elif f.kind == "boot":
        pn.add(dep + 0.0004, lambda: pn.poly(pts, fill=MAT["Rubber"] + (255,), outline=(90, 90, 90), w_px=0.6))
    else:
        pn.add(dep, lambda: pn.poly(pts, fill=col + (235,), outline=INK, w_px=0.6))


def draw_support(pn, sp):
    """Rods as lines, every other solid (strut, caps, plates, couplers, rails, rungs, feet) as its box."""
    for a, b in sp.rods:
        r = sp.params["rod_r"]
        pn.add(pn.depth((a + b) / 2) - 0.005, lambda a=a, b=b, r=r: pn.line([a, b], MAT["MetalDull"], w_m=2 * r))
    for _, fr, size, mat in sp.solids():
        c = fr.corners(size)
        pn.add(float(np.mean(c @ pn.d)), lambda c=c, mat=mat: pn.poly(c, fill=MAT.get(mat, DARK) + (255,), outline=INK,
                                                                       w_px=0.6))


def draw_entry(pn, e, col=ENTRYC):
    c = [e.o + i * e.ha * e.a + j * e.hb * e.b for i in (-1, 1) for j in (-1, 1)]
    pn.add(pn.depth(e.o) + 0.002, lambda: pn.poly(c, fill=col + (60,), outline=col, w_px=1.4))


def draw_port(pn, port, label=True):
    o, t, s, u = port.frame()
    if abs(pn.d @ t) > 0.9:     # facing the port: its lane rings
        for l in TL.lanes(port.density):
            q = TL.lane_point(port, l)
            pn.add(99, lambda q=q, l=l: pn.circle(q, TL.R_B, outline=(220, 40, 40), w_px=1.1))
        pn.add(99, lambda: (pn.line([o, o + 0.06 * s], (220, 40, 40), 1.4), pn.line([o, o + 0.06 * u], (220, 40, 40),
                                                                                      1.4),
                            pn.text(o + 0.075 * s, "s", 9, (220, 40, 40)), pn.text(o + 0.075 * u, "u", 9, (220, 40, 40))))
        return
    tip = o + 0.09 * t
    pn.add(99, lambda: (pn.line([o, tip], (220, 40, 40), 1.6), pn.circle(o, 0.006, fill=(220, 40, 40)),
                        pn.text(tip + 0.025 * t, f"{port.name} ({port.density})" if label else port.name, 9,
                                (200, 30, 30), bold=True)))


def draw_plan(pn, pl, grid=True, ports=True, offset_box=None):
    lo = np.zeros(3) if offset_box is None else offset_box[0]
    hi = pl.size if offset_box is None else offset_box[1]
    if grid:
        pn.add(-99, lambda: (pn.grid(lo, hi), pn.box_outline(lo, hi)))
    for path in pl.structure:
        draw_basket(pn, path)
    for sp in pl.supports:
        draw_support(pn, sp)
    for b in pl.bundles:
        draw_bundle(pn, b)
    for f in pl.fittings:
        draw_fitting(pn, f)
    for e in pl.entries:
        draw_entry(pn, e)
    if ports:
        for p in pl.ports.values():
            draw_port(pn, p)


# ---------------------------------------------------------------------------------------------------- sheets
def hstack(images, gap=10, bg=BG):
    h = max(i.height for i in images)
    out = Image.new("RGB", (sum(i.width for i in images) + gap * (len(images) - 1), h), bg)
    x = 0
    for i in images:
        out.paste(i, (x, (h - i.height) // 2))
        x += i.width + gap
    return out


def vstack(images, gap=10, bg=BG):
    w = max(i.width for i in images)
    out = Image.new("RGB", (w, sum(i.height for i in images) + gap * (len(images) - 1)), bg)
    y = 0
    for i in images:
        out.paste(i, ((w - i.width) // 2, y))
        y += i.height + gap
    return out


def titled(im, title, sub=None):
    head = 40 if sub else 28
    out = Image.new("RGB", (im.width, im.height + head), BG)
    out.paste(im, (0, head))
    g = ImageDraw.Draw(out)
    g.text((10, 6), title, fill=INK, font=ImageFont.truetype(FONT_B, 16))
    if sub:
        g.text((10, 25), sub, fill=(90, 92, 96), font=ImageFont.truetype(FONT, 11))
    return out


def lanes_panel(density, scale=1500):
    """The end-on port diagram of a straight at `density`: port b of a StraightS, seen from outside."""
    pl = P.plan("StraightS", density)
    port = pl.ports["b"]
    o = np.asarray(port.o)
    lo, hi = np.array([0.5, -0.03, -0.035]), np.array([0.5, 0.53, 0.27])
    pn = Panel(f"Port lanes: {density}", "end", lo, hi, scale,
               note=f"{len(TL.lanes(density))} lanes; red rings = this port's lanes; dashed = lanes a denser tray adds")
    pn.add(-99, lambda: (pn.grid([0.5, 0, 0], [0.5, 0.5, 0.25]), pn.box_outline([0.5, 0, 0], [0.5, 0.5, 0.25])))
    draw_basket(pn, pl.structure[0])
    for sp in pl.supports:
        for a, b in sp.rods:
            pn.add(-1, lambda a=a, b=b: pn.line([a, b], MAT["MetalDull"], w_m=2 * TL.ROD_R))
        for _, fr, size, mat in sp.solids():
            c = fr.corners(size)
            pn.add(-1, lambda c=c, mat=mat: pn.poly(c, fill=MAT.get(mat, DARK) + (255,)))
    for l in TL.LANES:
        q = TL.lane_point(port, l)
        if l in TL.lanes(density):
            pn.add(1, lambda q=q, l=l: draw_cables(pn, q, TL.R_B, MAT[l.material]))
            pn.add(2, lambda q=q: pn.circle(q, TL.R_B, outline=(220, 40, 40), w_px=1.2))
        else:
            pn.add(2, lambda q=q, l=l: pn.circle(q, TL.R_B, outline=DENS_C[l.first], w_px=1.0, dash=True))
        lab = q + np.array([0, 0, TL.R_B + 0.012 if l.h > 0.05 else -TL.R_B - 0.011])
        pn.add(3, lambda lab=lab, l=l: pn.text(lab, l.name, 9, INK if l in TL.lanes(density) else (150, 150, 150),
                                               bold=l in TL.lanes(density)))
    # dimensions
    z_dim = o[2] - 0.026
    for l in TL.LANES:
        if l.s >= 0 and l.h < 0.05:
            q = TL.lane_point(port, l)
            pn.add(4, lambda q=q, l=l: pn.text(np.array([0.5, q[1], o[2] - 0.075]), f"{l.s:+.3f}", 8,
                                               (90, 92, 96)))
    pn.add(4, lambda: (pn.text(np.array([0.5, o[1] + TL.WALL_S, o[2] + TL.WALL_H + 0.022]),
                               f"wall s=±{TL.WALL_S}, top wire h={TL.WALL_H}", 8, (90, 92, 96)),
                       pn.text(np.array([0.5, o[1] - DM.ROD_S + 0.012, o[2] + 0.17]), f"rod s=±{DM.ROD_S}", 8,
                               (90, 92, 96), anchor="lm"),
                       pn.text(np.array([0.5, 0.02, o[2]]), f"floor top\nz={TL.FLOOR_Z}", 8, (90, 92, 96),
                               anchor="lm"),
                       pn.dashed([0.5, 0.0, o[2]], [0.5, 0.5, o[2]], (150, 150, 150)),
                       pn.text(np.array([0.5, o[1], -0.022]), "grid planes (0.25 m) = cell box of the port face", 8,
                               (120, 122, 126))))
    return pn.finish()


def nesting_panel(scale=1500):
    pl = P.plan("StraightS", "Full")
    port = pl.ports["b"]
    pn = Panel("Density nesting", "end", np.array([0.5, -0.03, 0.0]), np.array([0.5, 0.53, 0.2]), scale,
               note="ring colour = the density that adds the lane: Low (blue) < Moderate (green) < Full (red)")
    draw_basket(pn, pl.structure[0])
    for l in TL.LANES:
        q = TL.lane_point(port, l)
        pn.add(1, lambda q=q, l=l: draw_cables(pn, q, TL.R_B, MAT[l.material]))
        pn.add(2, lambda q=q, l=l: pn.circle(q, TL.R_B + 0.002, outline=DENS_C[l.first], w_px=2.2))
        pn.add(3, lambda q=q, l=l: pn.text(q + np.array([0, 0, -TL.R_B - 0.012 if l.h < 0.05 else TL.R_B + 0.012]),
                                           f"{l.name} {l.first[0]}", 9, DENS_C[l.first], bold=True))
    return pn.finish()


def piece_sheet(pl, title):
    size = pl.size
    pad = np.array([0.08, 0.08, 0.08])
    lo, hi = -pad, size + pad
    sc = 600 if size[0] <= 1.0 else 420
    if pl.shape == "Chute":
        sc = 300
    if pl.shape == "Rods":
        sc = 300 if size[2] > 0.3 else 600
    views = []
    for v, t in (("top", "top (from +z)"), ("side", "side (from -y)"), ("end", "end (from +x)")):
        pn = Panel(t, v, lo, hi, sc)
        draw_plan(pn, pl)
        views.append(pn.finish())
    row = [vstack(views[:2]), views[2]]
    for name, port in pl.ports.items():
        o = np.asarray(port.o)
        k = int(np.argmax(np.abs(port.t)))
        _, _, ps, pu = port.frame()
        span = np.array([o + 0.3 * ps, o - 0.3 * ps, o - 0.08 * pu, o + 0.25 * pu])     # 0.6 across, -0.08 .. 0.25 up
        flo, fhi = span.min(axis=0), span.max(axis=0)
        flo[k] = fhi[k] = o[k]
        pn = Panel(f"port {name}: {port.density}", (ps, pu), flo, fhi, 900,
                   note="seen from outside; rings = the contract lanes; cables = the plan's PORT ends")
        glo, ghi = np.zeros(3), size.copy()
        glo[k] = ghi[k] = o[k]
        pn.add(-99, lambda pn=pn, glo=glo, ghi=ghi: (pn.grid(glo, ghi), pn.box_outline(glo, ghi)))
        wh = max((q.wall_h for q in pl.structure if q.kind == "basket"), default=TL.WALL_H)
        draw_profile(pn, o, ps, pu, wh)
        for b in pl.bundles:
            for i, e in enumerate(b.ends):
                if e.kind == "PORT" and e.ref.startswith(name + ":"):
                    q = b.end_point(i)
                    pn.add(1, lambda q=q, b=b: draw_cables(pn, q, b.radius, MAT[b.material]))
        draw_port(pn, port)
        row.append(pn.finish())
    n_b = len(pl.bundles)
    kinds = sorted({f.kind for f in pl.fittings})
    sub = (f"{pl.cells} cells; {n_b} bundles; fittings: {', '.join(kinds) or 'none'}; supports: "
           f"{', '.join(s.kind for s in pl.supports)}; occupied cells {len(P.occupied_cells(pl))}")
    return titled(hstack(row), title, sub)


def chain(pieces):
    placed = [pieces[0]]
    for nxt in pieces[1:]:
        placed.append(nxt.transformed(P.place(nxt, "a", placed[-1].ports["b"])))
    return placed


def run_panels(placed, title, views=("top", "side"), scale=420, marks=True):
    lo = np.min([np.zeros(3)] + [p.ports["a"].o - np.array([0, 0.25, 0.545 if p.shape == "Drop" else 0.045])
                                 for p in placed], axis=0) - 0.08
    hi = np.max([p.ports["b"].o + np.array([0, 0.5, 0.25]) for p in placed], axis=0) + 0.08
    lo[2] = min(lo[2], -0.08)
    out = []
    for v in views:
        pn = Panel(f"{title}: {v}", v, lo, hi, scale)
        for pl in placed:
            corner = pl.ports["a"].o - np.array([0.0, P.Y_C, pl.ports["a"].o[2] - (0.5 if pl.shape == "Drop"
                                                                                      else 0.0) - TL.FLOOR_Z])
            corner[2] = 0.0 if pl.shape != "Drop" else corner[2]
            draw_plan(pn, pl, grid=True, ports=False, offset_box=(corner, corner + pl.size))
        if marks:
            for pl in placed[1:]:
                o = pl.ports["a"].o
                pn.add(100, lambda o=o: pn.dashed(o + np.array([0, -0.3, -0.06]), o + np.array([0, 0.3, 0.3]),
                                                  (220, 40, 40), 1.4))
        out.append(pn.finish())
    return out


def rack_box(pn, x0, h, label, entries):
    """A stand-in rack (1.0 x 1.25, h tall, on z = 0) with its front top entries."""
    lo, hi = np.array([x0 - 0.5, -0.625, 0.0]), np.array([x0 + 0.5, 0.625, h])
    c = [np.array([x, y, z]) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    pn.add(-50, lambda: (pn.poly(c, fill=(60, 64, 72, 40), outline=(60, 64, 72), w_px=1.4),
                         pn.text(np.array([x0, 0.0, h / 2]), label, 12, (60, 64, 72), bold=True)))
    (xa, xb), (ya, yb) = entries
    for k in (-1, 1):
        q = [np.array([x0 + k * xx, yy, h]) for xx in (xa, xb) for yy in (ya, yb)]
        q += [p - np.array([0, 0, 0.004]) for p in q]
        pn.add(-49, lambda q=q: pn.poly(q, fill=ENTRYC + (160,), outline=ENTRYC, w_px=1.2))


def drop_over_rack():
    full_h = 0.25 * catalog.BY_NAME["DC_Rack42_Open"].cells[1]
    drop = P.plan("Drop", "Full")
    T = P.Transform(np.eye(3), np.array([-0.5, DM.TRAY_RACK_Y - P.Y_C, full_h]))
    w = drop.transformed(T)
    lo, hi = np.array([-0.62, -0.7, full_h - 0.35]), np.array([0.62, 0.7, full_h + 0.85])
    ims = []
    for v, t in (("front", "front (from +y, the rack's front)"), ("end", "side (from +x)"), ("top", "top")):
        pn = Panel(t, v, lo, hi, 520)
        rack_box(pn, 0.0, full_h, "DC_Rack42 (stand-in)", DM.TOP_ENTRY)
        draw_plan(pn, w, grid=True, ports=False, offset_box=(T(np.zeros(3)), T(drop.size)))
        if v != "top":
            z = full_h
            pn.add(100, lambda pn=pn: pn.text(np.array([0.0, 0.0, full_h + DM.TRAY_HANG / 2]),
                                              f"TRAY_HANG {DM.TRAY_HANG}", 9, (200, 30, 30)))
        ims.append(pn.finish())
    # the landing, close up: top view of each entry with the bundle footprint and its margins
    close = []
    for k in (-1, 1):
        x0, x1 = sorted(k * np.array(DM.TOP_ENTRY[0]))
        y0, y1 = DM.TOP_ENTRY[1]
        pn = Panel(f"landing {'-' if k < 0 else '+'}x (top)", "top", np.array([x0 - 0.03, y0 - 0.03, 0]),
                   np.array([x1 + 0.03, y1 + 0.03, 0]), 2200)
        q = [np.array([x, y, full_h]) for x in (x0, x1) for y in (y0, y1)]
        pn.add(0, lambda pn=pn, q=q: pn.poly(q, fill=ENTRYC + (70,), outline=ENTRYC, w_px=1.6))
        wf = next(b for b in w.bundles if b.lane.startswith("WF") and np.sign(b.end_point(1)[0]) == k)
        p = wf.end_point(1)
        m = min(p[0] - x0, x1 - p[0], p[1] - y0, y1 - p[1]) - TL.R_WF
        pn.add(1, lambda pn=pn, p=p: draw_cables(pn, p, TL.R_WF, MAT["PaintedMetalColorable"]))
        pn.add(2, lambda pn=pn, p=p, m=m: pn.text(p + np.array([0, -0.045, 0]),
                                                  f"({p[0]:+.4f}, {p[1]:.4f})  clear {m * 1000:.1f} mm", 9, INK))
        close.append(pn.finish())
    return titled(hstack([vstack(ims[:2]), vstack([ims[2]] + close)]), "Drop (Full) over a full rack",
                  "bottom plane on the rack top; tray centreline at rack y = TRAY_RACK_Y; waterfalls land on "
                  "(±WF_X, WF_Y) in the brush-plate openings (orange)")


def drop_chute_half_rack():
    full_h = 0.25 * catalog.BY_NAME["DC_Rack42_Open"].cells[1]
    half_h = 0.25 * catalog.BY_NAME["DC_Rack24_Open"].cells[1]
    d1, d2, ch = P.plan("Drop", "Moderate"), P.plan("Drop", "Moderate"), P.plan("Chute")
    T1 = P.Transform(np.eye(3), np.array([-0.5, DM.TRAY_RACK_Y - P.Y_C, full_h]))
    T2 = P.place(d2, "a", d1.transformed(T1).ports["b"])
    Tc = T2 @ P.Transform(np.eye(3), np.array([0.0, 2 * TL.CELL, -ch.size[2]]))
    lo, hi = np.array([-0.62, -0.7, -0.05]), np.array([1.62, 0.7, full_h + 0.85])
    ims = []
    for v, t in (("front", "front (from +y)"), ("end", "side (from +x)")):
        pn = Panel(t, v, lo, hi, 300)
        rack_box(pn, 0.0, full_h, "42U", DM.TOP_ENTRY)
        rack_box(pn, 1.0, half_h, "24U", DM.HALF_TOP_ENTRY)
        for pl, T in ((d1, T1), (d2, T2), (ch, Tc)):
            draw_plan(pn, pl.transformed(T), grid=True, ports=False, offset_box=(T(np.zeros(3)), T(pl.size)))
        ims.append(pn.finish())
    return titled(hstack(ims), "Drop + Chute over a half rack (row pitch 1.0 m)",
                  "the Chute stands in the second Drop's waterfall column and lands 1.25 m lower on the 24U's "
                  "roof entries")


# ---------------------------------------------------------------------------------------------------- Task 3 sheets
from dc import tray_bends as TB  # noqa: E402


def place_steps(steps):
    """[(plan, in port, previous index, previous out port)] -> [(placed plan, its box lo, hi)]."""
    out = []
    for pl, pin, k, pout in steps:
        T = P.Transform.identity() if k is None else P.place(pl, pin, out[k][0].ports[pout])
        c = np.array([T(np.array([x, y, z])) for x in (0, pl.size[0]) for y in (0, pl.size[1])
                      for z in (0, pl.size[2])])
        out.append((pl.transformed(T), c.min(axis=0), c.max(axis=0)))
    return out


def scene_panel(placed, title, view, scale, pad=0.08, note=None, joints=True, extra=None):
    lo = np.min([q[1] for q in placed], axis=0) - pad
    hi = np.max([q[2] for q in placed], axis=0) + pad
    pn = Panel(title, view, lo, hi, scale, note=note)
    for pl, blo, bhi in placed:
        draw_plan(pn, pl, grid=True, ports=False, offset_box=(blo, bhi))
    if joints:
        seen = []
        for pl, *_ in placed:
            for port in pl.ports.values():
                o = np.asarray(port.o)
                if any(np.linalg.norm(o - q) < 1e-6 for q in seen):
                    _, _, ps, pu = port.frame()
                    pn.add(100, lambda o=o, ps=ps, pu=pu: pn.dashed(o - 0.27 * ps - 0.05 * pu, o + 0.27 * ps + 0.25 * pu,
                                                                    (220, 40, 40), 1.4))
                seen.append(o)
    if extra:
        extra(pn)
    return pn.finish()


def bend_strap_radials(pn, pl):
    """Dashed radial lines from a (placed) bend's arc centre through each of its strap stations."""
    straps = [f for f in pl.fittings if f.kind == "strap"]
    c = np.asarray(straps[0].params["centre"], float)
    for st in sorted({round(f.params["station"], 9) for f in straps}):
        here = [f.frame.o for f in straps if abs(f.params["station"] - st) < 1e-9]
        q = max(here, key=lambda o: np.linalg.norm(o - c))
        e = (q - c) / np.linalg.norm(q - c)
        pn.add(98, lambda q=q, e=e: pn.dashed(c, q + 0.06 * e, (200, 40, 160), 1.2, 0.01))
        pn.add(98, lambda q=q, e=e, st=st: pn.text(q + 0.085 * e, f"{st:.3f}", 8, (200, 40, 160)))
    pn.add(98, lambda: pn.circle(c, 0.006, fill=(200, 40, 160)))


def strap_sheet():
    ims = []
    for shape, view in (("TurnH", "top"), ("TurnUp", "side"), ("TurnDown", "side")):
        pl = P.plan(shape, "Full")
        L = TB.bend_sweep(shape).length
        st = TB.radial_stations(L)
        pn = Panel(f"{shape} (Full): straps on radials", view, -np.full(3, 0.06), pl.size + 0.06, 760,
                   note=f"centreline {L:.3f} m; stations {', '.join(f'{x:.3f}' for x in st)}; "
                        f"pitch {st[1] - st[0]:.3f} m")
        draw_plan(pn, pl)
        bend_strap_radials(pn, pl)
        ims.append(pn.finish())
    # the rhythm carried across joints: StraightS -> TurnH -> StraightS
    placed = place_steps([(P.plan("StraightS", "Full"), "a", None, None), (P.plan("TurnH", "Full"), "a", 0, "b"),
                          (P.plan("StraightS", "Full"), "a", 1, "b")])
    run = scene_panel(placed, "StraightS -> TurnH -> StraightS: the strap rhythm across the joints", "top", 520,
                      note="0.125 m from every port on both sides of a joint: 0.25 m across each joint (red dashes)",
                      extra=lambda pn: bend_strap_radials(pn, placed[1][0]))
    return titled(vstack([hstack(ims), run]), "Radial strap rhythm (Decision 13)",
                  "bends: straps on radial lines through the arc centre, 0.125 m of centreline from each port, "
                  "evenly spaced at the pitch nearest 0.25 m")


def junction_run(d):
    s = lambda n: P.plan(n, d)
    return place_steps([(s("StraightS"), "a", None, None), (s("Tee"), "a", 0, "b"), (s("TurnH"), "a", 1, "c"),
                        (s("Cross"), "a", 2, "b"), (s("StraightL"), "a", 3, "b")])


def junction_run_sheet():
    rows = []
    for d in TL.DENSITIES:
        placed = junction_run(d)
        rows.append(hstack([scene_panel(placed, f"{d}: top", "top", 300),
                            scene_panel(placed, f"{d}: side (from -y)", "side", 300)]))
    return titled(vstack(rows), "Junction run: StraightS -> Tee (out of its branch) -> TurnH -> Cross -> StraightL",
                  "every density; joints dashed red: every bundle continues lane for lane")


def junction_run_full():
    placed = junction_run("Full")
    big = scene_panel(placed, "Full: top", "top", 520)
    close = []
    for k in (1, 2, 3, 4):      # every joint, close up from above
        o = np.asarray(placed[k][0].ports["a"].o)
        lo, hi = o - 0.3, o + 0.3
        pn = Panel(f"joint {k}: {placed[k - 1][0].shape} -> {placed[k][0].shape}", "top", lo, hi, 900)
        for pl, blo, bhi in placed:
            draw_plan(pn, pl, grid=True, ports=False, offset_box=(blo, bhi))
        close.append(pn.finish().crop((0, 0, int(0.6 * 900 + 2 * 46), int(0.6 * 900 + 2 * 46 + 34))))
    return titled(vstack([big, hstack(close)]), "Junction run at Full, with every joint close up", None)


def junction_detail_sheet():
    tee, cross = P.plan("Tee", "Full"), P.plan("Cross", "Full")
    ims = []
    pn = Panel("Tee (Full): top", "top", -np.full(3, 0.04), tee.size + 0.04, 820,
               note="branch-side lanes turn in from both ports, concentric with the r 0.15 fillets; M0 splits at a "
                    "collar (x 0.11-0.14)")
    draw_plan(pn, tee)
    pn.add(99, lambda: pn.text(np.array([0.125, 0.18, 0.2]), "split collar", 10, (200, 30, 30), bold=True))
    ims.append(pn.finish())
    pn = Panel("Cross (Full): top", "top", -np.full(3, 0.04), cross.size + 0.04, 620,
               note="c-d stack rides the crossover saddle (deck 0.095, Brushed legs in the corners)")
    draw_plan(pn, cross)
    ims.append(pn.finish())
    pn = Panel("Cross (Full): side (from -x), along c-d", ((0, -1, 0), (0, 0, 1)), -np.full(3, 0.04),
               cross.size + 0.04, 620, note="ramps <= 30 deg, level 5 cm at each port; the bottom layer rests on "
                                             "the deck over the a-b stack")
    draw_plan(pn, cross)
    ims.append(pn.finish())
    return titled(vstack([hstack(ims[:2]), ims[2]]), "Tee and Cross: split collar, turning groups, crossover saddle",
                  None)


def offset_sheet():
    rows = []
    for d in ("Full", "Low"):
        s = lambda n: P.plan(n, d)
        placed = place_steps([(s("StraightS"), "a", None, None), (s("TurnUp"), "a", 0, "b"),
                              (s("StraightS"), "a", 1, "b"), (s("StraightS"), "a", 2, "b"),
                              (s("TurnDown"), "a", 3, "b"), (s("StraightS"), "a", 4, "b")])
        rise = placed[-1][0].ports["b"].o[2] - placed[0][0].ports["a"].o[2]
        rows.append(scene_panel(placed, f"{d}: side (from -y), 0.25 m grid", "side", 420,
                                note=f"StraightS, TurnUp, 2 x StraightS riser, TurnDown, StraightS: up {rise:.3f} m, "
                                     "every box on the grid"))
    return titled(hstack(rows), "Vertical offset: an up / down turn pair", None)


def main_t3(out):
    os.makedirs(out, exist_ok=True)
    written = []

    def save(im, name):
        path = os.path.join(out, name)
        im.save(path, optimize=True)
        written.append(path)

    for b in catalog.CATALOGUE:
        if b.family == "tray" and b.variant in P.BENDS:
            save(piece_sheet(P.plan(b), b.name), f"10_{b.name}.png")
    save(strap_sheet(), "20_strap_radials.png")
    save(junction_detail_sheet(), "30_tee_cross_detail.png")
    save(junction_run_sheet(), "31_junction_run_densities.png")
    save(junction_run_full(), "32_junction_run_full.png")
    save(offset_sheet(), "40_offset_up_down.png")
    contact(written, save)
    print(f"wrote {len(written)} images to {out}")


def contact(written, save):
    ims = [Image.open(p) for p in written]
    thumbs = []
    for im, p in zip(ims, written):
        im = im.copy()
        im.thumbnail((520, 360), Image.LANCZOS)
        cell = Image.new("RGB", (530, 390), (255, 255, 255))
        cell.paste(im, ((530 - im.width) // 2, 24))
        ImageDraw.Draw(cell).text((6, 4), os.path.basename(p), fill=INK, font=ImageFont.truetype(FONT, 12))
        thumbs.append(cell)
    cols_n = 5
    rows = [hstack(thumbs[i:i + cols_n], 4, (230, 230, 230)) for i in range(0, len(thumbs), cols_n)]
    save(vstack(rows, 4, (230, 230, 230)), "contact.png")


def main(argv):
    task = argv[argv.index("--task") + 1] if "--task" in argv else "2"
    out = os.path.join(config.PREVIEW_DIR, f"p2-task-{task}")
    if "--out" in argv:
        out = os.path.abspath(argv[argv.index("--out") + 1])
    if task == "3":
        return main_t3(out)
    os.makedirs(out, exist_ok=True)
    written = []

    def save(im, name):
        path = os.path.join(out, name)
        im.save(path, optimize=True)
        written.append(path)

    ladder = []
    for d in TL.DENSITIES:
        im = lanes_panel(d)
        save(im, f"01_lanes_{d}.png")
        ladder.append(im)
    save(titled(hstack([lanes_panel(d, 900) for d in TL.DENSITIES]), "Port lanes, Empty -> Full",
                "end-on at a port (s to the right, h up); each density adds lanes to the one below"), "01_lanes_ladder.png")
    save(nesting_panel(), "02_nesting.png")
    for b in catalog.CATALOGUE:
        if b.family in ("tray", "trayrods") and b.variant not in P.BENDS:     # the Task 2 set
            save(piece_sheet(P.plan(b), b.name), f"10_{b.name}.png")
    # the density ladder: StraightS at each density, top + end
    cols = []
    for d in TL.DENSITIES:
        pl = P.plan("StraightS", d)
        pa = Panel(f"StraightS {d}: top", "top", np.array([-0.05, -0.05, 0]), np.array([0.55, 0.55, 0.25]), 520)
        draw_plan(pa, pl, ports=False)
        pb = Panel("end", "end", np.array([0.5, -0.05, -0.05]), np.array([0.5, 0.55, 0.3]), 520)
        draw_plan(pb, pl, ports=False)
        cols.append(vstack([pa.finish(), pb.finish()]))
    save(titled(hstack(cols), "Density ladder (StraightS)", "Empty / Low / Moderate / Full"), "20_density_ladder.png")
    # mixed joint: Full meets Low without a reducer
    pl = chain([P.plan("StraightS", "Full"), P.plan("StraightL", "Low")])
    save(titled(vstack(run_panels(pl, "StraightS Full -> StraightL Low", ("top", "side"), 520)),
                "Mixed-density joint (no reducer)",
                "the Low lanes run straight on; only the extra Full lanes end at the joint (red dashes)"),
         "21_mixed_joint.png")
    pl = chain([P.plan("Reducer", d) for d in ("Full", "Moderate", "Low")] + [P.plan("StraightS", "Empty")])
    save(titled(vstack(run_panels(pl, "Reducer chain", ("top", "side"), 520)), "Reducer chain Full -> Moderate -> "
                "Low -> Empty", "each Reducer boots its dropped lanes (rubber boots, saddle clamps, yellow tags)"),
         "22_reducer_chain.png")
    pl = chain([P.plan("StraightS", "Full"), P.plan("StraightL", "Full"), P.plan("Drop", "Full"),
                P.plan("Reducer", "Full")])
    save(titled(vstack(run_panels(pl, "Run", ("top", "side"), 330)), "Strap rhythm across joints",
                "StraightS + StraightL + Drop + Reducer: straps every 0.25 m from 0.125, joints dashed red"),
         "23_run_rhythm.png")
    save(drop_over_rack(), "30_drop_over_rack.png")
    save(drop_chute_half_rack(), "31_drop_chute_half_rack.png")
    # contact sheet
    ims = [Image.open(p) for p in written]
    thumbs = []
    for im, p in zip(ims, written):
        im = im.copy()
        im.thumbnail((520, 360), Image.LANCZOS)
        cell = Image.new("RGB", (530, 390), (255, 255, 255))
        cell.paste(im, ((530 - im.width) // 2, 24))
        ImageDraw.Draw(cell).text((6, 4), os.path.basename(p), fill=INK, font=ImageFont.truetype(FONT, 12))
        thumbs.append(cell)
    cols_n = 5
    rows = [hstack(thumbs[i:i + cols_n], 4, (230, 230, 230)) for i in range(0, len(thumbs), cols_n)]
    save(vstack(rows, 4, (230, 230, 230)), "contact.png")
    print(f"wrote {len(written)} images to {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
