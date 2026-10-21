"""One source for the GUIDs the C# scripts look up (Plan 4 Ruling P4-6; plain Python, no bpy).

    python3 Source/Model/build_integration.py      stages the package, then writes Scripts/Simulation/Shared/DcGuids.g.cs

Every constant is read from where the data itself takes it: a block's clone record (.clonemap.json "info"), or a
stable key of asset_guids.json. The generator never mints: a constant whose GUID is not in the staging (or not yet a
key) is an error, so the scripts can only ever name a definition the package really ships.
Tests/test_programmable_data.py::test_script_guids_current fails when the checked-in file is stale.

Five kinds of constant:
  definition  the GUID of a definition the package stages (a prefab, a composite, an animation, ...): it must be the
              own GUID of a staged .def / .partialdef;
  id          a component id (a composition key), not a definition: it must be an asset_guids.json key. The ones the
              data does not use yet (a component only a script adds) are minted with the data's keys by
              integration.write_all, through reserve(), so they stay stable across rebuilds;
  material    a vanilla material the scripts assign: its GUID is read from dc/material_guids.py (the same table the
              exported .model files are mapped with; Tests/test_integration.py checks it against the SDK);
  name        a string the data defines and a script must match, e.g. a mesh part (= material slot) name: emitted as
              a C# const string, read from the Python constant that builds the model;
  int         a small number the data defines, e.g. which sides of a rack carry door leaves: a C# const int, computed
              from the Python that builds the data.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from . import catalog, clone, config, doors, functional, scripting
from .material_guids import MATERIAL_GUIDS
from .assetio import own_guid, read_json
from .guids import GUIDS_PATH, Guids

OUT = os.path.join(config.MOD_DIR, "Scripts", "Simulation", "Shared", "DcGuids.g.cs")
PROG, KVM = "DC_Srv_Programmable", "DC_Srv_KVM"
KVM_SEQUENCER_KEY = "Kvm.SequencerComponentId"


@dataclass(frozen=True)
class Const:
    name: str
    doc: str
    kind: str                                   # "definition" | "id" | "material" | "name" | "int"
    key: Optional[str] = None                   # asset_guids.json key ...
    clone_info: Optional[Tuple[str, str]] = None   # ... or (block, .clonemap.json info field)
    material: Optional[str] = None              # material: the slot name in MATERIAL_GUIDS
    value: Optional[object] = None              # name: the string itself; int: the number


def door_side_bits(spec):
    """doors.door_sides(spec) as bits: 1 = front (+1, the block's Forward), 2 = rear (-1)."""
    sides = doors.door_sides(spec)
    return (1 if 1 in sides else 0) | (2 if -1 in sides else 0)


CONSTANTS = (
    Const("ProgrammableServerPrefab", "The Programmable's server prefab (the block in the world; saved).",
          "definition", clone_info=(PROG, "server_prefab")),
    Const("ProgrammableClientPrefab", "The Programmable's client prefab (its visuals; never saved).",
          "definition", clone_info=(PROG, "client_prefab")),
    Const("ProgrammableScriptingDefinition", "The Programmable's InGameScriptingDefinition (entry type, limits).",
          "definition", key=scripting.DEFINITION_KEY),
    Const("ProgrammableScriptingComponentId", "The InGameScriptingComponent's id in the Programmable's server "
          "composition (Route A': always in the data).", "id", key=scripting.COMPONENT_KEY),
    Const("ProgrammableSwapper", "The Programmable's BlockMaterialSwapperDefinition: empty in data; the scripts map "
          "the status LED to green while Working (Ruling P4-7).", "definition", key=f"def/{PROG}/BlockMaterialSwapper"),
    Const("KvmClientPrefab", "The KVM's client prefab (the sequencer is added to it at load).",
          "definition", clone_info=(KVM, "client_prefab")),
    Const("KvmSequencerComponentId", "The id the KVM sequencer component gets in the KVM's client composition "
          "(added at load by the scripts; client entities are never saved).", "id", key=KVM_SEQUENCER_KEY),
    Const("KvmDrawerComposite", "The KVM drawer subpart's composite (its TranslationAnimation slot).",
          "definition", key=f"def/{KVM}/KvmDrawer/Composite"),
    Const("KvmScreenComposite", "The KVM screen subpart's composite (its RotationAnimation slot).",
          "definition", key=f"def/{KVM}/KvmScreen/Composite"),
    Const("KvmDrawerTranslationDef", "The drawer's TranslationAnimationDefinition (the travel the data owns).",
          "definition", key=f"def/{KVM}/KvmDrawer/Animation"),
    Const("KvmScreenRotationDef", "The screen's RotationAnimationDefinition (the fold the data owns).",
          "definition", key=f"def/{KVM}/KvmScreen/Animation"),
    *(Const(f"Rack{h}{v}Block", f"The DC_Rack{h}_{v} block definition: the rack a KVM sits in is a "
            f"{'full (42U)' if h == 42 else 'half (24U)'} rack (Ruling P4-12 routes a full rack's top slot to the data-only motion).",
            "definition", clone_info=(f"DC_Rack{h}_{v}", "block_def"))
      for h in (42, 24) for v in ("Open", "SplitFront", "SplitFrontRear")),
    *(Const(f"Rack{h}{v}DoorSides", f"The sides of DC_Rack{h}_{v} that carry door leaves (dc/doors.py door_sides): bit 1 = "
            "the rack's front (its block Forward), bit 2 = its rear. The KVM interlock waits only for a door on its "
            "own face's side (Ruling P4-13).", "int",
            value=door_side_bits(catalog.BY_NAME[f"DC_Rack{h}_{v}"]))
      for h in (42, 24) for v in ("Open", "SplitFront", "SplitFrontRear")),
    Const("ProgrammableStatusMeshPart", "The mesh part (material slot) of the Programmable's script-status lamp and LCD "
          "status bar: static amber in data; the client script maps it to EmissiveGreen while Working (Ruling P4-7).",
          "name", value=functional.PROG_LED),
    Const("EmissiveGreenMaterial", "Vanilla EmissiveGreen, the lit status colour the Programmable's status lamp takes "
          "while Working with scripts on (the racks' power-OK green).", "material", material="EmissiveGreen"),
)
# ids only the scripts use: integration.write_all mints them with the data's keys (reserve)
RUNTIME_IDS = (KVM_SEQUENCER_KEY,)

HEADER = """\
// <auto-generated>
// DcGuids: the definition, component and material GUIDs (and data names) the Data Center scripts look up (Ruling P4-6).
// GENERATED by Source/Model/dc/script_guids.py from the staged definitions, Source/Model/asset_guids.json,
// dc/material_guids.py and dc/functional.py.
// Do not edit: run python3 Source/Model/build_integration.py. Tests/test_programmable_data.py fails when stale.
//
// Game APIs: none (System.Guid only).
// </auto-generated>
#nullable enable
using System;

namespace DataCenter.Shared;

/// <summary>
/// GUIDs and names shared with the mod's data, generated from it, so a script never names a definition, material or
/// mesh part the package does not ship.
/// </summary>
public static class DcGuids
{
"""


def reserve(G):
    """Mint (or keep) the asset_guids.json keys of the ids only the scripts use."""
    for k in RUNTIME_IDS:
        G[k]
    return {k: G[k] for k in RUNTIME_IDS}


def _staged_definitions(stage_dir):
    out = set()
    for dp, _, fs in os.walk(stage_dir):
        for f in fs:
            if f.endswith((".def", ".partialdef")):
                g = own_guid(read_json(os.path.join(dp, f)))
                if g:
                    out.add(g)
    return out


def resolve(c, keys, cmap):
    """The GUID of constant c (no minting)."""
    if c.clone_info:
        block, field = c.clone_info
        e = clone.entry(catalog.BY_NAME[block], cmap)
        g = (e or {}).get("info", {}).get(field)
        if not g:
            raise RuntimeError(f"DcGuids.{c.name}: {block} has no clone info {field!r} (run dc/clone.py)")
        return g
    if c.kind == "material":
        if c.material not in MATERIAL_GUIDS:
            raise RuntimeError(f"DcGuids.{c.name}: dc/material_guids.py has no material {c.material!r}")
        return MATERIAL_GUIDS[c.material][0]
    if c.key not in keys:
        raise RuntimeError(f"DcGuids.{c.name}: asset_guids.json has no key {c.key!r} (run build_integration.py)")
    return keys[c.key]


def generate(stage_dir):
    """The text of DcGuids.g.cs for the staging at stage_dir (config.STAGE_ASSETS). Raises when a constant is not
    staged / not a key."""
    keys = Guids(GUIDS_PATH).d
    cmap = clone.load_map()
    staged = _staged_definitions(stage_dir)
    lines = [HEADER]
    for i, c in enumerate(CONSTANTS):
        if i:
            lines.append("\n")
        lines.append(f"    /// <summary>{c.doc}</summary>\n")
        if c.kind == "name":
            if not c.value or not all(ch.isalnum() or ch in "_-" for ch in c.value):
                raise RuntimeError(f"DcGuids.{c.name}: {c.value!r} is not a plain mesh part name")
            lines.append(f'    public const string {c.name} = "{c.value}";\n')
            continue
        if c.kind == "int":
            if not isinstance(c.value, int) or isinstance(c.value, bool):
                raise RuntimeError(f"DcGuids.{c.name}: {c.value!r} is not an int")
            lines.append(f"    public const int {c.name} = {c.value};\n")
            continue
        g = resolve(c, keys, cmap)
        if c.kind == "definition" and g not in staged:
            raise RuntimeError(f"DcGuids.{c.name}: {g} is not staged under {stage_dir}")
        lines.append(f'    public static readonly Guid {c.name} = new Guid("{g}");\n')
    lines.append("}\n")
    return "".join(lines)


def write(stage_dir=None):
    """Write DcGuids.g.cs from the current staging (config.STAGE_ASSETS); returns its path."""
    text = generate(stage_dir or config.STAGE_ASSETS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return Path(OUT)
