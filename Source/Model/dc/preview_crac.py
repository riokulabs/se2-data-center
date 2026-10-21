"""CRAC previews: the in-row cooler DC_CRAC.

    DC_PREVIEW=crac blender -b --python Source/Model/build_dc.py -- DC_CRAC "DC_Rack42_*" "DC_Srv_*" \
        "DC_Floor_*" "DC_Contain_Roof_*" "DC_Contain_Door_*" "DC_Tray_Drop_Full" "DC_Tray_StraightS_Full" \
        "DC_TrayRods_100"

Writes Source/Model/preview/crac/ (DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution):
  crac_<view>                 the turntable (front, back, both sides, 3/4 front and back, top), running
  crac_lods                   LOD0..n side by side
  crac_fans_off / _on         the fan door switched off (lamp dark, rotors still) and running (RUN lit, rotors
                              motion-blurred at 600 deg/s, the shutter of a 25 fps camera)
  crac_fan_rotor              the CracFan rotor model alone, front and back
  anim/fan_NNN.png            the spin-up / coast-down sequence (25 fps: off, switched on at 0.4 s, the linear
                              InfiniteRotation ramp to 600 deg/s in 2 s, running, switched off at 3.4 s, a 4 s coast);
                              crac_sheet.py turns it into crac_fans.gif, a frame strip and the speed graph
  closeup_*                   the controller, a fan module, hinge and latch, the CHW well, the brush plates, the rear
                              filter grille, the condensate pan, the nameplate and the rating plate
  paints_*                    keen, black, and the cold / hot pair (blue, orange)
  vanilla_compare             beside a 42U rack, vanilla Gyroscope250_Base (the clone source) and WallInsertVent
  room_*                      the reference room (dc/preview_room.py): cold and hot aisles, every camera at 1.5 m,
                              the main three at 1.0 / 2.0 m, photo 1 with black racks
The fracture shots (exploded / broken / damaged, from the EXPORTED files) are Source/Model/crac_fracture_preview.py.
"""
import math
import os

import bpy
from mathutils import Matrix, Vector

from . import catalog, crac
from . import preview as PV
from . import preview_room as PR
from . import preview_rack_doors as P9
from .preview import Rz, T, want

NAME = "DC_CRAC"
H = crac.H
ZC = H / 2          # the block centre over the ground in the studio shots
FPS = 25
ANIM = (0.4, 3.4, 7.8)   # switched on, switched off, end (s)


def _ry(deg):
    return Matrix.Rotation(math.radians(deg), 4, Vector((0, -1, 0)))   # the fans' turn (InfiniteRotation, game +Z)


def unit(s, built, M, angle=0.0, working=True, paint="keen", lod=0):
    """The cabinet and its three rotors (dc/preview_room.crac_unit) into a Shot."""
    PR.crac_unit(s, built, NAME, M, angle, working, paint, lod)


def _studio(nm, light=1.0, res=(1800, 1150), floor=(-2.0, 2.0, -2.0, 2.0)):
    return PV.Shot(nm, res=res, floor=floor, light=light)


# ---------------------------------------------------------------------------------------------------- hero
VIEWS = {"front": ((0, 6.6, ZC), (0, 0, ZC * 0.95), 50), "back": ((0, -6.6, ZC), (0, 0, ZC * 0.95), 50),
         "left": ((-6.6, 0, ZC), (0, 0, ZC * 0.95), 50), "right": ((6.6, 0, ZC), (0, 0, ZC * 0.95), 50),
         "3q_front_left": ((-3.4, 5.0, 3.6), (0, 0, ZC * 0.95), 50),
         "3q_front_right": ((3.6, 4.9, 2.2), (0, 0, ZC * 0.95), 50),
         "3q_back_right": ((3.4, -5.0, 3.6), (0, 0, ZC * 0.95), 50),
         "3q_back_left": ((-3.6, -4.9, 2.2), (0, 0, ZC * 0.95), 50),
         "top": ((0.0, 0.35, H + 5.6), (0, 0, ZC), 50)}


def hero(built):
    for v, (loc, tgt, lens) in VIEWS.items():
        nm = f"crac_{v}"
        if not want(nm):
            continue
        s = _studio(nm)
        unit(s, built, T(0, 0, ZC), 17.0)
        s.camera(loc, tgt, lens)
        s.render()
    nm = "crac_human_scale"
    if want(nm):
        s = _studio(nm, floor=(-2.5, 2.5, -2.0, 2.0))
        unit(s, built, T(0, 0, ZC), 17.0)
        if "DC_Rack42_SplitFront" in built:
            P9.rack(s, built, "DC_Rack42_SplitFront", x=-1.0, y=0.0, mix=P9.MIX42)
        s.inst(PV.human(), T(1.15, 0.9, 0))
        s.camera((1.8, 5.6, 1.9), (0.1, 0, 1.2), 40)
        s.render()


def lods(built):
    PV.lods(built, NAME)


# ---------------------------------------------------------------------------------------------------- fans
def _blur(s, empties, omega):
    """EEVEE motion blur over a 25 fps frame (shutter 0.5): each rotor empty keyframed one frame either side, turned
    by omega deg/s about the fans' axis."""
    sc = s.sc
    for k, v in (("use_motion_blur", True), ("motion_blur_shutter", 0.5)):
        for tgt in (sc.render, sc.eevee):
            try:
                setattr(tgt, k, v)
            except (AttributeError, TypeError):
                pass
    sc.render.fps = FPS
    sc.frame_set(1)
    step = omega / FPS
    for e, base in empties:
        for f, a in ((0, -step), (1, 0.0), (2, step)):
            e.matrix_world = base @ _ry(a)
            e.keyframe_insert("rotation_euler", frame=f)
            e.keyframe_insert("location", frame=f)
        if e.animation_data and e.animation_data.action:
            for fc in getattr(e.animation_data.action, "fcurves", []):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
    sc.frame_set(1)


def _rotors(s, built, M, angle, paint="keen"):
    rot = P9.sub(built, NAME, crac.FAN, paint)
    out = []
    for i, p in enumerate(crac.fan_points(catalog.BY_NAME[NAME])):
        base = M @ T(*p) @ _ry(angle + 23.0 * i)
        out.append((s.inst(rot, base), base))
    return out


def fans(built):
    cam = ((1.05, 2.75, 1.95), (0.0, 0.45, 1.42), 32)
    for tag, working, omega in (("off", False, 0.0), ("on", True, crac.FAN_DEG_S)):
        nm = f"crac_fans_{tag}"
        if not want(nm):
            continue
        s = _studio(nm, res=(1500, 1300))
        M = T(0, 0, ZC)
        s.inst(P9.body(built, NAME, "keen", working), M)
        emp = _rotors(s, built, M, 17.0)
        s.camera(*cam)
        if omega:
            _blur(s, emp, omega)
        s.render()
    nm = "crac_fan_rotor"
    if want(nm):
        s = _studio(nm, res=(1500, 800), floor=(-1, 1, -1, 1))
        rot = P9.sub(built, NAME, crac.FAN, "keen")
        s.inst(rot, T(-0.28, 0, 0.35) @ Rz(0))
        s.inst(rot, T(0.28, 0, 0.35) @ Rz(180))
        s.camera((0.0, 1.55, 0.62), (0.0, 0.0, 0.33), 45)
        s.caption("front (+y: the cold aisle)", (-0.28, 0.0, 0.62), 0.035)
        s.caption("back (air in)", (0.28, 0.0, 0.62), 0.035)
        s.render()


def anim_profile(t):
    """(angle deg, omega deg/s, working) at time t of the preview sequence: InfiniteRotationAnimationComponent's
    linear ramp toward AngularSpeed (AngularSpeedup while rising, AngularSlowdown while falling)."""
    on, off, _ = ANIM
    w, up, down = crac.FAN_DEG_S, crac.FAN_SPEEDUP, crac.FAN_SLOWDOWN
    t_full = on + w / up
    t_stop = off + w / down

    def omega(x):
        if x < on:
            return 0.0
        if x < off:
            return min(w, up * (x - on))
        w0 = min(w, up * (off - on))
        return max(0.0, w0 - down * (x - off))

    # angle: integrate omega (piecewise linear: exact with the trapezoid on a fine step)
    n = max(1, int(t * 200))
    dt = t / n if n else 0.0
    a = sum((omega(i * dt) + omega((i + 1) * dt)) / 2 * dt for i in range(n))
    return a, omega(t), on <= t < off, (t_full, t_stop)


def anim(built):
    """The spin-up / coast-down frames (anim/fan_NNN.png) of the fan door's middle and top modules, with the RUN lamp:
    rendered as one animation (the rotors keyframed every frame with the ramp's angle, linear, so EEVEE's motion blur
    smears each frame by its own speed; the lamp swaps with Working)."""
    nm = "anim"
    if not want(nm):
        return
    out = os.path.join(PV.OUT, "anim")
    os.makedirs(out, exist_ok=True)
    s = _studio("crac_fan_anim", res=(720, 720))
    M = T(0, 0, ZC)
    lit, dark = (s.inst(P9.body(built, NAME, "keen", w), M) for w in (True, False))
    emp = _rotors(s, built, M, 0.0)
    s.camera((0.62, 1.55, 1.95), (0.0, 0.45, 1.66), 40)
    sc = s.sc
    for k, v in (("use_motion_blur", True), ("motion_blur_shutter", 0.5)):
        for tgt in (sc.render, sc.eevee):
            try:
                setattr(tgt, k, v)
            except (AttributeError, TypeError):
                pass
    sc.render.fps = FPS
    nf = int(round(ANIM[2] * FPS))
    sc.frame_start, sc.frame_end = 1, nf
    for f in range(0, nf + 2):
        t = (f - 1) / FPS
        a, _, working, _ = anim_profile(max(0.0, t))
        for i, (e, base) in enumerate(emp):
            e.matrix_world = base @ _ry(a)
            e.keyframe_insert("rotation_euler", frame=f)
            e.keyframe_insert("location", frame=f)
        lit.hide_render, dark.hide_render = not working, working
        lit.keyframe_insert("hide_render", frame=f)
        dark.keyframe_insert("hide_render", frame=f)
    for e, _ in emp:
        for fc in getattr(e.animation_data.action, "fcurves", []):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    sc.render.filepath = os.path.join(out, "fan_")
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(animation=True, scene=sc.name)
    with open(os.path.join(out, "profile.csv"), "w") as fh:
        fh.write("frame,t,angle_deg,omega_deg_s,working\n")
        for f in range(1, nf + 1):
            t = (f - 1) / FPS
            a, w, working, _ = anim_profile(t)
            fh.write(f"{f},{t:.3f},{a:.2f},{w:.2f},{int(working)}\n")
    print("WROTE", out)


# ---------------------------------------------------------------------------------------------------- close-ups
CLOSE = {   # name: (camera, target, lens, working)
    "closeup_controller": ((0.55, 1.45, 2.25), (0.02, 0.56, 2.05), 42, True),
    "closeup_fan_module": ((0.45, 1.25, 1.18), (0.0, 0.55, 1.05), 40, True),
    "closeup_guard_oblique": ((-0.65, 0.95, 1.75), (0.0, 0.55, 1.55), 45, False),
    "closeup_hinges_latch": ((0.0, 1.45, 1.20), (0.0, 0.55, 1.05), 30, False),
    "closeup_chw_well": ((0.55, -1.15, 3.25), (0.0, -0.25, 2.40), 36, True),
    "closeup_brush_plates": ((0.75, 1.25, 3.05), (0.0, 0.42, 2.45), 38, True),
    "closeup_rear_filters": ((0.85, -1.35, 1.35), (0.0, -0.57, 1.15), 34, True),
    "closeup_condensate_pan": ((0.45, -1.15, 0.45), (0.15, -0.58, 0.15), 38, True),
    "closeup_nameplate": ((0.35, 1.25, 0.45), (0.0, 0.58, 0.14), 40, True),
    "closeup_rating_plate": ((1.45, -0.2, 1.25), (0.5, -0.16, 1.02), 40, True),
    "closeup_top_band_front": ((0.95, 1.55, 2.75), (0.0, 0.58, 2.38), 34, True),
}


def closeups(built):
    for nm, (loc, tgt, lens, working) in CLOSE.items():
        if not want(nm):
            continue
        s = _studio(nm)
        unit(s, built, T(0, 0, ZC), 17.0, working)
        s.camera(loc, tgt, lens)
        s.render()


# ---------------------------------------------------------------------------------------------------- paints
def paints(built):
    for paint in ("keen", "black", "blue", "orange"):
        nm = f"paints_{paint}"
        if not want(nm):
            continue
        s = _studio(nm)
        unit(s, built, T(0, 0, ZC), 17.0, True, paint)
        s.camera((-2.6, 4.4, 3.0), (0, 0, ZC * 0.95), 46)
        s.caption(f"paint: {paint}", (0.0, 0.2, H + 0.3), 0.12)
        s.render()


# ---------------------------------------------------------------------------------------------------- vanilla
def vanilla_compare(built):
    """The CRAC beside a 42U rack (the shared footprint) and the vanilla sources: Gyroscope250_Base (the clone source,
    its gimbal rings as they ship) and WallInsertVent (the only vanilla air device), read-only FBX, same light."""
    nm = "vanilla_compare"
    if not want(nm):
        return
    s = PV.Shot(nm, res=(2600, 1150), floor=(-8.5, 2.2, -2.5, 2.5))
    labels = []
    unit(s, built, T(1.0, 0, ZC), 17.0)
    labels.append(("ours: DC_CRAC\n1.0 x 1.25 x 2.5 m", (1.0, 0.7, H + 0.35)))
    x = -0.2
    if "DC_Rack42_SplitFront" in built:
        P9.rack(s, built, "DC_Rack42_SplitFront", x=x, y=0.0, mix=P9.MIX42)
        labels.append(("ours: 42U rack", (x, 0.7, H + 0.35)))
    x -= 1.0
    for rel, label in (("Gyroscopes/Gyroscopes/250/Models/NonFractured/Base/Gyroscope250_Base.fbx",
                        "vanilla Gyroscope250_Base\n(the clone source)"),
                       ("Walls/Inserts/Vent/Models/NonFractured/WallInsertVent.fbx", "vanilla WallInsertVent")):
        c, lo, hi = PV.vanilla(rel)
        w = hi.x - lo.x
        ctr = (lo + hi) / 2
        s.inst(c, T(x - w / 2, 0, 0) @ T(-ctr.x, -ctr.y, -lo.z))
        labels.append((label, (x - w / 2, 0.7, hi.z - lo.z + 0.35)))
        x -= w + 0.5
    s.inst(PV.human(), T(x + 0.1, 0.6, 0))
    cx = (x + 1.6) / 2
    s.camera((cx, 0.9 * (1.6 - x) + 2.2, 2.4), (cx, 0, 1.25), 32)
    for txt, at in labels:
        s.caption(txt, at, 0.13)
    s.render()


# ---------------------------------------------------------------------------------------------------- room
def _cams():
    def crac_cold(info):     # in the cold aisle, facing row A's cooler (the third unit: x = 2.5)
        w, L, *_, front = PR._geo(info)
        yc = -(w / 2 + 0.625)
        return PR.Cam((2.5 + 1.3, yc + front * 1.45, 1.75), (2.5, yc + front * 0.62, 1.25), 20)

    def crac_rear(info):     # in the other aisle (the walkway behind row A): the cooler's filter door
        w, L, *_, front = PR._geo(info)
        yc = -(w / 2 + 0.625)
        return PR.Cam((2.5 - 1.3, yc - front * 1.45, 1.7), (2.5, yc - front * 0.62, 1.25), 20)
    PR.CAMERAS.update(crac_front=crac_cold, crac_rear=crac_rear)


def room_shots(built):
    _cams()
    for aisle in ("cold", "hot"):
        for cam in ("aisle_eye", "photo1", "overhead", "end_row", "crac_front", "crac_rear"):
            PR.shot(built, cam, 1.5, aisle, captions=False)
    for w in (1.0, 2.0):
        for aisle in ("cold", "hot"):
            PR.shot(built, "aisle_eye", w, aisle, captions=False)
    PR.shot(built, "photo1", 1.5, "cold", paint="black", name="room_150_cold_photo1_black", captions=False)
    PR.shot(built, "crac_front", 1.5, "cold", paint="black", name="room_150_cold_crac_front_black", captions=False)


def render_all(built):
    PR._out("crac")
    if NAME not in built:
        print("crac previews: DC_CRAC not built")
        return
    hero(built)
    lods(built)
    fans(built)
    closeups(built)
    paints(built)
    vanilla_compare(built)
    room_shots(built)
    anim(built)
    print("crac previews ->", PV.OUT)
