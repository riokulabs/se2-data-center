"""Task-7 preview set: the UPS server (Source/Model/preview/task-7/).

Same rig and stand-ins as Tasks 3-6 (dc/preview.py, dc/preview_mats.py, dc/preview_task6.py). Vanilla FBX are imported
READ ONLY: Battery50 from tools/vanilla-ref, the Power Cell item model (Components/Simple/PowerCell/Models/
PowerCell.fbx) from the Mod SDK. The inserted cells are the real vanilla cell mesh placed exactly at the UPS's
CellSlot dummies (dc/functional.ups_dummies, game frame -> Blender), as the game's InventorySlotRender draws them.

    DC_PREVIEW=task7 blender -b --python Source/Model/build_dc.py -- DC_Rack42_Open DC_Rack24_Open DC_Srv_Blank \
        DC_Srv_Compute DC_Srv_Storage DC_Srv_Switch DC_Srv_Timer DC_Srv_EventCtl DC_Srv_Status DC_Srv_UPS
(DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution).
"""
import math
import os

import bpy
from mathutils import Matrix, Vector

from . import config, functional
from . import preview as PV
from . import preview_mats as PM
from . import preview_task6 as P6
from .preview import Rz, Shot, T, human, want

OUT = os.path.join(config.PREVIEW_DIR, "task-7")
UPS = "DC_Srv_UPS"
HU = 0.5                       # UPS height
FULL, HALF = "DC_Rack42_Open", "DC_Rack24_Open"
SDK_CELL = os.path.expanduser("~/.steam/debian-installation/steamapps/common/Space Engineers 2 - Mod SDK/GameData/"
                              "Vanilla/Assets/Components/Simple/PowerCell/Models/PowerCell.fbx")
B50 = "Batteries/Battery/50/Models/NonFractured/Battery50.fbx"


# ---------------------------------------------------------------------------------------------------- sources
def cell(paint="keen"):
    """The vanilla Power Cell item mesh (read-only import), stand-in materials; origin = its face (CellSlot)."""
    nm = "pv7_powercell"
    if nm in bpy.data.collections:
        return bpy.data.collections[nm]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=SDK_CELL)
    new = [o for o in bpy.data.objects if o not in before]
    c = bpy.data.collections.new(nm)
    bpy.context.scene.collection.children.link(c)
    for o in new:
        for uc in list(o.users_collection):
            uc.objects.unlink(o)
        c.objects.link(o)
        if o.type == "MESH":
            for i, s in enumerate(o.material_slots):
                if s.material:
                    n = s.material.name.split(".")[0]
                    key = "EmGreen" if n == "PowerCell_Discharge" else PM.keen_key(n, paint)
                    o.material_slots[i].material = PM.get(key)
    PV._exclude(c)
    return c


def cell_matrices():
    """Blender matrices (UPS frame, origin = cell-box centre) of the two CellSlot dummies."""
    sx, sy, sz = functional.UPS_SHIFT
    out = []
    for name, typ, (xg, yg, zg), q, e, sc in functional.ups_dummies():
        if not name.startswith("CellSlot"):
            continue
        m = T(xg - sx, -(zg - sz), yg - sy)
        out.append(m @ Rz(180) if q[1] else m)
    return out


def ups(s, built, x=0.0, y=0.0, z=0.0, paint="keen", lod=0, rot=0, cells=True):
    """The UPS standing with its bottom at z; cells = True puts a vanilla Power Cell in both bays."""
    m = T(x, y, z + HU / 2) @ Rz(rot)
    s.inst(P6.stated(built, UPS, lod, paint, {}), m)
    if cells and lod <= 2:
        for cm in cell_matrices():
            s.inst(cell(), m @ cm)
    return m


def srv6(s, built, name, x=0.0, y=0.0, z=0.0, paint="keen"):
    P6.srv(s, built, name, x, y, z, paint)


def rack(s, built, name, mix, x=0.0, y=0.0, paint="keen", cells=True):
    """mix: one entry per slot from the bottom; "UPS" takes that slot and the next (None for the second)."""
    Hr = 0.25 * (10 if name == FULL else 5)
    s.inst(PV.painted(built, name, 0, paint), T(x, y, Hr / 2))
    for k, n in enumerate(mix, 1):
        if n == "UPS":
            ups(s, built, x, y, 0.25 * k, paint, cells=cells)
        elif n:
            srv6(s, built, n, x, y, 0.25 * k, paint)


def _vanilla_b50(paint="keen"):
    return PV.vanilla(B50, paint)


# ---------------------------------------------------------------------------------------------------- shots
def per_view(built):
    zc = HU / 2
    views = {
        "front": ((0.0, 2.0, zc), (0, 0, zc), 55),
        "3q_front": ((-1.05, 1.45, 0.95), (0, 0.02, zc * 0.85), 50),
        "3q_front_empty": ((-1.05, 1.45, 0.95), (0, 0.02, zc * 0.85), 50),
        "back": ((0.0, -2.0, zc), (0, 0, zc), 55),
        "3q_back": ((1.05, -1.45, 0.95), (0, -0.02, zc * 0.85), 50),
        "side": ((2.0, 0.0, zc), (0, 0, zc), 55),
        "top": ((0.0, 0.25, 2.4), (0, 0.0, zc), 45),
    }
    for v, (loc, tgt, lens) in views.items():
        nm = f"{UPS}_{v}"
        if not want(nm):
            continue
        s = Shot(nm, floor=(-1.5, 1.5, -1.5, 1.5))
        ups(s, built, cells=not v.endswith("empty"))
        s.camera(loc, tgt, lens)
        s.render()
    nm = f"{UPS}_lods"
    if want(nm):
        import json
        with open(config.REPORT_PATH) as f:
            rep = json.load(f)["blocks"].get(UPS, {}).get("lods", [])
        n = len(built[UPS]["lods"])
        s = Shot(nm, res=(2400, 1000), floor=(-0.8 * n, 1, -1.2, 1.2))
        for i in range(n):
            ups(s, built, x=-0.8 * i, lod=i, cells=False)
        cx = -0.8 * (n - 1) / 2
        s.camera((cx - 0.4, 4.2, 1.3), (cx, 0, 0.25), 35)
        for i in range(n):
            r = rep[i] if i < len(rep) else {}
            s.caption(f"LOD{i}\n{r.get('tris', '?')}/{r.get('max_tris', '?')} tris, "
                      f"{r.get('materials', '?')}/{r.get('max_materials', '?')} mats", (-0.8 * i, 0.4, 0.68), 0.045)
        s.render()


def bays(built):
    """Each open bay close up, with the vanilla cell inserted and empty."""
    (_, xf, zf, yf, _), (_, xr, zr, yr, _) = functional.UPS_BAYS
    zc = HU / 2
    shots = {
        "bay1_front_cell": (True, (-xf + 0.28, 0.98, zc + zf + 0.22), (xf, yf, zc + zf)),
        "bay1_front_empty": (False, (-xf + 0.28, 0.98, zc + zf + 0.22), (xf, yf, zc + zf)),
        "bay1_front_empty_straight": (False, (xf, 1.05, zc + zf + 0.03), (xf, yf, zc + zf)),
        "bay2_rear_cell": (True, (xr - 0.28, -0.98, zc + zr + 0.22), (xr, yr, zc + zr)),
        "bay2_rear_empty": (False, (xr - 0.28, -0.98, zc + zr + 0.22), (xr, yr, zc + zr)),
    }
    for v, (cells, loc, tgt) in shots.items():
        nm = f"{UPS}_{v}"
        if not want(nm):
            continue
        s = Shot(nm, res=(1600, 1200), floor=(-1.5, 1.5, -1.5, 1.5))
        ups(s, built, cells=cells)
        s.camera(loc, tgt, 42)
        s.render()


def panel(built):
    zc = HU / 2
    for nm, loc, tgt, lens in ((f"{UPS}_closeup_panel", (-0.32, 0.62, zc + 0.10), (-0.207, 0.38, zc + 0.02), 40),
                               (f"{UPS}_closeup_topband", (0.0, 0.75, zc + 0.30), (0.0, 0.38, zc + 0.21), 40),
                               (f"{UPS}_closeup_rear_strip", (0.05, -0.75, zc + 0.30), (-0.05, -0.37, zc + 0.20), 40),
                               (f"{UPS}_closeup_ear_handle", (-0.55, 0.75, zc + 0.10), (-0.279, 0.40, zc), 40)):
        if not want(nm):
            continue
        s = Shot(nm, res=(1600, 1200), floor=(-1.5, 1.5, -1.5, 1.5))
        ups(s, built)
        s.camera(loc, tgt, lens)
        s.render()


FULL_MIX = ("DC_Srv_Storage", "UPS", None, "DC_Srv_Timer", "DC_Srv_Compute", "DC_Srv_Status", "DC_Srv_Switch",
            "DC_Srv_Blank")
HALF_MIX = ("UPS", None, "DC_Srv_Switch", "DC_Srv_EventCtl")


def in_rack(built):
    shots = {
        "rack42_ups_front": (FULL, FULL_MIX, (0.0, 4.4, 1.3), (0, 0, 1.25), 40),
        "rack42_ups_3q": (FULL, FULL_MIX, (-1.75, 2.9, 2.05), (0, 0, 1.2), 35),
        "rack42_ups_back_3q": (FULL, FULL_MIX, (1.6, -2.9, 1.8), (0, 0, 1.0), 35),
        "rack42_ups_first_person": (FULL, FULL_MIX, (0.35, 0.625 + 2.0, 1.70), (0.0, 0.0, 0.85), 24),
        "rack24_ups_front": (HALF, HALF_MIX, (0.0, 3.0, 0.75), (0, 0, 0.7), 40),
        "rack24_ups_3q": (HALF, HALF_MIX, (-1.4, 2.2, 1.4), (0, 0, 0.65), 35),
        "rack24_ups_first_person": (HALF, HALF_MIX, (0.35, 0.625 + 1.6, 1.70), (0.0, 0.0, 0.55), 26),
    }
    for nm, (rk, mix, loc, tgt, lens) in shots.items():
        if not want(nm):
            continue
        s = Shot(nm, floor=(-2.5, 2.5, -2.5, 4.0))
        rack(s, built, rk, mix)
        s.camera(loc, tgt, lens)
        s.render()
    nm = "racks_row_black_ups"
    if want(nm):
        s = Shot(nm, res=(2200, 1250), floor=(-3, 2, -2, 4))
        rack(s, built, FULL, FULL_MIX, x=0.0, paint="black")
        rack(s, built, FULL, ("UPS", None, "UPS", None, "DC_Srv_Storage", "DC_Srv_Storage", "DC_Srv_Status",
                              "DC_Srv_Blank"), x=-1.0, paint="black")
        rack(s, built, HALF, HALF_MIX, x=-2.0, paint="black")
        s.inst(human(), T(0.9, 1.6, 0) @ Rz(200))
        s.camera((1.4, 4.2, 1.9), (-1.0, 0, 1.15), 32)
        s.render()


LINE = (("DC_Srv_Timer", "TIMER"), ("DC_Srv_EventCtl", "EVENT CTL"), ("DC_Srv_Status", "STATUS"),
        ("DC_Srv_Compute", "COMPUTE"), ("DC_Srv_Storage", "STORAGE"), ("DC_Srv_Switch", "SWITCH"),
        ("DC_Srv_Blank", "BLANK"), ("UPS", "UPS 12U\n2 cells fitted"), ("UPS_EMPTY", "UPS 12U\nbays empty"))


def lineup(built):
    nm = "servers_lineup_9"
    if not want(nm):
        return
    xs, x = [], 0.0
    for n, _ in LINE:
        xs.append(x)
        x -= 0.85 if n.startswith("UPS") else 0.68
    s = Shot(nm, res=(3400, 1000), floor=(xs[-1] - 0.8, 0.8, -1, 1.5))
    cx = (xs[0] + xs[-1]) / 2
    s.camera((cx, 7.6, 1.15), (cx, 0, 0.28), 33)
    for (n, lbl), x in zip(LINE, xs):
        if n.startswith("UPS"):
            ups(s, built, x=x, cells=(n == "UPS"))
        else:
            srv6(s, built, n, x=x)
        s.caption(lbl, (x, 0.45, 0.72 if n.startswith("UPS") else 0.46), 0.055)
    s.render()


def paints(built):
    nm = f"{UPS}_paints_black_keen_blue"
    if not want(nm):
        return
    s = Shot(nm, res=(2200, 1100), floor=(-2.2, 1.2, -1.2, 2.5))
    s.camera((-0.7, 3.2, 1.0), (-0.7, 0, 0.25), 35)
    for i, p in enumerate(("black", "keen", "blue")):
        ups(s, built, x=-0.7 * i, paint=p)
        s.caption(("BLACK", "KEEN GREY", "BLUE")[i], (-0.7 * i, 0.4, 0.62), 0.04)
    s.render()


def vanilla_compare(built):
    """Ours next to vanilla Battery50 (read-only), then the bays side by side (empty and with a cell)."""
    c, lo, hi = _vanilla_b50()
    ctr = (lo + hi) / 2
    place = lambda x: T(x, 0, 0) @ T(-ctr.x, -ctr.y, -lo.z)   # noqa: E731
    nm = f"{UPS}_vanilla_comparison"
    if want(nm):
        s = Shot(nm, res=(2400, 1100), floor=(-2.5, 1.0, -1.5, 1.5))
        ups(s, built, x=0.0)
        ups(s, built, x=-0.75, cells=False)
        s.inst(c, place(-1.55))
        s.inst(c, place(-2.2))
        s.inst(cell(), place(-2.2) @ T(0, 0.2545, 0))      # Battery50's CellSlot 0 (its own frame)
        s.camera((-1.1, 3.7, 1.0), (-1.1, 0, 0.25), 35)
        for txt, x, zt in (("OURS: UPS 12U\n2 cells", 0.0, 0.66), ("OURS: bays empty", -0.75, 0.66),
                           ("vanilla Battery50\nempty", -1.55, 0.66), ("vanilla Battery50\n1 cell", -2.2, 0.66)):
            s.caption(txt, (x, 0.3, zt), 0.035)
        s.render()
    nm = f"{UPS}_vanilla_bays_side_by_side"
    if want(nm):
        (_, xf, zf, yf, _), _ = functional.UPS_BAYS
        s = Shot(nm, res=(2400, 1100), floor=(-2.8, 1.0, -1.5, 1.5))
        # front faces aligned on y: our bay mouth at yf, Battery50's frame mouth (CELL_KIT_MOUTH) on the same plane
        ups(s, built, x=0.0, y=0.0, cells=False)
        ups(s, built, x=-0.72, y=0.0, cells=True)
        dz = HU / 2 + zf                      # our bay centre height: Battery50's bay centred on it
        for x, with_cell in ((-1.47, False), (-2.12, True)):
            m = T(x, yf - functional.CELL_KIT_MOUTH, dz)     # Battery50's frame origin is its centre
            s.inst(c, m)
            if with_cell:
                s.inst(cell(), m @ T(0, 0.2545, 0))
        s.camera((-1.06, 2.9, dz + 0.45), (-1.06, 0.3, dz + 0.02), 33)
        for txt, x in (("OURS: bay empty", xf), ("OURS: + vanilla cell", -0.72 + xf),
                       ("Battery50: bay empty", -1.47), ("Battery50: + cell", -2.12)):
            s.caption(txt, (x, 0.45, dz + 0.36), 0.035)
        s.render()


def render_all(built):
    PV.OUT = OUT
    PM.get("Caption")
    if UPS not in built:
        return
    per_view(built)
    bays(built)
    panel(built)
    paints(built)
    vanilla_compare(built)
    if all(n in built for n in P6.FUNC + P6.DECO):
        lineup(built)
    if all(n in built for n in P6.FUNC + P6.DECO + (FULL, HALF)):
        in_rack(built)
