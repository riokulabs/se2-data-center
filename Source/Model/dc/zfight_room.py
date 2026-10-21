"""Z-fight audit for the room blocks: the containment door's sliding leaves.

dc/zfight.py audits every built block's decal elements and the RACK doors' hinged
leaves. The containment door (dc/contain.py) has sliding leaves instead: two subparts (ContainLeafL / ContainLeafR)
that translate along x by contain.leaf_travel. This module adds, with zfight's bpy-free rules:
  contain_leaf_coplanar  same-facing coplanar overlapping faces between two parts of one leaf model (every LOD);
  contain_leaf_frame     the same between a leaf placed in the block frame (closed AND open pose) and the door
                         frame's LOD0 (jambs, pocket covers and back plates, header, sill);
  contain_leaf_leaf      the two leaves against each other in the closed pose (the meeting stiles).
build_dc.py stores the result in build_report.json "zfight" next to zfight.audit_built's keys.
"""
from . import zfight as Z


def _tris(objs, matrix=None):
    """Mesh triangles (decal faces included: a leaf decal coplanar with the frame fights too) as (n, d, pts, part)."""
    decal, geom = Z._mesh_tris(objs, matrix)
    out = [(n, d, pts, tag[0]) for n, d, pts, tag in geom]
    for faces in decal.values():
        out += [(n, d, pts, "decal") for n, d, pts in faces]
    return out


def _pairs(tris, other):
    idx = Z.PlaneIndex()
    for n, d, pts, tag in other:
        idx.add(n, d, pts, tag)
    return sorted(Z.coplanar_pairs(tris, idx).items())


def contain_door_check(spec, built):
    """{contain_leaf_coplanar, contain_leaf_frame, contain_leaf_leaf} for a DC_Contain_Door_* block (else {})."""
    if spec.family != "contain_door" or not built:
        return {}
    from mathutils import Matrix
    from . import contain
    sub = built.get("subparts") or {}
    rep = {"contain_leaf_coplanar": [], "contain_leaf_frame": [], "contain_leaf_leaf": []}
    for model in contain.LEAF_MODELS:
        for lod, (_, objs) in enumerate(sub[model]):
            rep["contain_leaf_coplanar"] += Z._coplanar_geom(f"{model}_LOD{lod}", Z._mesh_tris(objs)[1])
    frame = _tris(built["lods"][0][1])
    placed = {}
    for lf in contain.door_leaves(spec):
        for pose, f in (("closed", 0.0), ("open", 1.0)):
            m = Matrix.Translation((contain.leaf_centre_x(spec, lf.side, f), 0.0, contain.LEAF_ORIGIN_Z))
            tris = _tris(sub[lf.model][0][1], m)
            placed[(lf.model, pose)] = tris
            pts = [p for _, _, ps, _ in tris for p in ps]
            rep.setdefault("contain_leaf_bounds", {})[f"{lf.model}_{pose}"] = [
                [round(min(p[i] for p in pts), 4) for i in range(3)], [round(max(p[i] for p in pts), 4) for i in range(3)]]
            for (a, b), v in _pairs(tris, frame):
                rep["contain_leaf_frame"].append({"leaf": lf.name, "pose": pose, "leaf_part": a, "frame_part": b,
                                                  "area_mm2": round(v * 1e6, 3)})
    a, b = contain.LEAF_MODELS
    for (pa, pb), v in _pairs(placed[(a, "closed")], placed[(b, "closed")]):
        rep["contain_leaf_leaf"].append({"a": pa, "b": pb, "area_mm2": round(v * 1e6, 3)})
    return rep


# ------------------------------------------------------------------------------------------------ stencil contrast
# In game: white stencils straight on the player's paint read poorly on a light paint (the keen
# default grey). Every white stencil glyph of a room block must have a non-paint backing: the nearest same-facing face
# behind it (within BACK_D) that it overlaps must be a Darker / Yellow / MetalDull / ... plate, not PaintedMetalColorable.
BACK_D = 0.020
PAINT_MATS = ("PaintedMetalColorable",)


def _faces_with_mats(objs):
    """[(n, d, pts3, material, is_white_stencil)] of every face of the mesh objects (evaluated, world frame)."""
    from .style import STENCIL_WHITE
    out = []
    for o in objs:
        if o.type != "MESH":
            continue
        me, m = o.data, o.matrix_world
        rot = m.to_3x3()
        mats = [s.material.name if s.material else "" for s in o.material_slots]
        att = me.attributes.get(Z.TAG)
        tags = [a.value for a in att.data] if att is not None and att.domain == "FACE" else [0] * len(me.polygons)
        for poly in me.polygons:
            pts = [tuple(m @ me.vertices[i].co) for i in poly.vertices]
            n = (rot @ poly.normal).normalized()
            if n.length < 0.5:
                continue
            mat = mats[poly.material_index] if poly.material_index < len(mats) else ""
            mat = mat.split(".")[0]
            white = mat.startswith(STENCIL_WHITE) and Z._STATE["labels"].get(tags[poly.index], "?")
            out.append((tuple(n), n.dot(pts[0]), pts, mat, white))
    return out


def stencil_backing(spec, built):
    """[{model, stencil, backing, glyphs}] per white stencil (zfight element label) whose backing is paint or none.
    The backing of a glyph: the same-facing non-decal face with the largest depth d2 <= d (behind it) within BACK_D
    whose in-plane box contains the glyph's centre."""
    if not built:
        return []
    bad = {}
    models = [("block", i, objs) for i, (_, objs) in enumerate(built["lods"])]
    for name, lods in (built.get("subparts") or {}).items():
        models += [(name, i, objs) for i, (_, objs) in enumerate(lods)]
    for model, lod, objs in models:
        faces = _faces_with_mats(objs)
        idx = {}
        for n, d, pts, mat, white in faces:
            if mat.startswith("AtlasFont") or mat.startswith("AtlasDecal") or "Sticker" in mat:
                continue
            k = Z.nkey(n)
            idx.setdefault(k, []).append((d, Z.box_of(Z.project(pts, k)), mat))
        for n, d, pts, mat, white in faces:
            if not white:
                continue
            k = Z.nkey(n)
            p2 = Z.project(pts, k)
            cx, cy = sum(p[0] for p in p2) / len(p2), sum(p[1] for p in p2) / len(p2)
            best = None
            for d2, bx, m2 in idx.get(k, ()):
                if d - BACK_D <= d2 <= d + 1e-6 and bx[0] <= cx <= bx[2] and bx[1] <= cy <= bx[3]:
                    if best is None or d2 > best[0]:
                        best = (d2, m2)
            backing = best[1] if best else None
            if backing is None or backing.startswith(PAINT_MATS):
                key = (f"{model}_LOD{lod}", white, backing)
                bad[key] = bad.get(key, 0) + 1
    return [{"model": m, "stencil": s, "backing": b, "glyphs": c} for (m, s, b), c in sorted(bad.items(),
                                                                                            key=lambda kv: str(kv[0]))]
