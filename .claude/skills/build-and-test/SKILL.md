---
name: build-and-test
description: Build and test Data Center with its real commands, and say which checks need tools that are not available in CI. Use when asked to run the tests, verify a change, or check whether the repo builds.
---
<!-- managed by riokulabs/.github - edit there (templates/), not here -->

# Build and test Data Center

1. Run the offline checks first: `scripts/test.sh`.
2. For a quick guard pass on what you changed: `python3 scripts/check_repo_guard.py --staged`.
3. Then, if the change needs it, the steps that only work on the maintainer's machine:

- Models: `blender -b --python Source/Model/build_dc.py -- all --no-render` (Blender 5.x).
- Stage and install: `python3 Source/Model/build_integration.py`, then `bash Source/Model/integration/install.sh` (dry run; `--apply` only when asked).
- SDK build: `pgrep -x Modern.bin` must print nothing, then `python3 ../../tools/scripts/se2mod.py build DataCenter`. Main checkout only, never a worktree.

Report what ran, what passed, and what you could not run (and why). Do not claim a build passed if only the offline checks ran.
