"""Plan 4 preview set (Source/Model/preview/plan4/): the data changes the scripts plan makes to the models.

Task 3: the Programmable's re-lettered management module (Ruling P4-7: "SCRIPT HOST" / "PRG-06", lamp legend
"SCRIPT" / "STATUS"), to compare with preview/task-8/DC_Srv_Programmable_*. Same rig and stand-ins as Task 8
(dc/preview_task8.py), so the pairs differ only in the model.
Task 4: the same block as the scripts show it while Working (programmable_scripts_on_*): only the script-status slot
(functional.PROG_LED: the lamp and the LCD status bar) takes the EmissiveGreen stand-in; the rear PSU lamps
(functional.PROG_PSU_LAMP) stay amber. programmable_back is the data-only rear for comparison.

    DC_PREVIEW=plan4 blender -b --python Source/Model/build_dc.py -- DC_Srv_Programmable
Task 7: with the KVM built, also the scripted KVM motion previews (dc/preview_scripts.py; its docstring has the block
list and the DC_SHOTS names).
(DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution).
"""
import os

from . import config, functional
from . import preview as PV
from . import preview_mats as PM
from . import preview_task6 as P6
from . import preview_task8 as P8
from .preview import Shot, T, want

OUT = os.path.join(config.PREVIEW_DIR, "plan4")
PROG = P8.PROG

# (camera, target, lens): front and 3q as Task 8's, plus a close-up square on the management module's LCD
PROG_VIEWS = {
    "front": ((0.0, 1.9, 0.18), (0, 0, 0.125), 50),
    "3q": ((-1.0, 1.4, 0.75), (0, 0.05, 0.11), 45),
    "closeup_lcd": ((-0.08, 0.78, 0.25), (-0.167, 0.38, 0.13), 50),
}
BACK_VIEW = ((0.6, -1.7, 0.45), (0, 0, 0.12), 45)       # Task 8's "back": the PSU lamps


def scripted(built, lod=0):
    """The Programmable as the scripts show it while Working: the status slot lit green (Task 6's lit-green indicator
    stand-in), every other slot as the data-only block."""
    return P6.stated(built, PROG, lod, "keen", {functional.PROG_LED: "act"})


def programmable(built):
    for v, (loc, tgt, lens) in PROG_VIEWS.items():
        nm = f"programmable_{v}"
        if not want(nm):
            continue
        s = Shot(nm, res=(1600, 1200), floor=(-1.5, 1.5, -1.5, 1.5))
        P8.prog(s, built)
        s.camera(loc, tgt, lens)
        s.render()


def programmable_scripts_on(built):
    shots = [(f"programmable_scripts_on_{v}", PROG_VIEWS[v]) for v in ("front", "closeup_lcd")]
    shots += [("programmable_scripts_on_back", BACK_VIEW), ("programmable_back", BACK_VIEW)]
    for nm, (loc, tgt, lens) in shots:
        if not want(nm):
            continue
        s = Shot(nm, res=(1600, 1200), floor=(-1.5, 1.5, -1.5, 1.5))
        if "scripts_on" in nm:
            s.inst(scripted(built), T(0, 0, P8.H / 2))
        else:
            P8.prog(s, built)
        s.camera(loc, tgt, lens)
        s.render()


def render_all(built):
    PV.OUT = OUT
    PM.get("Caption")
    if PROG in built:
        programmable(built)
        programmable_scripts_on(built)
    if P8.KVM in built:   # Task 9: the KVM's use boxes (dc/preview_use_boxes.py)
        from . import preview_use_boxes
        preview_use_boxes.render_all(built)
    if P8.KVM in built:   # Task 7: the scripted KVM motion (dc/preview_scripts.py)
        from . import preview_scripts
        preview_scripts.render_all(built)
