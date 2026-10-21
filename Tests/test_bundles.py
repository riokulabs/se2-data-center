"""Every "Bundle:Type" name in a Data Center asset file is resolvable: its bundle is declared in the file's own
$Bundles (Plan 4 Task 3 review C1). In archive-format JSON the serializer resolves a type name only through the
file's bundle set and throws "There is no bundle named X in the serialization context." otherwise
(VRage.Library/Keen.VRage.Library.Serialization.Migrations.Internal/MigrationsHelper.cs:126-147, reached from
JsonHelper.TryLocateType :531-535). Every vanilla file that names a Game2: type declares Game2.

Checked over every JSON asset of every block: the staged package and the installed mod, definitions, .model assets
and .meta files."""
import os

import pytest

from dc import config, integration
from dc.assetio import read_json

SUFFIXES = (".def", ".partialdef", ".model", ".meta")


def _files(root):
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(SUFFIXES):
                yield os.path.join(dp, f)


@pytest.fixture(scope="module")
def staged(stage_package):
    return stage_package()


@pytest.mark.parametrize("where", ["staged", "installed"])
def test_every_type_bundle_is_declared(staged, where):
    root = integration.STAGE if where == "staged" else os.path.join(config.MOD_ASSETS, config.NAME)
    bad, n = [], 0
    for p in _files(root):
        d = read_json(p)
        n += 1
        used = integration.type_bundles(d)
        missing = used - set(d.get("$Bundles") or {})
        if missing:
            bad.append((os.path.relpath(p, root), sorted(missing)))
    assert n > 500, n
    assert not bad, bad[:20]


def test_declare_bundles_adds_only_what_is_missing():
    d = {"$Bundles": {"System.Runtime": "1.0.0.0", "VRage": "2.3.0.467"},
         "$Type": "VRage:Keen.VRage.ContentPipeline.Definitions.PartialDefinitionDiff",
         "$Value": {"Manipulator": {"_entity": {"ObjectBuilders": {"Changed": [
             {"Value": {"$Type": "Game2:Keen.Game2.Simulation.WorldObjects.CubeBlocks.PowerableBlockObjectBuilder"}}]}}}}}
    integration.declare_bundles(d)
    assert d["$Bundles"] == {"Game2": "2.4.0.95", "System.Runtime": "1.0.0.0", "VRage": "2.3.0.467"}
    with pytest.raises(RuntimeError):
        integration.declare_bundles({"$Bundles": {}, "$Type": "DataCenter:DataCenter.Kvm.KvmDrawerPart"})
