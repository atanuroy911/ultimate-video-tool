"""The server's routes, in matching order, as a golden file. FastAPI picks the first route that matches, so moving a handler to another module (W4.2 split
`server/vt/server/app.py`) must not change this list. Regenerate on purpose with VT_UPDATE_GOLDEN=1 and read the diff."""
import json
import os
from pathlib import Path

from vt.server.app import app

GOLDEN = Path(__file__).parent / "golden" / "route_table.json"


def table() -> list[list]:
    out = []
    for r in app.routes:
        out.append([getattr(r, "path", getattr(r, "name", "")), sorted(getattr(r, "methods", None) or []), getattr(r, "name", "")])
    return out


def test_the_route_table_is_unchanged():
    now = table()
    if os.environ.get("VT_UPDATE_GOLDEN"):
        GOLDEN.write_text(json.dumps(now, indent=0), encoding="utf-8")
    assert GOLDEN.exists(), "run once with VT_UPDATE_GOLDEN=1"
    old = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert now == old, f"the routes changed: {len(old)} before, {len(now)} now"


def test_no_route_is_registered_twice_by_accident():
    seen = {}
    for path, methods, name in table():
        for m in methods:
            seen.setdefault((path, m), []).append(name)
    twice = {k: v for k, v in seen.items() if len(v) > 1 and k[0] not in ("/mcp", "/mcp/director")}
    assert not twice, twice
