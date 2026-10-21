"""The Data Center's shared SE2 design language (racks, servers, room pieces).

Ported from the v2 "SE-ified" mockups (tools/mockups/datacenter/dclib2.py) onto the se2model library:
- player paint: the bodies are PaintedMetalColorable (black is a paint choice, not baked in);
- material roles (as in vanilla blocks): Colorable shells, Darker housings and recesses, Brushed
  load-bearing steel (rails), MetalDull black-oxide hardware, Yellow as thin trim lines only;
- chunky chamfers toward Keen's ~9 cm on big edges, crisp small breaks;
- fewer, larger lights: lenses in Darker bezels;
- Keen stencils (AtlasFont_BarlowCondensed) and decal atlases instead of photoreal print.

All helpers write into se2model Parts (Blender frame: X width, +Y = the block's front = game Forward, Z up).
"""
from se2model.config import BM, C, DK, FONT, MD, P1, S2, YL

try:   # the geometry helpers need Blender; the constants do not (pytest imports them outside Blender)
    from mathutils import Vector
    from se2model import decals as DC
    from se2model import geom as G
except ImportError:
    Vector = DC = G = None

PAINT = C            # PaintedMetalColorable: the player's paint
DARK = DK            # PaintedMetalDarker: housings, recesses, combs
STEEL = BM           # BrushedMetal: rails and load-bearing steel
YELLOW = YL          # PaintedMetalYellow: thin trim lines
HARDWARE = MD        # MetalDull: black-oxide bolts on paint
STENCIL = FONT       # AtlasFont_BarlowCondensed (paint-masked: invisible on a same-colour body)
STENCIL_WHITE = FONT + "_CleanWhite"   # vanilla 1024 clean white glyph atlas: rack IDs on Darker plates
PARTS = P1           # AtlasDecal_Parts01
LAMP_GREEN = "EmissiveGreen"   # always-lit "power OK" lamp (vanilla EmissiveGreen 78f2cbaa)

CHAMFER_LARGE = 0.09   # Keen's big 45 deg chamfer on outer housing edges
CHAMFER_SMALL = 0.015  # the crisp small break
SHADOW_GAP = 0.016     # gap between split cover plates (reads at distance)
LED_SIZE = 0.012       # lens radius of a status lamp (Keen: 1.5-3 cm lenses in bezels)
BOLT_R = 0.009         # chunky bolt head radius (readable at first-person range)
KEEP_OUT = 0.027       # parts on a non-mounting face stay >= 2.5 cm inside the box plane


def oct_pts(a0, b0, a1, b1, c):
    """Rectangle [a0,a1] x [b0,b1] with 45 deg clipped corners (Keen panel shape), counter-clockwise."""
    return [(a0 + c, b0), (a1 - c, b0), (a1, b0 + c), (a1, b1 - c), (a1 - c, b1), (a0 + c, b1), (a0, b1 - c), (a0, b0 + c)]


def bolt(p, F, a, b, d=0.0, r=BOLT_R, mat=HARDWARE, lod=0):
    """Hex bolt head (6 sides, guide: hex nuts are 6) standing on face F at depth d."""
    if lod > 1:
        return
    G.cylinder(p, F(a, b, d - 0.001), F(a, b, d + 0.005), r, 6, mat)


def lamp(p, F, a, b, d=0.0, r=LED_SIZE, mat=LAMP_GREEN, lod=0):
    """Status light: a lens in a Darker bezel, proud of face F by about 7 mm."""
    n = 16 if lod == 0 else 8
    G.cylinder(p, F(a, b, d - 0.001), F(a, b, d + 0.005), r + 0.006, n, DARK)
    G.cylinder(p, F(a, b, d + 0.005), F(a, b, d + 0.007), r, n, mat)


def stencil(p, F, a, b, height, text, d=0.0, align="center", track=0.10, white=True):
    """Keen stencil text (decal quads 2 mm proud) on face F, (a, b) = anchor at the cap middle.

    white=True uses AtlasFont_BarlowCondensed_CleanWhite (the clean quadrant of the main font atlas as its own
    1024 px atlas, so the se2model glyph boxes apply at /1024): white text that reads on any paint when it sits on
    a Darker plate. white=False uses the paint-masked main atlas (se2model.decals.text)."""
    w = DC.text_width(height, text, track)
    a0 = a - w / 2 if align == "center" else (a - w if align == "right" else a)
    if not white:
        return DC.text(p, F, a0, b, height, text, d=d, track=track)
    s, x = height / DC.CAP_PX, 0.0
    for ch in text:
        if ch == " ":
            x += 0.45 * height
            continue
        x0, y0, x1, y1 = DC.GLYPHS[ch]
        gw, gh = (x1 - x0) * s, (y1 - y0) * s
        u0, u1, v0, v1 = x0 / 1024, x1 / 1024, 1 - y1 / 1024, 1 - y0 / 1024
        DC._quad(p, F, [(a0 + x, b - gh / 2), (a0 + x + gw, b - gh / 2), (a0 + x + gw, b + gh / 2), (a0 + x, b + gh / 2)],
                 d, STENCIL_WHITE, ((u0, v0), (u1, v0), (u1, v1), (u0, v1)))
        x += gw + track * height
    return x


# Stickers02 warning triangles as exact triangles: the shared se2model.decals.HAZARD_TRIANGLES (measured there; the
# atlas interlocks point-up / point-down triangles, so a bounding rectangle catches its neighbours' corners, the
# in-game "diagonal lines"). Drawn point up (ISO 7010 W012 for tri_electric).
def hazard_triangle(p, F, a, b, width, key="tri_electric", d=0.0):
    """A warning triangle decal (one triangle face, point up) centred on (a, b) of face F, base `width` wide."""
    uv, ratio = DC.hazard_triangle_uv(key)
    h = width * ratio
    return DC._quad(p, F, [(a - width / 2, b - h / 2), (a + width / 2, b - h / 2), (a, b + h / 2)], d, S2, uv)


def corner_cap(p, sx, sy, xo, yo, z0, z1, size=0.12, chamfer=0.06, lod=0, trim_at=None):
    """Armoured corner cap: a chunky Darker block wrapped round the outer vertical corner (xo, yo) of a cabinet,
    the corner itself cut by a big 45 deg chamfer, a Yellow trim line and two bolts on the chamfer face.
    sx, sy = +-1 point outward. Purpose: impact armour on the corners that get knocked when racks are moved
    (the bolts hold it to the post)."""
    x0, y0 = xo - sx * size, yo - sy * size
    c = chamfer if lod < 3 else 0.0
    # polygon in plan (x, y), counter-clockwise
    pts = [(x0, y0), (xo, y0), (xo, yo - sy * c), (xo - sx * c, yo), (x0, yo)]
    if sx * sy < 0:
        pts = list(reversed(pts))
    Fz = G.Face((0, 0, 0), (1, 0, 0), (0, 1, 0))
    G.prism(p, Fz, pts, z0, z1, DARK)
    if lod >= 2 or c == 0:
        return
    # yellow trim line round the two flats and the chamfer, 1.5 mm proud, near the inner end of the cap
    zt = (z1 - 0.022) if trim_at == "top" else (z0 + 0.022)
    t = 0.0015
    tp = [(x0 + sx * 0.01, y0 - sy * t), (xo + sx * t, y0 - sy * t), (xo + sx * t, yo - sy * c + sy * 0.0006),
          (xo - sx * c + sx * 0.0006, yo + sy * t), (x0 + sx * 0.01, yo + sy * t)]
    inner = [(x0 + sx * 0.01, y0 + sy * 0.004), (xo - sx * 0.004, y0 + sy * 0.004),
             (xo - sx * 0.004, yo - sy * c - sy * 0.002), (xo - sx * c - sx * 0.002, yo - sy * 0.004),
             (x0 + sx * 0.01, yo - sy * 0.004)]
    poly = tp + list(reversed(inner))
    if sx * sy < 0:
        poly = list(reversed(poly))
    G.prism(p, Fz, poly, zt - 0.005, zt + 0.005, YELLOW)
    if lod == 0:
        # two bolts on the chamfer face
        m = Vector(((xo - sx * c / 2), (yo - sy * c / 2), 0))
        nrm = Vector((sx, sy, 0)).normalized()
        u = Vector((-sy, sx, 0)).normalized()
        Fc = G.Face(m, u, (0, 0, 1)) if u.cross(Vector((0, 0, 1))).dot(nrm) > 0 else G.Face(m, -u, (0, 0, 1))
        zc = (z0 + z1) / 2
        for k in (-1, 1):
            bolt(p, Fc, 0.0, zc + k * (z1 - z0) * 0.22, 0.0, r=0.008)


def louvre_panel(p, F, a0, b0, a1, b1, n, lod=0):
    """Angled Darker slats in an opening (air path), slats inset 1.5 cm."""
    if lod >= 2:
        return
    G.louvre(p, F, a0, a1, b0, b1, -0.015, n if lod == 0 else max(2, n // 2), DARK, angle=38, t=0.005)


# ---------------------------------------------------------------------------------------------------- cable trays
# Cable tray roles. The basket COULD take the player's paint (PaintedMetalColorable is vanilla's only fully
# paintable material), but it stays unpainted: on the same material the basket and the data cables are always one
# color and blur into one mass. The basket is fixed bright steel (BrushedMetal, chosen by preview: basket_compare);
# the data cables take the paint, so there is always contrast.
TRAY_STEEL = STEEL     # the basket wires: galvanised / bright steel, not paintable
TRAY_HW = STEEL        # rods, nuts, washers, rod plates, splice plates, buckles: zinc-plated, bright like the basket
#                        (one material fewer, so a Reducer keeps <= 8 across its LODs with the card)
DATA = PAINT           # data bundles take the player's paint (tray_lanes)
FIBRE = YELLOW         # fibre
POWER = "PaintedMetalGrey"   # power (moderate)
POWER_BLACK = "Rubber"       # black power (full); also boots
TIE = DARK             # straps, collars, clamps, the strut channel
TRAY_CARD = "GratingMetallic"   # LOD2 basket card (alpha-tested vanilla, chosen by preview)


PERF = "MetalPerforationSteel"   # vanilla perforated steel (alpha-masked, ~44 % open): door leaves, cable-tray floors
PERF_UV_M = 3.0                  # metres per UV unit: the texture's ~180 holes per tile -> ~17 mm hole pitch


def perf_quad(p, corners, axes):
    """One open perforated quad from 4 world corners (wound for the facing side), world-scaled UVs taken from the
    two coordinate axes `axes` (e.g. (0, 2) = x, z for a vertical leaf). p must be a decal-style Part (keeps winding)."""
    bm = p.bm
    uvl = bm.loops.layers.uv.verify()
    f = bm.faces.new([bm.verts.new(c) for c in corners])
    f.material_index = p.mi(PERF)
    for loop, c in zip(f.loops, corners):
        loop[uvl].uv = (c[axes[0]] / PERF_UV_M, c[axes[1]] / PERF_UV_M)
    return f
