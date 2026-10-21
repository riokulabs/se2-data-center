"""Every block at in-game distances (preview/block-views/<set>/, set = DC_BLOCK_VIEWS_SET, default "before").

Per catalogue block, at an in-game-like field of view (25 mm on 16:9, ~71 deg horizontal) and a player's eye
height (1.65 m):
  * <block>_front34_1m / _front34_3m: from front-left, the block 1 m / 3 m away (horizontal, from its front face);
  * <block>_back34_1m / _back34_3m: from back-right;
  * racks also <block>_top34_3m (from above: the roof / tray), servers <block>_side_1m (the body side and top);
  * <block>_vanilla: ours beside the most comparable vanilla block (read-only import), same light.
Plus the shared scenes: vp1_servers_in_rack_3m / _1m (every 6U type in one open rack: distinguishable at 3 m?),
vp1_hero_aisle (the hero aisle at this set's resolution).

Racks stand on the floor, populated (the store-preview server mixes), doors closed; servers stand on a dark
0.9 m pedestal (rack-slot height), default paint, indicators in their default states.

    DC_PREVIEW=block-views DC_BLOCK_VIEWS_SET=before blender -b --python Source/Model/build_dc.py -- all
(DC_SHOTS=prefix,... renders a subset)."""
import math
import os

import bmesh
import bpy
from mathutils import Vector

from . import catalog, config
from . import preview as PV
from . import preview_icons as pv_icons
from .preview import Rz, T, want

SET = os.environ.get("DC_BLOCK_VIEWS_SET", "before")
OUT = os.path.join(config.PREVIEW_DIR, os.environ.get("DC_VP_DIR", "block-views"), SET)   # DC_VP_DIR=<folder> for another set
RES = (1280, 720)
LENS = 25
EYE = 1.65
PED = 0.9   # server pedestal height

VANILLA = {   # block -> (vanilla FBX rel to Blocks/, label, yaw so its front faces +Y)
    "rack": ("Batteries/Battery/250/Models/NonFractured/Battery250.fbx", "vanilla Battery250", -90),
    "DC_Srv_Timer": ("Timer/50/Models/NonFractured/Timer50.fbx", "vanilla Timer50", 0),
    "DC_Srv_EventCtl": ("EventController/100/Models/NonFractured/EventController100.fbx", "vanilla EventController100", 0),
    "DC_Srv_KVM": ("ControlPanel/25/Models/NonFractured/ControlPanel25.fbx", "vanilla ControlPanel25", 0),
    "DC_Srv_UPS": ("Batteries/Battery/50/Models/NonFractured/Battery50.fbx", "vanilla Battery50", -90),
    "DC_Srv_Status": ("LCDPanels/NarrowLCD/50/Models/Nonfractured/NarrowLCD50.fbx", "vanilla NarrowLCD50", 0),
    "server": ("Conveyors/ConveyorSorter/50/Models/NonFractured/ConveyorSorter50.fbx", "vanilla ConveyorSorter50", 0),
}

MIX42 = pv_icons.MIX_KVM
MIX24 = ("UPS", None, "DC_Srv_Switch", "DC_Srv_Status")
IN_RACK = ("DC_Srv_Compute", "DC_Srv_Storage", "DC_Srv_Switch", "DC_Srv_Blank", "DC_Srv_Timer", "DC_Srv_EventCtl",
           "DC_Srv_Status", "DC_Srv_Programmable")


def _scene(name):
    s = pv_icons.Mood(name, res=RES, room=(-4.0, 4.0, -4.0, 4.0), walls=False, ceiling_visible=False,
                 strips=((-2.0, 2.0, 0.0),), world=(0.020, 0.021, 0.025))
    s.sc.render.resolution_percentage = 100
    try:
        s.sc.eevee.taa_render_samples = 32
    except Exception:
        pass
    return s


def _lights(s, tgt, front=True):
    """Even comparison light: a soft key from the camera side, a cool fill from the other side, a top wash."""
    tgt = Vector(tgt)
    c = s.cam.location
    d = (c - tgt)
    d.z = 0
    d.normalize()
    side = d.cross(Vector((0, 0, 1)))
    s.soft(tgt + d * 2.5 - side * 1.5 + Vector((0, 0, 1.6)), tgt, 260, size=3.0, name="key")
    s.soft(tgt + d * 2.0 + side * 2.5 + Vector((0, 0, 0.6)), tgt, 90, size=3.0, col=(0.75, 0.85, 1.0), name="fill")
    s.soft(tgt + Vector((0, 0, 3.0)), tgt, 160, size=4.0, name="top")
    s.soft(tgt - d * 2.5 + side * 1.0 + Vector((0, 0, 1.5)), tgt, 120, size=2.0, col=(0.8, 0.9, 1.0), name="rim")


def _render(s):
    PV.OUT = OUT
    return s.render()


def _pedestal(s, x=0.0, y=0.0, h=PED, w=0.44, d=0.6):
    bm = bmesh.new()
    s._box(bm, (x - w / 2, y - d / 2, 0.0), (x + w / 2, y + d / 2, h - 0.002), 0)
    s._obj("mood_pedestal", bm, [pv_icons._mat("mood_ped", (0.03, 0.031, 0.035), 0.5, 0.4)])


def _place(s, built, name):
    """Put the block at the origin; returns (front face y, centre z, height, back face y)."""
    spec = catalog.BY_NAME[name]
    if spec.family == "rack":
        H = 0.25 * spec.cells[1]
        pv_icons.rack(s, built, name, f=0.0, f_rear=0.0, paint="keen", mix=MIX42 if H > 2 else MIX24, fan=20, working=True)
        return 0.6, H / 2, H, -0.6
    h = 0.25 * spec.cells[1]
    _pedestal(s)
    pv_icons.server(s, built, name, z=PED, kvm_f=1.0)
    return 0.375, PED + h / 2, h, -0.375


def _cam_at(s, tgt, horiz_dir, dist, z):
    d = Vector((horiz_dir[0], horiz_dir[1], 0)).normalized()
    loc = Vector(tgt) + d * dist
    loc.z = z
    s.camera(tuple(loc), tuple(tgt), LENS)


def per_block(built, name):
    spec = catalog.BY_NAME[name]
    rack = spec.family == "rack"
    views = [("front34_1m", (-0.7, 1.0), 1.0, True), ("front34_3m", (-0.7, 1.0), 3.0, True),
             ("back34_1m", (0.7, -1.0), 1.0, False), ("back34_3m", (0.7, -1.0), 3.0, False)]
    views += [("top34_3m", (-0.7, 1.0), 3.0, True)] if rack else [("side_1m", (-1.0, 0.25), 1.0, True)]
    for v, hd, dist, front in views:
        nm = f"{name}_{v}"
        if not want(nm):
            continue
        s = _scene(nm)
        yf, zc, H, yb = _place(s, built, name)
        face_y = yf if front else yb
        if rack:
            tz = min(1.3, H * 0.62) if dist < 2 else H * 0.5
            if v == "top34_3m":
                tz = H * 0.85
            tgt = Vector((0.0, face_y * 0.5, tz))
            cz = EYE if v != "top34_3m" else H + 1.4
        else:
            tgt = Vector((0.0, 0.0, zc))
            cz = EYE
        # dist = from the face plane (horizontal), along the 3/4 direction
        d = Vector((hd[0], hd[1], 0)).normalized()
        start = Vector((0.0, face_y, 0.0)) if v != "side_1m" else Vector((-0.25, 0.0, 0.0))
        loc = start + d * dist
        loc.z = cz
        s.camera(tuple(loc), tuple(tgt), LENS)
        _lights(s, tgt)
        _render(s)


def vanilla_pair(built, name):
    nm = f"{name}_vanilla"
    if not want(nm):
        return
    spec = catalog.BY_NAME[name]
    rel, label, rot = VANILLA.get(name) or VANILLA[spec.family]
    s = _scene(nm)
    yf, zc, H, yb = _place(s, built, name)
    c, lo, hi = PV.vanilla(rel)
    ctr = (lo + hi) / 2
    w = max(hi.x - lo.x, hi.y - lo.y)
    gap = 0.35 if spec.family == "server" else 0.6
    x = 0.5 + gap + w / 2 if spec.family == "rack" else 0.25 + gap + w / 2
    base = 0.0 if spec.family == "rack" else PED
    if spec.family == "server":
        _pedestal(s, x=x, w=max(0.3, w * 0.8), d=max(0.3, w * 0.8))
    s.inst(c, T(x, 0, base) @ Rz(rot) @ T(-ctr.x, -ctr.y, -lo.z))
    vh = hi.z - lo.z
    tgt = Vector(((x - 0.25) / 2 if spec.family == "server" else (x - 0.5) / 2 + 0.0, 0.0,
                  (zc if spec.family == "server" else max(H, vh) * 0.5)))
    span = x + w / 2 + (0.25 if spec.family == "server" else 0.5)
    dist = max(1.4, span * 1.35) if spec.family == "server" else max(3.5, span * 1.45, max(H, vh) * 1.5)
    d = Vector((-0.2, 1.0, 0.0)).normalized()
    loc = tgt + d * dist
    loc.z = EYE if spec.family == "server" else max(EYE, H * 0.7)
    s.camera(tuple(loc), tuple(tgt), 35)
    s.caption("OURS", (0.0, 0.0, base + (H if spec.family == "rack" else 0.25 * spec.cells[1]) + 0.12),
              0.05 if spec.family == "server" else 0.1)
    s.caption(label, (x, 0.0, base + (hi.z - lo.z) + 0.12), 0.05 if spec.family == "server" else 0.1)
    _lights(s, tgt)
    _render(s)


def servers_in_rack(built):
    for dist in (3, 1):
        nm = f"vp1_servers_in_rack_{dist}m"
        if not want(nm):
            continue
        s = _scene(nm)
        pv_icons.rack(s, built, "DC_Rack42_Open", paint="keen", mix=IN_RACK, fan=10, working=True)
        pv_icons.rack(s, built, "DC_Rack24_Open", x=1.0, paint="keen", mix=("UPS", None, "KVM", "DC_Srv_Blank"), fan=10, working=True)
        tgt = Vector((0.3, 0.3, 1.2 if dist == 3 else 1.25))
        d = Vector((-0.35, 1.0, 0.0)).normalized()
        loc = Vector((0.3, 0.6, 0.0)) + d * dist
        loc.z = EYE
        s.camera(tuple(loc), tuple(tgt), LENS)
        _lights(s, tgt)
        _render(s)


def hero(built):
    nm = "vp1_hero_aisle"
    if want(nm):
        s = pv_icons.aisle_scene(built, nm, res=(1600, 860))
        s.camera((0.05, 2.05, 1.55), (1.25, 0.55, 1.05), 20)
        s.soft((-1.6, 2.6, 1.7), (1.2, 0.6, 1.0), 70, size=2.5, name="front")
        s.soft((3.8, 1.6, 2.4), (1.0, 0.6, 1.0), 40, size=2.0, col=(0.7, 0.85, 1.0), name="back")
        _render(s)
    nm = "vp1_hero_aisle_wide"
    if want(nm):
        s = pv_icons.aisle_scene(built, nm, res=(1600, 860))
        s.camera((-4.4, 1.375, 2.6), (1.0, 1.375, 0.95), 28)
        s.soft((-4.8, 1.4, 2.2), (1.0, 1.4, 1.0), 60, size=3.0, name="front")
        s.soft((4.6, 1.4, 2.6), (1.0, 1.4, 1.0), 40, size=2.0, col=(0.7, 0.85, 1.0), name="back")
        _render(s)


def render_all(built):
    from . import preview_mats as PM
    PM.get("Caption")
    os.makedirs(OUT, exist_ok=True)
    for b in catalog.CORE_BLOCKS:         # racks and servers (trays, built or not, have their own previews)
        if b.name in built:
            per_block(built, b.name)
            vanilla_pair(built, b.name)
    if all(b.name in built for b in catalog.CORE_BLOCKS):
        servers_in_rack(built)
        hero(built)
