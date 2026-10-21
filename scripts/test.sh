#!/usr/bin/env bash
# managed by riokulabs/.github - edit there (templates/), not here
# The checks CI and the pull request template ask for. Run from anywhere in the clone.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
python3 -m pytest -q Tests -m "not build and not sdkbuild" "$@"
