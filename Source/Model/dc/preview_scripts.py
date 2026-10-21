"""Plan 4 Task 7: the scripted KVM motion, rendered (Source/Model/preview/plan4/).

The real KVM model (dc/servers/kvm.py, as built) animated along the CoreTests trajectories
(Source/Model/preview/plan4/traj/*.csv, 240 Hz; Scripts/Client/Core/KvmMotion.cs), sampled at 60 fps: the drawer and
the screen are placed every frame exactly as the game places them (preview_task8.kvm_part_matrices). The KVM sits in
slot 5 of a populated DC_Rack42_SplitFront (DC_Srv_Compute in slot 6 above it), the doors open; in
door_close_while_out the door leaves run on the same clock (OpenRatio linear over DOOR_SECONDS, starting
kvm_charts.DOOR_LEAD before the sequencer's stow command: P4-4's latency). Every frame carries the time and the pose.

Views: side (an orthographic section at x = +0.26 m, so the rack's side panel and right leaf do not hide the
profile), 3q (front-left, above), first_person (standing at the rack), top (door_close_while_out only: an
orthographic plan section just above the lid's apex, the leaves against the drawer), orbit (open only).

Outputs (the raw frames under frames/ are not tracked):
    frames/<traj>/<view>_%04d.png        60 fps, 1280 x 720
    kvm_<traj>_<view>.mp4                H.264, 60 fps
    kvm_<traj>_3q.gif                    15 fps, 640 wide
    kvm_<traj>_sheet.png                 contact sheet: 24 frames spread over the whole run, time burned in
    kvm_dataonly_vs_scripted_3q.mp4      left the data-only simultaneous pose(f) over 1.0 s, right the scripted open
    kvm_data_only_top_<view>.mp4         Ruling P4-12: the full rack's top slot runs the data-only path
    kvm_scripted_{f_gate,f_lift,f_bounce,out}_3q.png   stills at the open's key moments
    kvm_timing.svg, kvm_motion_graphs.svg               dc/kvm_charts.py (stdlib)

    DC_PREVIEW=plan4 blender -b --python Source/Model/build_dc.py -- DC_Rack42_SplitFront DC_Srv_KVM DC_Srv_Compute \
        DC_Srv_Timer DC_Srv_UPS DC_Srv_Storage DC_Srv_Status DC_Srv_Programmable
(DC_SHOTS=prefix,... renders a subset of the sequences, e.g. DC_SHOTS=open,stills; DC_FAST=1 half resolution;
DC_KVM_ENCODE_ONLY=1 skips rendering and only re-runs the ffmpeg steps over existing frames).
"""
import math
import os
import shutil
import subprocess

from . import catalog, config, doors
from . import kvm_charts as KC
from . import kvm_motion as K
from . import preview as PV
from . import preview_mats as PM
from . import preview_task8 as P8
from . import preview_task9 as P9
from . import subparts as S
from .kvm_preview_plan import FPS, PLAN, SLOT, TOP, runs  # noqa: F401  (bpy-free: the tests read it)
from .preview import Shot, T, want

OUT = os.path.join(config.PREVIEW_DIR, "plan4")
FRAMES = os.path.join(OUT, "frames")
GIF_FPS = 15
RES = (1280, 720)
RACK = "DC_Rack42_SplitFront"
SECTION_X = 0.26                                  # the side view's cut plane (the KVM spans x +-0.21)
KVM = P8.KVM

# camera, target, lens (perspective) or ("ortho", camera, target, ortho scale, near-plane distance)
VIEWS = {
    "side": ("ortho", (3.0, 0.55, 1.47), (0.0, 0.55, 1.47), 1.75, 3.0 - SECTION_X),
    "3q": ((-1.15, 2.75, 2.05), (0.0, 0.62, 1.44), 50),
    "first_person": ((0.30, 1.75, 1.70), (0.0, 0.45, 1.30), 26),
}
TOP_SECTION_Z = 1.72                              # above the lid's apex in slot 5 (~1.64 m)
TOP_VIEW = ("plan", (0.0, 0.78, 6.0), 1.7, 6.0 - TOP_SECTION_Z)


def _mix(built, kvm_slot):
    """The populated rack (preview_task9.MIX42) with the animated KVM's slot left empty; a stowed KVM in slot 5 when
    the animated one is elsewhere; anything not built becomes an empty slot."""
    mix = list(P9.MIX42)
    mix[SLOT - 1] = "KVM0" if kvm_slot != SLOT else None
    mix[kvm_slot - 1] = None
    names = {"UPS": "DC_Srv_UPS", "PROG": P8.PROG, "KVM0": KVM}
    return tuple(n if n and names.get(n, n) in built else None for n in mix)


# ---------------------------------------------------------------------------------------------------- the scene
class Scene:
    """One Shot: the populated rack, its door leaves (driven), the animated KVM (driven), a camera-fixed caption."""

    def __init__(self, built, run, view, res=RES):
        self.run, self.view = run, view
        s = Shot(f"p4kvm_{run.name}_{view}", res=res, floor=(-2.5, 2.5, -2.5, 4.0))
        try:
            s.sc.eevee.taa_render_samples = 16 if PV.FAST else 64
        except Exception:
            pass
        self.s = s
        spec = catalog.BY_NAME[RACK]
        self.spec = spec
        P9.rack(s, built, RACK, f=run.door(0.0), mix=_mix(built, run.slot), fan=15, working=True)
        self.leaves = []
        for lf in doors.leaves(spec):
            cname = f"pv9_{RACK}_{lf['model']}_L0_keen"
            ob = next(o for o in s.sc.collection.objects if o.instance_collection and o.instance_collection.name == cname)
            self.leaves.append((ob, lf))
        self.C = T(0, 0, P9._H(RACK) / 2)
        _, self.parts = P8.kvm(s, built, 0.0, 0.0, 0.25 * run.slot, slide=0.0, fold=0.0)
        self.base = T(0, 0, 0.25 * run.slot + P8.H / 2)
        self._camera(view)
        self.hud = self._hud()

    def _camera(self, view):
        s = self.s
        if view == "top":
            _, loc, scale, near = TOP_VIEW
            s.camera(loc, (loc[0], loc[1], 0.0), 50, ortho=scale)
            s.cam.rotation_euler = (0, 0, 0)
            s.cam.data.clip_start = near
            self.hud_at = (scale, near + 0.0005, True)
            return
        if view == "orbit":
            self.orbit_target = (0.0, 0.55, 1.42)
            s.camera((0, 3.4, 2.0), self.orbit_target, 50)
            self.hud_at = (0.3 * 36 / 50, 0.3, False)
            return
        v = VIEWS[view]
        dz = 0.25 * (self.run.slot - SLOT)             # follow the KVM to another slot
        if v[0] == "ortho":
            _, loc, tgt, scale, near = v
            loc, tgt = (loc[0], loc[1], loc[2] + dz), (tgt[0], tgt[1], tgt[2] + dz)
            s.camera(loc, tgt, 50, ortho=scale)
            s.cam.data.clip_start = near
            self.hud_at = (scale, near + 0.0005, True)
        else:
            loc, tgt, lens = v
            s.camera((loc[0], loc[1], loc[2] + dz), (tgt[0], tgt[1], tgt[2] + dz), lens)
            self.hud_at = (0.3 * 36 / lens, 0.3, False)

    def _hud(self):
        """Two caption lines fixed to the camera's lower-left corner."""
        import bpy
        width, dist, _ = self.hud_at
        height = width * RES[1] / RES[0]
        cu = bpy.data.curves.new("hud", "FONT")
        cu.size = width / 42
        cu.align_x, cu.align_y = "LEFT", "BOTTOM"
        cu.materials.append(PM.get("Caption"))
        o = bpy.data.objects.new("hud", cu)
        o.parent = self.s.cam
        x0, y0 = -width / 2 * 0.95, -height / 2 + cu.size * 2.4
        o.location = (x0, y0, -dist)
        self.s.link(o)
        # a dark plate behind the caption, so it reads over the bright floor and the perforated leaves
        mat = bpy.data.materials.get("pv_hud_plate") or PM.simple("pv_hud_plate", (0.012, 0.013, 0.016), 0.95)
        me = bpy.data.meshes.new("hud_plate")
        pad = cu.size * 0.6
        x1, y1, x2, y2 = x0 - pad, y0 - pad, x0 + width * 0.56, y0 + cu.size * 2.0 + pad
        me.from_pydata([(x1, y1, 0), (x2, y1, 0), (x2, y2, 0), (x1, y2, 0)], [], [(0, 1, 2, 3)])
        me.materials.append(mat)
        plate = bpy.data.objects.new("hud_plate", me)
        plate.parent = self.s.cam
        plate.location = (0, 0, -dist - 0.0003)
        self.s.link(plate)
        return o

    def orbit(self, u):
        """The orbit camera at u in [0, 1]: from 55 deg left to 55 deg right of the KVM's front, 3.4 m out."""
        from mathutils import Vector
        a = math.radians(-55 + 110 * u)
        tx, ty, tz = self.orbit_target
        loc = Vector((tx + 2.6 * math.sin(a), ty + 2.6 * math.cos(a), 1.95))
        self.s.cam.location = loc
        self.s.cam.rotation_euler = (Vector(self.orbit_target) - loc).to_track_quat("-Z", "Y").to_euler()

    def pose(self, t):
        run = self.run
        slide, fold = run.at(t)
        md, ms = P8.kvm_part_matrices(self.base, slide, fold)
        self.parts[0].matrix_world = md
        self.parts[1].matrix_world = ms
        f = run.door(t)
        for ob, lf in self.leaves:
            ob.matrix_world = self.C @ T(lf["axis"][0], lf["axis"][1], 0) @ P9.Rz(doors.swing_yaw(lf, f))
        door = f"   door {f:.2f}" if run.name == "door_close_while_out" else ""
        self.hud.data.body = (f"{run.label}\nt = {t:5.3f} s   drawer {slide * S.TRAVEL:5.3f} m   "
                              f"lid {fold * S.FOLD_DEG:5.1f} deg{door}")
        return slide, fold

    def render_to(self, path):
        import bpy
        self.s.sc.render.filepath = path
        bpy.ops.render.render(write_still=True, scene=self.s.sc.name)

    def free(self):
        import bpy
        for o in list(self.s.sc.collection.objects):
            if o.type in ("FONT", "CAMERA", "LIGHT", "MESH"):
                data = o.data
                bpy.data.objects.remove(o)
                if data is not None and data.users == 0:
                    for coll in (bpy.data.curves, bpy.data.cameras, bpy.data.lights, bpy.data.meshes):
                        if data.name in coll and coll[data.name] == data:
                            coll.remove(data)
                            break
            else:
                bpy.data.objects.remove(o)
        bpy.data.scenes.remove(self.s.sc)


def render_sequence(built, run, view):
    folder = os.path.join(FRAMES, run.name)
    os.makedirs(folder, exist_ok=True)
    sc = Scene(built, run, view)
    for i in range(run.frames):
        t = i / FPS
        if view == "orbit":
            sc.orbit(i / max(run.frames - 1, 1))
        sc.pose(t)
        sc.render_to(os.path.join(folder, f"{view}_{i:04d}.png"))
    print(f"RENDERED {run.name}/{view}: {run.frames} frames")
    sc.free()


def stills(built, all_runs):
    """kvm_scripted_{f_gate,f_lift,f_bounce,out}_3q.png: the scripted open at its key moments."""
    op = all_runs["open"]
    tun = K.read_tuning()
    gate = next(t for t, s, _ in op.traj if s >= tun["FoldGate"])
    lift = next(t for t, _, f in op.traj if f >= 0.5)
    bounce = max(op.traj, key=lambda r: r[2])[0]
    sc = Scene(built, op, "3q", res=(1920, 1080))
    for key, t in (("f_gate", gate), ("f_lift", lift), ("f_bounce", bounce), ("out", op.duration)):
        sc.pose(t)
        sc.render_to(os.path.join(OUT, f"kvm_scripted_{key}_3q.png"))
    sc.free()


# ---------------------------------------------------------------------------------------------------- ffmpeg
def _ff(*args):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    subprocess.run(cmd, check=True)


def encode(all_runs):
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found: frames only")
        return
    for name, views in PLAN.items():
        run = all_runs[name]
        folder = os.path.join(FRAMES, name)
        for view in views:
            pattern = os.path.join(folder, f"{view}_%04d.png")
            if not os.path.exists(pattern % 0):
                continue
            if name != "dataonly_open":
                _ff("-framerate", str(FPS), "-i", pattern, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
                    "-preset", "slow", "-movflags", "+faststart", os.path.join(OUT, f"kvm_{name}_{view}.mp4"))
            if view == "3q" and name not in ("dataonly_open",):
                _ff("-framerate", str(FPS), "-i", pattern, "-vf",
                    f"fps={GIF_FPS},scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];"
                    "[b][p]paletteuse=dither=bayer:bayer_scale=4", os.path.join(OUT, f"kvm_{name}_3q.gif"))
                step = max(1, math.ceil(run.frames / 24))
                _ff("-framerate", str(FPS), "-i", pattern, "-vf",
                    f"select=not(mod(n\\,{step})),scale=320:-1,tile=8x3:padding=4:color=0x101214",
                    "-frames:v", "1", os.path.join(OUT, f"kvm_{name}_sheet.png"))
    left = os.path.join(FRAMES, "dataonly_open", "3q_%04d.png")
    right = os.path.join(FRAMES, "open", "3q_%04d.png")
    if os.path.exists(left % 0) and os.path.exists(right % 0):
        _ff("-framerate", str(FPS), "-i", left, "-framerate", str(FPS), "-i", right, "-filter_complex",
            "[0:v][1:v]hstack=inputs=2,scale=1920:-2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
            "-preset", "slow", "-movflags", "+faststart", os.path.join(OUT, "kvm_dataonly_vs_scripted_3q.mp4"))


# ---------------------------------------------------------------------------------------------------- entry
NEED = (RACK, KVM, "DC_Srv_Compute")


def render_all(built):
    PV.OUT = OUT
    PM.get("Caption")
    if any(n not in built for n in NEED):
        print("plan4 KVM previews need", [n for n in NEED if n not in built])
        return
    all_runs = runs()
    os.makedirs(OUT, exist_ok=True)
    KC.timing_svg()
    KC.graphs_svg()
    probe = os.environ.get("DC_KVM_PROBE")       # a time in seconds: one frame per wanted (run, view), to frame cameras
    if probe:
        os.makedirs(os.path.join(FRAMES, "probe"), exist_ok=True)
        for name, views in PLAN.items():
            for view in views:
                if want(f"{name}_{view}"):
                    sc = Scene(built, all_runs[name], view)
                    if view == "orbit":
                        sc.orbit(0.5)
                    sc.pose(float(probe))
                    sc.render_to(os.path.join(FRAMES, "probe", f"{name}_{view}.png"))
                    sc.free()
        return
    if not os.environ.get("DC_KVM_ENCODE_ONLY"):
        for name, views in PLAN.items():
            for view in views:
                if want(f"{name}_{view}") or want(name):
                    render_sequence(built, all_runs[name], view)
        if want("stills"):
            stills(built, all_runs)
    encode(all_runs)
