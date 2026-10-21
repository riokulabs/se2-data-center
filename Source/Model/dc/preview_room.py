"""The reference room preview scene: the backdrop of every room block's in-context shots.

    DC_PREVIEW=room blender -b --python Source/Model/build_dc.py -- "DC_Rack42*" "DC_Srv_*" \
        "DC_Tray_Drop_*" "DC_Tray_StraightS_*" "DC_TrayRods_*"

room_scene() lays out dc/room.reference_room() in a closed data hall: every block that is built in this run is its
real model (racks with doors, fans and servers fitted; trays, cables painted blue), every other block a
labelled ghost stand-in in its exact cell box, so a new block drops into the same room and the same cameras
once it is built. The hall: a dark deck under the raised floor, grey SE panel walls with seams, a stencilled hall
plate, a dark ceiling with suspended linear luminaires (real area lights) between the tray runs, and a soft fill
under the containment roof (the roof's LED strip). Moody (dark world, pools of light) but readable.

render_room(built) writes Source/Model/preview/room/ (DC_SHOTS=prefix,... renders a subset, DC_FAST=1
half resolution):
  room_<w>_<aisle>_<camera>     the room for each aisle width and hot / cold, at the CAMERAS
  room_150_cold_photo1_black    the photo 1 camera with black racks (the paint most real halls use)
  vanilla_sources               the room pieces' vanilla clone sources at the same scale and light
  and, for every room block built in this run (blocks=): its turntable, its LODs and its paint set.
Plan sheets (pure Python, no Blender): python3 Source/Model/room_sheet.py.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import catalog, config, room
from . import dims as DM
from . import preview as PV
from . import preview_mats as PM
from .preview import Rz, T, want

OUT = os.path.join(config.PREVIEW_DIR, "room")
TRAY_PAINT = "blue"                    # the data cables take the paint; the photos' blue
_ROOMS = {}                            # (w, aisle, paint, racks, doors) -> (collection, info)
_MATS = {}

# ghost stand-ins: family -> (tint, alpha, caption)
GHOST = {
    "floor": ((0.55, 0.57, 0.60), 1.0, "raised floor (ghost)"),
    "crac": ((0.25, 0.70, 1.00), 0.16, "in-row CRAC (ghost)"),
    "pdu_cabinet": ((1.00, 0.62, 0.15), 0.14, "PDU cabinet (ghost)"),
    "pdu_strip": ((1.00, 0.62, 0.15), 0.06, "rack PDU A / B (ghost)"),
    "contain_door": ((0.70, 0.85, 1.00), 0.16, "containment door (ghost)"),
    "contain_roof": ((0.86, 0.90, 0.95), 0.30, "containment roof (ghost)"),
    "sign": ((0.30, 0.60, 1.00), 1.0, "signs (ghost)"),
    "other": ((0.80, 0.80, 0.80), 0.25, "not built in this run"),
}
EDGE_GLOW = {"contain_door": 0.35, "contain_roof": 0.25, "pdu_strip": 0.22}   # ghost edge emission (default 0.9)
COLD, HOT = (0.30, 0.62, 1.00), (1.00, 0.42, 0.10)
LUM_W = 32.0                           # one linear luminaire (W): pools of light, not a showroom
ROOF_W = 9.0                           # the roof LED strip fill, per metre of aisle (stand-in while no roof is built)
ROOF_LED_W = 11.0                      # a built roof's LED batten: area light per metre of diffuser
# per rack: the slots from the bottom (P9.srv names; unbuilt servers are left out). KVM0 = the KVM stowed
MIXES = (
    ("DC_Srv_Storage", "DC_Srv_Storage", "DC_Srv_Compute", "DC_Srv_Compute", "DC_Srv_Switch", "DC_Srv_Compute",
     "DC_Srv_Blank", "DC_Srv_Switch"),
    ("DC_Srv_Compute", "DC_Srv_Compute", "DC_Srv_Compute", "DC_Srv_Timer", "DC_Srv_Compute", "DC_Srv_Blank",
     "DC_Srv_Switch", "DC_Srv_Switch"),
    ("DC_Srv_Storage", "DC_Srv_Storage", "DC_Srv_Storage", "DC_Srv_Blank", "KVM0", "DC_Srv_Status",
     "DC_Srv_Compute", "DC_Srv_Switch"),
    ("DC_Srv_Compute", "DC_Srv_Timer", "DC_Srv_Compute", "DC_Srv_Compute", "DC_Srv_Storage", "DC_Srv_Blank",
     None, "DC_Srv_Switch"),
)


def _out(folder):
    """Point the room shots (and the core rig's) at preview/<folder>/[DC_PREVIEW_SUB]."""
    global OUT
    OUT = os.path.join(config.PREVIEW_DIR, folder, os.environ.get("DC_PREVIEW_SUB", ""))
    os.makedirs(OUT, exist_ok=True)
    PV.OUT = OUT


def _M(p):
    """A placed block's world matrix (its model origin = cell-box centre)."""
    return T(*p.origin) @ Rz(90 * p.yaw)


# ---------------------------------------------------------------------------------------------------- materials
def mat(key):
    """Room materials: the shared Keen stand-ins (dc/preview_mats.py) plus this scene's own."""
    if key in _MATS and _MATS[key].name in bpy.data.materials:
        return _MATS[key]
    if key in ("tile", "tile_perf"):
        m = _tile_mat("pvr_" + key, perf=key == "tile_perf")
    elif key == "deck":
        m = PM.simple("pvr_deck", (0.012, 0.013, 0.015), 0.8)
    elif key == "wall":
        m = PM.simple("pvr_wall", (0.20, 0.21, 0.225), 0.55, 0.45, noise=0.08)
    elif key == "wall_band":
        m = PM.simple("pvr_wall_band", (0.05, 0.053, 0.058), 0.5, 0.5, noise=0.05)
    elif key == "ceiling":
        m = PM.simple("pvr_ceiling", (0.035, 0.037, 0.04), 0.7, 0.3, noise=0.05)
    elif key == "lamp":
        m = PM.simple("pvr_lamp", (0.9, 0.93, 1.0), 0.3, 0.0, emit=(0.88, 0.93, 1.0), estr=6.0)
    elif key == "stencil":
        m = PM.simple("pvr_stencil", (0.75, 0.76, 0.78), 0.6, 0.0, emit=(0.8, 0.82, 0.85), estr=0.25)
    elif key.startswith("text_"):
        c = {"text_cold": COLD, "text_hot": HOT, "text_white": (0.92, 0.95, 1.0)}[key]
        m = PM.simple("pvr_" + key, c, 0.4, 0.0, emit=c, estr=4.0)
    elif key.startswith("ghost_") or key.startswith("edge_"):
        fam = key.split("_", 1)[1]
        c, a, _ = GHOST.get(fam, GHOST["other"])
        if key.startswith("edge_"):
            m = PM.simple("pvr_" + key, c, 0.4, 0.0, emit=c, estr=EDGE_GLOW.get(fam, 0.9))
        else:
            m = PM.simple("pvr_" + key, c, 0.3 if fam == "contain_roof" else 0.15, 0.0, emit=c,
                          estr=0.08 if fam in ("contain_door", "contain_roof") else 0.35, alpha=a)
    else:
        m = PM.get(key)
    _MATS[key] = m
    return m


def _tile_mat(name, perf):
    """The raised-floor tile top: light grey, a 2 mm darker bevel line at its edge; perforated = a 20 x 20 grid of
    round holes (25 % open) inside a solid 25 mm border, laid on the tile's own UVs (0..1 per 0.5 m tile)."""
    m = PM.simple(name, (0.34, 0.35, 0.37), 0.5, 0.35, noise=0.05)
    if not perf:
        return m
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    N = lambda kind, **kw: PM._node(nt, kind, **kw)  # noqa: E731
    uv = N("ShaderNodeUVMap")
    sep = N("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs[0])

    def holes(axis):
        mul = N("ShaderNodeMath", operation="MULTIPLY")
        mul.inputs[1].default_value = 20.0
        nt.links.new(sep.outputs[axis], mul.inputs[0])
        fr = N("ShaderNodeMath", operation="FRACT")
        nt.links.new(mul.outputs[0], fr.inputs[0])
        sub = N("ShaderNodeMath", operation="SUBTRACT")
        sub.inputs[1].default_value = 0.5
        nt.links.new(fr.outputs[0], sub.inputs[0])
        return sub

    def border(axis):
        a = N("ShaderNodeMath", operation="PINGPONG")      # distance from the nearest tile edge, 0 .. 0.5
        a.inputs[1].default_value = 0.5
        nt.links.new(sep.outputs[axis], a.inputs[0])
        lt = N("ShaderNodeMath", operation="LESS_THAN")
        lt.inputs[1].default_value = 0.05
        nt.links.new(a.outputs[0], lt.inputs[0])
        return lt
    hx, hy = holes("X"), holes("Y")
    cmb = N("ShaderNodeCombineXYZ")
    nt.links.new(hx.outputs[0], cmb.inputs["X"])
    nt.links.new(hy.outputs[0], cmb.inputs["Y"])
    ln = N("ShaderNodeVectorMath", operation="LENGTH")
    nt.links.new(cmb.outputs[0], ln.inputs[0])
    hole = N("ShaderNodeMath", operation="LESS_THAN")
    hole.inputs[1].default_value = 0.28                 # pi r^2 at pitch 1: 0.246, the 25 % open area
    nt.links.new(ln.outputs["Value"], hole.inputs[0])
    edge = N("ShaderNodeMath", operation="MAXIMUM")
    nt.links.new(border("X").outputs[0], edge.inputs[0])
    nt.links.new(border("Y").outputs[0], edge.inputs[1])
    keep = N("ShaderNodeMath", operation="SUBTRACT")
    keep.use_clamp = True
    nt.links.new(hole.outputs[0], keep.inputs[0])
    nt.links.new(edge.outputs[0], keep.inputs[1])
    mix = N("ShaderNodeMix", data_type="RGBA")
    nt.links.new(keep.outputs[0], mix.inputs[0])
    mix.inputs[6].default_value = (0.30, 0.31, 0.33, 1)
    mix.inputs[7].default_value = (0.004, 0.004, 0.005, 1)  # the dark plenum seen through a hole
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    rough = N("ShaderNodeMix", data_type="FLOAT")
    nt.links.new(keep.outputs[0], rough.inputs[0])
    rough.inputs[2].default_value, rough.inputs[3].default_value = 0.45, 1.0
    nt.links.new(rough.outputs[0], b.inputs["Roughness"])
    return m


# ---------------------------------------------------------------------------------------------------- meshes
class Mesh:
    """Boxes (and their UVs) accumulated into one bmesh, one material slot per key."""

    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.keys = []

    def box(self, lo, hi, key, M=None, top_uv=None):
        lo, hi = Vector(lo), Vector(hi)
        vs = bmesh.ops.create_cube(self.bm, size=1.0)["verts"]
        bmesh.ops.scale(self.bm, vec=hi - lo, verts=vs)
        bmesh.ops.translate(self.bm, vec=(lo + hi) / 2, verts=vs)
        faces = {f for v in vs for f in v.link_faces}
        if key not in self.keys:
            self.keys.append(key)
        mi = self.keys.index(key)
        for f in faces:
            f.material_index = mi
            for lp in f.loops:   # planar UVs per face (the tiles use the top face's: 0..1 over top_uv metres)
                co = lp.vert.co
                n = f.normal
                ax = (0, 1) if abs(n.z) > 0.5 else ((1, 2) if abs(n.x) > 0.5 else (0, 2))
                s = top_uv or 1.0
                lp[self.uv].uv = ((co[ax[0]] - lo[ax[0]]) / s, (co[ax[1]] - lo[ax[1]]) / s)
        if M is not None:
            bmesh.ops.transform(self.bm, matrix=M, verts=vs)
        return vs

    def frame(self, lo, hi, key, t=0.008, M=None):
        """The 12 edges of a box as square bars (inside the box)."""
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        for a, b in (((x0, y0), (x1, y0 + t)), ((x0, y1 - t), (x1, y1))):
            for z in ((z0, z0 + t), (z1 - t, z1)):
                self.box((a[0], a[1], z[0]), (b[0], b[1], z[1]), key, M)
        for xs in ((x0, x0 + t), (x1 - t, x1)):
            for z in ((z0, z0 + t), (z1 - t, z1)):
                self.box((xs[0], y0, z[0]), (xs[1], y1, z[1]), key, M)
            for ys in ((y0, y0 + t), (y1 - t, y1)):
                self.box((xs[0], ys[0], z0), (xs[1], ys[1], z1), key, M)

    def obj(self, coll, name, shadow=True):
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for k in self.keys:
            me.materials.append(mat(k))
        ob = bpy.data.objects.new(name, me)
        ob.visible_shadow = shadow
        coll.objects.link(ob)
        return ob


def text(coll, body, M, size, key, name="txt"):
    """Flat text facing the matrix's +Y (a sign face), centred on its origin."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.materials.append(mat(key))
    o = bpy.data.objects.new(name, cu)
    o.matrix_world = M @ Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Rotation(math.radians(180), 4, "Y")
    coll.objects.link(o)
    return o


class _Sink:
    """The `s` the core preview helpers expect (inst / link), adding to a room collection instead of a Shot."""

    def __init__(self, coll):
        self.coll = coll
        self.cam = None

    def inst(self, c, m):
        e = bpy.data.objects.new("i_" + c.name, None)
        e.instance_type = "COLLECTION"
        e.instance_collection = c
        e.matrix_world = m
        self.coll.objects.link(e)
        return e

    def link(self, ob):
        self.coll.objects.link(ob)
        return ob


# ---------------------------------------------------------------------------------------------------- real blocks
def _rack(sink, built, p, mix, f=0.0, paint="keen"):
    """A built rack at its placed matrix, as preview_rack_doors.rack shows it (side panels, door leaves at open fraction
    f, tray fans, servers from slot 1 up), standing on the raised floor."""
    from . import doors
    from . import preview_rack_doors as P9
    spec = room.spec(p)
    H = 0.25 * spec.cells[1]
    C = _M(p)
    M = C @ T(0, 0, -H / 2)                                 # the rack's floor point (preview_rack_doors's base matrix)
    sink.inst(P9.body(built, p.name, paint, True), C)
    side = (built[p.name].get("subparts") or {}).get("RackSide")
    if side:
        for yaw in (0, 180):
            sink.inst(P9.sub(built, p.name, "RackSide", paint), C @ Rz(yaw))
    for lf in doors.leaves(spec):
        sink.inst(P9.sub(built, p.name, lf["model"], paint), C @ T(lf["axis"][0], lf["axis"][1], 0) @
                  Rz(doors.swing_yaw(lf, f)))
    tp = doors.fan_tray_point(spec)
    if tp:
        sink.inst(P9.sub(built, p.name, doors.FAN_TRAY_SUB, paint), C @ T(*tp))
    for i, q in enumerate(doors.fan_points(spec)):
        sink.inst(P9.sub(built, p.name, doors.FAN, paint), C @ T(*q) @ Rz(23 + 41 * i))
    z0 = p.origin[2] - H / 2
    for k, n in enumerate(mix, 1):
        if n:
            P9.srv(sink, built, n, M, z0 + 0.25 * k, paint)


def contain_door(sink, built, name, M, f=0.0, paint="keen", lod=0):
    """A built containment door at matrix M (its cell-box centre): the frame and both leaves at open fraction f (the
    leaves slide by contain.leaf_travel; the vanilla slide is linear in OpenRatio)."""
    from . import contain
    from . import preview_rack_doors as P9
    spec = catalog.BY_NAME[name]
    sink.inst(PV.painted(built, name, lod, paint), M)
    for lf in contain.door_leaves(spec):
        sink.inst(P9.sub(built, name, lf.model, paint, lod),
                  M @ T(contain.leaf_centre_x(spec, lf.side, f), 0, contain.LEAF_ORIGIN_Z))


def crac_unit(sink, built, name, M, angle=0.0, working=True, paint="keen", lod=0):
    """A built in-row cooler at matrix M (its cell-box centre): the cabinet (RUN lamp lit while working: the swapper's
    EmissiveOff -> EmissiveGreen) and its three CracFan rotors at their pivots, turned `angle` deg about the fans'
    axis (Blender -y, the game's +Z: the way InfiniteRotation turns them), each a little out of phase."""
    from . import crac
    from . import preview_rack_doors as P9
    sink.inst(P9.body(built, name, paint, working, lod), M)
    rot = P9.sub(built, name, crac.FAN, paint, lod)
    for i, p in enumerate(crac.fan_points(catalog.BY_NAME[name])):
        sink.inst(rot, M @ T(*p) @ Matrix.Rotation(math.radians(angle + 23.0 * i), 4, Vector((0, -1, 0))))


def _mix(built, i):
    from . import preview_kvm as P8
    ok = lambda n: n and (n in built or (n in ("KVM0", "KVM") and P8.KVM in built))  # noqa: E731   KVM = popped
    return tuple(n if ok(n) else None for n in MIXES[i % len(MIXES)])


# ---------------------------------------------------------------------------------------------------- ghosts
def _ghost_floor(coll, tiles):
    """The raised-floor stand-in: every 0.5 m tile a 35 mm deck plate (2 mm shadow gap round it) on a dark
    pedestal void, perforated tiles with their hole pattern."""
    m = Mesh()
    top = room.STACK["floor_top"]
    g = 0.002
    for p in tiles:
        s = room.spec(p)
        n = s.cells[0] // 2
        lo, _ = room.box(p)
        key = "tile_perf" if s.variant == "Perf" else "tile"
        for i in range(n):
            for j in range(n):
                x, y = lo[0] + 0.5 * i, lo[1] + 0.5 * j
                m.box((x + g, y + g, top - DM.RF_DECK_T), (x + 0.5 - g, y + 0.5 - g, top), key, top_uv=None)
    # UVs: per tile 0..1 (the box UVs are in metres from the box corner; a 0.5 m tile -> scale 2)
    for f in m.bm.faces:
        for lp in f.loops:
            u, v = lp[m.uv].uv
            lp[m.uv].uv = (u * 2.0, v * 2.0)
    ob = m.obj(coll, "room_floor_tiles")
    x0 = min(room.box(p)[0][0] for p in tiles)
    x1 = max(room.box(p)[1][0] for p in tiles)
    y0 = min(room.box(p)[0][1] for p in tiles)
    y1 = max(room.box(p)[1][1] for p in tiles)
    v = Mesh()
    v.box((x0, y0, 0.0), (x1, y1, top - DM.RF_DECK_T - 0.001), "deck")
    for x in _steps(x0 + 0.5, x1, 0.5):          # pedestal heads under the tile corners (seen through the gaps)
        for y in _steps(y0 + 0.5, y1, 0.5):
            v.box((x - 0.02, y - 0.02, top - DM.RF_DECK_T - 0.006), (x + 0.02, y + 0.02, top - DM.RF_DECK_T - 0.001),
                  "MetalDull")
    v.obj(coll, "room_floor_void")
    return ob


def _steps(a, b, d):
    out, x = [], a
    while x < b - 1e-6:
        out.append(x)
        x += d
    return out


def _ghost_box(m, e, p, fam):
    """A ghost stand-in: the block's cell box, translucent, with bright edges; a few family cues so it reads."""
    s = room.spec(p)
    sx, sy, sz = room.size(s)
    lo, hi = (-sx / 2, -sy / 2, -sz / 2), (sx / 2, sy / 2, sz / 2)
    M = _M(p)
    if fam == "contain_door":
        w = room.aisle_width(s)
        hb = sz / 2 - 0.25                             # the header band (the top cell)
        m.box((-w / 2, -0.012, -sz / 2 + 0.01), (w / 2, 0.012, hb), "ghost_contain_door", M)      # the two leaves
        e.box((-0.006, -0.02, -sz / 2 + 0.01), (0.006, 0.02, hb), "edge_contain_door", M)          # meeting stiles
        for sg in (-1, 1):
            for xc in (sg * (w / 2), sg * (w - 0.02)):                     # the jamb posts and the pocket ends
                e.box((xc - 0.02, -0.06, -sz / 2), (xc + 0.02, 0.06, hb), "edge_contain_door", M)
        m.box((-sx / 2, -sy / 2, hb), (sx / 2, sy / 2, sz / 2), "ghost_contain_door", M)          # header
        e.frame((-sx / 2, -sy / 2, hb), (sx / 2, sy / 2, sz / 2), "edge_contain_door", 0.01, M)
        return
    if fam == "contain_roof":
        m.box((-sx / 2 + 0.01, -sy / 2, sz / 2 - 0.03), (sx / 2 - 0.01, sy / 2, sz / 2 - 0.018), "ghost_contain_roof", M)
        e.frame((-sx / 2, -sy / 2, sz / 2 - 0.04), (sx / 2, sy / 2, sz / 2 - 0.005), "edge_contain_roof", 0.012, M)
        return
    m.box(lo, hi, f"ghost_{fam}", M)
    e.frame(lo, hi, f"edge_{fam}", 0.008 if max(sx, sy, sz) > 0.6 else 0.004, M)
    if fam == "crac":       # three fan rings on the front (the cold-air discharge), a filter grille line at the back
        for k in range(3):
            zc = sz / 2 - 0.5 - 0.62 * k
            for a in range(24):
                t0, t1 = 2 * math.pi * a / 24, 2 * math.pi * (a + 1) / 24
                r = 0.23
                p0 = (r * math.cos(t0), sy / 2 - 0.002, zc + r * math.sin(t0))
                p1 = (r * math.cos(t1), sy / 2 - 0.002, zc + r * math.sin(t1))
                e.box((min(p0[0], p1[0]) - 0.008, sy / 2 - 0.01, min(p0[2], p1[2]) - 0.008),
                      (max(p0[0], p1[0]) + 0.008, sy / 2, max(p0[2], p1[2]) + 0.008), "edge_crac", M)
    if fam == "pdu_cabinet":   # the breaker panel door and the meter window
        e.frame((-0.42, sy / 2 - 0.012, -0.9), (0.42, sy / 2, 0.95), "edge_pdu_cabinet", 0.01, M)
        e.box((-0.15, sy / 2 - 0.01, 0.75), (0.15, sy / 2, 0.88), "edge_pdu_cabinet", M)


def _ghost_sign(coll, m, p, aisle):
    """A sign stand-in: a dark Colorable-frame panel, its LCD face with the room's text (both faces when hung)."""
    s = room.spec(p)
    sx, sy, sz = room.size(s)
    M = _M(p)
    frame = 0.018
    hang = s.variant == "AisleHang"
    d = 0.06 if hang else 0.05
    if hang:                       # double-faced, hung on its centre line
        y0 = -d / 2
    elif s.variant == "Rack":      # on the rack's top front edge, its face at the front
        y0 = sy / 2 - 0.002 - d
    else:                          # against the wall / the door header behind it
        y0 = -sy / 2 + 0.002
    y1 = y0 + d
    m.box((-sx / 2 + 0.004, y0, -sz / 2 + 0.03), (sx / 2 - 0.004, y1, sz / 2 - 0.045 * hang - 0.03), "Darker", M)
    if hang:   # the hanger bar across the top, carried by the turned rod hanger's two rods (+-ROD_S)
        m.box((-0.02, -DM.ROD_S - 0.012, sz / 2 - 0.045), (0.02, DM.ROD_S + 0.012, sz / 2 - 0.001), "MetalDull", M)
    if s.variant == "Rack":
        tag = p.tag.split("/")[0]
        body = f"RACK {ROW_NO.get(tag[0], 1)}.{int(tag[1:]):02d}"
        key, size = "text_white", 0.085
    else:
        body = f"AISLE {2 if p.tag.startswith('hot/') else 1} {aisle.upper()}"
        key, size = ("text_cold" if aisle == "cold" else "text_hot"), 0.11
    faces = (1, -1) if hang else (1,)
    for sg in faces:
        Mf = M @ T(0, sg * (y1 if sg > 0 else -y0) + sg * 0.001, 0) @ Rz(0 if sg > 0 else 180)
        m.box((-sx / 2 + frame, -0.0008, -sz / 2 + 0.03 + frame * 0.6), (sx / 2 - frame, 0.0, sz / 2 - 0.03 - frame * 0.6),
              "EmOff", Mf)
        text(coll, body, Mf @ T(0, 0.001, 0), size, key, f"sign_{p.tag}")


SIGN_PAINT = {"cold": "blue", "hot": "red"}    # hot / cold is the frame's paint (no vanilla blue)
ROW_NO = {"A": 1, "B": 2, "C": 3}              # rack label rows (the two-aisle hall adds row C)


def aisle_of(p, aisle):
    """The aisle a placed sign belongs to: the two-aisle hall's hot-aisle pieces ("hot/..." tags) and row C's rack labels
    are the hot aisle's; everything else the room's own aisle."""
    return "hot" if p.tag.startswith("hot/") or p.tag.startswith("C") else aisle


def sign_text(p, aisle):
    """The sample text a placed sign shows in the previews (in game the player types it): the aisle signs "AISLE 1
    COLD" / "HOT", a rack label "RACK <row>.<nn>" (row A = 1, B = 2)."""
    s = room.spec(p)
    if s.variant == "Rack":
        tag = p.tag.split("/")[0]
        return f"RACK {ROW_NO.get(tag[0], 1)}.{int(tag[1:]):02d}" if tag[1:].isdigit() else "RACK 1.01"
    return f"AISLE {2 if p.tag.startswith('hot/') else 1} {aisle.upper()}"


def built_sign(coll, sink, built, p, aisle, paint=None):
    """A built sign at its placed matrix, its frame painted for the aisle (SIGN_PAINT), white sample text on every
    LCD surface (dc/preview_signs.screen_text)."""
    from . import preview_signs as P8
    sink.inst(PV.painted(built, p.name, 0, paint or SIGN_PAINT[aisle]), _M(p))
    P8.screen_text(coll, p.name, _M(p), sign_text(p, aisle))


# ---------------------------------------------------------------------------------------------------- the hall
def _roof_leds(coll, roofs):
    """Each built roof panel's own LED batten lights the contained aisle: a thin area light under its
    EmissiveWhite diffuser (dc/contain.py LED_*), facing down."""
    from . import contain
    out = []
    for p in roofs:
        s = room.spec(p)
        L = contain.width(s) - 2 * (contain.LED_END + 0.012)
        ld = bpy.data.lights.new("roof_led", "AREA")
        ld.shape, ld.size, ld.size_y = "RECTANGLE", 2 * contain.LED_LENS_HW, L
        ld.energy, ld.color = ROOF_LED_W * L, (0.92, 0.96, 1.0)
        o = bpy.data.objects.new("roof_led", ld)
        o.matrix_world = _M(p) @ T(0, 0, contain.LED_LENS_Z - 0.0015)
        coll.objects.link(o)
        out.append(o)
    return out


def _hall(coll, ext, aisle_w, racks, roof_fill=True, lum_ys=None, aisle_ys=(0.0,)):
    """Walls, ceiling, luminaires, the hall plate. Returns {group: [objects]} for per-camera cutaways.
    lum_ys: the luminaire runs' y (default: the aisle and each walkway); aisle_ys: the runs that skip the hanging
    aisle sign mid-row."""
    x0, x1, y0, y1 = ext
    zc = room.STACK["ceiling"]
    t = 0.2
    groups = {}

    def wall(name, lo, hi, axis, inner, sg):
        """A wall slab; its inner face at `inner` on `axis`, the room toward sg. Seams, bands and the skirting
        stand a few mm proud of the inner face."""
        m = Mesh()
        m.box(lo, hi, "wall")
        a = 1 - axis                                    # the axis along the wall
        L0, L1 = lo[a], hi[a]

        def strip(u0, u1, z0, z1, key, proud=0.004):
            b0, b1 = [0.0, 0.0, z0], [0.0, 0.0, z1]
            b0[a], b1[a] = u0, u1
            b0[axis], b1[axis] = sorted((inner, inner + sg * proud))
            m.box(tuple(b0), tuple(b1), key)
        strip(L0, L1, 0.0, 0.32, "wall_band", 0.02)              # skirting over the floor edge
        strip(L0, L1, 3.05, 3.55, "wall_band", 0.012)            # the Darker service band (cable-tray height)
        for u in _steps(L0 + 2.5, L1, 2.5):                      # panel seams
            strip(u - 0.006, u + 0.006, 0.32, zc, "Darker", 0.002)
        for z in (1.45, 2.6):
            strip(L0, L1, z - 0.005, z + 0.005, "Darker", 0.002)
        groups[name] = [m.obj(coll, name)]

    wall("wall_south", (x0 - t, y0 - t, 0.0), (x1 + t, y0, zc + 0.2), 1, y0, 1)
    wall("wall_north", (x0 - t, y1, 0.0), (x1 + t, y1 + t, zc + 0.2), 1, y1, -1)
    wall("wall_west", (x0 - t, y0, 0.0), (x0, y1, zc + 0.2), 0, x0, 1)
    wall("wall_east", (x1, y0, 0.0), (x1 + t, y1, zc + 0.2), 0, x1, -1)
    # the hall plate on the east wall: a Darker plate with a white stencil, the SE way
    m = Mesh()
    m.box((x1 - 0.012, -1.1, 3.62), (x1, 1.1, 4.12), "Darker")
    m.obj(coll, "hall_plate")
    text(coll, "DATA HALL 1", T(x1 - 0.013, 0, 3.87) @ Rz(90), 0.26, "stencil", "hall_text")
    # the ceiling: a dark slab with lighter coffer seams every 1.25 m
    c = Mesh()
    c.box((x0, y0, zc), (x1, y1, zc + 0.15), "ceiling")
    for x in _steps(x0 + 1.25, x1, 1.25):
        c.box((x - 0.01, y0, zc - 0.004), (x + 0.01, y1, zc), "Grey")
    groups["ceiling"] = [c.obj(coll, "ceiling")]
    # linear luminaires: one run over the aisle (clear of the hanging sign) and one over each walkway
    L = room.PITCH * len(room.row_units(racks))
    walk = aisle_w / 2 + room.ROW_BAND + room.SERVICE / 2
    lum, lights = Mesh(), []
    zl = zc - 0.28
    for y in (lum_ys or (0.0, -walk, walk)):
        for xc in _steps(x0 + 1.0, x1 - 0.5, 1.6):
            if y in aisle_ys and abs(xc - L / 2) < 0.9:
                continue
            lum.box((xc - 0.6, y - 0.06, zl), (xc + 0.6, y + 0.06, zl + 0.05), "Grey")
            lum.box((xc - 0.58, y - 0.045, zl - 0.004), (xc + 0.58, y + 0.045, zl), "lamp")
            for sx in (-0.5, 0.5):
                lum.box((xc + sx - 0.003, y - 0.003, zl + 0.05), (xc + sx + 0.003, y + 0.003, zc), "MetalDull")
            ld = bpy.data.lights.new("lum", "AREA")
            ld.shape, ld.size, ld.size_y = "RECTANGLE", 1.16, 0.09
            ld.energy, ld.color = LUM_W, (0.88, 0.93, 1.0)
            o = bpy.data.objects.new("lum", ld)
            o.location = (xc, y, zl - 0.006)
            coll.objects.link(o)
            lights.append(o)
    groups["luminaires"] = [lum.obj(coll, "luminaires")]
    if not roof_fill:   # the built roofs light the aisle with their own LED battens (_roof_leds)
        return groups
    # the containment roof's LED strip (a soft fill under the roof plane, along the aisle): a stand-in when no roof is built
    ld = bpy.data.lights.new("roof_led", "AREA")
    ld.shape, ld.size, ld.size_y = "RECTANGLE", L - 0.4, max(0.3, aisle_w - 0.5)
    ld.energy, ld.color = ROOF_W * L, (0.9, 0.95, 1.0)
    o = bpy.data.objects.new("roof_led", ld)
    o.location = (L / 2, 0.0, room.STACK["roof"][0] - 0.02)
    coll.objects.link(o)
    return groups


# ---------------------------------------------------------------------------------------------------- the scene
def room_scene(built, aisle_w=1.5, aisle="cold", paint="keen", racks=4, doors_open=0.0, contain_open=0.0,
               label_side="front", hall=None):
    """The reference room as a collection (cached per arguments): built blocks real, the rest ghosts. Its info dict
    (_ROOMS[...][1]) has the placed list, the hall's object groups and one caption anchor per ghost family.
    doors_open: the racks' leaves (fraction of 85 deg); contain_open: the containment doors' leaves.
    hall: a hot aisle width -> the two-aisle hall (room.two_aisle_room: the cold aisle aisle_w wide at
    y = 0, the hot one `hall` wide behind row B); aisle is then the cold one and label_side is ignored."""
    key = (aisle_w, aisle, paint, racks, doors_open, contain_open, label_side, hall)
    if key in _ROOMS:
        return _ROOMS[key][0]
    if hall:
        placed = room.two_aisle_room(aisle_w, hall, racks)
    else:
        placed = room.reference_room(aisle_w, aisle, racks, label_side=label_side)
    coll = bpy.data.collections.new(f"room_{round(aisle_w * 100):03d}_{aisle}_{paint}" + ("_hall" if hall else ""))
    bpy.context.scene.collection.children.link(coll)
    PV._exclude(coll)
    sink = _Sink(coll)
    ghosts, edges, signs = Mesh(), Mesh(), Mesh()
    anchors, rack_i = {}, 0
    floor = [p for p in placed if room.spec(p).family == "floor"]
    for p in placed:
        s = room.spec(p)
        fam = s.family
        if fam == "floor":
            continue
        if p.name in built:
            if fam == "rack":
                _rack(sink, built, p, _mix(built, rack_i), doors_open, paint)
                rack_i += 1
            elif fam == "contain_door":
                contain_door(sink, built, p.name, _M(p), contain_open, paint)
            elif fam == "crac":    # running (lamp lit, fans mid-turn)
                crac_unit(sink, built, p.name, _M(p), 11.0 + 31.0 * rack_i, True, paint)
            elif fam == "sign":    # built signs, painted for the aisle, sample text on their LCDs
                built_sign(coll, sink, built, p, aisle_of(p, aisle))
            else:
                sink.inst(PV.painted(built, p.name, 0, TRAY_PAINT if fam in ("tray", "trayrods") else paint), _M(p))
            continue
        if fam == "sign":
            _ghost_sign(coll, signs, p, aisle_of(p, aisle))
        else:
            _ghost_box(ghosts, edges, p, fam if fam in GHOST else "other")
        anchors.setdefault(fam if fam in GHOST else "other", p)
    if floor and not any(p.name in built for p in floor):
        _ghost_floor(coll, floor)
        anchors["floor"] = next(p for p in floor if room.spec(p).variant == ("Perf" if aisle == "cold" else "Solid"))
    elif floor:
        for p in floor:
            if p.name in built:
                sink.inst(PV.painted(built, p.name, 0, paint), _M(p))
    if ghosts.keys:
        ghosts.obj(coll, "ghosts", shadow=False)
    else:
        ghosts.bm.free()
    if edges.keys:
        edges.obj(coll, "ghost_edges", shadow=False)
    else:
        edges.bm.free()
    if signs.keys:
        signs.obj(coll, "signs")
    else:
        signs.bm.free()
    roofs = [p for p in placed if room.spec(p).family == "contain_roof" and p.name in built]
    if roofs:
        _roof_leds(coll, roofs)
    if hall:
        dy = room.hot_offset(aisle_w, hall)
        walk = hall / 2 + room.ROW_BAND + room.SERVICE / 2
        groups = _hall(coll, room.hall_extent(aisle_w, hall, racks), aisle_w, racks, roof_fill=not roofs,
                       lum_ys=(0.0, -(aisle_w / 2 + room.ROW_BAND + room.SERVICE / 2), dy, dy + walk),
                       aisle_ys=(0.0, dy))
    else:
        groups = _hall(coll, room.floor_extent(aisle_w, racks), aisle_w, racks, roof_fill=not roofs)
    _ROOMS[key] = (coll, {"placed": placed, "groups": groups, "anchors": anchors, "aisle_w": aisle_w,
                          "aisle": aisle, "racks": racks, "hall": hall})
    return coll


# ---------------------------------------------------------------------------------------------------- cameras
class Cam:
    def __init__(self, loc, target, lens, hide=()):
        self.loc, self.target, self.lens, self.hide = loc, target, lens, tuple(hide)


def _geo(info):
    w, racks = info["aisle_w"], info["racks"]
    L = room.PITCH * len(room.row_units(racks))
    x0, x1, y0, y1 = room.floor_extent(w, racks)
    front = 1 if info["aisle"] == "cold" else -1     # row A's front direction (+y toward the aisle when cold)
    return w, L, x0, x1, y0, y1, front


def _cam_aisle_eye(info):
    w, L, *_ = _geo(info)
    return Cam((0.45, -0.18 * w, 1.7), (L - 0.4, 0.06 * w, 1.42), 17)


def _cam_door_outside(info):
    w, L, x0, *_ = _geo(info)
    return Cam((x0 + 0.45, -0.35 * w - 0.7, 1.72), (0.2, 0.05, 1.9), 20)


def _cam_overhead(info):
    w, L, x0, x1, y0, y1, _ = _geo(info)
    return Cam((L / 2 - 2.6, y0 - 3.8, 9.4), (L / 2 + 0.2, 0.0, 1.0), 21, ("ceiling", "luminaires", "wall_south"))


def _cam_rack_top(info):
    """Row A's second rack top close: its Drop's waterfalls, the rack label between them, the roof panel beside it
    (cold: on the aisle side; hot: the label's front faces the walkway, so the camera stands there)."""
    w, L, *_, front = _geo(info)
    xr = 1.5                                             # rack A2 (row_units: A1, A2, crac, A3, A4, pdu)
    yc = -(w / 2 + 0.625)
    yf = yc + front * 0.625
    return Cam((xr - 0.75, yf + front * 0.95, room.STACK["rack_top"] + 0.95), (xr + 0.05, yf - front * 0.2,
                                                                                 room.STACK["rack_top"] + 0.12), 30)


def _cam_photo1(info):
    """Photo 1 (docs/ideas/reference/datacenter/01): standing at the aisle's end, eye a little low, looking down the
    aisle past the right-hand row (its in-row cooler), the tray waterfalls above both rows. Inside a contained aisle
    the end is the door, so the camera stands just inside it."""
    w, L, *_ = _geo(info)
    return Cam((0.3, -0.32 * w, 1.55), (0.62 * L, 0.3 * w, 1.55), 15)


def _cam_end_row(info):
    w, L, x0, x1, y0, y1, front = _geo(info)
    walk = -(w / 2 + room.ROW_BAND + room.SERVICE / 2)
    return Cam((x0 + 0.5, walk - 0.1, 1.75), (L * 0.6, -(w / 2 + 0.9), 1.45), 19)


CAMERAS = {"aisle_eye": _cam_aisle_eye, "door_outside": _cam_door_outside, "overhead": _cam_overhead,
           "rack_top": _cam_rack_top, "photo1": _cam_photo1, "end_row": _cam_end_row}
CAPTIONS = {"aisle_eye": ("contain_roof", "contain_door", "crac"), "door_outside": ("contain_door", "sign", "floor"),
            "overhead": ("crac", "pdu_cabinet", "contain_roof", "contain_door", "floor"),
            "rack_top": ("sign", "contain_roof"), "photo1": ("crac", "contain_roof"),
            "end_row": ("pdu_cabinet", "crac", "floor")}


def shot(built, cam, aisle_w=1.5, aisle="cold", paint="keen", name=None, res=(1920, 1080), captions=True,
         doors_open=0.0, contain_open=0.0, label_side="front", hall=None, cam_fn=None):
    """Render one camera of the room; returns the PNG path. hall: the two-aisle hall (room_scene); cam_fn: a
    camera function (info -> Cam) instead of CAMERAS[cam]."""
    nm = name or f"room_{round(aisle_w * 100):03d}_{aisle}_{cam}"
    if not want(nm):
        return None
    coll = room_scene(built, aisle_w, aisle, paint, doors_open=doors_open, contain_open=contain_open,
                      label_side=label_side, hall=hall)
    info = next(i for c, i in _ROOMS.values() if c == coll)
    s = PV.Shot(nm, res=res, floor=None, world=(0.004, 0.0045, 0.006), light=0.0)
    for o in [o for o in s.sc.collection.objects if o.type == "LIGHT"]:    # the studio rig: not in a hall
        bpy.data.objects.remove(o)
    try:
        s.sc.eevee.shadow_pool_size = "2048"      # ~20 luminaires over a big room: the default pool overflows
        s.sc.eevee.shadow_resolution_scale = 0.5
    except (AttributeError, TypeError):
        pass
    s.sc.collection.children.link(coll)
    c = cam_fn(info) if cam_fn else CAMERAS[cam](info)
    s.camera(c.loc, c.target, c.lens)
    hidden = [o for g in c.hide for o in info["groups"].get(g, [])]
    for o in hidden:
        o.visible_camera = False
    if captions:
        for fam in CAPTIONS.get(cam, ()):
            p = info["anchors"].get(fam)
            if p is None:
                continue
            lo, hi = room.box(p)
            at = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, hi[2] + 0.12))
            d = (at - Vector(c.loc)).length
            o = s.caption(GHOST[fam][2], tuple(at), max(0.04, 0.024 * d * 17 / c.lens))
            o.visible_shadow = False
    try:
        path = s.render()
    finally:
        for o in hidden:
            o.visible_camera = True
    return path


# ------------------------------------------------------------------------------------------------------- room sets
MAIN = ("aisle_eye", "door_outside", "overhead")
ROOM_SET = [(1.5, "cold", tuple(CAMERAS)), (1.5, "hot", tuple(CAMERAS)),
            (1.0, "cold", MAIN), (1.0, "hot", MAIN), (2.0, "cold", MAIN), (2.0, "hot", MAIN)]
VANILLA = (("Catwalks/CatwalkSquareBase/250/Models/NonFractured/CatwalkSquareBase_250.fbx", "CatwalkSquareBase_250"),
           ("DeckPanel/250/Models/NonFractured/DeckPanel250.fbx", "DeckPanel250"),
           ("Gyroscopes/Gyroscopes/250/Models/NonFractured/Base/Gyroscope250_Base.fbx", "Gyroscope250_Base"),
           ("Doors/SlideDoorNarrow/250/Models/NonFractured/NarrowSlidingDoor.fbx", "NarrowSlidingDoor"),
           ("LCDPanels/NarrowLCD/50/Models/Nonfractured/NarrowLCD50.fbx", "NarrowLCD50"),
           ("Walls/Inserts/Vent/Models/NonFractured/WallInsertVent.fbx", "WallInsertVent"),
           ("Batteries/Battery/50/Models/NonFractured/Battery50.fbx", "Battery50"))


def vanilla_sources(built, paint="keen"):
    """The room pieces' vanilla clone sources (read-only FBX) in a line beside a built full rack, at the same scale
    and with the same Keen stand-in materials."""
    nm = "vanilla_sources"
    if not want(nm):
        return
    s = PV.Shot(nm, res=(2400, 1000), floor=None, light=1.4)
    x, labels = 0.0, []
    rk = "DC_Rack42_SplitFront"
    if rk in built:
        s.inst(PV.painted(built, rk, 0, paint), T(0, 0, 1.25))
        labels.append(("ours: 42U rack\n1.0 x 1.25 x 2.5 m", (0, 0.7, 2.75)))
        x = -0.75
    for rel, label in VANILLA:
        c, lo, hi = PV.vanilla(rel, paint)
        w = hi.x - lo.x
        ctr = (lo + hi) / 2
        s.inst(c, T(x - w / 2, 0, 0) @ T(-ctr.x, -ctr.y, -lo.z))
        labels.append((f"vanilla\n{label}", (x - w / 2, 0.7, hi.z - lo.z + 0.25)))
        x -= w + 0.4
    cx, span = (x + 0.75) / 2, 0.75 - x
    s.grid(x - 0.5, 1.5, -1.5, 1.5)
    s.camera((cx, 1.25 * span, 0.18 * span + 1.2), (cx, 0, 1.0), 35)   # the whole line in frame (~15 m)
    for txt, at in labels:
        s.caption(txt, at, 0.16)
    s.render()


def block_set(built, name):
    """A built room block's set: its turntable, LODs and paints (keen, black, the cold / hot pair)."""
    PV.turntable(built, name)
    PV.lods(built, name)
    for paint in ("black", "blue", "orange"):
        nm = f"{name}_paint_{paint}"
        if want(nm):
            H = 0.25 * catalog.BY_NAME[name].cells[1]
            s = PV.Shot(nm, floor=(-1.5, 1.5, -1.5, 1.5))
            s.inst(PV.painted(built, name, 0, paint), T(0, 0, H / 2))
            D = 2.5 * H + 1.2
            s.camera((-0.55 * D, 0.8 * D, H / 2 + 0.38 * D), (0, 0, H / 2), 50)
            s.render()


def render_room(built, blocks=None, folder="room"):
    """The room shot set into preview/<folder>/: the room at every camera
    (all aisle widths, cold and hot), photo 1 with black racks, the vanilla sources, and per built room block
    (blocks, default: every built room block) its turntable, LODs and paints."""
    _out(folder)
    blocks = [n for n in (blocks or built) if n in built and catalog.BY_NAME[n].family in catalog.ROOM_FAMILIES]
    for name in blocks:
        block_set(built, name)
    for w, aisle, cams in ROOM_SET:
        for cam in cams:
            shot(built, cam, w, aisle)
    shot(built, "photo1", 1.5, "cold", paint="black", name="room_150_cold_photo1_black")
    vanilla_sources(built)
