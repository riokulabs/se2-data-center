"""Indicator server previews: the timer, event-controller and status-display servers (Source/Model/preview/indicator-servers/).

Same rig and stand-ins as the rack and server sets (dc/preview.py, dc/preview_mats.py); vanilla FBX imported READ ONLY from
tools/vanilla-ref. The indicator lamps are shown in their vanilla states with the vanilla ColorIndicatorMaterial
colours (dc/functional.py; SDK BlockMaterials/Indicators_Placeholder): every lamp of an indicator slot takes the
state's material, exactly as the game's indicator component does. Blinking states are shown in both phases.
The status screen shows a sample LCD text (Blender text, emissive, laid on the LCD surface).

    DC_PREVIEW=indicator-servers blender -b --python Source/Model/build_dc.py -- DC_Rack42_Open DC_Rack24_Open DC_Srv_Blank \
        DC_Srv_Compute DC_Srv_Storage DC_Srv_Switch DC_Srv_Timer DC_Srv_EventCtl DC_Srv_Status
(DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution).
"""
import math
import os

import bpy
from mathutils import Matrix

from . import config, functional
from . import preview as PV
from . import preview_mats as PM
from .preview import Rz, Shot, T, human, want

OUT = os.path.join(config.PREVIEW_DIR, "indicator-servers")
H = 0.25
FUNC = ("DC_Srv_Timer", "DC_Srv_EventCtl", "DC_Srv_Status")
DECO = ("DC_Srv_Blank", "DC_Srv_Compute", "DC_Srv_Storage", "DC_Srv_Switch")
FULL, HALF = "DC_Rack42_Open", "DC_Rack24_Open"
SHORT = {"DC_Srv_Timer": "TIMER", "DC_Srv_EventCtl": "EVENT CONTROLLER", "DC_Srv_Status": "STATUS DISPLAY",
         "DC_Srv_Blank": "BLANK", "DC_Srv_Compute": "COMPUTE", "DC_Srv_Storage": "STORAGE", "DC_Srv_Switch": "SWITCH"}
LABEL = {
    "DC_Srv_Timer": "TIMER (Timer50)\nLCD strip + nav keys, 3 drive sleds,\nCOUNT lamp, honeycomb intake",
    "DC_Srv_EventCtl": "EVENT CONTROLLER\nkey switch, reset, T / F action\nport rows with lamps",
    "DC_Srv_Status": "STATUS DISPLAY (LCDFlat50)\nangled LCD bezel, grille strips,\n5-way pad, lamps",
    "DC_Srv_Blank": "BLANK (deco)", "DC_Srv_Compute": "COMPUTE (deco)", "DC_Srv_Storage": "STORAGE (deco)",
    "DC_Srv_Switch": "SWITCH (deco)"}


# ---------------------------------------------------------------------------------------------------- states
def _lin(c):
    return tuple((v / 255.0) ** 2.2 for v in c)


# vanilla ColorIndicatorMaterial colours (R, G, B) and emissivity -> preview emission strength
STATE_MATS = {
    "off": None,                                                     # EmissiveOffBroken / an unlit lens
    "pow": ((153, 0, 0), 2.0), "act": ((0, 127, 0), 7.0), "rdy": ((214, 186, 0), 3.0), "rdy_off": ((96, 83, 0), 1.5),
    "count": ((0, 87, 127), 5.0), "count_off": ((0, 54, 78), 2.0), "null": ((255, 255, 255), 3.0),
}
TIMER_STATES = [("NotFunctional", "off", ""), ("NotPowered", "pow", "blink 2 s, on 10 %: ON phase"),
                ("NotPowered", "off", "OFF phase"), ("Idle", "act", ""), ("Paused", "rdy", "blink 2 s, on 40 %: ON"),
                ("Paused", "rdy_off", "OFF phase (dim)"), ("Running", "count", "blink 1 s, on 10 %: ON"),
                ("Running", "count_off", "OFF phase (dim teal)")]
EVC_STATES = [("NotFunctional", "off", "off"), ("NotPowered", "pow", "pow"), ("NullState", "null", "null"),
              ("True", "act", "off"), ("False", "off", "act")]
DEFAULT = {"DC_Srv_Timer": {functional.TIMER_IND: "act"},                       # Idle
           "DC_Srv_EventCtl": {functional.EVC_TRUE: "act", functional.EVC_FALSE: "off"}}   # True


def state_mat(key):
    if key is None or key == "off" or STATE_MATS.get(key) is None:
        return PM.get("EmOff")
    nm = "pv_state_" + key
    if nm in bpy.data.materials:
        return bpy.data.materials[nm]
    c, e = STATE_MATS[key]
    lc = _lin(c)
    return PM.simple(nm, tuple(0.02 + 0.2 * v for v in lc), 0.3, 0.0, emit=lc, estr=e)


def terminal_mat():
    """Vanilla Terminal material stand-in with its real albedo (the UV region shows) and emission."""
    nm = "pv_TerminalTex"
    if nm in bpy.data.materials:
        return bpy.data.materials[nm]
    path = os.path.join(os.path.expanduser("~/.steam/debian-installation/steamapps/common/Space Engineers 2 - Mod SDK"
                                           "/GameData/Vanilla/Assets/BlockMaterials/Terminal/Terminal_albedo.png"))
    m = bpy.data.materials.new(nm)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path, check_existing=True)
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 2.2
    b.inputs["Roughness"].default_value = 0.15
    return m


def lcd_mat():
    """The status LCD showing text: a dark blue-black lit background (the default LCD look)."""
    return PM.simple("pv_lcd_bg", (0.004, 0.008, 0.014), 0.12, 0.0, emit=(0.01, 0.025, 0.05), estr=1.0)


SLOT_OVERRIDE = {"Terminal": terminal_mat, "LCDScreen_Off": lcd_mat}


def stated(built_or_objs, name, lod=0, paint="keen", states=None, key=None):
    """A copy of one LOD of a built block (or of given objects, e.g. a vanilla import) with preview stand-ins, the
    indicator slots taking the given state materials {slot: state key}."""
    states = DEFAULT.get(name, {}) if states is None else states
    ck = key or (name, lod, paint, tuple(sorted(states.items())))
    cname = "pv6_" + "_".join(str(k) for k in ck)
    if cname in bpy.data.collections:
        return bpy.data.collections[cname]
    objs = built_or_objs[name]["lods"][lod][1] if isinstance(built_or_objs, dict) else built_or_objs
    c = bpy.data.collections.new(cname)
    bpy.context.scene.collection.children.link(c)
    for o in objs:
        if o.type != "MESH":
            continue
        n = o.copy()
        n.data = o.data.copy()
        c.objects.link(n)
        _assign(n, states, paint)
    PV._exclude(c)
    return c


def _assign(n, states, paint, lcd=True):
    """Preview materials by slot name: indicator slots -> state materials, screens -> textured / lit stand-ins."""
    for i, sl in enumerate(n.material_slots):
        if not sl.material:
            continue
        slot = sl.material.name.split(".")[0]
        if slot in states:
            n.material_slots[i].material = state_mat(states[slot])
        elif slot in SLOT_OVERRIDE and (lcd or slot != "LCDScreen_Off"):
            n.material_slots[i].material = SLOT_OVERRIDE[slot]()
        else:
            n.material_slots[i].material = PM.get(PM.keen_key(slot, paint))


LCD_LINES = ("RACK A1   ONLINE", "IN 21C   OUT 33C", "PWR 4.2 KW", "BLOCKS 38/38")


def lcd_text(s, m, lines=LCD_LINES):
    """Sample LCD text laid on the status screen of a server placed with matrix m (its origin = cell-box centre)."""
    sa, sb, sd = functional.STATUS_SCREEN["a"], functional.STATUS_SCREEN["b"], functional.STATUS_SCREEN["d"]
    w, h = sa[1] - sa[0], sb[1] - sb[0]
    ca, cb = (sa[0] + sa[1]) / 2, (sb[0] + sb[1]) / 2
    cu = bpy.data.curves.new("lcdtxt", "FONT")
    cu.body = "\n".join(lines)
    cu.size = h / (len(lines) + 0.9)
    cu.space_line = 1.05
    cu.align_x, cu.align_y = "LEFT", "CENTER"
    mat = PM.simple("pv_lcd_text", (0.6, 0.85, 1.0), 0.4, 0.0, emit=(0.55, 0.85, 1.0), estr=3.0) \
        if "pv_lcd_text" not in bpy.data.materials else bpy.data.materials["pv_lcd_text"]
    cu.materials.append(mat)
    o = bpy.data.objects.new("lcdtxt", cu)
    # face (a, b, d) -> Blender (-a, 0.375 + d, b); the text faces +Y and runs toward -X (the viewer's right)
    loc = (-(ca - w / 2 + 0.012), functional.FRONT_Y + sd + 0.0012, cb)
    o.matrix_world = m @ Matrix.Translation(loc) @ Rz(180) @ Matrix.Rotation(math.radians(90), 4, "X")
    s.link(o)
    return o


def srv(s, built, name, x=0.0, y=0.0, z=0.0, paint="keen", lod=0, rot=0, states=None, text=True):
    """A server standing with its bottom at z (origin = cell-box centre), indicator states applied."""
    m = T(x, y, z + H / 2) @ Rz(rot)
    s.inst(stated(built, name, lod, paint, states), m)
    if name == "DC_Srv_Status" and text and lod <= 2:
        lcd_text(s, m)


def rack(s, built, name, mix, x=0.0, y=0.0, paint="keen", srv_paint=None):
    Hr = 0.25 * (10 if name == FULL else 5)
    s.inst(PV.painted(built, name, 0, paint), T(x, y, Hr / 2))
    for k, n in enumerate(mix, 1):
        if n:
            srv(s, built, n, x, y, 0.25 * k, srv_paint or paint)


# ---------------------------------------------------------------------------------------------------- per server
def per_server(built, name, paint="keen"):
    zc = H / 2
    views = {
        "front": ((0.0, 1.55, zc), (0, 0, zc), 60),
        "3q_front": ((-0.85, 1.15, 0.72), (0, 0.02, zc * 0.8), 50),
        "back": ((0.0, -1.55, zc), (0, 0, zc), 60),
        "closeup_front": ((-0.30, 0.78, 0.33), (-0.12, 0.37, zc), 40),
    }
    # the indicator / screen area close-up (face a, b of the detail -> Blender x = -a, z = b + zc)
    ind = {"DC_Srv_Timer": (0.13, 0.075), "DC_Srv_EventCtl": (0.06, 0.04), "DC_Srv_Status": (-0.03, 0.0)}[name]
    views["closeup_indicator"] = ((-ind[0] + 0.10, 0.75, zc + ind[1] + 0.10), (-ind[0], 0.37, zc + ind[1]), 55)
    for v, (loc, tgt, lens) in views.items():
        nm = f"{name}_{v}"
        if not want(nm):
            continue
        s = Shot(nm, floor=(-1.5, 1.5, -1.5, 1.5))
        srv(s, built, name, paint=paint)
        s.camera(loc, tgt, lens)
        s.render()
    nm = f"{name}_lods"
    if want(nm):
        import json
        with open(config.REPORT_PATH) as f:
            rep = json.load(f)["blocks"].get(name, {}).get("lods", [])
        n = len(built[name]["lods"])
        s = Shot(nm, res=(2200, 900), floor=(-0.8 * n, 1, -1.2, 1.2))
        for i in range(n):
            srv(s, built, name, x=-0.8 * i, lod=i, paint=paint)
        cx = -0.8 * (n - 1) / 2
        s.camera((cx - 0.4, 3.9, 1.2), (cx, 0, 0.15), 35)
        for i in range(n):
            r = rep[i] if i < len(rep) else {}
            s.caption(f"LOD{i}\n{r.get('tris', '?')}/{r.get('max_tris', '?')} tris, "
                      f"{r.get('materials', '?')}/{r.get('max_materials', '?')} mats", (-0.8 * i, 0.4, 0.42), 0.045)
        s.render()


def states(built):
    """Every indicator state on our model (vanilla state materials)."""
    nm = "DC_Srv_Timer_indicator_states"
    if want(nm):
        n = len(TIMER_STATES)
        s = Shot(nm, res=(2600, 1100), floor=(-0.62 * n, 1, -1, 1.5))
        for i, (st, key, note) in enumerate(TIMER_STATES):
            srv(s, built, "DC_Srv_Timer", x=-0.62 * i, states={functional.TIMER_IND: key})
        cx = -0.62 * (n - 1) / 2
        s.camera((cx, 6.6, 0.75), (cx, 0, 0.17), 36)
        for i, (st, key, note) in enumerate(TIMER_STATES):
            s.caption(f"{st}\n{note}", (-0.62 * i, 0.4, 0.40), 0.03)
        s.caption("TIMER: TimerBlockIndicator states (COUNT lamp, power ring, sled lamps, rear PSU lamps = "
                  "mesh part 'EmissiveOff')", (cx, 0.4, 0.58), 0.04)
        s.render()
        # close-up pairs of the blinking COUNT lamp
        nm2 = "DC_Srv_Timer_indicator_states_closeup"
        if want(nm2):
            # 2 rows of 4 (stacked like a rack face) so each COUNT lamp reads large
            s = Shot(nm2, res=(2400, 1300), floor=(-2.2, 1, -1, 1.5))
            for i, (st, key, note) in enumerate(TIMER_STATES):
                r, c = divmod(i, 4)
                srv(s, built, "DC_Srv_Timer", x=-0.56 * c, z=0.36 * (1 - r), states={functional.TIMER_IND: key})
            s.camera((-0.84, 2.9, 0.42), (-0.84, 0, 0.30), 40)
            for i, (st, key, note) in enumerate(TIMER_STATES):
                r, c = divmod(i, 4)
                s.caption(f"{st} {note}", (-0.56 * c, 0.42, 0.36 * (1 - r) + 0.275), 0.018)
            s.render()
    nm = "DC_Srv_EventCtl_indicator_states"
    if want(nm):
        n = len(EVC_STATES)
        s = Shot(nm, res=(2400, 1000), floor=(-0.62 * n, 1, -1, 1.5))
        for i, (st, t, f) in enumerate(EVC_STATES):
            srv(s, built, "DC_Srv_EventCtl", x=-0.62 * i,
                states={functional.EVC_TRUE: t, functional.EVC_FALSE: f})
        cx = -0.62 * (n - 1) / 2
        s.camera((cx, 4.6, 0.6), (cx, 0, 0.17), 36)
        for i, (st, t, f) in enumerate(EVC_STATES):
            s.caption(f"{st}\nT row: {t}  F row: {f}", (-0.62 * i, 0.4, 0.40), 0.032)
        s.caption("EVENT CONTROLLER: EventControllerIndicator states (row T = 'Emissive01', row F = 'Emissive02')",
                  (cx, 0.4, 0.58), 0.04)
        s.render()


def status_sample(built):
    nm = "DC_Srv_Status_lcd_sample_text"
    if want(nm):
        s = Shot(nm, res=(1800, 1000), floor=(-1.5, 1.5, -1.5, 1.5))
        srv(s, built, "DC_Srv_Status")
        s.camera((0.05, 0.95, 0.20), (0.04, 0.37, H / 2), 45)
        s.render()


def lineup(built):
    nm = "servers_lineup_7"
    if not want(nm):
        return
    order = FUNC + DECO
    s = Shot(nm, res=(3000, 1000), floor=(-4.6, 0.6, -1, 1.5))
    for i, n in enumerate(order):
        srv(s, built, n, x=-0.68 * i)
    cx = -0.68 * (len(order) - 1) / 2
    s.camera((cx, 5.6, 0.85), (cx, 0, 0.2), 35)
    for i, n in enumerate(order):
        s.caption(LABEL[n], (-0.68 * i, 0.45, 0.42), 0.028)
    s.render()


FULL_MIX = ("DC_Srv_Storage", "DC_Srv_Compute", "DC_Srv_Timer", "DC_Srv_EventCtl", "DC_Srv_Status", "DC_Srv_Blank",
            "DC_Srv_Switch", None)
FULL_MIX_B = ("DC_Srv_Storage", "DC_Srv_Storage", "DC_Srv_EventCtl", "DC_Srv_Compute", "DC_Srv_Timer",
              "DC_Srv_Switch", "DC_Srv_Status", "DC_Srv_Blank")
HALF_MIX = ("DC_Srv_Switch", "DC_Srv_Timer", "DC_Srv_Status", None)


def in_rack(built):
    shots = {
        "rack42_mixed_front": ((0.0, 4.4, 1.3), (0, 0, 1.25), 40),
        "rack42_mixed_3q": ((-1.75, 2.9, 2.05), (0, 0, 1.2), 35),
        # first person: eye 1.70 m, 2.0 m in front of the rack's front
        "rack42_mixed_first_person": ((0.35, 0.625 + 2.0, 1.70), (0.0, 0.0, 1.15), 24),
    }
    for nm, (loc, tgt, lens) in shots.items():
        if not want(nm):
            continue
        s = Shot(nm, floor=(-2.5, 2.5, -2.5, 4.0))
        rack(s, built, FULL, FULL_MIX)
        s.camera(loc, tgt, lens)
        s.render()
    nm = "racks_row_black_mixed"
    if want(nm):
        s = Shot(nm, res=(2200, 1250), floor=(-3, 2, -2, 4))
        rack(s, built, FULL, FULL_MIX, x=0.0, paint="black")
        rack(s, built, FULL, FULL_MIX_B, x=-1.0, paint="black")
        rack(s, built, HALF, HALF_MIX, x=-2.0, paint="black")
        s.inst(human(), T(0.9, 1.6, 0) @ Rz(200))
        s.camera((1.4, 4.2, 1.9), (-1.0, 0, 1.15), 32)
        s.render()
    nm = "racks_row_black_mixed_first_person"
    if want(nm):
        s = Shot(nm, res=(2000, 1250), floor=(-3, 2, -2, 4))
        rack(s, built, FULL, FULL_MIX, x=0.0, paint="black")
        rack(s, built, FULL, FULL_MIX_B, x=-1.0, paint="black")
        rack(s, built, HALF, HALF_MIX, x=-2.0, paint="black")
        s.camera((0.6, 0.625 + 1.6, 1.70), (-0.6, 0.0, 1.1), 22)
        s.render()


def paints(built):
    nm = "functional_paints_black_keen_blue"
    if not want(nm):
        return
    s = Shot(nm, res=(2200, 1250), floor=(-2.2, 1.2, -1.2, 2.5))
    s.camera((-0.62, 3.2, 1.0), (-0.62, 0, 0.38), 35)
    for r, p in enumerate(("black", "keen", "blue")):
        for i, n in enumerate(FUNC):
            srv(s, built, n, x=-0.62 * i, z=0.25 * (2 - r), paint=p)
        s.caption(("BLACK", "KEEN GREY", "BLUE")[r], (0.55, 0.3, 0.25 * (2 - r) + 0.12), 0.05)
    s.render()


def _vanilla_stated(rel, states, paint="keen"):
    """Import a vanilla FBX READ ONLY (tools/vanilla-ref) with the same stand-ins and indicator state materials as
    ours (its slots carry the same names: EmissiveOff, Emissive01/02, Terminal, LCDScreen_Off)."""
    from mathutils import Vector
    cname = "pv6_v_" + os.path.basename(rel) + "_" + "_".join(f"{k}{v}" for k, v in sorted(states.items()))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(PV.VREF, rel))
    new = [o for o in bpy.data.objects if o not in before]
    c = bpy.data.collections.new(cname)
    bpy.context.scene.collection.children.link(c)
    for o in new:
        for uc in list(o.users_collection):
            uc.objects.unlink(o)
        c.objects.link(o)
        if o.type == "MESH":
            _assign(o, states, paint, lcd=False)
    PV._exclude(c)
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(b) for o in new if o.type == "MESH" for b in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return c, lo, hi


def vanilla_compare(built):
    nm = "functional_vanilla_comparison"
    if not want(nm):
        return
    s = Shot(nm, res=(2600, 1200), floor=(-5.0, 1.0, -1.5, 1.5))
    pairs = (("DC_Srv_Timer", "Timer/50/Models/NonFractured/Timer50.fbx", "vanilla Timer50 (Idle)",
              {functional.TIMER_IND: "act"}),
             ("DC_Srv_EventCtl", "EventController/100/Models/NonFractured/EventController100.fbx",
              "vanilla EventController (True)", {functional.EVC_TRUE: "act", functional.EVC_FALSE: "off"}),
             ("DC_Srv_Status", "LCDPanels/LCD/50/Models/NonFractured/LCD50.fbx", "vanilla LCDFlat50", {}))
    x = 0.0
    caps = []
    for name, rel, lbl, st in pairs:
        srv(s, built, name, x=x, states=st)
        caps.append((f"OURS: {SHORT[name]}", (x, 0.3, 0.45)))
        x -= 0.75
        c, lo, hi = _vanilla_stated(rel, st)
        w = hi.x - lo.x
        ctr = (lo + hi) / 2
        s.inst(c, T(x - w / 2 + 0.25, 0, 0) @ T(-ctr.x, -ctr.y, -lo.z))
        caps.append((lbl, (x - w / 2 + 0.25, 0.3, hi.z - lo.z + 0.15)))
        x -= w + 0.55
    cx = (0.3 + x + 0.55) / 2          # from our timer (x = 0, image left) to the last vanilla block
    s.camera((cx, 5.4, 1.2), (cx, 0, 0.25), 30)
    for txt, at in caps:
        s.caption(txt, at, 0.04)
    s.render()


def render_all(built):
    PV.OUT = OUT
    PM.get("Caption")
    for n in FUNC:
        if n in built:
            per_server(built, n)
    if all(n in built for n in FUNC):
        states(built)
        status_sample(built)
        paints(built)
        vanilla_compare(built)
    if all(n in built for n in FUNC + DECO):
        lineup(built)
    if all(n in built for n in FUNC + DECO + (FULL, HALF)):
        in_rack(built)
