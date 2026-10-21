import os
import shutil
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Source", "Model"))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "..", "tools")))
CORE_TESTS = os.path.join(HERE, "CoreTests")
SCRIPTS = os.path.join(HERE, "..", "Scripts")

# Every test module's `staged` fixture regenerates the package (integration.write_all: rmtree, then write). Into the
# shared Source/Model/integration/Assets, two concurrent pytest runs raced ("Directory not empty"), and a run could
# leave a half-written staging for install.sh. So each run stages into its own temp dir: dc.config.STAGE_ASSETS is
# redirected here, before dc.integration is imported (its STAGE is bound at import), and removed when the run ends.
# build_integration.py and install.sh keep using the shared staging (install.sh's default source is unchanged; the
# dry-run test points it at this run's staging through DC_STAGE_SRC).
from dc import config as _dc_config  # noqa: E402

RUN_STAGE_ROOT = tempfile.mkdtemp(prefix="dc-pytest-stage-")
_dc_config.STAGE_ASSETS = os.path.join(RUN_STAGE_ROOT, "Assets")


def pytest_configure(config):
    config.addinivalue_line("markers", "build: needs a prior Blender build (build_report.json); skipped if absent")
    config.addinivalue_line("markers", "sdkbuild: runs the real SDK content build (se2mod.py build); opt-in with DC_SDK_BUILD=1")
    config.addinivalue_line("markers", "path_a: pins Ruling DB-10 Path A (rack subparts as ConditionalSubParts); skipped "
                                       "when dc.config.RACK_PATH is 'B' (Tests/test_rack_path_b.py covers B)")
    config.addinivalue_line("markers", "scripts: needs the optional C# layer (Scripts/); skipped without it, the data-only package")


def pytest_unconfigure(config):
    shutil.rmtree(RUN_STAGE_ROOT, ignore_errors=True)


def pytest_collection_modifyitems(config, items):
    """Without Scripts/ the mod is its data-only self (Plan 4: scripts are optional): the script tests skip, and every
    data test still runs and must pass (Task 11 checks exactly that by moving Scripts/ aside). Under Ruling DB-10
    Path B (dc.config.RACK_PATH "B") the Path A pins skip."""
    if _dc_config.RACK_PATH != "A":
        skip_a = pytest.mark.skip(reason="Path A only: dc.config.RACK_PATH is " + repr(_dc_config.RACK_PATH))
        for item in items:
            if item.get_closest_marker("path_a"):
                item.add_marker(skip_a)
    if os.path.isdir(SCRIPTS):
        return
    skip = pytest.mark.skip(reason="Scripts/ absent: the data-only package (the C# layer is optional)")
    for item in items:
        if item.get_closest_marker("scripts"):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def trajectories():
    """The motion core's dump (Source/Model/preview/plan4/traj: the trajectories, routing.json, data_only_open.csv),
    which stays out of git. When its content stamp does not match the core sources on disk (absent, or made from other
    sources), Tests/CoreTests regenerates it, so the geometry checks always run on the motion the game runs, on a fresh
    clone too. Without dotnet an absent dump skips; a stale one is left for test_trajectories_fresh to fail."""
    from dc import kvm_motion as K

    if K.dump_stamp() == K.core_sources_digest():
        return K.TRAJ_DIR
    if shutil.which("dotnet"):
        r = subprocess.run(["dotnet", "run", "-c", "Release", "--project", CORE_TESTS, "--", "--dump", K.TRAJ_DIR],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
        if r.returncode != 0:
            pytest.fail("CoreTests --dump failed, so the trajectories cannot be regenerated:\n" + r.stdout[-4000:])
    elif not os.path.exists(os.path.join(K.TRAJ_DIR, "open.csv")):
        pytest.skip("no trajectories and no dotnet to dump them: cd Tests/CoreTests && dotnet run -c Release -- "
                    "--dump ../../Source/Model/preview/plan4/traj")
    return K.TRAJ_DIR
