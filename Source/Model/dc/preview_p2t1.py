"""Plan 2 Task 1 previews: the rack tops with their top-entry brush plates, and the rack <-> tray interface proof.

    DC_P2T1_SET=before|after DC_PREVIEW=plan2-t1 blender -b --python Source/Model/build_dc.py -- \
        DC_Rack42_Open DC_Rack42_SplitFront DC_Rack24_Open DC_Rack24_SplitFront
    python3 Source/Model/p2t1_sheet.py          # before | after pairs and the contact sheet

Writes preview/p2-task-1/<set>/ (set = DC_P2T1_SET, default "after"). Shots (DC_SHOTS=prefix,... renders a subset):
  * <rack>_top34 / <rack>_plan: the rack top from a 3/4 high angle and straight down (ortho), every built rack;
  * <rack>_entry_{L,R}_34, <rack>_entry_plan, <rack>_entry_section: brush-plate close-ups (open racks), the
    section is an ortho cut through the left waterfall's x plane (the cable path from the top plane into the manager);
  * <rack>_top_lods: LOD0 / LOD1 / LOD2 side by side;
  * row_ghost_{34,front,side,plan}: 2 full racks + a half rack at the 1.0 m pitch with the ghost Drop, tray and
    Chute volumes placed from dc/dims.py ONLY, the waterfall bundles (R_WF) ending on the rack top plane, and
    dimension annotations; "plan" is a section just above the full racks' top plane (the bundles' footprints);
  * top_vs_vanilla: the half rack beside vanilla WallInsertPipes and CatwalkNarrowBase_250 (read-only FBX)."""
import math
import os

import bmesh
import bpy
from mathutils import Vector

from . import catalog, config, dims as DM
from . import preview as PV
from . import preview_mats as PM
from . import preview_task10 as P10
from . import preview_task9 as P9
from .preview import Rz, T, want

SET = os.environ.get("DC_P2T1_SET", "after")
ROOT = os.path.join(config.PREVIEW_DIR, "p2-task-1")
OUT = os.path.join(ROOT, SET)
RACKS = ("DC_Rack42_Open", "DC_Rack42_SplitFront", "DC_Rack24_Open", "DC_Rack24_SplitFront")
OPEN = ("DC_Rack42_Open", "DC_Rack24_Open")


def _H(name):
    return 0.25 * catalog.BY_NAME[name].cells[1]


def _scene(name, res=(1600, 1000)):
    s = P10.Mood(name, res=res, room=(-4.0, 5.0, -4.0, 4.0), walls=False, ceiling_visible=False,
                 world=(0.030, 0.032, 0.037))
    s.sc.render.resolution_percentage = 100
    return s


def _lights(s, tgt, scale=1.0):
    """Even audit light (as visual pass 1): key from the camera side, cool fill, top wash, rim."""
    tgt = Vector(tgt)
    d = s.cam.location - tgt
    d.z = 0
    if d.length < 1e-6:
        d = Vector((0, 1, 0))
    d.normalize()
    side = d.cross(Vector((0, 0, 1)))
    k = scale
    s.soft(tgt + (d * 2.5 - side * 1.5 + Vector((0, 0, 1.8))) * k, tgt, 260 * k * k, size=3.0 * k, name="key")
    s.soft(tgt + (d * 2.0 + side * 2.5 + Vector((0, 0, 0.8))) * k, tgt, 90 * k * k, size=3.0 * k,
           col=(0.75, 0.85, 1.0), name="fill")
    s.soft(tgt + Vector((0, 0, 3.0)) * k, tgt, 170 * k * k, size=4.0 * k, name="top")
    s.soft(tgt + (-d * 2.5 + side * 1.0 + Vector((0, 0, 1.5))) * k, tgt, 120 * k * k, size=2.0 * k,
           col=(0.8, 0.9, 1.0), name="rim")


def _render(s):
    PV.OUT = OUT
    return s.render()


def _rack(s, built, name, x=0.0, lod=0, paint="keen"):
    return P9.rack(s, built, name, x, 0.0, 0.0, f=0.0, paint=paint, mix=(), fan=20, working=True, lod=lod)


def _ortho_down(s, x, y, z_top, scale, height=3.0, near=None):
    cam = s.camera((x, y, z_top + height), (x, y, z_top), 50, ortho=scale)
    cam.rotation_euler = (0.0, 0.0, 0.0)          # straight down, +Y up in the frame (front of the rack at the top)
    if near is not None:
        cam.data.clip_start = near
    return cam


# ---------------------------------------------------------------------------------------------------- ghosts
def _mat(key):
    return PM.get(key)


def _ghost_box(s, name, lo, hi, mat="GhostSlot", wire=True):
    bm = bmesh.new()
    vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.scale(bm, vec=Vector(hi) - Vector(lo), verts=vs)
    bmesh.ops.translate(bm, vec=(Vector(lo) + Vector(hi)) / 2, verts=vs)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    me.materials.append(_mat(mat))
    ob = s.link(bpy.data.objects.new(name, me))
    if wire:
        s.link(PV.wire_copy(ob, t=0.006))
    return ob


def _line(s, p0, p1, t=0.006, mat="EmWhite"):
    """A thin axis-aligned bar from p0 to p1 (dimension lines, ticks)."""
    p0, p1 = Vector(p0), Vector(p1)
    lo = Vector([min(a, b) - t / 2 for a, b in zip(p0, p1)])
    hi = Vector([max(a, b) + t / 2 for a, b in zip(p0, p1)])
    return _ghost_box(s, "dim", lo, hi, mat, wire=False)


def _cap_x(s, text, loc, size):
    """A caption lying in the x = const plane, facing -x (the side section view: no tilt through the cut plane)."""
    o = s.caption(text, loc, size)
    o.constraints.clear()
    o.rotation_euler = (math.radians(90), 0.0, math.radians(-90))
    return o


def _dim(s, p0, p1, text, tick, off=(0, 0, 0), size=0.05, t=0.006, flat_x=False):
    """Dimension: a bar p0 -> p1, end ticks along `tick` (a vector), the caption at the middle + off."""
    p0, p1, tk = Vector(p0), Vector(p1), Vector(tick)
    _line(s, p0, p1, t)
    for p in (p0, p1):
        _line(s, p - tk, p + tk, t)
    loc = tuple((p0 + p1) / 2 + Vector(off))
    if flat_x:
        _cap_x(s, text, loc, size)
    else:
        s.caption(text, loc, size)


def _bundle(s, name, pts, r=DM.R_WF, mat="PMC:blue"):
    """The waterfall bundle as a round sweep (R_WF) through pts, filleted at the corners like a real bend."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 4
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    from se2model import geom as G
    path, _ = G.fillet_path([Vector(p) for p in pts], 0.09, steps_per_90=6)
    sp.points.add(len(path) - 1)
    for k, p in enumerate(path):
        sp.points[k].co = (p[0], p[1], p[2], 1.0)
    cu.materials.append(_mat(mat))
    return s.link(bpy.data.objects.new(name, cu))


def _interface(s, x, H_rack, full_top, chute=False, ghosts=True):
    """Ghost Drop (+ tray floor plane and port) over one rack at x, the two waterfalls landing on its top plane
    (full_top = the full rack's top; a half rack gets the Chute between the two). ghosts=False: the bundles only,
    plus the Drop's footprint outline on the full racks' top plane."""
    y0 = DM.TRAY_RACK_Y - 0.25
    z_drop = full_top
    if not ghosts:
        zf = z_drop + DM.TRAY_HANG + DM.FLOOR_Z
        zl, zo = zf + 0.027, zf + 0.135
        for a, b in (((x - 0.5, y0), (x + 0.5, y0)), ((x - 0.5, y0 + 0.75), (x + 0.5, y0 + 0.75)),
                     ((x - 0.5, y0), (x - 0.5, y0 + 0.75)), ((x + 0.5, y0), (x + 0.5, y0 + 0.75))):
            _line(s, (a[0], a[1], z_drop + 0.002), (b[0], b[1], z_drop + 0.002), 0.005, "EmAmber")
        for sx in (-1, 1):
            xw, lane = x + sx * DM.WF_X, x + sx * 0.085
            _bundle(s, f"wf_{x}_{sx}", [(lane, DM.TRAY_RACK_Y - 0.1, zl), (lane, DM.TRAY_RACK_Y + 0.08, zl),
                                        (xw, DM.TRAY_RACK_Y + 0.17, zo), (xw, DM.WF_Y, zo), (xw, DM.WF_Y, H_rack)])
        return
    _ghost_box(s, f"drop_{x}", (x - 0.5 + 0.004, y0 + 0.004, z_drop + 0.004),
               (x + 0.5 - 0.004, y0 + 0.75 - 0.004, z_drop + 0.75 - 0.004))
    # the tray proper inside the Drop: its 2-cell cross-section box (dark ghost) and the floor-top plane
    zt = z_drop + DM.TRAY_HANG
    _ghost_box(s, f"tray_{x}", (x - 0.5 + 0.01, DM.TRAY_RACK_Y - 0.25 + 0.01, zt + 0.004),
               (x + 0.5 - 0.01, DM.TRAY_RACK_Y + 0.25 - 0.01, zt + 0.25 - 0.004), "GhostOcc", wire=False)
    zf = zt + DM.FLOOR_Z
    _line(s, (x - 0.5, DM.TRAY_RACK_Y - 0.21, zf), (x + 0.5, DM.TRAY_RACK_Y - 0.21, zf), 0.004, "EmAmber")
    _line(s, (x - 0.5, DM.TRAY_RACK_Y + 0.21, zf), (x + 0.5, DM.TRAY_RACK_Y + 0.21, zf), 0.004, "EmAmber")
    if chute:
        _ghost_box(s, f"chute_{x}", (x - 0.5 + 0.004, DM.WF_Y - 0.0575 + 0.004, H_rack + 0.004),
                   (x + 0.5 - 0.004, DM.WF_Y - 0.0575 + 0.25 - 0.004, full_top - 0.004), "GhostMount")
    for sx in (-1, 1):
        xw = x + sx * DM.WF_X
        lane = x + sx * 0.085                       # peels off lane L1 (s = +-0.085, h = 0.027)
        zl = zf + 0.027
        zo = zf + 0.135                             # over the tray's front wall (top wire h = 0.10)
        _bundle(s, f"wf_{x}_{sx}", [(lane, DM.TRAY_RACK_Y - 0.1, zl), (lane, DM.TRAY_RACK_Y + 0.08, zl),
                                    (xw, DM.TRAY_RACK_Y + 0.17, zo), (xw, DM.WF_Y, zo), (xw, DM.WF_Y, H_rack)])


def _row(s, built, ghosts=True):
    """2 full racks + 1 half rack at the 1.0 m rack pitch; returns [(name, x, H)]."""
    row = [(n, x) for n, x in (("DC_Rack42_Open", 0.0), ("DC_Rack42_SplitFront", 1.0), ("DC_Rack24_Open", 2.0))
           if n in built]
    out = []
    for n, x in row:
        _rack(s, built, n, x)
        out.append((n, x, _H(n)))
    full = max(h for _, _, h in out)
    for n, x, h in out:
        _interface(s, x, h, full, chute=h < full, ghosts=ghosts)
    return out, full


def row_shots(built):
    if "DC_Rack42_Open" not in built:
        return
    for view in ("34", "front", "side", "plan", "landing"):
        nm = f"row_ghost_{view}"
        if not want(nm):
            continue
        s = _scene(nm, res={"plan": (1800, 900), "side": (1700, 1500)}.get(view, (1800, 1150)))
        xd = -DM.WF_X + 0.001           # the side section's annotation plane (just behind the cut)
        if view == "34":
            s.camera((-1.0, 3.3, 4.7), (1.0, 0.15, 2.45), 30)
        elif view == "front":
            s.camera((1.0, 8.0, 2.3), (1.0, 0.0, 2.3), 50, ortho=4.4)
        elif view == "side":   # a section through the left waterfall of the first rack, from -x
            cam = s.camera((-6.0, 0.05, 2.78), (0.0, 0.05, 2.78), 50, ortho=1.9)
            cam.data.clip_start = 6.0 - DM.WF_X
        elif view == "plan":
            _ortho_down(s, 1.0, 0.0, 2.5, 3.5, height=3.0, near=3.0 - 0.06)
        else:                  # the money shot: one waterfall landing in its brush plate
            s.camera((-DM.WF_X - 0.55, DM.WF_Y + 0.75, 2.5 + 0.55), (-DM.WF_X + 0.05, DM.WF_Y - 0.02, 2.5 + 0.05), 40)
        row, full = _row(s, built, ghosts=view not in ("plan", "landing"))
        z = full
        if view in ("front", "34"):
            _dim(s, (-0.5 - 0.12, DM.WF_Y, z), (-0.5 - 0.12, DM.WF_Y, z + DM.TRAY_HANG), "TRAY_HANG\n0.500",
                 (0.03, 0, 0), off=(-0.25, 0, 0), size=0.06)
            _dim(s, (0.0, 0.66, z + 0.82), (DM.WF_X, 0.66, z + 0.82), "WF_X 0.3585", (0, 0, 0.03), off=(0, 0, 0.07))
            _dim(s, (-DM.WF_X, 0.66, z + 0.82), (0.0, 0.66, z + 0.82), "WF_X", (0, 0, 0.03), off=(0, 0, 0.07))
            _dim(s, (1.5, 0.66, z + 0.82), (2.5, 0.66, z + 0.82), "rack pitch 1.000 = Drop length",
                 (0, 0, 0.03), off=(0, 0, 0.07), size=0.045)
            h24 = _H("DC_Rack24_Open")
            if any(n == "DC_Rack24_Open" for n, _, _ in row):
                _dim(s, (2.62, DM.WF_Y, h24), (2.62, DM.WF_Y, full), "Chute\n1.250", (0.03, 0, 0), off=(0.18, 0, 0))
            if view == "front":
                s.caption("ghosts placed from dc/dims.py only: Drop (cyan), tray (amber), Chute (green); "
                          "blue = waterfall bundle R_WF 22.5 mm, ending on the rack top plane",
                          (1.0, 0.7, full + 1.07), 0.05)
        elif view == "side":
            _dim(s, (xd, 0.0, z + 0.80), (xd, DM.TRAY_RACK_Y, z + 0.80), "TRAY_RACK_Y +0.125", (0, 0, 0.02),
                 off=(0, 0, 0.05), size=0.035, flat_x=True)
            _dim(s, (xd, DM.TRAY_RACK_Y - 0.25, z + 0.93), (xd, DM.TRAY_RACK_Y + 0.25, z + 0.93),
                 "tray span +-0.25 (grid planes)", (0, 0, 0.02), off=(0, 0, 0.05), size=0.035, flat_x=True)
            _dim(s, (xd, 0.0, z - 0.30), (xd, DM.WF_Y, z - 0.30), "WF_Y 0.4325", (0, 0, 0.02), off=(0, 0, -0.05),
                 size=0.035, flat_x=True)
            _dim(s, (xd, DM.DOOR_Y_BACK, z - 0.42), (xd, DM.DOOR_Y_BACK, z - 0.02), "DOOR_Y_BACK\n0.600",
                 (0, 0.015, 0), off=(0, -0.1, 0.0), size=0.03, flat_x=True)
            _dim(s, (xd, -0.66, z), (xd, -0.66, z + DM.TRAY_HANG), "TRAY_HANG\n0.500", (0, 0.02, 0),
                 off=(0, -0.0, 0.31), size=0.035, flat_x=True)
            _line(s, (xd, 0.0, z - 0.45), (xd, 0.0, z + 1.0), 0.003)
            _cap_x(s, "rack centre", (xd, 0.0, z - 0.50), 0.03)
            _cap_x(s, "section x = -WF_X (front = left)", (xd, 0.05, z + 1.06), 0.04)
        elif view == "plan":
            for n, x, h in row:
                P9.flat(s, n.replace("DC_", ""), (x, -0.45, full + 0.01), 0.07)
            P9.flat(s, "section 6 cm above the full racks' top: the bundles' footprints in the entries; "
                    "amber = the Drop's footprint", (1.0, -0.85, full + 0.01), 0.05)
        tgt = (1.0, 0.1, 2.4) if view != "landing" else (-DM.WF_X, DM.WF_Y, 2.5)
        _lights(s, tgt, 1.4 if view != "landing" else 0.6)
        _render(s)


# ---------------------------------------------------------------------------------------------------- rack tops
def rack_tops(built):
    for name in RACKS:
        if name not in built:
            continue
        H = _H(name)
        nm = f"{name}_top34"
        if want(nm):
            s = _scene(nm)
            s.camera((-1.05, 1.55, H + 1.05), (0.0, 0.05, H - 0.12), 32)
            _rack(s, built, name)
            _lights(s, (0, 0, H))
            _render(s)
        nm = f"{name}_plan"
        if want(nm):
            s = _scene(nm, res=(1150, 1400))
            _ortho_down(s, 0.0, 0.0, H, 1.40)
            _rack(s, built, name)
            P9.flat(s, "FRONT", (0.0, 0.66, H + 0.01), 0.05)
            _lights(s, (0, 0, H))
            _render(s)


def closeups(built):
    for name in OPEN:
        if name not in built:
            continue
        H = _H(name)
        for side, sx in (("L", -1), ("R", 1)):
            nm = f"{name}_entry_{side}_34"
            if want(nm):
                s = _scene(nm, res=(1600, 1100))
                tgt = Vector((sx * DM.WF_X, DM.WF_Y - 0.02, H - 0.03))
                s.camera(tuple(tgt + Vector((sx * 0.20, 0.36, 0.30))), tuple(tgt), 55)
                _rack(s, built, name)
                _lights(s, tgt, 0.5)
                _render(s)
        nm = f"{name}_entry_plan"
        if want(nm):
            s = _scene(nm, res=(1600, 1000))
            _ortho_down(s, -DM.WF_X, DM.WF_Y - 0.01, H, 0.24)
            _rack(s, built, name)
            _lights(s, (-DM.WF_X, DM.WF_Y, H), 0.6)
            _render(s)
        nm = f"{name}_entry_section"
        if want(nm):   # ortho cut at x = -WF_X looking +x: the opening, the lips and the path into the manager
            s = _scene(nm, res=(1300, 1300))
            zc = H - (0.12 if "42" in name else 0.06)
            cam = s.camera((-DM.WF_X - 4.0, 0.42, zc), (-DM.WF_X, 0.42, zc), 50, ortho=0.36 if "42" in name else 0.2)
            cam.data.clip_start = 4.0
            _rack(s, built, name)
            _lights(s, (-DM.WF_X + 0.3, 0.4, zc), 0.6)
            _render(s)


def lods(built):
    for name in OPEN:
        nm = f"{name}_top_lods"
        if name not in built or not want(nm):
            continue
        H = _H(name)
        s = _scene(nm, res=(1900, 900))
        s.camera((-0.6, 3.3, H + 2.1), (1.2, 0.0, H - 0.2), 32)   # (before the captions: they track it)
        n = min(3, len(built[name]["lods"]) - 1)
        for L in range(n):
            _rack(s, built, name, x=1.2 * L, lod=L)
            s.caption(f"LOD{L}", (1.2 * L, 0.0, H + 0.18), 0.08)
        _lights(s, (1.2, 0, H), 1.2)
        _render(s)


def vanilla(built):
    nm = "top_vs_vanilla"
    name = "DC_Rack24_Open"
    if name not in built or not want(nm):
        return
    H = _H(name)
    s = _scene(nm, res=(1800, 1000))
    s.camera((-0.4, 2.6, H + 1.4), (0.0, 0.0, H - 0.25), 34)
    _rack(s, built, name)
    for rel, x, label in (("Walls/Inserts/Pipes/Models/NonFractured/WallInsertPipes.fbx", 1.25, "vanilla WallInsertPipes"),
                          ("Catwalks/CatwalkNarrowBase/250/Models/NonFractured/CatwalkNarrowBase_250.fbx", -1.3,
                           "vanilla CatwalkNarrowBase_250")):
        c, lo, hi = PV.vanilla(rel)
        ctr = (lo + hi) / 2
        s.inst(c, T(x, 0.0, H - (hi.z - lo.z)) @ T(-ctr.x, -ctr.y, -lo.z))   # tops level with the rack's top plane
        s.caption(label, (x, 0.0, H + 0.2), 0.06)
        # a plinth under the vanilla piece so it stands at the rack top's height
        bm = bmesh.new()
        w = max(hi.x - lo.x, hi.y - lo.y) * 0.5 + 0.02
        s._box(bm, (x - w, -w, 0.0), (x + w, w, H - (hi.z - lo.z) - 0.002), 0)
        s._obj("mood_ped", bm, [P10._mat("mood_ped", (0.03, 0.031, 0.035), 0.5, 0.4)])
    s.caption("OURS (24U roof)", (0.0, 0.0, H + 0.2), 0.06)
    _lights(s, (0, 0, H), 1.2)
    _render(s)


def render_all(built):
    PM.get("Caption")
    os.makedirs(OUT, exist_ok=True)
    rack_tops(built)
    closeups(built)
    row_shots(built)
    lods(built)
    vanilla(built)
