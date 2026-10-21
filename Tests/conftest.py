import contextlib
import hashlib
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
# The SDK build (se2mod build / se2modkit sdkbuild) moves Scripts/ here while the builder runs and back afterwards. A run
# collected in that window took the mod for the data-only package and silently skipped every `scripts` test (112 of
# them: the serial 115-skip run in docs/research/dev-speed-and-token-efficiency.md section 1.4), so it must not start.
SCRIPTS_HIDDEN = os.path.join(HERE, "..", ".Scripts.hidden-for-build")

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
    if not os.path.isdir(SCRIPTS) and os.path.isdir(SCRIPTS_HIDDEN):
        raise pytest.UsageError("Scripts/ is hidden by a running SDK build (.Scripts.hidden-for-build exists): run the "
                                "tests after the build, or every `scripts` test would silently skip. If no build is "
                                "running, a crashed one left it behind: move .Scripts.hidden-for-build back to Scripts/.")
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
    config._dc_data_only = True
    skip = pytest.mark.skip(reason="Scripts/ absent: the data-only package (the C# layer is optional)")
    for item in items:
        if item.get_closest_marker("scripts"):
            item.add_marker(skip)


def pytest_runtest_setup(item):
    """Scripts/ present at collection but gone now: an SDK build started mid-run and hid it. Fail the `scripts` tests
    rather than let them read a half-moved tree (or, in a later run, skip)."""
    if (item.get_closest_marker("scripts") and not getattr(item.config, "_dc_data_only", False)
            and not os.path.isdir(SCRIPTS)):
        pytest.fail("Scripts/ disappeared during the run (an SDK build hides it in .Scripts.hidden-for-build): rerun "
                    "the tests after the build", pytrace=False)


@contextlib.contextmanager
def _core_tests_lock():
    """Hold an exclusive lock on Tests/CoreTests while `dotnet run` builds it. Under pytest-xdist the trajectories
    fixture (in up to three workers) and test_scripts_layout::test_core_tests_pass can build the one project at the
    same time, and concurrent MSBuild runs on one obj/ fail at random. The lock file lives in the temp dir, keyed by
    the project path, so separate pytest runs on this checkout queue too. No fcntl (Windows): no lock."""
    try:
        import fcntl
    except ImportError:
        yield
        return
    key = hashlib.sha1(os.path.realpath(CORE_TESTS).encode()).hexdigest()[:12]
    with open(os.path.join(tempfile.gettempdir(), f"dc-coretests-{key}.lock"), "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


@pytest.fixture(scope="session")
def core_tests_lock():
    """The CoreTests build lock (_core_tests_lock), for tests that `dotnet run` Tests/CoreTests themselves."""
    return _core_tests_lock


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
        with _core_tests_lock():
            if K.dump_stamp() == K.core_sources_digest():   # another worker regenerated it while this one waited
                return K.TRAJ_DIR
            r = subprocess.run(["dotnet", "run", "-c", "Release", "--project", CORE_TESTS, "--", "--dump", K.TRAJ_DIR],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
        if r.returncode != 0:
            pytest.fail("CoreTests --dump failed, so the trajectories cannot be regenerated:\n" + r.stdout[-4000:])
    elif not os.path.exists(os.path.join(K.TRAJ_DIR, "open.csv")):
        pytest.skip("no trajectories and no dotnet to dump them: cd Tests/CoreTests && dotnet run -c Release -- "
                    "--dump ../../Source/Model/preview/plan4/traj")
    return K.TRAJ_DIR
