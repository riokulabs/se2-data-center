"""What a broken block shows inside, in the game's own style:
a zone's inside is a solid core whose exposed faces are FracturedMaterial01, plus a few large recognisable parts; no
zone opens onto an empty hollow, and the inside is not a modelled machine. dc/interior.py surveys the cut Fractured
LOD0 at export (export.json fractured.interior): per zone its interior detail, its core faces, whether its death
exposes the interior, and how much of its seams its neighbours cover when it dies."""
import json
import os

import pytest

from dc import catalog, config
from dc import interior as IN

# Families with a closed shell round a machine: every exposing zone must leave a covered seam (a core, not a hollow)
# and the interior holds only a few large parts. (The racks, trays, floors, doors, roofs and signs are open frames or
# thin panels; the 6U servers are a known follow-up.)
INTERIOR_FAMILIES = ("pdu_cabinet", "crac")
# Blocks whose plinth is split in two halves (rack._plinth): a half's break shows the other half's core
PLINTH_HALVES = {"DC_Rack42_Open": ("Fracture_01", "Fracture_02"), "DC_Rack42_SplitFront": ("Fracture_01", "Fracture_02"),
                 "DC_Rack42_SplitFrontRear": ("Fracture_01", "Fracture_02"),
                 "DC_PDU_Cabinet": ("Fracture_01", "Fracture_02")}


def _export(name):
    p = os.path.join(config.MODELS_DIR, name, "export.json")
    if not os.path.exists(p):
        pytest.skip(f"{name} not exported")
    with open(p) as f:
        return json.load(f)


# ------------------------------------------------------------------------------------------------ the rule itself
def _box_tris(lo, hi):
    from dc import zfight as Z
    return [pts for _, _, pts, _ in Z.box_tris(lo, hi, 0)]


LO, HI = (-0.5, -0.5, -1.0), (0.5, 0.5, 1.0)
SEAMS = [((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), ["Fracture_01"], ["Fracture_02"])]   # Fracture_01 on +x


def _walls(sx):
    """One half's outer skin: its side wall, and the front / back / top / bottom walls of its half."""
    x0, x1 = sorted((0.0, sx * 0.5))
    out = _box_tris(*sorted([(sx * 0.49, -0.5, -1.0), (sx * 0.5, 0.5, 1.0)], key=lambda p: p[0]))
    for lo, hi in (((x0, -0.5, -1.0), (x1, -0.49, 1.0)), ((x0, 0.49, -1.0), (x1, 0.5, 1.0)),
                   ((x0, -0.5, -1.0), (x1, 0.5, -0.99)), ((x0, -0.5, 0.99), (x1, 0.5, 1.0))):
        out += _box_tris(lo, hi)
    return out


def _core(sx):
    """One half's piece of a solid core: its body faces and its break cap on the seam (x = 0)."""
    x0, x1 = sorted((0.0, sx * 0.49))
    faces = _box_tris((x0, -0.49, -0.99), (x1, 0.49, 0.99))
    cap = [t for t in faces if all(abs(p[0]) < 1e-9 for p in t)]
    return [t for t in faces if t not in cap], cap


def test_inner_box_shrinks_and_vanishes_on_thin_blocks():
    assert IN.inner_box((-0.5, -0.6, -1.25), (0.5, 0.6, 1.25)) == pytest.approx(
        ([-0.4, -0.5, -1.15], [0.4, 0.5, 1.15]))
    assert IN.inner_box((-0.5, -0.5, -0.02), (0.5, 0.5, 0.02)) is None          # a tile: no interior


def test_survey_fails_an_empty_shell():
    """Two halves of a hollow box: either half's death opens onto the other's empty inside."""
    rows = IN.survey(LO, HI, {"Fracture_01": _walls(1), "Fracture_02": _walls(-1)}, {}, SEAMS)
    assert rows["Fracture_01"]["exposes"] and rows["Fracture_01"]["cover"] < 0.05
    assert {z for z, _ in IN.faults(rows)} == {"Fracture_01", "Fracture_02"}


def test_survey_fails_a_modelled_machine_in_a_hollow():
    """The 597f7c6e way: the hollow filled with modelled parts (here 8 x 12 boxes per half, a pipe run's worth of
    triangles) still opens onto a hollow between them, and its detail is over the cap."""
    def parts(sx):
        out = []
        for k in range(40):
            x = sx * (0.15 + 0.008 * (k % 5))
            z = -0.9 + 0.045 * k
            out += _box_tris(*sorted([(x, -0.3, z), (x + sx * 0.02, 0.3, z + 0.02)], key=lambda p: p[0]))
        return out
    rows = IN.survey(LO, HI, {"Fracture_01": _walls(1) + parts(1), "Fracture_02": _walls(-1) + parts(-1)}, {}, SEAMS)
    why = dict(IN.faults(rows))
    assert "empty hollow" in why["Fracture_01"] and "modelled interior" in why["*"]


def test_survey_passes_a_solid_core():
    """The same halves on a solid core cut at the seam: the dead half leaves the live half's FracturedMaterial01 cap
    (and a core face counts as something inside: core_m2), so nothing opens onto a hollow."""
    b1, c1 = _core(1)
    b2, c2 = _core(-1)
    rows = IN.survey(LO, HI, {"Fracture_01": _walls(1), "Fracture_02": _walls(-1)},
                     {"Fracture_01": c1 + b1, "Fracture_02": c2 + b2}, SEAMS)
    assert rows["Fracture_01"]["cover"] > 0.95 and rows["Fracture_01"]["core_m2"] > 1.0
    assert IN.faults(rows) == []


def test_survey_counts_a_part_just_behind_the_seam():
    """A recognisable face just behind the seam (the CRAC's coil face 2 mm behind the core zone's front) covers it;
    the same face DEPTH + 5 cm back does not."""
    def plate(x):
        return _box_tris((x - 0.004, -0.49, -0.99), (x, 0.49, 0.99))
    for x, want in ((-0.002, True), (-(IN.DEPTH + 0.05), False)):
        rows = IN.survey(LO, HI, {"Fracture_01": _walls(1), "Fracture_02": _walls(-1) + plate(x)}, {}, SEAMS)
        assert (rows["Fracture_01"]["cover"] > 0.95) is want, x


# ------------------------------------------------------------------------------------------------ the exported models
@pytest.mark.build
@pytest.mark.parametrize("name", [b.name for b in catalog.BLOCKS if b.family in INTERIOR_FAMILIES])
def test_broken_zones_show_a_core(name):
    """Every zone whose death exposes the interior leaves its seams covered (a core, its FracturedMaterial01 faces,
    or a large part just behind; the 597f7c6e machine interiors and the older empty shells opened onto hollows), and
    the exposing zones carry at most MAX_DETAIL_TRIS interior triangles together."""
    rows = _export(name)["fractured"].get("interior")
    assert rows, f"{name}: no interior survey in export.json (re-export)"
    assert any(r["exposes"] for r in rows.values())
    assert all("cover" in r for r in rows.values()), f"{name}: survey without cover (re-export)"
    assert IN.faults(rows) == []
    assert sum(r["core_m2"] for r in rows.values() if r["exposes"]) > 0.5, name   # the core is there


@pytest.mark.build
@pytest.mark.parametrize("name", sorted(PLINTH_HALVES))
def test_plinth_half_shows_a_core(name):
    """A plinth half's break shows the other half's solid core (its FracturedMaterial01 cap), not the hollow of a
    load frame (597f7c6e's welded rails left 17 cm of nothing behind the seam)."""
    rows = _export(name)["fractured"]["interior"]
    a, b = PLINTH_HALVES[name]
    for z, other in ((a, b), (b, a)):
        got = [c for ids, c in rows[z].get("seam_cover", []) if ids == [other]]
        assert got and got[0] >= IN.MIN_COVER, (name, z, rows[z])
