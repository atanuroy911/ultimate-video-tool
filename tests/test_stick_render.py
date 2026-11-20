"""The stick-figure engine drawn by the real renderer: the Phase 13 vocabulary (emoji actors, looks, props handed over, marks, night and rain, hiding) must be visible, move, stay centred and
inside the picture. Runs scripts/qa_stick.py (headless Chrome), so it is slow; the contact sheets in qa_out_stick/ are for a person to look at."""
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.browser]
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("aspect", ["16:9", "9:16"])
def test_the_new_stick_patterns_render_and_move(aspect, tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "qa_stick.py"), "--aspects", aspect, "--out", str(tmp_path), "--only", "fable_fox,wallet_story,night_rain,haggle,hide_seek,island"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    out = r.stdout + r.stderr
    assert r.returncode == 0 and "no problems found" in out, out[-1500:]
    assert (tmp_path / f"all-{aspect.replace(':', 'x')}.png").exists()
