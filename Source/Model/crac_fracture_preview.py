"""CRAC fracture previews: DC_CRAC's Fractured and Damaged models AS EXPORTED, beside vanilla Gyroscope250's
(the clone source, read-only from tools/vanilla-ref).

    blender -b --python Source/Model/crac_fracture_preview.py

Panels go to preview/crac/fracture/<subject>_<panel>.png; the renderer is fracture_compare_preview.py's:
  intact   the NonFractured LOD0;
  zones    the Fractured LOD0 exploded along its zones, each zone's skin in its colour, break faces in vanilla
           FracturedMaterial01, each zone's collider as a wire cage (ours);
  broken   the same explosion in the game materials;
  damaged  the Damaged (vanilla "Deformed") LOD0, lamps in the broken material.
Plus, ours only:
  dead_f2_filters   the Fractured model as the game shows it after fan section F2 (critical: the block stops, its
                    rotors despawn) and the upper filter-door half died: the zones hidden in place, the break faces of
                    the neighbours showing;
  dead_core         the coil core dead: the fan sections and the filter halves stay (graph-wise: largest island).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "fracture_compare_preview.py")).read()
src = src[:src.rindex("\nmain(")]                      # the renderer without its own entry point
ns = {"__file__": os.path.join(HERE, "fracture_compare_preview.py"), "__name__": "fracture_compare_preview"}
exec(compile(src, ns["__file__"], "exec"), ns)          # noqa: S102 (our own module, read from the checkout)

DIR = (-0.70, 0.62, 0.42)
ns["SUBJECTS"] = {
    "DC_CRAC": (None, DIR, 0.16),
    "Vanilla_Gyroscope250": (("Gyroscopes/Gyroscopes/250/Models/NonFractured/Base/Gyroscope250_Base.fbx",
                              "Gyroscopes/Gyroscopes/250/Models/Fractured/Gyroscope250_Fractured.fbx",
                              "Gyroscopes/Gyroscopes/250/Models/Deformed/Gyroscope250_Deformed.fbx"), DIR, 0.14),
}
ns["OUT"] = os.path.join(ns["config"].PREVIEW_DIR, "crac", "fracture")
os.makedirs(ns["OUT"], exist_ok=True)


def dead(name, gone, panel, direction=(0.62, -0.70, 0.42)):
    nf_p, fr_p, dm_p, gl = ns["sources"](name)
    fr = [o for o in ns["load"](fr_p) if ns["info"](o)[1] != "scaffold" and ns["info"](o)[0] not in gone]
    sc = ns["new_scene"](f"{name}_{panel}")
    objs = ns["place"](sc, fr)
    for o in objs:
        ns["apply_real"](o)
    ns["shoot"](sc, objs, direction, os.path.join(ns["OUT"], f"{name}_{panel}.png"))


for n in ns["SUBJECTS"]:
    ns["subject"](n)
dead("DC_CRAC", {2, 6}, "dead_f2_filters")
dead("DC_CRAC", {2}, "dead_f2_front", direction=(-0.70, 0.62, 0.30))
dead("DC_CRAC", {0}, "dead_core", direction=(-0.75, 0.55, 0.35))
