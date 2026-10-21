# Model pipeline

Every block in this mod is generated. The Python package in `Source/Model/dc/` describes each block, Blender builds
and exports its models, and a staging step writes the game-format files under `Assets/DataCenter/`. Change the
generator and regenerate; never hand-edit files under `Assets/`, `.meta` files or GUIDs.

The full reference, with every check the install step runs, is `Source/Model/integration/INTEGRATION.md`.

## What you need

- Python 3.11+ for the generator, the staging step and the tests.
- Blender 5.x (the models are built with 5.2 LTS) with the VRAGE Tools add-on for the export step.
- The Space Engineers 2 Mod SDK (Steam app 3578990) for cloning vanilla definitions and for the final build.
- `se2model`, the shared modeling library, and `se2mod.py`, the build helper. Both currently live outside this
  repository (`../../tools`), so on a bare clone only the offline tests that do not import them run.

## Folder layout

| Path | What it holds |
|---|---|
| `Source/Model/dc/catalog.py` | the block catalog: name, family, size in cells, vanilla source block |
| `Source/Model/dc/dims.py` | shared measurements (slot sizes, rail positions, clearances) |
| `Source/Model/dc/rack.py`, `server.py`, `servers/`, `tray*.py`, `crac.py`, `pdu.py`, `contain.py`, `floor.py`, `signs.py` | the geometry of each block family |
| `Source/Model/dc/fracture*.py`, `interior.py`, `construction.py` | broken and damaged models, construction stages |
| `Source/Model/dc/names.py`, `menu.py`, `recipes.py`, `texts.py` | build-menu names, groups, costs and descriptions |
| `Source/Model/dc/clone.py` | copies a vanilla block's definitions under new GUIDs |
| `Source/Model/dc/export_models.py` | FBX and glTF export (called by `build_dc.py --export`) |
| `Source/Model/dc/integration.py` | staging: writes the definitions and model files |
| `Source/Model/build_dc.py` | the Blender entry point |
| `Source/Model/Models/<block>/` | exported models and `export.json` per block |
| `Source/Model/UI/` | build-menu icons |
| `Source/Model/build_report.json` | measurements of the last build, read by many tests |
| `Source/Model/integration/` | `install.sh` and the pipeline reference |
| `Assets/DataCenter/` | the installed, game-format output (models tracked with Git LFS) |
| `Scripts/` | the optional C# layer, loaded only with `-loadScripts` |

## The steps

Run everything from the repository root. Each step writes only its own outputs, so any step can be rerun alone.

1. **Clone** (once per new block). Copies the vanilla block's definition chain under new GUIDs and records the
   mapping in `.clonemap.json`:

   ```bash
   python3 Source/Model/dc/clone.py DC_Srv_Compute
   ```

2. **Build and export.** Builds the meshes, LODs, collision, broken and damaged models, and exports them to
   `Source/Model/Models/<block>/`. The VRAGE Tools add-on needs a GPU context, so the export runs in a Blender
   window (it quits by itself when done):

   ```bash
   blender --python Source/Model/build_dc.py -- DC_Srv_Compute --no-render --export
   ```

   Use `all` instead of block names to rebuild everything. Without `--export` you can run headless
   (`blender -b`) to check geometry and update `build_report.json`.

3. **Check placement** after a re-export, so the exported mount points match the report:

   ```bash
   blender -b --python Source/Model/check_placement.py -- DC_Srv_Compute
   ```

4. **Stage.** Writes names, menu groups, costs, icons and model definitions into
   `Source/Model/integration/Assets/` (no Blender needed):

   ```bash
   python3 Source/Model/build_integration.py
   ```

5. **Install.** A dry run first; it lists problems and every new, changed and stale file. `--apply` copies the
   staged files into `Assets/DataCenter/` and backs up whatever it overwrites. Close the game, the HUB and the Editor
   first:

   ```bash
   bash Source/Model/integration/install.sh
   bash Source/Model/integration/install.sh --apply
   ```

6. **Build the mod with the SDK.** The game must not be running (`pgrep -x Modern.bin` prints nothing):

   ```bash
   python3 ../../tools/scripts/se2mod.py build DataCenter
   ```

   The log must show no warnings for `Assets\DataCenter\...`. Run this from your main checkout, not a git worktree.

## Adding or changing a block

1. Add or edit the entry in `Source/Model/dc/catalog.py`. Pick the vanilla block whose behavior the new block should
   have; the clone keeps that behavior.
2. Write or change the geometry in the family's module. Every modeled part should have a believable purpose in a
   real data center and fit the block. Broken blocks follow the game's own style: a solid core with the vanilla
   fracture material on the cuts and a few large pieces, not modeled internals.
3. Add the name, menu group and cost in `names.py`, `menu.py` and `recipes.py` if it is a new block.
4. Run steps 1 to 6 above (clone only for a new block).
5. Run the offline tests and extend the test file for that family (see below).
6. Commit the generator change together with the regenerated `Assets/`, `Models/`, `build_report.json` and
   `asset_guids.json`. Add a line to `CHANGELOG.md` for anything players will notice.

Preview renders land in `Source/Model/preview/`, which is ignored by git. README images go in `docs/media/`.

## Triangle budgets

`docs/triangle-budgets.md` lists each block's triangle count per LOD against its limit. It is generated from the
committed `export.json` files; after a re-export, refresh it with:

```bash
python3 Source/Model/dc/budget_table.py
```

A test fails when the table is out of date or a block goes over its limit.

## Tests

```bash
python3 -m pytest -q Tests -m "not build and not sdkbuild"                     # offline, serial
python3 -m pytest -q -n auto --dist loadfile Tests -m "not build and not sdkbuild"   # offline, parallel (pytest-xdist)
```

Markers: `build` needs a prior Blender build, `sdkbuild` runs the real SDK build (opt in with `DC_SDK_BUILD=1`),
`scripts` needs the `Scripts/` folder. Each test run stages its own copy of the package in a temporary folder, so
the tests never touch `Assets/`.

The C# layer has two more checks: `bash Tests/CompileCheck/run.sh all` compiles both script assemblies the way the
game does, and `cd Tests/CoreTests && dotnet run -c Release` runs the game-free logic tests.

## Rolling back

To undo an install, copy the newest `Source/Model/integration/backup/<time>/` back over `Assets/DataCenter/`, delete
the files the dry run listed as new (or `git checkout -- Assets/ && git clean -fd Assets/`), then rebuild.
