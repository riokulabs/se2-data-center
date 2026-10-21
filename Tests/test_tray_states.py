"""The cable trays' construction states and sparks.

Roles     fracture.ROLES["tray"] follows what the kit's Parts are (dc/tray_kit.py Parts): the cable bundles and their
          dressing (straps, split collars, saddle clamps; their buckles and collar bolts, `tiehw`) are `hide`: pulled
          into the finished tray, they arrive on completion, as vanilla CableStraight250 (65 % of its FR LOD0 in
          `_Hide` groups); the hangers' and the basket's hardware (`hw`) and the strut channels that carry the basket
          (`strut`) are `support`; the basket wire, the tray furniture (`guide`) and the trim stay skin.
Sparks    each per-zone spark dummy (ParticleEffects_<zone>) sits on its zone's cables: the centre of the
          zone's `hide` role box (effects.zone_dummies prefer_role="hide").
Scaffold  a tray's cage follows its zone hulls (scaffold.boxes_for), so a Tee or a Cross is caged along its own
          outline, not as a square round it.

Share floors (set from the shares measured on the exported FR LOD0, break faces and scaffold included):
  hide     Full >= 40 % (the design target; measured 42-60 %), Moderate >= 35 % (38.5-55 %), Low >= 20 %
           (23.7-48.5 %: one or two thin bundles over a full basket); the Empty trays < 10 % (stencils only, 0-0.6 %);
  support  1.5-30 % (measured 1.7 % on the Tee Full, whose cables dwarf its floor strut, to 24.5 % on the StraightS
           Low, a short basket on a trapeze)."""
import os

import pytest

from dc import catalog, config, effects, integration, scaffold as SC, state_view as SV
from dc import fracture as FR
from dc import fracture_rules as FRR
from dc.assetio import read_json

TRAYS = [b.name for b in catalog.BLOCKS if b.family == "tray"]
CUT = [n for n in TRAYS if FR.unfractured_reason(catalog.BY_NAME[n]) is None]
WITH_CABLES = [n for n in CUT if not n.endswith("_Empty")]
EMPTY = [n for n in CUT if n.endswith("_Empty")]
HIDE_FLOOR = {"Low": 0.20, "Moderate": 0.35, "Full": 0.40}
SUPPORT_RANGE = (0.015, 0.30)
EMPTY_CEIL = 0.10
SHOTS_BELOW_DONE = sorted(r for r in SV.SHOTS.values() if r < 1)
GROW = 0.005
NEAR_CABLE = 0.2      # a spark dummy within this of its zone's nearest cable vertex (measured <= 0.142 m)


def _man(name):
    return read_json(os.path.join(config.MODELS_DIR, name, "export.json"))


def _hide_share(name):
    fr = _man(name)["fractured"]
    return fr["role_tris"]["hide"] / fr["lods"][0]["tris"]


@pytest.fixture(scope="module")
def staged(stage_package):
    return stage_package()


# ---------------------------------------------------------------------------------------------------- pure
def test_tray_role_table():
    """The table names the kit's Parts by what they are (dc/tray_kit.py Parts): every name is a real Part, the basket
    wire and the tray furniture are skin (not in the table), and the dressing metal is kept whole like hw."""
    t = FR.ROLES["tray"]
    assert t == {"hide": ("cable", "tie", "tiehw"), "support": ("hw", "strut")}
    for part in ("wire", "guide", "trim", "card", "solid"):
        assert FR.role_of("tray", part, "BrushedMetal") == "skin", part
    assert FR.role_of("tray", "cable", "Rubber") == "hide"
    assert FR.role_of("tray", "strut", "PaintedMetalDarker") == "support"
    assert "tiehw" in FR.KEEP_WHOLE["tray"]


def test_zone_dummies_prefer_role():
    """prefer_role: a per-zone dummy goes to the centre of the zone's role box when it has one, else its hull's."""
    zs = [{"id": "Fracture_01", "lo": [-1, -1, -1], "hi": [0, 1, 1], "health_share": 0.6},
          {"id": "Fracture_02", "lo": [0, -1, -1], "hi": [1, 1, 1], "health_share": 0.4},
          {"id": "Fracture_03", "lo": [1, -1, -1], "hi": [2, 1, 1], "health_share": 0.2}]
    rb = {"Fracture_02": {"skin": [0, -1, -1, 1, 1, 1], "hide": [0.2, 0.0, 0.5, 0.4, 0.2, 0.7]},
          "Fracture_03": {"skin": [1, -1, -1, 2, 1, 1]}}
    out = effects.zone_dummies({"zones": zs, "role_bounds": rb}, (0, 0, 0), True, prefer_role="hide")
    assert out[0] == ("ParticleEffects", (0, 0, 0), "Fracture_01")
    assert out[1] == ("ParticleEffects_Fracture_02", effects.blender_to_game((0.3, 0.1, 0.6), (0, 0, 0)),
                      "Fracture_02")
    assert out[2] == ("ParticleEffects_Fracture_03", effects.blender_to_game((1.5, 0, 0), (0, 0, 0)), "Fracture_03")


# ---------------------------------------------------------------------------------------------------- build
def _stages(name):
    """The block's stages as this run staged them (integration.write_all): the installed copy follows on install."""
    return read_json(SV.bmd_path(name, config.STAGE_ASSETS))["$Value"]["Manipulator"]["BuildProgressModels"]


@pytest.mark.build
@pytest.mark.parametrize("name", WITH_CABLES)
def test_cables_arrive_on_completion(staged, name):
    """The cables are pulled into the finished tray: their share of the FR LOD0 is at least the density's floor, and
    every Fracture_NN_Hide part is hidden at every build ratio below 1 (shown on completion)."""
    density = name.rsplit("_", 1)[1]
    assert _hide_share(name) >= HIDE_FLOOR[density], (name, round(_hide_share(name), 3))
    hide = [p for p in _man(name)["fractured"]["parts"] if p.split("-", 1)[0].endswith("_Hide")]
    assert any(not FR.is_hide(p.split("-", 1)[1]) for p in hide), name      # cable parts, not only stencils
    st = _stages(name)
    for r in SHOTS_BELOW_DONE:
        ps = SV.part_state(st, r)
        shown = [p for p in hide if ps.get(p, (True, None))[0]]
        assert not shown, (name, r, shown)
    assert SV.part_state(st, 1.0) == {}


@pytest.mark.build
@pytest.mark.parametrize("name", EMPTY)
def test_empty_trays_have_no_cable_hide(name):
    """An Empty tray hides its stencils only (no cables)."""
    assert _hide_share(name) < EMPTY_CEIL, name
    hide = [p for p in _man(name)["fractured"]["parts"] if p.split("-", 1)[0].endswith("_Hide")]
    assert all(FR.is_hide(p.split("-", 1)[1]) for p in hide), (name, hide)


@pytest.mark.build
@pytest.mark.parametrize("name", WITH_CABLES)
def test_tray_supports(name):
    """The hangers and their hardware are supports: a Fracture_NN_Support group exists, its share of the LOD0
    within SUPPORT_RANGE (measured)."""
    fr = _man(name)["fractured"]
    share = fr["role_tris"]["support"] / fr["lods"][0]["tris"]
    assert SUPPORT_RANGE[0] <= share <= SUPPORT_RANGE[1], (name, round(share, 3))
    assert any(p.split("-", 1)[0].endswith("_Support") for p in fr["parts"]), name


@pytest.mark.build
def test_spark_dummies_on_cables(staged):
    """Every ParticleEffects_<zone> dummy of a tray, back in the Blender frame, lies inside its zone's `hide`
    role box grown by 5 mm and within NEAR_CABLE of the nearest vertex of that zone's hide meshes in the FR LOD0 (it
    sparks on the cables, not in the empty air of a bend: the box centre alone could miss a bundle)."""
    seen = 0
    for name in WITH_CABLES:
        man = _man(name)
        sh = man["shift"]
        meshes = FRR.fbx_meshes(os.path.join(config.MODELS_DIR, name, "Fractured",
                                             man["fractured"]["lods"][0]["file"]))
        hide_verts = {}
        for m in meshes.values():
            g = m["props"].get("Group") or ""
            if g.endswith("_Hide"):
                hide_verts.setdefault(g[:-len("_Hide")], []).extend(m["verts"])
        bmd = read_json(SV.bmd_path(name, config.STAGE_ASSETS))
        for d in SV.dummies_of(bmd["$Value"]["Manipulator"]):
            if d["Type"] != effects.PARTICLE_EFFECTS_TYPE or not d["Name"].startswith("ParticleEffects_"):
                continue
            z = d["SupportingFracture"]["Id"]
            assert d["Name"] == f"ParticleEffects_{z}", (name, d["Name"])
            g = d["Transform"]["Transform"]["Position"]
            p = (g["X"] - sh[0], -(g["Z"] - sh[2]), g["Y"] - sh[1])        # game -> Blender (effects.blender_to_game)
            box = man["fractured"]["role_bounds"][z]["hide"]
            for i in range(3):
                assert box[i] - GROW <= p[i] <= box[3 + i] + GROW, (name, d["Name"], p, box)
            near = min(sum((a - b) ** 2 for a, b in zip(v, p)) ** 0.5 for v in hide_verts[z])
            assert near <= NEAR_CABLE, (name, d["Name"], round(near, 3))
            seen += 1
    assert seen >= len(WITH_CABLES), seen


@pytest.mark.build
@pytest.mark.parametrize("name", [n for n in CUT if "_Tee_" in n or "_Cross_" in n])
def test_tray_scaffold_follows_shape(name):
    """A Tee's and a Cross's scaffold boxes are their zone hull AABBs (one per zone, each within the snap tolerance
    and OUTSET of its zone's box), not the envelope: their union leaves the free corner cells open."""
    fr = _man(name)["fractured"]
    sp = fr["scaffold"]
    assert sp, name
    zones = fr["zones"]
    boxes = sp["boxes"]
    assert len(boxes) == len(zones), name
    tol = 2 * sp["radius"] + SC.OUTSET + 1e-5
    for (lo, hi), z in zip(boxes, zones):
        for i in range(3):
            assert z["lo"][i] - tol <= lo[i] and hi[i] <= z["hi"][i] + tol, (name, z["id"], i)
            assert lo[i] <= z["lo"][i] + tol and z["hi"][i] - tol <= hi[i], (name, z["id"], i)
    vol = sum((hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2]) for lo, hi in boxes)
    elo = [min(b[0][i] for b in boxes) for i in range(3)]
    ehi = [max(b[1][i] for b in boxes) for i in range(3)]
    env = (ehi[0] - elo[0]) * (ehi[1] - elo[1]) * (ehi[2] - elo[2])
    assert vol < 0.95 * env, (name, vol, env)
