"""Decorative servers (no function, visual density): compute, storage, switch, blank. 6U (2x1x3 cells).

v2 SE design language (design doc, "Deco blades need refactoring"): the player's paint on every bezel and caddy
face, chunky clipped corners, real shadow gaps between modules, white Keen stencils on Darker label plates, fewer and
larger status lenses. Detail vocabulary: docs/ideas/reference/datacenter/servers/README.md.

Every face builds inside server.face_frame(spec): F.area is the bezel opening (a to the viewer's right, b up), F.floor
the Darker recess floor (d = -0.015), F.top the bezel frame's front (d = +0.008). Modules stand on the floor and
stay just below the frame front, so the frame reads as a border round a recessed panel (Keen panel layout).

| part                         | purpose                                                                    |
| drive caddy (storage/compute)| hot-swap disk carrier: hex vent (air over the drive), lever + Yellow release button, activity lamp |
| honeycomb intake / bezel     | front-to-back cooling air path into the fans (Darker tub behind)           |
| hinged intake door (compute) | swings down for memory / fan service: quarter-turn latch, hinge knuckles   |
| control module               | power button with lit ring, unit-ID locator button, health lamp, ID stencil|
| port field (switch)          | 24 copper ports in 2 groups (contact strips inside), one link lamp each    |
| SFP uplinks, console, mgmt   | switch uplink cages and out-of-band management                             |
| fan tray (switch)            | hot-swap fan module: louvred intake, thumbscrew, pull lip, fan-OK lamp     |
| blank label strip            | slot size stencil + a locator lamp (slot reserved)                         |
"""
import math

from .. import server
from ..style import DARK, HARDWARE, LAMP_GREEN, PAINT, STEEL, YELLOW, lamp, louvre_panel, oct_pts, stencil
from se2model.config import EM

try:
    from se2model import geom as G
    from se2model.geom import Part
except ImportError:
    G = Part = None

LAMP_OFF = EM   # EmissiveOff: an unlit lens (vanilla library material)
GAP = 0.005     # shadow gap between modules


# ---------------------------------------------------------------------------------------------------- helpers

def _grille(P):
    """The perforated-plate Part (no bevel: keeps the honeycomb webs crisp and cheap), created on first use."""
    if "grille" not in P:
        P["grille"] = Part("grille")
    return P["grille"]


def hex_holes(a0, a1, b0, b1, r, web):
    """Pointy-top hexagon holes (circumradius r, web between holes) filling [a0,a1] x [b0,b1], staggered rows,
    the pattern centred in the field."""
    s3 = math.sqrt(3.0)
    dx, dy = s3 * r + web, 1.5 * r + web * 0.866
    n = max(1, int((a1 - a0 - s3 * r) / dx) + 1)
    rows = max(1, int((b1 - b0 - 2 * r) / dy) + 1)
    bs = (b0 + b1) / 2 - (rows - 1) * dy / 2
    out = []
    for j in range(rows):
        m = n if j % 2 == 0 else n - 1
        if m <= 0:
            continue
        as_ = (a0 + a1) / 2 - (m - 1) * dx / 2
        for i in range(m):
            ac, bc = as_ + i * dx, bs + j * dy
            out.append([(ac + x, bc + y) for x, y in G.ngon(r, 6, math.pi / 2)])
    return out


def honeycomb(P, F, a0, a1, b0, b1, d0, d1, r, lod, web=None, chamfer=0.0):
    """A painted perforated plate (Keen: cut in, don't add): hex holes through it show the Darker tub behind.
    LOD1 uses holes ~2x larger (a third of the count); LOD2 a plain Darker slab."""
    outer = oct_pts(a0, b0, a1, b1, chamfer) if chamfer else G.rect(a0, a1, b0, b1)
    if lod >= 2:
        G.prism(P["dark"], F, outer, d0, d1 - 0.004, DARK)
        return
    if lod == 1:
        r *= 2.0
    web = web or max(0.004, 0.42 * r)
    m = r * 0.6 + 0.004
    holes = hex_holes(a0 + m, a1 - m, b0 + m, b1 - m, r, web)
    G.plate(_grille(P), F, outer, holes, d0, d1, PAINT, bottom=False)


def led(P, F, a, b, d, lit, lod, r=0.006, mat=None):
    """Status lamp: lit = EmissiveGreen, unlit = EmissiveOff (mat overrides both, e.g. a functional server's
    indicator mesh part). LOD0 a round lens in a Darker bezel, LOD1 a square lens, LOD2 nothing."""
    server._led(P, F, a, b, d, mat or (LAMP_GREEN if lit else LAMP_OFF), lod, r=r)


def label(P, F, a0, a1, b0, b1, d, text, cap, lod, align="center", pad=0.006):
    """A Darker label plate with a white stencil (reads on any paint)."""
    G.prism(P["dark"], F, oct_pts(a0, b0, a1, b1, min(0.004, (b1 - b0) / 4)), d, d + 0.003, DARK)
    if lod <= 1 and text:
        bc = (b0 + b1) / 2
        if align == "center":
            stencil(P["decal"], F, (a0 + a1) / 2, bc, cap, text, d=d + 0.003)
        else:
            stencil(P["decal"], F, a0 + pad, bc, cap, text, d=d + 0.003, align="left")


def power_button(P, F, a, b, d, lod, r=0.010, ring=LAMP_GREEN):
    """Power button: a Colorable cap inside a lit ring (LOD0; ring = EmissiveGreen, or a functional server's
    indicator part), a lens of the ring material below LOD0."""
    if lod >= 2:
        return
    if lod == 1:
        led(P, F, a, b, d, True, 1, r=r * 0.7, mat=ring)
        return
    G.cylinder(P["hw"], F(a, b, d - 0.001), F(a, b, d + 0.004), r + 0.004, 16, DARK)        # bezel
    G.cylinder(P["hw"], F(a, b, d + 0.004), F(a, b, d + 0.0055), r, 16, ring)                # lit ring
    G.cylinder(P["frame"], F(a, b, d + 0.0055), F(a, b, d + 0.009), r * 0.72, 16, PAINT)     # the button cap


def caddy(P, F, a0, a1, b0, b1, d, lod, lit, vertical=False, lamp=None):
    """Hot-swap drive caddy: Darker carrier; a painted face with a hex vent (air over the drive); a Darker lever
    with a Yellow release button; an activity lamp. Horizontal = 3.5" (lever on the right), vertical = 2.5" SFF
    (lever at the bottom)."""
    w, h = a1 - a0, b1 - b0
    if lod >= 2:
        return
    G.prism(P["dark"], F, oct_pts(a0, b0, a1, b1, 0.004 if lod == 0 else 0.0), d, d + 0.006, DARK)   # carrier
    if vertical:
        vent = (a0 + 0.004, a1 - 0.004, b0 + 0.36 * h, b1 - 0.004)
        lever = (a0 + 0.004, a1 - 0.004, b0 + 0.005, b0 + 0.33 * h)
        btn = (a1 - 0.013, lever[2] + 0.004, a1 - 0.006, lever[3] - 0.004)
        lamp_at = (a0 + 0.010, b0 + 0.33 * h - 0.012)
    else:
        vent = (a0 + 0.004, a0 + 0.62 * w, b0 + 0.005, b1 - 0.005)
        lever = (a0 + 0.62 * w + 0.003, a1 - 0.004, b0 + 0.006, b1 - 0.006)
        btn = (lever[0] + 0.004, lever[3] - 0.014, lever[1] - 0.004, lever[3] - 0.004)
        lamp_at = ((lever[0] + lever[1]) / 2, b0 + 0.014)
    va0, va1, vb0, vb1 = vent
    if lod == 0:
        r = min(va1 - va0, vb1 - vb0) / 8.5
        holes = hex_holes(va0 + 0.005, va1 - 0.005, vb0 + 0.005, vb1 - 0.005, r, 0.0035)
        G.plate(_grille(P), F, G.rect(va0, va1, vb0, vb1), holes, d + 0.006, d + 0.010, PAINT, bottom=False)
    else:
        G.prism(P["frame"], F, G.rect(va0, va1, vb0, vb1), d + 0.006, d + 0.010, PAINT)
    G.prism(P["dark"], F, oct_pts(lever[0], lever[2], lever[1], lever[3], 0.003 if lod == 0 else 0.0), d + 0.006,
            d + 0.013, DARK)
    G.prism(P["fine"], F, G.rect(btn[0], btn[2], btn[1], btn[3]), d + 0.013, d + 0.016, YELLOW)
    led(P, F, lamp_at[0], lamp_at[1], d + 0.013 if not vertical else d + 0.010, lit, lod, r=0.0042, mat=lamp)


def _lit(i, j=0):
    return (i * 7 + j * 3) % 5 != 0


# ---------------------------------------------------------------------------------------------------- faces

def face_storage(spec, P, lod):
    """Storage array (visual pass 2): a RAID controller column at the left (two hot-swap controller canisters:
    ejector lever with a Yellow tip, two host ports, health + activity lamps, C1 / C2), then the drive wall of
    3 rows x 3 large 3.5" caddies (R720xd / P6300 style), and the control strip at the right."""
    F = server.face_frame(spec)
    a0, a1, b0, b1 = F.area
    fl = F.floor
    cs = 0.050                    # control strip width (right)
    cc = 0.082                    # controller column width (left)
    ca0 = a0 + cc + GAP
    ca1 = a1 - cs - GAP
    if lod >= 2:
        for k in range(3):
            bb0 = b0 + k * (b1 - b0) / 3
            G.prism(P["dark"], F, G.rect(ca0, ca1, bb0 + 0.004, bb0 + (b1 - b0) / 3 - 0.004), fl, fl + 0.008, DARK)
        G.prism(P["dark"], F, G.rect(ca1 + GAP, a1, b0, b1), fl, fl + 0.006, DARK)
        G.prism(P["frame"], F, G.rect(a0, a0 + cc, b0, b1), fl, fl + 0.010, PAINT)
        return
    cols, rows = 3, 3
    w = (ca1 - ca0 - (cols - 1) * GAP) / cols
    h = (b1 - b0 - (rows - 1) * GAP) / rows
    for j in range(rows):
        for i in range(cols):
            x0 = ca0 + i * (w + GAP)
            y0 = b1 - (j + 1) * h - j * GAP
            caddy(P, F, x0, x0 + w, y0, y0 + h, fl, lod, _lit(i, j))
    # controller canisters
    hh = (b1 - b0 - GAP) / 2
    for k in range(2):
        cb0 = b0 + k * (hh + GAP)
        cb1 = cb0 + hh
        G.prism(P["frame"], F, oct_pts(a0, cb0, a0 + cc, cb1, 0.006), fl, fl + 0.010, PAINT)          # canister face
        G.prism(P["dark"], F, oct_pts(a0 + 0.008, cb0 + 0.010, a0 + cc - 0.008, cb0 + 0.040, 0.004), fl + 0.010,
                fl + 0.013, DARK)                                                                     # port plate
        for pa in (a0 + 0.024, a0 + 0.050):
            G.prism(P["hw"], F, G.rect(pa - 0.010, pa + 0.010, cb0 + 0.016, cb0 + 0.034), fl + 0.013, fl + 0.017,
                    STEEL)
            if lod == 0:
                G.prism(P["fine"], F, G.rect(pa - 0.0075, pa + 0.0075, cb0 + 0.019, cb0 + 0.031), fl + 0.017,
                        fl + 0.0173, DARK)
        # ejector lever: a Brushed bar across the canister top, Yellow release tip
        G.prism(P["hw"], F, oct_pts(a0 + 0.008, cb1 - 0.020, a0 + cc - 0.020, cb1 - 0.010, 0.003), fl + 0.010,
                fl + 0.020, STEEL)
        G.prism(P["fine"], F, oct_pts(a0 + cc - 0.020, cb1 - 0.021, a0 + cc - 0.008, cb1 - 0.009, 0.003),
                fl + 0.010, fl + 0.021, YELLOW)
        led(P, F, a0 + 0.016, cb1 - 0.036, fl + 0.010, True, lod, r=0.0042)
        led(P, F, a0 + 0.032, cb1 - 0.036, fl + 0.010, k == 0, lod, r=0.0042)
        if lod <= 1:
            stencil(P["decal"], F, a0 + cc - 0.020, cb1 - 0.036, 0.012, f"C{k + 1}", d=fl + 0.010)
    # control strip: Darker plate, ID stencil, power button, unit ID + fault lamps
    sa0, sa1 = ca1 + GAP, a1
    G.prism(P["dark"], F, oct_pts(sa0, b0, sa1, b1, 0.005), fl, fl + 0.008, DARK)
    sc = (sa0 + sa1) / 2
    if lod <= 1:
        stencil(P["decal"], F, sc, b1 - 0.017, 0.016, "ST", d=fl + 0.008)
        stencil(P["decal"], F, sc, b1 - 0.038, 0.016, "09", d=fl + 0.008)
    power_button(P, F, sc, b0 + 0.028, fl + 0.008, lod)
    led(P, F, sc, b0 + 0.066, fl + 0.008, False, lod, r=0.0065)       # unit-ID locator (off)
    led(P, F, sc, b0 + 0.092, fl + 0.008, True, lod, r=0.0065)        # health


def fan_module(P, F, ac, bc, R, d, lod, lit, label=None):
    """One front intake fan behind a cut-in round opening (the opening itself is the caller's plate hole): a Darker
    shroud ring, a MetalDull wire finger guard (two rings + four spokes) on a hub disc, the rotor blades seen
    through the guard, a fan-OK lamp and an "F<n>" stencil on the hub. Purpose: GPU / CPU sled cooling, front to
    back (vocabulary: the DGX / DL580 fan walls). LOD1: shroud + one guard ring + hub; LOD2: nothing (plate only)."""
    if lod >= 2:
        return
    n = 16 if lod == 0 else 8
    G.ring(P["fine"], F, G.ngon(R, n), G.ngon(R - 0.006, n), d - 0.021, d - 0.002, DARK, ca=ac, cb=bc)   # shroud
    if lod == 0:   # rotor: 5 swept blades round the motor can
        from mathutils import Matrix
        for k in range(5):
            ang = 2 * math.pi * k / 5 + 0.3
            m = F.matrix(ac, bc, d - 0.014) @ Matrix.Rotation(ang, 4, "Y") @ Matrix.Translation((0.0, 0.0, R * 0.52)) \
                @ Matrix.Rotation(math.radians(28), 4, "Z")
            G.box(P["fine"], (-0.012, -0.0012, -R * 0.36), (0.012, 0.0012, R * 0.36), DARK, m)
    G.cylinder(P["hw"], F(ac, bc, d - 0.016), F(ac, bc, d - 0.004), R * 0.30, 12 if lod == 0 else 6, DARK)  # motor
    rings = ((R - 0.008, 0.0028), (R * 0.62, 0.0024)) if lod == 0 else ()
    for rr, w in rings:   # wire guard rings, flush with the plate front
        G.ring(P["hw"], F, G.ngon(rr + w / 2, n), G.ngon(rr - w / 2, n), d - 0.004, d - 0.001, HARDWARE, ca=ac, cb=bc)
    if lod == 0:
        for k in range(4):   # spokes
            ang = math.pi / 4 + k * math.pi / 2
            ca, sa = math.cos(ang), math.sin(ang)
            r0, r1 = R * 0.30, R - 0.006
            pts = [(ac + ca * r0 - sa * 0.0013, bc + sa * r0 + ca * 0.0013), (ac + ca * r1 - sa * 0.0013, bc + sa * r1 + ca * 0.0013),
                   (ac + ca * r1 + sa * 0.0013, bc + sa * r1 - ca * 0.0013), (ac + ca * r0 + sa * 0.0013, bc + sa * r0 - ca * 0.0013)]
            G.prism(P["hw"], F, pts, d - 0.004, d - 0.0015, HARDWARE)
        G.cylinder(P["hw"], F(ac, bc, d - 0.004), F(ac, bc, d - 0.001), R * 0.26, 12, DARK)    # hub badge
        if label:
            stencil(P["decal"], F, ac, bc, 0.012, label, d=-0.001 + d)
    if lod == 0:
        led(P, F, ac + R * 0.80, bc - R * 0.80, d, lit, lod, r=0.0035)


def face_compute(spec, P, lod):
    """Compute node (GPU-sled style, the DGX "fan wall" / DL580 vocabulary): a top row of six 2.5" SFF caddies and a
    control module, over a full-width hot-swap FAN TRAY: a painted tray plate with three large round cut-outs, each
    a fan behind a wire finger guard (fan_module), a pull handle on each end and quarter-turn release latches. The
    three big circles are the compute node's silhouette cue at rack distance (no other server has round fans)."""
    F = server.face_frame(spec)
    a0, a1, b0, b1 = F.area
    fl = F.floor
    rb0 = b1 - 0.084                  # drive row bottom
    db1 = rb0 - GAP                   # fan tray top
    n = 6
    cw = 0.046
    ra1 = a0 + n * cw + (n - 1) * GAP
    if lod >= 2:
        G.prism(P["dark"], F, G.rect(a0, ra1, rb0, b1), fl, fl + 0.008, DARK)
        G.prism(P["dark"], F, G.rect(ra1 + GAP, a1, rb0, b1), fl, fl + 0.006, DARK)
        G.prism(P["frame"], F, G.rect(a0, a1, b0, db1), fl, fl + 0.010, PAINT)
        bc = (b0 + db1) / 2
        for k in (-1, 0, 1):   # three dark discs: the fans still read at distance
            G.prism(P["dark"], F, G.ngon(0.045, 8), fl + 0.010, fl + 0.011, DARK, ca=k * 0.125, cb=bc)
        return
    for i in range(n):
        x0 = a0 + i * (cw + GAP)
        caddy(P, F, x0, x0 + cw, rb0, b1, fl, lod, _lit(i), vertical=True)
    # control module
    ma0 = ra1 + GAP
    G.prism(P["dark"], F, oct_pts(ma0, rb0, a1, b1, 0.006), fl, fl + 0.008, DARK)
    if lod <= 1:
        stencil(P["decal"], F, (ma0 + a1) / 2, b1 - 0.017, 0.017, "CX-06", d=fl + 0.008)
    power_button(P, F, ma0 + 0.022, rb0 + 0.026, fl + 0.008, lod, r=0.011)
    led(P, F, ma0 + 0.058, rb0 + 0.026, fl + 0.008, False, lod, r=0.0075)     # unit-ID locator
    led(P, F, ma0 + 0.088, rb0 + 0.026, fl + 0.008, True, lod, r=0.0065)      # health
    # fan tray: a painted plate with three round cut-outs (fans behind), stepped end caps with pull handles
    td = fl + 0.022                   # tray plate front (the fans sit in front of the tub face, behind it)
    bc = (b0 + db1) / 2
    R = min(0.054, (db1 - b0) / 2 - 0.007)
    pitch = 0.124
    centres = [k * pitch for k in (-1, 0, 1)]
    nh = 16 if lod == 0 else 8
    holes = [[(c + x, bc + y) for x, y in G.ngon(R, nh)] for c in centres]
    G.plate(P["frame"], F, oct_pts(a0, b0, a1, db1, 0.008), holes, fl, td, PAINT, bottom=False)
    for k, c in enumerate(centres):
        fan_module(P, F, c, bc, R, td, lod, lit=True, label=f"F{k + 1}")
    if lod == 0:
        for sx in (-1, 1):   # end caps: a Darker strip with a quarter-turn latch, the tray's pull lip
            ea = a1 - 0.020 if sx > 0 else a0 + 0.020
            G.prism(P["dark"], F, oct_pts(ea - 0.012, b0 + 0.008, ea + 0.012, db1 - 0.008, 0.004), td, td + 0.004,
                    DARK)
            G.cylinder(P["hw"], F(ea, db1 - 0.026, td + 0.004), F(ea, db1 - 0.026, td + 0.009), 0.0085, 12, HARDWARE)
            G.prism(P["fine"], F, G.rect(ea - 0.006, ea + 0.006, db1 - 0.0275, db1 - 0.0245), td + 0.009, td + 0.0105,
                    YELLOW)
            G.prism(P["hw"], F, oct_pts(ea - 0.007, b0 + 0.020, ea + 0.007, b0 + 0.060, 0.003), td + 0.004,
                    td + 0.016, STEEL)   # pull lip


def face_switch(spec, P, lod):
    """Network switch: 24 copper ports in two groups of 2x6 with a link lamp per port (alternating above / below
    the rows), SFP uplink cages + console + mgmt, an ID plate, and a hot-swap fan tray at the right."""
    F = server.face_frame(spec)
    a0, a1, b0, b1 = F.area
    fl = F.floor
    ft0 = a1 - 0.098                  # fan tray left edge
    pa1 = ft0 - GAP
    pb0 = b0 + 0.074                  # port plate bottom
    if lod >= 2:
        G.prism(P["frame"], F, G.rect(a0, pa1, pb0, b1), fl, fl + 0.010, PAINT)
        G.prism(P["dark"], F, G.rect(a0 + 0.01, pa1 - 0.01, pb0 + 0.03, b1 - 0.03), fl + 0.010, fl + 0.011, DARK)
        G.prism(P["dark"], F, G.rect(a0, pa1, b0, pb0 - GAP), fl, fl + 0.006, DARK)
        G.prism(P["dark"], F, G.rect(ft0, a1, b0, b1), fl, fl + 0.008, DARK)
        return
    # port plate with real port openings (sockets in the Darker tub behind)
    pw, ph = 0.0175, 0.0145
    pitch = 0.0245
    gw = 6 * pitch
    gap_g = (pa1 - a0 - 2 * gw)
    rows_b = (b1 - 0.034, b1 - 0.067)
    holes, ports = [], []
    for g in range(2):
        ga = a0 + gap_g / 3 + g * (gw + gap_g / 3)
        for r, bc in enumerate(rows_b):
            for i in range(6):
                ac = ga + pitch * (i + 0.5)
                holes.append(G.rect(ac - pw / 2, ac + pw / 2, bc - ph / 2, bc + ph / 2))
                ports.append((ac, bc, r, g * 6 + i))
    G.plate(P["frame"], F, oct_pts(a0, pb0, pa1, b1, 0.006), holes, fl, fl + 0.010, PAINT, bottom=(lod == 0))
    for ac, bc, r, i in ports:
        if lod == 0:   # gold-less SE contacts: a Brushed contact strip inside the socket, top
            G.prism(P["fine"], F, G.rect(ac - pw / 2 + 0.002, ac + pw / 2 - 0.002, bc + ph / 2 - 0.004,
                    bc + ph / 2 - 0.001), fl, fl + 0.0015, STEEL)
        lb = bc + (ph / 2 + 0.0075) * (1 if r == 0 else -1)
        lit = _lit(i, r)
        if lod == 0:
            G.prism(P["fine"], F, G.rect(ac - 0.0045, ac + 0.0045, lb - 0.0035, lb + 0.0035), fl + 0.010,
                    fl + 0.011, DARK)
            G.prism(P["fine"], F, G.rect(ac - 0.003, ac + 0.003, lb - 0.0022, lb + 0.0022), fl + 0.011, fl + 0.0125,
                    LAMP_GREEN if lit else LAMP_OFF)
        else:
            led(P, F, ac, lb, fl + 0.010, lit, lod, r=0.0028)
    patch_cables(P, F, ports, fl, pb0, a0, lod)
    # lower strip: SFP uplink cages, console + mgmt ports, ID plate with system lamp
    sb1 = pb0 - GAP
    G.prism(P["dark"], F, oct_pts(a0, b0, pa1, sb1, 0.005), fl, fl + 0.006, DARK)
    ub = (b0 + sb1) / 2 + 0.012
    for i in range(4):
        ac = a0 + 0.022 + i * 0.03
        G.prism(P["hw"], F, G.rect(ac - 0.0125, ac + 0.0125, ub - 0.008, ub + 0.008), fl + 0.006, fl + 0.012, STEEL)
        G.prism(P["fine"], F, G.rect(ac - 0.0095, ac + 0.0095, ub - 0.0045, ub + 0.0045), fl + 0.012, fl + 0.0124,
                DARK)
        led(P, F, ac, ub - 0.016, fl + 0.006, i < 2, lod, r=0.003)
    for k, ac in enumerate((a0 + 0.152, a0 + 0.178)):    # console, mgmt
        G.prism(P["hw"], F, G.rect(ac - 0.009, ac + 0.009, ub - 0.008, ub + 0.008), fl + 0.006, fl + 0.011, STEEL)
        G.prism(P["fine"], F, G.rect(ac - 0.0065, ac + 0.0065, ub - 0.0055, ub + 0.005), fl + 0.011, fl + 0.0114,
                DARK)
    label(P, F, pa1 - 0.092, pa1 - 0.006, b0 + 0.006, b0 + 0.030, fl + 0.006, "SW-24", 0.016, lod)
    power_button(P, F, pa1 - 0.020, ub + 0.002, fl + 0.006, lod, r=0.0085)
    # fan tray: painted module, louvred intake, thumbscrew + pull lip, fan-OK lamp
    G.plate(P["frame"], F, oct_pts(ft0, b0, a1, b1, 0.008), [G.rect(ft0 + 0.012, a1 - 0.012, b0 + 0.05, b1 - 0.012)],
            fl, fl + 0.010, PAINT)
    louvre_panel(P["fine"], F, ft0 + 0.012, b0 + 0.05, a1 - 0.012, b1 - 0.012, 7, lod)
    fc = (ft0 + a1) / 2
    G.cylinder(P["hw"], F(ft0 + 0.022, b0 + 0.026, fl + 0.010), F(ft0 + 0.022, b0 + 0.026, fl + 0.018), 0.0075,
               12 if lod == 0 else 8, HARDWARE)
    G.prism(P["dark"], F, oct_pts(fc - 0.01, b0 + 0.012, a1 - 0.014, b0 + 0.020, 0.002), fl + 0.010, fl + 0.024, DARK)
    led(P, F, a1 - 0.024, b0 + 0.036, fl + 0.010, True, lod, r=0.0055)


def plugged(i, r):
    """Which switch ports carry a patch cable (about 60 %, irregular like a real patch field)."""
    return (i * 5 + r * 3) % 7 < 4


def patch_cables(P, F, ports, fl, pb0, a0, lod):
    """Patch cables in the switch (purpose: the switch is the one server that is visibly WIRED; its silhouette at
    rack distance is the cable waterfall and the bundle). Each plugged port gets a Darker plug boot; its cable
    leaves straight out, drops (lower row close to the face, upper row in front of it) into a horizontal bundle
    held by two saddle clips below the port plate, and the bundle turns back into the bezel at the left end
    (towards the rack's cable manager). Everything stays within 4.5 cm of the slot front (Ruling 11: <= 6 cm)."""
    bb, bd, br = pb0 - 0.008, 0.022, 0.007      # bundle height (b), depth (d), radius
    cols = sorted({round(ac, 4) for ac, _, _, _ in ports})
    if lod >= 2:
        return
    if lod == 1:   # the silhouette only: a drop curtain per port group and the bundle
        half = len(cols) // 2
        for grp in (cols[:half], cols[half:]):
            G.prism(P["dark"], F, G.rect(grp[0] - 0.006, grp[-1] + 0.006, bb, max(b for _, b, _, _ in ports)),
                    0.014, 0.020, DARK)
        G.prism(P["dark"], F, G.rect(a0 + 0.004, cols[-1] + 0.008, bb - br, bb + br), bd - br, bd + br, DARK)
        return
    for ac, bc, r, i in ports:
        if not plugged(i, r):
            continue
        G.prism(P["fine"], F, oct_pts(ac - 0.0072, bc - 0.0062, ac + 0.0072, bc + 0.0062, 0.002), fl, 0.006, DARK)
        dc = 0.017 if r == 1 else 0.027                 # lower row runs close to the face, the upper row over it
        pts = [F(ac, bc, 0.004), F(ac, bc, dc), F(ac, bb, dc)]
        G.pipe_path(P["fine"], pts, 0.0032, 6, DARK, bend=0.010, bend_steps=2)
        if i % 3 == 0:   # Yellow strain-relief collars: the uplinks
            G.cylinder(P["fine"], F(ac, bc, 0.006), F(ac, bc, 0.011), 0.0045, 6, YELLOW)
    # the bundle: along the plate's foot to the left end, then back into the bezel
    pts = [F(cols[-1] + 0.006, bb, bd), F(a0 + 0.020, bb, bd), F(a0 + 0.008, bb, 0.0)]
    G.pipe_path(P["fine"], pts, br, 8, DARK, bend=0.012, bend_steps=3)
    for ac in (cols[2] + 0.012, cols[-3] + 0.012):   # saddle clips (Darker posts, Brushed strap)
        for sb in (-1, 1):
            G.prism(P["dark"], F, G.rect(ac - 0.004, ac + 0.004, bb + sb * (br + 0.001), bb + sb * (br + 0.005)),
                    fl + 0.006, bd + br + 0.002, DARK)
        G.prism(P["hw"], F, G.rect(ac - 0.0045, ac + 0.0045, bb - br - 0.005, bb + br + 0.005), bd + br,
                bd + br + 0.003, STEEL)


def face_blank(spec, P, lod):
    """Blanking panel: a perforated honeycomb bezel over the whole opening (keeps the slot front closed while the
    cold aisle still feeds the rack plenum evenly) and a Darker label strip: slot size stencil + locator lamp."""
    F = server.face_frame(spec)
    a0, a1, b0, b1 = F.area
    fl = F.floor
    sb1 = b0 + 0.026
    honeycomb(P, F, a0, a1, sb1 + GAP, b1, fl, fl + 0.010, 0.0105, lod, chamfer=0.006)
    if lod >= 2:
        G.prism(P["dark"], F, G.rect(a0, a1, b0, sb1), fl, fl + 0.006, DARK)
        return
    G.prism(P["dark"], F, oct_pts(a0, b0, a1, sb1, 0.005), fl, fl + 0.008, DARK)
    if lod <= 1:
        stencil(P["decal"], F, a0 + 0.012, (b0 + sb1) / 2, 0.014, "6U BLANK", d=fl + 0.008, align="left")
    led(P, F, a1 - 0.02, (b0 + sb1) / 2, fl + 0.008, True, lod, r=0.0065)


FACES = {"Compute": face_compute, "Storage": face_storage, "Switch": face_switch, "Blank": face_blank}


def build(spec, lod):
    """Parts for one LOD: the shared chassis + the variant's face (the last-LOD guard lives in server.build)."""
    return server.build(spec, lod, FACES[spec.variant])


def build_compute(spec, lod):
    return build(spec, lod)


def build_storage(spec, lod):
    return build(spec, lod)


def build_switch(spec, lod):
    return build(spec, lod)


def build_blank(spec, lod):
    return build(spec, lod)
