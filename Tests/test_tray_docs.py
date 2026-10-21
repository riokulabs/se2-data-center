import os
import re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def _tray_section():
    text = _read("INGAME-CHECKLIST.md")
    m = re.search(r"^## 11\. Cable trays.*", text, re.S | re.M)
    assert m, "INGAME-CHECKLIST.md has no cable tray section"
    return m.group(0)


def test_checklist_has_every_topic():
    sec = _tray_section()
    for word in ("Straight", "TurnH", "Tee", "Cross", "TurnUp", "TurnDown", "Reducer", "Drop", "Chute",
                 "Hanger Rods", "Paint", "LOD", "End caps", "Mount faces", "Weld", "Grind", "Save",
                 "probe", "Zones break off", "Damaged model", "Critical zone", "Non-breakable"):
        assert word.lower() in sec.lower(), word


def test_checklist_decisions_listed():
    sec = _tray_section()
    for ruling in ("P2-1,", "P2-2,", "P2-18", "P2-21", "P2-23", "P2-25", "P2-28", "P2-26", "4 non-breakable"):
        assert ruling in sec, ruling


def test_readme_tray_section():
    readme = _read("README.md")
    for word in ("Reducer", "Drop", "floor to floor", "0.5 m above"):
        assert word in readme, word


def test_notes_rulings_listed():
    notes = _read("NOTES.md")
    for n in ("P2-1 ", "P2-2 ", "P2-18", "P2-21", "P2-26", "P2-27", "P2-29"):
        assert n in notes, n
