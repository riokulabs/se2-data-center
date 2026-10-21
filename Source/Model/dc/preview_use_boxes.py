"""Plan 4 Task 9 (Ruling P4-8a): the KVM's two use boxes, rendered over the real model (Source/Model/preview/plan4/).

The boxes are the staged dummies' boxes (dc/functional.py KVM_TOGGLE_BOX / KVM_TERMINAL_BOX, the numbers
integration.patch_kvm_dummies writes), drawn as ghosts with a wire edge:
  amber  KvmToggle: vanilla UsePowerable, Use = On/Off = pop out / stow
  cyan   Terminal:  vanilla UseTerminal, Use = open the terminal
The KVM pair: stowed (viewer's left) and out (right, the data-only end pose f = 1, which is also the scripted end pose).
kvm_use_rays_side: an orthographic side view of the out KVM with use rays from a standing eye (0.4 m above the KVM,
1.2 m in front) through points up the lid, each drawn to where it meets the face and coloured by the box it gets
(dc/functional.kvm_use_target; grey: neither, e.g. the neighbour above).

    DC_PREVIEW=plan4 DC_SHOTS=kvm_use blender -b --python Source/Model/build_dc.py -- DC_Srv_KVM
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import functional as FN
from . import preview as PV
from . import preview_mats as PM
from . import preview_task8 as P8
from . import subparts as S
from .preview import Shot, T, want

KVM = P8.KVM
PAIR_X = 0.33                                  # the stowed KVM at +x (viewer's left from the front), the out one at -x
BOXES = ((FN.KVM_TOGGLE, FN.KVM_TOGGLE_BOX, "GhostOcc"), ("Terminal", FN.KVM_TERMINAL_BOX, "GhostSlot"))
RAY_MAT = {FN.KVM_TOGGLE: "EmAmber", "Terminal": "Terminal", None: "MetalDull"}
EYE = (0.0, FN.KVM_FACE_PLANE_Y + 1.2, 0.4)   # KVM frame (centre at z = 0)


def _box_object(name, box, base, mat):
    """A face box {a, b, d} (a = viewer's right = -x, d = out from the front cell plane) as a mesh in the KVM frame
    moved by base."""
    (a0, a1), (b0, b1), (d0, d1) = box["a"], box["b"], box["d"]
    lo = Vector((-a1, FN.FRONT_Y + d0, b0)) + base
    hi = Vector((-a0, FN.FRONT_Y + d1, b1)) + base
    bm = bmesh.new()
    vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.scale(bm, vec=hi - lo, verts=vs)
    bmesh.ops.translate(bm, vec=(lo + hi) / 2, verts=vs)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    me.materials.append(PM.get(mat))
    return bpy.data.objects.new(name, me)


def _boxes(s, base, tag):
    for name, box, mat in BOXES:
        ob = s.link(_box_object(f"use_{name}_{tag}", box, base, mat))
        s.link(PV.wire_copy(ob, t=0.0015))


def _rod(name, p0, p1, r, mat):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    m = Matrix.Translation((p0 + p1) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=r, radius2=r, depth=d.length, matrix=m)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    me.materials.append(PM.get(mat))
    return bpy.data.objects.new(name, me)


def lid_point(s_up, f=1.0):
    """A point s_up metres up the lid from the hinge (KVM frame, x = 0) at the data-only pose f."""
    dy, ang = S.pose(f)
    a = math.radians(ang)
    return (0.0, S.HINGE[1] + dy + s_up * math.cos(a), S.HINGE[2] + s_up * math.sin(a))


def pair(view, loc, tgt, lens):
    nm = f"kvm_use_boxes_{view}"
    if not want(nm):
        return
    s = Shot(nm, res=(1800, 1100), floor=(-1.5, 1.5, -1.5, 2.0))
    for x, f, tag in ((PAIR_X, 0.0, "stowed"), (-PAIR_X, 1.0, "out")):
        P8.kvm(s, P8_BUILT[0], x=x, f=f)
        _boxes(s, Vector((x, 0.0, P8.H / 2)), tag)
    s.camera(loc, tgt, lens)
    if view != "front":                        # the captions are placed for the front camera
        s.render()
        return
    s.caption("stowed: Use on the drawer pops it out", (PAIR_X, 0.45, 0.52), 0.028)
    s.caption("out: the screen opens the terminal, its hinge edge stows it", (-PAIR_X, 0.45, 0.52), 0.028)
    s.caption("amber KvmToggle = UsePowerable (On/Off)     cyan Terminal = UseTerminal", (0.0, 0.45, 0.46), 0.024)
    s.render()


def rays_side():
    nm = "kvm_use_rays_side"
    if not want(nm):
        return
    s = Shot(nm, res=(1800, 1100), floor=(-1.5, 1.5, -1.5, 2.0))
    base = Vector((0.0, 0.0, P8.H / 2))
    P8.kvm(s, P8_BUILT[0], f=1.0)
    _boxes(s, base, "out")
    eye = Vector(EYE) + base
    for i in range(11):
        p = lid_point(0.03 * i)
        name, (hx, hz) = FN.kvm_use_target(EYE, p)
        hit = Vector((hx, FN.KVM_FACE_PLANE_Y, hz)) + base
        s.link(_rod(f"ray_{i}", eye, hit, 0.0018, RAY_MAT[name]))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=0.02, matrix=Matrix.Translation(eye))
    me = bpy.data.meshes.new("eye")
    bm.to_mesh(me)
    me.materials.append(PM.get("EmWhite"))
    s.link(bpy.data.objects.new("eye", me))
    cy, cz = (eye.y - 0.42) / 2, 0.36           # frame the whole KVM (its back at y -0.375) and the eye
    s.camera((2.6, cy, cz), (0.0, cy, cz), 50, ortho=2.3)
    s.caption("use rays from a standing eye through the out lid:\namber stows it, cyan opens the terminal, "
              "grey meets neither box", (0.0, cy, cz + 0.55), 0.045)
    s.render()


P8_BUILT = [None]


def render_all(built):
    if KVM not in built:
        return
    P8_BUILT[0] = built
    pair("front", (0.0, 2.3, 0.42), (0.0, 0.40, 0.14), 40)
    pair("3q", (-1.35, 1.95, 1.05), (0.0, 0.40, 0.12), 38)
    rays_side()
