"""Makes se2modkit importable for the scripts Blender runs directly (`blender --python Source/Model/build_dc.py`).

`se2mod blender run` and an installed se2modkit already put it on the path, and then this does nothing. Otherwise it
uses `$SE2MODKIT_SRC` (a se2modkit checkout's `src/` folder), then the workspace's `tools/se2-modkit/src` next to
`mods/`, and stops with a plain message when neither is there.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _importable() -> bool:
    return importlib.util.find_spec("se2modkit") is not None


def ensure(repo: Path = REPO) -> str:
    """Put se2modkit on sys.path if it isn't importable yet; returns "installed" or the folder it added."""
    if _importable():
        return "installed"
    candidates = [Path(os.environ["SE2MODKIT_SRC"])] if os.environ.get("SE2MODKIT_SRC") else []
    candidates.append(Path(repo).resolve().parents[1] / "tools" / "se2-modkit" / "src")
    for src in candidates:
        if (src / "se2modkit").is_dir():
            sys.path.insert(0, str(src))
            return str(src)
    raise SystemExit("se2modkit is not importable. Run the script through `se2mod blender run SCRIPT -- ARGS`, "
                     "install se2modkit, or set SE2MODKIT_SRC to a se2modkit checkout's src/ folder.")
