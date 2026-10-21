"""Front-panel pieces shared by the functional servers (timer, event controller, status display).

| piece          | purpose                                                                              |
| screen         | a lit display (vanilla Terminal UI art, or the LCD surface the game draws into), UV-mapped |
| bezel_ring     | the angled (45 deg) bezel wall between a panel opening and a recessed screen          |
| ind_lamp       | an indicator lamp kept at every LOD but the last (a vanilla state stays visible far away) |
| key            | a chunky push key (nav keys, 5-way pad)                                               |
"""
from .. import server
from ..style import DARK, lamp, oct_pts

try:
    from se2model import geom as G
except ImportError:
    G = None

# Terminal_albedo (1024 px) region with the "SERVER TERMINAL / ACCESS TERMINAL - 3" panel: 270 x 90 px (3:1)
TERMINAL_UV = (10 / 1024, 280 / 1024, 1 - 375 / 1024, 1 - 285 / 1024)   # u0, u1, v0, v1


def _quad(p, F, a0, a1, b0, b1, d, mat, uv=(0.0, 1.0, 0.0, 1.0)):
    """One open quad facing +d (decal Part: the authored winding is kept), UVs u along a, v along b."""
    bm = p.bm
    uvl = bm.loops.layers.uv.verify()
    f = bm.faces.new([bm.verts.new(F(a, b, d)) for a, b in G.rect(a0, a1, b0, b1)])
    f.material_index = p.mi(mat)
    u0, u1, v0, v1 = uv
    for loop, t in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
        loop[uvl].uv = t
    return f


def screen(P, F, a0, a1, b0, b1, d, mat, uv=(0.0, 1.0, 0.0, 1.0)):
    """A display surface (a quad in the decal Part, so it keeps its UVs and winding)."""
    return _quad(P["decal"], F, a0, a1, b0, b1, d, mat, uv)


def bezel_ring(p, F, outer, inner, d_out, d_in, mat):
    """Four sloped quads from the outer rectangle (a0, a1, b0, b1) at depth d_out to the inner one at d_in: the
    angled bezel round a recessed screen. p must keep its winding (a decal Part)."""
    oa0, oa1, ob0, ob1 = outer
    ia0, ia1, ib0, ib1 = inner
    O = [(oa0, ob0), (oa1, ob0), (oa1, ob1), (oa0, ob1)]
    I = [(ia0, ib0), (ia1, ib0), (ia1, ib1), (ia0, ib1)]
    bm = p.bm
    mi = p.mi(mat)
    for i in range(4):
        j = (i + 1) % 4
        f = bm.faces.new([bm.verts.new(F(*O[i], d_out)), bm.verts.new(F(*O[j], d_out)),
                          bm.verts.new(F(*I[j], d_in)), bm.verts.new(F(*I[i], d_in))])
        f.material_index = mi


def ind_lamp(P, F, a, b, d, mat, lod, r=0.006):
    """An indicator lamp: LOD0 a round lens in a Darker bezel, LOD1 a square lens, LOD2 a flat square (2 tris)."""
    if lod == 0:
        lamp(P["hw"], F, a, b, d, r=r, mat=mat, lod=0)
    elif lod == 1:
        server._led(P, F, a, b, d, mat, 1, r=r)
    else:
        _quad(P["decal"], F, a - r, a + r, b - r, b + r, d + 0.0015, mat)


def key(P, F, a, b, d, w, h, mat, lod, part="hw"):
    """A push key: a Darker collar and a chamfered cap of mat standing 6 mm proud."""
    if lod >= 2:
        return
    G.prism(P["dark"], F, oct_pts(a - w / 2 - 0.002, b - h / 2 - 0.002, a + w / 2 + 0.002, b + h / 2 + 0.002, 0.002),
            d, d + 0.002, DARK)
    G.prism(P[part], F, oct_pts(a - w / 2, b - h / 2, a + w / 2, b + h / 2, 0.003 if lod == 0 else 0.0), d + 0.002,
            d + 0.006, mat)
