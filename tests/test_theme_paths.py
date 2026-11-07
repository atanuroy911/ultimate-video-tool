"""All theme entry points share the same traversal and junction boundary."""
from pathlib import Path

import pytest

from vt.project import load_theme


@pytest.mark.parametrize("name", ["../outside", "..\\outside", "/outside", "C:\\outside", "C:outside", ".", "..", "", "bad\x00name"])
def test_theme_names_cannot_name_files_outside_the_library(name):
    with pytest.raises(ValueError, match="theme"):
        load_theme(name)


def test_theme_junction_cannot_resolve_outside_the_library(monkeypatch, tmp_path):
    from vt import paths

    monkeypatch.setattr(paths, "THEMES", tmp_path / "themes")
    target = paths.THEMES / "linked" / "theme.json"
    original = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda file, *a, **k: tmp_path / "outside.json" if file == target else original(file, *a, **k))
    with pytest.raises(ValueError, match="inside"):
        load_theme("linked")


def test_builtin_themes_still_load():
    from vt.project import list_themes

    themes = list_themes()
    assert themes and load_theme(themes[0].name) == themes[0]
