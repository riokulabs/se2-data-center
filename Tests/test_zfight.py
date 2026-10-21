"""Nothing in a built model fights for the same pixels (in-game: the rack side labels flickering into
each other, the door leaves' meeting edge "fighting").

The Blender build tags every decal quad with its element (one stencil line, one atlas sticker, one stripe band) and
records the built models' check in build_report.json ("zfight", dc/zfight.py):
  elements        each decal element's in-plane box per model / LOD (facing n, plane depth d);
  decal_geometry  decal quads coplanar with, or buried under, a same-facing mesh face they overlap;
  leaf_coplanar   same-facing coplanar overlapping faces between parts of a door leaf model (every LOD);
  leaf_frame      the same between a leaf (closed AND open pose, placed in the block frame) and the rack frame + both
                  side panels.
The decal element rule is re-checked here from the recorded boxes (zfight.decal_conflicts)."""
import json
import os
import re

import pytest

from dc import catalog, config, doors
from dc import zfight as Z

HERE = os.path.dirname(os.path.abspath(__file__))
DC_SRC = os.path.join(HERE, "..", "Source", "Model", "dc")

# The rack side panel's decal elements as an earlier build made them (DC_Rack42_*, model RackSide_LOD0, facing +x):
# the in-game report's two overlaps must be caught by the rule.
HEAD_SIDE = [
    ("rack_side.py:146 A1", 0.492, (-0.85057, -0.00953, -0.74143, 0.09953)),
    ("rack_side.py:147 ROW A  POS 1", 0.492, (-0.72709, -0.03042, -0.70491, 0.12042)),
    ("rack_side.py:151 PDU ACCESS", 0.488, (0.01888, -0.04433, 0.04912, 0.13433)),
    ("rack_side.py:152 ISOLATE BEFORE OPENING", 0.488, (0.06094, -0.05455, 0.07706, 0.14455)),
    ("rack_side.py:153 danger_hv", 0.488, (0.05958, -0.055, 0.19842, 0.145)),
    ("rack_side.py:214 FLOW", 0.496, (-0.07606, -0.44757, -0.05994, -0.40543)),
    ("rack_side.py:215 COOLANT", 0.496, (0.06846, -0.45035, 0.07954, -0.40265)),
    ("rack_side.py:234 tri_electric", 0.496, (0.28411, -0.239, 0.33589, -0.179)),
    ("rack_side.py:235 caution_maint", 0.496, (0.25537, 0.015, 0.32863, 0.255)),
    ("rack_side.py:236 barcode_long", 0.496, (0.30813, 0.035, 0.35587, 0.235)),
]


def _els(rows, model="RackSide_LOD0", n=(1.0, 0.0, 0.0)):
    return [{"label": lb, "model": model, "n": list(n), "d": d, "box": list(b)} for lb, d, b in rows]


def _report():
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        return json.load(f)["blocks"]


def _zf(name):
    e = _report().get(name, {})
    if not e.get("placement", {}).get("total"):
        pytest.skip(f"{name} not built")
    assert "zfight" in e, f"{name}: no zfight check in build_report.json (rebuild with build_dc.py)"
    return e["zfight"]


# ------------------------------------------------------------------------------------------------ the rule itself
def test_rule_catches_the_head_side_panel():
    """The original layout fails: ISOLATE BEFORE OPENING over the DANGER sign, the barcode over the CAUTION text."""
    bad = {(a, b) for a, b, _, _ in Z.decal_conflicts(_els(HEAD_SIDE))}
    assert ("rack_side.py:152 ISOLATE BEFORE OPENING", "rack_side.py:153 danger_hv") in bad
    assert ("rack_side.py:235 caution_maint", "rack_side.py:236 barcode_long") in bad


def test_rule_depth_and_facing():
    a = ("a", 0.0, (0.0, 0.0, 0.10, 0.05))
    b = ("b", 0.0, (0.05, 0.02, 0.15, 0.07))
    assert Z.decal_conflicts(_els([a, b]))                                         # same depth, overlapping
    assert Z.decal_conflicts(_els([a, ("b", 0.0003, b[2])]))                       # closer than the epsilon
    assert not Z.decal_conflicts(_els([a, ("b", 0.0006, b[2])]))                   # a sticker >= 0.5 mm proud
    assert not Z.decal_conflicts(_els([a]) + _els([b], n=(-1.0, 0.0, 0.0)))        # opposite facings
    assert not Z.decal_conflicts(_els([a]) + _els([b], model="other"))             # other model
    assert Z.decal_conflicts(_els([a, ("c", 0.0, (0.1005, 0.0, 0.2, 0.05))]))      # crowding: 0.5 mm apart
    assert not Z.decal_conflicts(_els([a, ("c", 0.0, (0.10, 0.0, 0.2, 0.05))]))    # an exact edge joint (stripes)
    assert not Z.decal_conflicts(_els([a, ("c", 0.0, (0.102, 0.0, 0.2, 0.05))]))   # 2 mm clear


def test_overlap_area():
    sq = [(0, 0), (1, 0), (1, 1), (0, 1)]
    assert Z.overlap_area(sq, [(0.5, 0.5), (2, 0.5), (2, 2), (0.5, 2)]) == pytest.approx(0.25)
    assert Z.overlap_area(sq, sq[::-1]) == pytest.approx(1.0)                      # either winding
    assert Z.overlap_area(sq, [(2, 2), (3, 2), (3, 3)]) == 0.0


def test_no_rectangle_hazard_triangles():
    """The Stickers02 warning triangles are packed point-up / point-down: a rectangle around one catches its
    neighbours' corners (the "diagonal lines" cutting the side panel's triangle). Draw them with style.hazard_triangle."""
    hits = []
    for dp, _, fs in os.walk(DC_SRC):
        for f in fs:
            if f.endswith(".py"):
                src = open(os.path.join(dp, f)).read()
                hits += [f"{f}: {m}" for m in re.findall(r"element\([^)]*\"tri_(?:electric|hot)\"", src)]
    assert not hits, hits


# ------------------------------------------------------------------------------------------------ the built models
BUILT = [b.name for b in catalog.BLOCKS]


@pytest.mark.build
@pytest.mark.parametrize("name", BUILT)
def test_decal_elements_do_not_fight(name):
    """No two decal elements of a model overlap (or crowd within 1 mm) in-plane at depths closer than 0.5 mm."""
    assert Z.decal_conflicts(_zf(name)["elements"]) == []


@pytest.mark.build
@pytest.mark.parametrize("name", BUILT)
def test_decals_clear_of_coplanar_geometry(name):
    """No decal quad lies in the plane of (or under) a same-facing mesh face it overlaps."""
    assert _zf(name)["decal_geometry"] == []


@pytest.mark.build
@pytest.mark.parametrize("name", [b.name for b in catalog.BLOCKS if doors.has_doors(b)])
def test_door_leaves_have_no_coplanar_faces(name):
    """Leaf models (every LOD): no two parts share a same-facing face plane where they overlap (the meeting stile's
    end face and the seal strip did: the in-game edge z-fight); closed and open leaves against the frame too."""
    zf = _zf(name)
    assert any(e["model"].startswith(doors.LEAF_L) for e in zf["elements"]), "leaf models not checked"
    assert zf["leaf_coplanar"] == []
    assert zf["leaf_frame"] == []


@pytest.mark.build
def test_side_panel_labels_checked():
    """Every side panel label reaches the check (the 24U hatch is the tightest layout)."""
    els = [e for e in _zf("DC_Rack24_SplitFront")["elements"] if e["model"] == "RackSide_LOD0"]
    labels = {e["label"].split(" ", 1)[1] for e in els}
    assert {"RACK ID", "PDU ACCESS", "ISOLATE BEFORE OPENING", "danger_hv", "caution_maint",
            "barcode_long", "FLOW", "COOLANT"} <= labels


@pytest.mark.build
@pytest.mark.parametrize("name", [b.name for b in catalog.BLOCKS if b.family == "rack"])
def test_racks_carry_no_baked_id(name):
    """No rack bakes a specific ID ("A1", "ROW A POS 1": every rack read
    A1). The front header / kick plate and the half rack's roof say "RACK", the side hatch placard "RACK ID", each
    with a blank write-on tag; the ID comes from the editable rack-label LCD (DC_Sign_Rack)."""
    labels = {e["label"].split(" ", 1)[1] for e in _zf(name)["elements"]}
    assert not {lb for lb in labels if lb == "A1" or "ROW A" in lb or "POS 1" in lb}, sorted(labels)
    assert "RACK" in labels


# ------------------------------------------------------------------------------------------------ model faces
# In game (DC_Rack42_Open from below, beside a Feed A strip): the containment rail's clamp pads were exactly
# as tall as the rail and sat in its back plane (their top / bottom / back faces in the rail's planes: the Darker pad
# and the Colorable rail flickered, under each clip a dark block read loose), and the strip's Yellow feed band stood
# exactly as proud as the Colorable face plate (only its side wraps showed, as loose tabs; its LEDs 0.1 mm proud too).
def _old_clamp_layout(sy=1):
    """The rail and pads as dc/rack.py built them before the fix, z relative to ZT."""
    from dc import dims as DM
    from dc import rack
    z0, z1 = rack.CONTAIN_Z
    y0, yp = DM.CONTAIN_RAIL_Y
    xa, lip = rack.XO - 0.002, 0.026
    return [("lip_lo", (-xa, y0, z0), (xa, rack.CONTAIN_LIP_Y, z0 + lip)),
            ("lip_hi", (-xa, y0, z1 - lip), (xa, rack.CONTAIN_LIP_Y, z1)),
            ("channel", (-xa, y0, z0 + lip), (xa, y0 + 0.011, z1 - lip))] + \
        [("pad", (xp - 0.021, y0, z0), (xp + 0.021, yp - 0.0002, z1)) for xp in rack.CONTAIN_PADS]


def test_rule_catches_the_old_clamp_pads():
    """The coplanar rule flags the in-game layout: the pads' top, bottom and back faces in the rail's planes."""
    bad = Z.boxes_coplanar(_old_clamp_layout())
    assert {("lip_hi", "pad"), ("lip_lo", "pad")} <= {tuple(sorted(k)) for k in bad}, bad


@pytest.mark.parametrize("lod", [0, 1])
@pytest.mark.parametrize("sy", [1, -1])
def test_containment_rail_boxes_share_no_face_plane(lod, sy):
    """The clips wrap the rail (CONTAIN_WRAP over its top and bottom, the back face buried in it): no box of the rail,
    its pads or standoffs shares a same-facing face plane with another where they overlap."""
    from dc import rack
    boxes = rack.contain_rail_boxes(sy, lod)
    assert {k for k, _, _ in boxes} >= {"pad"}
    assert Z.boxes_coplanar(boxes) == {}


def test_containment_rail_keeps_its_band():
    """The fix moves no interface: the pads still span the rail band CONTAIN_Z (the measured contain_rails, the roof's
    mount band) and stand to the band's outer plane; the rail body sits CONTAIN_WRAP inside it."""
    from dc import dims as DM
    from dc import rack
    for sy in (1, -1):
        bx = rack.contain_rail_boxes(sy, 0)
        z = [c for _, lo, hi in bx if _ != "standoff" for c in (lo[2], hi[2])]
        assert (min(z), max(z)) == pytest.approx(rack.CONTAIN_Z)
        pads = [(lo, hi) for k, lo, hi in bx if k == "pad"]
        assert len(pads) == len(rack.CONTAIN_PADS)
        outer = max(abs(c) for lo, hi in pads for c in (lo[1], hi[1]))
        assert outer == pytest.approx(DM.CONTAIN_RAIL_Y[1] - 0.0002)
        lips = [(lo, hi) for k, lo, hi in bx if k.startswith("lip")]
        assert min(lo[2] for lo, _ in lips) == pytest.approx(rack.CONTAIN_Z[0] + rack.CONTAIN_WRAP)
        assert max(hi[2] for _, hi in lips) == pytest.approx(rack.CONTAIN_Z[1] - rack.CONTAIN_WRAP)


def test_pdu_feed_band_clears_the_face_plate():
    """The feed band's front face stands >= 1 mm proud of the face plate (it was flush: coplanar), the per-outlet
    LEDs >= 0.5 mm (they were 0.1 mm)."""
    from dc import pdu
    for lod in (0, 1, 2):
        front = min(y for _, y in pdu.feed_band_outline(lod))
        plate = pdu.FACE_Y - pdu.FACEPLATE_T
        assert plate - front >= 0.001 - 1e-9, (lod, front, plate)
    src = open(os.path.join(DC_SRC, "pdu.py")).read()
    assert "FACEPLATE_T + 0.0006)" in src     # the LEDs' depth (lit_quad in _decor)


# Pre-existing visible coplanar faces of different materials (the catalogue-wide check), per block:
# (part a / material, part b / material) with the part names' block prefix and LOD removed. They are known
# follow-ups; the test fails on any pair not listed, so none can come back or appear new.
KNOWN_COPLANAR = {
    "rack": {("dark/PaintedMetalDarker", "frame/PaintedMetalColorable"), ("dark/PaintedMetalDarker", "hw/MetalDull"),
             ("frame/PaintedMetalColorable", "hw/PaintedMetalYellow"),
             ("ceiling/PaintedMetalColorable", "hw/BrushedMetal"), ("ceiling/PaintedMetalColorable", "rail/BrushedMetal"),
             ("fine/PaintedMetalDarker", "socket/PaintedMetalYellow")},
    "pdu_cabinet": {("breaker/BrushedMetal", "breaker/MetalDull"), ("caps/PaintedMetalDarker", "frame/PaintedMetalColorable"),
                    ("caps/PaintedMetalDarker", "hw/MetalDull"), ("frame/PaintedMetalColorable", "hw/PaintedMetalYellow")},
    "pdu_strip": {("dark/PaintedMetalDarker", "hw/MetalDull"), ("chan/PaintedMetalColorable", "dark/PaintedMetalDarker")},
    "crac": {("dark/PaintedMetalDarker", "dark/PaintedMetalYellow"), ("dark/PaintedMetalDarker", "hw/MetalDull"),
             ("fine/PaintedMetalDarker", "frame/PaintedMetalColorable")},
    "contain_door": {("dark/PaintedMetalDarker", "frame/PaintedMetalColorable"), ("dark/PaintedMetalDarker", "hw/MetalDull")},
    "contain_roof": {("cap/PaintedMetalColorable", "glass/FrostedGlass"), ("hw/MetalDull", "tape/PaintedMetalDarker")},
    "sign": {("dark/PaintedMetalDarker", "hw/MetalDull")},
    "server": {("dark/PaintedMetalDarker", "fine/PaintedMetalColorable"), ("dark/PaintedMetalDarker", "frame/PaintedMetalColorable"),
               ("dark/PaintedMetalDarker", "decal/EmissiveScriptStatus"), ("dark/PaintedMetalDarker", "hw/BrushedMetal"),
               ("dark/PaintedMetalDarker", "fine/MetalDull"), ("fine/BrushedMetal", "fine/PaintedMetalDarker"),
               ("fine/PaintedMetalDarker", "hw/BrushedMetal")},
    "tray": {("guide/PaintedMetalDarker", "solid/BrushedMetal")},
    "trayrods": {("strut/PaintedMetalDarker", "trim/PaintedMetalYellow")},
}


def _short(part):
    """'DC_Rack42_Open_LOD0_contain/PaintedMetalDarker' -> 'contain/PaintedMetalDarker' (block, subpart and LOD gone)."""
    name, mat = part.split("/", 1)
    return re.sub(r"^.*_LOD\d+_", "", name) + "/" + mat


@pytest.mark.build
@pytest.mark.parametrize("name", BUILT)
def test_no_new_visible_coplanar_faces(name):
    """Close LODs (0, 1) of the block and its subparts: no VISIBLE same-facing coplanar overlap of two different
    materials (they flicker in game) beyond the known follow-ups. The in-game cases are not in the list: the rail
    clips (contain / Darker vs Colorable) and the strip's feed band and LEDs (arrow, lamp vs chan)."""
    zf = _zf(name)
    assert "coplanar" in zf, "no coplanar check in build_report.json (rebuild with build_dc.py)"
    fam = catalog.BY_NAME[name].family
    known = KNOWN_COPLANAR.get(fam, set())
    new = sorted({tuple(sorted((_short(r["a"]), _short(r["b"])))) for r in zf["coplanar"]
                  if r["a"].split("/")[1] != r["b"].split("/")[1]} - known)
    assert new == [], [r for r in zf["coplanar"] if tuple(sorted((_short(r["a"]), _short(r["b"])))) in new]


@pytest.mark.build
@pytest.mark.parametrize("name", [b.name for b in catalog.BLOCKS if b.family in ("rack", "pdu_strip")])
def test_rail_clips_and_feed_band_are_clean(name):
    """The two in-game cases by name: no visible coplanar row on the containment rail part, none between the strip's
    feed band or LEDs and its face plate (any material)."""
    rows = [r for r in _zf(name)["coplanar"]
            if "_contain/" in r["a"] + r["b"] or {_short(r["a"]).split("/")[0], _short(r["b"]).split("/")[0]}
            in ({"arrow", "chan"}, {"lamp", "chan"}, {"lamp", "dark"})]
    assert rows == []


@pytest.mark.build
@pytest.mark.parametrize("name", [b.name for b in catalog.BLOCKS if b.family == "rack"])
def test_spawned_subparts_clear_of_the_block(name):
    """Path A: the side panels (block origin and turned 180 deg) and the 42U fan tray, at their spawned pose, share no
    visible same-facing face plane with the rack's own LOD0 / LOD1 (the 24U roof rail's end faces did)."""
    zf = _zf(name)
    assert "subpart_frame" in zf
    assert zf["subpart_frame"] == []
