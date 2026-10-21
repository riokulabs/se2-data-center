"""Offline placement check on the EXPORTED files (an earlier prototype's pattern).

    blender -b --python Source/Model/check_placement.py -- [BLOCK|GLOB ...|all]     (GLOB quoted: "DC_Tray_*")

For each exported block: imports the LOD0 FBX (the game builds the precise mount-point collider from LOD0), reads
the collision glTF (regular / occupancy* / mountpoints* nodes) and the Fractured glTF (Fracture_NN hulls), and runs
se2model.placement with the block's cell bounds and per-axis grid shift. Writes
Models/<name>/placement_exported.json:
  nonfractured: the generator on LOD0 + collision only (must equal build_report.json "placement", which was computed
                from the in-Blender meshes before export; Tests/test_integration.py compares them);
  fractured:    the same plus the fracture hulls, which split mount groups per fracture as the game does
                (informational: group counts can be higher, coverage and occupancy must not change).
Read-only on its inputs.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "tools")))

import bpy  # noqa: E402

from dc import catalog, config  # noqa: E402
from se2model import placement as PL  # noqa: E402


def rep(r):
    return {"occupied": r["occupied_in_box"], "total": r["box_cells"], "outside": r["occupied_outside_box"],
            "faces": {d: {"groups": f["groups"], "coverage": round(f["box_face_coverage_pct"] / 100.0, 4)}
                      for d, f in r["faces"].items()},
            "free_cells": [list(c) for c in r["free_cells"]], "shift": list(r["shift"])}


def check(name):
    spec = catalog.BY_NAME[name]
    d = os.path.join(config.MODELS_DIR, name)
    nf, fr = os.path.join(d, "NonFractured"), os.path.join(d, "Fractured")
    fbx = os.path.join(nf, f"{name}.fbx")
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.import_scene.fbx(filepath=fbx)
    tris = PL.tris_from_objects([o for o in bpy.context.scene.objects if o.type == "MESH"])
    reg, occ, mnt = PL.split_hulls(PL.gltf_hulls(os.path.join(nf, f"{name}_collision.gltf")))
    frac = [(n, v) for n, v in PL.gltf_hulls(os.path.join(fr, f"{name}_Fractured_collision.gltf")).items()
            if n.lower().startswith("fracture")]
    b = catalog.bounds(spec)
    r0 = PL.analyse(tris, reg, occ, mnt, bounds=b, shift="bounds")
    r1 = PL.analyse(tris, reg, occ, mnt, frac, bounds=b, shift="bounds")
    # Task 9b: which fracture supports each mount cell (the game's FindFractureId: the first fracture collider the
    # cell's box query hits); a cell no fracture covers keeps its mount whatever breaks
    hulls = [PL.Hull(n, v) for n, v in frac]
    by_frac = {}
    for f in r1["faces"].values():
        for c in f["mount_cell_list"]:
            z = PL.fracture_of(c, hulls, r1["shift"]) if hulls else None
            by_frac[z or "none"] = by_frac.get(z or "none", 0) + 1
    with open(fbx, "rb") as fh:
        fbx_sha256 = hashlib.sha256(fh.read()).hexdigest()
    out = {"model": name, "fbx_sha256": fbx_sha256, "inputs": [os.path.relpath(p, d) for p in (fbx, os.path.join(nf, f"{name}_collision.gltf"),
                                                                       os.path.join(fr, f"{name}_Fractured_collision.gltf"))],
           "colliders": {"regular": len(reg), "occupancy_hints": len(occ), "mount_hints": len(mnt),
                         "fractures": len(frac)},
           "render_tris": len(tris),
           "nonfractured": dict(rep(r0), summary=PL.summary_line(name, r0)),
           "fractured": dict(rep(r1), summary=PL.summary_line(name, r1), mount_cells_by_fracture=by_frac)}
    with open(os.path.join(d, "placement_exported.json"), "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print("PLACEMENT (exported, NonFractured)", out["nonfractured"]["summary"])
    print("PLACEMENT (exported, + fractures) ", out["fractured"]["summary"])
    return out


def main(argv):
    names = [a for a in argv if not a.startswith("--")]
    if not names or names == ["all"]:
        names = [b.name for b in catalog.BLOCKS if os.path.exists(os.path.join(config.MODELS_DIR, b.name, "export.json"))]
    else:
        names = catalog.expand(names)          # R12: one name or glob per argument ("DC_*")
    for n in names:
        check(n)


try:
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
except Exception:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    sys.exit(1)
