"""The CRAC's two O2 / coolant service ports: Keen's small conveyor port as
a kit part, blanked, on the cooler's hot-aisle service bay.

Decorative today, designed to be "turned on" later: when SE2 gets air vents and airtightness, the block only needs
data (the conveyor / vent components, the ports' dummy type switched to vanilla UseConveyor, mount points); the
geometry and the dummies are already where vanilla puts a small port: centred on a 2 x 2 cell patch of a cell face,
facing out (dc/crac.py PORTS, the dummies conveyor_port_o2_1 / _2 in dc/integration.py patch_crac_dummies). Until then
they carry our own inert dummy type, so nothing snaps to them and they add no mount points.

Provenance (read-only import, nothing written back): tools/vanilla-ref/Blocks/O2H2Generator/250/Models/NonFractured/
(vanilla O2/H2 generator: its side ports are the same small port Keen puts on every 0.5 m conveyor face)

| LOD | file                      | object (SECTION ConveyorRight)       | tris |
|-----|---------------------------|--------------------------------------|------|
| 0   | O2Generator250.fbx        | ConveyorPortSmall_Border_low.001     | 240  |
| 1   | O2Generator250_LOD1.fbx   | ConveyorPortSmall_Border_low.003     | 38   |
| 2+  | (none in vanilla)         | our own Yellow block + Darker plate (dc/crac.py) |  |

The port frame's geometry, custom normals and first UV layer are used unchanged (the extra UV layers are dropped:
the exporter writes one UV set, as servers/cellbay.py; PaintedMetalYellow, a material the CRAC already has). The hatch is NOT reused: these ports are blanked, so a bolted Darker blind plate (ours) takes the hatch's place
in the recess; the hatch's face (Fracture_01.017, the ConveyorsAtlas two-leaf door, a 9th material) and its latch
handle (ConveyorPortSmall_Handle_low, 336 tris: it opens the hatch, so it goes with it) stay out. That also keeps the
CRAC at 8 materials and LOD0 under 90 % of Keen's limit.

Vanilla frame: the port faces -X, its frame's outer face at x = -1.255, centred on y = 0, z = -1.25 (0.4 x 0.4 m).
"""
import math
import os

import bpy
from mathutils import Matrix

from se2model.kit import KitPart
from se2model.materials import get_mat

from . import config

SRC = os.path.join(config.VANILLA_REF, "Blocks", "O2H2Generator", "250", "Models", "NonFractured")
FILES = {0: "O2Generator250.fbx", 1: "O2Generator250_LOD1.fbx"}
SECTION = "ConveyorRight"
PREFIX = "ConveyorPortSmall_Border"     # the frame only (the hatch and its handle: see above)
SRC_FACE_X, SRC_CZ = -1.255, -1.25        # the source port's outer frame face and centre height
HATCH_X = -1.2219                         # the source hatch face (the blind plate's face goes here)
HALF = 0.2                                # the frame's half size (0.4 m square: a small conveyor's port)
CLIP = 0.054                              # its outline's 45 deg corner cut (measured: |y| + |z| <= 0.3467 at the face)
_CACHE = {}                               # LOD -> [mesh in the vanilla frame, our library materials]
PROVENANCE = {}                           # LOD -> [source object names]


def _base(name):
    return name.split(".")[0]


def _load(L):
    before = set(bpy.data.objects)
    mats_before = set(bpy.data.materials)
    meshes_before = set(bpy.data.meshes)
    bpy.ops.import_scene.fbx(filepath=os.path.join(SRC, FILES[L]))
    for m in set(bpy.data.materials) - mats_before:
        m.name = "KITIMP_" + m.name
    new = [o for o in bpy.data.objects if o not in before]
    src = sorted((o for o in new if o.type == "MESH" and o.get("SECTION") == SECTION and o.name.startswith(PREFIX)),
                 key=lambda o: o.name)
    assert len(src) == 1, (FILES[L], [o.name for o in new if o.get("SECTION") == SECTION])
    out = []
    for o in src:
        me = o.data.copy()
        me.name = f"CRACPORT_KIT_{L}_{_base(o.name)}"
        me.transform(o.matrix_world)
        if o.matrix_world.to_3x3().determinant() < 0:
            me.flip_normals()
        while len(me.uv_layers) > 1:
            me.uv_layers.remove(me.uv_layers[-1])
        me.uv_layers[0].name = "UVMap"
        for i, m in enumerate(me.materials):
            if m:
                me.materials[i] = get_mat(_base(m.name[len("KITIMP_"):] if m.name.startswith("KITIMP_") else m.name))
        out.append(me)
    PROVENANCE[L] = [f"{FILES[L]}:{o.name}" for o in src]
    for ob in new:
        bpy.data.objects.remove(ob)
    for m in set(bpy.data.meshes) - meshes_before - set(out):
        if m.users == 0:
            bpy.data.meshes.remove(m)
    for m in [m for m in bpy.data.materials if m.name.startswith("KITIMP_")]:
        if m.users == 0:
            bpy.data.materials.remove(m)
    _CACHE[L] = out


def matrix(x, z, face_y):
    """Vanilla frame -> the CRAC's centred Blender frame: the port faces -Y (the hot aisle), its frame's outer face at
    y = face_y, centred on (x, z)."""
    return Matrix.Translation((x, face_y, z)) @ Matrix.Rotation(math.pi / 2, 4, "Z") @ \
        Matrix.Translation((-SRC_FACE_X, 0.0, -SRC_CZ))


def hatch_y(face_y):
    """The source hatch face mapped into our frame (the blind plate's face: 33 mm in from the frame's face)."""
    return face_y + (HATCH_X - SRC_FACE_X)


def port(lod, x, z, face_y, name):
    """The kit port frame (one KitPart) for LOD 0 / 1, None for the LODs vanilla has no kit mesh for."""
    if lod not in FILES:
        return None
    if lod not in _CACHE:
        _load(lod)
    m = matrix(x, z, face_y)
    meshes = []
    for src in _CACHE[lod]:
        me = src.copy()
        me.name = f"{name}_{src.name}"
        me.transform(m)
        meshes.append(me)
    return KitPart(name, meshes, None)


def triangles(lod):
    if lod not in FILES:
        return 0
    if lod not in _CACHE:
        _load(lod)
    return sum(sum(len(p.vertices) - 2 for p in me.polygons) for me in _CACHE[lod])
