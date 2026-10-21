"""KVM previews: the KVM console (pop-out drawer + fold-up screen) and the programmable shell
(Source/Model/preview/kvm/).

Same rig and stand-ins as the other server sets (dc/preview.py, dc/preview_mats.py, dc/preview_indicator_servers.py,
dc/preview_ups.py). The KVM's subparts
are the built subpart models placed exactly as the game will place them: the drawer at the "KvmDrawer" dummy
(subparts.HINGE) moved by TRAVEL * f along +Y (TranslationAnimation, block space), the screen at the drawer's
"KvmScreen" dummy (its local origin) rotated FOLD_DEG * f about +X (RotationAnimation, local). f is the shared
animation fraction (both animations take POP_TIME), so f = 0.25 / 0.5 / 0.75 are the real mid-motion frames of the
simultaneous slide-and-fold. Vanilla ControlPanel25 is imported READ ONLY from tools/vanilla-ref.

    DC_PREVIEW=kvm blender -b --python Source/Model/build_dc.py -- DC_Rack42_Open DC_Rack24_Open DC_Srv_Blank \
        DC_Srv_Compute DC_Srv_Storage DC_Srv_Switch DC_Srv_Timer DC_Srv_EventCtl DC_Srv_Status DC_Srv_UPS \
        DC_Srv_KVM DC_Srv_Programmable
(DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution).
"""
import json
import math
import os

import bpy
from mathutils import Matrix

from . import config
from . import preview as PV
from . import preview_mats as PM
from . import preview_indicator_servers as P6
from . import preview_ups as P7
from . import subparts as S
from .preview import Rz, Shot, T, human, want

OUT = os.path.join(config.PREVIEW_DIR, "kvm")
KVM, PROG = "DC_Srv_KVM", "DC_Srv_Programmable"
H = 0.25
FULL, HALF = "DC_Rack42_Open", "DC_Rack24_Open"
FRAMES = (0.0, 0.25, 0.5, 0.75, 1.0)


def Rx(deg):
    return Matrix.Rotation(math.radians(deg), 4, "X")


def _sub(built, sub, lod=0, paint="keen"):
    """A painted collection of one subpart LOD (screen art via the Terminal stand-in)."""
    objs = built[KVM]["subparts"][sub][lod][1]
    return P6.stated(objs, f"{KVM}_{sub}", lod, paint, {}, key=(KVM, sub, lod, paint))


def kvm_part_matrices(m, slide, fold):
    """(drawer, screen) world matrices of a KVM placed with matrix m at the normalised pose (slide, fold): the drawer
    at the "KvmDrawer" dummy moved slide * TRAVEL along +Y, the screen on it turned fold * FOLD_DEG about +X."""
    md = m @ T(S.HINGE[0], S.HINGE[1] + S.TRAVEL * slide, S.HINGE[2])
    return md, md @ Rx(S.FOLD_DEG * fold)


def kvm(s, built, x=0.0, y=0.0, z=0.0, paint="keen", f=1.0, lod=0, sub_lod=None, rot=0, slide=None, fold=None):
    """The KVM standing with its bottom at z, its drawer / screen at animation fraction f (the data-only motion: both
    together), or at the scripted normalised pose (slide, fold) when both are given (the scripted motion). Returns the base
    matrix; with a pose, also the drawer and screen instance objects (for animating them)."""
    m = T(x, y, z + H / 2) @ Rz(rot)
    s.inst(P6.stated(built, KVM, lod, paint, {}), m)
    parts = None
    if lod < len(built[KVM]["lods"]) - 1:
        md, ms = kvm_part_matrices(m, *((slide, fold) if slide is not None and fold is not None else (f, f)))
        dl = sub_lod if sub_lod is not None else 0
        sl = min(dl, len(built[KVM]["subparts"][S.SCREEN]) - 1)
        parts = (s.inst(_sub(built, S.DRAWER, min(dl, len(built[KVM]["subparts"][S.DRAWER]) - 1), paint), md),
                 s.inst(_sub(built, S.SCREEN, sl, paint), ms))
    return (m, parts) if slide is not None and fold is not None else m


def prog(s, built, x=0.0, y=0.0, z=0.0, paint="keen", lod=0, rot=0):
    m = T(x, y, z + H / 2) @ Rz(rot)
    s.inst(P6.stated(built, PROG, lod, paint, {}), m)
    return m


def srv(s, built, name, x=0.0, y=0.0, z=0.0, paint="keen", f=1.0):
    if name == "KVM":
        kvm(s, built, x, y, z, paint, f)
    elif name == "PROG":
        prog(s, built, x, y, z, paint)
    elif name == "UPS":
        P7.ups(s, built, x, y, z, paint)
    elif name:
        P6.srv(s, built, name, x, y, z, paint)


def rack(s, built, name, mix, x=0.0, y=0.0, paint="keen", f=1.0):
    Hr = 0.25 * (10 if name == FULL else 5)
    s.inst(PV.painted(built, name, 0, paint), T(x, y, Hr / 2))
    for k, n in enumerate(mix, 1):
        srv(s, built, n, x, y, 0.25 * k, paint, f)


def _rep(name):
    with open(config.REPORT_PATH) as fh:
        return json.load(fh)["blocks"].get(name, {})


# ---------------------------------------------------------------------------------------------------- KVM
KVM_VIEWS = {   # camera, target, lens
    "front": ((0.0, 2.6, 0.30), (0, 0.45, 0.10), 45),
    "3q": ((-1.25, 2.1, 0.95), (0, 0.40, 0.08), 42),
    "side": ((2.3, 0.45, 0.20), (0, 0.45, 0.08), 42),
    "first_person": ((0.25, 1.55, 0.58), (0.0, 0.45, 0.06), 30),   # standing at the drawer, eyes ~0.45 m above it
}


def kvm_frames(built):
    for f in FRAMES:
        for v, (loc, tgt, lens) in KVM_VIEWS.items():
            nm = f"{KVM}_f{int(f * 100):03d}_{v}"
            if not want(nm):
                continue
            s = Shot(nm, res=(1600, 1200), floor=(-1.5, 1.5, -1.5, 2.0))
            kvm(s, built, f=f)
            s.camera(loc, tgt, lens)
            dy, ang = S.pose(f)
            s.caption(f"f = {f:.2f}:  drawer +{dy:.3f} m,  screen {ang:.0f} deg", (0.0, 0.45, 0.60), 0.035)
            s.render()


def kvm_closeups(built):
    shots = {
        f"{KVM}_closeup_screen_keyboard": (1.0, (0.12, 1.25, 0.42), (0.0, 0.78, 0.10), 38),
        f"{KVM}_closeup_keyboard_top": (1.0, (0.0, 0.93, 0.75), (0.0, 0.72, 0.03), 40),
        f"{KVM}_closeup_closed_face": (0.0, (-0.25, 0.95, 0.25), (0.0, 0.38, 0.11), 40),
        f"{KVM}_closeup_hinge": (1.0, (0.55, 0.80, 0.30), (0.19, 0.52, 0.10), 40),
        f"{KVM}_closeup_bay_open": (1.0, (-0.30, 0.95, 0.10), (0.0, 0.36, 0.08), 38),
    }
    for nm, (f, loc, tgt, lens) in shots.items():
        if not want(nm):
            continue
        s = Shot(nm, res=(1600, 1200), floor=(-1.5, 1.5, -1.5, 2.0))
        kvm(s, built, f=f)
        s.camera(loc, tgt, lens)
        s.render()


def kvm_misc(built):
    nm = f"{KVM}_back"
    if want(nm):
        s = Shot(nm, floor=(-1.5, 1.5, -1.5, 2.0))
        kvm(s, built, f=1.0)
        s.camera((0.9, -1.6, 0.6), (0, 0.1, 0.1), 40)
        s.render()


def lods(built):
    for name, place in ((KVM, kvm), (PROG, prog)):
        nm = f"{name}_lods"
        if not want(nm):
            continue
        rep = _rep(name).get("lods", [])
        n = len(built[name]["lods"])
        s = Shot(nm, res=(2400, 1000), floor=(-0.8 * n, 1, -1.2, 1.6))
        for i in range(n):
            if name == KVM:
                kvm(s, built, x=-0.75 * i, lod=i, sub_lod=i, f=1.0)
            else:
                prog(s, built, x=-0.75 * i, lod=i)
        cx = -0.75 * (n - 1) / 2
        s.camera((cx - 0.3, 4.0, 1.0), (cx, 0.2, 0.15), 35)
        for i in range(n):
            r = rep[i] if i < len(rep) else {}
            s.caption(f"base LOD{i}\n{r.get('tris', '?')}/{r.get('max_tris', '?')} tris, "
                      f"{r.get('materials', '?')}/{r.get('max_materials', '?')} mats", (-0.75 * i, 0.4, 0.50), 0.04)
        s.render()
    nm = f"{KVM}_subpart_lods"
    if want(nm):
        rep = _rep(KVM).get("subparts", {}).get("models", {})
        s = Shot(nm, res=(2400, 1100), floor=(-2.5, 1.0, -1.0, 1.5))
        nsub = sum(len(built[KVM]["subparts"][k]) for k in (S.DRAWER, S.SCREEN))
        xe = -0.55 * nsub
        s.camera((xe / 2 + 0.1, 3.2, 1.2), (xe / 2 + 0.25, 0.1, 0.12), 35)
        x = 0.0
        for sub in (S.DRAWER, S.SCREEN):
            for i, _ in enumerate(built[KVM]["subparts"][sub]):
                m = T(x, 0, 0.12) @ (Rx(80) if sub == S.SCREEN else Matrix.Identity(4))
                s.inst(_sub(built, sub, i), m)
                r = rep.get(sub, {}).get("lods", [{}] * 9)[i]
                s.caption(f"{sub} LOD{i}\n{r.get('tris', '?')}/{r.get('max_tris', '?')} tris, "
                          f"{r.get('materials', '?')}/{r.get('max_materials', '?')} mats", (x, 0.3, 0.52), 0.035)
                x -= 0.55
        s.render()


RACK_MIX = ("DC_Srv_Storage", "UPS", None, "DC_Srv_Timer", "KVM", "DC_Srv_Compute", "DC_Srv_Status", "PROG")


def in_rack(built):
    """The KVM in slot 5 of the full rack with the compute server in slot 6 above it: popped (the screen covers the
    lower half of slot 6) and closed."""
    shots = {
        "rack42_kvm_popped_front": (1.0, (0.0, 4.2, 1.45), (0, 0.2, 1.3), 40),
        "rack42_kvm_popped_3q": (1.0, (-1.8, 2.9, 1.95), (0, 0.25, 1.35), 35),
        "rack42_kvm_popped_side": (1.0, (1.15, 2.1, 1.45), (0, 0.55, 1.40), 30),   # from the front-right (the rack side panel hides a pure side view)
        "rack42_kvm_popped_cover_closeup": (1.0, (-0.55, 1.65, 1.62), (0.0, 0.45, 1.43), 38),
        "rack42_kvm_closed_3q": (0.0, (-1.8, 2.9, 1.95), (0, 0.25, 1.35), 35),
        "rack42_kvm_closed_front": (0.0, (0.0, 4.2, 1.45), (0, 0.2, 1.3), 40),
        "rack42_kvm_first_person": (1.0, (0.30, 1.75, 1.70), (0.0, 0.45, 1.30), 26),
        "rack42_kvm_mid_f050_3q": (0.5, (-1.0, 1.9, 1.75), (0, 0.4, 1.38), 35),
    }
    for nm, (f, loc, tgt, lens) in shots.items():
        if not want(nm):
            continue
        s = Shot(nm, floor=(-2.5, 2.5, -2.5, 4.0))
        rack(s, built, FULL, RACK_MIX, f=f)
        s.camera(loc, tgt, lens)
        s.render()


# ---------------------------------------------------------------------------------------------------- programmable
def prog_views(built):
    views = {
        "front": ((0.0, 1.9, 0.18), (0, 0, 0.125), 50),
        "3q": ((-1.0, 1.4, 0.75), (0, 0.05, 0.11), 45),
        "back": ((0.6, -1.7, 0.45), (0, 0, 0.12), 45),
        "side": ((1.8, 0.2, 0.25), (0, 0.1, 0.12), 45),
        "closeup_led": ((0.30, 0.78, 0.24), (-0.17, 0.38, 0.11), 42),
        "closeup_sleds": ((0.25, 0.80, 0.30), (0.06, 0.38, 0.13), 40),
    }
    for v, (loc, tgt, lens) in views.items():
        nm = f"{PROG}_{v}"
        if not want(nm):
            continue
        s = Shot(nm, res=(1600, 1200), floor=(-1.5, 1.5, -1.5, 1.5))
        prog(s, built)
        s.camera(loc, tgt, lens)
        s.render()


# ---------------------------------------------------------------------------------------------------- set pieces
LINE = (("DC_Srv_Timer", "TIMER"), ("DC_Srv_EventCtl", "EVENT CTL"), ("DC_Srv_Status", "STATUS"),
        ("DC_Srv_Compute", "COMPUTE"), ("DC_Srv_Storage", "STORAGE"), ("DC_Srv_Switch", "SWITCH"),
        ("DC_Srv_Blank", "BLANK"), ("UPS", "UPS 12U"), ("KVM0", "KVM\nclosed"), ("KVM", "KVM\npopped out"),
        ("PROG", "PROGRAMMABLE\n(script host)"))


def lineup(built):
    nm = "servers_lineup_11"
    if not want(nm):
        return
    xs, x = [], 0.0
    for n, _ in LINE:
        xs.append(x)
        x -= 0.85 if n in ("UPS", "KVM") else 0.68
    s = Shot(nm, res=(3800, 1100), floor=(xs[-1] - 0.8, 0.8, -1, 1.8))
    cx = (xs[0] + xs[-1]) / 2
    s.camera((cx, 8.4, 1.3), (cx, 0.1, 0.28), 33)
    for (n, lbl), x in zip(LINE, xs):
        if n == "KVM0":
            kvm(s, built, x=x, f=0.0)
        else:
            srv(s, built, n, x=x)
        s.caption(lbl, (x, 0.45, 0.72 if n in ("UPS", "KVM") else 0.46), 0.055)
    s.render()


def paints(built):
    nm = "kvm_paints_black_keen_blue"
    if not want(nm):
        return
    s = Shot(nm, res=(2400, 1250), floor=(-2.4, 1.0, -1.2, 2.2))
    s.camera((-0.75, 3.4, 1.25), (-0.75, 0.25, 0.22), 35)
    for i, p in enumerate(("black", "keen", "blue")):
        kvm(s, built, x=-0.75 * i, z=0.30, paint=p, f=1.0)
        prog(s, built, x=-0.75 * i, z=0.0, paint=p)
        s.caption(("BLACK", "KEEN GREY", "BLUE")[i], (-0.75 * i, 0.3, 0.92), 0.04)
    s.render()


def vanilla_compare(built):
    nm = f"{KVM}_vanilla_comparison"
    if want(nm):
        c, lo, hi = PV.vanilla("ControlPanel/25/Models/NonFractured/ControlPanel25.fbx")
        ctr = (lo + hi) / 2
        s = Shot(nm, res=(2400, 1100), floor=(-2.4, 1.0, -1.2, 1.8))
        kvm(s, built, x=0.0, f=0.0)
        kvm(s, built, x=-0.75, f=1.0)
        s.inst(c, T(-1.55, 0, 0) @ T(-ctr.x, -ctr.y, -lo.z))
        s.camera((-0.8, 3.2, 1.0), (-0.8, 0.2, 0.18), 35)
        for txt, x in (("OURS: KVM 6U\nclosed", 0.0), ("OURS: KVM 6U\npopped out", -0.75),
                       ("vanilla ControlPanel25\n(same terminal)", -1.55)):
            s.caption(txt, (x, 0.3, 0.72), 0.035)
        s.render()
    nm = f"{PROG}_next_to_lineup"
    if want(nm):
        s = Shot(nm, res=(2600, 1000), floor=(-3.0, 0.8, -1, 1.5))
        names = ("PROG", "DC_Srv_Compute", "DC_Srv_Storage", "DC_Srv_Switch", "DC_Srv_Blank")
        s.camera((-1.24, 3.9, 0.9), (-1.24, 0, 0.13), 33)
        for i, n in enumerate(names):
            srv(s, built, n, x=-0.62 * i)
            s.caption(("PROGRAMMABLE", "COMPUTE", "STORAGE", "SWITCH", "BLANK")[i], (-0.62 * i, 0.4, 0.44), 0.045)
        s.render()


ROW = (("DC_Rack42_Open", ("UPS", None, "DC_Srv_Storage", "KVM", "DC_Srv_Compute", "DC_Srv_Status", "PROG",
                           "DC_Srv_Blank")),
       ("DC_Rack42_Open", ("DC_Srv_Storage", "DC_Srv_Storage", "DC_Srv_Switch", "DC_Srv_Timer", "DC_Srv_EventCtl",
                           "PROG", "PROG", "DC_Srv_Blank")),
       ("DC_Rack24_Open", ("UPS", None, "DC_Srv_Switch", "KVM")))


def row(built):
    for nm, paint, cam in (("racks_row_all_types", "keen", ((1.6, 4.4, 2.0), (-1.0, 0, 1.15), 32)),
                           ("racks_row_all_types_black", "black", ((1.6, 4.4, 2.0), (-1.0, 0, 1.15), 32)),
                           ("racks_row_first_person", "keen", ((0.55, 1.95, 1.70), (-0.6, 0.3, 1.05), 24))):
        if not want(nm):
            continue
        s = Shot(nm, res=(2200, 1250), floor=(-3, 2, -2, 4))
        for i, (rk, mix) in enumerate(ROW):
            rack(s, built, rk, mix, x=-1.0 * i, paint=paint, f=1.0 if i != 1 else 0.0)
        if nm != "racks_row_first_person":
            s.inst(human(), T(0.9, 1.6, 0) @ Rz(200))
        s.camera(*cam)
        s.render()


def render_all(built):
    PV.OUT = OUT
    PM.get("Caption")
    if KVM in built:
        kvm_frames(built)
        kvm_closeups(built)
        kvm_misc(built)
    if PROG in built:
        prog_views(built)
    if KVM in built and PROG in built:
        lods(built)
        paints(built)
        vanilla_compare(built)
        if all(n in built for n in P6.FUNC + P6.DECO + ("DC_Srv_UPS",)):
            lineup(built)
            if all(n in built for n in (FULL, HALF)):
                in_rack(built)
                row(built)
