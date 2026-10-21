"""The break faces (FracturedMaterial01 caps) of a part that is hidden under construction.

A cap closes a cut cross-section of one part (fracture_mesh.build_caps: triangle_fill over the part's own cut loop,
so every cap vertex is a vertex of that part). A hidden part (role hide: the trays' cables and ties, the PDU's
breakers, the signs' screens, HIDE_PREFIXES materials) arrives only on completion; its caps went to the zone's own
Fracture_NN-FracturedMaterial01 (Split / HiddenUntilSecondSequenceStart) and stood as loose discs in the empty tray
from 30 % on. They now go to the zone's _Hide group (AlwaysHidden) with the part (export_models._split_cut)."""
import os

import pytest

from dc import catalog, config, state_view as SV
from dc import fracture as FR
from dc import fracture_rules as FRR

CUT_BLOCKS = [b.name for b in catalog.BLOCKS
              if (SV.manifest(b.name, config.MODELS_DIR)["fractured"].get("zones") or [])]
CAP = FR.CUT_MATERIAL


def _key(p):
    return tuple(round(c, 4) for c in p)


def _lod0(name):
    man = SV.manifest(name, config.MODELS_DIR)
    return man, FRR.fbx_meshes(os.path.join(config.MODELS_DIR, name, "Fractured", man["fractured"]["lods"][0]["file"]))


@pytest.mark.build
@pytest.mark.parametrize("name", CUT_BLOCKS)
def test_hidden_parts_caps_hide_with_them(name):
    """No cap face of a hidden part is in a visible group: a cap face all of whose vertices lie on the zone's _Hide
    geometry and not all on its visible geometry is in that zone's _Hide group; and every _Hide cap part is hidden at
    every construction ratio below 1 (c00 .. c77) and shown on the finished block."""
    man, meshes = _lod0(name)
    hide_v, vis_v = {}, {}
    caps = []                                     # (group, [vertex keys]) of every cap face
    for m in meshes.values():
        g = m["props"].get("Group") or ""
        for poly, k in zip(m["polys"], m["poly_mat"]):
            mat = m["materials"][k]
            keys = [_key(m["verts"][i]) for i in poly]
            if mat == CAP:
                caps.append((g, keys))
                continue
            if mat.endswith(FR.SUBPART_SUFFIX) or not g:
                continue
            zone = g.split("_Hide")[0].split("_Support")[0].split("_Frame")[0]
            (hide_v if g.endswith("_Hide") else vis_v).setdefault(zone, set()).update(keys)
    bad = []
    for g, keys in caps:
        zone = g.replace("_Hide", "")
        of_hidden = all(k in hide_v.get(zone, ()) for k in keys) and not all(k in vis_v.get(zone, ()) for k in keys)
        if of_hidden and not g.endswith("_Hide"):
            bad.append((g, keys[0]))
    assert not bad, (name, len(bad), bad[:3])
    hide_caps = sorted(p for p in man["fractured"]["parts"] if p.endswith(f"_Hide-{CAP}"))
    stages = SV.installed_stages(name)
    for ratio in (r for r in SV.SHOTS.values() if r < 1):
        st = SV.part_state(stages, ratio)
        shown = [p for p in hide_caps if st.get(p, (True, None))[0]]
        assert not shown, (name, ratio, shown)
    for p in hide_caps:
        assert man["fractured"]["parts"][p][1] == "AlwaysHidden", (name, p)
