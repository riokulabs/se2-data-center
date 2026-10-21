"""The vanilla Battery50 Power Cell slot frame as a kit part (the UPS's two open cell bays).

Provenance (read-only import, nothing written back): tools/vanilla-ref/Blocks/Batteries/Battery/50/Models/NonFractured/

| LOD | file               | object (prefix)            | tris | Keen's SECTION   |
|-----|--------------------|----------------------------|------|------------------|
| 0   | Battery50.fbx      | UpgradePort_SpeedModule    | 367  | -                |
| 1   | Battery50_LOD1.fbx | UpgradePort_SpeedModule    | 181  | CellAction 0     |
| 2   | Battery50_LOD2.fbx | UpgradePort_SpeedModule    | 28   | -                |

The frame (vanilla FBX frame): an octagonal Yellow sleeve 0.4 x 0.4 m (the 0.3 m opening inside it) whose mouth faces +Y
at y = 0.2319, centred on x = z = 0, with a Darker back wall (battery icon decal, AtlasDecal_Parts02) 0.13 m in and
Yellow guide rails running back to y = -0.152 (the inserted cell is 0.355 m deep). It is used unchanged (Keen's
custom normals and atlas UVs) except one slot: its small EmissiveOff part is remapped to PaintedMetalDarker (an unlit
lens looks the same, and the UPS's 8-material budget has no room for EmissiveOff next to the lit ladder).
The SE2 vanilla kit-part reuse rule applies (the user approved reusing vanilla parts in this SE2 mod).
"""
import os

import bpy
from mathutils import Matrix

from se2model.kit import KitPart
from se2model.materials import get_mat

from .. import config
from .. import functional as FN

SRC = os.path.join(config.VANILLA_REF, "Blocks", "Batteries", "Battery", "50", "Models", "NonFractured")
FILES = {0: "Battery50.fbx", 1: "Battery50_LOD1.fbx", 2: "Battery50_LOD2.fbx"}
OBJECT = "UpgradePort_SpeedModule"
REMAP = {"EmissiveOff": "PaintedMetalDarker"}
_CACHE = {}          # LOD -> world-space mesh in the vanilla frame (materials = our library materials)
PROVENANCE = {}      # LOD -> source object name


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
    src = [o for o in new if o.type == "MESH" and o.name.startswith(OBJECT)]
    assert len(src) == 1, (FILES[L], [o.name for o in new])
    o = src[0]
    me = o.data.copy()
    me.name = f"CELLBAY_KIT_{L}"
    me.transform(o.matrix_world)
    while len(me.uv_layers) > 1:
        me.uv_layers.remove(me.uv_layers[-1])
    me.uv_layers[0].name = "UVMap"
    names = [_base(m.name[len("KITIMP_"):]) if m else "PaintedMetalDarker" for m in me.materials]
    names = [REMAP.get(n, n) for n in names]
    uniq = sorted(set(names), key=names.index)
    idx = [uniq.index(n) for n in names]
    poly_idx = [idx[p.material_index] for p in me.polygons]
    me.materials.clear()
    for n in uniq:
        me.materials.append(get_mat(n))
    for p, i in zip(me.polygons, poly_idx):
        p.material_index = i
    PROVENANCE[L] = f"{FILES[L]}:{o.name}"
    for ob in new:
        bpy.data.objects.remove(ob)
    for m in set(bpy.data.meshes) - meshes_before - {me}:
        if m.users == 0:
            bpy.data.meshes.remove(m)
    for m in [m for m in bpy.data.materials if m.name.startswith("KITIMP_")]:
        if m.users == 0:
            bpy.data.materials.remove(m)
    _CACHE[L] = me


def matrix(x, z, mouth_y, facing):
    """Vanilla frame -> UPS (Blender) frame: the mouth at y = mouth_y, centred on (x, z), facing +Y (facing = 1) or
    -Y (facing = -1, turned 180 deg about Z)."""
    rot = Matrix.Identity(4) if facing > 0 else Matrix.Rotation(3.141592653589793, 4, "Z")
    return Matrix.Translation((x, mouth_y, z)) @ rot @ Matrix.Translation((0, -FN.CELL_KIT_MOUTH, 0))


def bay(lod, x, z, mouth_y, facing, name):
    """A KitPart of the vanilla slot frame for LOD 0..2 placed as one UPS bay; None for LODs without a kit mesh."""
    if lod not in FILES:
        return None
    if lod not in _CACHE:
        _load(lod)
    me = _CACHE[lod].copy()
    me.name = f"{name}_mesh"
    me.transform(matrix(x, z, mouth_y, facing))
    return KitPart(name, [me], None)


def triangles(lod):
    if lod not in _CACHE:
        _load(lod)
    return sum(len(p.vertices) - 2 for p in _CACHE[lod].polygons)
