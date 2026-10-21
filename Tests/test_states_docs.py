"""The in-game testing doc covers construction and damage, and the generated triangle budget table is current."""
import os
import re

from dc import budget_table, catalog

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def test_testing_doc_has_states_sections():
    text = _read(os.path.join("docs", "testing-in-game.md"))
    for heading in ("### Construction stages", "### Damage and broken interiors", "### Scripts on and off"):
        assert heading in text, heading
    for word in ("cage", "30 %", "fracture texture", "still copies", "LOD"):
        assert word in text, word


def test_budget_table_lists_every_block():
    doc = _read(budget_table.doc_path())
    a, b = doc.index(budget_table.BEGIN), doc.index(budget_table.END)
    region = doc[a:b]
    for blk in catalog.BLOCKS:
        assert re.search(r"^\| " + re.escape(blk.name) + r" \|", region, re.M), blk.name
    assert len(catalog.BLOCKS) == 73


def test_budget_table_is_current_and_within_limits():
    doc = _read(budget_table.doc_path())
    assert budget_table.block() in doc, "stale: run python3 Source/Model/dc/budget_table.py"
    for r in budget_table.rows():
        assert r["fr"] <= r["fr_limit"], r["name"]
        assert r["dm"] <= r["dm_limit"], r["name"]


def test_readme_mentions_building_and_damage():
    assert "## Building and damage" in _read("README.md")
