"""Raised-floor previews: the floor tiles.

    DC_PREVIEW=floor blender -b --python Source/Model/build_dc.py -- "DC_Floor_*" "DC_Rack42_SplitFront" \
        "DC_Srv_*" "DC_Tray_Drop_Full" "DC_Tray_StraightS_Full" "DC_TrayRods_100"

Writes Source/Model/preview/floor/ (DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution):
  <block>_34 / _top / _side / _section   each tile: 3/4 view, top (ortho), side (ortho), a section through a
                                         pedestal row (cut faces red)
  <block>_lods                           LOD0..n side by side
  grid_*                                 a 2 x 2 m (4 x 4 tile) floor mixing all four blocks: 3/4, top, the seams
                                         where four blocks meet, the open edge
  exploded_corner                        a 2 x 2 tile corner with one deck lifted off its pedestals
  fracture_*                             the two fracture pieces (deck, understructure) pulled apart
  paints_*                               keen, black, blue and orange paint
  room_*                                 the reference room (dc/preview_room.py): the tiles under a rack row, the
                                         cold-aisle perforated row, a rack plinth on the tile grid, overhead, hot
  vanilla_compare                        our tiles beside vanilla CatwalkSquareBase_250 and DeckPanel250
Contact sheet: python3 Source/Model/floor_sheet.py.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import config, floor, room
from . import preview as PV
from . import preview_mats as PM
from . import preview_room as PR
from .preview import Rz, T, want

FLOORS = ("DC_Floor_Solid_050", "DC_Floor_Perf_050", "DC_Floor_Solid_100", "DC_Floor_Perf_100")
ZC = floor.H2                         # block centre above the ground (the floor stands on z = 0)
_SPLIT = {}


def _out():
    PR._out("floor")                        # preview/floor/ for PV and PR shots alike


def _w(name):
    return 2 * floor.half(floor_spec(name))


def floor_spec(name):
    from . import catalog
    return catalog.BY_NAME[name]


# ---------------------------------------------------------------------------------------------------- geometry
def _copy_world(o):
    me = o.data.copy()
    me.transform(o.matrix_world)
    return me


def _new_coll(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    PV._exclude(c)
    return c


def section(built, name, y0, paint="keen"):
    """A copy of LOD0 cut at y = y0 (the part with y < y0 kept), the closed parts' cut faces filled in red."""
    key = ("section", name, y0, paint)
    if key in _SPLIT:
        return _SPLIT[key]
    src = PV.painted(built, name, 0, paint)
    c = _new_coll(f"sec_{name}_{paint}")
    red = PM.get("Section")
    for o in src.objects:
        if o.type != "MESH":
            continue
        me = _copy_world(o)
        bm = bmesh.new()
        bm.from_mesh(me)
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, y0, 0), plane_no=(0, 1, 0), clear_outer=True)
        cut = [e for e in bm.edges if e.is_boundary and all(abs(v.co.y - y0) < 1e-5 for v in e.verts)]
        if cut and len(bm.faces) > 8:   # closed solids only (decal quads stay open)
            new = bmesh.ops.holes_fill(bm, edges=cut, sides=0)["faces"]
            if new:
                me.materials.append(red)
                for f in new:
                    f.material_index = len(me.materials) - 1
        bm.to_mesh(me)
        bm.free()
        if len(me.polygons):
            c.objects.link(bpy.data.objects.new(f"sec_{o.name}", me))
    _SPLIT[key] = c
    return c


def pieces(built, name, paint="keen"):
    """The two fracture pieces of LOD0 as the export assigns them (fracture.plan, each face's centroid):
    {zone id: collection}."""
    key = ("pieces", name, paint)
    if key in _SPLIT:
        return _SPLIT[key]
    from . import fracture as FR
    spec = floor_spec(name)
    plan = FR.plan(spec, floor.collision(spec))   # the export's zones (fracture.plan; faces by centroid)
    zones = [(z.id, *z.hull) for z in plan.zones]
    src = PV.painted(built, name, 0, paint)
    out = {}
    for z, _, _ in zones:
        c = _new_coll(f"piece_{name}_{z}_{paint}")
        for o in src.objects:
            if o.type != "MESH":
                continue
            me = _copy_world(o)
            bm = bmesh.new()
            bm.from_mesh(me)
            drop = [f for f in bm.faces if plan.zones[plan.zone_index(tuple(f.calc_center_median()))].id != z]
            bmesh.ops.delete(bm, geom=drop, context="FACES")
            bm.to_mesh(me)
            bm.free()
            if len(me.polygons):
                c.objects.link(bpy.data.objects.new(f"pc_{o.name}_{z}", me))
        out[z] = c
    _SPLIT[key] = out
    return out


# ---------------------------------------------------------------------------------------------------- shots
def _shot(nm, floor_rect=(-2, 2, -2, 2), **kw):
    return PV.Shot(nm, floor=floor_rect, **kw)


def tile_views(built, name):
    w = _w(name)
    D = 1.5 * w + 0.5
    views = {"34": dict(loc=(-0.62 * D, 0.85 * D, 0.62 * D), tgt=(0, 0, 0.09), lens=50),
             "top": dict(loc=(0, 0, 3.0), tgt=(0, 0, 0), lens=50, ortho=w * 1.2 * 1800 / 1150),
             "side": dict(loc=(0, 3.0, ZC), tgt=(0, 0, ZC), lens=50, ortho=w * 1.2),
             "under": dict(loc=(0.55 * D, 0.95 * D, 0.06), tgt=(0, 0, 0.07), lens=45)}
    for v, c in views.items():
        nm = f"{name}_{v}"
        if not want(nm):
            continue
        s = _shot(nm)
        s.inst(PV.painted(built, name, 0), T(0, 0, ZC))
        s.camera(c["loc"], c["tgt"], c["lens"], ortho=c.get("ortho"))
        s.render()
    nm = f"{name}_section"
    if want(nm):
        # through the first tile: its lift cup (solid) or its damper and insert (perforated); the pedestal row behind
        a0, b0, a1, b1 = floor.tiles(floor_spec(name))[0]
        cy = (b0 + b1) / 2
        y0 = cy + 0.0001 if floor.is_perf(floor_spec(name)) else cy - floor.CUP_Y + 0.0001
        s = _shot(nm)
        s.inst(section(built, name, y0), T(0, 0, ZC))
        s.camera((0.2 * w, y0 + 0.75 * w + 0.35, 0.42), (0.0, y0, 0.10), 40)
        s.render()


GRID = (("DC_Floor_Solid_100", 0.5, 0.5), ("DC_Floor_Perf_100", 1.5, 0.5), ("DC_Floor_Solid_100", 1.5, 1.5),
        ("DC_Floor_Perf_050", 0.25, 1.25), ("DC_Floor_Solid_050", 0.75, 1.25), ("DC_Floor_Solid_050", 0.25, 1.75),
        ("DC_Floor_Perf_050", 0.75, 1.75))


def grid(built, paint="keen", nm_prefix="grid"):
    """A 2 x 2 m floor (4 x 4 tiles) of every block, centred on the origin."""
    def place(s):
        for n, x, y in GRID:
            s.inst(PV.painted(built, n, 0, paint), T(x - 1.0, y - 1.0, ZC))
    shots = {"34": ((-1.9, 2.6, 2.0), (0, 0, 0.0), 40, None),
             "top": ((0, 0, 4.0), (0, 0, 0), 50, 2.3),
             "seams_closeup": ((0.40, 0.36, 0.55), (0.0, 0.0, 0.12), 34, None),
             "seam_050_closeup": ((-0.30, 0.62, 0.55), (-0.5, 0.25, 0.12), 36, None),
             "edge_closeup": ((-1.55, 1.2, 0.22), (-1.0, 0.55, 0.08), 30, None)}
    for k, (loc, tgt, lens, ortho) in shots.items():
        n = f"{nm_prefix}_{k}"
        if not want(n):
            continue
        s = _shot(n, (-3, 3, -3, 3))
        place(s)
        s.camera(loc, tgt, lens, ortho=ortho)
        s.render()


def exploded_corner(built):
    """2 x 2 tiles of 0.5 m blocks; the front-left tile's deck lifted off its pedestals (as the fracture splits it)."""
    nm = "exploded_corner"
    if not want(nm):
        return
    s = _shot(nm)
    layout = (("DC_Floor_Solid_050", 0.25, 0.25), ("DC_Floor_Perf_050", -0.25, 0.25),
              ("DC_Floor_Perf_050", 0.25, -0.25))
    for n, x, y in layout:
        s.inst(PV.painted(built, n, 0), T(x, y, ZC))
    pc = pieces(built, "DC_Floor_Solid_050")
    sub, deck = pc["Fracture_02"], pc["Fracture_01"]
    s.inst(sub, T(-0.25, -0.25, ZC))
    s.inst(deck, T(-0.42, -0.30, ZC + 0.26) @ Matrix.Rotation(math.radians(28), 4, "Y"))
    s.camera((-1.35, -1.45, 1.35), (-0.15, -0.1, 0.15), 36)
    s.caption("deck lifted off: pedestals, stringers, gasket pads", (-0.25, -0.25, 0.75), 0.04)
    s.render()


def fracture(built, name):
    """The block's two fracture pieces pulled apart (deck up and tilted, as a broken-off plate)."""
    nm = f"fracture_{name}"
    if not want(nm):
        return
    w = _w(name)
    pc = pieces(built, name)
    s = _shot(nm)
    s.inst(pc["Fracture_02"], T(0, 0, ZC))
    s.inst(pc["Fracture_01"], T(0.12 * w, -0.08 * w, ZC + 0.22 + 0.25 * w) @ Matrix.Rotation(math.radians(-24), 4, "X")
           @ Matrix.Rotation(math.radians(9), 4, "Y"))
    D = 1.5 * w + 0.6
    s.camera((-0.7 * D, 0.9 * D, 0.55 * D + 0.2), (0, 0, 0.18 + 0.1 * w), 45)
    s.caption("Fracture_01: deck", (0.12 * w, -0.08 * w, 0.62 + 0.3 * w), 0.035 + 0.01 * w)
    s.caption("Fracture_02: understructure", (-0.2 * w, 0.62 * w, 0.02), 0.035 + 0.01 * w)
    s.render()


def paints(built):
    for paint in ("keen", "black", "blue", "orange"):
        nm = f"paints_{paint}"
        if not want(nm):
            continue
        s = _shot(nm)
        s.inst(PV.painted(built, "DC_Floor_Solid_100", 0, paint), T(-0.5, 0, ZC))
        s.inst(PV.painted(built, "DC_Floor_Perf_100", 0, paint), T(0.5, 0, ZC))
        s.camera((-1.1, 2.3, 1.7), (0, 0, 0.05), 42)
        s.render()


def vanilla_compare(built):
    """Our four blocks beside the clone source (vanilla CatwalkSquareBase_250) and DeckPanel250, same light and
    stand-in materials, standing on one ground plane."""
    nm = "vanilla_compare"
    if not want(nm):
        return
    s = PV.Shot(nm, res=(2400, 1100), floor=(-6, 3, -2, 2))
    x, labels = 0.0, []
    for n in FLOORS:
        w = _w(n)
        s.inst(PV.painted(built, n, 0), T(x - w / 2, 0, ZC))
        labels.append((n.replace("DC_Floor_", ""), (x - w / 2, 0.0, 0.45)))
        x -= w + 0.25
    for rel, label in PR.VANILLA[:2]:
        c, lo, hi = PV.vanilla(rel)
        w = hi.x - lo.x
        ctr = (lo + hi) / 2
        s.inst(c, T(x - w / 2, 0, 0) @ T(-ctr.x, -ctr.y, -lo.z))
        labels.append((f"vanilla {label}", (x - w / 2, 0.0, hi.z - lo.z + 0.25)))
        x -= w + 0.3
    cx = x / 2
    s.camera((cx + 0.6, 0.7 * abs(x) + 1.0, 0.42 * abs(x) + 0.8), (cx, 0, 0.2), 38)
    for txt, at in labels:
        s.caption(txt, at, 0.07)
    s.render()


def _cams():
    """Extra room cameras for the floor (added to dc/preview_room.CAMERAS)."""
    def cold_aisle_floor(info):
        w, L, *_ = PR._geo(info)
        return PR.Cam((-0.6, 0.28 * w, 1.35), (L * 0.55, -0.05 * w, 0.05), 20)

    def plinth(info):   # rack A2's front plinth on the tiles (cold: the front faces the aisle)
        w, L, *_, front = PR._geo(info)
        yf = -(w / 2 + 0.625) + front * 0.625
        return PR.Cam((1.95, yf + front * 0.75, 0.55), (1.35, yf - front * 0.05, 0.22), 30)

    def under_row(info):   # low along the walkway: the floor's open edge is not in the room, so the tile grid
        w, L, x0, x1, y0, y1, _ = PR._geo(info)
        return PR.Cam((x0 + 0.6, y0 + 0.45, 0.65), (L * 0.5, -(w / 2 + 0.6), 0.3), 18)
    PR.CAMERAS.update(floor_cold_aisle=cold_aisle_floor, floor_plinth=plinth, floor_row=under_row)


def room_shots(built):
    _cams()
    for cam, aisle in (("end_row", "cold"), ("floor_row", "cold"), ("aisle_eye", "cold"), ("floor_cold_aisle", "cold"),
                       ("floor_plinth", "cold"), ("overhead", "cold"), ("end_row", "hot"), ("floor_plinth", "hot"),
                       ("overhead", "hot")):
        PR.shot(built, cam, 1.5, aisle, captions=False)
    PR.shot(built, "floor_cold_aisle", 1.5, "cold", paint="black", name="room_150_cold_floor_cold_aisle_black",
            captions=False)


def render_all(built):
    _out()
    for n in FLOORS:
        if n in built:
            tile_views(built, n)
            PV.lods(built, n)
    if all(n in built for n in FLOORS):
        grid(built)
        grid(built, "black", "grid_black")
        paints(built)
        vanilla_compare(built)
    if "DC_Floor_Solid_050" in built and "DC_Floor_Perf_050" in built:
        exploded_corner(built)
    for n in ("DC_Floor_Perf_050", "DC_Floor_Solid_100"):
        if n in built:
            fracture(built, n)
    room_shots(built)
    print("floor previews ->", PV.OUT)
