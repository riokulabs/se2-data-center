"""Plan 5 Task 14: the damage / build-states docs exist and the generated budget table is current."""
import os
import re

from dc import budget_table, catalog

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def _section(text, heading):
    m = re.search(r"^" + re.escape(heading) + r".*?(?=^## |\Z)", text, re.S | re.M)
    assert m, heading
    return m.group(0)


def test_checklist_has_states_section():
    sec = _section(_read("INGAME-CHECKLIST.md"), "## 14. Damage and build states (4.0)")
    assert "Not yet run in game" in sec
    assert "DEFERRED: native Linux" not in sec
    for name in ("DC_Srv_UPS", "DC_Srv_KVM", "DC_CRAC", "DC_Contain_Roof_100"):
        assert name in _read("INGAME-CHECKLIST.md"), name
    for word in ("UPS", "KVM", "CRAC", "Roof", "sill", "Cables arrive last", "On/Off", "unpowered"):
        assert word in sec, word
    for i in range(1, 11):
        assert f"Ruling DB-{i}," in sec, i


def test_rack_first_load_test_stays_first():
    text = _read("INGAME-CHECKLIST.md")
    first = text.index("## Next session: rack subparts first-load test")
    assert first < text.index("## Test session 2026-10-19") < text.index("## 0. Smoke test")
    sec = text[first:text.index("## Test session 2026-10-19")]
    for need in ("should not be on server compositions", "Definition that is linked from",
                 'RACK_PATH = "B"', "Tests/test_rack_path_b.py", "git rm", "build_dc.py", "install.sh --apply",
                 "se2mod.py build DataCenter", "se2mod.py play DataCenter --native"):
        assert need in sec, need
    assert "revert" not in sec.lower().replace("not a revert", "")   # Path B is a switch (final review I1)


def test_one_play_command_and_nothing_deferred():
    text = _read("INGAME-CHECKLIST.md")
    assert "DEFERRED" not in text
    plays = set(re.findall(r"se2mod\.py play [^`]*", text))
    assert plays <= {"se2mod.py play DataCenter --native", "se2mod.py play DataCenter --native --no-scripts"}, plays


def test_rack_path_b_is_documented_as_a_switch():
    notes = _read("NOTES.md")
    db10 = notes[notes.index("- **Ruling DB-10:**", notes.index("## Plan 5 summary")):]
    db10 = db10[:db10.index("\n- **")]
    assert 'RACK_PATH = "B"' in db10 and "10455382" not in db10, db10


def test_notes_summary_and_budget_table():
    notes = _read("NOTES.md")
    assert "Ruling DB-10" in notes
    for i in range(1, 11):
        assert f"Ruling DB-{i}" in notes, i
    a, b = notes.index(budget_table.BEGIN), notes.index(budget_table.END)
    region = notes[a:b]
    for blk in catalog.BLOCKS:
        assert re.search(r"^\| " + re.escape(blk.name) + r" \|", region, re.M), blk.name
    assert len(catalog.BLOCKS) == 73


def test_budget_table_is_current_and_within_limits():
    notes = _read("NOTES.md")
    assert budget_table.block() in notes, "stale: run python3 Source/Model/dc/budget_table.py"
    for r in budget_table.rows():
        assert r["fr"] <= r["fr_limit"], r["name"]
        assert r["dm"] <= r["dm_limit"], r["name"]


def test_readme_mentions_building_and_damage():
    assert "## Building and damage" in _read("README.md")
