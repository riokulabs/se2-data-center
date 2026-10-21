"""Room fracture previews: the room's floor and roof fracture refinement (in-plane tile / bay zones, own Damaged
models) AS EXPORTED, against the pre-merge layer split (deck over understructure, glazing over frame).

    blender -b --python Source/Model/room_fracture_preview.py -- --before=<dir> [SUBJECT ...]   (default: every subject)
    python3 Source/Model/room_fracture_sheet.py                                                 before / after sheet

<dir>/<name>/Fractured/<name>_Fractured[.fbx | _collision.gltf / .bin]: the pre-merge exports (copied before the
re-export). Panels go to preview/room-fracture/panels/<subject>_<panel>.png; the renderer is fracture_compare_preview.py's
(intact / before_zones / zones / broken / damaged: each zone's skin in its colour, break faces in vanilla
FracturedMaterial01, each zone's collider as a wire cage), run here on the room's subjects.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "fracture_compare_preview.py")).read()
src = src[:src.rindex("\nmain(")]                      # the renderer without its own entry point
ns = {"__file__": os.path.join(HERE, "fracture_compare_preview.py"), "__name__": "fracture_compare_preview"}
exec(compile(src, ns["__file__"], "exec"), ns)          # noqa: S102 (our own module, read from the checkout)

FLOOR_DIR, ROOF_DIR = (-0.70, -0.62, 0.55), (-0.62, -0.70, 0.62)
ns["SUBJECTS"] = {
    "DC_Floor_Solid_050": (None, FLOOR_DIR, 0.30), "DC_Floor_Perf_050": (None, FLOOR_DIR, 0.30),
    "DC_Floor_Solid_100": (None, FLOOR_DIR, 0.22), "DC_Floor_Perf_100": (None, FLOOR_DIR, 0.22),
    "DC_Contain_Roof_100": (None, ROOF_DIR, 0.22), "DC_Contain_Roof_150": (None, ROOF_DIR, 0.20),
    "DC_Contain_Roof_200": (None, ROOF_DIR, 0.18),
}
ns["OUT"] = os.path.join(ns["config"].PREVIEW_DIR, "room-fracture", "panels")

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
for a in argv:
    if a.startswith("--before="):
        ns["BEFORE"] = a.split("=", 1)[1]
for n in [a for a in argv if not a.startswith("--")] or list(ns["SUBJECTS"]):
    ns["subject"](n)
