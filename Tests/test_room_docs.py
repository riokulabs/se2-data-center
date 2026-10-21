"""The room pieces' docs (in-game testing doc, README player section) and the room probe."""
import os
import re

from dc import catalog, menu

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def _section(text, heading):
    m = re.search(rf"^## {heading}.*?(?=^## |\Z)", text, re.S | re.M)
    assert m, f"no '## {heading}' section"
    return m.group(0)


def test_testing_doc_names_every_room_group():
    text = _read(os.path.join("docs", "testing-in-game.md"))
    for g in ("floor", "roompower", "contain", "signs"):
        assert menu.GROUPS[g]["name"] in text, menu.GROUPS[g]["name"]
    for w in ("CRAC", "Rack PDU", "Containment doors", "roof panels", "Rack Labels"):
        assert w in text, w


def test_readme_room_section():
    readme = _read("README.md")
    sec = _section(readme, "Room Pieces")
    for w in ("Feed A", "Feed B", "1.0", "1.5 m", "2.0", "beyond the row end", "draws power", "floor first",
              "full-rack rows", "editable LCD", "open aisle", "back pad"):
        assert w in sec, w


def test_room_probe_is_a_room_copy():
    """Tests/InGame/probe_mountpoints_room.csx: the mount-point probe with the room blocks' names, and only theirs."""
    p = _read(os.path.join("Tests", "InGame", "probe_mountpoints_room.csx"))
    m = re.search(r"var needles = new\[\] \{(.*?)\};", p)
    assert m
    needles = re.findall(r'"([^"]+)"', m.group(1))
    for b in catalog.ROOM:
        assert any(n in b.name for n in needles), b.name
    assert not any(n in b.name for n in needles for b in catalog.BLOCKS if b not in catalog.ROOM)
    assert "MountPointsGroupsPerDirection" in p
