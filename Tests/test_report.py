import json
import os

import pytest

from dc import catalog, config


@pytest.mark.build
def test_report_has_every_block():
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        data = json.load(f)
    # every pipeline block, plus any other catalogue block that has been built (Ruling P2-15: trays before Task 5)
    names = set(data["blocks"])
    assert names >= {b.name for b in catalog.BLOCKS}
    assert names <= {b.name for b in catalog.CATALOGUE}
    for n in names - {b.name for b in catalog.BLOCKS}:
        assert data["blocks"][n]["placement"]["total"], n
