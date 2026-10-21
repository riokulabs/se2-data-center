"""Plan 5 Task 10: the room blocks' construction roles and the door sill's hull (audit G10).

Supports  fracture.ROLES per room family: the floor's pedestals (base plate, tube, jack, head) carry the deck; the
          roof's frame and its rail clamps carry the panes; the signs' bolts and hangers; the PDUs' fixings (the
          cabinet's levelling feet and bolts, the strips' standoff brackets and button heads). Vanilla doors have no
          support, nor do ours.
Hide      the PDUs' detail arrives on completion (vanilla CircuitBreaker: 48 % _Hide): the cabinet's lamps (the meter's
          unlit bar segments too), placard sticker and the branch breakers themselves (the `breaker` part, dc/pdu.py
          _breakers); the strips' lamps, jumper cords and the inlet plug.
Sill      a zone below fracture.MIN_ZONE_SHARE of the block's health gets an axis box hull (fracture.min_share_box),
          at most MIN_HULL_T beyond its geometry, or the export raises. The doors' 8 mm sill (Fracture_08, 0.06 %)
          is exempt (fracture.MIN_SHARE_EXEMPT, controller ruling, Task 10 fix round 1): it is the one non-critical
          door zone and its death changes no function (the door stays Functional, only the sill_down mount drops);
          audit G10 is rated Low; the hull is a live collider (a broken door's physics, debris, re-weld check), and
          reaching 1 % would put a 6-7 cm invisible step in the doorway. Accepted cost: the sill can die early."""
import os

import pytest

from dc import catalog, config, state_view as SV
from dc import fracture as FR
from dc.assetio import read_json

ROOM_FAMILIES = ("floor", "contain_roof", "contain_door", "sign", "pdu_cabinet", "pdu_strip")
SUPPORTED = ("floor", "contain_roof", "sign", "pdu_cabinet", "pdu_strip")
ROOM = [b.name for b in catalog.BLOCKS if b.family in ROOM_FAMILIES]
DOORS = [b.name for b in catalog.BLOCKS if b.family == "contain_door"]
ROOFS = [b.name for b in catalog.BLOCKS if b.family == "contain_roof"]
STRIPS = [b.name for b in catalog.BLOCKS if b.family == "pdu_strip"]
CUT = [b.name for b in catalog.BLOCKS if not FR.unfractured_reason(b)]
CABINET = "DC_PDU_Cabinet"
# measured after this task's export (LOD0 hide / role triangles; R18 measured 3.6 % before the breakers moved)
CABINET_HIDE_MIN = 0.10
GOLDEN = read_json(SV.BASELINE_PATH)


def _fr(name):
    return read_json(os.path.join(config.MODELS_DIR, name, "export.json"))["fractured"]


def _groups(parts):
    return {p.split("-", 1)[0] for p in parts}


# ---------------------------------------------------------------------------------------------------- pure
def test_room_inventory():
    assert len(ROOM) == 18 and len(DOORS) == 3 and len(ROOFS) == 3 and len(STRIPS) == 4
    assert FR.MIN_ZONE_SHARE == 0.01 and FR.MIN_HULL_T == 0.02


def test_room_role_tables():
    """The tables name parts the builders make (dc/floor.py, contain.py, signs.py, pdu.py)."""
    assert FR.ROLES["floor"] == {"support": ("ped", "pedplate")}
    assert FR.ROLES["contain_roof"] == {"support": ("frame", "clamp")}
    assert FR.ROLES["contain_door"] == {}
    assert FR.ROLES["sign"] == {"support": ("hw",)}
    assert FR.ROLES["pdu_cabinet"] == {"hide": ("lamp", "sticker", "breaker"), "support": ("hw",)}
    assert FR.ROLES["pdu_strip"] == {"hide": ("lamp", "cord", "plug"), "support": ("hw", "steel")}
    assert FR.role_of("pdu_cabinet", "breaker", "PaintedMetalDarker") == "hide"
    assert FR.role_of("contain_roof", "frame", "FrostedGlass") == "glass"      # glass by material first


def _door_like():
    """The 1 m door's numbers: 7 critical frame zones (weighted 1.43 m^3) and the 8 mm sill between the posts."""
    lo, hi = (-1.0, -0.125, -1.25), (1.0, 0.125, 1.25)
    big = {f"Fracture_0{i}": FR.box_hull((-0.9, -0.12, -1.2), (-0.5, 0.12, -1.2 + v / 0.096)) for i, v in
           zip(range(1, 8), (0.066, 0.1025, 0.0939, 0.1292, 0.1025, 0.0939, 0.1292))}
    sill = ((-0.45, -0.06, -1.2495), (0.45, 0.06, -1.242))
    shapes = dict(big, Fracture_08=FR.box_hull(*sill))
    return shapes, set(big), sill, lo, hi


def test_min_share_exempt_is_the_door_sill():
    assert FR.MIN_SHARE_EXEMPT == {("contain_door", "Fracture_08")}


def test_sill_raises_unless_exempt():
    """Reaching 1 % would take the sill far more than MIN_HULL_T past its 8 mm: the lift raises, naming the zone and
    the exemption list (no spreading to the cells or seams); exempt, it keeps its hull."""
    shapes, crit, sill, lo, hi = _door_like()
    assert FR.health_shares({z: s["volume"] for z, s in shapes.items()}, crit)["Fracture_08"] < 0.001
    with pytest.raises(RuntimeError, match=r"Fracture_08: under MIN_ZONE_SHARE.*MIN_SHARE_EXEMPT"):
        FR.lift_small_zones(shapes, crit, {"Fracture_08": sill}, lo, hi)
    assert FR.lift_small_zones(shapes, crit, {"Fracture_08": sill}, lo, hi, {"Fracture_08"}) == {}


def test_min_hull_t_alone_where_enough():
    """A thin plate whose 2 cm box already reaches the floor keeps its footprint, exactly MIN_HULL_T thick, within
    MIN_HULL_T of its geometry and inside the cells; one needing more raises."""
    lo, hi = (-1.0, -1.0, -1.0), (1.0, 1.0, 1.0)
    g = ((-0.5, -0.5, 0.2), (0.5, 0.5, 0.208))
    shapes = {"Fracture_01": FR.box_hull((-1, -1, -1), (1, 1, -0.75)), "Fracture_02": FR.box_hull(*g)}
    new = FR.lift_small_zones(shapes, set(), {"Fracture_02": g}, lo, hi)
    vs = new["Fracture_02"]["verts"]
    blo = [min(v[i] for v in vs) for i in range(3)]
    bhi = [max(v[i] for v in vs) for i in range(3)]
    assert [b - a for a, b in zip(blo, bhi)] == pytest.approx([1.0, 1.0, FR.MIN_HULL_T])
    assert all(g[0][i] - blo[i] <= FR.MIN_HULL_T + 1e-9 and bhi[i] - g[1][i] <= FR.MIN_HULL_T + 1e-9
               for i in range(3))
    with pytest.raises(RuntimeError, match="needs"):        # half as wide: 4 cm would be needed
        FR.min_share_box((-0.25, -0.5, 0.2), (0.25, 0.5, 0.208), lo, hi, 0.02, "Fracture_02")


def test_no_lift_above_the_floor():
    shapes = {"Fracture_01": FR.box_hull((0, 0, 0), (1, 1, 1)), "Fracture_02": FR.box_hull((1, 0, 0), (2, 1, 0.5))}
    assert FR.lift_small_zones(shapes, set(), {}, (-5,) * 3, (5,) * 3) == {}


# ---------------------------------------------------------------------------------------------------- the build
@pytest.mark.build
@pytest.mark.parametrize("name", CUT)
def test_min_zone_share(name):
    """Every zone of every cut block holds >= MIN_ZONE_SHARE of the health (the export's shares, Keen's rule), except
    exactly fracture.MIN_SHARE_EXEMPT: the three doors' sills (see the module docstring for why)."""
    fam = catalog.BY_NAME[name].family
    zones = _fr(name)["zones"]
    low = {z["id"]: z["health_share"] for z in zones if z["health_share"] < FR.MIN_ZONE_SHARE}
    want = {zid for f, zid in FR.MIN_SHARE_EXEMPT if f == fam}
    assert set(low) == want, (name, low)


@pytest.mark.build
@pytest.mark.parametrize("name", DOORS)
def test_door_sill_keeps_its_zone(name):
    """The sill keeps its zone and its shaped hull: 8 zones, 7 critical, the baseline's ids, no min_share flag; the
    sill hull stays within the visible threshold (<= 0.01 m over the cell floor, y within +-0.06), so a broken door
    (its Fractured collision live) has no step in the doorway."""
    fr = _fr(name)
    ids = [z["id"] for z in fr["zones"]]
    assert ids == GOLDEN[name]["zones"] and len(ids) == 8
    assert fr["critical"] == GOLDEN[name]["critical"] and len(fr["critical"]) == 7
    assert not [z["id"] for z in fr["zones"] if z.get("min_share")], name
    sill = fr["zones"][-1]
    assert sill["id"] == "Fracture_08"
    floor = -0.125 * catalog.BY_NAME[name].cells[1]
    assert sill["lo"][2] >= floor - 1e-4 and sill["hi"][2] - floor <= 0.01 + 1e-6, sill
    assert -0.06 - 1e-6 <= sill["lo"][1] and sill["hi"][1] <= 0.06 + 1e-6, sill


@pytest.mark.build
@pytest.mark.parametrize("name", ROOM)
def test_room_support_roles(name):
    """Floors, roofs, signs, the PDU cabinet and strips build their supports first (>= 1 _Support group and
    support triangles); the doors have none (vanilla doors)."""
    fr = _fr(name)
    fam = catalog.BY_NAME[name].family
    sup = {g for g in _groups(fr["parts"]) if g.endswith("_Support")}
    if fam in SUPPORTED:
        assert sup and fr["role_tris"]["support"] > 0, name
        assert all(v == list(FR.ROLE_PROPS["support"]) for p, v in fr["parts"].items()
                   if p.split("-", 1)[0].endswith("_Support")), name
    else:
        assert not sup and fr["role_tris"]["support"] == 0, name


@pytest.mark.build
def test_pdu_detail_on_completion():
    """The cabinet's lamps, sticker and branch breakers arrive on completion: its LOD0 hide share >= the measured
    CABINET_HIDE_MIN, the breakers' Darker bodies in _Hide groups; on every PDU each -Emissive* part is in a _Hide
    group, and the strips' jumper cords (Rubber) are too."""
    fr = _fr(CABINET)
    rt = fr["role_tris"]
    assert rt["hide"] / sum(rt.values()) >= CABINET_HIDE_MIN, rt
    assert any(p.split("-", 1)[0].endswith("_Hide") and p.endswith("-PaintedMetalDarker") for p in fr["parts"])
    for name in [CABINET] + STRIPS:
        parts = _fr(name)["parts"]
        em = [p for p in parts if "-Emissive" in p]
        assert em and all(p.split("-", 1)[0].endswith("_Hide") for p in em), name
        if name in STRIPS:
            assert any(p.split("-", 1)[0].endswith("_Hide") and p.endswith("-Rubber") for p in parts), name
        for p, v in parts.items():
            if p.split("-", 1)[0].endswith("_Hide"):
                assert v == list(FR.ROLE_PROPS["hide"]), (name, p)


@pytest.mark.build
@pytest.mark.parametrize("name", ROOFS)
def test_roof_glass_preset(name):
    """With the frame now support, every roof glass part (material in GLASS_MATERIALS) is still glass: in the zone's
    own group (never _Support), stage-0 SetMaterial = the WindowGlass preset 83c075f5."""
    parts = _fr(name)["parts"]
    glass = [p for p in parts if "-" in p and p.split("-", 1)[1] in FR.GLASS_MATERIALS]
    assert glass and all(not p.split("-", 1)[0].endswith(("_Support", "_Hide", "_Frame")) for p in glass), name
    assert all(parts[p] == list(FR.ROLE_PROPS["glass"]) for p in glass), name
    s0 = {c["Value"]["MeshPart"]: c["Value"] for c in SV.installed_stages(name)[0]["Value"]["PartChanges"]["_data"]}
    assert all(s0[p]["SetMaterial"].startswith("83c075f5") for p in glass), name
