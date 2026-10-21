"""The racks', servers' and cable trays' fracture plans (dc/fracture.py, plain Python) and their
exported Fractured / Damaged models (Models/<name>/export.json, written by build_dc.py --export). The racks use the
same cutter (no uncut physics-box zones), and the 6U servers have a critical core. The room's staged breakable
blocks use it too: the raised floor, the containment roof and doors.

Keen's rules checked here come from the decompiled content pipeline (VRage.ContentPipeline.ModelsValidation
ModelLimitsChecker / ModelAssetProcessorValidator, VRage.ContentPipeline.ModelsBase ModelProcessorLoader):
  * a breakable collider needs 2 .. 16 fractures (one fracture fails the build: "cannot be created from a single
    instance"), and the size allows round(interp(max edge)) of them (a warning above);
  * each model's LOD count is keyed on ITS OWN LOD0 triangles and bounding box (a warning when it differs);
  * a fractured model's LOD i may hold 1.83425 x the triangles, 32 materials and 256 mesh parts.
"""
import os

import pytest

from dc import catalog, config, contain, crac, floor, fracture as FR, integration, rack, server, tray
from dc import tray_plan as TP
from dc.assetio import read_json
from dc.material_guids import MATERIAL_GUIDS

FAMILIES = [b for b in catalog.BLOCKS if b.family in ("rack", "server", "tray", "trayrods")]
PLANNED = [b for b in FAMILIES if not FR.unfractured_reason(b)]
UNFRACTURED = [b for b in FAMILIES if FR.unfractured_reason(b)]
ROOM = [b for b in catalog.STAGED if b.family in ("floor", "contain_roof", "contain_door", "crac")]   # room, staged
ALL_PLANNED = PLANNED + ROOM


def _collision(spec):
    return {"rack": rack.collision, "server": server.collision, "floor": floor.collision,
            "contain_roof": contain.collision, "contain_door": contain.door_collision,
            "crac": crac.collision}.get(spec.family, tray.collision)(spec)


def _plan(spec):
    return FR.plan(spec, _collision(spec))


def _inside(p, lo, hi, eps=1e-6):
    return all(lo[i] - eps <= p[i] <= hi[i] + eps for i in range(3))


# ---------------------------------------------------------------------------------------------------- plans
def test_every_block_has_a_plan():
    """Every rack, server and tray but the justified exception (fracture.UNFRACTURED: the three rod hangers and the
    Chute, whose independent members no fracture connection can join) has a plan, the racks included."""
    assert len(FAMILIES) == 54 and len(catalog.BLOCKS) == 54 + len(catalog.ROOM) and len(PLANNED) == 50
    assert sorted(b.name for b in UNFRACTURED) == ["DC_TrayRods_025", "DC_TrayRods_100", "DC_TrayRods_200",
                                                   "DC_Tray_Chute"]
    for b in FAMILIES:
        assert (_plan(b) is None) == (b in UNFRACTURED), b.name


@pytest.mark.parametrize("spec", UNFRACTURED, ids=lambda s: s.name)
def test_unfractured_members_cannot_connect(spec):
    """The exception's premise: its physics boxes (one per rod / ladder) lie further apart than Havok's fracture
    connection distance (BreakableColliderArgs.MaxEdgeDistance, 0.1 m), so any two zones of one member each would
    leave the breakable collider without a connection (the builder's "Connectivity graph" failure)."""
    reg = _collision(spec)["regular"]
    assert len(reg) == 2
    (_, a0, a1), (_, b0, b1) = reg
    gap = max(max(b0[i] - a1[i], a0[i] - b1[i]) for i in range(3))
    assert gap > 0.1, gap


@pytest.mark.parametrize("spec", ALL_PLANNED, ids=lambda s: s.name)
def test_plan_zones(spec):
    """2 .. Keen's maximum zones for the cell size, named Fracture_01.., each with a non-degenerate collider inside the
    block, the colliders covering every physics box; every seam lies between its two zones."""
    p = _plan(spec)
    size = [0.25 * spec.cells[i] for i in (0, 2, 1)]      # game cells (x, up, depth) -> Blender (x, y, z)
    ids = [z.id for z in p.zones]
    assert ids == [f"Fracture_{i:02d}" for i in range(1, len(ids) + 1)]
    assert 2 <= len(ids) <= min(16, FR.max_fractures(size)), (len(ids), FR.max_fractures(size))
    half = [s / 2 for s in size]
    for z in p.zones:
        if z.hull is None:          # no physics box under it (the half rack's roof): shaped at export only
            assert z.hull_from == "geometry", z
            continue
        lo, hi = z.hull
        assert min(h - l for l, h in zip(lo, hi)) >= 0.004, z
        assert _inside(lo, [-h for h in half], half, 1e-4) and _inside(hi, [-h for h in half], half, 1e-4), z
    for nm, lo, hi in _collision(spec)["regular"]:
        if nm in FR.UNFRACTURED_BOXES:   # the racks' rear stop plate (fracture.UNFRACTURED_BOXES)
            assert spec.family == "rack", nm
            continue
        for f in ((0.02, 0.02, 0.02), (0.5, 0.5, 0.5), (0.98, 0.98, 0.98), (0.02, 0.98, 0.5), (0.98, 0.02, 0.5)):
            q = [a + t * (b - a) for a, b, t in zip(lo, hi, f)]
            assert any(z.hull and _inside(q, *z.hull, 1e-4) for z in p.zones), q
    for s in p.seams:
        eps = 1e-3
        a = [o + eps * n for o, n in zip(s.o, s.n)]
        b = [o - eps * n for o, n in zip(s.o, s.n)]
        assert p.zone_index(a) in s.A and p.zone_index(b) in s.B, (s.o, s.n)


def test_room_plans():
    """Room blocks (vanilla-style fracture): the floor and roof split IN PLANE, every
    zone the full thickness (2 zones per 0.5 m, 4 per 1.0 m floor; the roof's 0.5 m bays within Keen's table for the
    panel's measured edge: 3 on the 1.0 m aisle (0.998 m: Keen's 3), 4 on the 1.5 m, a zone per bay on the 2.0 m),
    no critical zone (structural, as vanilla DeckPanel250); the door's 8 frame segments with the 7 round the
    opening critical (vanilla SlidingDoorNarrow250) and the closed leaves supported by the lintel."""
    assert len(ROOM) == 11
    want = {"DC_CRAC": 9, "DC_Floor_Solid_050": 2, "DC_Floor_Perf_050": 2, "DC_Floor_Solid_100": 4, "DC_Floor_Perf_100": 4,
            "DC_Contain_Roof_100": 3, "DC_Contain_Roof_150": 4, "DC_Contain_Roof_200": 8,
            "DC_Contain_Door_100": 8, "DC_Contain_Door_150": 8, "DC_Contain_Door_200": 8}
    for b in ROOM:
        p = _plan(b)
        assert len(p.zones) == want[b.name], b.name
        size = [0.25 * b.cells[i] for i in (0, 2, 1)]
        lo_z, hi_z = -size[2] / 2, size[2] / 2
        if b.family == "crac":            # functional: the core and the fan sections (test_crac.py)
            assert p.critical() == [z.id for z in p.zones[:4]]
            continue
        if b.family == "contain_door":
            assert p.critical() == [z.id for z in p.zones[:7]] and "sill" in p.zones[-1].label
            assert p.manifest()["supporting"] == {"LeftDoorClosed": "Fracture_01", "RightDoorClosed": "Fracture_01"}
            continue
        assert p.critical() == []
        for z in p.zones:                 # in plane: every zone's hull spans the block's full thickness
            if b.family == "floor":
                assert z.hull[0][2] == pytest.approx(lo_z) and z.hull[1][2] == pytest.approx(hi_z), (b.name, z)
            else:
                assert z.hull[1][2] == pytest.approx(hi_z) and z.hull[0][2] < contain.ZS - 0.05, (b.name, z)
        assert all(s.axis() in (0, 1) for s in p.seams)    # no layer seam


@pytest.mark.parametrize("spec", PLANNED, ids=lambda s: s.name)
def test_plan_critical_zone(spec):
    """Functional blocks: Fracture_01 is the key zone and the only critical one (trays are structural: none): a 6U
    server's central core (between the front service module and the rear chassis, so it always keeps two
    neighbours), the UPS's front bay module (vanilla Battery50), the tray zone holding the hanger (trapeze / floor
    strut: its centre lies in Fracture_01) or the junction hub. Racks are structural: no critical zone, but on a door
    rack every side column zone (the hinges)."""
    p = _plan(spec)
    if spec.family == "rack":
        from dc import doors
        cols = [z.id for z in p.zones if "column" in z.label]
        assert cols and p.critical() == (cols if doors.has_doors(spec) else []), p.critical()
        return
    if spec.family == "tray":     # structural, no critical zone, like the open racks
        assert p.critical() == []
    else:
        assert p.critical() == ["Fracture_01"]
    if spec.family == "server":
        front, back = p.zone_index((0.0, 0.375, 0.0)), p.zone_index((0.0, -0.37, 0.0))
        if spec.variant == "UPS":
            assert (front, back) == (0, 1)
        else:   # the core lies between the two shells (both seams are its faces)
            assert (front, back) == (1, 2) and p.zone_index((0.0, 0.08, 0.0)) == 0
            assert {s.a for s in p.seams} == {0}
        return
    pl = TP.plan(spec)
    sh = [v / 2 for v in pl.size]
    for sp in pl.supports:
        assert p.zone_index([float(c) - s for c, s in zip(sp.position, sh)]) == 0, (sp.kind, sp.position)


def test_server_seams_follow_the_chassis():
    """The 6U break runs through the 8 mm shadow gap between the rear cover and the service lid (dc/server.py
    yg0 / yg1 = -0.030 / -0.022); the UPS's between its two cell bays' core segments (dc/servers/ups.core_bays)."""
    import re
    assert -0.030 < FR.SERVER_SEAM_Y < -0.022
    assert 0.14 < FR.SERVER_FRONT_Y - 0.02 and FR.SERVER_FRONT_Y + 0.02 < 0.2125   # swages end 0.138, intakes 0.2125
    src = open(os.path.join(config.HERE, "dc", "servers", "ups.py")).read()   # (a bpy module: read, not imported)
    body = src[src.index("def core_bays"):src.index("def _ladder")]
    assert float(re.search(r"ys = ([0-9.]+)", body).group(1)) == FR.UPS_SEAM_Y
    p = _plan(catalog.BY_NAME["DC_Srv_UPS"])
    assert p.manifest()["supporting"] == {"CellAction 0": "Fracture_01", "CellAction 1": "Fracture_02",
                                          "CellSlot 0": "Fracture_01", "CellSlot 1": "Fracture_02"}


def test_clip_box():
    pts = FR.clip_box((0, 0, 0), (1, 1, 1), [((0.25, 0, 0), (1, 0, 0))])
    assert min(p[0] for p in pts) == pytest.approx(0.25) and max(p[0] for p in pts) == pytest.approx(1)
    assert FR.clip_box((0, 0, 0), (1, 1, 1), [((2, 0, 0), (1, 0, 0))]) == []
    pts = FR.clip_box((-1, -1, 0), (1, 1, 1), [((0, 0, 0), FR._unit((1, 1, 0)))])
    assert min(p[0] for p in pts) == pytest.approx(-1) and min(p[0] + p[1] for p in pts) == pytest.approx(0)


def test_max_fractures_is_keens_table():
    """GetMaximumNumberOfFractures: interp on the largest edge, MathF.Round (half to even)."""
    assert [FR.max_fractures((m, 0.1, 0.1)) for m in (0.25, 0.5, 0.79, 1.0, 1.5, 2.0)] == [1, 2, 3, 4, 5, 10]


def test_damaged_slots_are_vanilla_broken_materials():
    """The Damaged .model's swaps resolve to the vanilla broken materials vanilla's Deformed models use."""
    for slot, broken in FR.DAMAGED_SLOTS.items():
        g, rel = MATERIAL_GUIDS[broken]
        assert rel in ("EmissiveOffBroken.def", "Display01Broken.def", "LCDScreen_Off.def", "WindowGlassBroken.def",
                       # the 4.0 parallax Deformed metals
                       "PaintedMetalColorable_Deformed/PaintedMetalColorableDeformed.def",
                       "PaintedMetalColorable_Deformed/PaintedMetalDarkerDeformed.partialdef",
                       "BrushedMetalDeformed/BrushedMetalDeformed.def", "Chrome_Deformed/ChromeDeformed.def"), \
            (slot, rel)
    assert MATERIAL_GUIDS[FR.CUT_MATERIAL][1] == "FracturedMaterial01.def"


# ---------------------------------------------------------------------------------------------------- exports
def _manifest(n):
    p = os.path.join(config.MODELS_DIR, n, "export.json")
    return read_json(p) if os.path.exists(p) else None


EXPORTED = [b.name for b in ALL_PLANNED if (_manifest(b.name) or {}).get("fractured", {}).get("kind") == "cut"]


def test_all_planned_blocks_exported_cut():
    assert sorted(EXPORTED) == sorted(b.name for b in ALL_PLANNED)


@pytest.mark.parametrize("name", EXPORTED)
def test_exported_lods_follow_keen(name):
    """Every model (NonFractured, Fractured, Damaged) has exactly Keen's LOD count for its own LOD0 and bounds; the
    fractured ones stay within the fractured triangle and material limits; the LastLOD box has one material; the
    Damaged model's bounds equal the intact one's (the dents are pinned there: render bounds, ports, mount faces)."""
    from se2model import limits
    m = _manifest(name)
    for variant in ("nonfractured", "fractured", "damaged"):
        size = m[variant]["size"] if variant != "nonfractured" else m["nonfractured"]["size"]
        lods = m[variant]["lods"]
        t0 = lods[0]["tris"]
        assert limits.optimal_lods(size, t0)[0] == len(lods), (variant, size, t0, len(lods))
        lim = limits.model_limits(size, t0, fractured=variant != "nonfractured")
        for i, l in enumerate(lods):
            assert l["tris"] <= lim["lods"][i]["max_tris"], (variant, i, l["tris"], lim["lods"][i]["max_tris"])
            assert len(l["materials"]) <= lim["lods"][i]["max_materials"], (variant, i, l["materials"])
        assert len(lods[-1]["materials"]) == 1
    assert m["damaged"]["size"] == pytest.approx(m["nonfractured"]["size"], abs=2e-4)
    # (the FR carries the construction cage, which stands scaffold.OUTSET proud of each cell face the block fills,
    # i.e. within FILLS of it)
    from dc import scaffold as SC
    assert m["fractured"]["size"] == pytest.approx(m["nonfractured"]["size"], abs=2 * (SC.OUTSET + SC.FILLS) + 2e-4)
    assert all(f >= n - 2e-4 for f, n in zip(m["fractured"]["size"], m["nonfractured"]["size"]))
    d = m["damaged"]["dent"]
    assert 2.0 <= d["mean_mm"] <= 10.0 and d["max_mm"] <= 30.0, d     # vanilla Deformed: mean 5-8, max 15-25 mm


@pytest.mark.parametrize("name", EXPORTED)
def test_exported_break_faces(name):
    """The cut zones carry vanilla break faces: closed caps on LOD0, FracturedMaterial01 mesh parts in the zones'
    groups, built like vanilla's Fracture_NN_Cut (Split / HiddenUntilSecondSequenceStart / Fracture), a hidden part's
    in its zone's _Hide group (Default / AlwaysHidden / Default); the
    construction parts and the per-LOD groups of the Damaged model equal the
    Fractured model's, and its materials too but the scaffold's (the FR-only cage brings
    BrushedMetal to the FR of the blocks that had none, 15 at the time)."""
    m = _manifest(name)
    closed, _ = m["fractured"]["caps"][0]
    cut_parts = {k: v for k, v in m["fractured"]["parts"].items() if k.endswith("-" + FR.CUT_MATERIAL)}
    if "no wire-end caps" in m["fractured"]["cut_mode"]:   # a light empty basket: its cut 6 mm wires' ends stay open
        assert not catalog.BY_NAME[name].density or catalog.BY_NAME[name].density == "Empty", name
    else:
        assert closed > 0 and cut_parts, (closed, cut_parts)
    for k, v in cut_parts.items():       # (a hidden part's caps go with it, AlwaysHidden)
        g = k.split("-")[0]
        assert g.replace("_Hide", "") in {z["id"] for z in m["fractured"]["zones"]}
        want = ["Default", "AlwaysHidden", "Default"] if g.endswith("_Hide") else \
            ["Split", "HiddenUntilSecondSequenceStart", "Fracture"]
        assert v == want, (k, v)
    assert [l["groups"] for l in m["damaged"]["lods"]] == [l["groups"] for l in m["fractured"]["lods"]]
    sc = (m["fractured"].get("scaffold") or {}).get("tris") or {}
    for i, (f, d) in enumerate(zip(m["fractured"]["lods"], m["damaged"]["lods"])):
        extra = set(f["materials"]) - set(d["materials"])
        assert set(d["materials"]) <= set(f["materials"]) and extra <= {"BrushedMetal"}, (name, i, extra)
        assert not extra or str(i) in sc, (name, i)


@pytest.mark.parametrize("name", EXPORTED)
def test_fractures_keep_placement(name):
    """check_placement.py on the exported files: with the fracture colliders the occupancy, free cells and mount
    coverage are those of the NonFractured model (the game only splits mount groups per fracture), and every mount
    cell is supported by one of the block's fractures (none is left to "no fracture")."""
    p = os.path.join(config.MODELS_DIR, name, "placement_exported.json")
    if not os.path.exists(p):
        pytest.skip("run check_placement.py")
    pe = read_json(p)
    a, b = pe["nonfractured"], pe["fractured"]
    assert (a["occupied"], a["free_cells"]) == (b["occupied"], b["free_cells"])
    assert {d: f["coverage"] for d, f in a["faces"].items()} == {d: f["coverage"] for d, f in b["faces"].items()}
    by = b["mount_cells_by_fracture"]
    zones = {z["id"] for z in _manifest(name)["fractured"]["zones"]}
    assert "none" not in by and set(by) <= zones, by
    assert pe["colliders"]["fractures"] == len(zones)


@pytest.fixture(scope="module")
def staged(stage_package):
    stage_package()
    return config.STAGE_ASSETS


def test_damaged_model_maps_broken_materials(staged):
    """The staged Damaged .model maps the lamp and screen slots to the broken materials (vanilla Deformed) and every
    other slot exactly as the Fractured .model."""
    for n in EXPORTED:
        fr = read_json(os.path.join(staged, config.NAME, n, "Models", "Fractured", f"{n}_Fractured.model"))["$Value"]
        dm = read_json(os.path.join(staged, config.NAME, n, "Models", "Damaged", f"{n}_Damaged.model"))["$Value"]
        a = {x["MaterialName"]: x["MaterialReference"] for x in fr["MaterialAssignments"]}
        b = {x["MaterialName"]: x["MaterialReference"] for x in dm["MaterialAssignments"]}
        assert set(b) <= set(a) and set(a) - set(b) <= {"BrushedMetal"}, n    # the FR-only scaffold
        for slot, ref in b.items():
            want = MATERIAL_GUIDS[FR.damaged_slot(slot)][0] if FR.damaged_slot(slot) != slot else a[slot]
            assert ref == want, (n, slot)
