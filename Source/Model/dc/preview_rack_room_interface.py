"""Rack room-interface previews: the racks' room interface (containment rails, freed PDU columns with the plinth
receptacles, label pads) and a ghost containment roof + door over a rack row.

    DC_RACK_ROOM_SET=before|after DC_PREVIEW=rack-room-interface blender -b --python Source/Model/build_dc.py -- all
    python3 Source/Model/rack_room_interface_sheet.py          # before | after pairs and the contact sheet

Writes preview/rack-room-interface/<set>/ (set = DC_RACK_ROOM_SET, default "after"). DC_SHOTS=prefix,... renders a subset. Shots:
  * <rack>_front34 / <rack>_rear34 / <rack>_plan: every rack variant (open, front + rear doors), servers fitted;
  * <rack>_pdu_cols: the rear of the rack with the ghost PDU envelopes (dims.PDU_ENVELOPE x the PDU band, green);
  * <rack>_pdu_close / <rack>_receptacle: the A column and its plinth receptacle up close;
  * <rack>_rail_front / <rack>_rail_back: the containment rail, its clamp pads and the CONTAINMENT tag (full racks);
  * half_top_pads: the half rack's top with its label pads (dims.LABEL_X x LABEL_Y, front and back) ghosted;
  * kvm_rail_34 / kvm_rail_side: a KVM popped out in the full rack's top slot beside the rail (section at x = 0);
  * doors85_<rack>: the door racks open at 85 deg (front and rear) under the rail;
  * <rack>_lods: LOD0 / LOD1 / LOD2 side by side (rear 3/4);
  * vanilla_cmp: the rack with a vanilla DeckPanel250 at the roof position and a vanilla NarrowSlidingDoor
    (read-only FBX), the room pieces' clone sources at the same scale and light;
  * row_ghost_{34,end,section,plan}: two rows of three full racks facing across a 1.5 m cold aisle, the ghost roof
    panels (1.0 m x W in the top cell, on the rails) and the ghost end door (the 0.25 m slice beyond the row end,
    2W wide with its leaf pockets in front of the end racks' sides), placed from dc/dims.py only, dimensioned."""
import math
import os

import bpy
from mathutils import Vector

from . import catalog, config, dims as DM
from . import preview as PV
from . import preview_mats as PM
from . import preview_rack_tops as pv_rack_tops
from . import preview_rack_doors as pv_rack_doors
from .preview import T, want

SET = os.environ.get("DC_RACK_ROOM_SET", "after")
ROOT = os.path.join(config.PREVIEW_DIR, "rack-room-interface")
OUT = os.path.join(ROOT, SET)
RACKS = ("DC_Rack42_Open", "DC_Rack42_SplitFrontRear", "DC_Rack24_Open", "DC_Rack24_SplitFrontRear")
FULL_MIX = ("UPS", None, "DC_Srv_Storage", "DC_Srv_Timer", "DC_Srv_Compute", "DC_Srv_Compute", "DC_Srv_Status", "KVM")
HALF_MIX = ("UPS", None, "DC_Srv_Switch", "DC_Srv_Compute")
W_AISLE = 1.5


def _H(name):
    return 0.25 * catalog.BY_NAME[name].cells[1]


def _ZT(name):
    return DM.rack_frame(catalog.BY_NAME[name].cells[1])[1]


def _render(s):
    PV.OUT = OUT
    return s.render()


def _mix(name, servers=True):
    if not servers:
        return ()
    return FULL_MIX if "42" in name else HALF_MIX


def _rack(s, built, name, x=0.0, y=0.0, rot=0.0, f=0.0, f_rear=None, lod=0, servers=True, paint="keen"):
    mix = tuple(m for m in _mix(name, servers))
    mix = tuple(m if (m is None or m in ("UPS", "KVM", "PROG") or m in built) else None for m in mix)
    if "KVM" in mix and "DC_Srv_KVM" not in built:
        mix = tuple(None if m == "KVM" else m for m in mix)
    if "UPS" in mix and "DC_Srv_UPS" not in built:
        mix = tuple(None if m == "UPS" else m for m in mix)
    return pv_rack_doors.rack(s, built, name, x, y, rot, f=f, paint=paint, mix=mix, fan=20, working=True, lod=lod,
                   f_rear=f_rear)


def _pdu_band(name):
    """Local z of the PDU band (the slot band under the full rack's tray; under the half rack's top corner caps)."""
    try:
        from . import rack
        return rack.pdu_band(catalog.BY_NAME[name])
    except AttributeError:   # the "before" set: the band the plan asks for
        H, ZT = _H(name), _ZT(name)
        return 0.25, (ZT if "42" in name else H - 0.12)


def _envelopes(s, name, x=0.0):
    (x0, x1), (y0, y1) = DM.PDU_ENVELOPE
    z0, z1 = _pdu_band(name)
    for sx in (-1, 1):
        a, b = sorted((sx * x0, sx * x1))
        pv_rack_tops._ghost_box(s, f"pdu_env_{sx}", (x + a, y0, z0 + 0.002), (x + b, y1, z1), "GhostMount")


# ---------------------------------------------------------------------------------------------------- racks
def rack_views(built):
    for name in RACKS:
        if name not in built:
            continue
        H = _H(name)
        doors = "Split" in name
        for v in ("front34", "rear34", "plan"):
            nm = f"{name}_{v}"
            if not want(nm):
                continue
            s = pv_rack_tops._scene(nm, res=(1500, 1500) if v == "plan" else (1500, 1150))
            if v == "front34":
                s.camera((-1.55, 2.35, H + 0.95), (0.0, 0.1, H * 0.62), 34)
            elif v == "rear34":
                s.camera((1.6, -2.4, H + 0.9), (0.0, -0.1, H * 0.6), 34)
            else:
                pv_rack_tops._ortho_down(s, 0.0, 0.0, H, 1.45)
            _rack(s, built, name, f=0.0, f_rear=1.0 if (doors and v == "rear34") else 0.0)
            if v == "plan":
                pv_rack_doors.flat(s, "FRONT", (0.0, 0.67, H + 0.01), 0.05)
            pv_rack_tops._lights(s, (0, 0, H * 0.6), 1.0 if v != "plan" else 0.8)
            _render(s)


def pdu_shots(built):
    for name in RACKS:
        if name not in built:
            continue
        H = _H(name)
        doors = "Split" in name
        fr = 1.0 if doors else 0.0
        nm = f"{name}_pdu_cols"
        if want(nm):
            s = pv_rack_tops._scene(nm, res=(1500, 1250))
            s.camera((0.0, -2.9, H * 0.55 + 0.6), (0.0, -0.4, H * 0.5), 38)
            _rack(s, built, name, f_rear=fr)
            _envelopes(s, name)
            z0, z1 = _pdu_band(name)
            s.caption("ghost: dims.PDU_ENVELOPE x the PDU band (green), both columns", (0.0, -0.7, z1 + 0.35), 0.045)
            pv_rack_tops._lights(s, (0, -0.5, H * 0.5), 1.0)
            _render(s)
        rx, ry = DM.PDU_RECEPTACLE
        nm = f"{name}_pdu_close"
        if want(nm):
            s = pv_rack_tops._scene(nm, res=(1300, 1500))
            zc = min(1.0, H * 0.45)
            s.camera((rx - 0.45, -1.35, zc + 0.30), (rx, -0.47, zc - 0.05), 36)
            _rack(s, built, name, f_rear=fr)
            pv_rack_tops._lights(s, (rx, -0.5, zc), 0.6)
            _render(s)
        nm = f"{name}_receptacle"
        if want(nm):
            s = pv_rack_tops._scene(nm, res=(1400, 1100))
            s.camera((rx - 0.22, ry - 0.50, 0.78), (rx, ry, 0.25), 34)
            _rack(s, built, name, f_rear=fr)
            pv_rack_tops._lights(s, (rx, ry, 0.3), 0.4)
            _render(s)


def rail_shots(built):
    for name in ("DC_Rack42_Open", "DC_Rack42_SplitFrontRear"):
        if name not in built:
            continue
        H, ZT = _H(name), _ZT(name)
        for side, sy in (("front", 1), ("back", -1)):
            nm = f"{name}_rail_{side}"
            if not want(nm):
                continue
            s = pv_rack_tops._scene(nm, res=(1600, 1000))
            tgt = Vector((0.12, sy * 0.6, ZT + 0.16))
            s.camera(tuple(tgt + Vector((-0.55, sy * 1.05, 0.38))), tuple(tgt), 38)
            _rack(s, built, name, f=0.0)
            pv_rack_tops._lights(s, tgt, 0.6)
            _render(s)


def half_top(built):
    name = "DC_Rack24_Open"
    nm = "half_top_pads"
    if name not in built or not want(nm):
        return
    H = _H(name)
    s = pv_rack_tops._scene(nm, res=(1600, 1150))
    s.camera((-1.25, 1.75, H + 1.1), (0.0, 0.0, H - 0.05), 32)
    _rack(s, built, name)
    for sy in (1, -1):
        y0, y1 = sorted(sy * v for v in DM.LABEL_Y)
        pv_rack_tops._ghost_box(s, f"pad_{sy}", (DM.LABEL_X[0], y0, H + 0.001), (DM.LABEL_X[1], y1, H + 0.012), "GhostMount")
        # the rack label's cell (0.5 x 0.25 x 0.25 m) standing on the pad
        pv_rack_tops._ghost_box(s, f"label_{sy}", (DM.LABEL_X[0] + 0.004, y0 + 0.004, H + 0.016),
                       (DM.LABEL_X[1] - 0.004, y1 - 0.004, H + 0.25 - 0.004), "GhostSlot")
    s.caption("label pads: LABEL_X x LABEL_Y front and back (green); ghost rack label cell (cyan)",
              (0.0, 0.0, H + 0.45), 0.045)
    pv_rack_tops._lights(s, (0, 0, H), 1.0)
    _render(s)


def kvm_rail(built):
    name = "DC_Rack42_Open"
    if name not in built or "DC_Srv_KVM" not in built:
        return
    H, ZT = _H(name), _ZT(name)
    for v in ("34", "side"):
        nm = f"kvm_rail_{v}"
        if not want(nm):
            continue
        s = pv_rack_tops._scene(nm, res=(1600, 1250))
        if v == "34":
            s.camera((-1.25, 2.1, ZT + 0.75), (0.0, 0.45, ZT - 0.05), 34)
        else:   # an ortho section at x = 0 seen from -x (front = right)
            cam = s.camera((-5.0, 0.30, ZT + 0.05), (0.0, 0.30, ZT + 0.05), 50, ortho=1.6)
            cam.data.clip_start = 5.0 - 0.001
        _rack(s, built, name, f=0.0)
        y0, y1 = DM.CONTAIN_RAIL_Y
        z0, z1 = ZT + DM.CONTAIN_RAIL_DZ[0], ZT + DM.CONTAIN_RAIL_DZ[1]
        if v == "side":
            xd = 0.001
            pv_rack_tops._ghost_box(s, "rail_band", (xd - 0.002, y0, z0), (xd, y1, z1), "GhostOcc", wire=False)
            pv_rack_tops._ghost_box(s, "roof_cell", (xd - 0.002, 0.625, ZT), (xd, 0.625 + 0.5, H), "GhostSlot", wire=False)
            pv_rack_tops._dim(s, (xd, 0.66, ZT), (xd, 0.66, H), "roof cell ZT..H", (0, 0.02, 0), off=(0, 0.22, 0), size=0.03,
                     flat_x=True)
            pv_rack_tops._dim(s, (xd, y0, z1 + 0.06), (xd, y1, z1 + 0.06), "CONTAIN_RAIL_Y 0.600..0.624", (0, 0, 0.015),
                     off=(0, 0, 0.04), size=0.025, flat_x=True)
            pv_rack_tops._line(s, (xd, -0.3, ZT), (xd, 1.1, ZT), 0.003)
            pv_rack_tops._cap_x(s, "ZT (slot band top)", (xd, -0.15, ZT - 0.03), 0.025)
            pv_rack_tops._cap_x(s, "section x = 0: the KVM lid stays behind the rail band (orange) above ZT",
                       (xd, 0.35, H + 0.2), 0.03)
        pv_rack_tops._lights(s, (0, 0.4, ZT), 0.9)
        _render(s)


def doors85(built):
    for name in ("DC_Rack42_SplitFrontRear", "DC_Rack24_SplitFrontRear"):
        if name not in built:
            continue
        H = _H(name)
        for v, loc in (("front", (-1.7, 2.3, H + 0.6)), ("rear", (1.7, -2.3, H + 0.6))):
            nm = f"doors85_{name}_{v}"
            if not want(nm):
                continue
            s = pv_rack_tops._scene(nm, res=(1500, 1150))
            s.camera(loc, (0.0, 0.0, H * 0.55), 34)
            _rack(s, built, name, f=1.0, f_rear=1.0)
            s.caption(f"doors open {DM.DOOR_OPEN_DEG:.0f} deg", (0.0, 0.0, H + 0.25), 0.05)
            pv_rack_tops._lights(s, (0, 0, H * 0.5), 1.0)
            _render(s)


def lods(built):
    for name in ("DC_Rack42_Open", "DC_Rack24_Open"):
        nm = f"{name}_lods"
        if name not in built or not want(nm):
            continue
        H = _H(name)
        s = pv_rack_tops._scene(nm, res=(1900, 1000))
        s.camera((3.6, -3.6, H + 1.2), (1.2, 0.0, H * 0.5), 34)
        n = min(3, len(built[name]["lods"]) - 1)
        for L in range(n):
            _rack(s, built, name, x=1.2 * L, lod=L, servers=False)
            s.caption(f"LOD{L}", (1.2 * L, -0.7, H + 0.15), 0.08)
        pv_rack_tops._lights(s, (1.2, -0.5, H * 0.5), 1.3)
        _render(s)


def vanilla(built):
    nm = "vanilla_cmp"
    name = "DC_Rack42_Open"
    if name not in built or not want(nm):
        return
    H, ZT = _H(name), _ZT(name)
    s = pv_rack_tops._scene(nm, res=(1800, 1150))
    s.camera((-2.4, 3.4, 2.3), (0.3, 0.6, 1.4), 30)
    _rack(s, built, name)
    # vanilla DeckPanel250 at the roof position: in the aisle's top cell, its edge against the rail
    c, lo, hi = PV.vanilla("DeckPanel/250/Models/NonFractured/DeckPanel250.fbx")
    ctr = (lo + hi) / 2
    s.inst(c, T(0.0, 0.625 + (hi.y - lo.y) / 2, H - (hi.z - lo.z) / 2) @ T(-ctr.x, -ctr.y, -ctr.z))
    s.caption("vanilla DeckPanel250 (roof clone source) at the roof position", (0.0, 1.0, H + 0.25), 0.045)
    c, lo, hi = PV.vanilla("Doors/SlideDoorNarrow/250/Models/NonFractured/NarrowSlidingDoor.fbx")
    ctr = (lo + hi) / 2
    s.inst(c, T(1.6, 0.6, 0.0) @ T(-ctr.x, -ctr.y, -lo.z))
    s.caption("vanilla NarrowSlidingDoor (door clone source)", (1.6, 0.6, (hi.z - lo.z) + 0.2), 0.045)
    s.caption("OURS 42U (rail, PDU columns)", (0.0, 0.0, H + 0.12), 0.05)
    pv_rack_tops._lights(s, (0.5, 0.5, 1.4), 1.4)
    _render(s)


# ---------------------------------------------------------------------------------------------------- the row
def _row(s, built, name="DC_Rack42_Open", n=3, W=W_AISLE):
    """Two rows of n full racks facing across the aisle (y = 0 centre): row S (fronts +y), row N (fronts -y)."""
    yc = W / 2 + 0.625
    for i in range(n):
        _rack(s, built, name, x=float(i), y=-yc, rot=0.0)
        _rack(s, built, name, x=float(i), y=yc, rot=180.0)
    return yc


def _ghost_room(s, name, n=3, W=W_AISLE):
    H, ZT = _H(name), _ZT(name)
    for i in range(n):   # roof panels: 1.0 m along the row x W, the aisle's top cell (ZT .. H)
        pv_rack_tops._ghost_box(s, f"roof_{i}", (i - 0.5 + 0.004, -W / 2 + 0.002, ZT + 0.004),
                       (i + 0.5 - 0.004, W / 2 - 0.002, H - 0.002), "GhostSlot")
    xe = n - 0.5        # the row end: the door slice x xe .. xe + 0.25, 2W across (the aisle + a pocket each side)
    pv_rack_tops._ghost_box(s, "door_frame", (xe + 0.004, -W, 0.004), (xe + 0.25 - 0.004, W, H - 0.004), "GhostOcc")
    for sy in (-1, 1):   # the leaf pockets in front of the end racks' side panels
        a, b = sorted((sy * W / 2, sy * W))
        pv_rack_tops._ghost_box(s, f"pocket_{sy}", (xe + 0.03, a + 0.01, 0.02), (xe + 0.22, b - 0.01, ZT - 0.02), "GhostMount")
    pv_rack_tops._ghost_box(s, "door_header", (xe + 0.01, -W / 2, ZT), (xe + 0.24, W / 2, H - 0.004), "GhostReg", wire=False)


def row_ghost(built):
    name = "DC_Rack42_Open"
    if name not in built:
        return
    H, ZT = _H(name), _ZT(name)
    n, W = 3, W_AISLE
    for v in ("34", "end", "section", "plan"):
        nm = f"row_ghost_{v}"
        if not want(nm):
            continue
        s = pv_rack_tops._scene(nm, res=(1900, 1250) if v != "section" else (1800, 1400))
        s.sc.render.film_transparent = False
        if v == "34":
            s.camera((-2.6, 4.2, 4.6), (1.2, 0.0, 1.6), 30)
        elif v == "end":
            s.camera((n + 2.6, 0.0, 1.7), (0.0, 0.0, 1.6), 38)
        elif v == "section":   # across the aisle, x = 1 (the middle rack pair), seen from -x
            cam = s.camera((-4.0, 0.0, 1.9), (1.0, 0.0, 1.9), 50, ortho=4.6)
            cam.data.clip_start = 5.0 - 0.002
        else:
            pv_rack_tops._ortho_down(s, 1.4, 0.0, H, 6.2, height=4.0)
        _row(s, built, name, n, W)
        _ghost_room(s, name, n, W)
        y0, y1 = DM.CONTAIN_RAIL_Y
        if v in ("34", "end"):
            pv_rack_tops._dim(s, (-0.75, -W / 2, H + 0.12), (-0.75, W / 2, H + 0.12), f"aisle W {W:.1f}", (0.03, 0, 0),
                     off=(0, 0, 0.1), size=0.07)
            pv_rack_tops._dim(s, (-0.5, -W / 2 - 0.3, H + 0.3), (0.5, -W / 2 - 0.3, H + 0.3), "roof panel 1.0 (rack pitch)",
                     (0, 0.03, 0), off=(0, 0, 0.1), size=0.06)
            s.caption("ghosts from dc/dims.py: roof panels (cyan) on the containment rails, end door (amber) with "
                      "leaf pockets (green) and header (red)", (1.0, 0.0, H + 0.85), 0.06)
        elif v == "section":
            xd = 1.0 + 0.002
            yr = W / 2 + 0.625 - y0    # rail band |y| in the aisle frame
            pv_rack_tops._dim(s, (xd, -W / 2, H + 0.1), (xd, W / 2, H + 0.1), f"aisle W = {W:.1f} (rack front planes)",
                     (0, 0, 0.03), off=(0, 0, 0.08), size=0.06, flat_x=True)
            pv_rack_tops._dim(s, (xd, W / 2 + 0.05, ZT), (xd, W / 2 + 0.05, H), "roof cell\nZT..H 0.25", (0, 0.03, 0),
                     off=(0, 0.35, 0), size=0.045, flat_x=True)
            pv_rack_tops._dim(s, (xd, -yr, ZT + DM.CONTAIN_RAIL_DZ[0]), (xd, -yr, ZT + DM.CONTAIN_RAIL_DZ[1]),
                     "CONTAIN_RAIL_DZ\n0.012..0.238", (0, 0.03, 0), off=(0, -0.45, 0.0), size=0.04, flat_x=True)
            pv_rack_tops._dim(s, (xd, -W / 2 - 1.25, 0.0), (xd, -W / 2 - 1.25, H), f"H {H:.2f}", (0, 0.03, 0),
                     off=(0, -0.2, 0), size=0.05, flat_x=True)
            pv_rack_tops._cap_x(s, "section x = 1.0 across the cold aisle (rack fronts face the aisle)", (xd, 0.0, H + 0.55),
                       0.06)
        else:
            pv_rack_doors.flat(s, f"cold aisle W {W:.1f}: roof panels 1.0 x W (cyan), door slice 0.25 x 2W (amber)",
                    (1.4, 0.0, H + 0.02), 0.08)
        pv_rack_tops._lights(s, (1.2, 0.0, 1.5), 2.2)
        _render(s)


def render_all(built):
    PM.get("Caption")
    os.makedirs(OUT, exist_ok=True)
    rack_views(built)
    pdu_shots(built)
    rail_shots(built)
    half_top(built)
    kvm_rail(built)
    doors85(built)
    lods(built)
    vanilla(built)
    row_ghost(built)
