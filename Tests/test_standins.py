"""Plan 5 Task 8: the servers' construction supports and the baked subpart stand-ins (audit G6, Decision 9).

Supports  fracture.ROLES["server"]: the rack ears and the slide (inner) members are the server's mounting hardware,
          built first (Fracture_NN_Support, the Support preset), as vanilla Timer50 (11 %) / Battery50 (8 %).
Stand-ins the parked moving parts baked into the Fractured and Damaged models (never the NonFractured), as vanilla
          Gyroscope250 (17 `_Subpart` parts in FR, 16 in DM, 0 in NF): each subpart's next-lower LOD in its closed
          pose, its slots renamed `<Mat>_Subpart` (the SubpartConstruct preset), in its owning zone; the block's
          ConditionalSubParts lists them in MeshPartsToHideWhenActive, so they show while the block is not Functional
          (under construction, broken) and hide when the real subparts spawn. The KVM: the drawer, closed, and its lid.
Review Focus 5: player paint on a damaged stand-in: every `<Mat>_Subpart` slot resolves to its base slot's GUID on FR
and to its base's Deformed GUID on DM (fracture.damaged_slot), never a KeyError or an unpainted fallback."""
import math
import os

import pytest

from dc import catalog, config, integration, state_view as SV
from dc import construction as C
from dc import fracture as FR
from dc import fracture_rules as FRR
from dc.assetio import read_json
from dc.guids import Guids
from dc.material_guids import MATERIAL_GUIDS, guid

KVM = "DC_Srv_KVM"
CRAC = "DC_CRAC"
SUBPART_CONSTRUCT = C.PRESETS["subpartconstruct"]["T"][0]          # 851d4d6e...
SERVERS = [b.name for b in catalog.BLOCKS if b.family == "server"]


def _man(name):
    return read_json(os.path.join(config.MODELS_DIR, name, "export.json"))


def _fr_parts(name, key="fractured", lod=0):
    m = _man(name)[key]
    return FRR.mesh_parts(FRR.fbx_meshes(os.path.join(config.MODELS_DIR, name, key.capitalize(),
                                                      m["lods"][lod]["file"])))


def _violation(zone, p):
    """How far p lies outside a manifest zone's half spaces (m)."""
    return max([0.0] + [-sum((p[i] - o[i]) * n[i] for i in range(3)) for o, n in zone["halfspaces"]])


def _standin_faces_in_zone(name):
    """Every FR LOD0 stand-in face is in the group of the zone holding its centroid and no vertex of it lies more
    than 2 cm past that zone (Task 8 re-review: copied for every stand-in block). The zones are convex (half-space
    intersections) and a violation is convex, so the vertex bound bounds the whole face: no edge or face can cross a
    third zone's volume between two in-zone vertices. Returns the stand-in triangles counted."""
    man = _man(name)
    zones = man["fractured"]["zones"]
    zz = {z["id"]: z for z in zones}
    meshes = FRR.fbx_meshes(os.path.join(config.MODELS_DIR, name, "Fractured", man["fractured"]["lods"][0]["file"]))
    n = 0
    for m in meshes.values():
        g = m["props"].get("Group", "")
        for poly, k in zip(m["polys"], m["poly_mat"]):
            if m["materials"][k].endswith("_Subpart"):
                c = tuple(sum(m["verts"][i][a] for i in poly) / len(poly) for a in range(3))
                z = g.replace("_Hide", "")
                if m["materials"][k] != FR.CUT_MATERIAL + "_Subpart":   # (a cut stand-in's break cap lies ON its
                    assert FR.Plan.zone_at(zones, c) == z, (name, g, m["materials"][k], c)   # seam: bound only)
                assert max(_violation(zz[z], m["verts"][i]) for i in poly) <= 0.02, (name, g, m["materials"][k], c)
                n += len(poly) - 2
    return n


def _hide_list_matches(staged, name, rel):
    """The staged ConditionalSubParts hides exactly the FR LOD0 stand-in parts (integration.standin_parts), in
    vanilla's keyed form with the registry's stable `hide/<block>/<part>` keys; they build in the SubpartConstruct
    material through both sequences (0 and 0.3)."""
    man = _man(name)
    want = integration.standin_parts(man)
    assert want and want == sorted(p for p in _fr_parts(name) if p.endswith("_Subpart"))
    assert want == man["fractured"]["standins"]["parts"]
    d = read_json(os.path.join(config.STAGE_ASSETS, rel))["$Value"]
    assert [x["Value"] for x in d["MeshPartsToHideWhenActive"]] == want
    keys = [x["Key"] for x in d["MeshPartsToHideWhenActive"]]
    assert len(set(keys)) == len(keys) and all(len(k) == 36 for k in keys)
    reg = Guids().d                                                # (read, never allocate: a lost entry fails here)
    assert all(f"hide/{name}/{p}" in reg for p in want)
    assert keys == [reg[f"hide/{name}/{p}"] for p in want]
    stages = SV.installed_stages(name)
    for p in want:
        sets = sorted((s["Value"]["BuildRatioLowerBound"], c["Value"]["SetMaterial"]) for s in stages
                      for c in s["Value"]["PartChanges"]["_data"] if c["Value"]["MeshPart"] == p)
        assert sets == [(0.0, SUBPART_CONSTRUCT), (0.3, SUBPART_CONSTRUCT)], (name, p, sets)
    return d


@pytest.fixture(scope="module")
def staged(stage_package):
    return stage_package()


def _staged_model(name, variant):
    stem = name if variant == "NonFractured" else f"{name}_{variant}"
    p = os.path.join(config.STAGE_ASSETS, config.NAME, name, "Models", variant, f"{stem}.model")
    return {a["MaterialName"]: a["MaterialReference"] for a in read_json(p)["$Value"]["MaterialAssignments"]} \
        if os.path.exists(p) else None


# ---------------------------------------------------------------------------------------------------- pure
def test_standin_table():
    """The KVM's drawer (FR LOD0 <- its LOD1, FR LOD1 <- its LOD2) and lid (its LOD1 for both), each split over the
    zones it sits in (zone None; fix round 1, vanilla Gyroscope50 / O2H2Generator250) and cut along the seams with
    break caps (final review M4, as the racks')."""
    racks = {b.name for b in catalog.BLOCKS if b.family == "rack"}      # Task 12: test_rack_states
    assert len(racks) == 6 and set(FR.rack_standins("A")) == racks
    assert set(FR.STANDINS) == {KVM, CRAC} | set(FR.rack_standins(config.RACK_PATH))
    s = {x.subpart: x for x in FR.STANDINS[KVM]}
    assert s["KvmDrawer"].zone is None and s["KvmScreen"].zone is None
    assert s["KvmDrawer"].cut and s["KvmScreen"].cut
    assert s["KvmDrawer"].src_lods == (1, 2) and s["KvmScreen"].src_lods == (1, 1)


def test_crac_standin_table():
    """Task 11 (G6): the CRAC's three CracFan rotors, parked (no power: still, not spinning), each in its own fan
    section (Fracture_02..04, the zones supporting CracFan1..3), FR LOD0 <- the rotor's LOD1, FR LOD1 <- its LOD2,
    each at its own rotor pivot (crac.fan_points, the CracFan1..3 dummies' order)."""
    from dc import crac
    fans = FR.STANDINS[CRAC]
    pts = crac.fan_points(catalog.BY_NAME[CRAC])
    assert [s.subpart for s in fans] == [crac.FAN] * 3
    assert [s.zone for s in fans] == ["Fracture_02", "Fracture_03", "Fracture_04"]
    assert all(s.src_lods == (1, 2) for s in fans)
    assert all(max(abs(a - b) for a, b in zip(s.at, p)) < 1e-9 for s, p in zip(fans, pts))


def test_crac_role_table():
    """The CRAC's mounting hardware (dc/crac.py `hw`: the levelling feet, the fan modules' and panels' fixing bolts,
    hinges and latches) and its coolant stubs (`pipe`: the CHW supply / return and condensate stubs the facility's
    pipework lands on) are its supports, built first. Task 13: the fan modules' venturi lip rings (`lip`, the orifice
    trim) are no mount: their own part, skin (built with the housing they trim), still kept whole."""
    from dc import crac
    assert FR.ROLES["crac"] == {"support": ("hw", "pipe")}
    assert "lip" in crac.PART_NAMES and "lip" in FR.KEEP_WHOLE["crac"]
    assert FR.role_of("crac", "lip", "MetalDull") == "skin"
    FR.check_role_tables(FR.ROLES)


@pytest.mark.build
def test_crac_support_share():
    """Task 13: without the lips the CRAC's supports are 16.4 % of its FR LOD0 (Task 11: 18.7 %; vanilla Smelter250
    24 %, Gyroscope250 11 %, Timer50 11 %): inside the servers' 3-25 % band, below Task 11's share."""
    fr = _man(CRAC)["fractured"]
    share = fr["role_tris"]["support"] / fr["lods"][0]["tris"]
    assert 0.08 <= share < 0.187, round(share, 4)


def test_server_role_table():
    """The ears, slides and the ears' captive thumbscrews are the server's mounting hardware (dc/server.py _ears /
    _slides); nothing else (the washers and rivets of hw / fine mix in skin details)."""
    assert FR.ROLES["server"] == {"support": ("ear", "slide", "screw")}
    FR.check_role_tables(FR.ROLES)


def test_subpart_slots_resolve(staged):
    """Review Focus 5. A `_Subpart` slot wears its base slot's material (player paint on the Colorable one) on the
    Fractured model and its base's Deformed material on the Damaged one, on every staged model that has one."""
    SUBPART_SUFFIX = FR.SUBPART_SUFFIX              # (export_models.SUBPART_SUFFIX: the same constant, bpy-side)
    assert SUBPART_SUFFIX == "_Subpart"
    assert guid("PaintedMetalColorable_Subpart") == guid("PaintedMetalColorable")
    assert guid("EmissiveGreen_Subpart") == guid("EmissiveGreen")
    assert FR.damaged_slot("PaintedMetalDarker_Subpart") == "PaintedMetalDarkerDeformed"
    assert FR.damaged_slot("PaintedMetalDarker") == "PaintedMetalDarkerDeformed"
    assert FR.damaged_slot("EmissiveGreen_Subpart") == "EmissiveOffBroken"
    assert FR.damaged_slot("MetalDull_Subpart") == "MetalDull_Subpart"   # no swap: the base's own material
    assert FR.damaged_slot("MetalDull") == "MetalDull"
    with pytest.raises(KeyError):
        guid("NoSuchMaterial_Subpart")
    seen = 0
    for b in catalog.STAGED:
        fr, dm = _staged_model(b.name, "Fractured"), _staged_model(b.name, "Damaged")
        for slot, ref in (fr or {}).items():
            if slot.endswith(SUBPART_SUFFIX):
                base = slot[:-len(SUBPART_SUFFIX)]
                assert ref == MATERIAL_GUIDS[base][0], (b.name, slot)
                seen += 1
        for slot, ref in (dm or {}).items():
            if slot.endswith(SUBPART_SUFFIX):
                base = slot[:-len(SUBPART_SUFFIX)]
                want = FR.DAMAGED_SLOTS.get(base, base)
                assert ref == MATERIAL_GUIDS[want][0], (b.name, slot)
                seen += 1
    assert seen, "no staged model carries a _Subpart slot"


# ---------------------------------------------------------------------------------------------------- build
@pytest.mark.build
def test_kvm_standins(staged):
    """The KVM FR and DM LOD0 carry the stand-ins split by zone (the drawer's fascia in the front module Fracture_02,
    its tray in the core Fracture_01, its tail in the rear chassis Fracture_03), cut along the seams with break caps
    (final review M4), every face in the group of the zone holding its centroid and no vertex more than 2 cm past it
    (_standin_faces_in_zone); its NF none; the staged ConditionalSubParts hides exactly them (_hide_list_matches)."""
    man = _man(KVM)
    for key in ("fractured", "damaged"):
        parts = _fr_parts(KVM, key)
        mine = sorted(p for p in parts if p.endswith("_Subpart"))
        assert {p.split("-")[0] for p in mine} >= {"Fracture_01", "Fracture_02", "Fracture_03"}, (key, mine)
    assert _standin_faces_in_zone(KVM) == man["fractured"]["standins"]["tris"]["0"]
    nf = FRR.mesh_parts(FRR.fbx_meshes(os.path.join(config.MODELS_DIR, KVM, "NonFractured",
                                                    man["nonfractured"]["lods"][0]["file"])))
    assert not [p for p in nf if p.endswith("_Subpart")]
    cs = staged["blocks"][KVM]["subparts"]["conditional_subparts"]
    rel = f"{config.NAME}/{KVM}/Subparts/{KVM}_ConditionalSubPartsDefinition.def"
    assert _hide_list_matches(staged, KVM, rel)["Guid"] == cs


@pytest.mark.build
def test_kvm_standin_closed_pose():
    """The stand-ins sit in the drawer bay in the closed pose (the KVM is placed with its drawer closed, commit
    79378423): every stand-in vertex of the FR LOD0 lies behind the bezel front (subparts.FACE_Y + the fascia's 22 mm
    pull bar) and inside the core's width and height."""
    from dc import subparts as S
    meshes = FRR.fbx_meshes(os.path.join(config.MODELS_DIR, KVM, "Fractured", _man(KVM)["fractured"]["lods"][0]["file"]))
    pts = []
    for m in meshes.values():
        sub = [i for i, n in enumerate(m["materials"]) if n.endswith("_Subpart")]
        for poly, k in zip(m["polys"], m["poly_mat"]):
            if k in sub:
                pts += [m["verts"][i] for i in poly]
    assert pts
    assert max(p[1] for p in pts) <= S.DRAWER_BOX["y_front"] + 0.023
    assert min(p[1] for p in pts) >= S.DRAWER_BOX["y0"] - 0.002
    assert max(abs(p[0]) for p in pts) <= S.BAY["x"]
    assert min(p[2] for p in pts) >= S.BAY["z0"] - 0.006 and max(p[2] for p in pts) <= S.BAY["z1"] + 0.006


@pytest.mark.build
@pytest.mark.parametrize("name", SERVERS)
def test_server_support_roles(name):
    """Every server's FR LOD0 has its supports (Fracture_NN_Support), between 3 % and 25 % of its triangles (vanilla
    Timer50 11 %, Battery50 8 %)."""
    fr = _man(name)["fractured"]
    groups = fr["lods"][0]["groups"]
    assert any(g.startswith(FR.PREFIX) and g.endswith("_Support") for g in groups), (name, groups)
    share = fr["role_tris"]["support"] / fr["lods"][0]["tris"]
    assert 0.03 <= share <= 0.25, (name, round(share, 4))


@pytest.mark.build
def test_fr_budget_with_standins():
    """The stand-ins count in the KVM's Fractured triangles: its LOD0 stays within the fractured budget, and the LOD
    count is still Keen's for the FR's own size and LOD0 (and the NF's)."""
    from se2model import limits
    man = _man(KVM)
    fr = man["fractured"]
    st = fr["standins"]["tris"]
    assert st["0"] > 0 and st["1"] > 0
    for i, row in enumerate(fr["lods"][:-1]):
        assert row["tris"] <= fr["budget"][i], (i, row["tris"], fr["budget"][i])
    assert len(fr["lods"]) == len(man["nonfractured"]["lods"])
    assert limits.optimal_lods(tuple(fr["size"]), fr["lods"][0]["tris"])[0] == len(fr["lods"])


@pytest.mark.build
def test_crac_fan_standins(staged):
    """Task 11 (G6): the CRAC's FR and DM LOD0 carry a parked fan in each fan section (`_Subpart` parts in exactly
    Fracture_02, _03 and _04), its NF none; every stand-in face sits in its zone (<= 2 cm past it); each section's
    stand-in is that fan's rotor, still, at its pivot (inside the blade-tip circle about the rotor axis, between the
    blades' front and back); the staged ConditionalSubParts hides exactly them while the fans run (Functional); the
    FR LOD0 stays within 28 006 triangles and the LOD count is unchanged (Keen's for the FR's size and LOD0, = NF's)."""
    from dc import crac
    from se2model import limits
    man = _man(CRAC)
    fr = man["fractured"]
    fans = ("Fracture_02", "Fracture_03", "Fracture_04")
    for key in ("fractured", "damaged"):
        mine = [p for p in _fr_parts(CRAC, key) if p.endswith("_Subpart")]
        assert {p.split("-")[0] for p in mine} == set(fans), (key, mine)
    nf = FRR.mesh_parts(FRR.fbx_meshes(os.path.join(config.MODELS_DIR, CRAC, "NonFractured",
                                                    man["nonfractured"]["lods"][0]["file"])))
    assert not [p for p in nf if p.endswith("_Subpart")]
    assert _standin_faces_in_zone(CRAC) == fr["standins"]["tris"]["0"]
    # the parked rotors: each section's stand-in vertices around its own pivot (the rotor's frame, no spin offset)
    pts = dict(zip(fans, crac.fan_points(catalog.BY_NAME[CRAC])))
    meshes = FRR.fbx_meshes(os.path.join(config.MODELS_DIR, CRAC, "Fractured", fr["lods"][0]["file"]))
    seen = set()
    for m in meshes.values():
        g = m["props"].get("Group", "")
        for poly, k in zip(m["polys"], m["poly_mat"]):
            if m["materials"][k].endswith("_Subpart"):
                px, py, pz = pts[g]
                for i in poly:
                    x, y, z = m["verts"][i]
                    assert math.hypot(x - px, z - pz) <= crac.ROTOR_R[1] + 0.002, (g, (x, y, z))
                    assert abs(y - py) <= 0.04, (g, (x, y, z))
                seen.add(g)
    assert seen == set(fans)
    rel = staged["blocks"][CRAC]["crac_subparts"]["conditional_subparts"]     # (the clone's SubParts.def, patched)
    assert rel.endswith("SubParts.def")
    _hide_list_matches(staged, CRAC, rel)
    st = fr["standins"]["tris"]
    assert st["0"] > 0 and st["1"] > 0
    assert fr["lods"][0]["tris"] <= 28006 and fr["lods"][0]["tris"] <= fr["budget"][0]
    for i, row in enumerate(fr["lods"][:-1]):
        assert row["tris"] <= fr["budget"][i], (i, row["tris"], fr["budget"][i])
    assert len(fr["lods"]) == len(man["nonfractured"]["lods"])
    assert limits.optimal_lods(tuple(fr["size"]), fr["lods"][0]["tris"])[0] == len(fr["lods"])
