import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def test_readme_tray_section():
    readme = _read("README.md")
    for word in ("Reducer", "Drop", "floor to floor", "0.5 m above"):
        assert word in readme, word


def test_testing_doc_covers_trays():
    text = _read(os.path.join("docs", "testing-in-game.md"))
    for word in ("Trays join floor to floor", "Hanger Rods", "tray cables"):
        assert word in text, word
