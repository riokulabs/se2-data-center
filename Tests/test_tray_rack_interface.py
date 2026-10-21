"""The rack <-> cable-tray interface (dc/dims.py) and the racks' top-entry brush plates.

The tray plan (dc/tray_plan.py) hangs its Drop blocks over the racks from these numbers alone, so the
waterfall bundles must land inside the brush plates the rack build actually made. The build-marked tests check the
couplings on the MEASURED LOD0 geometry (build_report.json "geometry"["top_entries"], from dc/rack.py's "brush"
part), the others on the constants only."""
import json
import os
import re

import pytest

from dc import catalog, config, dims as DM

HERE = os.path.dirname(os.path.abspath(__file__))
OPEN_RACKS = ("DC_Rack42_Open", "DC_Rack24_Open")
ALL_RACKS = OPEN_RACKS + ("DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear", "DC_Rack24_SplitFront",
                          "DC_Rack24_SplitFrontRear")
MARGIN = 0.003   # the waterfall bundle clears the opening's edges by at least this (it parts the bristles, not steel)


def _entry(name):
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        blocks = json.load(f)["blocks"]
    assert name in blocks, f"{name} not in build_report.json"
    e = blocks[name]
    assert e["placement"]["total"] > 0, f"{name} has no placement data (stub builder?)"
    return e


# ---------------------------------------------------------------------------------------------------- constants

def test_interface_constants():
    assert DM.WF_X == pytest.approx(sum(DM.MANAGER_CH_X) / 2)
    assert DM.WF_Y == pytest.approx((DM.MANAGER_SPINE_Y[1] + DM.RACK_TRAY_IY) / 2)
    # the tray's 2-cell span TRAY_RACK_Y +- 0.25 lies on grid planes of the odd-depth (5-cell) rack
    assert DM.TRAY_RACK_Y % 0.25 == pytest.approx(0.125)
    assert DM.TRAY_HANG % 0.25 == 0
    # the documented values (plan: lane contract, rack interface)
    assert (DM.TRAY_RACK_Y, DM.TRAY_HANG, DM.FLOOR_Z, DM.R_WF, DM.ROD_S) == (0.125, 0.5, 0.045, 0.0225, 0.232)
    assert DM.WF_X == pytest.approx(0.3585) and DM.WF_Y == pytest.approx(0.4325)
    assert DM.TOP_ENTRY == (DM.MANAGER_CH_X, (DM.MANAGER_SPINE_Y[1], DM.RACK_TRAY_IY))


def test_constants_moved_out_of_rack():
    """rack.py reads the tray / manager constants from dims (single source), it no longer defines its own."""
    from dc import rack
    src = open(rack.__file__).read()
    assert not re.search(r"IX\s*,\s*IY\s*=\s*\(?\s*0\.", src, re.M), "rack.py still defines IX, IY"
    assert not re.search(r"^CH_X\s*=\s*\(", src, re.M) and not re.search(r"^SPINE_Y\s*=\s*\(", src, re.M)
    assert rack.CH_X is DM.MANAGER_CH_X and rack.SPINE_Y is DM.MANAGER_SPINE_Y
    assert (rack.IX, rack.IY) == (DM.RACK_TRAY_IX, DM.RACK_TRAY_IY)


def test_waterfall_clear_of_doors():
    assert DM.WF_Y + DM.R_WF < DM.DOOR_Y_BACK


def test_waterfall_clear_of_fan_lane():
    """The front entries are nowhere near the rear exhaust-fan lane (FAN_Y, the fan openings)."""
    assert DM.WF_Y - DM.R_WF > DM.FAN_Y + DM.FAN_R + 0.006
    assert DM.TOP_ENTRY[1][0] > 0.0


# ---------------------------------------------------------------------------------------------------- measured

@pytest.mark.build
@pytest.mark.parametrize("name", ALL_RACKS)
def test_waterfall_inside_entry(name):
    e = _entry(name)
    ents = e["geometry"].get("top_entries")
    assert ents, f"{name}: rebuild to record geometry.top_entries"
    assert len(ents) == 2, ents
    H2 = 0.125 * catalog.BY_NAME[name].cells[1]          # the top plane (centred frame)
    sides = set()
    for x0, x1, y0, y1, z_top in ents:
        sx = 1 if x0 > 0 else -1
        assert x0 * x1 > 0, ("an entry straddles x = 0", x0, x1)
        sides.add(sx)
        ax0, ax1 = sorted((sx * x0, sx * x1))             # mirrored for -x
        assert ax0 + DM.R_WF + MARGIN <= DM.WF_X <= ax1 - DM.R_WF - MARGIN, (name, (x0, x1))
        assert y0 + DM.R_WF + MARGIN <= DM.WF_Y <= y1 - DM.R_WF - MARGIN, (name, (y0, y1))
        assert H2 - 0.002 <= z_top < H2, (name, z_top, H2)   # within 2 mm under the top plane, never on it
    assert sides == {-1, 1}


@pytest.mark.build
@pytest.mark.parametrize("name", ALL_RACKS)
def test_entries_mirror(name):
    """The two entries are mirror images in x (the tray lanes are mirror-symmetric: one Drop serves both)."""
    a, b = sorted(_entry(name)["geometry"]["top_entries"], key=lambda r: r[0])
    assert a[0] == pytest.approx(-b[1], abs=1e-4) and a[1] == pytest.approx(-b[0], abs=1e-4)
    assert a[2:] == pytest.approx(b[2:], abs=1e-4)


# The golden placement summaries (the analysis' one-line summary minus the block name). Hard-coded so any drift
# fails. They reflect the freed rear PDU columns (16 / 8 cells more free and the pdu_bracket inner Backward mounts;
# the 42U containment rail band: Forward / Backward 1 row = 10 %; the side faces lose the PDU cells: 84 %; the half
# rack's label pads add Up groups) and the slot placement fix (the slots' front-zone row is free, 16 / 8 cells; the
# slot floor / ceiling mount only on the rear row, so the full rack's Down groups drop to 2; on the half rack the
# front label pad's two cells are now free top cells, so its Up plane loses them: 6 groups, 50 %). Change these only
# deliberately.
# ACCEPTED REGRESSION, not a design target: the 24U "U ... 50%" means the half rack's FRONT label pad no longer
# mounts (the rack label goes on the back pad only). A dedicated half-rack front label mount is planned; when it
# lands, the 24U Up groups / coverage here are EXPECTED to change: re-record this golden then, it is not a broken
# golden.
GOLDEN_SUMMARIES = {
    "DC_Rack42_Open": "groups F/B/L/R/U/D = 1 / 3 / 4 / 4 / 5 / 2; plane coverage = 10% / 10% / 84% / 84% / 40% / "
                      "100%; occupied 120/200 box cells, 80 empty, 0 outside",
    "DC_Rack24_Open": "groups F/B/L/R/U/D = 0 / 2 / 3 / 3 / 6 / 1; plane coverage = 0% / 0% / 84% / 84% / 50% / "
                      "100%; occupied 60/100 box cells, 40 empty, 0 outside",
}


@pytest.mark.build
@pytest.mark.parametrize("name", ALL_RACKS)
def test_rack_unchanged_except_entries(name):
    """The brush plates are render-only: placement (occupied / free cells, face groups and coverage) is exactly the
    golden result (GOLDEN_SUMMARIES), and every LOD stays inside Keen's limits."""
    from dc import rack
    base = "DC_Rack42_Open" if name.startswith("DC_Rack42") else "DC_Rack24_Open"
    e = _entry(name)
    p = e["placement"]
    assert p["summary"].split(": ", 1)[1] == GOLDEN_SUMMARIES[base], (p["summary"], GOLDEN_SUMMARIES[base])
    assert len(p["free_cells"]) == len(rack.FREE_CELLS(catalog.BY_NAME[name]))
    for i, lod in enumerate(e["lods"]):
        assert lod["tris"] <= lod["max_tris"], (name, i, lod)
        assert lod["materials"] <= lod["max_materials"], (name, i, lod)


# the rack LOD0 material sets without the brush plates: they may only reuse these
_BASE_MATS = {"42": {"AtlasFont_BarlowCondensed_CleanWhite", "BrushedMetal", "EmissiveGreen", "MetalDull",
                     "MetalPerforationSteel", "PaintedMetalColorable", "PaintedMetalDarker", "PaintedMetalYellow"},
              "24": {"AtlasDecal_Stickers02", "AtlasFont_BarlowCondensed_CleanWhite", "BrushedMetal", "EmissiveGreen",
                     "MetalDull", "PaintedMetalColorable", "PaintedMetalDarker", "PaintedMetalYellow"}}


@pytest.mark.build
@pytest.mark.parametrize("name", ALL_RACKS)
def test_entries_reuse_existing_materials(name):
    lods = _entry(name)["lods"]
    base = set(_BASE_MATS["42" if "42" in name else "24"])
    if "Split" in name:   # door racks: the power lamp is EmissiveOff (the cloned material swapper lights it)
        base = (base - {"EmissiveGreen"}) | {"EmissiveOff"}
    assert set(lods[0]["material_names"]) == base, lods[0]["material_names"]
    for lod in lods[1:-1]:
        assert set(lod["material_names"]) <= base, lod["material_names"]


@pytest.mark.build
@pytest.mark.parametrize("name", ALL_RACKS)
def test_entries_match_dims(name):
    """The built openings are the documented ones: the full rack's dims.TOP_ENTRY (the tray plan's interface), the
    half rack's dims.HALF_TOP_ENTRY (its roof-rail holes, re-cut for the same plate)."""
    (ex0, ex1), (ey0, ey1) = DM.TOP_ENTRY if name.startswith("DC_Rack42") else DM.HALF_TOP_ENTRY
    for x0, x1, y0, y1, _ in _entry(name)["geometry"]["top_entries"]:
        ax0, ax1 = sorted((abs(x0), abs(x1)))
        assert (ax0, ax1, y0, y1) == pytest.approx((ex0, ex1, ey0, ey1), abs=1e-4)


# ------------------------------------------------------------------------------------------------------ tray coupling
def _landings(plan, corner):
    """The waterfalls' ENTRY ends of a Drop / Chute plan moved into a rack's centred frame by its box corner there
    (the rack's top plane at z = 0): [(lane, point, the plan's last 0.2 m of its centreline)]."""
    import numpy as np
    out = []
    for b in plan.bundles:
        if b.ends[1].kind == "ENTRY":
            pts = b.points + corner
            out.append((b.lane, pts[-1], pts[pts[:, 2] <= pts[-1][2] + 0.2]))
    return out


def _margin(p, entry):
    """How far a bundle of radius R_WF centred at p clears the edges of a front top entry ((|x| lo, hi), (y lo, hi))."""
    (x0, x1), (y0, y1) = entry
    return min(abs(p[0]) - x0, x1 - abs(p[0]), p[1] - y0, y1 - p[1]) - DM.R_WF


@pytest.mark.parametrize("density", ("Low", "Moderate", "Full"))
def test_drop_lands_in_full_rack_entries(density):
    """From dims.py alone: a Drop hung TRAY_HANG over a 42U (its box corner at x -0.5, y TRAY_RACK_Y - 0.25,
    its bottom on the rack's top plane) lands both waterfalls inside the full rack's front brush-plate openings
    (TOP_ENTRY) with >= MARGIN between the bundle's skin and every edge, plumb over their last 0.2 m."""
    import numpy as np
    from dc import tray_plan as TP
    pl = TP.plan("Drop", density)
    land = _landings(pl, np.array([-0.5, DM.TRAY_RACK_Y - 0.25, 0.0]))
    assert sorted(np.sign(p[0]) for _, p, _ in land) == [-1, 1]
    for lane, p, tail in land:
        assert p[2] == pytest.approx(0.0) and _margin(p, DM.TOP_ENTRY) >= MARGIN, (density, lane, _margin(p, DM.TOP_ENTRY))
        assert np.allclose(tail[:, :2], p[:2], atol=1e-9)
        assert (abs(p[0]), p[1]) == pytest.approx((DM.WF_X, DM.WF_Y))


def test_chute_lands_in_half_rack_entries():
    """The Chute stood on a 24U's roof in the Drop's waterfall column lands both bundles inside the half
    rack's front brush-plate openings (HALF_TOP_ENTRY) with >= MARGIN, plumb; its top meets the Drop's waterfalls
    hung over the same rack 1.25 m higher (a full rack's top), to the micron."""
    import numpy as np
    from dc import tray_plan as TP
    chute = TP.plan("Chute")
    full_h, half_h = (0.25 * catalog.BY_NAME[n].cells[1] for n in ("DC_Rack42_Open", "DC_Rack24_Open"))
    corner = np.array([-0.5, DM.TRAY_RACK_Y - 0.25 + 0.5, 0.0])        # on the half rack's top plane
    land = _landings(chute, corner)
    for lane, p, tail in land:
        assert _margin(p, DM.HALF_TOP_ENTRY) >= MARGIN, (lane, _margin(p, DM.HALF_TOP_ENTRY))
        assert np.allclose(tail[:, :2], p[:2], atol=1e-9)
    drop = TP.plan("Drop", "Low")
    tops = sorted((b.points[0] + corner for b in chute.bundles), key=lambda q: q[0])
    falls = sorted((p + [0.0, 0.0, full_h - half_h] for _, p, _ in _landings(drop, np.array([-0.5, DM.TRAY_RACK_Y
                                                                                                 - 0.25, 0.0]))),
                   key=lambda q: q[0])
    assert len(tops) == len(falls) == 2
    for a, b in zip(tops, falls):
        assert np.allclose(a, b, atol=1e-9)
