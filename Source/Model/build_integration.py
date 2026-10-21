"""Stage the integration package (no Blender needed).

    python3 Source/Model/build_integration.py

Needs the clones (python3 Source/Model/dc/clone.py, once) and the exports of the built blocks
(blender --python Source/Model/build_dc.py -- <blocks> --no-render --export). Writes integration/Assets/DataCenter/,
asset_guids.json and, from that staging, the scripts' Scripts/Simulation/Shared/DcGuids.g.cs (dc/script_guids.py);
next: bash Source/Model/integration/install.sh (dry run), then --apply.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "tools")))

from dc import integration, script_guids  # noqa: E402

if __name__ == "__main__":
    s = integration.write_all()
    guids_cs = script_guids.write()
    for n, b in s["blocks"].items():
        extra = f"  models {b['models']}  stages {b['stages']}  fractures {b['fractures']}" if b["built"] else ""
        print(f"{n:26s} {b['name']!r}{extra}")
    print(f"staged {s['staged_files']} files; unlocked {len(s['unlock'])} blocks")
    print(f"wrote {os.path.relpath(guids_cs, os.path.join(HERE, '..', '..'))}")
    print(json.dumps({"staged_files": s["staged_files"]}))
