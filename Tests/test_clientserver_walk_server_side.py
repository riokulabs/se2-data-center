"""Plan 5 Task 12a, (b) must FAIL, continued: the per-rack server-side mistakes Path A could make, each a full walk of
the staged package with one definition changed. Split out of test_clientserver_walk.py (same fixtures, helpers and
input gate, imported from it) only so that a parallel run (pytest-xdist --dist loadfile) can run the two halves on two
workers: together they were the longest module of the suite.
"""
import pytest

import clientserver_walk as csw
from test_clientserver_walk import (  # noqa: F401  (pytest fixtures, used by name)
    DOOR_RACKS, FAN_DOOR_RACKS, OB_HIERARCHY, OPEN_RACKS, SUBPART_COMPOSITE_TEMPLATE, T_COMPOSITE, T_PARTIAL, T_PREFAB,
    _gate_inputs, as_def, errors_of, own, package, package_walk, res, run, types)


@pytest.fixture(scope="module", autouse=True)
def _resolved_package(package_walk):  # noqa: F811 (fixture)
    """Walk the package once first, as test_clientserver_walk.py does before these tests: the walk fills the package's
    resolution cache, which every derive() below reuses for the definitions it does not replace (~1.3 s per walk)."""
    return package_walk


@pytest.mark.path_a
@pytest.mark.parametrize("rack,server", [(r, f) for r in FAN_DOOR_RACKS for f in
                                          ("LeftDoor_Server.def", "RackFanTray_Server.def", "RackSide_Server.def")]
                         + [("DC_Rack42_Open", f) for f in ("RackFanTray_Server.def", "RackSide_Server.def")])
def test_bound_entry_whose_server_prefab_has_a_child_fails(package, types, rack, server):  # noqa: F811 (fixtures)
    """A BOUND ConditionalSubParts entry is blocked on the server side only at its client prefab: its server prefab is
    walked as server through the binding, so a child there (the rotor) is a server composite. On the door leaves and
    on Task 12's real RackFanTray / RackSide server prefabs (door and open racks)."""
    sp = res(package, own(package, rack, server))
    fan = res(package, own(package, rack, "RackFan.partialdef"))
    for ob in sp["_entity"]["ObjectBuilders"]:
        if (ob.get("Value") or {}).get("$Type") == OB_HIERARCHY:
            ob["Value"]["Children"] = [dict(fan["_entity"], DebugName="Rotor")]
    w, errs = run(package.derive(as_def(T_PREFAB, sp)), types)
    assert errors_of(errs, "client-type-on-server", csw.composition_of(fan)), csw.format_errors(errs)


@pytest.mark.path_a
@pytest.mark.parametrize("rack,comp", [(r, f) for r in DOOR_RACKS for f in
                                        ("LeftDoor_ServerComposition.def", "RackSide_ServerComposition.def")]
                         + [(r, "RackFanTray_ServerComposition.def") for r in FAN_DOOR_RACKS + ("DC_Rack42_Open",)]
                         + [(r, "RackSide_ServerComposition.def") for r in OPEN_RACKS])
def test_server_composition_inheriting_a_client_type_fails(package, types, rack, comp):  # noqa: F811 (fixtures)
    """A bound entry's server composition that INHERITS render components from its Copy base (the subpart template)
    instead of inserting them: the resolver applies the base chain, so the inherited client types are seen. On the
    door leaves and on Task 12's real RackSide / RackFanTray server compositions."""
    sc = own(package, rack, comp)
    delta = as_def(T_PARTIAL, {"BaseDefinition": SUBPART_COMPOSITE_TEMPLATE, "PartialDefinitionKind": "Copy",
                              "Manipulator": {"Guid": sc}, "DefinitionType": T_COMPOSITE, "PriorityOverride": False})
    w, errs = run(package.derive(delta), types)
    assert errors_of(errs, "client-type-on-server", sc), csw.format_errors(errs)
