"""The showcase set: clean presentation stills and looping clips of the mod as it stands (no captions, no HUD).

    DC_PREVIEW=showcase blender -b --python Source/Model/build_dc.py -- all

Reuses the existing scenes: the T12 two-aisle hall (dc/preview_room.room_scene, dc/preview_p3t12 cameras), the
studio rig (dc/preview.Shot), the populated racks (dc/preview_task9.rack, dc/preview_p3t7.rack_with_strips), the
Plan 2 rack row (dc/preview_trays.rack_row), the KVM's scripted motion (dc/preview_scripts.Scene on the CoreTests
trajectories) and the CRAC fan ramp (dc/crac FAN_*). The Damaged server is a read-only import of our own exported
Models/.

Writes Source/Model/preview/showcase/:
  NN-slug.png                      the stills, 1920 x 1080
  anim/<clip>/f_NNNN.png           the clips' frames, 1280 x 720 at ANIM_FPS (not tracked)
DC_SHOTS=prefix,... renders a subset (still names, or "anim-<clip>"); DC_FAST=1 half resolution;
DC_SHOWCASE_NO_ANIM=1 skips the clips, DC_SHOWCASE_NO_STILLS=1 the stills.

The web copies (no Blender; ffmpeg + Pillow):
    python3 -m dc.preview_showcase web       (from Source/Model)
  -> resources/showcase/img/<name>.jpg (1920 px, q90), anim/<name>.{gif,mp4,jpg}, shots.json (WEB_NAMES)
"""
import json
import math
import os
import shutil
import subprocess

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # Source/Model
OUT = os.path.join(HERE, "preview", "showcase")
WEB = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "resources", "showcase"))
RES = (1920, 1080)
ANIM_RES = (1280, 720)
ANIM_FPS = 30
COLD_W, HOT_W = 1.5, 1.0
R42, R42R = "DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear"
# a 42U rack's slots from the bottom: UPS (two slots), storage, compute, the KVM in slot 5, switch, status, programmable
MIX_SHOW = ("UPS", None, "DC_Srv_Storage", "DC_Srv_Compute", "KVM", "DC_Srv_Switch", "DC_Srv_Status", "PROG")
MIX_REAR = ("UPS", None, "DC_Srv_Storage", "DC_Srv_Compute", "DC_Srv_Compute", "DC_Srv_Switch", "DC_Srv_Timer",
            "DC_Srv_Switch")
MIX24 = ("UPS", None, "DC_Srv_Switch", "DC_Srv_Compute")

# ---------------------------------------------------------------------------------------------------- web metadata
SHOTS = [
    ("01-cold-aisle", "Contained cold aisle",
     "A two-aisle server hall built entirely from the mod's blocks, looking down the contained cold aisle. Like a "
     "real data centre, cold air is fed into this sealed aisle through the floor and the in-row cooler, and the hot "
     "exhaust leaves through the backs of the racks."),
    ("02-hall-overhead", "The whole hall from above",
     "Three rows of racks with a cold aisle and a hot aisle, each closed off by roof panels and sliding doors. "
     "In-row coolers, power cabinets and overhead cable trays complete the room."),
    ("03-containment-doors", "Containment doors",
     "The sliding doors at the end of each aisle, with blue (cold) and red (hot) aisle signs above them. The doors "
     "really slide open and closed in game, keeping the cold and hot air apart."),
    ("04-rack-front", "42U rack, front",
     "A full-height 42U rack with its split front doors swung open, loaded with a mix of servers: storage, compute, "
     "a network switch, a UPS battery unit, a status display, a programmable server and a pull-out KVM console."),
    ("05-rack-rear", "42U rack, rear",
     "The same rack from the back with the rear doors open: two vertical power strips (feed A and feed B), as in a "
     "real rack with redundant power, and the servers' rear panels."),
    ("06-kvm-open", "KVM console",
     "The KVM drawer pulled out with its screen folded up, the way a real rack-mounted keyboard and monitor tray "
     "works. In game it slides out and opens in a sprung, sequenced motion."),
    ("07-server-lineup", "Every server type",
     "All ten server blocks side by side. The front row is the hardware (compute, storage, switch, blank panel, "
     "UPS); the back row holds the working blocks: timer, event controller, status display, programmable and KVM."),
    ("08-cable-trays", "Overhead cable trays",
     "Cable trays hung from ceiling rods over a row of racks: a tee branching off, reducers stepping the bundle "
     "down, and drops that waterfall cables into each rack, the way real overhead cable management is done."),
    ("09-crac-front", "In-row cooler, front",
     "The in-row CRAC (computer room air conditioner) between two racks: three big fans that spin up with a soft "
     "start when powered, and a controller panel on top."),
    ("10-crac-rear", "In-row cooler, rear",
     "The cooler's back: the return-air filters on top and, below them, the oxygen and coolant service ports "
     "(shown blanked off), where the block connects to the game's pipe networks."),
    ("11-pdu-cabinet", "Power distribution",
     "A PDU (power distribution unit) cabinet beside a rack seen from behind, its two power strips in place. The "
     "cabinet feeds power to the racks in its row, like the breaker cabinets in a real hall."),
    ("12-raised-floor", "Raised floor",
     "Racks and a cooler standing on the raised floor: solid tiles plus perforated tiles where cold air rises in "
     "front of the racks, with the support pedestals underneath."),
    ("13-signs", "Signs and labels",
     "The aisle sign over the door, the hanging aisle sign and the labels on top of each rack. They are LCD signs: "
     "players type their own text, and the frame colour marks hot or cold."),
    ("14-damage", "Damage states",
     "An intact compute server beside a damaged one. Every block has its own dented model, which the game swaps "
     "in when the block takes damage, and a broken model for when it is destroyed."),
    ("15-half-racks", "24U half racks",
     "The three half-height 24U racks: open frame, split front doors, and front and rear doors. They take the same "
     "servers and power strips as the full racks."),
    ("16-cold-aisle-black", "Cold aisle in black",
     "The same cold aisle with the racks painted black, the colour most real halls use. Every block takes the "
     "player's paint colour."),
]
ANIMS = [
    ("01-kvm", "KVM console opening",
     "The KVM drawer slides out, the screen lifts with a small spring at the top, then it folds away and slides "
     "back in. The motion is scripted and sequenced, like a real sprung console arm."),
    ("02-rack-doors", "Rack doors",
     "The split front doors swing open to 85 degrees and close again, timed like the game's door blocks."),
    ("03-containment-door", "Containment door",
     "The aisle's sliding door opening and closing, seen from inside the contained cold aisle."),
    ("04-crac-fans", "Cooler fans spinning up",
     "The cooler is switched on: its run lamp lights and the three fans ramp up over a two-second soft start, then "
     "keep running."),
    ("05-rack-orbit", "Loaded 42U rack",
     "A slow turn around a full 42U rack with its doors open, servers installed and the power strips at the back."),
    ("06-aisle-dolly", "Walking the cold aisle",
     "A slow walk into the contained cold aisle between two rows of racks, under the roof's light strips."),
]


def want(name):
    only = [s for s in os.environ.get("DC_SHOTS", "").split(",") if s]
    return not only or any(name.startswith(o) for o in only)


# ---------------------------------------------------------------------------------------------------- scenes
def _studio(name, res=RES, floor=(-8.0, 8.0, -8.0, 8.0), light=1.0):
    from . import preview as PV
    PV.OUT = OUT
    return PV.Shot(name, res=res, floor=floor, light=light)


def _hall_shot(built, name, doors_open=0.0, contain_open=0.0, res=RES, paint="keen"):
    """The T12 hall in a fresh Shot (dc/preview_room.shot without the render): returns (shot, room collection,
    info)."""
    from . import preview as PV
    from . import preview_room as PR
    import bpy
    PV.OUT = PR.OUT = OUT
    coll = PR.room_scene(built, COLD_W, "cold", paint, doors_open=doors_open, contain_open=contain_open,
                         hall=HOT_W)
    info = next(i for c, i in PR._ROOMS.values() if c == coll)
    s = PV.Shot(name, res=res, floor=None, world=(0.004, 0.0045, 0.006), light=0.0)
    for o in [o for o in s.sc.collection.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o)
    try:
        s.sc.eevee.shadow_pool_size = "2048"
        s.sc.eevee.shadow_resolution_scale = 0.5
    except (AttributeError, TypeError):
        pass
    s.sc.collection.children.link(coll)
    return s, coll, info


def _hide(info, groups):
    objs = [o for g in groups for o in info["groups"].get(g, [])]
    for o in objs:
        o.visible_camera = False
    return objs


def _hall_still(built, name, cam, doors_open=0.0, contain_open=0.0, paint="keen"):
    if not want(name):
        return
    s, coll, info = _hall_shot(built, name, doors_open, contain_open, paint=paint)
    s.camera(cam.loc, cam.target, cam.lens)
    hidden = _hide(info, cam.hide)
    try:
        s.render()
    finally:
        for o in hidden:
            o.visible_camera = True


def _placed_vignette(s, built, keep, doors_open=0.0):
    """The hall's own placements (room.two_aisle_room) that pass keep(p), real blocks into the Shot s."""
    from . import room
    from . import preview as PV
    from . import preview_room as PR
    placed = room.two_aisle_room(COLD_W, HOT_W, 4)
    rack_i = 0
    for p in placed:
        if not keep(p) or p.name not in built:
            continue
        fam = room.spec(p).family
        if fam == "rack":
            PR._rack(s, built, p, PR._mix(built, rack_i), doors_open)
            rack_i += 1
        elif fam == "crac":
            PR.crac_unit(s, built, p.name, PR._M(p), 11.0 + 31.0 * rack_i, True)
        elif fam == "contain_door":
            PR.contain_door(s, built, p.name, PR._M(p), 0.0)
        elif fam == "sign":
            PR.built_sign(s.sc.collection, s, built, p, PR.aisle_of(p, "cold"))
        else:
            paint = PR.TRAY_PAINT if fam in ("tray", "trayrods") else "keen"
            s.inst(PV.painted(built, p.name, 0, paint), PR._M(p))
    return placed


# ---------------------------------------------------------------------------------------------------- the stills
def hall_stills(built):
    from . import preview_room as PR
    from . import preview_p3t12 as P12
    from . import room
    probe = PR.room_scene(built, COLD_W, "cold", "keen", hall=HOT_W)   # noqa: F841  (info for the cameras)
    info = next(i for c, i in PR._ROOMS.values() if i.get("hall") == HOT_W)
    # the T12 photo 1 framing (rack doors shut: open 85 deg, the leaves wall off a 1.5 m aisle from this camera)
    _hall_still(built, "01-cold-aisle", PR._cam_photo1(info))
    _hall_still(built, "02-hall-overhead", P12.cam_overhead(info))
    _hall_still(built, "03-containment-doors", P12.cam_doors_outside(info))
    # 13: from the walkway beyond row A, over the rack tops: the rack labels, the hanging sign, the west door's sign
    L = room.PITCH * len(room.row_units(4))
    _hall_still(built, "13-signs", PR.Cam((-1.6, -2.75, 2.55), (1.6, 0.0, 2.85), 24))
    _hall_still(built, "16-cold-aisle-black", PR._cam_photo1(info), paint="black")
    return L


def rack_front(built):
    from . import preview_p3t7 as P7
    nm = "04-rack-front"
    if want(nm) and R42 in built:
        s = _studio(nm)
        P7.rack_with_strips(s, built, R42, f=1.0, mix=MIX_SHOW)
        s.camera((2.3, 4.6, 2.05), (0.05, 0.1, 1.3), 35)
        s.render()


def rack_rear(built):
    from . import preview_p3t7 as P7
    nm = "05-rack-rear"
    if want(nm) and R42R in built:
        s = _studio(nm)
        P7.rack_with_strips(s, built, R42R, f=0.0, f_rear=1.0, mix=MIX_REAR)
        s.camera((-2.2, -4.6, 2.1), (-0.05, -0.1, 1.3), 35)
        s.render()


def kvm_open(built):
    from . import preview_task9 as P9
    nm = "06-kvm-open"
    if want(nm) and R42 in built and "DC_Srv_KVM" in built:
        s = _studio(nm)
        P9.rack(s, built, R42, f=1.0, mix=MIX_SHOW, fan=15, working=True)
        s.camera((-0.95, 2.05, 1.95), (0.02, 0.62, 1.42), 40)
        s.render()


LINEUP = (("DC_Srv_Compute", "DC_Srv_Storage", "DC_Srv_Switch", "DC_Srv_Blank", "UPS"),
          ("DC_Srv_Timer", "DC_Srv_EventCtl", "DC_Srv_Status", "PROG", "KVM"))


def lineup(built):
    from . import preview_task9 as P9
    from .preview import T
    nm = "07-server-lineup"
    if not want(nm):
        return
    s = _studio(nm)
    dx = 0.62
    for r, row in enumerate(LINEUP):
        y = 0.75 - 2.0 * r
        for i, n in enumerate(row):
            P9.srv(s, built, n, T((2 - i) * dx, y, 0.0), 0.0, "keen")   # screen right is -x
    s.camera((-0.4, 5.4, 2.5), (-0.12, -0.1, -0.05), 50)
    s.render()


def _tray_scene(built, nm, cam):
    from . import preview_trays as PT
    from . import preview as PV
    from . import dims as DM
    from .preview import Rz, T
    PV.OUT = OUT
    s = PT.scene(nm, res=RES, floor=(-6.0, 10.0, -5.0, 8.0), light=1.3)
    row = [("DC_Tray_Tee_Full", None)] + list(PT.ROW)
    # rack_row starts its run at x = -1.0; the Tee goes one metre before it
    racks, joints, zc = _rack_row_from(PT, s, built, row, x0=-2.0)
    # the Tee's branch (port c, +y at x0 + 0.5): a long straight across toward the aisle, a rod at its middle
    y0 = DM.TRAY_RACK_Y - 0.25
    z0 = PT.FULL42 + DM.TRAY_HANG
    bx = -2.0 + 0.5
    s.inst(PV.painted(built, "DC_Tray_StraightL_Full", 0, "blue"),
           T(bx + 0.25, y0 + 0.75, z0) @ Rz(90) @ T(0.75, 0.25, 0.125))
    if "DC_TrayRods_100" in built:
        PT.piece(s, built, "DC_TrayRods_100", bx - 0.25, y0 + 0.75 + 0.75 - 0.25, z0 + 0.25, paint="blue")
    ceil = PT.box(s, "ceiling", (-8.0, -6.0, zc), (12.0, 8.0, zc + 0.12), "Grey")
    ceil.visible_shadow = False   # a hall ceiling for the eye; the sun still lights the row
    s.camera(*cam)
    PT.sun(s, 3.5)
    return s


def _rack_row_from(PT, s, built, row, x0):
    """preview_trays.rack_row with the run starting at x0 (the Tee before the row's own start)."""
    from . import dims as DM
    from . import preview_task9 as P9
    x, racks, joints = x0, {}, []
    mix = tuple(m if (m is None or m in built) else None for m in PT.MIX)
    top = PT.FULL42 + 0.75
    for name, rack in row:
        L = PT._len(name)
        if rack:
            racks[x + L / 2] = rack
            PT._drop_on_rack(s, built, name, x + L / 2,
                             chute="DC_Tray_Chute" if rack.startswith("DC_Rack24") else None, paint="blue")
        else:
            PT.piece(s, built, name, x, DM.TRAY_RACK_Y - 0.25, PT.FULL42 + DM.TRAY_HANG, paint="blue")
        if "DC_TrayRods_100" in built:
            PT.piece(s, built, "DC_TrayRods_100", x + L / 2 - 0.25, DM.TRAY_RACK_Y - 0.25, top, paint="blue")
        x += L
        joints.append(x)
    for rx, rack in racks.items():
        if rack in built:
            P9.rack(s, built, rack, rx, 0.0, mix=mix if rack.startswith("DC_Rack42") else mix[:4], working=True)
    return racks, joints[:-1], top + 1.0


TRAY_CAMS = {"08-cable-trays": ((-3.6, 5.0, 3.6), (1.8, 0.3, 2.6), 24)}


def tray_stills(built):
    from . import preview_trays as PT
    for nm, cam in TRAY_CAMS.items():
        if not want(nm):
            continue
        row = [("DC_Tray_Tee_Full", None)] + list(PT.ROW)
        need = [n for n, _ in row] + ["DC_Tray_Chute", "DC_Rack42_Open", "DC_Rack24_Open", "DC_Tray_StraightL_Full"]
        if not all(n in built for n in need):
            print("showcase: trays skipped (blocks missing)")
            return
        _tray_scene(built, nm, cam).render()


def _crac_row(s, built):
    """The CRAC between two closed SplitFront racks (an in-row cooler's place)."""
    from . import preview_p3t6 as P6
    from . import preview_task9 as P9
    from .preview import T
    P6.unit(s, built, T(0, 0, P6.ZC), 17.0)
    for x, mix in ((-1.0, MIX_REAR), (1.0, P9.MIX42)):
        P9.rack(s, built, R42, x=x, f=0.0, mix=tuple("KVM0" if m == "KVM" else m for m in mix), working=True)


def crac(built):
    if "DC_CRAC" not in built:
        return
    for nm, cam in (("09-crac-front", ((2.6, 4.3, 2.1), (0.0, 0.0, 1.3), 35)),
                    ("10-crac-rear", ((-2.5, -4.2, 2.0), (0.0, 0.0, 1.25), 35))):
        if not want(nm):
            continue
        s = _studio(nm)
        _crac_row(s, built)
        s.camera(*cam)
        s.render()


def pdu(built):
    from . import preview_p3t7 as P7
    from . import preview as PV
    from .preview import T
    nm = "11-pdu-cabinet"
    if not want(nm) or "DC_PDU_Cabinet" not in built:
        return
    s = _studio(nm)
    s.inst(PV.painted(built, "DC_PDU_Cabinet", 0, "keen"), T(0.5, 0, 1.25))
    P7.rack_with_strips(s, built, R42R, x=-0.5, rot=180.0, f=0.0, f_rear=1.0, mix=MIX_REAR)
    s.camera((-1.9, 4.4, 2.1), (-0.05, 0.0, 1.25), 35)
    s.render()


def raised_floor(built):
    nm = "12-raised-floor"
    if not want(nm):
        return
    s = _studio(nm, floor=(-12, 12, -12, 12))

    def keep(p):
        from . import room
        fam = room.spec(p).family
        x, y = p.origin[0], p.origin[1]
        if fam == "floor":
            return -1.0 < x < 3.5 and -2.8 < y < 0.75
        if fam in ("rack", "crac", "pdu_strip"):
            return x < 3.0 and y < 0
        return False
    _placed_vignette(s, built, keep)
    s.camera((-2.4, 2.5, 1.75), (1.2, -1.1, 0.95), 28)
    s.render()


def _import_model(name, kind):
    """A read-only import of our own exported Models/<name>/<kind>/<name>_<kind>.fbx, LOD0, Keen stand-ins."""
    import bpy
    from . import config
    from . import preview as PV
    from . import preview_mats as PM
    path = os.path.join(config.MODELS_DIR, name, kind, f"{name}_{kind}.fbx")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    c = bpy.data.collections.new(f"sc_{name}_{kind}")
    bpy.context.scene.collection.children.link(c)
    for o in new:
        for uc in list(o.users_collection):
            uc.objects.unlink(o)
        c.objects.link(o)
        if o.type != "MESH":
            continue
        for i, sl in enumerate(o.material_slots):
            n = (sl.material.name if sl.material else "").split(".")[0]
            k = "Fractured" if n.startswith("Fractured") else PM.keen_key(n, "keen")
            o.material_slots[i].material = PM.get(k)
    PV._exclude(c)
    return c, new


def damage(built):
    """An intact Compute server beside its Damaged model (the dented one the game swaps in), the exported file."""
    from . import preview_task6 as P6
    from .preview import Rz, T
    nm = "14-damage"
    name = "DC_Srv_Compute"
    if not want(nm) or name not in built:
        return
    s = _studio(nm)
    # screen right is -x: the intact server on the left, its Damaged model on the right
    dx = 0.33
    P6.srv(s, built, name, dx, 0.0, 0.0)
    c, _ = _import_model(name, "Damaged")
    s.inst(c, T(-dx, 0, P6.H / 2) @ Rz(DAMAGE_YAW))
    s.camera((-0.55, 1.65, 0.75), (0.0, 0.0, 0.1), 42)
    s.render()


DAMAGE_YAW = float(os.environ.get("DC_SHOWCASE_DAMAGE_YAW", "0"))


def half_racks(built):
    from . import preview_p3t7 as P7
    nm = "15-half-racks"
    if not want(nm):
        return
    s = _studio(nm)
    # from the front-left (looking along -y, screen right is -x): open, split front, front + rear (its rear leaves
    # out on the right)
    for x, rk, f, fr in ((1.6, "DC_Rack24_Open", 0.0, 0.0), (0.0, "DC_Rack24_SplitFront", 1.0, 0.0),
                         (-1.6, "DC_Rack24_SplitFrontRear", 1.0, 1.0)):
        if rk in built:
            P7.rack_with_strips(s, built, rk, x=x, f=f, f_rear=fr, mix=MIX24)
    s.camera((-3.0, 4.9, 2.3), (-0.1, 0.0, 0.6), 35)
    s.render()


def stills(built):
    os.makedirs(OUT, exist_ok=True)
    hall_stills(built)
    rack_front(built)
    rack_rear(built)
    kvm_open(built)
    lineup(built)
    tray_stills(built)
    crac(built)
    pdu(built)
    raised_floor(built)
    damage(built)
    half_racks(built)


# ---------------------------------------------------------------------------------------------------- the clips
def _frames_dir(clip):
    d = os.path.join(OUT, "anim", clip)
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        if f.endswith(".png"):
            os.remove(os.path.join(d, f))
    return d


ANIM_STEP = int(os.environ.get("DC_SHOWCASE_ANIM_STEP", "1"))   # > 1: every Nth frame only (a quick check)


def _render_frame(s, path):
    import bpy
    i = int(os.path.basename(path)[2:6])
    if i % ANIM_STEP:
        return
    s.sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=s.sc.name)


def _anim_samples(s):
    try:
        s.sc.eevee.taa_render_samples = 32
    except Exception:
        pass


def _ease(u):
    """Cosine ease in-out on [0, 1]."""
    u = min(1.0, max(0.0, u))
    return 0.5 - 0.5 * math.cos(math.pi * u)


def _door_timeline(t, hold0=0.4, move=1.0, hold1=1.2):
    """Open fraction of a linear 1 s door (the game's OpeningDuration, no easing): closed, open, hold, close."""
    if t < hold0:
        return 0.0
    t -= hold0
    if t < move:
        return t / move
    t -= move
    if t < hold1:
        return 1.0
    t -= hold1
    if t < move:
        return 1.0 - t / move
    return 0.0


def _leaf_objects(s, rack_name):
    from . import catalog, doors
    out = []
    for lf in doors.leaves(catalog.BY_NAME[rack_name]):
        cname = f"pv9_{rack_name}_{lf['model']}_L0_keen"
        ob = next(o for o in s.sc.collection.objects if o.instance_collection and o.instance_collection.name == cname)
        out.append((ob, lf))
    return out


def anim_kvm(built):
    """A1: the scripted open (CoreTests trajectory), a hold, the scripted close, a hold: stowed at both ends."""
    from . import preview_scripts as PS
    from . import preview_task8 as P8
    clip = "01-kvm"
    if not want("anim-" + clip):
        return
    all_runs = PS.runs()
    op, cl = all_runs["open"], all_runs["close"]
    hold = 0.6
    total = op.duration + hold + cl.duration + hold
    d = _frames_dir(clip)
    sc = PS.Scene(built, op, "3q", res=ANIM_RES)
    for o in sc.s.sc.collection.objects:
        if o.name.startswith("hud"):
            o.hide_render = True
    _anim_samples(sc.s)
    sc.s.camera((-1.05, 2.45, 1.98), (0.02, 0.6, 1.42), 45)
    n = int(round(total * ANIM_FPS))
    for i in range(n):
        t = i / ANIM_FPS
        if t <= op.duration:
            slide, fold = op.at(t)
        elif t <= op.duration + hold:
            slide, fold = op.at(op.duration)
        elif t <= op.duration + hold + cl.duration:
            slide, fold = cl.at(t - op.duration - hold)
        else:
            slide, fold = cl.at(cl.duration)
        md, ms = P8.kvm_part_matrices(sc.base, slide, fold)
        sc.parts[0].matrix_world = md
        sc.parts[1].matrix_world = ms
        _render_frame(sc.s, os.path.join(d, f"f_{i:04d}.png"))
    print(f"SHOWCASE clip {clip}: {n} frames")


def anim_rack_doors(built):
    """A2: the split front doors open to 85 deg and close (linear over 1 s each way), three-quarter front."""
    from . import doors
    from . import preview_p3t7 as P7
    from . import preview_task9 as P9
    from .preview import T
    clip = "02-rack-doors"
    if not want("anim-" + clip):
        return
    s = _studio("anim_" + clip, res=ANIM_RES)
    _anim_samples(s)
    mix = tuple("KVM0" if m == "KVM" else m for m in MIX_SHOW)
    P7.rack_with_strips(s, built, R42, f=0.0, mix=mix)
    leaves = _leaf_objects(s, R42)
    C = T(0, 0, P9._H(R42) / 2)
    s.camera((2.0, 4.3, 1.95), (0.05, 0.15, 1.3), 40)
    d = _frames_dir(clip)
    total = 0.4 + 1.0 + 1.2 + 1.0 + 0.4
    n = int(round(total * ANIM_FPS))
    for i in range(n):
        f = _door_timeline(i / ANIM_FPS)
        for ob, lf in leaves:
            ob.matrix_world = C @ T(lf["axis"][0], lf["axis"][1], 0) @ P9.Rz(doors.swing_yaw(lf, f))
        _render_frame(s, os.path.join(d, f"f_{i:04d}.png"))
    print(f"SHOWCASE clip {clip}: {n} frames")


def anim_contain_door(built):
    """A3: the cold aisle's west door slides open and closed (linear, contain.DOOR_SECONDS), from inside the aisle."""
    from . import catalog, contain, room
    from . import preview_room as PR
    from .preview import T
    clip = "03-containment-door"
    if not want("anim-" + clip):
        return
    s, coll, info = _hall_shot(built, "anim_" + clip, res=ANIM_RES)
    _anim_samples(s)
    door = next(p for p in info["placed"] if p.tag == "west/door")
    spec = catalog.BY_NAME[door.name]
    M = PR._M(door)
    leaves = []
    for lf in contain.door_leaves(spec):
        cname = f"pv9_{door.name}_{lf.model}_L0_keen"
        want_m = M @ T(contain.leaf_centre_x(spec, lf.side, 0.0), 0, contain.LEAF_ORIGIN_Z)
        cands = [o for o in coll.objects if o.instance_collection and o.instance_collection.name == cname]
        ob = min(cands, key=lambda o: (o.matrix_world.translation - want_m.translation).length)
        leaves.append((ob, lf))
    s.camera((2.5, 0.22, 1.62), (-0.1, -0.05, 1.4), 20)
    d = _frames_dir(clip)
    move = contain.DOOR_SECONDS
    total = 0.4 + move + 1.4 + move + 0.4
    n = int(round(total * ANIM_FPS))
    for i in range(n):
        f = _door_timeline(i / ANIM_FPS, 0.4, move, 1.4)
        for ob, lf in leaves:
            ob.matrix_world = M @ T(contain.leaf_centre_x(spec, lf.side, f), 0, contain.LEAF_ORIGIN_Z)
        _render_frame(s, os.path.join(d, f"f_{i:04d}.png"))
    for ob, lf in leaves:
        ob.matrix_world = M @ T(contain.leaf_centre_x(spec, lf.side, 0.0), 0, contain.LEAF_ORIGIN_Z)
    print(f"SHOWCASE clip {clip}: {n} frames")


CRAC_ON, CRAC_END = 0.4, 5.0


def crac_angle(t):
    """(angle deg, omega deg/s, working): switched on at CRAC_ON, the linear InfiniteRotation ramp to FAN_DEG_S at
    FAN_SPEEDUP (the 2 s soft start), then running."""
    from . import crac
    w, up = crac.FAN_DEG_S, crac.FAN_SPEEDUP
    if t < CRAC_ON:
        return 0.0, 0.0, False
    x = t - CRAC_ON
    tr = w / up
    if x < tr:
        return 0.5 * up * x * x, up * x, True
    return 0.5 * up * tr * tr + w * (x - tr), w, True


def anim_crac(built):
    """A4: off, switched on (RUN lamp), the fans' 2 s soft start, running; keyframed so EEVEE blurs each frame by its
    own speed (dc/preview_p3t6.anim's approach)."""
    import bpy
    from . import preview_p3t6 as P6
    from . import preview_task9 as P9
    from .preview import T
    clip = "04-crac-fans"
    if not want("anim-" + clip) or "DC_CRAC" not in built:
        return
    s = _studio("anim_" + clip, res=ANIM_RES)
    _anim_samples(s)
    M = T(0, 0, P6.ZC)
    lit, dark = (s.inst(P9.body(built, P6.NAME, "keen", w), M) for w in (True, False))
    emp = P6._rotors(s, built, M, 0.0)
    for x in (-1.0, 1.0):
        P9.rack(s, built, R42, x=x, f=0.0, mix=tuple("KVM0" if m == "KVM" else m for m in MIX_REAR), working=True)
    s.camera((1.8, 4.2, 2.0), (0.0, 0.2, 1.35), 32)
    sc = s.sc
    for k, v in (("use_motion_blur", True), ("motion_blur_shutter", 0.5)):
        for tgt in (sc.render, sc.eevee):
            try:
                setattr(tgt, k, v)
            except (AttributeError, TypeError):
                pass
    sc.render.fps = ANIM_FPS
    n = int(round(CRAC_END * ANIM_FPS))
    sc.frame_start, sc.frame_end = 1, n
    sc.frame_step = ANIM_STEP
    for f in range(0, n + 2):
        a, _, working = crac_angle(max(0.0, (f - 1) / ANIM_FPS))
        for e, base in emp:
            e.matrix_world = base @ P6._ry(a)
            e.keyframe_insert("rotation_euler", frame=f)
            e.keyframe_insert("location", frame=f)
        lit.hide_render, dark.hide_render = not working, working
        lit.keyframe_insert("hide_render", frame=f)
        dark.keyframe_insert("hide_render", frame=f)
    for e, _ in emp:
        for fc in getattr(e.animation_data.action, "fcurves", []):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    d = _frames_dir(clip)
    sc.render.filepath = os.path.join(d, "f_")
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(animation=True, scene=sc.name)
    # Blender names the frames f_0001..: renumber from 0
    for f in sorted(os.listdir(d)):
        k = int(f[2:6])
        os.rename(os.path.join(d, f), os.path.join(d, f"g_{k - 1:04d}.png"))
    for f in sorted(os.listdir(d)):
        os.rename(os.path.join(d, f), os.path.join(d, "f_" + f[2:]))
    print(f"SHOWCASE clip {clip}: {n} frames")


def anim_orbit(built):
    """A5: one full turn around the loaded 42U split-front rack (doors open, KVM out, strips at the back)."""
    from mathutils import Vector
    from . import preview_p3t7 as P7
    clip = "05-rack-orbit"
    if not want("anim-" + clip):
        return
    s = _studio("anim_" + clip, res=ANIM_RES)
    _anim_samples(s)
    P7.rack_with_strips(s, built, R42, f=1.0, mix=MIX_SHOW)
    tgt = Vector((0.0, 0.0, 1.35))
    s.camera((0, 5.0, 2.0), tuple(tgt), 30)
    d = _frames_dir(clip)
    total = 5.0
    n = int(round(total * ANIM_FPS))
    for i in range(n):
        a = math.radians(30.0 + 360.0 * i / n)
        loc = Vector((5.0 * math.sin(a), 5.0 * math.cos(a), 2.1))
        s.cam.location = loc
        s.cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
        _render_frame(s, os.path.join(d, f"f_{i:04d}.png"))
    print(f"SHOWCASE clip {clip}: {n} frames")


def anim_dolly(built):
    """A6: a slow walk into the contained cold aisle and back (eased, so the loop is seamless), rack doors shut."""
    from mathutils import Vector
    clip = "06-aisle-dolly"
    if not want("anim-" + clip):
        return
    s, coll, info = _hall_shot(built, "anim_" + clip, res=ANIM_RES)
    _anim_samples(s)
    s.camera((0.3, -0.3, 1.6), (4.0, 0.2, 1.5), 16)
    d = _frames_dir(clip)
    total = 5.0
    n = int(round(total * ANIM_FPS))
    for i in range(n):
        u = i / n
        k = _ease(2 * u) if u < 0.5 else _ease(2 - 2 * u)
        x = 0.3 + 2.0 * k
        loc = Vector((x, -0.12, 1.6))
        tgt = Vector((x + 3.7, 0.05, 1.5))
        s.cam.location = loc
        s.cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
        _render_frame(s, os.path.join(d, f"f_{i:04d}.png"))
    print(f"SHOWCASE clip {clip}: {n} frames")


def anims(built):
    anim_kvm(built)
    anim_rack_doors(built)
    anim_crac(built)
    anim_orbit(built)
    anim_contain_door(built)
    anim_dolly(built)


def render_all(built):
    from . import preview as PV
    PV.OUT = OUT
    os.makedirs(OUT, exist_ok=True)
    if not os.environ.get("DC_SHOWCASE_NO_STILLS"):
        stills(built)
    if not os.environ.get("DC_SHOWCASE_NO_ANIM"):
        anims(built)


# ---------------------------------------------------------------------------------------------------- web copies
def _ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def web():
    """Shareable copies (plain Python: ffmpeg + Pillow): the stills as 1920 px JPEG q90 in img/, the clips as GIF
    (800-960 px, under GIF_MAX, looping) + H.264 MP4 + poster JPEG in anim/, all under descriptive names, and
    shots.json with the titles and captions."""
    from PIL import Image
    img, anim = (os.path.join(WEB, d) for d in ("img", "anim"))
    for d in (img, anim):
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(d):                     # this set owns these folders: no stale names
            os.remove(os.path.join(d, f))
    shots = []
    for slug, title, caption in SHOTS:
        src = os.path.join(OUT, slug + ".png")
        if not os.path.exists(src):
            print("missing still", slug)
            continue
        name = WEB_NAMES[slug]
        im = Image.open(src).convert("RGB")
        if im.width != 1920:
            im = im.resize((1920, round(im.height * 1920 / im.width)), Image.LANCZOS)
        im.save(os.path.join(img, name + ".jpg"), quality=90, optimize=True, progressive=True)
        shots.append({"file": f"img/{name}.jpg", "title": title, "caption": caption})
    anims_out = []
    for slug, title, caption in ANIMS:
        fr = os.path.join(OUT, "anim", slug)
        pattern = os.path.join(fr, "f_%04d.png")
        if not os.path.exists(pattern % 0):
            print("missing clip", slug)
            continue
        name = WEB_NAMES[slug]
        gif, mp4, poster = (os.path.join(anim, name + e) for e in (".gif", ".mp4", ".jpg"))
        _ff("-framerate", str(ANIM_FPS), "-i", pattern, "-vf", "scale=1280:-2:flags=lanczos", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "slow", "-movflags", "+faststart", mp4)
        speed = f"setpts=PTS/{GIF_SPEED[slug]}," if slug in GIF_SPEED else ""
        for gw, gfps, colours, dither in GIF_LADDER:   # the first rung under the budget
            _ff("-framerate", str(ANIM_FPS), "-i", pattern, "-vf",
                f"{speed}fps={gfps},scale={gw}:-1:flags=lanczos,split[a][b];"
                f"[a]palettegen=max_colors={colours}:stats_mode=diff[p];"
                f"[b][p]paletteuse=dither={dither}:diff_mode=rectangle", "-loop", "0", gif)
            if os.path.getsize(gif) <= GIF_MAX:
                break
        else:
            print(f"{slug}: GIF over budget at the last rung")
        frames = sorted(f for f in os.listdir(fr) if f.endswith(".png"))
        pick = POSTER.get(slug, 0.5)
        im = Image.open(os.path.join(fr, frames[int(pick * (len(frames) - 1))])).convert("RGB")
        im.save(poster, quality=90, optimize=True)
        anims_out.append({"gif": f"anim/{name}.gif", "mp4": f"anim/{name}.mp4", "poster": f"anim/{name}.jpg",
                          "title": title, "caption": caption})
        print(f"{name}: gif {os.path.getsize(gif) / 1e6:.2f} MB ({gw} px, {gfps} fps, {colours} colours), "
              f"mp4 {os.path.getsize(mp4) / 1e6:.2f} MB")
    with open(os.path.join(WEB, "shots.json"), "w") as fh:
        json.dump({"shots": shots, "anims": anims_out}, fh, indent=2)
        fh.write("\n")
    print("WROTE", os.path.join(WEB, "shots.json"))


WEB_NAMES = {
    "01-cold-aisle": "datacenter-cold-aisle", "02-hall-overhead": "datacenter-hall-overhead",
    "03-containment-doors": "containment-doors-and-aisle-signs", "04-rack-front": "rack-42u-front-loaded",
    "05-rack-rear": "rack-42u-rear-power-strips", "06-kvm-open": "kvm-console-open",
    "07-server-lineup": "server-lineup", "08-cable-trays": "overhead-cable-trays",
    "09-crac-front": "in-row-cooler-front", "10-crac-rear": "in-row-cooler-rear",
    "11-pdu-cabinet": "power-distribution-cabinet", "12-raised-floor": "raised-floor",
    "13-signs": "aisle-signs-and-rack-labels", "14-damage": "server-damage", "15-half-racks": "half-racks-24u",
    "16-cold-aisle-black": "datacenter-cold-aisle-black-racks",
    "01-kvm": "kvm-drawer", "02-rack-doors": "rack-doors", "03-containment-door": "containment-door",
    "04-crac-fans": "cooler-fans-spin-up", "05-rack-orbit": "rack-42u-turntable", "06-aisle-dolly": "cold-aisle-walk",
}


GIF_MAX = 7_900_000
GIF_SPEED = {"06-aisle-dolly": 1.25}   # the walk's GIF plays 1.25x (4 s): every frame is new, 5 s will not fit 8 MB
# GIF rungs, best first, never under 800 px: the camera moves in the turntable and the walk, so every frame is new
# and they need the lower rungs (the grey hall survives 64 colours undithered)
GIF_LADDER = ((960, 15, 256, "sierra2_4a"), (900, 15, 256, "sierra2_4a"), (800, 15, 256, "sierra2_4a"),
              (800, 15, 128, "none"), (800, 12, 64, "none"), (800, 10, 64, "none"), (800, 10, 48, "none"))
POSTER = {"01-kvm": 0.33, "02-rack-doors": 0.45, "03-containment-door": 0.45, "04-crac-fans": 0.9,
          "05-rack-orbit": 0.0, "06-aisle-dolly": 0.3}


if __name__ == "__main__":
    import sys
    if "web" in sys.argv[1:]:
        web()
    if shutil.which("ffmpeg") is None:
        print("ffmpeg not found")
