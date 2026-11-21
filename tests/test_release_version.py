"""The automatic release number (scripts/next_version.py): it counts on from this major version only, never back to an old one."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("next_version", Path(__file__).resolve().parents[1] / "scripts" / "next_version.py")
nv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nv)


@pytest.mark.parametrize("files,tags,expected", [
    ("0.5.0", ["v1.0.0"], "0.5.0"),                       # the old 1.0.0 tag is another major: ignored
    ("0.5.0", ["v0.5.0", "v1.0.0"], "0.5.1"),
    ("0.5.0", ["v0.5.3"], "0.5.4"),
    ("0.6.0", ["v0.5.3"], "0.6.0"),                       # a hand-made step in the files is respected
    ("0.5.0", [], "0.5.0"),
    ("0.5.0", ["v0.5.1-rc1", "v0.5.0"], "0.5.1"),          # pre-release tags do not count
    ("0.5.9", ["v0.5.9"], "0.5.10"),                      # numbers compare as numbers, not as text
    ("1.2.0", ["v1.2.4", "v0.9.9"], "1.2.5"),
])
def test_next_version(files, tags, expected):
    assert nv.next_version(files, tags) == expected


def test_not_a_version():
    with pytest.raises(ValueError):
        nv.parse("release-5")
