"""Server previews: the deco servers alone, in racks, standalone, painted, and next to vanilla.

Writes into Source/Model/preview/servers/. Same rig and material stand-ins as the rack set (dc/preview.py);
vanilla FBX are imported READ ONLY from tools/vanilla-ref. Needs the four deco servers and both open racks built
in the same run:  blender -b --python Source/Model/build_dc.py -- DC_Rack42_Open DC_Rack24_Open DC_Srv_Blank
DC_Srv_Compute DC_Srv_Storage DC_Srv_Switch   (DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution).
"""
import json
import os

from mathutils import Vector

from . import config
from . import preview as PV
from . import preview_mats as PM
from .preview import Rz, Shot, T, human, painted, vanilla, want

OUT = os.path.join(config.PREVIEW_DIR, "servers")
SERVERS = ("DC_Srv_Blank", "DC_Srv_Compute", "DC_Srv_Storage", "DC_Srv_Switch")
FULL, HALF = "DC_Rack42_Open", "DC_Rack24_Open"
LABEL = {"DC_Srv_Blank": "BLANK\nhoneycomb bezel, locator lamp",
         "DC_Srv_Compute": "COMPUTE\n6 SFF caddies, control module,\nhinged honeycomb intake door",
         "DC_Srv_Storage": "STORAGE\n3 x 4 drive wall, control strip",
         "DC_Srv_Switch": "SWITCH\n24 ports + link lamps, SFP uplinks,\nfan tray"}
H = 0.25   # 6U height
# full rack slots 1..8 (None = empty) and half rack slots 1..4
FULL_MIX = ("DC_Srv_Storage", "DC_Srv_Storage", "DC_Srv_Compute", None, "DC_Srv_Compute", "DC_Srv_Blank",
            "DC_Srv_Switch", None)
HALF_MIX = ("DC_Srv_Switch", None, "DC_Srv_Compute", "DC_Srv_Storage")


def _report():
    with open(config.REPORT_PATH) as f:
        return json.load(f)["blocks"]


def _srv(s, built, name, x=0.0, y=0.0, z=0.0, paint="keen", lod=0, rot=0):
    """A server standing with its bottom at z (its origin is the cell-box centre)."""
    s.inst(painted(built, name, lod, paint), T(x, y, z + H / 2) @ Rz(rot))


def _rack(s, built, name, mix, x=0.0, y=0.0, paint="keen", srv_paint=None):
    Hr = 0.25 * (10 if name == FULL else 5)
    s.inst(painted(built, name, 0, paint), T(x, y, Hr / 2))
    for k, srv in enumerate(mix, 1):
        if srv:
            _srv(s, built, srv, x, y, 0.25 * k, srv_paint or paint)   # slot k floor = 0.25 k (plinth 0.25)


# ---------------------------------------------------------------------------------------------------- per server
def per_server(built, name, paint="keen"):
    zc = H / 2
    views = {
        "front": ((0.0, 1.55, zc), (0, 0, zc), 60),
        "3q_front": ((-0.85, 1.15, 0.72), (0, 0.02, zc * 0.8), 50),
        "back": ((0.0, -1.55, zc), (0, 0, zc), 60),
        "side": ((1.65, 0.0, zc + 0.05), (0, 0.02, zc), 50),
        "top": ((0.0, 0.03, 1.85), (0, 0.02, zc), 45),
        "closeup_front": ((-0.30, 0.78, 0.33), (-0.12, 0.37, zc), 40),
    }
    for v, (loc, tgt, lens) in views.items():
        nm = f"{name}_{v}"
        if not want(nm):
            continue
        s = Shot(nm, floor=(-1.5, 1.5, -1.5, 1.5))
        _srv(s, built, name, paint=paint)
        s.camera(loc, tgt, lens)
        s.render()
    nm = f"{name}_lods"
    if want(nm):
        rep = _report().get(name, {}).get("lods", [])
        n = len(built[name]["lods"])
        s = Shot(nm, res=(2200, 900), floor=(-0.8 * n, 1, -1.2, 1.2))
        for i in range(n):
            _srv(s, built, name, x=-0.8 * i, lod=i, paint=paint)
        cx = -0.8 * (n - 1) / 2
        s.camera((cx - 0.4, 3.9, 1.2), (cx, 0, 0.15), 35)
        for i in range(n):
            r = rep[i] if i < len(rep) else {}
            s.caption(f"LOD{i}\n{r.get('tris', '?')}/{r.get('max_tris', '?')} tris, "
                      f"{r.get('materials', '?')}/{r.get('max_materials', '?')} mats", (-0.8 * i, 0.4, 0.42), 0.045)
        s.render()


def lineup(built, paint="keen"):
    nm = "servers_lineup_fronts"
    if not want(nm):
        return
    s = Shot(nm, res=(2400, 1000), floor=(-2.6, 0.6, -1, 1.5))
    for i, n in enumerate(SERVERS):
        _srv(s, built, n, x=-0.68 * i, paint=paint)
    cx = -0.68 * 1.5
    s.camera((cx, 3.7, 0.75), (cx, 0, 0.2), 35)
    for i, n in enumerate(SERVERS):
        s.caption(LABEL[n], (-0.68 * i, 0.45, 0.40), 0.032)
    s.render()


# ---------------------------------------------------------------------------------------------------- in racks
def in_rack(built):
    shots = {
        "rack42_populated_front": ((0.0, 4.4, 1.3), (0, 0, 1.25), 40),
        "rack42_populated_3q": ((-1.75, 2.9, 2.05), (0, 0, 1.2), 35),
        # first person: eye 1.70 m (an SE2 engineer), 2.5 m in front of the rack's front, ~70 deg horizontal FOV
        "rack42_populated_eye_2p5m": ((0.35, 0.625 + 2.5, 1.70), (0.0, 0.0, 1.25), 26),
        "rack24_populated_3q": ((-1.3, 2.2, 1.55), (0, 0, 0.62), 35),
        "rack24_populated_front": ((0.0, 3.2, 0.7), (0, 0, 0.62), 40),
    }
    for nm, (loc, tgt, lens) in shots.items():
        if not want(nm):
            continue
        s = Shot(nm, floor=(-2.5, 2.5, -2.5, 4.0))
        if nm.startswith("rack42"):
            _rack(s, built, FULL, FULL_MIX)
        else:
            _rack(s, built, HALF, HALF_MIX)
        s.camera(loc, tgt, lens)
        s.render()
    # a black row: two full racks + a half rack, populated (the reference-photo look)
    nm = "racks_row_black_populated"
    if want(nm):
        s = Shot(nm, res=(2200, 1250), floor=(-3, 2, -2, 4))
        _rack(s, built, FULL, FULL_MIX, x=0.0, paint="black")
        _rack(s, built, FULL, tuple(reversed(FULL_MIX)), x=-1.0, paint="black")
        _rack(s, built, HALF, HALF_MIX, x=-2.0, paint="black")
        s.camera((1.4, 4.2, 1.9), (-1.0, 0, 1.15), 32)
        s.render()


def ear_closeups(built):
    """Ears on the rails: the full rack with slots 3 (compute) and 2 (storage) filled, slot 4 empty above."""
    shots = {
        "ears_on_rails_closeup_3q": ((0.12, 0.98, 1.12), (-0.27, 0.38, 0.86), 45),
        "ears_on_rails_closeup_front": ((-0.27, 1.15, 0.80), (-0.27, 0.375, 0.80), 70),
        "ears_on_rails_closeup_right": ((0.62, 0.95, 0.95), (0.27, 0.38, 0.80), 45),
    }
    for nm, (loc, tgt, lens) in shots.items():
        if not want(nm):
            continue
        s = Shot(nm, floor=(-2.0, 2.0, -2.0, 2.5))
        _rack(s, built, FULL, FULL_MIX)
        s.camera(loc, tgt, lens)
        s.render()
    # sections: ortho cuts using the camera near plane, annotated with emissive guide lines (green = a plane of
    # the rack, red = the clearance limit) and captions placed just beyond the cut
    sec = {
        # plan cut at the slide height of slot 3 (z = 0.75 + 0.0975): server slide at |x| <= 0.247, the rack's outer
        # member web from 0.25, its countersunk bolt head (1.5 mm into the slot) at y = 0.333
        "clearance_section_plan_slides": (
            "full", (-0.245, 0.30, 10.0), (-0.245, 0.30, 0.0), 0.12, 10.0 - 0.8475,
            [((-0.25, 0.258, 0.846), (-0.25, 0.342, 0.846), "EmGreen"),
             ((-0.248, 0.258, 0.846), (-0.248, 0.342, 0.846), "EmRed")],
            [("PLAN CUT AT SLIDE HEIGHT, SLOT 3 (full rack)", (-0.245, 0.343, 0.846)),
             ("green: slot plane x = -0.250   red: server limit 0.248", (-0.245, 0.337, 0.846)),
             ("rack slide bolt head\nto x = -0.2485", (-0.275, 0.325, 0.846)),
             ("server slide\n0.2405 .. 0.247", (-0.226, 0.318, 0.846)),
             ("server side skin 0.240", (-0.222, 0.27, 0.846)),
             ("rack slide outer member", (-0.274, 0.27, 0.846))], 0.0028),
        # plan cut through the lower thumbscrews of slot 3 (z = 0.75 + 0.031): ear flange on the rail face
        "clearance_section_plan_ear": (
            "full", (-0.27, 0.37, 10.0), (-0.27, 0.37, 0.0), 0.12, 10.0 - 0.781,
            [((-0.318, 0.375, 0.78), (-0.222, 0.375, 0.78), "EmGreen"),
             ((-0.25, 0.33, 0.78), (-0.25, 0.42, 0.78), "EmGreen")],
            [("PLAN CUT THROUGH A THUMBSCREW, SLOT 3", (-0.27, 0.423, 0.78)),
             ("green: rail ear face y = 0.375 and slot plane x = -0.25", (-0.27, 0.417, 0.78)),
             ("19\" rail", (-0.296, 0.36, 0.78)), ("ear flange 0.3755 .. 0.3815", (-0.29, 0.40, 0.78)),
             ("ear leg on the body side", (-0.226, 0.345, 0.78))], 0.0028),
        # side cut at x = 0.18 through the half rack's top slot: server top 6 mm under the cell top, roof in the 5 mm
        "clearance_section_halfrack_top": (
            "half", (6.0, 0.31, 1.235), (0.0, 0.31, 1.235), 0.08, 6.0 - 0.18,
            [((0.178, 0.272, 1.25), (0.178, 0.348, 1.25), "EmGreen"),
             ((0.178, 0.272, 1.245), (0.178, 0.348, 1.245), "EmRed")],
            [("SIDE CUT x = 0.18, HALF RACK TOP SLOT", (0.178, 0.31, 1.2625)),
             ("green: cell / slot top z = 1.250   red: roof underside 1.245", (0.178, 0.31, 1.2575)),
             ("server lid top z = 1.244 (6 mm under the cell top)", (0.178, 0.31, 1.225))], 0.0022),
    }
    for nm, (which, loc, tgt, ortho, clip, lines, caps, csz) in sec.items():
        if not want(nm):
            continue
        s = Shot(nm, res=(1600, 1200), floor=None, light=1.8)
        if which == "full":
            _rack(s, built, FULL, FULL_MIX)
        else:
            _rack(s, built, HALF, HALF_MIX)
        s.camera(loc, tgt, 50, ortho=ortho)
        s.cam.data.clip_start = clip
        for p0, p1, mat in lines:
            s.link(_line(p0, p1, mat, ortho / 400))
        for txt, at in caps:   # flat captions facing the ortho camera (no track-to: the camera looks straight on)
            o = s.caption(txt, at, csz)
            o.constraints.clear()
            o.rotation_euler = s.cam.rotation_euler
        s.render()


def _line(p0, p1, mat, t):
    """A thin emissive guide line (a box) from p0 to p1 for annotated sections."""
    import bmesh
    import bpy
    p0, p1 = Vector(p0), Vector(p1)
    bm = bmesh.new()
    lo = Vector([min(a, b) - t / 2 for a, b in zip(p0, p1)])
    hi = Vector([max(a, b) + t / 2 for a, b in zip(p0, p1)])
    vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.scale(bm, vec=hi - lo, verts=vs)
    bmesh.ops.translate(bm, vec=(lo + hi) / 2, verts=vs)
    me = bpy.data.meshes.new("guide")
    bm.to_mesh(me)
    me.materials.append(PM.get(mat))
    return bpy.data.objects.new("guide", me)


# ---------------------------------------------------------------------------------------------------- standalone etc.
def standalone(built):
    nm = "servers_standalone_floor"
    if not want(nm):
        return
    s = Shot(nm, res=(2000, 1150), floor=(-3, 1.5, -1.5, 2))
    _srv(s, built, "DC_Srv_Compute", x=0.0)
    _srv(s, built, "DC_Srv_Storage", x=0.0, z=0.25)             # stacked on the compute (top / bottom mounts)
    _srv(s, built, "DC_Srv_Switch", x=-0.5)                     # flush neighbour (side mounts)
    _srv(s, built, "DC_Srv_Blank", x=-1.25, rot=25)
    s.inst(human(), T(-2.0, 0.3, 0) @ Rz(160))
    s.camera((0.9, 3.2, 1.6), (-0.8, 0, 0.35), 32)
    s.caption("standalone on the floor: compute + storage stacked, switch as a flush neighbour, blank", (-0.8, 0.6, 1.0),
              0.05)
    s.render()


def paints(built):
    nm = "servers_paints_black_keen_blue"
    if not want(nm):
        return
    s = Shot(nm, res=(2200, 1250), floor=(-3, 1.2, -1.2, 2.5))
    s.camera((-0.75, 3.9, 1.0), (-0.75, 0, 0.38), 35)
    # three rows stacked vertically like a rack face: row = paint
    for r, p in enumerate(("black", "keen", "blue")):
        for i, n in enumerate(SERVERS):
            _srv(s, built, n, x=-0.62 * i, z=0.25 * (2 - r), paint=p)
        s.caption(("BLACK", "KEEN GREY", "BLUE")[r], (0.55, 0.3, 0.25 * (2 - r) + 0.12), 0.05)
    s.render()


def vanilla_compare(built, paint="keen"):
    nm = "servers_vanilla_comparison"
    if not want(nm):
        return
    s = Shot(nm, res=(2200, 1100), floor=(-4.5, 1.0, -1.5, 1.5))
    s.camera((-1.95, 4.6, 1.3), (-1.95, 0, 0.18), 30)
    for i, n in enumerate(SERVERS):
        _srv(s, built, n, x=-0.62 * i, paint=paint)
    x = -2.55
    for rel, lbl, rot in (("Timer/50/Models/NonFractured/Timer50.fbx", "vanilla Timer50", 0),
                          ("Batteries/Battery/50/Models/NonFractured/Battery50.fbx", "vanilla Battery50", -90)):
        c, lo, hi = vanilla(rel, paint)
        w = hi.x - lo.x
        ctr = (lo + hi) / 2
        s.inst(c, T(x - w / 2, 0, 0) @ Rz(rot) @ T(-ctr.x, -ctr.y, -lo.z))
        s.caption(lbl, (x - w / 2, 0.3, hi.z - lo.z + 0.12), 0.045)
        x -= w + 0.35
    s.caption("OURS: blank, compute, storage, switch (6U, 0.5 x 0.25 x 0.75 m, Keen grey)", (-0.93, 0.3, 0.45), 0.045)
    s.render()


def render_all(built):
    missing = [n for n in SERVERS + (FULL, HALF) if n not in built]
    PV.OUT = OUT          # Shot.render writes into PV.OUT
    PM.get("Caption")
    for n in SERVERS:
        if n in built:
            per_server(built, n)
    if all(n in built for n in SERVERS):
        lineup(built)
        standalone(built)
        paints(built)
        vanilla_compare(built)
    if missing:
        print("servers previews: not built, skipping the scenes that need them:", missing)
    if all(n in built for n in SERVERS + (FULL, HALF)):
        in_rack(built)
        ear_closeups(built)
