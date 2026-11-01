"""A control character in a source file is always a mistake: a regex written `\b` that became a backspace never matches, silently.
(Found 2026-10-26 in renderer/runtime/vt-stick.js, where it stopped the cartoon mouths from being found, and in vt/script/score.py.)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = ("node_modules", ".venv", "third_party", "dist", "__pycache__", "projects", "models", "desktop", "tests/golden", "qa_")
ALLOWED = {9, 10, 13}                      # tab, newline, carriage return


def test_no_source_file_contains_a_control_character():
    bad = []
    for sub, exts in (("vt", {".py"}), ("renderer/runtime", {".js", ".css"}), ("studio/src", {".ts", ".tsx", ".css"}), ("tests", {".py"}), ("scripts", {".py", ".ps1"}), ("studio/e2e", {".mjs"}), ("docs", {".md", ".MD"})):
        for p in (ROOT / sub).rglob("*"):
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            if not p.is_file() or p.suffix not in exts or any(s in rel for s in SKIP):
                continue
            ctrl = sorted(set(p.read_bytes()) - ALLOWED)
            ctrl = [c for c in ctrl if c < 32]
            if ctrl:
                bad.append((rel, ctrl))
    assert not bad, f"control characters (8 is a backspace where a regex meant \b): {bad}"
