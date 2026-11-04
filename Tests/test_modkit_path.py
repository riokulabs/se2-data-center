"""Scripts run straight in Blender find se2modkit: installed, from SE2MODKIT_SRC, or the workspace checkout."""
import ast
import sys
from pathlib import Path

import pytest

import modkit_path

MODEL = Path(__file__).resolve().parents[1] / "Source" / "Model"


def test_installed_modkit_is_used_as_is(monkeypatch):
    monkeypatch.setattr(modkit_path, "_importable", lambda: True)
    before = list(sys.path)
    assert modkit_path.ensure() == "installed"
    assert sys.path == before


def test_env_then_workspace_checkout(monkeypatch, tmp_path):
    monkeypatch.setattr(modkit_path, "_importable", lambda: False)
    src = tmp_path / "src" / "se2modkit"
    src.mkdir(parents=True)
    monkeypatch.setenv("SE2MODKIT_SRC", str(tmp_path / "src"))
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert modkit_path.ensure() == str(tmp_path / "src")
    assert sys.path[0] == str(tmp_path / "src")
    monkeypatch.delenv("SE2MODKIT_SRC")
    ws = tmp_path / "ws"
    (ws / "tools" / "se2-modkit" / "src" / "se2modkit").mkdir(parents=True)
    repo = ws / "mods" / "DataCenter"
    assert modkit_path.ensure(repo=repo) == str(ws / "tools" / "se2-modkit" / "src")


def test_missing_modkit_says_how_to_run(monkeypatch, tmp_path):
    monkeypatch.setattr(modkit_path, "_importable", lambda: False)
    monkeypatch.delenv("SE2MODKIT_SRC", raising=False)
    with pytest.raises(SystemExit) as e:
        modkit_path.ensure(repo=tmp_path / "mods" / "DataCenter")
    assert "se2mod blender run" in str(e.value)


def test_blender_entry_scripts_use_it_and_not_the_old_copy():
    for script in ("build_dc.py", "build_integration.py", "check_placement.py", "fracture_compare_preview.py",
                   "fracture_preview.py", "rack_placement_sheet.py", "room_sheet.py", "states_preview.py"):
        text = (MODEL / script).read_text(encoding="utf-8")
        assert "import modkit_path" in text, script
        assert "se2model import" not in text and '"tools"))' not in text, script
        tree = ast.parse(text)
        def loads_modkit(n):   # se2modkit itself, or the dc package, whose modules import it
            names = [n.module or ""] if isinstance(n, ast.ImportFrom) else [a.name for a in n.names]
            return any(x.split(".")[0] in ("se2modkit", "dc") for x in names)
        first = next((i for i, n in enumerate(tree.body)
                      if isinstance(n, (ast.Import, ast.ImportFrom)) and loads_modkit(n)), len(tree.body))
        ensure = next(i for i, n in enumerate(tree.body) if "modkit_path" in ast.unparse(n))
        assert ensure < first, script
