"""Icon renders: the build-menu icons (Source/Model/UI/<name>_Icon.png), one store preview per block
(preview/blocks/<name>.png), the hero shots (preview/hero/) and the working set (preview/icons/).

Same models, placement helpers and material stand-ins as the other preview sets (dc/preview*.py): racks with their door leaves
at the game's SLERP pose, tray fans, servers with their default indicator states, the KVM drawer and screen at the
animation pose, the UPS with vanilla Power Cells (read-only import).

ICONS follow the vanilla build-menu icons (tools/vanilla-ref/Blocks/**/<name>_Icon.png, 200 x 200 RGBA):
  * transparent background, the block alone in the default (Keen grey) paint, emissives lit;
  * a 3/4 view from front-left-above (the working face on the left, the block's left side on the right), mild
    perspective (70 mm), ~25 deg elevation;
  * neutral studio light: a large key from the upper left, a soft fill, a top light and a cool rim for the edges;
  * the subject fills ~78 % of the frame; a family shares one camera distance so relative size reads (a 24U rack is
    visibly half a 42U one; the 12U UPS is twice a 6U server), each centred on its own bounds.
  * Variants read at a glance: Open = no doors, the empty slots show through; Split Front = closed perforated front
    doors; Front + Rear = the front doors swung open and the closed rear door visible through the empty slots.
    Servers: a more frontal view so the face (their only difference) is large.

HERO shots use a dark data-hall rig (`Mood`): a dark raised floor of 0.5 m tiles, perforated cold-aisle tiles over
a faint blue plenum glow, ceiling light strips (visible fixtures + rectangular area lights), dark walls, and a low
front fill so faces stay readable. Racks are painted black (the reference look), servers keep the default paint.

    DC_PREVIEW=icons blender -b --python Source/Model/build_dc.py -- all
    DC_PREVIEW=icons blender -b --python Source/Model/build_dc.py -- "DC_Tray*"   (tray icons + shots)
    DC_PREVIEW=icons DC_ICONS_PART=icons blender -b --python Source/Model/build_dc.py -- "DC_Floor_*" DC_CRAC \
        "DC_PDU_*" "DC_Contain_*" "DC_Sign_*"                                        (room icons)
(DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution for the preview shots, icons always full size).
"""
import math
import os

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

from . import catalog, config, doors
from . import preview as PV
from . import preview_mats as PM
from . import preview_rack_doors as pv_rack_doors
from .preview import Rz, Shot, T, want

ICON_DIR = os.path.join(config.HERE, "UI")
OUT = os.path.join(config.PREVIEW_DIR, "icons")
BLOCKS_DIR = os.path.join(config.PREVIEW_DIR, "blocks")
HERO_DIR = os.path.join(config.PREVIEW_DIR, "hero")
SERVERS = ("DC_Srv_Timer", "DC_Srv_EventCtl", "DC_Srv_KVM", "DC_Srv_Status", "DC_Srv_UPS", "DC_Srv_Programmable",
           "DC_Srv_Compute", "DC_Srv_Storage", "DC_Srv_Switch", "DC_Srv_Blank")
SHORT = {"DC_Srv_Timer": "TIMER", "DC_Srv_EventCtl": "EVENT CONTROLLER", "DC_Srv_KVM": "KVM CONSOLE",
         "DC_Srv_Status": "STATUS DISPLAY", "DC_Srv_UPS": "UPS 12U", "DC_Srv_Programmable": "PROGRAMMABLE",
         "DC_Srv_Compute": "COMPUTE", "DC_Srv_Storage": "STORAGE", "DC_Srv_Switch": "NETWORK SWITCH",
         "DC_Srv_Blank": "BLANKING PANEL"}
# pv_rack_doors mix tokens for the special servers
TOKEN = {"DC_Srv_UPS": "UPS", "DC_Srv_KVM": "KVM", "DC_Srv_Programmable": "PROG"}
# icon mixes: sparse, so the slots show what is behind them (nothing / the rear door)
ICON_MIX42 = ("DC_Srv_Storage", "DC_Srv_Compute", None, "DC_Srv_Switch", None, "DC_Srv_Timer", None, "DC_Srv_Storage")
ICON_MIX24 = ("DC_Srv_Storage", None, "DC_Srv_Switch", None)


def _o(name):
    return os.path.join(OUT, name)


def tok(n):
    return TOKEN.get(n, n)


# ------------------------------------------------------------------------------------------------ placing blocks
def rack(s, built, name, x=0.0, y=0.0, rot=0.0, f=0.0, f_rear=None, paint="black", srv_paint="keen", mix=(),
         fan=0.0, working=None, kvm_f=1.0):
    """A rack (doors at f / f_rear, pv_rack_doors pose) with its servers from slot 1 up in their own paint. A KVM behind
    closed front doors is shown stowed (switched Off): Working it would pop through the leaves (in-game checklist)."""
    M = pv_rack_doors.rack(s, built, name, x, y, rot, f=f, paint=paint, mix=(), fan=fan, working=working, f_rear=f_rear)
    spec = catalog.BY_NAME[name]
    for k, n in enumerate(mix, 1):
        if not n:
            continue
        n = tok(n)
        if n == "KVM" and (kvm_f < 1.0 or (doors.door_sides(spec) and f < 1.0)):
            n = "KVM0"
        pv_rack_doors.srv(s, built, n, M, 0.25 * k, srv_paint)
    return M


def server(s, built, name, x=0.0, y=0.0, z=0.0, rot=0.0, paint="keen", kvm_f=1.0):
    n = tok(name)
    if n == "KVM" and kvm_f < 1.0:
        n = "KVM0"
    pv_rack_doors.srv(s, built, n, T(x, y, 0) @ Rz(rot), z, paint)


# ------------------------------------------------------------------------------------------------ bounds / fit
def scene_bounds(sc, skip=("floor",)):
    pts = []
    for e in sc.collection.all_objects:
        if e.name.split(".")[0] in skip or e.name.startswith(("mood_", "cap")):
            continue
        if e.instance_type == "COLLECTION" and e.instance_collection:
            for o in e.instance_collection.all_objects:
                if o.type == "MESH":
                    pts += [e.matrix_world @ o.matrix_world @ Vector(c) for c in o.bound_box]
        elif e.type == "MESH":
            pts += [e.matrix_world @ Vector(c) for c in e.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def corners(lo, hi):
    return [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]


def project(sc, cam, pts):
    sc.view_layers[0].update()
    cam.data.shift_x = cam.data.shift_y = 0.0
    p = [world_to_camera_view(sc, cam, q) for q in pts]
    return min(q.x for q in p), max(q.x for q in p), min(q.y for q in p), max(q.y for q in p)


def aim(cam, target, direction, dist):
    d = Vector(direction).normalized()
    cam.location = Vector(target) + d * dist
    q = (-d).to_track_quat("-Z", "Y")
    cam.rotation_euler = q.to_euler()
    cam.matrix_world = Matrix.Translation(cam.location) @ q.to_matrix().to_4x4()   # icon scenes are not active


def fit_distance(sc, cam, lo, hi, direction, fill):
    """Camera distance along direction at which the bounds' larger projected extent spans `fill` of the frame."""
    tgt = (lo + hi) / 2
    dist = 3.0 * (hi - lo).length
    for _ in range(6):
        aim(cam, tgt, direction, dist)
        x0, x1, y0, y1 = project(sc, cam, corners(lo, hi))
        span = max(x1 - x0, y1 - y0)
        dist *= span / fill
    return dist


def centre(sc, cam, lo, hi):
    """Lens shift that centres the bounds' projection (the view direction is unchanged)."""
    x0, x1, y0, y1 = project(sc, cam, corners(lo, hi))
    cam.data.shift_x = (x0 + x1) / 2 - 0.5
    cam.data.shift_y = (y0 + y1) / 2 - 0.5


# ------------------------------------------------------------------------------------------------ icons
ICON_DIR_RACK = (-0.58, 0.82, 0.52)       # front-left-above (Blender +Y = the block's front)
ICON_DIR_SERVER = (-0.34, 0.92, 0.25)     # more frontal: a server's face is what tells it apart
ICON_FILL = 0.80
ICON_LENS = 70


class Icon:
    """A transparent 200 x 200 icon scene with the vanilla-like studio light."""

    def __init__(self, name, size=200):
        self.name = name
        sc = bpy.data.scenes.new("icon_" + name)
        self.sc = sc
        r = sc.render
        r.resolution_x = r.resolution_y = size
        r.resolution_percentage = 100
        r.film_transparent = True
        r.filter_size = 1.2
        r.engine = "BLENDER_EEVEE"
        for k, v in (("taa_render_samples", 96), ("use_raytracing", True), ("use_shadows", True),
                     ("use_gtao", True), ("fast_gi_method", "GLOBAL_ILLUMINATION")):
            try:
                setattr(sc.eevee, k, v)
            except Exception:
                pass
        try:
            sc.view_settings.view_transform = "AgX"
            sc.view_settings.look = "AgX - Medium High Contrast"
            sc.view_settings.exposure = -0.55     # vanilla icons: mid-grey paint, dark recesses, crisp highlights
        except Exception:
            pass
        r.image_settings.file_format = "PNG"
        r.image_settings.color_mode = "RGBA"
        r.image_settings.color_depth = "8"
        for a in [a for a in dir(r) if a.startswith("use_stamp")]:
            try:
                setattr(r, a, False)
            except (AttributeError, TypeError):
                pass
        w = bpy.data.worlds.new("W_icon_" + name)
        sc.world = w
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.30, 0.31, 0.33, 1)
        w.node_tree.nodes["Background"].inputs[1].default_value = 0.30
        cam = bpy.data.objects.new("cam_icon_" + name, bpy.data.cameras.new("cam_icon_" + name))
        cam.data.lens = ICON_LENS
        cam.data.clip_start, cam.data.clip_end = 0.02, 200
        sc.collection.objects.link(cam)
        sc.camera = self.cam = cam

    def inst(self, coll, m):
        e = bpy.data.objects.new("i_" + coll.name, None)
        e.instance_type = "COLLECTION"
        e.instance_collection = coll
        e.matrix_world = m
        self.sc.collection.objects.link(e)
        return e

    def link(self, ob):
        self.sc.collection.objects.link(ob)
        return ob

    def lights(self, tgt, scale):
        """Key upper-left (camera side), fill right, top, cool rim from behind: all aimed at the subject."""
        cd = (self.cam.location - Vector(tgt)).normalized()
        right = cd.cross(Vector((0, 0, 1))).normalized()
        for nm, off, e, sz, col in (("key", -1.1 * right + 0.6 * cd + Vector((0, 0, 0.9)), 420, 2.0, (1.0, 0.98, 0.95)),
                                    ("fill", 1.2 * right + 0.8 * cd + Vector((0, 0, 0.1)), 60, 3.5, (0.92, 0.95, 1.0)),
                                    ("top", Vector((0, 0, 1.6)), 35, 3.0, (1, 1, 1)),
                                    ("rim", -1.3 * cd + 0.4 * right + Vector((0, 0, 0.9)), 380, 2.0, (0.85, 0.92, 1.0))):
            ld = bpy.data.lights.new(f"{self.name}_{nm}", "AREA")
            ld.energy, ld.size, ld.color = e * scale * scale, sz * scale, col
            o = bpy.data.objects.new(ld.name, ld)
            o.location = Vector(tgt) + off * 2.2 * scale
            o.rotation_euler = (Vector(tgt) - o.location).to_track_quat("-Z", "Y").to_euler()
            self.sc.collection.objects.link(o)

    def render(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.sc.render.filepath = path
        bpy.ops.render.render(write_still=True, scene=self.sc.name)
        print("WROTE", path)
        return path


def _icon_subject(built, name, s):
    spec = catalog.BY_NAME[name]
    if spec.family == "rack":
        mix = ICON_MIX42 if spec.cells[1] == 10 else ICON_MIX24
        if spec.variant == "Open":
            rack(s, built, name, paint="keen", mix=mix, fan=20, working=True)
        elif spec.variant == "SplitFront":
            rack(s, built, name, f=0.0, paint="keen", mix=mix, fan=20, working=True)
        else:   # front doors open, rear doors closed: the rear door shows through the empty slots
            rack(s, built, name, f=1.0, f_rear=0.0, paint="keen", mix=mix, fan=20, working=True)
    else:
        server(s, built, name, kvm_f=1.0)


ICON_FILLS = {"DC_Rack24": 0.70, "DC_Rack42": 0.86, "DC_Srv_UPS": 0.84}   # else (6U servers) ICON_FILL

# Cable trays. The vanilla framing (3/4 from front-left, the same lens, light and exposure), but from
# higher up for the routing pieces (about 45 deg instead of 30): the open basket is what tells a tray apart, so the
# camera looks into it and the cable load reads (Empty: bare mesh; Low: two blue data bundles; Moderate: + the yellow
# fibre and the grey power; Full: + the second layer, blue data and black power). The data cables take the block
# paint, so icons show them in the blue preview paint, as vanilla icons show a coloured accent; the
# basket stays galvanised steel. Supports (rods, chute) are tall and slim: the rack view.
ICON_DIR_TRAY = (-0.50, 0.66, 0.78)
# straight-type pieces (one long axis along x) are seen more along their run, as vanilla draws its conveyor straights
# receding from the front-left: the piece stays compact in the frame instead of a thin diagonal, and the mesh and the
# cables read denser; the rod hangers from the side, so their two rods stand apart instead of overlapping
ICON_DIR_RUN = (-0.74, 0.42, 0.70)
ICON_DIR_RODS = (-0.86, 0.38, 0.34)
RUN_SHAPES = ("StraightS", "StraightL", "Reducer", "Drop")
TRAY_ICON_PAINT = "blue"
# each piece is fitted to its own bounds; the short pieces (0.5 m) are drawn smaller, as the 24U rack, so a short and
# a long straight differ in size as well as proportion; the rods by length (three sizes of one kind)
TRAY_FILLS = {"StraightS": 0.70, "Reducer": 0.74, "StraightL": 0.92, "TurnH": 0.86, "TurnUp": 0.82,
              "TurnDown": 0.80, "Tee": 0.90, "Cross": 0.90, "Drop": 0.90, "Chute": 0.86,
              "DC_TrayRods_025": 0.50, "DC_TrayRods_100": 0.76, "DC_TrayRods_200": 0.90}


ROD_ICON_EXPOSURE = 0.6    # the rod hangers' icons (the core rig's -0.55 leaves 5 mm rods as hairlines at 64 px)


# Room pieces: the same rig. Floor tiles and roof panels are seen 3/4 from above (their top is what
# tells Solid from Perforated and shows the roof's frosted panes and LED batten); the in-row units (CRAC, PDU cabinet)
# as the racks; the containment doors front 3/4 with the leaves half open (the slide and the pockets read); the rack
# PDU strips from the rear (their outlets, cords and bank meters face the rack's rear door); the signs nearly
# frontal with sample text on the screen (in game the player types it). Sizes of one kind are drawn at different
# fills, as the 24U / 42U racks: a 0.5 m tile smaller than a 1.0 m one, a 1.0 m roof or door smaller than a 2.0 m one.
ICON_DIR_FLOOR = (-0.52, 0.62, 0.86)
ICON_DIR_DOOR = (-0.44, 0.86, 0.32)
ICON_DIR_STRIP = (-0.50, -0.84, 0.38)    # from behind: the strip's outlets face -Y (the rack's rear)
ICON_DIR_SIGN = (-0.36, 0.90, 0.26)
ROOM_FILLS = {"DC_Floor_Solid_050": 0.66, "DC_Floor_Perf_050": 0.66, "DC_Floor_Solid_100": 0.90,
              "DC_Floor_Perf_100": 0.90, "DC_CRAC": 0.86, "DC_PDU_Cabinet": 0.86,
              "DC_PDU_Rack42_A": 0.95, "DC_PDU_Rack42_B": 0.95, "DC_PDU_Rack24_A": 0.76, "DC_PDU_Rack24_B": 0.76,
              "DC_Contain_Door_100": 0.80, "DC_Contain_Door_150": 0.86, "DC_Contain_Door_200": 0.92,
              "DC_Contain_Roof_100": 0.72, "DC_Contain_Roof_150": 0.82, "DC_Contain_Roof_200": 0.92,
              "DC_Sign_Aisle": 0.90, "DC_Sign_AisleHang": 0.88, "DC_Sign_Rack": 0.70}
ROOM_ICON_DIR = {"floor": ICON_DIR_FLOOR, "contain_roof": ICON_DIR_FLOOR, "crac": ICON_DIR_RACK,
                 "pdu_cabinet": ICON_DIR_RACK, "pdu_strip": ICON_DIR_STRIP, "contain_door": ICON_DIR_DOOR,
                 "sign": ICON_DIR_SIGN}
DOOR_ICON_OPEN = 0.5          # the leaves half open
STRIP_ICON_LEAN = -38.0       # deg about the strip's depth axis: it reads as a long strip, its outlets large
ROOF_ICON_EXPOSURE = -1.25    # the frosted panes are near-white: the core rig's -0.55 washes the mullions out
SIGN_ICON_TEXT = {"DC_Sign_Aisle": "AISLE 1 COLD", "DC_Sign_AisleHang": "AISLE 1 COLD", "DC_Sign_Rack": "RACK 1.01"}


def _room_icon_subject(built, name, s):
    """A room piece in the icon scene at its cell-box centre, in the default paint, working (lamps and LEDs lit)."""
    from . import preview_room as PR
    spec = catalog.BY_NAME[name]
    M = Matrix.Identity(4)
    if spec.family == "contain_door":
        PR.contain_door(s, built, name, M, f=DOOR_ICON_OPEN, paint="keen")
    elif spec.family == "crac":
        PR.crac_unit(s, built, name, M, angle=17.0, working=True, paint="keen")
    elif spec.family == "sign":
        from . import preview_signs as pv_signs
        pv_signs.place(s, built, name, M, paint="keen", text=SIGN_ICON_TEXT[name])
    elif spec.family == "pdu_strip":   # leaned across the tile (a 0.25 x 2 m strip upright is a hairline at 64 px)
        s.inst(PV.painted(built, name, 0, "keen"), Matrix.Rotation(math.radians(STRIP_ICON_LEAN), 4, "Y"))
    else:
        s.inst(PV.painted(built, name, 0, "keen"), M)


def _icon_frame(b):
    """(view direction, fill) of a block's icon."""
    if b.family in ROOM_ICON_DIR:
        return ROOM_ICON_DIR[b.family], ROOM_FILLS[b.name]
    if b.family == "rack":
        return ICON_DIR_RACK, next(v for k, v in ICON_FILLS.items() if b.name.startswith(k))
    if b.family == "server":
        return ICON_DIR_SERVER, ICON_FILLS.get(b.name, ICON_FILL)
    if b.family == "trayrods":
        return ICON_DIR_RODS, TRAY_FILLS[b.name]
    if b.variant == "Chute":
        return ICON_DIR_RACK, TRAY_FILLS[b.variant]
    return (ICON_DIR_RUN if b.variant in RUN_SHAPES else ICON_DIR_TRAY), TRAY_FILLS[b.variant]


def icons(built):
    """One icon per built catalogue block, each fitted to its own bounds: the larger projected extent spans its fill
    of the frame (a 24U rack is drawn smaller than a 42U one, as vanilla draws Battery50 smaller than Battery250)."""
    for b in catalog.BLOCKS:
        if b.name not in built or not want("icon_" + b.name):
            continue
        s = Icon(b.name)
        if b.family in ("tray", "trayrods"):
            s.inst(PV.painted(built, b.name, 0, TRAY_ICON_PAINT), Matrix.Identity(4))
        elif b.family in ROOM_ICON_DIR:
            _room_icon_subject(built, b.name, s)
        else:
            _icon_subject(built, b.name, s)
        lo, hi = scene_bounds(s.sc)
        d, fill = _icon_frame(b)
        dd = fit_distance(s.sc, s.cam, lo, hi, d, fill)
        aim(s.cam, (lo + hi) / 2, d, dd)
        centre(s.sc, s.cam, lo, hi)
        s.lights((lo + hi) / 2, max(1.0, (hi - lo).length / 2.2))
        if b.family == "trayrods":     # thin rods: brighter, so the pair reads on the dark tile
            s.sc.view_settings.exposure = ROD_ICON_EXPOSURE
        if b.family == "contain_roof":
            s.sc.view_settings.exposure = ROOF_ICON_EXPOSURE
        s.render(os.path.join(ICON_DIR, f"{b.name}_Icon.png"))


# ------------------------------------------------------------------------------------------------ mood rig
def _mat(name, col, rough=0.5, metal=0.0, emit=None, estr=0.0):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    return PM.simple(name, col, rough, metal, emit=emit, estr=estr)


class Mood(Shot):
    """A dark data hall: Shot without its studio lights or grid floor, plus the room."""

    def __init__(self, name, res=(2400, 1350), room=(-2.0, 6.0, -1.5, 4.5), ceiling=3.3, strips=(),
                 walls=True, fill=1.0, plenum=None, ceiling_visible=True, world=(0.004, 0.0045, 0.006)):
        super().__init__(name, res=res, floor=None, world=world, light=1.0)
        for o in list(self.sc.collection.objects):
            if o.type == "LIGHT":
                bpy.data.objects.remove(o)
        sc = self.sc
        try:
            sc.view_settings.look = "AgX - Medium High Contrast"
        except Exception:
            pass
        try:
            sc.eevee.shadow_pool_size = "1024"
        except Exception:
            pass
        self.room = room
        x0, x1, y0, y1 = room
        self.floor(x0, x1, y0, y1, plenum)
        if walls:
            self.walls(x0, x1, y0, y1, ceiling)
        if ceiling_visible:
            self.ceiling(x0, x1, y0, y1, ceiling)
        for st in strips:
            self.strip(*st, z=ceiling)
        # low front fill (camera side) and a soft overhead wash so the faces stay readable
        self.fill_level = fill

    # -------------------------------------------------------------------------------------------- room parts
    def _box(self, bm, lo, hi, mi=0):
        vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
        bmesh.ops.scale(bm, vec=Vector(hi) - Vector(lo), verts=vs)
        bmesh.ops.translate(bm, vec=(Vector(lo) + Vector(hi)) / 2, verts=vs)
        for fc in {fc for v in vs for fc in v.link_faces}:
            fc.material_index = mi

    def _obj(self, name, bm, mats, uv_scale=None):
        me = bpy.data.meshes.new(name)
        if uv_scale:
            uv = bm.loops.layers.uv.new()
            for fc in bm.faces:
                for lp in fc.loops:
                    lp[uv].uv = (lp.vert.co.x / uv_scale, lp.vert.co.y / uv_scale)
        bm.to_mesh(me)
        for m in mats:
            me.materials.append(m)
        return self.link(bpy.data.objects.new(name, me))

    def floor(self, x0, x1, y0, y1, plenum):
        """0.5 m raised-floor tiles with 6 mm dark joints; tiles inside `plenum` (x0, x1, y0, y1) are perforated
        cold-aisle tiles over a faint blue glow."""
        tile = _mat("mood_tile", (0.022, 0.023, 0.027), 0.42, 0.3)
        joint = _mat("mood_joint", (0.005, 0.005, 0.006), 0.8)
        perf = bpy.data.materials.get("mood_floor_perf")
        if not perf:   # the doors' perforation, darkened for a floor tile: the plenum glow shows through the holes
            perf = PM.get("Perf").copy()
            perf.name = "mood_floor_perf"
            nt = perf.node_tree
            bsdf = nt.nodes["Principled BSDF"]
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
            mix.inputs[0].default_value = 1.0
            mix.inputs[7].default_value = (0.25, 0.26, 0.28, 1)
            src = bsdf.inputs["Base Color"].links[0].from_socket
            nt.links.new(src, mix.inputs[6])
            nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
        bm, bp = bmesh.new(), bmesh.new()
        step = 0.5
        x = x0
        while x < x1 - 1e-6:
            y = y0
            while y < y1 - 1e-6:
                c = (x + step / 2, y + step / 2)
                inside = plenum and plenum[0] <= c[0] <= plenum[1] and plenum[2] <= c[1] <= plenum[3]
                self._box(bp if inside else bm, (x + 0.003, y + 0.003, -0.012), (x + step - 0.003, y + step - 0.003,
                                                                                  0.0), 0)
                y += step
            x += step
        self._box(bm, (x0, y0, -0.03), (x1, y1, -0.012), 1)
        self._obj("mood_floor", bm, [tile, joint])
        if plenum:
            self._obj("mood_perf", bp, [perf], uv_scale=0.75)
            glow = _mat("mood_plenum", (0.0, 0.0, 0.0), 1.0, 0.0, emit=(0.06, 0.28, 1.0), estr=1.4)
            b2 = bmesh.new()
            self._box(b2, (plenum[0], plenum[2], -0.0118), (plenum[1], plenum[3], -0.0112), 0)   # inside the perf tiles
            self._obj("mood_glow", b2, [glow])
            # the cold air: a faint blue uplight through the tiles
            ld = bpy.data.lights.new(self.name + "_plenum", "AREA")
            ld.shape, ld.size, ld.size_y = "RECTANGLE", plenum[1] - plenum[0], plenum[3] - plenum[2]
            ld.energy, ld.color = 8 * (plenum[1] - plenum[0]) * (plenum[3] - plenum[2]), (0.35, 0.6, 1.0)
            o = bpy.data.objects.new("mood_plenum_light", ld)
            o.location = ((plenum[0] + plenum[1]) / 2, (plenum[2] + plenum[3]) / 2, -0.05)
            o.rotation_euler = (math.pi, 0, 0)   # facing up
            self.link(o)

    def walls(self, x0, x1, y0, y1, h):
        wall = _mat("mood_wall", (0.011, 0.012, 0.014), 0.65, 0.2)
        seam = _mat("mood_seam", (0.008, 0.008, 0.009), 0.8)
        bm = bmesh.new()
        for (a, b, c, d) in ((x0 - 0.1, x1 + 0.1, y0 - 0.1, y0), (x0 - 0.1, x1 + 0.1, y1, y1 + 0.1),
                             (x0 - 0.1, x0, y0, y1), (x1, x1 + 0.1, y0, y1)):
            self._box(bm, (a, c, 0), (b, d, h), 0)
        # vertical panel seams every 1.25 m and a skirting band
        x = x0
        while x <= x1:
            for yy in (y0 + 0.001, y1 - 0.011):
                self._box(bm, (x - 0.006, yy, 0), (x + 0.006, yy + 0.01, h), 1)
            x += 1.25
        for (yy, d) in ((y0, 0.012), (y1 - 0.012, 0.012)):
            self._box(bm, (x0, yy, 0), (x1, yy + d, 0.12), 1)
        self._obj("mood_walls", bm, [wall, seam])

    def ceiling(self, x0, x1, y0, y1, h):
        bm = bmesh.new()
        self._box(bm, (x0 - 0.1, y0 - 0.1, h), (x1 + 0.1, y1 + 0.1, h + 0.05), 0)
        self._obj("mood_ceiling", bm, [_mat("mood_ceil", (0.02, 0.021, 0.024), 0.7)])

    def strip(self, xa, xb, y, z, energy=80, col=(0.86, 0.93, 1.0), w=0.12):
        """A ceiling light strip from xa to xb at y: a visible fixture (housing + emissive diffuser) and a
        rectangular area light just below it."""
        fx = _mat("mood_fixture", (0.05, 0.05, 0.055), 0.4, 0.6)
        diff = _mat("mood_diffuser", (0.9, 0.95, 1.0), 0.3, 0.0, emit=col, estr=14.0)
        bm = bmesh.new()
        self._box(bm, (xa, y - w, z - 0.07), (xb, y + w, z), 0)
        self._box(bm, (xa + 0.03, y - w + 0.025, z - 0.075), (xb - 0.03, y + w - 0.025, z - 0.07), 1)
        self._obj("mood_strip", bm, [fx, diff])
        ld = bpy.data.lights.new(self.name + "_strip", "AREA")
        ld.shape, ld.size, ld.size_y = "RECTANGLE", xb - xa, 2 * w
        ld.energy, ld.color = energy * (xb - xa), col
        o = bpy.data.objects.new("mood_strip_light", ld)
        o.location = ((xa + xb) / 2, y, z - 0.08)
        self.link(o)   # area lights face -Z by default: straight down

    def soft(self, loc, target, energy, size=4.0, col=(0.9, 0.94, 1.0), name="fill"):
        ld = bpy.data.lights.new(f"{self.name}_{name}", "AREA")
        ld.energy, ld.size, ld.color = energy * self.fill_level, size, col
        o = bpy.data.objects.new("mood_" + name, ld)
        o.location = loc
        o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return self.link(o)

    def dof(self, focus, fstop=2.8):
        self.cam.data.dof.use_dof = True
        self.cam.data.dof.focus_distance = (Vector(focus) - self.cam.location).length
        self.cam.data.dof.aperture_fstop = fstop


def _hero(s):
    PV.OUT = HERO_DIR
    return s.render()


# ------------------------------------------------------------------------------------------------ hero shots
MIX_KVM = ("UPS", None, "DC_Srv_Storage", "DC_Srv_Timer", "KVM", "DC_Srv_Compute", "DC_Srv_Status", "PROG")
MIX_DENSE = ("DC_Srv_Storage", "DC_Srv_Compute", "DC_Srv_Storage", "DC_Srv_Switch", "DC_Srv_Status",
             "DC_Srv_Compute", "DC_Srv_Storage", "DC_Srv_Blank")
MIX_OPEN = ("DC_Srv_Storage", "DC_Srv_Storage", "DC_Srv_Compute", "DC_Srv_Switch", "DC_Srv_EventCtl", "DC_Srv_Blank",
            "DC_Srv_Compute", "DC_Srv_Switch")
MIX_UPS = ("DC_Srv_Compute", "UPS", None, "DC_Srv_Storage", "DC_Srv_EventCtl", "DC_Srv_Switch", "DC_Srv_Timer",
           "DC_Srv_Storage")
ROW_A = (  # (rack, f, mix): the left row in the aisle shot (faces +Y)
    ("DC_Rack42_SplitFrontRear", 0.0, MIX_DENSE),
    ("DC_Rack42_SplitFront", 1.0, MIX_KVM),
    ("DC_Rack24_Open", 0.0, ("UPS", None, "DC_Srv_Switch", "DC_Srv_Status")),
)
ROW_B = (  # the right row (faces -Y across the cold aisle)
    ("DC_Rack42_Open", 0.0, MIX_OPEN),
    ("DC_Rack24_SplitFrontRear", 0.0, ("DC_Srv_Switch", "DC_Srv_Compute", "DC_Srv_Timer", "DC_Srv_Storage")),
    ("DC_Rack42_SplitFront", 1.0, MIX_UPS),
)
AISLE_Y = 2.75     # row B's rack centre line: a 1.5 m cold aisle between the door planes (0.625 .. 2.125)


def aisle_scene(built, name, res=(2600, 1400)):
    s = Mood(name, res=res, room=(-6.0, 5.0, -1.75, 4.5), plenum=(-6.0, 5.0, 0.75, 2.0),
             strips=((-5.8, 4.8, AISLE_Y / 2), (-5.8, 4.8, -1.0), (-5.8, 4.8, 3.75)))
    for i, (n, f, mix) in enumerate(ROW_A):
        rack(s, built, n, x=1.0 * i, f=f, mix=mix, fan=17 * i)
    for i, (n, f, mix) in enumerate(ROW_B):
        rack(s, built, n, x=1.0 * i, y=AISLE_Y, rot=180, f=f, mix=mix, fan=11 * i)
    return s


def hero_aisle(built):
    nm = "hero_aisle"
    if want(nm):   # standing in the cold aisle at row B's left end, looking along row A's fronts
        s = aisle_scene(built, nm)
        s.camera((0.05, 2.05, 1.55), (1.25, 0.55, 1.05), 20)
        s.soft((-1.6, 2.6, 1.7), (1.2, 0.6, 1.0), 70, size=2.5, name="front")
        s.soft((3.8, 1.6, 2.4), (1.0, 0.6, 1.0), 40, size=2.0, col=(0.7, 0.85, 1.0), name="back")
        _hero(s)
    nm = "hero_aisle_wide"
    if want(nm):   # from above the aisle end: both rows, the aisle between
        s = aisle_scene(built, nm)
        s.camera((-4.4, 1.375, 2.6), (1.0, 1.375, 0.95), 28)
        s.soft((-4.8, 1.4, 2.2), (1.0, 1.4, 1.0), 60, size=3.0, name="front")
        s.soft((4.6, 1.4, 2.6), (1.0, 1.4, 1.0), 40, size=2.0, col=(0.7, 0.85, 1.0), name="back")
        _hero(s)


LINEUP = SERVERS


def hero_lineup(built):
    nm = "hero_server_lineup"
    if not want(nm):
        return
    s = Mood(nm, res=(3200, 1000), room=(-1.0, 7.0, -1.5, 3.0), walls=False, ceiling_visible=False,
             strips=((-0.5, 6.5, 0.6),), world=(0.006, 0.007, 0.009))
    # a low dark plinth carries the line-up; servers 0.62 m apart, the KVM popped, the UPS with its cells
    bm = bmesh.new()
    s._box(bm, (-0.45, -0.5, 0.0), (6.05, 0.55, 0.06), 0)
    s._box(bm, (-0.45, 0.53, 0.06), (6.05, 0.55, 0.065), 1)
    s._obj("mood_plinth", bm, [_mat("mood_plinth_m", (0.03, 0.031, 0.035), 0.35, 0.5),
                               _mat("mood_plinth_edge", (0.8, 0.5, 0.03), 0.4, 0.2, emit=(1.0, 0.55, 0.05), estr=1.5)])
    s.camera((2.9, 5.0, 0.8), (2.9, 0.0, 0.36), 23)
    for i, n in enumerate(LINEUP):   # the camera looks along -Y, so +X is screen-left: list right to left
        x = 0.64 * (len(LINEUP) - 1 - i)
        server(s, built, n, x=x, y=0.0, z=0.06)
        s.caption(SHORT[n], (x, 0.0, 0.70), 0.04)
    s.soft((2.9, 3.6, 2.2), (2.9, 0.0, 0.2), 900, size=6.0, name="front")
    s.soft((-1.5, 1.5, 1.2), (2.9, 0.0, 0.2), 180, size=2.0, col=(0.7, 0.85, 1.0), name="left")
    s.soft((7.0, 1.5, 1.2), (2.9, 0.0, 0.2), 180, size=2.0, col=(1.0, 0.85, 0.7), name="right")
    _hero(s)


def hero_paints(built):
    nm = "hero_door_variants_3_paints"
    if not want(nm):
        return
    s = Mood(nm, res=(3200, 1250), room=(-1.5, 14.5, -2.0, 11.0), walls=True, plenum=None,
             strips=((-0.8, 14.3, 1.75),))
    sets = (("DC_Rack42_SplitFront", 0.0), ("DC_Rack42_SplitFrontRear", 1.0), ("DC_Rack24_SplitFront", 1.0),
            ("DC_Rack24_SplitFrontRear", 0.0))
    mix42 = ("UPS", None, "DC_Srv_Storage", "DC_Srv_Timer", "KVM", "DC_Srv_Compute", "DC_Srv_Status", "PROG")
    mix24 = ("UPS", None, "DC_Srv_Switch", "DC_Srv_Compute")
    s.camera((6.25, 8.6, 1.4), (6.25, 0.0, 1.0), 19)
    x = 0.0
    for p, label in (("black", "BLACK"), ("keen", "DEFAULT GREY"), ("blue", "BLUE")):
        x0 = x
        for n, f in sets:
            rack(s, built, n, x=x, f=f, paint=p, mix=mix42 if "42" in n else mix24, fan=13 * x)
            x += 1.0
        s.caption(label, ((x0 + x - 1.0) / 2, 1.9, 0.06), 0.12)
        x += 0.75
    s.soft((5.5, 7.0, 3.0), (5.5, 0.0, 1.0), 1400, size=9.0, name="front")
    _hero(s)


def hero_layout_top(built):
    nm = "hero_layout_top"
    if not want(nm):
        return
    # a small hall: three rows, a cold aisle between rows 1 and 2, row 3 back to back with row 2 (hot aisle)
    s = Mood(nm, res=(2400, 2000), room=(-1.5, 7.5, -2.25, 6.25), walls=True, ceiling_visible=False,
             plenum=(-1.5, 7.5, 0.75, 2.0), strips=())
    s.camera((3.0, 2.0, 12.0), (3.0, 2.0, 0.0), 50, ortho=9.6)
    rows = [(0.0, 0.0, ROW_A + ROW_B[:2]), (AISLE_Y, 180, ROW_B + ROW_A[:2]), (AISLE_Y + 1.25 + 1.0, 0, ROW_A[::-1]
                                                                                + ROW_B[1:])]
    for y, rot, row in rows:
        for i, (n, f, mix) in enumerate(row):
            rack(s, built, n, x=1.0 * i + (0.5 if y > 3 else 0.0), y=y, rot=rot, f=f, mix=mix, fan=9 * i)
    for ln in (-1.0, AISLE_Y / 2, 5.0):
        s.soft((3.0, ln, 6.0), (3.0, ln, 0.0), 700, size=8.0, name=f"top{ln}")
    s.cam.rotation_euler = (0, 0, 0)
    pv_rack_doors.flat(s, "COLD AISLE", (5.6, AISLE_Y / 2, 0.005), 0.16)
    pv_rack_doors.flat(s, "HOT AISLE", (6.0, AISLE_Y + 0.625 + 0.5, 0.005), 0.16)
    _hero(s)


def hero_detail(built):
    nm = "hero_detail"
    if not want(nm):
        return
    s = Mood(nm, res=(2400, 1500), room=(-2.0, 4.0, -1.5, 4.0), plenum=(-2.0, 4.0, 0.75, 2.0),
             strips=((-1.8, 3.8, 1.375),))
    mix = ("DC_Srv_Storage", "UPS", None, "DC_Srv_Status", "KVM", "DC_Srv_Timer", "DC_Srv_Switch", "DC_Srv_Compute")
    rack(s, built, "DC_Rack42_SplitFront", x=0.0, f=1.0, mix=mix, fan=30)
    rack(s, built, "DC_Rack42_SplitFrontRear", x=1.0, f=0.0, mix=MIX_DENSE, fan=10)
    rack(s, built, "DC_Rack42_Open", x=-1.0, mix=MIX_OPEN, fan=50)
    s.camera((-0.75, 1.75, 1.42), (0.05, 0.5, 1.05), 32)
    s.soft((-1.4, 2.3, 1.6), (0.0, 0.5, 1.1), 260, size=2.0, name="front")
    s.soft((1.6, 1.4, 2.4), (0.0, 0.5, 1.1), 90, size=1.5, col=(0.7, 0.85, 1.0), name="side")
    s.dof((0.0, 0.85, 1.12), fstop=2.2)
    _hero(s)


# ------------------------------------------------------------------------------------------------ per-block
def block_previews(built):
    """One store-style 3/4 preview per catalogue block (preview/blocks/<name>.png)."""
    PV.OUT = BLOCKS_DIR
    for b in catalog.BLOCKS:
        if b.name not in built or not want("block_" + b.name):
            continue
        if b.family in ("tray", "trayrods"):
            _tray_preview(built, b)
            continue
        s = Mood(b.name, res=(1600, 1200), room=(-2.5, 2.5, -2.5, 3.5), walls=False, ceiling_visible=False,
                 strips=((-1.5, 1.5, 1.0),), world=(0.012, 0.013, 0.016))
        if b.family == "rack":
            H = 0.25 * b.cells[1]
            mix = MIX_KVM if H > 2 else ("UPS", None, "DC_Srv_Switch", "DC_Srv_Status")
            f = 1.0 if b.variant == "SplitFrontRear" else (0.0 if b.variant == "SplitFront" else 0.0)
            rack(s, built, b.name, f=f, f_rear=0.0 if b.variant == "SplitFrontRear" else None, mix=mix, fan=20,
                 working=True)
            d = 3.0 * H / 2.5 + 2.2
            s.camera((-0.6 * d, 0.8 * d, H * 0.75 + 0.5), (0, 0.15, H * 0.47), 45 if H > 2 else 42)
            s.soft((-0.6 * d - 1, 0.8 * d, H + 1.0), (0, 0, H / 2), 1100, size=4.0, name="front")
        else:
            z = 0.0
            server(s, built, b.name, z=z)
            h = 0.25 * b.cells[1]
            s.camera((-0.95, 1.95, h + 0.62), (0, 0.22, h * 0.5), 42)
            s.soft((-1.5, 2.0, 1.5), (0, 0, h / 2), 220, size=2.5, name="front")
        s.soft((1.8, -1.2, 2.2), (0, 0, 0.5), 160, size=2.0, col=(0.7, 0.85, 1.0), name="rim")
        s.render()


def _tray_preview(built, b):
    """A tray block's store shot: standing on its floor strut (or rod feet) on the dark hall floor, data cables in the
    blue paint, seen 3/4 from above like the icon, framed on its own bounds."""
    s = Mood(b.name, res=(1600, 1200), room=(-3.0, 3.0, -3.0, 3.5), walls=False, ceiling_visible=False,
             strips=((-1.5, 1.5, 1.0),), world=(0.012, 0.013, 0.016))
    lx, lz, ly = (0.25 * c for c in b.cells)
    s.inst(PV.painted(built, b.name, 0, TRAY_ICON_PAINT), T(0, 0, lz / 2 + 0.002))
    d, _ = _icon_frame(b)
    d = Vector(d).normalized()
    size = max(lx, ly, lz)
    tgt = Vector((0, 0, lz * 0.45))
    s.camera(tuple(tgt + d * (1.25 * size + 0.9)), tuple(tgt), 45)
    s.soft(tuple(tgt + Vector((-1.6, 1.4, 2.4)) * max(1.0, size)), tuple(tgt), 260 * max(1.0, size) ** 2, size=2.5,
           name="front")
    s.soft((1.8, -1.2, 2.2), tuple(tgt), 160, size=2.0, col=(0.7, 0.85, 1.0), name="rim")
    s.render()


def render_all(built):
    """Icons and block previews for every built block (DC_ICONS_PART=icons|blocks|hero|all); the hero shots need every
    core block built. The cable trays render alone: their icons and previews do not need the racks."""
    PM.get("Caption")
    os.makedirs(OUT, exist_ok=True)
    part = os.environ.get("DC_ICONS_PART", "all")
    if part in ("all", "icons"):
        icons(built)
    if part in ("all", "blocks"):
        block_previews(built)
    missing = [b.name for b in catalog.CORE_BLOCKS if b.name not in built]
    if part in ("all", "hero") and missing:
        print("icons: hero shots need every core block built; missing", missing)
        return
    if part in ("all", "hero"):
        hero_aisle(built)
        hero_lineup(built)
        hero_paints(built)
        hero_layout_top(built)
        hero_detail(built)
