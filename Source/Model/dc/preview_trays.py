"""The cable-tray preview catalogue: Blender renders of the built tray blocks.

    DC_PREVIEW=trays blender -b --python Source/Model/build_dc.py -- "DC_Tray_StraightS_*" "DC_Tray_StraightL_*" \
        "DC_Tray_Reducer_*" DC_Rack42_Open DC_Rack24_Open DC_Srv_Compute DC_Srv_Storage DC_Srv_Switch DC_Srv_Blank
    python3 Source/Model/tray_sheet.py          # the per-piece sheets and the contact sheet (Pillow)

Writes preview/trays/ (DC_SHOTS=prefix,... renders a subset). Every shot uses the core preview rig
(dc/preview.py Shot, dc/preview_mats.py stand-ins: the paint goes to PaintedMetalColorable, i.e. the data cables;
the basket is fixed BrushedMetal). DC_PREVIEW=tray-turns | tray-junctions | tray-drops | tray-compare | tray-hall
render the other shot families into preview/trays-<family>/ (render_all(BUILT, which=...)); each renders whatever
pieces are built.

Shot families (the catalogue):
  piece_<name>_{34,top,end}          every built piece: 3/4 front, top (ortho), nearly end-on at port a
  close_{mesh,edge,splice,strap,hanger,boot,tag}   1 m close-ups of the kit parts
  ladder_{side,joint}                the density ladder (Empty / Low / Moderate / Full) and Full nested on Low
  chain_{34,joint_*}                 StraightL + StraightS + the Reducer chain Full -> Empty, joints close up
  run_racks_{34,front,joint}         a run over a populated rack row with the Drop ghost and its waterfalls
  run20_{2,10,30,60}m                a 20 m Full run, each piece at the LOD its distance picks (illustrative bands)
  mount_{ceiling,wall,floor}         ceiling-hung on its rod plates, wall-mounted on its strut, floor-standing
  paint_{keen,blue,teal,black}       the same run in four paints (the data cables take the paint)
  lods_<name>                        LOD0..last side by side
  card_compare                       LOD2 with each candidate basket card (the TRAY_CARD choice)
  basket_compare                     the fixed basket steel candidates (BrushedMetal / Chrome / MetalDull)
  vanilla_compare                    beside vanilla WallInsertPipes and CatwalkNarrowBase_250 (read-only FBX)
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from . import catalog, config, dims as DM
from . import tray_plan as TP
from . import preview as PV
from . import preview_mats as PM
from .preview import Rz, Shot, T, want

OUT = os.path.join(config.PREVIEW_DIR, "trays")
CELL = 0.25
D = ("Empty", "Low", "Moderate", "Full")
STAMP = {}


def _out(which):
    global OUT
    folder = "trays" if which == "catalogue" else f"trays-{which}"
    OUT = os.path.join(config.PREVIEW_DIR, folder, os.environ.get("DC_PREVIEW_SUB", ""))
    os.makedirs(OUT, exist_ok=True)
    PV.OUT = OUT


def _len(name):
    return CELL * catalog.BY_NAME[name].cells[0]


def piece(s, built, name, x0, y0=-0.25, z0=0.0, lod=0, paint="keen", rot=0.0):
    """Place a built tray by its box corner (x0, y0, z0) (rot about z through that corner); returns its length."""
    spec = catalog.BY_NAME[name]
    lx, lz, ly = (CELL * c for c in spec.cells)
    lod = min(lod, len(built[name]["lods"]) - 1)
    s.inst(PV.painted(built, name, lod, paint), T(x0, y0, z0) @ Rz(rot) @ T(lx / 2, ly / 2, lz / 2))
    return lx


def chain(s, built, names, x0=0.0, y0=-0.25, z0=0.0, paint="keen", lod=0, cam=None):
    """Pieces end to end along +x from x0 (each one's port a on the previous one's port b). lod: an int, or None
    = by distance from `cam` (a Vector) with the illustrative bands of LOD_BANDS. Returns the joint x positions."""
    x, joints = x0, []
    for n in names:
        L = _len(n)
        lv = lod
        if lv is None:
            d = (Vector((x + L / 2, y0 + 0.25, z0 + 0.125)) - cam).length
            lv = next((i for i, b in enumerate(LOD_BANDS) if d < b), len(LOD_BANDS))
        piece(s, built, n, x, y0, z0, lv, paint)
        x += L
        joints.append(x)
    return joints[:-1]


LOD_BANDS = (6.0, 18.0, 40.0)   # illustrative: LOD0 under 6 m, LOD1 to 18 m, LOD2 to 40 m, then the last LOD


def scene(name, res=(1600, 1000), floor=(-3, 3, -3, 3), floor_z=0.0, light=1.0):
    return Shot(name, res=res, floor=floor, floor_z=floor_z, light=light)


def box(s, name, lo, hi, mat):
    bm = bmesh.new()
    vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.scale(bm, vec=Vector(hi) - Vector(lo), verts=vs)
    bmesh.ops.translate(bm, vec=(Vector(lo) + Vector(hi)) / 2, verts=vs)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    me.materials.append(PM.get(mat))
    return s.link(bpy.data.objects.new(name, me))


def sun(s, energy=5.0, rot=(0.7, 0.2, 2.4)):
    """A sun for the big scenes (the studio rig's area lights only reach a few metres)."""
    ld = bpy.data.lights.new(f"{s.name}_sun", "SUN")
    ld.energy = energy
    o = bpy.data.objects.new(ld.name, ld)
    o.rotation_euler = rot
    s.link(o)
    return o


def ortho(s, loc, tgt, scale):
    cam = s.camera(loc, tgt, 50, ortho=scale)
    return cam


def done(s):
    path = s.render()
    STAMP[s.name] = path
    return path


def built_trays(built, variant=None):
    return [n for n in built if catalog.BY_NAME[n].family == "tray" and (variant is None or
                                                                           catalog.BY_NAME[n].variant == variant)]


# ---------------------------------------------------------------------------------------------------- per piece
def pieces(built, only=None):
    for n in sorted(built_trays(built), key=lambda k: [b.name for b in catalog.CATALOGUE].index(k)):
        spec = catalog.BY_NAME[n]
        if only and spec.variant not in only:
            continue
        L, H, W = (CELL * c for c in spec.cells)
        pa = TP.plan(spec).ports["a"].o
        pa = Vector((pa[0] - L / 2, pa[1] - W / 2, pa[2]))        # port a in the scene (box centred in x, y)
        for v in ("34", "top", "end"):
            nm = f"piece_{n}_{v}"
            if not want(nm):
                continue
            s = scene(nm, res=(1300, 900), floor=(-2, 2, -2, 2), floor_z=-0.6)
            piece(s, built, n, -L / 2, -W / 2, 0.0)
            if v == "34":
                d = 0.75 + 0.55 * max(L, W, H)
                s.camera((-0.55 * d, 0.95 * d, 0.62 * d + 0.1), (0.0, 0.0, 0.08 + max(0.0, H - 0.25) / 2), 35)
            elif v == "top":     # (the frame is 1300 x 900: a deep piece is framed by its depth)
                ortho(s, (0.0, 0.0, 4.0), (0.0, 0.0001, 0.0), max(L, W * 1300 / 900) + 0.25)
            else:   # nearly end-on at port a (10 deg off the axis, so the open bundle ends show their cables)
                s.camera(tuple(pa + Vector((-1.4, 0.25, 0.3))), tuple(pa + Vector((0.0, 0.0, 0.06))), 40)
            done(s)


# ---------------------------------------------------------------------------------------------------- close-ups
def closeups(built):
    S, R = "DC_Tray_StraightS_Full", "DC_Tray_Reducer_Full"
    if S not in built:
        return
    shots = {   # name: (camera, target, lens): the pair StraightS + StraightS spans x -0.5 .. 0.5, joint at x 0
        "close_mesh": ((0.05, -0.55, -0.55), (0.0, 0.0, 0.03), 40),            # the floor mesh from below
        "close_edge": ((-0.30, 0.42, 0.30), (-0.05, 0.215, 0.14), 40),        # the safety edge, turned-over U tops
        "close_splice": ((0.10, -0.55, 0.16), (0.0, -0.22, 0.09), 45),        # the splice plates at the joint
        "close_strap": ((-0.08, 0.35, 0.40), (-0.125, 0.0, 0.11), 40),        # a shared band and its buckle
        "close_hanger": ((0.42, -0.50, 0.06), (0.25, -0.23, 0.10), 40),       # rod, washer, nut, end cap
        "close_plate": ((0.36, -0.40, 0.10), (0.25, -0.232, 0.235), 40),      # rod plate from below, its bolts
    }
    for nm, (loc, tgt, lens) in shots.items():
        if not want(nm):
            continue
        s = scene(nm, res=(1500, 1000), floor=(-2, 2, -2, 2), floor_z=-1.0)
        chain(s, built, [S, S], x0=-0.5, lod=0, paint="blue")
        s.camera(loc, tgt, lens)
        done(s)
    if R in built:
        for nm, loc, tgt in (("close_boot", (0.40, 0.42, 0.33), (0.05, 0.05, 0.10)),
                             ("close_tag", (-0.25, 0.75, 0.14), (-0.13, 0.22, 0.09))):
            if not want(nm):
                continue
            s = scene(nm, res=(1500, 1000), floor=(-2, 2, -2, 2), floor_z=-1.0)
            chain(s, built, [R], x0=-0.25, lod=0, paint="blue")
            s.camera(loc, tgt, 40)
            done(s)


# ---------------------------------------------------------------------------------------------------- ladders, chains
def ladder(built):
    names = [f"DC_Tray_StraightL_{d}" for d in D]
    if not all(n in built for n in names):
        return
    nm = "ladder_side"
    if want(nm):
        s = scene(nm, res=(1900, 1000), floor=(-3, 3, -3, 3), floor_z=-0.6)
        for k, n in enumerate(names):
            y = (k - 1.5) * 0.75
            piece(s, built, n, -0.75, y - 0.25, 0.0, paint="blue")
        s.camera((-3.4, 0.9, 2.3), (0.0, 0.0, 0.0), 30)
        for k, d in enumerate(D):
            s.caption(d.upper(), (-1.05, (k - 1.5) * 0.75, 0.12), 0.07)
        done(s)
    nm = "ladder_joint"
    if want(nm):   # Full on Low with no reducer: the shared lanes line up, the extra ones end at the port
        s = scene(nm, res=(1600, 1000), floor=(-3, 3, -3, 3), floor_z=-0.6)
        chain(s, built, ["DC_Tray_StraightL_Full", "DC_Tray_StraightL_Low"], x0=-1.5, paint="blue")
        s.camera((-0.55, 0.85, 0.75), (0.0, 0.0, 0.05), 35)
        s.caption("FULL | LOW (no reducer)", (0.0, 0.0, 0.32), 0.04)
        done(s)


CHAIN = ["DC_Tray_StraightL_Full", "DC_Tray_StraightS_Full", "DC_Tray_Reducer_Full", "DC_Tray_StraightS_Moderate",
         "DC_Tray_Reducer_Moderate", "DC_Tray_StraightS_Low", "DC_Tray_Reducer_Low", "DC_Tray_StraightS_Empty"]


def chains(built):
    if not all(n in built for n in CHAIN):
        return
    x0 = -2.25
    nm = "chain_34"
    if want(nm):
        s = scene(nm, res=(2200, 1000), floor=(-3, 3, -2, 2), floor_z=-0.6)
        chain(s, built, CHAIN, x0=x0, paint="blue")
        s.camera((-1.9, 1.9, 1.15), (-0.2, 0.0, 0.0), 30)
        done(s)
    nm = "chain_top"
    if want(nm):
        s = scene(nm, res=(2400, 700), floor=(-3, 3, -2, 2), floor_z=-0.6)
        joints = chain(s, built, CHAIN, x0=x0, paint="blue")
        ortho(s, (0.0, 0.0, 4.0), (0.0, 0.0001, 0.0), 4.7)
        del joints
        done(s)
    joints = []
    x = x0
    for n in CHAIN[:-1]:
        x += _len(n)
        joints.append((x, n))
    for k, (xj, n) in enumerate(joints):
        nm = f"chain_joint_{k}"
        if not want(nm):
            continue
        s = scene(nm, res=(1300, 900), floor=(-3, 3, -2, 2), floor_z=-0.6)
        chain(s, built, CHAIN, x0=x0, paint="blue")
        s.camera((xj - 0.35, 0.55, 0.45), (xj, 0.0, 0.06), 38)
        done(s)


# ---------------------------------------------------------------------------------------------------- over racks
MIX = ("DC_Srv_Compute", "DC_Srv_Storage", None, "DC_Srv_Switch", "DC_Srv_Compute", "DC_Srv_Blank", "DC_Srv_Storage",
       "DC_Srv_Switch")


def run_racks(built):
    from . import preview_rack_tops as pv_rack_tops
    from . import preview_rack_doors as pv_rack_doors
    need = ("DC_Rack42_Open", "DC_Tray_StraightL_Full", "DC_Tray_StraightS_Full")
    if not all(n in built for n in need):
        return
    half = "DC_Rack24_Open" if "DC_Rack24_Open" in built else "DC_Rack42_Open"
    mix = tuple(m if (m is None or m in built) else None for m in MIX)
    full_top = 2.5
    z0 = full_top + DM.TRAY_HANG
    y0 = DM.TRAY_RACK_Y - 0.25
    for view in ("34", "front", "joint", "below"):
        nm = f"run_racks_{view}"
        if not want(nm):
            continue
        s = scene(nm, res=(2200, 1250), floor=(-2.5, 5.0, -3.0, 4.0), light=1.3)
        for x, n in ((0.0, "DC_Rack42_Open"), (1.0, "DC_Rack42_Open"), (2.0, "DC_Rack42_Open"), (3.0, half)):
            pv_rack_doors.rack(s, built, n, x, 0.0, mix=mix if n != half else mix[:4], working=True)
        piece(s, built, "DC_Tray_StraightL_Full", -1.0, y0, z0, paint="blue")
        piece(s, built, "DC_Tray_StraightS_Full", 1.5, y0, z0, paint="blue")
        piece(s, built, "DC_Tray_StraightS_Full", 2.0, y0, z0, paint="blue")
        pv_rack_tops._interface(s, 1.0, 2.5, full_top)                       # the Drop ghost over rack 2, its waterfalls
        pv_rack_tops._interface(s, 3.0, 2.5 if half.endswith("42_Open") else 1.25, full_top, chute=not half.endswith("42_Open"))
        if view == "34":
            s.camera((-2.6, 4.6, 3.9), (1.2, 0.0, 2.6), 30)
            s.caption("Drop (ghost) over rack 2; Drop + Chute over the half rack", (1.6, 0.6, 3.75), 0.07)
        elif view == "front":
            s.camera((1.3, 7.5, 2.9), (1.3, 0.0, 2.6), 35)
        elif view == "joint":
            s.camera((0.1, 1.5, 3.45), (0.5, 0.1, 3.05), 35)
        else:
            s.camera((-0.6, 1.8, 1.7), (0.6, 0.1, 3.0), 30)
        sun(s, 4.0)
        done(s)


# ---------------------------------------------------------------------------------------------------- the 20 m run
def run20(built):
    L, S = "DC_Tray_StraightL_Full", "DC_Tray_StraightS_Full"
    if L not in built or S not in built:
        return
    names = [L] * 13 + [S]
    for d in (2, 10, 30, 60):
        nm = f"run20_{d}m"
        if not want(nm):
            continue
        s = scene(nm, res=(1800, 1000), floor=(-40, 60, -40, 40), light=1.6)
        sun(s)
        mid = Vector((10.0, 0.0, 2.6))
        direction = Vector((-0.35, 1.0, 0.25)).normalized() if d > 2 else Vector((-0.6, 1.0, 0.45)).normalized()
        cam = mid + direction * d if d > 2 else Vector((0.4, 1.2, 3.4))
        tgt = mid if d > 2 else Vector((1.5, 0.0, 2.6))
        chain(s, built, names, x0=0.0, z0=2.5, paint="blue", lod=None, cam=cam)
        s.camera(tuple(cam), tuple(tgt), 35)
        s.caption(f"camera {d} m: LOD0 < {LOD_BANDS[0]:.0f} m, LOD1 < {LOD_BANDS[1]:.0f} m, LOD2 < {LOD_BANDS[2]:.0f} m, "
                  "then the last LOD (illustrative bands)", tuple(tgt + Vector((0, 0, 0.6 + d * 0.06))), 0.03 + d * 0.004)
        done(s)


# ---------------------------------------------------------------------------------------------------- mounting
def _ghost_hints(s, built, name, M):
    """The block's mount hint boxes (green ghosts) at the block matrix M (centred frame)."""
    for kind, ob in built[name]["collision"]:
        if kind != "mount":
            continue
        me = ob.data.copy()
        me.materials.clear()
        me.materials.append(PM.get("GhostMount"))
        g = bpy.data.objects.new("hint_" + ob.name, me)
        g.matrix_world = M
        s.link(g)


def mounts(built):
    n = "DC_Tray_StraightS_Full"
    if n not in built:
        return
    for kind in ("ceiling", "wall", "floor"):
        nm = f"mount_{kind}"
        if not want(nm):
            continue
        s = scene(nm, res=(1500, 1000), floor=(-2, 2, -2, 2), floor_z=0.0)
        z0 = {"ceiling": 1.0, "wall": 1.0, "floor": 0.0}[kind]
        piece(s, built, n, -0.25, -0.25, z0, paint="keen")
        M = T(0.0, 0.0, z0 + 0.125)
        _ghost_hints(s, built, n, M)
        if kind == "ceiling":
            box(s, "slab", (-0.75, -0.75, z0 + 0.25), (0.75, 0.75, z0 + 0.35), "Grey")
            s.camera((-0.9, 1.1, 0.55), (0.0, 0.0, 1.05), 35)
        elif kind == "wall":
            box(s, "wall", (-0.75, -0.35, 0.0), (0.75, -0.25, 1.6), "Grey")
            s.camera((-0.8, 1.0, 1.55), (0.0, -0.1, 1.05), 35)
        else:
            s.camera((-0.9, 1.0, 0.75), (0.0, 0.0, 0.08), 35)
        s.caption({"ceiling": "ceiling-hung: rod plates on the slab (green = mount hints)",
                   "wall": "wall-mounted: strut end plate on the wall",
                   "floor": "floor-standing: on the strut"}[kind], (0.0, 0.0, z0 + 0.5), 0.035)
        done(s)


# ---------------------------------------------------------------------------------------------------- paints, LODs
def paints(built):
    names = ["DC_Tray_StraightL_Full", "DC_Tray_StraightS_Full", "DC_Tray_StraightL_Moderate"]
    if not all(n in built for n in names):
        return
    for paint in ("keen", "blue", "teal", "black"):
        nm = f"paint_{paint}"
        if not want(nm):
            continue
        s = scene(nm, res=(1600, 900), floor=(-3, 3, -3, 3), floor_z=-0.6)
        chain(s, built, names, x0=-1.75, paint=paint)
        s.camera((-1.9, 1.7, 1.15), (0.0, 0.0, 0.0), 32)
        s.caption(f"paint: {paint} (the data cables; the basket is fixed steel)", (0.0, 0.0, 0.45), 0.06)
        done(s)


def lods(built, names=("DC_Tray_StraightS_Full", "DC_Tray_StraightL_Full", "DC_Tray_Reducer_Full",
                        "DC_Tray_StraightS_Low", "DC_Tray_StraightL_Empty")):
    for n in names:
        nm = f"lods_{n}"
        if n not in built or not want(nm):
            continue
        k = len(built[n]["lods"])
        L, W = _len(n), CELL * catalog.BY_NAME[n].cells[2]
        pitch, Lc = (0.75, L) if W <= 0.5 else (W + 0.3, max(L, 0.5 * (W + 0.3) * k))   # (straights as in the catalogue)
        for view in ("34", "below"):
            s = scene(f"{nm}_{view}", res=(2200, 900), floor=(-4, 4, -3, 3) if view == "34" else None, floor_z=-0.8)
            if view == "34":
                s.camera((-3.0 - Lc, 0.3, 2.0 + Lc * 0.4), (0.0, 0.0, 0.0), 32)
            else:
                s.camera((-2.6 - Lc, 0.2, -1.4), (0.0, 0.0, 0.1), 32)
            for i in range(k):
                y = (i - (k - 1) / 2) * pitch
                piece(s, built, n, -L / 2, y - W / 2, 0.0, lod=i, paint="blue")
                s.caption(f"LOD{i}", (-L / 2 - 0.25, y, 0.15), 0.06)
            done(s)


# ---------------------------------------------------------------------------------------------------- card choice
CARDS = (("GratingMetallic", None), ("MetalPerforationSteel", None),
         ("ConstructionMesh01", "Constructions/Perforated/ConstructionMesh/ConstructionMesh01/ConstructionMesh01"),
         ("ConstructionMesh05", "Constructions/Perforated/ConstructionMesh/ConstructionMesh05/ConstructionMesh05"))


def _card_mat(name, rel):
    """Preview stand-in for a candidate card: the game's colour (_cm) and alpha (_add alpha), clipped, two-sided."""
    if rel is None:
        return PM.get("GratingMetallic:keen" if name == "GratingMetallic" else "Perf")
    key = "pv_card_" + name
    if key in bpy.data.materials:
        return bpy.data.materials[key]
    cm, add = (PM._dds_png(os.path.join(PM.GAME_MATS, rel + suf + ".dds")) for suf in ("_cm", "_add"))
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    t1 = nt.nodes.new("ShaderNodeTexImage")
    t1.image = PM._img(cm)
    t2 = nt.nodes.new("ShaderNodeTexImage")
    t2.image = PM._img(add, noncolor=True)
    nt.links.new(t1.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(t2.outputs["Alpha"], b.inputs["Alpha"])
    b.inputs["Metallic"].default_value = 0.8
    b.inputs["Roughness"].default_value = 0.45
    for attr, val in (("surface_render_method", "DITHERED"), ("blend_method", "CLIP"), ("use_backface_culling", False)):
        try:
            setattr(m, attr, val)
        except (AttributeError, TypeError):
            pass
    return m


def card_compare(built):
    n = "DC_Tray_StraightL_Full"
    nm = "card_compare"
    if n not in built or len(built[n]["lods"]) < 4 or not want(nm):
        return
    for view in ("34", "below"):
        s = scene(f"{nm}_{view}", res=(2200, 1100), floor=(-4, 4, -3, 3) if view == "34" else None, floor_z=-0.8)
        if view == "34":
            s.camera((-2.3, 1.5, 1.5), (0.1, 0.0, 0.0), 32)
        else:
            s.camera((-2.2, 1.2, -1.2), (0.1, 0.0, 0.1), 32)
        labels = []
        for k, (cname, rel) in enumerate(CARDS):
            y = (k - 1.5) * 0.75
            c = bpy.data.collections.new(f"card_{cname}")
            bpy.context.scene.collection.children.link(c)
            for o in built[n]["lods"][2][1]:
                cp = o.copy()
                cp.data = o.data.copy()
                c.objects.link(cp)
                for i, sl in enumerate(cp.material_slots):
                    base = sl.material.name.split(".")[0] if sl.material else ""
                    cp.material_slots[i].material = (_card_mat(cname, rel) if base == "GratingMetallic"
                                                     else PM.get(PM.keen_key(base, "keen")))
            PV._exclude(c)
            s.inst(c, T(0.0, y, 0.125))
            labels.append((cname, y))
        for cname, y in labels:
            s.caption(cname, (-1.05, y, 0.2), 0.05)
        done(s)


# ---------------------------------------------------------------------------------------------------- vanilla
def vanilla(built):
    nm = "vanilla_compare"
    if "DC_Tray_StraightL_Full" not in built or not want(nm):
        return
    s = scene(nm, res=(2200, 1100), floor=(-4, 4, -3, 3))
    s.camera((-4.2, 3.4, 2.6), (0.0, 0.0, 0.2), 32)
    chain(s, built, ["DC_Tray_StraightL_Full", "DC_Tray_Reducer_Full", "DC_Tray_StraightS_Moderate"]
          if "DC_Tray_Reducer_Full" in built else ["DC_Tray_StraightL_Full"], x0=-1.25, z0=0.0, paint="keen")
    s.caption("OURS: StraightL + Reducer + StraightS (keen grey paint)", (0.0, 0.0, 0.45), 0.06)
    for rel, y, label in (("Walls/Inserts/Pipes/Models/NonFractured/WallInsertPipes.fbx", 1.3, "vanilla WallInsertPipes"),
                          ("Catwalks/CatwalkNarrowBase/250/Models/NonFractured/CatwalkNarrowBase_250.fbx", -1.5,
                           "vanilla CatwalkNarrowBase_250")):
        c, lo, hi = PV.vanilla(rel)
        ctr = (lo + hi) / 2
        s.inst(c, T(0.0, y, 0.0) @ T(-ctr.x, -ctr.y, -lo.z))
        s.caption(label, (0.0, y, hi.z - lo.z + 0.25), 0.06)
    done(s)


# ---------------------------------------------------------------------------------------------------- basket steel
STEELS = (("BrushedMetal", "Brushed"), ("Chrome", "Chrome"), ("MetalDull", "MetalDull"))


def basket_compare(built):
    """The fixed basket steel, by comparison (the data cables keep the paint; blue here)."""
    n = "DC_Tray_StraightL_Full"
    if n not in built:
        return
    for view in ("34", "close"):
        nm = f"basket_compare_{view}"
        if not want(nm):
            continue
        s = scene(nm, res=(2200, 1100), floor=(-4, 4, -3, 3), floor_z=-0.8)
        if view == "34":
            s.camera((-2.6, 1.9, 1.7), (0.1, 0.0, 0.0), 32)
        else:
            s.camera((-1.05, 0.95, 0.55), (-0.5, 0.0, 0.05), 35)
        for k, (steel, key) in enumerate(STEELS):
            y = (k - 1) * 0.75
            c = bpy.data.collections.new(f"steel_{steel}")
            bpy.context.scene.collection.children.link(c)
            for o in built[n]["lods"][0][1]:
                cp = o.copy()
                cp.data = o.data.copy()
                c.objects.link(cp)
                for i, sl in enumerate(cp.material_slots):
                    base = sl.material.name.split(".")[0] if sl.material else ""
                    wire = o.name.split(".")[0].endswith("_wire")
                    cp.material_slots[i].material = PM.get(key) if wire else PM.get(PM.keen_key(base, "blue"))
            PV._exclude(c)
            s.inst(c, T(0.0, y, 0.125))
            s.caption(steel, (-0.95, y, 0.22), 0.05)
        done(s)


# ---------------------------------------------------------------------------------------------------- turns
TURNS = ("TurnH", "TurnUp", "TurnDown")


def _placed_matrix(Tr, name):
    """The Blender matrix of a built (centred) model whose plan (box-corner frame) is placed by Transform Tr."""
    from mathutils import Matrix
    half = TP.plan(catalog.BY_NAME[name]).size / 2
    M = Matrix.Identity(4)
    for i in range(3):
        for j in range(3):
            M[i][j] = float(Tr.R[i][j])
        M[i][3] = float(Tr.d[i])
    return M @ T(*half)


def route(s, built, steps, start=None, paint="blue", lod=0):
    """Pieces joined port to port, floor to floor (tray_plan.place, as the contract tests join them): steps =
    [(name, in port, out port)], each in port onto the previous piece's out port; the first placed by `start` (a
    tray_plan.Transform of its box-corner frame). Returns [(name, Transform, plan)]: the joints are their ports."""
    out, prev = [], None
    for name, pin, pout in steps:
        pl = TP.plan(catalog.BY_NAME[name])
        Tr = (start or TP.Transform.identity()) if prev is None else TP.place(pl, pin, prev)
        lv = min(lod, len(built[name]["lods"]) - 1)
        s.inst(PV.painted(built, name, lv, paint), _placed_matrix(Tr, name))
        out.append((name, Tr, pl))
        prev = pl.transformed(Tr).ports[pout]
    return out


def _joint(placed, k, port):
    """World position of piece k's port (a joint) in a route."""
    name, Tr, pl = placed[k]
    return Vector(tuple(Tr(pl.ports[port].o)))


def wall_grid(s, x0, x1, z0, z1, y, step=0.25):
    """A vertical 0.25 m grid board in the x-z plane at y (the side views of the vertical turns)."""
    bm = bmesh.new()
    me = bpy.data.meshes.new("wallgrid")

    def bx(lo, hi, mi):
        vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
        bmesh.ops.scale(bm, vec=Vector(hi) - Vector(lo), verts=vs)
        bmesh.ops.translate(bm, vec=(Vector(lo) + Vector(hi)) / 2, verts=vs)
        for f in {f for v in vs for f in v.link_faces}:
            f.material_index = mi
    bx((x0, y, z0), (x1, y + 0.01, z1), 0)          # the board, its lines on the face towards -y (the camera)
    x = x0
    while x <= x1 + 1e-6:
        bx((x - 0.003, y - 0.0006, z0), (x + 0.003, y, z1), 1)
        x += step
    z = z0
    while z <= z1 + 1e-6:
        bx((x0, y - 0.0006, z - 0.003), (x1, y, z + 0.003), 1)
        z += step
    bm.to_mesh(me)
    me.materials.append(PM.get("Floor"))
    me.materials.append(PM.get("Darker"))
    s.link(bpy.data.objects.new("wallgrid", me))


def turn_closeups(built):
    """The bend's wire mesh (radial U-wires, faceted floor and wall wires, the safety edge) and its radial straps."""
    H, U, D = "DC_Tray_TurnH_", "DC_Tray_TurnUp_", "DC_Tray_TurnDown_"
    S = "DC_Tray_StraightS_"
    shots = {   # name: (steps, camera, target, lens): TurnH's port a at x 0, its arc centre at (0.05, 0.45) here
        "close_bend_mesh_above": ([(S + "Empty", "a", "b"), (H + "Empty", "a", "b")],
                                  (0.25, -0.75, 0.75), (0.75, 0.15, 0.04), 32),
        "close_bend_mesh_below": ([(S + "Empty", "a", "b"), (H + "Empty", "a", "b")],
                                  (0.55, -0.55, -0.55), (0.80, 0.15, 0.03), 34),
        "close_bend_edge": ([(H + "Moderate", "a", "b")], (1.15, -0.45, 0.42), (0.80, 0.0, 0.12), 38),
        "close_bend_straps": ([(H + "Full", "a", "b")], (0.10, -0.55, 0.70), (0.42, 0.10, 0.08), 34),
        "close_bend_strut": ([(H + "Full", "a", "b")], (1.05, -0.55, -0.35), (0.62, 0.12, 0.02), 34),
        "close_turnup_straps": ([(U + "Full", "a", "b")], (0.95, 0.95, 0.40), (0.30, 0.0, 0.25), 32),
        "close_turnup_mesh": ([(U + "Empty", "a", "b")], (1.05, -0.85, 0.05), (0.32, 0.0, 0.22), 32),
        "close_turndown_straps": ([(D + "Full", "a", "b")], (0.95, 0.95, 0.75), (0.25, 0.0, 0.25), 32),
        "close_turndown_mesh": ([(D + "Empty", "a", "b")], (-0.55, -0.95, -0.25), (0.18, 0.0, 0.15), 32),
    }
    for nm, (steps, loc, tgt, lens) in shots.items():
        if not want(nm) or not all(n in built for n, _, _ in steps):
            continue
        s = scene(nm, res=(1500, 1000), floor=(-2, 2, -2, 2), floor_z=-1.0)
        route(s, built, steps, start=TP.Transform(np.eye(3), np.array([0.0 if len(steps) == 1 else -0.5, -0.25, 0.0])))
        s.camera(loc, tgt, lens)
        done(s)


def offset_run(built):
    """StraightL -> TurnUp -> StraightS (riser) -> TurnDown (turned 180 deg, entered at b) -> StraightL: the bundles
    continue across all four joints; side view over the 0.25 m grid."""
    names = ["DC_Tray_StraightL_{}", "DC_Tray_TurnUp_{}", "DC_Tray_StraightS_{}", "DC_Tray_TurnDown_{}",
             "DC_Tray_StraightL_{}"]
    ports = [("a", "b"), ("a", "b"), ("a", "b"), ("b", "a"), ("a", "b")]
    for d in ("Full", "Moderate", "Low"):
        steps = [(n.format(d), a, b) for n, (a, b) in zip(names, ports)]
        if not all(n in built for n, _, _ in steps):
            continue
        for view in (("side", "34", "joints") if d == "Full" else ("side",)):
            nm = f"offset_{d}_{view}"
            if not want(nm):
                continue
            s = scene(nm, res=(2200, 1100) if view != "joints" else (2200, 1200), floor=(-3, 6, -3, 3),
                      floor_z=-0.01)
            placed = route(s, built, steps, start=TP.Transform(np.eye(3), np.array([-1.5, -0.25, 0.0])))
            if view == "side":
                wall_grid(s, -1.75, 3.75, 0.0, 1.75, 0.81)
                ortho(s, (1.0, -6.0, 0.6), (1.0, 0.0, 0.6), 5.4)
                s.caption(f"{d}: StraightL > TurnUp > StraightS riser > TurnDown > StraightL (0.25 m grid)",
                          (1.0, 0.0, 1.62), 0.06)
            elif view == "34":
                s.camera((-1.6, 3.4, 2.2), (1.0, 0.0, 0.45), 32)
            else:
                s.camera((0.95, 1.25, 1.15), (0.35, 0.0, 0.55), 30)
            done(s)
        # every joint close up (Full)
        if d != "Full":
            continue
        joints = [_joint(placed, k, ports[k][1]) for k in range(4)]
        for k, p in enumerate(joints):
            nm = f"offset_joint_{k}"
            if not want(nm):
                continue
            s = scene(nm, res=(1300, 900), floor=(-3, 6, -3, 3), floor_z=-0.01)
            route(s, built, steps, start=TP.Transform(np.eye(3), np.array([-1.5, -0.25, 0.0])))
            s.camera(tuple(p + Vector((-0.30, 0.55, 0.30))), tuple(p + Vector((0.0, 0.0, 0.03))), 36)
            done(s)


def u_route(built):
    """A horizontal U: StraightL -> TurnH -> 1.5 m of straights (an aisle) -> TurnH -> StraightL back, Full."""
    L, H = "DC_Tray_StraightL_Full", "DC_Tray_TurnH_Full"
    if L not in built or H not in built:
        return
    steps = [(L, "a", "b"), (H, "a", "b"), (L, "a", "b"), (H, "a", "b"), (L, "a", "b")]
    for view in ("top", "34", "turn"):
        nm = f"uroute_{view}"
        if not want(nm):
            continue
        s = scene(nm, res=(2000, 1300), floor=(-3, 3, -2, 4), light=1.1)
        route(s, built, steps, start=TP.Transform(np.eye(3), np.array([-1.5, -0.25, 0.0])))
        if view == "top":
            ortho(s, (-0.3, 1.25, 5.0), (-0.3, 1.2501, 0.0), 4.6)
        elif view == "34":
            s.camera((-3.2, -2.0, 2.8), (-0.2, 1.1, 0.0), 30)
        else:
            s.camera((-0.4, -0.5, 1.1), (0.3, 0.55, 0.0), 32)
        done(s)


def turn_joints(built):
    """A TurnH joined to a StraightS at every density (rows), and each density's joint close up."""
    D_ = [d for d in D if f"DC_Tray_TurnH_{d}" in built and f"DC_Tray_StraightS_{d}" in built]
    if not D_:
        return
    nm = "turn_joint_ladder"
    if want(nm):
        s = scene(nm, res=(2000, 1300), floor=(-3, 4, -3, 3), floor_z=-0.01)
        for k, d in enumerate(D_):
            route(s, built, [(f"DC_Tray_StraightS_{d}", "a", "b"), (f"DC_Tray_TurnH_{d}", "a", "b"),
                             (f"DC_Tray_StraightS_{d}", "a", "b")],
                  start=TP.Transform(np.eye(3), np.array([k * 1.25 - 2.0, -1.0, 0.0])))
        s.camera((0.6, -4.8, 3.3), (0.6, 0.15, 0.0), 32)
        for k, d in enumerate(D_):
            s.caption(d.upper(), (k * 1.25 - 1.75, -1.25, 0.25), 0.07)
        done(s)
    for d in D_:
        for nm, (loc, tgt) in ((f"turn_joint_{d}", ((0.95, -0.55, 0.5), (0.5, 0.15, 0.05))),
                               (f"turn_joint_{d}_b", ((0.25, 1.5, 0.55), (0.5, 0.75, 0.05)))):
            if not want(nm):
                continue
            s = scene(nm, res=(1400, 950), floor=(-2, 3, -2, 3), floor_z=-0.01)
            route(s, built, [(f"DC_Tray_StraightS_{d}", "a", "b"), (f"DC_Tray_TurnH_{d}", "a", "b"),
                             (f"DC_Tray_StraightS_{d}", "a", "b")],
                  start=TP.Transform(np.eye(3), np.array([0.0, 0.0, 0.0])))
            s.camera(loc, tgt, 34)
            s.caption(f"StraightS {d} | TurnH {d}", (tgt[0], tgt[1], 0.35), 0.035)
            done(s)
    for shape in ("TurnUp", "TurnDown"):     # the vertical turns at a straight, every density in a row
        names = [(f"DC_Tray_StraightS_{d}", f"DC_Tray_{shape}_{d}") for d in D_ if f"DC_Tray_{shape}_{d}" in built]
        nm = f"turn_joint_ladder_{shape}"
        if not names or not want(nm):
            continue
        s = scene(nm, res=(2000, 1200), floor=(-3, 4, -3, 3), floor_z=-0.01)
        for k, (a, b) in enumerate(names):
            route(s, built, [(a, "a", "b"), (b, "a", "b")],
                  start=TP.Transform(np.eye(3), np.array([-0.5, k * 0.9 - 1.6, 0.0 if shape == "TurnUp" else 0.25])))
        s.camera((1.9, -2.8, 1.6), (0.0, -0.25, 0.25), 32)
        done(s)


def turn_vanilla(built):
    nm = "vanilla_curve_compare"
    if "DC_Tray_TurnH_Full" not in built or not want(nm):
        return
    s = scene(nm, res=(2000, 1100), floor=(-4, 4, -3, 3))
    route(s, built, [("DC_Tray_TurnH_Full", "a", "b")], start=TP.Transform(np.eye(3), np.array([-1.6, -0.4, 0.0])),
          paint="keen")
    s.camera((0.3, -7.0, 4.6), (0.6, 0.0, 0.7), 32)
    s.caption("OURS: TurnH Full (0.75 x 0.75 m)", (-1.2, 0.0, 0.5), 0.05)
    c, lo, hi = PV.vanilla("Conveyors/ConveyorCurve/200/Models/NonFractured/LargeConveyorCurve.fbx")
    ctr = (lo + hi) / 2
    s.inst(c, T(1.9, 0.6, 0.0) @ T(-ctr.x, -ctr.y, -lo.z))
    s.caption("vanilla LargeConveyorCurve (2.5 m)", (1.9, 0.6, hi.z - lo.z + 0.25), 0.09)
    done(s)


def render_turns(built):
    pieces(built, only=TURNS)
    turn_closeups(built)
    offset_run(built)
    u_route(built)
    turn_joints(built)
    turn_vanilla(built)
    lods(built, names=[f"DC_Tray_{t}_{d}" for t in TURNS for d in ("Full", "Low")])


# ---------------------------------------------------------------------------------------------------- junctions (7)
JUNCTIONS = ("Tee", "Cross")
ORIGIN = TP.Transform(np.eye(3), np.zeros(3))      # a piece's box corner at the world origin: plan frame = world


def attach(s, built, name, pin, onto, paint="blue", lod=0):
    """One piece joined by its port `pin` onto a placed port `onto` (a branch off a junction); returns (name, Tr, plan)
    like route()."""
    pl = TP.plan(catalog.BY_NAME[name])
    Tr = TP.place(pl, pin, onto)
    s.inst(PV.painted(built, name, min(lod, len(built[name]["lods"]) - 1), paint), _placed_matrix(Tr, name))
    return name, Tr, pl


def _port(placed, port):
    name, Tr, pl = placed
    return pl.transformed(Tr).ports[port]


def junction_closeups(built):
    """The hero details: the split collar (Moderate: open to view; Full: under the dressed top layer), the crossover
    saddle (Empty: the bare formed deck, legs, feet, lips, rolled ends and stencil; Full: the stack on it, its straps
    tied down), the wall step-down at a port, a fillet corner's floor, and the Tee's branch mouth."""
    T_, X_ = "DC_Tray_Tee_", "DC_Tray_Cross_"
    shots = {   # name: (piece, camera, target, lens), the piece's box corner at the origin (plan frame = world)
        "close_collar_Moderate": (T_ + "Moderate", (-0.06, 0.06, 0.26), (0.13, 0.25, 0.07), 30),
        "close_collar_Moderate_side": (T_ + "Moderate", (0.16, -0.10, 0.20), (0.125, 0.25, 0.07), 28),
        "close_collar_Full": (T_ + "Full", (-0.08, 0.02, 0.30), (0.13, 0.25, 0.08), 30),
        "close_saddle_Empty": (X_ + "Empty", (-0.05, 0.12, 0.55), (0.5, 0.5, 0.11), 30),
        "close_saddle_Empty_low": (X_ + "Empty", (0.12, -0.12, 0.20), (0.5, 0.42, 0.10), 30),
        "close_saddle_Empty_below": (X_ + "Empty", (0.15, 0.05, -0.45), (0.5, 0.5, 0.08), 30),
        "close_saddle_Full": (X_ + "Full", (-0.20, 0.18, 0.55), (0.5, 0.5, 0.15), 30),
        "close_saddle_ties": (X_ + "Full", (0.10, 0.28, 0.36), (0.29, 0.40, 0.15), 30),
        "close_saddle_roll": (X_ + "Full", (0.30, -0.20, 0.18), (0.45, 0.24, 0.12), 30),
        "close_saddle_stencil": (X_ + "Moderate", (-0.12, 0.62, 0.20), (0.26, 0.50, 0.13), 30),
        "close_wall_step": (T_ + "Empty", (-0.12, -0.32, 0.24), (0.07, 0.04, 0.13), 30),
        "close_wall_step_Full": (T_ + "Full", (1.12, -0.30, 0.26), (0.93, 0.05, 0.12), 30),
        "close_fillet": (T_ + "Empty", (0.02, 0.92, 0.45), (0.25, 0.50, 0.06), 30),
        "close_fillet_below": (T_ + "Empty", (0.10, 0.95, -0.30), (0.26, 0.50, 0.03), 30),
        "close_branch_Full": (T_ + "Full", (0.55, 1.15, 0.55), (0.50, 0.45, 0.06), 30),
    }
    for nm, (name, loc, tgt, lens) in shots.items():
        if not want(nm) or name not in built:
            continue
        s = scene(nm, res=(1500, 1000), floor=(-2, 3, -2, 3), floor_z=-1.0)
        route(s, built, [(name, "a", "b")], start=ORIGIN)
        s.camera(loc, tgt, lens)
        done(s)


def _run_steps(d):
    S, L = f"DC_Tray_StraightS_{d}", f"DC_Tray_StraightL_{d}"
    return [(L, "a", "b"), (f"DC_Tray_TurnH_{d}", "a", "b"), (S, "a", "b"), (f"DC_Tray_Tee_{d}", "a", "b"),
            (S, "a", "b"), (f"DC_Tray_Cross_{d}", "a", "b"), (f"DC_Tray_TurnUp_{d}", "a", "b"), (S, "a", "b"),
            (f"DC_Tray_TurnDown_{d}", "b", "a"), (L, "a", "b")]


def _place_run(d):
    """The full junction run (plan §Previews; the anti-goal #1 proof), placed port to port as the contract tests join
    pieces: StraightL -> TurnH -> StraightS -> Tee (a branch run off c) -> StraightS -> Cross (crossing runs off c and
    d) -> TurnUp -> riser -> TurnDown -> StraightL. -> ([(name, Transform, plan)], [(placed, port) per joint])."""
    steps = _run_steps(d)
    out, joints, prev = [], [], None
    for k, (name, pin, pout) in enumerate(steps):
        pl = TP.plan(catalog.BY_NAME[name])
        Tr = TP.Transform(np.eye(3), np.array([-1.5, -0.25, 0.0])) if prev is None else TP.place(pl, pin, prev)
        out.append((name, Tr, pl))
        prev = pl.transformed(Tr).ports[pout]
        if k < len(steps) - 1:
            joints.append(((name, Tr, pl), pout))

    def off(name, pin, onto):
        pl = TP.plan(catalog.BY_NAME[name])
        Tr = TP.place(pl, pin, onto)
        out.append((name, Tr, pl))
        return name, Tr, pl
    tee, cross = out[3], out[5]
    off(f"DC_Tray_StraightL_{d}", "a", _port(tee, "c"))
    joints.append((tee, "c"))
    for port in ("c", "d"):
        x = off(f"DC_Tray_StraightS_{d}", "a", _port(cross, port))
        joints.append((cross, port))
        off(f"DC_Tray_StraightS_{d}", "a", _port(x, "b"))
    return out, joints


def _run_bounds(d):
    """The placed run's extent (world x, y, z min / max) from every piece's cell box."""
    placed, _ = _place_run(d)
    pts = []
    for _, Tr, pl in placed:
        for i in (0, 1):
            for j in (0, 1):
                for k in (0, 1):
                    pts.append(Tr(pl.size * np.array([i, j, k])))
    pts = np.array(pts)
    return pts.min(axis=0), pts.max(axis=0)


def junction_run(s, built, d, paint="blue"):
    placed, joints = _place_run(d)
    for name, Tr, _ in placed:
        s.inst(PV.painted(built, name, 0, paint), _placed_matrix(Tr, name))
    return placed, joints


def junction_runs(built):
    """The run at every density (overview, top), and at Full and Moderate a camera on every joint."""
    for d in D:
        if not all(n in built for n, _, _ in _run_steps(d)):
            continue
        for view in ("34", "top"):
            nm = f"jrun_{d}_{view}"
            if not want(nm):
                continue
            lo, hi = _run_bounds(d)
            c = (lo + hi) / 2
            span = float(max(hi[0] - lo[0], (hi[1] - lo[1]) * 2400 / 1400)) + 0.6
            s = scene(nm, res=(2400, 1400), floor=(lo[0] - 3, hi[0] + 3, lo[1] - 3, hi[1] + 3), floor_z=-0.01,
                      light=1.2)
            junction_run(s, built, d)
            if view == "34":
                s.camera((c[0] - 0.30 * span, c[1] - 0.42 * span, 0.36 * span), (c[0], c[1], 0.3), 32)
            else:
                ortho(s, (c[0], c[1], 8.0), (c[0], c[1] + 0.0001, 0.0), span)
            s.caption(f"{d.upper()}: StraightL > TurnH > S > TEE (branch) > S > CROSS (crossing) > TurnUp > riser > "
                      "TurnDown > StraightL", (c[0], lo[1] - 0.4, 1.2), 0.07)
            sun(s, 3.0)
            done(s)
        if d not in ("Full", "Moderate"):
            continue
        _, joints = _place_run(d)
        for k, (pc, port) in enumerate(joints):
            nm = f"jrun_{d}_joint_{k:02d}"
            if not want(nm):
                continue
            pt = _port(pc, port)
            p, t = Vector(tuple(pt.o)), Vector(tuple(pt.t))
            side = Vector((-t.y, t.x, 0.0)) if abs(t.z) < 0.5 else Vector((0.0, 1.0, 0.0))
            s = scene(nm, res=(1300, 900), floor=(-4, 8, -5, 5), floor_z=-0.01)
            junction_run(s, built, d)
            s.camera(tuple(p - t * 0.30 + side * 0.45 + Vector((0, 0, 0.32))), tuple(p + Vector((0, 0, 0.05))), 34)
            s.caption(f"{pc[0].replace('DC_Tray_', '')} port {port}", tuple(p + Vector((0, 0, 0.30))), 0.03)
            done(s)


RACK = "DC_Rack42_Open"


def _ghosts_row(s, xs, M, full_top):
    """Drop ghosts (preview_rack_tops._interface) over the racks at rack-local xs, moved by M (a turned row)."""
    from . import preview_rack_tops as pv_rack_tops
    before = set(bpy.data.objects)
    for x in xs:
        pv_rack_tops._interface(s, x, full_top, full_top)
    for o in set(bpy.data.objects) - before:
        o.matrix_world = M @ o.matrix_world


def grid_layout(built):
    """An overhead grid over a rack row: two rows of four racks facing each other across a 1.0 m aisle, a tray over
    each row (Drop ghosts over its racks), joined by a connector: a Tee on row A's tray, two straights across the
    aisle, a Cross on row B's tray whose far port feeds on over row B (to the next room)."""
    from . import preview_rack_doors as pv_rack_doors
    d = "Full"
    need = [RACK, f"DC_Tray_Tee_{d}", f"DC_Tray_Cross_{d}", f"DC_Tray_StraightS_{d}", f"DC_Tray_StraightL_{d}"]
    if not all(n in built for n in need):
        return
    full_top = 2.5
    z0 = full_top + DM.TRAY_HANG
    YB = 3.25                                  # row B's rack centres (turned 180 deg: fronts face row A)
    S, L, Te, X = (f"DC_Tray_{v}_{d}" for v in ("StraightS", "StraightL", "Tee", "Cross"))
    mix = tuple(m if (m is None or m in built) else None for m in MIX)
    for view in ("top", "34", "aisle", "below"):
        nm = f"grid_{view}"
        if not want(nm):
            continue
        s = scene(nm, res=(2400, 1600), floor=(-3.0, 6.0, -3.0, 6.5), light=1.3)
        for x in range(4):
            pv_rack_doors.rack(s, built, RACK, float(x), 0.0, mix=mix[:4], working=True)
            pv_rack_doors.rack(s, built, RACK, float(x), YB, rot=180.0, mix=mix[4:], working=True)
        # row A tray (centreline y 0.125): S | Drop 0 | Tee over rack 1 | Drop 2 | Drop 3 | S
        ya = DM.TRAY_RACK_Y - 0.25
        piece(s, built, S, -1.0, ya, z0)
        tee = route(s, built, [(Te, "a", "b")], start=TP.Transform(np.eye(3), np.array([0.5, ya, z0])))[0]
        piece(s, built, S, 3.5, ya, z0)
        _ghosts_row(s, (0.0, 2.0, 3.0), T(0, 0, 0), full_top)
        # row B tray (turned: centreline y = YB - 0.125): S | Drop | Cross over rack 1 | Drop | Drop | S
        yb = YB - DM.TRAY_RACK_Y - 0.25
        piece(s, built, S, -1.0, yb, z0)
        cross = route(s, built, [(X, "a", "b")], start=TP.Transform(np.eye(3), np.array([0.5, yb - 0.25, z0])))[0]
        piece(s, built, S, 3.5, yb, z0)
        _ghosts_row(s, (-0.0, -2.0, -3.0), T(0, YB, 0) @ Rz(180.0), full_top)
        # the connector across the aisle (Tee c -> Cross c) and the feeder on from the Cross's d
        a = attach(s, built, L, "a", _port(tee, "c"))
        attach(s, built, S, "a", _port(a, "b"))
        f1 = attach(s, built, L, "a", _port(cross, "d"))
        attach(s, built, L, "a", _port(f1, "b"))
        if view == "top":
            ortho(s, (1.5, 1.6, 12.0), (1.5, 1.6001, 0.0), 7.0)
        elif view == "34":
            s.camera((-3.6, -3.4, 6.4), (1.6, 1.7, 2.6), 30)
        elif view == "aisle":
            s.camera((4.6, 1.6, 2.0), (1.0, 1.6, 3.0), 34)
        else:
            s.camera((1.6, 1.0, 1.7), (1.0, 2.6, 3.0), 30)
        sun(s, 4.0)
        done(s)


def junction_vanilla(built):
    nm = "vanilla_junctionT_compare"
    if "DC_Tray_Tee_Full" not in built or not want(nm):
        return
    s = scene(nm, res=(2000, 1100), floor=(-4, 4, -3, 3))
    route(s, built, [("DC_Tray_Tee_Full", "a", "b")], start=TP.Transform(np.eye(3), np.array([-1.6, -0.4, 0.0])),
          paint="keen")
    s.camera((0.0, -5.6, 3.4), (0.2, 0.3, 0.6), 32)
    s.caption("OURS: Tee Full (1.0 x 0.75 m)", (-1.4, 0.0, 0.5), 0.05)
    c, lo, hi = PV.vanilla("Conveyors/ConveyorJunctionT/250/Models/NonFractured/LargeConveyorJunctionT.fbx")
    from mathutils import Matrix
    k = 2.5 / max(hi - lo)          # this FBX imports at another unit scale: shown at its 2.5 m block size
    ctr = (lo + hi) / 2
    s.inst(c, T(1.6, 0.4, 0.0) @ Matrix.Scale(k, 4) @ T(-ctr.x, -ctr.y, -lo.z))
    s.caption("vanilla LargeConveyorJunctionT (2.5 m block)", (1.6, 0.4, k * (hi.z - lo.z) + 0.25), 0.09)
    done(s)


def junction_ladder(built):
    """Every junction at every density side by side (top, ortho): every collar and hump in one view."""
    for shape in JUNCTIONS:
        names = [f"DC_Tray_{shape}_{d}" for d in D if f"DC_Tray_{shape}_{d}" in built]
        nm = f"ladder_{shape}_top"
        if not names or not want(nm):
            continue
        s = scene(nm, res=(2600, 900), floor=(-4, 4, -3, 3))
        ortho(s, (0.0, 0.0, 5.0), (0.0, 0.0001, 0.0), 5.2)
        for k, n in enumerate(names):
            route(s, built, [(n, "a", "b")], start=TP.Transform(np.eye(3), np.array([k * 1.2 - 2.4, -0.5, 0.0])))
            s.caption(n.rsplit("_", 1)[1].upper(), (k * 1.2 - 1.9, -0.65, 0.3), 0.06)
        done(s)


def render_junctions(built):
    pieces(built, only=JUNCTIONS)
    junction_closeups(built)
    junction_ladder(built)
    junction_runs(built)
    grid_layout(built)
    junction_vanilla(built)
    lods(built, names=[f"DC_Tray_{t}_{d}" for t in JUNCTIONS for d in ("Full", "Low")])




# ------------------------------------------------------------------------------------------------------------- drops
DROPS = ("Drop", "Chute", "Rods")
FULL42, HALF24 = 2.5, 1.25           # rack top planes


def pieces8(built):
    """Every drop piece at 3/4, front (+y, the rack fronts), side (port a's end) and top (ortho)."""
    for n in sorted(built_trays(built) + [b for b in built if catalog.BY_NAME[b].family == "trayrods"],
                    key=lambda k: [b.name for b in catalog.CATALOGUE].index(k)):
        spec = catalog.BY_NAME[n]
        if spec.variant not in DROPS:
            continue
        L, H, W = (CELL * c for c in spec.cells)
        d = 0.9 + 1.05 * max(L, W, H)
        ctr = (0.0, 0.0, H / 2)
        for v in ("34", "front", "side", "top"):
            nm = f"piece_{n}_{v}"
            if not want(nm):
                continue
            s = scene(nm, res=(1300, 1000), floor=(-2, 2, -2, 2), floor_z=-0.002)
            piece(s, built, n, -L / 2, -W / 2, 0.0, paint="blue")
            if v == "34":
                s.camera((-0.6 * d, 0.95 * d, H / 2 + 0.55 * d), ctr, 35)
            elif v == "front":
                s.camera((0.0, 2.6 * d, H / 2 + 0.05), ctr, 45)
            elif v == "side":
                s.camera((-2.6 * d, 0.0, H / 2 + 0.05), ctr, 45)
            else:
                ortho(s, (0.0, 0.0, H + 3.0), (0.0, 0.0001, 0.0), max(L, W * 1300 / 1000) + 0.2)
            done(s)


def _drop_on_rack(s, built, drop, rack_x, full=True, chute=None, paint="blue"):
    """A Drop over a rack at rack_x (rack-local frame = world, rack front +y): its box corner on the rack's grid, the
    tray TRAY_HANG over the full-rack top; over a half rack a Chute stands on the roof in the waterfall column."""
    piece(s, built, drop, rack_x - 0.5, DM.TRAY_RACK_Y - 0.25, FULL42, paint=paint)
    if chute:
        piece(s, built, chute, rack_x - 0.5, DM.TRAY_RACK_Y - 0.25 + 0.5, HALF24, paint=paint)


def landing(built):
    """The brush-plate landings close up ON the real core racks: the 42U (a Drop) and the 24U (a Chute under a
    Drop), open and with doors (open 85 deg), at each top entry; and the half rack's chute foot."""
    from . import preview_rack_doors as pv_rack_doors
    D_ = "DC_Tray_Drop_Full"
    if D_ not in built:
        return
    racks = [r for r in ("DC_Rack42_Open", "DC_Rack42_SplitFront", "DC_Rack24_Open", "DC_Rack24_SplitFront")
             if r in built]
    for r in racks:
        half = r.startswith("DC_Rack24")
        if half and "DC_Tray_Chute" not in built:
            continue
        top = HALF24 if half else FULL42
        for side, sx in (("L", -1), ("R", 1)):
            for view in ("34", "plan", "low"):
                nm = f"land_{r.replace('DC_', '')}_{side}_{view}"
                if not want(nm):
                    continue
                s = scene(nm, res=(1500, 1050), floor=(-3, 3, -3, 3), light=1.2)
                pv_rack_doors.rack(s, built, r, 0.0, 0.0, f=1.0 if "Split" in r else 0.0, working=True)
                _drop_on_rack(s, built, D_, 0.0, chute="DC_Tray_Chute" if half else None)
                p = Vector((sx * DM.WF_X, DM.WF_Y, top))
                if view == "34":
                    s.camera(tuple(p + Vector((sx * 0.32, 0.42, 0.30))), tuple(p + Vector((0, 0, 0.04))), 38)
                elif view == "plan":
                    s.camera(tuple(p + Vector((sx * 0.02, 0.05, 0.62))), tuple(p), 40)
                else:
                    s.camera(tuple(p + Vector((sx * 0.45, 0.55, 0.06))), tuple(p + Vector((0, 0, 0.05))), 36)
                sun(s, 3.0)
                done(s)
    nm = "land_chute_top"
    if "DC_Rack24_Open" in built and "DC_Tray_Chute" in built and want(nm):   # the Drop's collar on the Chute's top
        s = scene(nm, res=(1500, 1050), floor=(-3, 3, -3, 3), light=1.2)
        pv_rack_doors.rack(s, built, "DC_Rack24_Open", 0.0, 0.0, working=True)
        _drop_on_rack(s, built, D_, 0.0, chute="DC_Tray_Chute")
        p = Vector((DM.WF_X, DM.WF_Y, FULL42))
        s.camera(tuple(p + Vector((0.30, 0.42, -0.10))), tuple(p + Vector((0.0, 0.0, 0.0))), 34)
        sun(s, 3.0)
        done(s)
    nm = "land_collar_macro"
    if "DC_Rack42_Open" in built and want(nm):           # the brush collar and its bristles, from above
        s = scene(nm, res=(1500, 1050), floor=(-3, 3, -3, 3), light=1.2)
        pv_rack_doors.rack(s, built, "DC_Rack42_Open", 0.0, 0.0, working=True)
        _drop_on_rack(s, built, D_, 0.0)
        p = Vector((DM.WF_X, DM.WF_Y, FULL42))
        s.camera(tuple(p + Vector((0.09, 0.13, 0.16))), tuple(p + Vector((0.0, 0.0, 0.0))), 40)
        sun(s, 3.0)
        done(s)
    nm = "land_chute_foot"
    if "DC_Rack24_Open" in built and "DC_Tray_Chute" in built and want(nm):
        s = scene(nm, res=(1500, 1050), floor=(-3, 3, -3, 3), light=1.2)
        pv_rack_doors.rack(s, built, "DC_Rack24_Open", 0.0, 0.0, working=True)
        _drop_on_rack(s, built, D_, 0.0, chute="DC_Tray_Chute")
        p = Vector((DM.WF_X, DM.WF_Y, HALF24))
        s.camera(tuple(p + Vector((0.38, 0.55, 0.35))), tuple(p + Vector((-0.02, 0.0, 0.12))), 34)
        sun(s, 3.0)
        done(s)


def guide_closeups(built):
    """The waterfall guide (the moulded radius trough, its ribs and cheeks, the spring clamps on the edge wire), the
    split collar and climb, the straps on the fall: Drop Full and Low, box corner at the origin."""
    shots = {   # name: (piece, camera, target, lens); WF- at x 0.1415, its guide centre (0.1415, 0.4575, 0.592)
        "close_guide_34": ("DC_Tray_Drop_Full", (-0.12, 0.85, 0.95), (0.14, 0.46, 0.64), 34),
        "close_guide_side": ("DC_Tray_Drop_Full", (-0.55, 0.62, 0.66), (0.14, 0.49, 0.62), 36),
        "close_guide_clamps": ("DC_Tray_Drop_Full", (0.30, 0.82, 0.52), (0.15, 0.46, 0.64), 30),
        "close_guide_empty": ("DC_Tray_Drop_Low", (-0.10, 0.80, 0.98), (0.14, 0.46, 0.63), 34),
        "close_climb_Full": ("DC_Tray_Drop_Full", (0.55, 0.05, 0.95), (0.30, 0.33, 0.60), 32),
        "close_climb_Low": ("DC_Tray_Drop_Low", (0.55, 0.05, 0.95), (0.30, 0.33, 0.60), 32),
        "close_fall_straps": ("DC_Tray_Drop_Full", (0.05, 1.25, 0.35), (0.14, 0.56, 0.32), 32),
        "close_drop_below": ("DC_Tray_Drop_Full", (0.30, 1.30, -0.35), (0.40, 0.40, 0.45), 30),
    }
    for nm, (name, loc, tgt, lens) in shots.items():
        if not want(nm) or name not in built:
            continue
        s = scene(nm, res=(1500, 1050), floor=(-2, 3, -2, 3), floor_z=-1.0)
        route(s, built, [(name, "a", "b")], start=ORIGIN)
        s.camera(loc, tgt, lens)
        done(s)


ROW = [("DC_Tray_StraightS_Full", None), ("DC_Tray_Drop_Full", "DC_Rack42_Open"),
       ("DC_Tray_Drop_Full", "DC_Rack42_Open"), ("DC_Tray_Reducer_Full", None),
       ("DC_Tray_Drop_Moderate", "DC_Rack42_Open"), ("DC_Tray_Reducer_Moderate", None),
       ("DC_Tray_Drop_Low", "DC_Rack42_Open"), ("DC_Tray_Drop_Low", "DC_Rack24_Open"),
       ("DC_Tray_Reducer_Low", None), ("DC_Tray_StraightS_Empty", None)]


def rack_row(s, built, paint="blue", rods=True, mix=None, doors=0.0, row=None):
    """The run over a rack row (plan §Previews): StraightS Full -> Drop Full (rack 1) -> Drop Full (rack 2) ->
    Reducer F>M -> Drop Moderate (rack 3) -> Reducer M>L -> Drop Low (rack 4) -> Drop Low over the half rack with a
    Chute -> Reducer L>0 -> StraightS Empty; Rods 1.0 m from every trapeze to a ceiling 1.0 m over the tray.
    -> {rack x: rack name}, the x of every joint, the ceiling height."""
    from . import preview_rack_doors as pv_rack_doors
    x, racks, joints = -1.0, {}, []
    mix = mix if mix is not None else tuple(m if (m is None or m in built) else None for m in MIX)
    top = FULL42 + 0.75
    for name, rack in (row or ROW):
        L = _len(name)
        if rack:
            racks[x + L / 2] = rack
            _drop_on_rack(s, built, name, x + L / 2, chute="DC_Tray_Chute" if rack.startswith("DC_Rack24") else None,
                          paint=paint)
        else:
            piece(s, built, name, x, DM.TRAY_RACK_Y - 0.25, FULL42 + DM.TRAY_HANG, paint=paint)
        if rods and "DC_TrayRods_100" in built:
            piece(s, built, "DC_TrayRods_100", x + L / 2 - 0.25, DM.TRAY_RACK_Y - 0.25, top, paint=paint)
        x += L
        joints.append(x)
    for rx, rack in racks.items():
        if rack in built:
            pv_rack_doors.rack(s, built, rack, rx, 0.0, mix=mix if rack.startswith("DC_Rack42") else mix[:4], working=True,
                    f=doors)
    return racks, joints[:-1], top + 1.0


def ceiling(s, x0, x1, y0, y1, z):
    box(s, "ceiling", (x0, y0, z), (x1, y1, z + 0.12), "Grey")


def row_shots(built):
    need = [n for n, _ in ROW] + ["DC_Tray_Chute", "DC_Rack42_Open", "DC_Rack24_Open"]
    if not all(n in built for n in need):
        return
    views = {   # name: (camera, target, lens)
        "row_34": ((-2.6, 5.2, 4.6), (2.3, 0.2, 2.6), 28),
        "row_front": ((2.3, 8.5, 2.6), (2.3, 0.0, 2.4), 32),
        "row_above": ((2.3, 3.2, 7.0), (2.3, 0.2, 2.6), 28),
        "row_side": ((-3.6, 0.6, 3.0), (2.0, 0.2, 2.9), 30),
        "row_reducer": ((1.7, 1.25, 3.55), (1.75, 0.15, 3.05), 30),
        "row_halfrack": ((5.9, 1.95, 2.2), (5.0, 0.35, 1.9), 30),
        "aisle_eye": ((3.1, 1.45, 1.8), (2.0, 0.15, 3.15), 22),
        "aisle_eye_wide": ((6.4, 1.35, 1.8), (2.4, 0.2, 2.9), 20),
        "aisle_up": ((2.6, 0.95, 1.7), (2.3, 0.35, 3.4), 18),
    }
    for nm, (loc, tgt, lens) in views.items():
        if not want(nm):
            continue
        s = scene(nm, res=(2200, 1300), floor=(-3.0, 8.0, -3.0, 5.0), light=1.3)
        _, _, zc = rack_row(s, built)
        ceiling(s, -2.0, 7.5, -1.2, 1.6, zc)
        s.camera(loc, tgt, lens)
        if nm.startswith("aisle"):
            s.inst(PV.human(), T(3.6, 1.15, 0.0) @ Rz(-60))
        sun(s, 3.5)
        done(s)
    for paint in ("blue", "teal", "black"):
        nm = f"row_paint_{paint}"
        if not want(nm):
            continue
        s = scene(nm, res=(2000, 1200), floor=(-3.0, 8.0, -3.0, 5.0), light=1.3)
        _, _, zc = rack_row(s, built, paint=paint)
        s.camera((-1.2, 3.6, 3.7), (1.6, 0.2, 2.9), 30)
        s.caption(f"paint: {paint} (the data cables and the waterfalls; the basket is fixed steel)", (1.6, 0.4, 3.95),
                  0.06)
        sun(s, 3.5)
        done(s)
    nm = "row_doors_open"
    door = [r for r in ("DC_Rack42_SplitFront", "DC_Rack24_SplitFront") if r in built]
    if len(door) == 2 and want(nm):
        s = scene(nm, res=(2200, 1300), floor=(-3.0, 8.0, -3.0, 5.0), light=1.3)
        rack_row(s, built, doors=1.0, row=[(n, ("DC_Rack42_SplitFront" if r == "DC_Rack42_Open" else
                                                "DC_Rack24_SplitFront") if r else None) for n, r in ROW])
        s.camera((1.0, 3.6, 3.2), (2.3, 0.4, 2.3), 26)
        s.caption("door racks, doors open 85 deg under the Drops (the leaves stay under the rack top)", (2.3, 0.9, 3.6),
                  0.06)
        sun(s, 3.5)
        done(s)
    nm = "row_mockup05b"
    if want(nm):   # the v2 mockup's 05b camera (lens 22, low from the aisle at the reducer and the long drop)
        s = scene(nm, res=(1920, 1080), floor=(-3.0, 8.0, -3.0, 5.0), light=1.3)
        _, _, zc = rack_row(s, built)
        ceiling(s, -2.0, 7.5, -1.2, 1.6, zc)
        s.camera((7.3, 2.4, 3.0), (4.6, 0.1, 2.15), 22)
        sun(s, 3.5)
        done(s)


def hangers(built):
    """Rod hangers from a ceiling with straights: three runs hung at the three rod lengths (0.25, 1.0, 2.0 m) from
    one slab, each on its trapezes' rod plates; and the hardware close up (coupler on the rod plate, the ceiling
    channel and anchor plates)."""
    R = ["DC_TrayRods_025", "DC_TrayRods_100", "DC_TrayRods_200"]
    S, L = "DC_Tray_StraightS_Full", "DC_Tray_StraightL_Full"
    if not all(n in built for n in R + [S, L]):
        return
    zc = 3.4
    for view in ("34", "front", "coupler", "ceiling", "below"):
        nm = f"hangers_{view}"
        if not want(nm):
            continue
        s = scene(nm, res=(2000, 1250), floor=(-3, 4, -3, 3), light=1.2)
        ceiling(s, -1.6, 2.8, -1.4, 1.4, zc)
        for k, r in enumerate(R):
            h = 0.25 * catalog.BY_NAME[r].cells[1]
            y0 = -1.0 + 0.8 * k
            z0 = zc - h - 0.25
            chain(s, built, [L, S], x0=-1.0, y0=y0, z0=z0, paint="blue")
            for xc in (-0.25, 0.75):         # the trapezes: StraightL's centre, StraightS's centre
                piece(s, built, r, xc - 0.25, y0, zc - h, paint="blue")
        if view == "34":
            s.camera((-2.9, 3.4, 1.4), (0.2, -0.1, 2.6), 30)
        elif view == "front":
            s.camera((0.3, 5.2, 2.3), (0.3, 0.0, 2.5), 32)
        elif view == "coupler":     # the coupler nut seated on the StraightS's rod plate (the 1.0 m run)
            p = Vector((0.75, -0.2 + 0.018, zc - 1.0))
            s.camera(tuple(p + Vector((0.28, 0.32, -0.12))), tuple(p + Vector((0, 0, 0.01))), 34)
        elif view == "ceiling":
            p = Vector((0.75, -0.2 + 0.25, zc - 0.03))
            s.camera(tuple(p + Vector((0.40, 0.45, -0.32))), tuple(p), 30)
        else:
            s.camera((0.6, 1.9, 0.9), (0.4, -0.2, 2.9), 26)
        if view in ("34", "front"):
            for k, r in enumerate(R):
                h = 0.25 * catalog.BY_NAME[r].cells[1]
                s.caption(f"{h:.2f} m rods", (-1.3, -1.0 + 0.8 * k + 0.25, zc - h - 0.25 + 0.35), 0.06)
        sun(s, 3.0)
        done(s)


def drop_vanilla(built):
    nm = "vanilla_drop_compare"
    if "DC_Tray_Drop_Full" not in built or not want(nm):
        return
    s = scene(nm, res=(2200, 1100), floor=(-4, 4, -3, 3))
    s.camera((0.6, 5.6, 2.6), (0.6, 0.0, 0.6), 32)
    piece(s, built, "DC_Tray_Drop_Full", -1.9, -0.375, 0.0, paint="keen")
    if "DC_Tray_Chute" in built:
        piece(s, built, "DC_Tray_Chute", -0.6, -0.125, 0.0, paint="keen")
    if "DC_TrayRods_100" in built:
        piece(s, built, "DC_TrayRods_100", 0.65, -0.25, 0.0, paint="keen")
    s.caption("OURS: Drop Full, Chute, Rods 1.0 m (keen grey)", (-0.6, 0.0, 1.45), 0.06)
    for rel, x, label in (("Walls/Inserts/Pipes/Models/NonFractured/WallInsertPipes.fbx", 2.1, "WallInsertPipes"),
                          ("Truss/Struts/Long/Models/NonFractured/TrussFrame_Long.fbx", 3.4, "TrussFrame_Long")):
        try:
            c, lo, hi = PV.vanilla(rel)
        except Exception as e:      # noqa: BLE001 (a missing reference model: the shot goes on without it)
            print("vanilla", rel, e)
            continue
        ctr = (lo + hi) / 2
        s.inst(c, T(x, 0.0, 0.0) @ T(-ctr.x, -ctr.y, -lo.z))
        s.caption(f"vanilla {label}", (x, 0.0, hi.z - lo.z + 0.2), 0.05)
    done(s)


def render_drops(built):
    pieces8(built)
    guide_closeups(built)
    landing(built)
    row_shots(built)
    hangers(built)
    drop_vanilla(built)
    lods(built, names=["DC_Tray_Drop_Full", "DC_Tray_Drop_Low", "DC_Tray_Chute", "DC_TrayRods_100",
                       "DC_TrayRods_025"])


# ---------------------------------------------------------------------------------------------------------- compare
COMPARE_SHAPES = ("StraightS", "StraightL", "TurnH", "TurnUp", "TurnDown", "Tee", "Cross", "Drop", "Reducer")


def compare_shapes(built):
    """Every shape at Full and Low (and the Chute and the 1.0 m rods), 3/4 from front-left-high, the camera 1 m and
    3 m from the piece's centre (the same cameras before and after: DC_PREVIEW_SUB=before|after)."""
    names = [f"DC_Tray_{sh}_{d}" for sh in COMPARE_SHAPES for d in ("Full", "Low")] + ["DC_Tray_Chute",
                                                                                     "DC_TrayRods_100"]
    direction = Vector((-0.55, 0.75, 0.42)).normalized()
    for n in names:
        if n not in built:
            continue
        L, H, W = (CELL * c for c in catalog.BY_NAME[n].cells)
        ctr = Vector((0.0, 0.0, H / 2))
        for dist in (1, 3):
            nm = f"shape_{n.replace('DC_Tray_', '').replace('DC_', '')}_{dist}m"
            if not want(nm):
                continue
            s = scene(nm, res=(1400, 900), floor=(-3, 3, -3, 3), floor_z=-0.002)
            piece(s, built, n, -L / 2, -W / 2, 0.0, paint="blue")
            s.camera(tuple(ctr + direction * dist), tuple(ctr), 30 if dist == 1 else 40)
            done(s)


def detail_shots(built):
    """Close-ups of the details that are easy to get wrong: a free run end and a joint next to it (the caps must not
    show there), the Tee's LOD0 branch peel, the lay at 1 m (banding), the landing collar and the Chute foot (the
    2.5 mm float), the Drop's dressing."""
    S, L = "DC_Tray_StraightS_", "DC_Tray_StraightL_"
    for d in ("Full", "Low"):
        nm = f"end_free_{d}"
        if want(nm) and L + d in built and S + d in built:
            s = scene(nm, res=(1500, 1000), floor=(-2, 3, -2, 3), floor_z=-1.0)
            route(s, built, [(L + d, "a", "b"), (S + d, "a", "b")], start=ORIGIN)
            s.camera((2.45, 0.62, 0.42), (2.0, 0.25, 0.06), 32)       # the StraightS's free port b, and the joint
            done(s)
        nm = f"end_free_{d}_square"
        if want(nm) and S + d in built:
            s = scene(nm, res=(1500, 1000), floor=(-2, 3, -2, 3), floor_z=-1.0)
            route(s, built, [(S + d, "a", "b")], start=ORIGIN)
            s.camera((0.95, 0.30, 0.16), (0.5, 0.25, 0.07), 34)         # nearly end-on into port b
            done(s)
    nm = "joint_Full"
    if want(nm) and L + "Full" in built:
        s = scene(nm, res=(1500, 1000), floor=(-2, 3, -2, 3), floor_z=-1.0)
        route(s, built, [(L + "Full", "a", "b"), (L + "Full", "a", "b")], start=ORIGIN)
        s.camera((1.75, 0.95, 0.42), (1.5, 0.25, 0.06), 30)
        done(s)
    nm = "lay_1m"
    if want(nm) and L + "Full" in built:
        s = scene(nm, res=(1500, 1000), floor=(-2, 3, -2, 3), floor_z=-1.0)
        route(s, built, [(L + "Full", "a", "b")], start=ORIGIN)
        s.camera((0.75, 1.15, 0.55), (0.75, 0.25, 0.06), 34)
        done(s)
    T_ = "DC_Tray_Tee_"
    for nm, name, loc, tgt in (("tee_branch_Full", T_ + "Full", (0.55, 1.15, 0.55), (0.50, 0.45, 0.06)),
                               ("tee_branch_Moderate", T_ + "Moderate", (0.55, 1.15, 0.55), (0.50, 0.45, 0.06)),
                               ("tee_collar_Moderate", T_ + "Moderate", (0.40, 0.95, 0.32), (0.46, 0.38, 0.05)),
                               ("tee_collar_Full", T_ + "Full", (0.40, 0.95, 0.36), (0.46, 0.38, 0.06))):
        if want(nm) and name in built:
            s = scene(nm, res=(1500, 1000), floor=(-2, 3, -2, 3), floor_z=-1.0)
            route(s, built, [(name, "a", "b")], start=ORIGIN)
            s.camera(loc, tgt, 30)
            done(s)
    from . import preview_rack_doors as pv_rack_doors
    D_ = "DC_Tray_Drop_Full"
    if D_ in built and "DC_Rack42_Open" in built:
        for nm, rack, chute, top, off, tgt_dz, lens in (
                ("land_collar_low", "DC_Rack42_Open", None, FULL42, (0.20, 0.30, 0.012), 0.012, 30),
                ("land_chute_foot_low", "DC_Rack24_Open", "DC_Tray_Chute", HALF24, (0.20, 0.30, 0.012), 0.012, 30),
                ("land_collar_34", "DC_Rack42_Open", None, FULL42, (0.32, 0.42, 0.30), 0.04, 38)):
            if not want(nm) or rack not in built or (chute and chute not in built):
                continue
            s = scene(nm, res=(1500, 1050), floor=(-3, 3, -3, 3), light=1.2)
            pv_rack_doors.rack(s, built, rack, 0.0, 0.0, working=True)
            _drop_on_rack(s, built, D_, 0.0, chute=chute)
            p = Vector((DM.WF_X, DM.WF_Y, top))
            s.camera(tuple(p + Vector(off)), tuple(p + Vector((0, 0, tgt_dz))), lens)
            sun(s, 3.0)
            done(s)
    for nm, name, loc, tgt in (("drop_full_climb", D_, (0.55, 0.05, 0.95), (0.30, 0.33, 0.60)),
                               ("drop_full_guide", D_, (-0.12, 0.85, 0.95), (0.14, 0.46, 0.64)),
                               ("drop_full_split", D_, (0.42, 0.72, 0.80), (0.32, 0.335, 0.58)),
                               ("drop_low_split", "DC_Tray_Drop_Low", (0.42, 0.72, 0.80), (0.32, 0.335, 0.58)),
                               ("drop_full_aisle", D_, (1.6, 2.2, -0.3), (0.5, 0.4, 0.45))):
        if want(nm) and name in built:
            s = scene(nm, res=(1500, 1050), floor=(-2, 3, -2, 3), floor_z=-1.0)
            route(s, built, [(name, "a", "b")], start=ORIGIN)
            s.camera(loc, tgt, 32)
            done(s)


def run_shots(built):
    """The long mixed run over a populated rack row (3/4, the aisle at eye level, a worm's-eye view from the floor)
    and the junction network (Full)."""
    need = [n for n, _ in ROW] + ["DC_Tray_Chute", "DC_Rack42_Open", "DC_Rack24_Open"]
    if all(n in built for n in need):
        views = {"run_row_34": ((-2.6, 5.2, 4.6), (2.3, 0.2, 2.6), 28),
                 "run_aisle_eye": ((7.6, 2.3, 1.7), (1.6, 0.3, 2.8), 24),
                 "run_aisle_worm": ((3.2, 1.75, 0.30), (2.2, 0.30, 3.3), 16),
                 "run_mockup05b": ((7.3, 2.4, 3.0), (4.6, 0.1, 2.15), 22)}
        for nm, (loc, tgt, lens) in views.items():
            if not want(nm):
                continue
            s = scene(nm, res=(2000, 1200), floor=(-3.0, 8.0, -3.0, 5.0), light=1.3)
            _, _, zc = rack_row(s, built)
            ceiling(s, -2.0, 7.5, -1.2, 1.6, zc)
            s.camera(loc, tgt, lens)
            if nm == "run_aisle_eye":
                s.inst(PV.human(), T(3.6, 1.15, 0.0) @ Rz(-60))
            sun(s, 3.5)
            done(s)
    nm = "run_junctions_Full"
    if want(nm) and all(f"DC_Tray_{v}_Full" in built for v in ("StraightS", "StraightL", "TurnH", "TurnUp",
                                                                  "TurnDown", "Tee", "Cross")):
        s = scene(nm, res=(2000, 1200), floor=(-3.0, 9.0, -4.0, 5.0))
        junction_run(s, built, "Full")
        lo, hi = _run_bounds("Full")
        c = (Vector(lo) + Vector(hi)) / 2
        s.camera(tuple(c + Vector((-2.2, 4.4, 3.4))), tuple(c), 26)
        sun(s, 3.0)
        done(s)


def render_compare(built):
    compare_shapes(built)
    detail_shots(built)
    run_shots(built)
    vanilla(built)
    junction_vanilla(built)
    drop_vanilla(built)


def render_all(built, which="catalogue"):
    """which: catalogue | turns | junctions | drops | compare | hall (build_dc.py TRAY_SETS)."""
    _out(which)
    PM.get("Caption")
    if which == "hall":   # the final hero set: the populated data hall, aisle eye level, worm's eye, junction network
        run_shots(built)
        print(f"preview_trays: {len(STAMP)} shots -> {OUT}")
        return
    if which == "compare":
        render_compare(built)
        print(f"preview_trays: {len(STAMP)} shots -> {OUT}")
        return
    if which == "drops":
        render_drops(built)
        print(f"preview_trays: {len(STAMP)} shots -> {OUT}")
        return
    if which == "turns":
        render_turns(built)
        print(f"preview_trays: {len(STAMP)} shots -> {OUT}")
        return
    if which == "junctions":
        render_junctions(built)
        print(f"preview_trays: {len(STAMP)} shots -> {OUT}")
        return
    pieces(built)
    closeups(built)
    ladder(built)
    chains(built)
    run_racks(built)
    run20(built)
    mounts(built)
    paints(built)
    lods(built)
    card_compare(built)
    basket_compare(built)
    vanilla(built)
    print(f"preview_trays: {len(STAMP)} shots -> {OUT}")
