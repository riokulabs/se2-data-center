"""The build- and damage-state `after` render set (states_preview.py --set=after) is complete.

Rendered by `blender -b --python Source/Model/states_preview.py -- --set=after` (every block of the catalogue plus
every family's vanilla analogues, dc/state_view.ANALOGUE) and laid out by
`python3 Source/Model/states_sheet.py --set=after --before=baseline --by-family`. Everything under
Source/Model/preview is local render output, out of git, so the test skips on a checkout that has not rendered it.
"""
import json
import os

import pytest

from dc import catalog, config, state_view as SV

AFTER = os.path.join(config.PREVIEW_DIR, "dmg-build", "after")
NOT_RENDERED = "local render output, not tracked: run states_preview.py --set=after to produce it"


def _load(name):
    path = os.path.join(AFTER, name)
    if not os.path.exists(path):
        pytest.skip(f"{name}: {NOT_RENDERED}")
    with open(path) as f:
        return json.load(f)


def test_after_set_complete():
    """The manifest holds all 73 blocks with every shot (c00 .. broken; the unfractured ones also `debris`), the
    analogues file every family's vanilla analogue with the same shots, and every listed shot has both views."""
    man = _load("manifest.json")
    ana = _load("analogues.json")
    assert len(catalog.BLOCKS) == 73
    assert set(man) == {b.name for b in catalog.BLOCKS}
    for name, shots in man.items():
        assert tuple(shots[:len(SV.ALL_SHOTS)]) == SV.ALL_SHOTS, name
        assert shots[len(SV.ALL_SHOTS):] in ([], [SV.DEBRIS_SHOT]), name
    want = {"V_" + a for f in {b.family for b in catalog.BLOCKS} for a in SV.ANALOGUE[f]}
    assert set(ana) == want
    for key, shots in ana.items():
        assert tuple(shots) == SV.ALL_SHOTS, key
    for key, shots in list(man.items()) + list(ana.items()):
        for shot in shots:
            for view in SV.VIEWS:
                assert os.path.exists(os.path.join(AFTER, key, f"{shot}_{view}.png")), (key, shot, view)
