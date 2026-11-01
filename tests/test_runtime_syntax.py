"""Every renderer script parses (a syntax error in one file blanks every video: 2026-10-24, a comment swallowed a statement in vt.js)."""
import shutil
import subprocess

import pytest

from vt import paths


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize("name", sorted(p.name for p in paths.RUNTIME.glob("*.js") if not p.name.endswith(".min.js")))
def test_runtime_script_parses(name):
    r = subprocess.run(["node", "--check", str(paths.RUNTIME / name)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-400:]
