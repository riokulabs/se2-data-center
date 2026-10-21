---
name: new-definition
description: Add a new block or change a block definition in this SE2 mod through the generator pipeline (catalogue entry, clone, build, stage, install, SDK build). Use when asked to add a block, add a definition, or change a definition under Assets/.
---
<!-- managed by riokulabs/.github - edit there (templates/), not here -->

# Add or change a block definition

Definitions under `Assets/` are game-format files (`.def`, `.partialdef`, `.meta`) that are written by the pipeline in `Source/Model/`. Change the generator, then regenerate; do not hand-edit them, and never hand-edit GUIDs.

1. Read the "Block catalogue" and clone sections of `Source/Model/integration/INTEGRATION.md` and the matching task in `NOTES.md`.
2. Add the entry to the catalogue (`Source/Model/dc/catalog.py`). Every modelled part needs a believable purpose; the block must behave like the vanilla block it is cloned from.
3. Clone once: `python3 Source/Model/dc/clone.py <BLOCK>`.
4. Build and export in Blender (windowed): `blender --python Source/Model/build_dc.py -- <BLOCK> --no-render --export`.
5. Stage: `python3 Source/Model/build_integration.py`; install: `bash Source/Model/integration/install.sh` (dry run), then `--apply` with the game and Editor closed.
6. Tests: `python3 -m pytest -q Tests -m "not build"`. Add or extend a test for the new block.
7. SDK build: `pgrep -x Modern.bin` must print nothing, then `python3 ../../tools/scripts/se2mod.py build <ModName>`.
8. Add a line to `CHANGELOG.md` under `[Unreleased]` and, for player-visible text, `README.md`.

Do not build or publish from a git worktree. Do not commit preview renders. Steps 3-7 need the maintainer's workspace (Blender, the Mod SDK, `../../tools`); if you do not have it, stop after the generator change and tests that run offline, and say so.
