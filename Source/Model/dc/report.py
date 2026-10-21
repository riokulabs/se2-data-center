"""build_report.json writer. Schema: {"blocks": {name: {cells, lods, placement, dummies, provenance}}}."""
import json
import os


def empty_entry(spec):
    return {"cells": list(spec.cells), "lods": [],
            "placement": {"occupied": 0, "total": 0, "faces": {}, "free_cells": []},
            "dummies": [], "provenance": []}


def write(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.write("\n")
