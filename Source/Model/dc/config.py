"""Paths shared by the Data Center build."""
import os

NAME = "DataCenter"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Source/Model
TOOLS_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "tools"))
MODELS_DIR = os.environ.get("DC_MODELS_DIR") or os.path.join(HERE, "Models")   # (env: the export determinism test
#                                                                               exports into temp dirs)
PREVIEW_DIR = os.path.join(HERE, "preview")
INTEGRATION_DIR = os.path.join(HERE, "integration")
REPORT_PATH = os.environ.get("DC_REPORT_PATH") or os.path.join(HERE, "build_report.json")
# Read-only hard links of the SDK's vanilla Blocks/ and Materials/. Never written to.
VANILLA_REF = os.path.join(TOOLS_DIR, "vanilla-ref")
MOD_DIR = os.path.normpath(os.path.join(HERE, "..", ".."))            # mods/DataCenter
MOD_ASSETS = os.path.join(MOD_DIR, "Assets")                           # the mod's Assets/ (clones land here)
CLONE_MAP = os.path.join(MOD_DIR, ".clonemap.json")
SE2MOD = os.path.join(TOOLS_DIR, "scripts", "se2mod.py")
STAGE_ASSETS = os.path.join(INTEGRATION_DIR, "Assets")                 # staged package (mirrors MOD_ASSETS)

# Plan 4 Task 2 (Ruling P4-1): the Programmable keeps its InGameScriptingComponent permanently in its data (Route A').
# No runtime injection exists or is wanted. See NOTES.md "Plan 4: save safety and the Programmable route".
PROGRAMMABLE_ROUTE = "A'"

# Plan 5 Ruling DB-10: how the racks' side panels and fan tray are built. "A" (default, shipped): ConditionalSubParts
# entries (bound client prefabs) spawned while the rack is Functional, with baked FR / DM stand-ins. "B" (the fallback
# if Path A fails the world load in game): static children of the rack's client prefab, always present, no stand-ins.
# Both keep On/Off on every rack. To fall back: set "B" here, then re-run the pipeline for the racks
# (INGAME-CHECKLIST.md "Next session", NOTES.md "Ruling DB-10").
RACK_PATH = "A"
