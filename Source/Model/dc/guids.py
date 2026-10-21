"""Stable asset GUIDs (Source/Model/asset_guids.json): created once, reused by every rebuild, so a regenerated
package never changes a reference. Keys are readable paths ("dir/DataCenter/DC_Rack42_Open/Models", ...)."""
import json
import os
import uuid

from .config import HERE

GUIDS_PATH = os.path.join(HERE, "asset_guids.json")


class Guids:
    def __init__(self, path=GUIDS_PATH):
        self.path = path
        self.d = {}
        if os.path.exists(path):
            with open(path) as f:
                self.d = json.load(f)

    def __getitem__(self, key):
        if key not in self.d:
            self.d[key] = str(uuid.uuid4())
        return self.d[key]

    def __contains__(self, key):
        return key in self.d

    def save(self):
        """Atomic (a temp file renamed over the old one): a concurrent reader (another pytest run, a build) never sees
        a half-written file."""
        tmp = f"{self.path}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
        with open(tmp, "w") as f:
            json.dump(dict(sorted(self.d.items())), f, indent=1)
            f.write("\n")
        os.replace(tmp, self.path)
