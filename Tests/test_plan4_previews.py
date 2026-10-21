"""Plan 4 Task 7: the scripted KVM motion previews exist and match their trajectories.

Rendered by `DC_PREVIEW=plan4 blender -b --python Source/Model/build_dc.py -- <blocks>` (dc/preview_scripts.py; the
block list is in its docstring). Everything under Source/Model/preview/plan4 is local render output, out of git (the
SVG charts and stills included), so every check of a preview file skips on a checkout that has not rendered it. The
parameter lists come from kvm_preview_plan.PLAN alone, so collection never reads the trajectory dump; the tests that
need the dump take the `trajectories` fixture, which regenerates it (or skips without dotnet).
Each MP4 must hold one frame per 1/60 s of its trajectory (dc/kvm_preview_plan.Run.frames), +-1.
"""
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

from dc import kvm_preview_plan as P

OUT = os.path.join(os.path.dirname(__file__), "..", "Source", "Model", "preview", "plan4")
BRIEF_RUNS = ("open", "close", "door_close_while_out", "reverse_mid_fold")
BRIEF_VIEWS = ("side", "3q", "first_person")

pytestmark = [pytest.mark.build, pytest.mark.scripts]
NOT_RENDERED = "local render output, not tracked: run DC_PREVIEW=plan4 (dc/preview_scripts.py) to produce it"


def _path(name):
    """The preview file's path; skips when it is absent (every file under preview/plan4 is local render output)."""
    path = os.path.join(OUT, name)
    if not os.path.exists(path):
        pytest.skip(f"{name}: {NOT_RENDERED}")
    return path


def _videos():
    """{file name: the run whose frames it holds} of every MP4 the plan renders (from PLAN alone: no file reads)."""
    out = {f"kvm_{name}_{view}.mp4": name
           for name, views in P.PLAN.items() if name != "dataonly_open" for view in views}
    out["kvm_dataonly_vs_scripted_3q.mp4"] = "open"
    return out


def _named():
    names = set(_videos())
    for name, views in P.PLAN.items():
        if "3q" in views and name != "dataonly_open":
            names |= {f"kvm_{name}_3q.gif", f"kvm_{name}_sheet.png"}
    names |= {f"kvm_scripted_{k}_3q.png" for k in ("f_gate", "f_lift", "f_bounce", "out")}
    names |= {"kvm_timing.svg", "kvm_motion_graphs.svg"}
    return sorted(names)


def test_plan_covers_the_brief(trajectories):
    for name in BRIEF_RUNS:
        assert set(BRIEF_VIEWS) <= set(P.PLAN[name]), name
    assert "top" in P.PLAN["door_close_while_out"]       # the race seen from above
    assert P.runs()["data_only_top"].slot == P.TOP          # P4-12's top slot, on its own path


@pytest.mark.parametrize("name", _named())
def test_preview_exists(name):
    path = _path(name)
    assert os.path.isfile(path) and os.path.getsize(path) > 0, name


@pytest.mark.skipif(not shutil.which("ffprobe"), reason="ffprobe not installed")
@pytest.mark.parametrize("name,run", sorted(_videos().items()))
def test_video_frame_count(name, run, trajectories):
    path = _path(name)
    frames = P.runs()[run].frames
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                        "stream=nb_read_frames,r_frame_rate,codec_name", "-of", "default=nw=1",
                        path], capture_output=True, text=True, check=True)
    info = dict(line.split("=", 1) for line in r.stdout.split())
    assert info["codec_name"] == "h264" and info["r_frame_rate"] == "60/1", info
    assert abs(int(info["nb_read_frames"]) - frames) <= 1, (name, info["nb_read_frames"], frames)


@pytest.mark.parametrize("name", ["kvm_timing.svg", "kvm_motion_graphs.svg"])
def test_charts_parse(name):
    root = ET.parse(_path(name)).getroot()
    assert root.tag.endswith("svg")
    assert len(list(root.iter("{http://www.w3.org/2000/svg}path"))) > 10


def test_run_interpolates_by_time():
    """Run.at brackets by sample time, so a non-uniform trajectory samples correctly; a non-increasing one is refused."""
    r = P.Run("x", [(0.0, 0.0, 0.0), (0.1, 1.0, 0.0), (0.5, 1.0, 1.0), (0.52, 0.0, 1.0)], "x")
    assert r.at(0.05) == pytest.approx((0.5, 0.0))
    assert r.at(0.3) == pytest.approx((1.0, 0.5))
    assert r.at(0.51) == pytest.approx((0.5, 1.0))
    assert r.at(-1.0) == (0.0, 0.0) and r.at(9.0) == (0.0, 1.0)
    with pytest.raises(ValueError):
        P.Run("bad", [(0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.1, 1.0, 0.0)], "bad")
