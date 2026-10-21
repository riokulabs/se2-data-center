"""The damage look and the fragility fixes, all data.

Look       every Damaged .model maps the painted / brushed / chrome slots to vanilla 4.0's scratched parallax Deformed
           materials, as vanilla's own Deformed models do (tools/vanilla-ref, measured below);
Fragility  the Programmable resolves to the Functional fragility (vanilla's PowerableBlockDefinition template
           value, which every powerable block such as Timer50 inherits), the containment roofs to Windows (as
           vanilla WindowFlat / WallInsertWindowFlat150) with the vanilla Windows BlockEffects (glass shatter,
           glass audio).
"""
import collections
import glob
import os
import sys

import pytest

from dc import catalog, clone, config, integration
from dc.assetio import read_json

DEFORMED = {"PaintedMetalColorable": "d8847d2a-cbb3-4982-9036-ee7785cce3c1",
            "PaintedMetalDarker": "ea15e749-58ce-4ca8-95e2-307af0bd273d",
            "BrushedMetal": "d2d76bf2-2c7c-4798-8eec-c515c07b84cc",
            "Chrome": "4418666d-ba5b-481c-b9a3-e7233fc001a8"}
STRUCTURAL = "c748fae2-a8fe-4012-9936-cf2a570fa685"   # vanilla Blocks/Shared/Fragility/Structural.def
FUNCTIONAL = "eaaa3a8d-d04c-461f-a7f5-00e8cabd27bd"   # .../Functional.def
WINDOWS = "060b61a3-51ed-4a47-8d4e-e3c2f8712216"      # .../Windows.partialdef
WINDOWS_EFFECTS = "30c64f59-209d-40b7-97d2-b7aaaf9a1add"   # Blocks/Windows/Windows_BlockEffectsComponentDefinition
FUNCTIONAL_BLOCKS = {f"DC_Rack{h}_{v}" for h in (42, 24) for v in ("SplitFront", "SplitFrontRear")} | {
    "DC_Srv_Timer", "DC_Srv_EventCtl", "DC_Srv_KVM", "DC_Srv_Status", "DC_Srv_UPS", "DC_Srv_Programmable",
    "DC_Contain_Door_100", "DC_Contain_Door_150", "DC_Contain_Door_200", "DC_CRAC",
    "DC_Sign_Aisle", "DC_Sign_AisleHang", "DC_Sign_Rack"}
ROOFS = ("DC_Contain_Roof_100", "DC_Contain_Roof_150", "DC_Contain_Roof_200")
VANILLA_BLOCKS = os.path.join(config.VANILLA_REF, "Blocks")
BLOCK_CHAIN = os.path.join(config.TOOLS_DIR, "scripts")


@pytest.fixture(scope="module")
def staged(stage_package):
    stage_package()
    return config.STAGE_ASSETS


@pytest.fixture(scope="module")
def sdk():
    sys.path.insert(0, BLOCK_CHAIN)
    try:
        import block_chain
    finally:
        sys.path.remove(BLOCK_CHAIN)
    if not block_chain.SDK.is_dir():
        pytest.skip("Mod SDK not installed")
    return block_chain.Index()


def _value(d):
    v = d["$Value"]
    return v["Manipulator"] if "PartialDefinitionKind" in v else v


def _assign(path):
    return {a["MaterialName"]: a["MaterialReference"] for a in read_json(path)["$Value"]["MaterialAssignments"]}


def _damaged(staged):
    out = {}
    for spec in catalog.STAGED:
        p = os.path.join(staged, config.NAME, spec.name, "Models", "Damaged", f"{spec.name}_Damaged.model")
        if os.path.exists(p):
            out[spec.name] = p
    return out


# ---------------------------------------------------------------------------------------------------- damage look
def test_deformed_remap(staged):
    """Each Damaged .model maps the four metal slots to the 4.0 Deformed materials; every other slot is mapped as in
    test_fracture_plan.py::test_damaged_model_maps_broken_materials (DAMAGED_SLOTS, else the Fractured .model's)."""
    from dc import fracture as FR
    from dc.material_guids import MATERIAL_GUIDS
    dms = _damaged(staged)
    assert len(dms) == 73, sorted(dms)   # every block (the 4 unfractured ones' dented debris too)
    seen = collections.Counter()
    for n, p in dms.items():
        fr = _assign(p.replace("Damaged", "Fractured"))
        dm = _assign(p)
        assert set(dm) <= set(fr) and set(fr) - set(dm) <= {"BrushedMetal"}, n   # the FR-only scaffold
        for slot, ref in dm.items():
            if slot in DEFORMED:
                assert ref == DEFORMED[slot], (n, slot, ref)
                seen[slot] += 1
            elif FR.damaged_slot(slot) != slot:          # (a stand-in's `_Subpart` slot: its base's)
                assert ref == MATERIAL_GUIDS[FR.damaged_slot(slot)][0], (n, slot)
            else:
                assert ref == fr[slot], (n, slot)
    # the remap reaches real slots (2026-10-19: Darker 69, BrushedMetal 63, Colorable 62 of 69 Damaged models; no
    # block has a Chrome slot yet, its vanilla mapping is kept for the first one that does)
    assert min(seen["PaintedMetalColorable"], seen["PaintedMetalDarker"], seen["BrushedMetal"]) >= 50, seen


@pytest.mark.skipif(not os.path.isdir(VANILLA_BLOCKS), reason="tools/vanilla-ref not present")
def test_deformed_remap_is_vanilla_majority():
    """In vanilla 4.0's Deformed models each of the four slots maps, in the large majority, to exactly the material
    we map it to (measured 2026-10-19: Colorable 249/264, Darker 239/251, BrushedMetal 87/97, Chrome 131/134)."""
    c = collections.defaultdict(collections.Counter)
    for f in glob.glob(os.path.join(VANILLA_BLOCKS, "**", "*Deformed*.model"), recursive=True):
        for slot, ref in _assign(f).items():
            if slot in DEFORMED:
                c[slot][ref] += 1
    for slot, want in DEFORMED.items():
        ref, k = c[slot].most_common(1)[0]
        assert ref == want and k >= 0.85 * sum(c[slot].values()), (slot, c[slot])


# ---------------------------------------------------------------------------------------------------- fragility
def _resolved_fragility(staged, sdk, spec):
    info = clone.entry(spec)["info"]
    d = read_json(os.path.join(staged, info["block_def_file"]))["$Value"]
    m = d["Manipulator"]
    return m["Fragility"] if "Fragility" in m else sdk.resolve(d["BaseDefinition"])["Fragility"]


def test_fragility_per_archetype(staged, sdk):
    """The resolved Fragility of all 73 block definitions: Functional for the working blocks, Windows for the roofs,
    Structural for every other block."""
    assert len(catalog.STAGED) == 73
    for spec in catalog.STAGED:
        want = FUNCTIONAL if spec.name in FUNCTIONAL_BLOCKS else WINDOWS if spec.name in ROOFS else STRUCTURAL
        assert _resolved_fragility(staged, sdk, spec) == want, spec.name
    assert integration.FRAGILITY == {"Structural": STRUCTURAL, "Functional": FUNCTIONAL, "Windows": WINDOWS}
    for g in integration.FRAGILITY.values():                     # each a vanilla 4.0 fragility definition
        assert sdk.type_of(g).endswith("CubeBlockFragilityDefinition"), g


def test_roof_windows_effects(staged, sdk):
    """Each roof's cloned BlockEffects Copy is based on the vanilla Windows BlockEffects (glass-shatter fracture and
    death effects, glass damage / destroy audio), still bound in the client composition, and overrides none of the
    Windows effects; re-basing again changes nothing."""
    w = sdk.resolve(WINDOWS_EFFECTS)
    for n in ROOFS:
        spec = catalog.BY_NAME[n]
        files = integration._block_files(spec, "BlockEffectsComponentDefinition")
        assert len(files) == 1, files
        d = read_json(os.path.join(staged, files[0]))
        assert d["$Value"]["BaseDefinition"] == WINDOWS_EFFECTS, n
        m = d["$Value"]["Manipulator"]
        for k in ("OnFractureBlockParticleEffect", "OnBlockDeathParticleEffect", "OnDamagedAudio", "OnDestroyedAudio"):
            assert k not in m, (n, k)
        assert w["OnDestroyedAudio"] == "event:/SFX/Explosions/DestroyGlassBlock"
        cc = integration.read_current(integration._block_files(spec, "_ClientComposition")[0])
        assert m["Guid"] in str(cc), n
        assert integration.patch_roof_effects(spec) == WINDOWS_EFFECTS


def test_programmable_hp_changes(staged, sdk):
    """The Programmable's resolved MaxHP mass multiplier is 0.8 (Functional; it was 1.0 as Structural)."""
    frag = _resolved_fragility(staged, sdk, catalog.BY_NAME["DC_Srv_Programmable"])
    assert sdk.resolve(frag)["MaxHPMassMultiplier"] == 0.8
    assert sdk.resolve(STRUCTURAL)["MaxHPMassMultiplier"] == 1
