"""Plan 5 Task 4: damage effects. The UPS's ParticleEffects dummies per bay (G3), the vanilla 4.0 spark bands on the
trays, PDUs and deco servers with dummies that follow the fracture zones (G7), the KVM's ControlPanel25 sparks and
the Programmable's Timer set.

Vanilla values are read from tools/vanilla-ref and the Mod SDK (read-only); the effective (client) BlockEffects of a
block is resolved through its client composition with tools/scripts/block_chain.py over the SDK, the mod's Assets
and this run's staging (the files install.sh will write)."""
import json
import os
import sys
from pathlib import Path

import pytest

from dc import catalog, clone, config, effects, integration
from dc.assetio import own_guid, read_json
from dc import state_view as SV

PE = "e9f28118-a0cf-4c6c-b6ad-2e0719e6cf5a"
ELEC_MEDIUM = "2113ece5-6d63-4753-b12a-83664c3b22e9"   # System/Particles/.../ElectricalDamageMedium
ELEC_SMALL = "617b0925-68b8-4683-acfe-2a71111a5d49"    # ElectricalDamageSmall
SMOKE_SMALL_SET = "d8cb4c53-5d1b-4aaa-9b56-71bb67ad1dd7"
CP25_REMOVED = "92d61473-88b0-416b-a1f0-272b0e1c4c8f"  # the 2.4 band-0 effect ControlPanel25 4.0 removes
CP25_EFFECTS = "ea688c5e-3d20-4a08-a688-0d726a3554e4"   # Blocks/ControlPanel/25/ControlPanel25_BlockEffects...
TIMER = "2cad179b-6b5b-41d9-99ea-e5e44f102485"
UPS = "DC_Srv_UPS"
BLOCK_CHAIN = os.path.join(config.TOOLS_DIR, "scripts")
SDK_ASSETS = os.path.expanduser("~/.steam/debian-installation/steamapps/common/Space Engineers 2 - Mod SDK/GameData/"
                                "Vanilla/Assets")

TRAYS_WITH_CABLES = [f"DC_Tray_{s}_{d}" for s in ("StraightS", "StraightL", "TurnH", "TurnUp", "TurnDown", "Tee",
                                                  "Cross", "Drop", "Reducer") for d in ("Low", "Moderate", "Full")]
BREAKERS = ["DC_PDU_Cabinet", "DC_PDU_Rack42_A", "DC_PDU_Rack42_B", "DC_PDU_Rack24_A", "DC_PDU_Rack24_B",
            "DC_Srv_Compute", "DC_Srv_Storage", "DC_Srv_Switch", "DC_Srv_Blank"]


@pytest.fixture(scope="module")
def staged(stage_package):
    return stage_package()


@pytest.fixture(scope="module")
def chain(staged):
    """block_chain.Index over the SDK with the mod's definitions (installed, then this run's staged copies) on top."""
    sys.path.insert(0, BLOCK_CHAIN)
    try:
        import block_chain
    finally:
        sys.path.remove(BLOCK_CHAIN)
    if not block_chain.SDK.is_dir():
        pytest.skip("Mod SDK not installed")
    idx = block_chain.Index()
    for root in (config.MOD_ASSETS, config.STAGE_ASSETS):
        mod = block_chain.Index(Path(root))
        idx.by_guid.update(mod.by_guid)
        for k, v in mod.overrides.items():
            idx.overrides[k].extend(v)
    return idx


def _composition(name):
    """The block's own client composition (mod-relative; not its subparts')."""
    cc = [f for f in integration._block_files(catalog.BY_NAME[name], "_ClientComposition")
          if os.path.basename(f).startswith(f"{name}_ClientComposition.")]
    assert len(cc) == 1, (name, cc)
    return cc[0]


def _client_effects(idx, name):
    """The resolved BlockEffects definition the block's client composition binds (and its GUID)."""
    comp = idx.resolve(own_guid(integration.read_current(_composition(name))))
    ds = [c["Value"]["Definition"] for c in comp["Components"] if isinstance(c.get("Value"), dict)
          and idx.type_of(c["Value"].get("Definition")) == "BlockEffectsComponentDefinition"]
    assert len(ds) == 1, (name, ds)
    return ds[0], idx.resolve(ds[0])


def _bands(eff):
    return [b["Value"] for b in eff.get("OnDamagedBlockParticleEffect") or []]


def _dummies(name):
    bmd = integration.read_current(clone.entry(catalog.BY_NAME[name])["info"]["model_def_file"])
    return SV.dummies_of(bmd["$Value"]["Manipulator"])


def _pos(d):
    p = d["Transform"]["Transform"]["Position"]
    return [p["X"], p["Y"], p["Z"]]


def _bound_effects_file(name):
    """The cloned BlockEffects file (mod-relative) the client composition binds, as staged."""
    spec = catalog.BY_NAME[name]
    cc = integration.read_current(_composition(name))
    bound = {c["Value"].get("Definition") for c in cc["$Value"]["Manipulator"]["Components"]["Changed"]
             if isinstance(c.get("Value"), dict)}
    files = [f for f in integration._block_files(spec, "BlockEffectsComponentDefinition")
             if own_guid(integration.read_current(f)) in bound]
    assert len(files) == 1, (name, files)
    return files[0]


# ---------------------------------------------------------------------------------------------- which blocks spark
def test_spark_blocks():
    """36 blocks: the 27 breakable trays with cables (cable), the PDU cabinet, the 4 strips and the 4 deco servers
    (breaker); the Empty trays, the non-breakable Chute and everything else: none."""
    kinds = {b.name: effects.spark_kind(b) for b in catalog.STAGED}
    assert sorted(n for n, k in kinds.items() if k == "cable") == sorted(TRAYS_WITH_CABLES)
    assert sorted(n for n, k in kinds.items() if k == "breaker") == sorted(BREAKERS)
    assert sum(1 for k in kinds.values() if k) == 36
    assert kinds["DC_Tray_Chute"] is None and kinds["DC_Tray_Tee_Empty"] is None and kinds["DC_Srv_KVM"] is None


@pytest.mark.skipif(not os.path.isdir(SDK_ASSETS), reason="Mod SDK not installed")
def test_spark_sources_are_the_4_0_sdk():
    """tools/vanilla-ref's three source files are the 4.0 SDK's, byte for byte, and say what the plan copies."""
    for kind, rel in effects.SPARK_SOURCES.items():
        with open(os.path.join(config.VANILLA_REF, rel), "rb") as a, open(os.path.join(SDK_ASSETS, rel), "rb") as b:
            assert a.read() == b.read(), rel
    for kind, fx, upper in (("cable", ELEC_MEDIUM, 0.99), ("breaker", ELEC_SMALL, 0.99)):
        b = effects.vanilla_band(kind)
        assert (b["HealthIntegrityLowerThreshold"], b["HealthIntegrityUpperThreshold"]) == (0, upper), kind
        assert [(e["Value"]["ParticleEffect"], e["Value"]["Dummy"]) for e in b["ParticleEffects"]] == [(fx, PE)], kind
    cp = effects.vanilla_band("cp25")
    assert cp["HealthIntegrityUpperThreshold"] == 0.99
    assert cp["ParticleEffects"]["Changed"][0]["Value"] == {"ParticleEffect": ELEC_SMALL, "Dummy": PE, "Scale": 0.3}


# ---------------------------------------------------------------------------------------------- the bands
def test_spark_band_matches_vanilla(staged):
    """Each spark block's bound BlockEffects Copy inserts exactly one band, the vanilla one verbatim (0 - 0.99, one
    effect on the ParticleEffects dummy at the vanilla scale), with stable keys from asset_guids.json."""
    from dc.guids import Guids
    G = Guids()
    for b in catalog.STAGED:
        kind = effects.spark_kind(b)
        if not kind:
            continue
        m = integration.read_current(_bound_effects_file(b.name))["$Value"]["Manipulator"]
        d = m["OnDamagedBlockParticleEffect"]
        assert d["$DeltaEncoded"] and d["Removed"] == [] and len(d["Changed"]) == 1, b.name
        assert d["Keys"] == [G[f"band/{b.name}/spark"]] and d["Changed"][0]["Kind"] == "Insert", b.name
        v = d["Changed"][0]["Value"]
        assert (v["HealthIntegrityLowerThreshold"], v["HealthIntegrityUpperThreshold"]) == (0, 0.99), b.name
        assert len(v["ParticleEffects"]) == 1, b.name
        fx = v["ParticleEffects"][0]
        assert fx["Key"] == G[f"band/{b.name}/spark/fx"], b.name
        want = effects.vanilla_band(kind)["ParticleEffects"][0]["Value"]
        assert fx["Value"] == {"ParticleEffect": ELEC_MEDIUM if kind == "cable" else ELEC_SMALL, "Dummy": PE,
                               "Scale": want["Scale"]}, b.name


def test_spark_effects_idempotent(staged):
    """Re-patching an already patched (staged) BlockEffects changes nothing."""
    from dc.guids import Guids
    for n in ("DC_Tray_Tee_Full", "DC_PDU_Cabinet", "DC_Srv_Compute"):
        f = _bound_effects_file(n)
        before = json.dumps(integration.read_current(f), sort_keys=True)
        integration.patch_spark_effects(catalog.BY_NAME[n], Guids())
        assert json.dumps(integration.read_current(f), sort_keys=True) == before, n


def test_every_band_dummy_exists(staged, chain):
    """Review Focus 4. For all 73 blocks: every Dummy type a resolved client damage band names has >= 1 dummy of that
    type in the staged BlockModelDefinition (no silent band: the UPS class of bug, G3), and the first ParticleEffects
    dummy (the death effect's origin, R15) is the centre "ParticleEffects" at the block centre (export.json "shift"),
    the UPS included (controller ruling, superseding R9: its bay dummies follow an unsupported centre one)."""
    assert len(catalog.STAGED) == 73
    for b in catalog.STAGED:
        _, eff = _client_effects(chain, b.name)
        dums = _dummies(b.name)
        types = {d["Type"] for d in dums}
        for band in _bands(eff):
            for e in band["ParticleEffects"]:
                t = e["Value"].get("Dummy")
                if e["Value"].get("ParticleEffect") and t:
                    assert t in types, (b.name, band, t)
        first = next(d for d in dums if d["Type"] == PE)
        assert first["Name"] in ("ParticleEffects", "Particles"), (b.name, first["Name"])   # (door racks: Particles)
        assert _pos(first) == pytest.approx(SV.manifest(b.name)["shift"]), b.name


def test_spark_emitters_capped(staged):
    """Controller ruling: no block has more than effects.MAX_EMITTERS (3) ParticleEffects-type dummies (each one is an
    emitter of every band); the PDU cabinet has exactly 3, one per zone group (bottom, middle = centre, top)."""
    assert effects.MAX_EMITTERS == 3
    for b in catalog.STAGED:
        n = len([d for d in _dummies(b.name) if d["Type"] == PE])
        assert n <= 3, (b.name, n)
    pe = [d for d in _dummies("DC_PDU_Cabinet") if d["Type"] == PE]
    assert [d["SupportingFracture"]["Id"] for d in pe] == ["Fracture_05", "Fracture_03", "Fracture_07"]


def test_spark_dummies_follow_zones(staged):
    """Every ParticleEffects-type dummy of a spark block is supported by one of its zones; the centre one keeps its
    name and the block-centre position; a per_zone block has one such dummy per zone up to 3 zones (more: 3, on
    distinct zones), each inside its zone's hull AABB (R11: the per-zone ones are ParticleEffects_<zone>)."""
    for b in catalog.STAGED:
        if not effects.spark_kind(b):
            continue
        man = SV.manifest(b.name)
        zones = {z["id"]: z for z in man["fractured"]["zones"]}
        pe = [d for d in _dummies(b.name) if d["Type"] == PE]
        assert pe[0]["Name"] == "ParticleEffects" and _pos(pe[0]) == pytest.approx(man["shift"]), b.name
        sup = [(d.get("SupportingFracture") or {}).get("Id") for d in pe]
        assert all(z in zones for z in sup), (b.name, sup)
        if effects.per_zone(b):
            if len(zones) <= 3:
                assert sorted(sup) == sorted(zones), (b.name, sup)
            else:
                assert len(sup) == 3 and len(set(sup)) == 3, (b.name, sup)
            for d, z in zip(pe[1:], sup[1:]):
                assert d["Name"] == f"ParticleEffects_{z}", b.name
                lo = effects.blender_to_game(zones[z]["lo"], man["shift"])
                hi = effects.blender_to_game(zones[z]["hi"], man["shift"])
                for c, a, e in zip(_pos(d), lo, hi):
                    assert min(a, e) - 1e-6 <= c <= max(a, e) + 1e-6, (b.name, d["Name"])
        else:
            assert len(pe) == 1, b.name


def test_zone_dummies_rules():
    """The centre zone is the one whose AABB holds the centre (largest share when a seam runs through it); per_zone
    adds the others in zone order."""
    zs = [{"id": "Fracture_01", "lo": [-1, -1, -1], "hi": [0, 1, 1], "health_share": 0.3},
          {"id": "Fracture_02", "lo": [0, -1, -1], "hi": [1, 1, 1], "health_share": 0.5},
          {"id": "Fracture_03", "lo": [1, -1, -1], "hi": [3, 1, 1], "health_share": 0.2}]
    out = effects.zone_dummies({"zones": zs}, (0.125, 0, 0), True)
    assert out[0] == ("ParticleEffects", (0.125, 0, 0), "Fracture_02")
    assert out[1:] == [("ParticleEffects_Fracture_01", (-0.375, 0.0, 0.0), "Fracture_01"),
                       ("ParticleEffects_Fracture_03", (2.125, 0.0, 0.0), "Fracture_03")]
    assert len(effects.zone_dummies({"zones": zs}, (0, 0, 0), False)) == 1
    # more than 3 zones: grouped along the longest axis (x) below / around / above the centre zone, one each
    zs4 = zs + [{"id": "Fracture_04", "lo": [3, -1, -1], "hi": [4, 1, 1], "health_share": 0.25},
                {"id": "Fracture_05", "lo": [0, 1, -1], "hi": [1, 2, 1], "health_share": 0.1}]
    assert [z for _, _, z in effects.zone_dummies({"zones": zs4}, (0, 0, 0), True)] == \
        ["Fracture_02", "Fracture_01", "Fracture_04"]
    outside = [dict(z, lo=[5, 5, 5], hi=[6, 6, 6]) for z in zs]
    assert effects.zone_dummies({"zones": outside}, (0, 0, 0), False)[0][2] == "Fracture_02"


# ---------------------------------------------------------------------------------------------- UPS, KVM, Programmable
def test_ups_particle_dummies(staged):
    """G3: the UPS has an unsupported centre "ParticleEffects" first (as Battery50; controller ruling: the death
    effect's origin), then one per bay ("ParticleEffects <i>", as its "CellSlot <i>"), supported like that bay's cell
    slot (bay 0 front: Fracture_01, bay 1 rear: Fracture_02), inside the bay's zone; the unnamed
    ConstructionStagesParticles dummy stays."""
    dums = {d.get("Name"): d for d in _dummies(UPS)}
    man = SV.manifest(UPS)
    zones = {z["id"]: z for z in man["fractured"]["zones"]}
    for i, zid in ((0, "Fracture_01"), (1, "Fracture_02")):
        p = dums[f"ParticleEffects {i}"]
        assert p["Type"] == PE
        assert p["SupportingFracture"] == dums[f"CellSlot {i}"]["SupportingFracture"] == {"Id": zid}
        lo = effects.blender_to_game(zones[zid]["lo"], man["shift"])
        hi = effects.blender_to_game(zones[zid]["hi"], man["shift"])
        for c, a, e in zip(_pos(p), lo, hi):
            assert min(a, e) <= c <= max(a, e), (i, _pos(p))
    assert [d for d in dums.values() if d["Type"] == PE] == \
        [dums["ParticleEffects"], dums["ParticleEffects 0"], dums["ParticleEffects 1"]]
    assert dums["ParticleEffects"]["SupportingFracture"] is None
    assert _pos(dums["ParticleEffects"]) == pytest.approx(man["shift"])
    assert None in dums and dums[None]["Type"] == integration.CONSTRUCTION_PARTICLES


def test_kvm_sparks_like_cp25(staged, chain):
    """Controller ruling: the KVM's damage band is 4.0 ControlPanel25's (0 - 0.99, ElectricalDamageSmall x0.3 on the
    ParticleEffects dummy); the 2.4 effect key stays removed and no SmokeSmall set remains."""
    _, eff = _client_effects(chain, "DC_Srv_KVM")
    bands = _bands(eff)
    b0 = bands[0]
    assert (b0["HealthIntegrityLowerThreshold"], b0["HealthIntegrityUpperThreshold"]) == (0, 0.99)
    assert [e["Value"] for e in b0["ParticleEffects"]] == [{"ParticleEffect": ELEC_SMALL, "Dummy": PE, "Scale": 0.3}]
    keys = [e["Key"] for b in eff["OnDamagedBlockParticleEffect"] for e in b["Value"]["ParticleEffects"]]
    assert CP25_REMOVED not in keys
    assert SMOKE_SMALL_SET not in json.dumps(eff["OnDamagedBlockParticleEffect"])
    cp25 = chain.resolve(CP25_EFFECTS)     # vanilla 4.0 ControlPanel25's own: the same resolved bands
    assert eff["OnDamagedBlockParticleEffect"] == cp25["OnDamagedBlockParticleEffect"]


def test_programmable_timer_effects(staged, chain):
    """The Programmable's BlockEffects Copy is re-based onto the vanilla Timer template (3 bands: sparks below 95 %,
    smoke 90 - 65 %, fire below 65 %), its own GUID kept (still bound in the client composition)."""
    f = _bound_effects_file("DC_Srv_Programmable")
    v = integration.read_current(f)["$Value"]
    assert v["BaseDefinition"] == TIMER
    assert own_guid(read_json(os.path.join(config.MOD_ASSETS, f))) == v["Manipulator"]["Guid"]
    g, eff = _client_effects(chain, "DC_Srv_Programmable")
    assert g == v["Manipulator"]["Guid"]
    assert [(b["HealthIntegrityLowerThreshold"], b["HealthIntegrityUpperThreshold"]) for b in _bands(eff)] == \
        [(0, 0.95), (0.65, 0.9), (0, 0.65)]
