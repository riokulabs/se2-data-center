# Data Center: regenerate, install, build, roll back

Everything below runs from `mods/DataCenter` unless stated. The pipeline has four steps; each one only writes its
own outputs, so any step can be rerun on its own.

| Step | Command | Writes | Needs |
|---|---|---|---|
| 1. Clone (once per block) | `python3 Source/Model/dc/clone.py [BLOCK ...]` | `Assets/DataCenter/<name>/` (vanilla definition chains under new GUIDs, with metas), `.clonemap.json` | the Mod SDK |
| 2. Build + export | `blender --python Source/Model/build_dc.py -- <blocks> --no-render --export` (**windowed**, it quits itself) | `Source/Model/build_report.json`, `Source/Model/Models/<name>/` | Blender 5.x + VRAGE Tools (GPU context) |
| 2b. Placement check | `blender -b --python Source/Model/check_placement.py -- all` | `Models/<name>/placement_exported.json` | step 2 |
| 3. Stage | `python3 Source/Model/build_integration.py` | `Source/Model/integration/Assets/DataCenter/`, `Source/Model/asset_guids.json` | steps 1-2 |
| 4. Install | `bash Source/Model/integration/install.sh` (dry run), then `--apply` | `Assets/DataCenter/` (backups in `integration/backup/<time>/`) | step 3, SE2/HUB/Editor closed |
| 5. Build the mod | `pgrep -x Modern.bin` (must print nothing), then `python3 ../../tools/scripts/se2mod.py build DataCenter` | `Content/`, the `.meta` processor info | step 4, SE2 closed |
| Tests | `python3 -m pytest -q Tests` | (each run stages its own copy in a temp dir, Tests/conftest.py; the step 3 staging is left alone) | steps 1-3 (and 2b for the placement test) |

Pass block names to step 2, or `all` to build every catalog entry. `docs/model-pipeline.md` is the short version of
this page.

## 1. Clones (`dc/clone.py`)

- Every catalog block gets its own clone of its vanilla source (`catalog.vanilla_source`), via two
  `tools/scripts/se2mod.py copy` runs under one `--map-key <name>`:
  1. the vanilla BlockKind folder into `<name>/UI/` (`<name>_BlockKindDefinition.def`);
  2. the block folder, recursive, into `<name>/` (`--from <copy_from> --to <name>`). The kind is mapped first, so the
     copy rewires the block definition's BlockKind; definitions that inherit their kind from a Copy base (doors,
     timer, event controller, LCD) get `BlockKind` written explicitly (`ensure_kind`), as `clone_block.py` does.
- Second prefixes in the same folder are renamed in the same copy with `--also`: the door's `SlideDoorNarrow_250_*`
  subparts and `NarrowSlidingDoor_*` LOD materials, the LCD's `LCD50_LastLOD`, the event controller's
  `EventController100_LastLOD`. One copy (not two) because the door's ConditionalSubParts point at the subpart
  prefabs and the subparts' SLERP definitions point back at the door's dummy definitions.
- `.clonemap.json` is keyed: `maps[<name>] = {copies: [...], guids: {vanilla: new}, info: {...}}`. `info` holds the
  block's new block-definition, kind, server-prefab and BlockModelDefinition GUIDs and files. A block with `info` is
  skipped on rerun (the guard). To re-clone a block: delete `Assets/DataCenter/<name>/` (+ `.meta`) and
  `maps[<name>]`, then rerun.
- Every cloned definition gets a `.meta` whose AssetID is its own GUID; folders get stable AssetIDs from
  `asset_guids.json`. Server and client compositions are untouched, so functional blocks behave as vanilla.

## 2. Export (`dc/export_models.py`, called by `build_dc.py --export`)

Per built block, into `Source/Model/Models/<name>/`:
- `NonFractured/<name>.fbx`, `<name>_LOD<i>.fbx`: the measured parts of each LOD merged into one object (one mesh
  part per material, as vanilla); `<name>_collision.gltf/.bin`: the regular boxes plus the `occupancy*` and
  `mountpoints*` hints (both MSFT extensions; `msft_physics_exporter_props.enabled` set before each export).
- `Fractured/<name>_Fractured[_LOD<i>].fbx` + `<name>_Fractured_collision.gltf/.bin`:
  - every rack, server and cable tray (`dc/fracture.py` + `dc/fracture_mesh.py`): a fracture PLAN per block. Racks: the full rack 8 zones (plinth and top-tray halves, each
    column's lower and upper half), the half rack 4 (plinth, columns, roof); no critical zone but a door rack's
    columns. Servers and trays 2-4 zones (`Fracture_01` is the key zone and the only critical one: a 6U server's
    central core between its front service module and rear chassis, the UPS's front bay module, the tray zone
    holding the trapeze / floor strut, the junction hub, the Drop's tray section above its two waterfalls). Each LOD is cut
    along the plan's seams with a ragged break line, every cut cross-section closed by a vanilla `FracturedMaterial01`
    break face (`Fracture_NN_Cut`: Group `Fracture_NN`, Split / HiddenUntilSecondSequenceStart / Fracture), one convex
    collider per zone shaped to the zone's own cut geometry and stopped at its seams (`fracture.shaped_hull`:
    zone health is the collider's volume share, so no box over empty space). A light tray whose cut LOD0 needs one more LOD (Keen keys the count on each model's own LOD0)
    takes the kit's mid detail as the extra LOD.
  - `Damaged/<name>_Damaged[_LOD<i>].fbx` + collision (every breakable block): vanilla's
    "Deformed" model, the Fractured meshes densified (at most 2 x the Fractured triangles) and dented (mean 7 / p90 13 / max 24 mm on the servers, as vanilla Timer50 / Battery50), pinned
    on the bounding box; its `.model` maps the lamp and screen slots to `EmissiveOffBroken` / `Display01Broken` /
    `LCDScreen_Off` (`fracture.DAMAGED_SLOTS`).
  - `ColliderMeshGroups` must list only groups the LOD0 has: one missing group makes the importer drop every
    fracture and check the model as unfractured (8 mesh parts, so a 2-zone server fails with 9 or 11 against 8).
    A fractured model may hold 32 materials and 256 mesh parts per LOD (`ModelLimitsChecker`, decompiled).
  - Every fractured block is **breakable** (`integration.ensure_breakable`): the BreakableBlockComponent the hotfix
    removed goes back right after the BlockModelComponent in both compositions (the clone's own BreakableBlock-
    Definition, its `CriticalFractures` from the plan; the KVM, a ControlPanel25 clone, gets a new Copy of the base
    definition), its five tag slots leave `RemovedKeys`, the prefabs' ObjectBuilders get it back. The UPS's cell
    slots are supported by their bay's fracture (vanilla Battery50); the functional 6U servers' Terminal / LcdPanel
    dummies by their front service module. `make_non_breakable` (vanilla `Non-Breakable/Structural` /
    ControlPanel25 pattern) is used for the unfractured exception below;
    `Tests/test_definition_validators.py` ports `BreakableBlockModelValidator` and requires 44 of the 48 servers and
    trays breakable (and the 6 racks).
  - The justified exception (`fracture.UNFRACTURED`): the three rod hangers and the Chute stay unfractured and
    non-breakable. Their members (two rods 0.44 m apart, two ladders 0.6 m apart) share nothing, and Havok connects
    two fractures only when their colliders lie within 0.1 m (`BreakableColliderArgs.MaxEdgeDistance`); a fracture
    set with no connection fails the build ("Connectivity graph should have at least one connection").
  - A light tray's cut LOD0 must sit clearly on one side of Keen's LOD-count row (the importer counts a few % fewer
    triangles than the FBX holds): at most 0.97 x the row, else at least 1.15 x (one more LOD); in between the
    exporter tries an edge-split cut, then drops the thin wire-end caps (`export.json` `cut_mode`).
- `export.json`: files, used materials, tris, objects and groups per LOD, fracture zones, and the Fractured LOD0
  construction mesh parts (`{Group}-{Material}` -> type / visibility / preset) for the build-stage generator.
- The LOD count comes from Keen's checker on the **measured** LOD0 bounds (`assemble.fit_lods`): the full rack is
  13.4 m2, just under a row threshold, so it has LOD0-2 + the LOD3 box.

## 3. Staging (`dc/integration.py`)

For every catalog block: the BlockKind's `Name` and `Description` and the block definition's `UIData.Name`
(`dc/names.py`; `UIData` has no Description). For built blocks also:
- `Models/NonFractured/` and `Models/Fractured/` with the FBX, glTF, bin and a `.model` each: hand-written
  `MaterialAssignments` (`dc/material_guids.py`), LOD0 translation = the per-axis grid shift (0.125 on even cell
  counts, 0 on odd ones), `SnapToGrid: false`, `GeneratePreciseCollider: true`;
- the cloned `<name>_BlockModelDefinition.partialdef` with `Model`, `FractureModel`, `DamagedModel`, the
  `ParticleEffects` dummy moved to the block center (= the shift), and `BuildProgressModels` generated by
  `se2model.construction` (stages 0 / 0.1 / 0.2 / 0.3 / 0.5333 / 0.7667 / 1);
- `UIData.Icon`, if `Source/Model/UI/<name>_Icon.png` exists (the icon render covers every block);
- `DataCenter/DataCenter_InitialUnlock.partialdef`: an Override of ProgressionInitialUnlockConfiguration adding the
  built blocks' server prefabs and kinds.

AssetIDs come from `asset_guids.json` and never change once created. A staged `.meta` is written only when the mod
does not already have one with the same AssetID, so a reinstall keeps the builder's hashes and processor info.

## 4. Install (`integration/install.sh`)

The dry run checks: every file and folder has a `.meta` (staged or installed); no duplicate AssetIDs; staged AssetIDs
match the installed ones; definition GUID == AssetID; every `{G}` in a `.model` is a staged asset and every used
material has an assignment; every BlockModelDefinition's `Model`/`FractureModel`/`DamagedModel` is a staged `.model`.
It prints `N problems`, then the new / overwritten / unchanged / stale files. `--apply` refuses while SE2, the HUB,
the Editor or the builder runs, backs up every overwritten file and moves stale generated model files (e.g. a
dropped LOD) into `integration/backup/<time>/`.

## 5. Build and verify

```bash
pgrep -x Modern.bin || python3 ../../tools/scripts/se2mod.py build DataCenter
```
- The log must show no `warn`/`fail` lines for `Assets\DataCenter\...` (the Vanilla "Found loose metafile" lines are
  the SDK's own) and `Exiting with 0.` twice (build + `--generateCaches`).
- Every `Models/*/*.model.meta` has `P_MODEL`, a `.vrm` output and `Problems: []`.

## Cable trays

The 38 tray blocks are in the pipeline (`catalog.PIPELINE_FAMILIES` has `tray` and `trayrods`), so
`clone.py`, `write_all`, the install and the build treat them like the core blocks. What is different:

- **Clone sources:**
  - every tray piece, Drop, Reducer and the Chute: `WallInsertPipes` (`Blocks/Walls/Inserts/Pipes`), a single file
    prefix, 13 definitions each (kind + 12) including its own `PlacementDefinition`;
  - the rod hangers: `StructuralSupportStraight` (`Blocks/Truss/Struts/Long`). Its LastLod material is named with a
    second prefix, so `clone.ALSO["StructuralSupportStraight"]` renames `TrussFrame_Long` to the block name in the
    same copy (`--also TrussFrame_Long=<name>`). It has no placement definition of its own (the template's).
  - First run: `python3 Source/Model/dc/clone.py $(python3 -c "from dc import catalog;print(' '.join(b.name for b in
    catalog.CATALOGUE if b.family.startswith('tray')))")` from `Source/Model`.
- **Patches** (`integration.tray_patch`, every tray block, built or not):
  - `PCU` 5 on the block definition;
  - no `MountPointGeneratorSettings` (all six directions mount; the model's mount hints decide where; neither source
    sets one);
  - the cloned `<name>_PlacementDefinition.def` gets `AutoRotateFace: null` (vanilla "Down" flips a tray upside
    down when aimed at a ceiling) and is staged; the block's `PlacerDefinition` must be that clone (checked).
- **Models:** fractured by plan like the other blocks (see above). The NonFractured LODs stay within 8 mesh parts; the Fractured / Damaged ones within
  Keen's fractured limits (32 materials, 256 mesh parts). The `ParticleEffects` dummy of the cloned WallInsertPipes model definition moves to the block center.
- **Menu, costs and icons:** see "Cable trays: menu, costs, icons" below.
- **Rod hangers:** the cloned model definition has no `ParticleEffects` dummy of its own; the staging adds one.

## Cable trays: menu, costs, icons

- **Menu** (`dc/menu.py`): five more group tiles in the "Data Center" subcategory, after Server Racks (Order 100) and
  Rack Servers (200): "Cable Trays: Empty / Low / Moderate / Full" (300-600) and "Cable Tray Supports" (700). A density
  tile lists its kinds in `TRAY_ORDER` (Straight, TurnH, TurnUp, TurnDown, Tee, Cross, Drop, Reducer; Empty has no
  Drop or Reducer). The Straight kind (owned by `StraightL`) holds the 0.5 m and 1.5 m straights as sizes 1 and 2; the
  Rods kind (owned by `DC_TrayRods_100`) holds 0.25 / 1.0 / 2.0 m. `patch_kind` replaces every tray kind's cloned
  vanilla groups (Structural > Walls, Trusses), and empties the non-owner kinds.
- **Names** (`dc/names.py`): "Cable Tray, <shape> (<load>)", e.g. "Cable Tray, Straight (Full)". No block name carries
  a size: the sizes of a kind share its name ("Cable Tray, Straight (Full)", "Cable Tray, Hanger Rods")
  and the game's size selector tells them apart; the descriptions keep the lengths.
- **Costs** (`dc/recipes.py`): the core rule against WallInsertPipes (its recipe is the wall panel's; trays at Hollow
  density, written to the block definition) and StructuralSupportStraight (in game 2 Steel Plate: scale 2), with a
  run-length floor for tray pieces (one of each Pipes item per 0.5 m of run, `recipes.RUN_LENGTH`).
  Each tray patches its own cloned recipe file.
- **Icons:** `DC_PREVIEW=icons blender -b --python Source/Model/build_dc.py -- "DC_Tray*"` renders the icons
  (`UI/<name>_Icon.png`) and the store shots (`preview/blocks/`) of the built blocks; `DC_ICONS_PART=icons|blocks`
  limits it. Sheets: `python3 Source/Model/icon_sheet.py trays` and `... menu` (written under `preview/`).
- After a re-export, re-run `blender -b --python Source/Model/check_placement.py -- <names>`
  (`test_exported_placement_matches_report` compares the mtimes).

## Roll back

- Before the first install, `git -C mods/DataCenter add -A` checkpoints the clones. To undo an install, copy the
  newest `integration/backup/<time>/` back over `Assets/DataCenter/` and delete the files the dry run listed as `new`
  (or `git checkout -- Assets/ && git clean -fd Assets/` back to the checkpoint), then rebuild.
- To remove the mod's blocks from a world, see `se2mod.py status` (worlds keep references to local mods).

## Checking in game

Placement, LOD switching, construction stages and breaking are checked offline here (the placement generator port,
the builder's validators). `docs/testing-in-game.md` lists what to check in game.
