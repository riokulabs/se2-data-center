"""Plan 3 Task 12: the room pieces' docs (in-game checklist, README player section, NOTES summary) and the probe."""
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


def _room_section():
    return _section(_read("INGAME-CHECKLIST.md"), r"13\. Room pieces")


def test_checklist_room_section_names_every_group():
    sec = _room_section()
    for g in ("floor", "roompower", "contain", "signs"):
        assert menu.GROUPS[g]["name"] in sec, menu.GROUPS[g]["name"]


def test_checklist_room_items_1_to_16():
    """The plan's 16 items, numbered in order; 15 (the looms) is marked N/A because Task 9 did not run."""
    sec = _room_section()
    nums = [int(n) for n in re.findall(r"^(\d+)\. ", sec, re.M)]
    assert nums[:16] == list(range(1, 17)), nums
    items = {int(n): body for n, body in re.findall(r"^(\d+)\. (.*?)(?=^\d+\. |^### |\Z)", sec, re.S | re.M)}
    must = {1: ("6 x 8 m", "tile seams"), 2: ("1.5 m cold aisle", "Roof"), 3: ("both ends", "reload"),
            4: ("hot aisle", "1.0 and 2.0 m"), 5: ("KVM", "85"), 6: ("power screen", "Off", "hum", "reload"),
            7: ("Feed A", "Feed B", "half"), 8: ("Drop",), 9: ("AISLE 1 COLD", "RACK A-01", "open aisle", "15 m",
                                                             "blue", "red", "back pad"),
            10: ("Glass", "Decision 13"), 11: ("Weld", "Grind"), 12: ("Damage",), 13: ("PCU", "floor 5", "door 150"),
            14: ("LOD", "frame time"), 15: ("N/A", "Task 9"), 16: ("probe_mountpoints_room.csx",)}
    for n, words in must.items():
        for w in words:
            assert w.lower() in items[n].lower(), (n, w)


def test_checklist_room_blocks_named():
    """Every room block is reachable from the checklist by its block name or its menu tile."""
    sec = _room_section()
    for fam, word in (("floor", "Raised Floor"), ("crac", "CRAC"), ("pdu_cabinet", "PDU Cabinet"),
                      ("pdu_strip", "Rack PDU"), ("contain_door", "door"), ("contain_roof", "Roof"),
                      ("sign", "Aisle Sign")):
        assert any(b.family == fam for b in catalog.ROOM)
        assert word.lower() in sec.lower(), word
    for w in ("Hanging Aisle Sign", "Rack Label", "O2 / COOLANT SERVICE", "decorative", "RACK ID"):
        assert w in sec, w


def test_checklist_test_session_on_top():
    """Plan 5 Task 12: the racks' first-load test opens the next session (the world-load risk of the bound
    ConditionalSubParts: fresh world with all 6 racks, reload of a save, weld / grind / shoot swaps, the two failure
    log lines); the 2026-10-19 test session comes right after it: launch both modes, the re-tests, what to capture,
    the update."""
    text = _read("INGAME-CHECKLIST.md")
    heads = re.findall(r"^## (.*)$", text, re.M)
    assert heads[0].startswith("Next session: rack subparts first-load test (do this FIRST)"), heads[0]
    assert "DEFERRED" not in heads[0]   # (final review M7: one native play command, nothing deferred)
    first = _section(text, re.escape("Next session: rack subparts"))
    for w in ("should not be on server compositions", "Definition that is linked from", "Fresh world",
              "Reload an existing save", "Weld a door rack 0 -> 100", "Weld an open rack 0 -> 100", "Grind slightly",
              "Shoot a column zone", "rotors spin", "stand-ins", "Path B"):
        assert w in first, w
    assert heads[1].startswith("Test session 2026-10-19 (start here"), heads[1]
    sec = _section(text, re.escape("Test session 2026-10-19"))
    for w in ("se2mod.py play DataCenter --native", "--no-scripts", "already running",
              "rear stop", "24U", "stack", "flicker", "KVM", "On/Off", "fans", "both sides", "Room pieces",
              "~/.config/SpaceEngineers2/Temp/Logs", "screenshot", "Hostile Encounters", "17:00 UTC"):
        assert w in sec, w
    assert len(sec.splitlines()) <= 50, "keep the test session to one screen"


def test_readme_room_section():
    readme = _read("README.md")
    sec = _section(readme, "Room Pieces")
    for w in ("Feed A", "Feed B", "1.0", "1.5 m", "2.0", "beyond the row end", "draws power", "floor first",
              "full-rack rows", "editable LCD", "open aisle", "back pad"):
        assert w in sec, w


def test_notes_plan3_summary():
    notes = _read("NOTES.md")
    sec = _section(notes, "Plan 3 summary")
    for n in range(1, 15):
        assert re.search(rf"\b{n}\. \*\*", sec) or f"P3-{n} " in sec or f"P3-{n}:" in sec, f"Decision {n}"
    for w in ("Shipped CRAC chain", "Gyroscope250", "GyroscopeComponent", "Provenance", "Budgets", "Builder findings",
              "Cost balance", "shared_row_doors_fit"):
        assert w in sec, w


def test_room_probe_is_a_room_copy():
    """Source/Model/review/probe_mountpoints_room.csx: the earlier prototype's probe (via the Data Center copy) with the room
    blocks' names; the original is never edited (read-only here)."""
    p = _read(os.path.join("Source", "Model", "review", "probe_mountpoints_room.csx"))
    m = re.search(r"var needles = new\[\] \{(.*?)\};", p)
    assert m
    needles = re.findall(r'"([^"]+)"', m.group(1))
    for b in catalog.ROOM:
        assert any(n in b.name for n in needles), b.name
    assert not any(n in b.name for n in needles for b in catalog.BLOCKS if b not in catalog.ROOM)
    assert "earlier prototype" in p and "MountPointsGroupsPerDirection" in p
