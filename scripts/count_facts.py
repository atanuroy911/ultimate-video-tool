"""The numbers the docs quote, measured from the code. Run it and compare with what docs/STATUS.md says.

    python scripts/count_facts.py            # prints a table and writes docs/evidence/facts.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))


def safe(fn):
    try:
        return fn()
    except Exception as e:  # a fact that cannot be measured is reported, not hidden
        return f"cannot measure: {type(e).__name__}: {str(e)[:80]}"


def js_registry_count(path: Path, name: str) -> int | str:
    """Count entries registered in a renderer registry such as `T["name"] = ...` or `R.name =` (a rough, honest count)."""
    src = path.read_text(encoding="utf-8")
    return len(set(re.findall(rf"\b{name}\[\s*[\"']([\w-]+)[\"']\s*\]\s*=", src))) + len(set(re.findall(rf"\b{name}\.(\w[\w-]*)\s*=\s*\(?(?:function|\()", src)))


def measure() -> dict[str, object]:
    facts: dict[str, object] = {}

    def f_elements():
        from vt.planner.catalogue import component_catalogue
        cat = component_catalogue()
        return len(cat["elements"]) if isinstance(cat, dict) and "elements" in cat else len(cat)
    facts["element types the planner may use"] = safe(f_elements)
    facts["scene archetypes (rule director)"] = safe(lambda: len(__import__("vt.director.archetypes", fromlist=["x"]).ARCHETYPES))
    facts["icons (lucide + tabler)"] = safe(lambda: len(__import__("vt.visuals.icons", fromlist=["x"]).all_names()))
    facts["emoji stickers indexed"] = safe(lambda: len(__import__("vt.visuals.emoji", fromlist=["x"]).index()))

    def f_script_cat():
        from vt.script import catalogue as C
        return {"stick verbs": len(C.VERBS) if hasattr(C, "VERBS") else "n/a", "places (sets)": len(getattr(C, "SETS", [])) or len(getattr(C, "SET_NAMES", [])),
                "roles": len(C.ROLES), "accessories": len(C.ACCESSORIES), "hairs": len(C.HAIRS), "toon characters": len(C.TOON_CHARACTERS), "toon scenes": len(C.TOON_SCENES)}
    facts["Video Script vocabulary"] = safe(f_script_cat)
    facts["animals recognised (distinct emoji)"] = safe(lambda: len(set(__import__("vt.script.animals", fromlist=["x"]).ANIMALS.values())))
    facts["shotcraft cards mapped"] = safe(lambda: len(__import__("vt.compose.motion", fromlist=["x"]).CARDS))
    motion = (ROOT / "server/renderer/runtime/vt-motion.js").read_text(encoding="utf-8")
    reg = {name: len(set(re.findall(rf'^\s*{name}\["([\w-]+)"\]\s*=', motion, re.M))) for name in ("T", "R", "S")}
    facts["motion recipes in vt-motion.js"] = {"text entrances (T)": reg["T"], "transitions (R)": reg["R"], "scene moves (S)": reg["S"], "total": sum(reg.values())}
    themes = [p.name for p in (ROOT / "server/design/themes").iterdir() if p.is_dir()]
    facts["themes (design/themes)"] = {"built in": sorted(n for n in themes if not n.startswith("auto-")), "auto-generated for projects": len([n for n in themes if n.startswith("auto-")])}
    facts["use-case profiles"] = len(list((ROOT / "server/design/profiles").glob("*.json")))
    facts["music tracks (assets/music)"] = len([p for p in (ROOT / "server/assets/music").glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg")])
    facts["sfx files (assets/sfx)"] = len([p for p in (ROOT / "server/assets/sfx").rglob("*") if p.is_file() and p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg")])
    facts["cartoon characters / scenes (assets/cartoon)"] = (len(list((ROOT / "server/assets/cartoon/characters").glob("*.svg"))), len(list((ROOT / "server/assets/cartoon/scenes").glob("*.*"))))
    facts["ComfyUI workflow assets"] = [p.name for p in sorted((ROOT / "server/assets/comfy/workflows").glob("*.json"))]
    facts["MCP tools / prompts"] = (len(re.findall(r"@tool\s*\n\s*def ", (ROOT / "server/vt/mcp/server.py").read_text(encoding="utf-8"))), len(re.findall(r"@server\.prompt", (ROOT / "server/vt/mcp/server.py").read_text(encoding="utf-8"))))

    def f_routes():
        from vt.server.app import app
        def walk(items):
            for r in items:
                if hasattr(r, "methods") and hasattr(r, "path"):
                    yield r
                elif hasattr(r, "original_router"):
                    yield from walk(r.original_router.routes)
        routes = [r for r in walk(app.routes) if r.path.startswith("/api")]
        return {"api routes": len(routes), "methods": sum(len(r.methods - {"HEAD", "OPTIONS"}) for r in routes)}
    facts["REST API"] = safe(f_routes)

    def f_models():
        from vt import models
        return len(models.MODELS) if hasattr(models, "MODELS") else "n/a"
    facts["downloadable models (vt/models.py)"] = safe(f_models)
    src = list((ROOT / "server/vt").rglob("*.py"))
    facts["python source"] = {"files": len([p for p in src if "__pycache__" not in p.parts]), "lines": sum(len(p.read_text(encoding="utf-8", errors="replace").splitlines()) for p in src if "__pycache__" not in p.parts)}
    facts["renderer runtime (js+css) lines"] = sum(len(p.read_text(encoding="utf-8", errors="replace").splitlines()) for p in (ROOT / "server/renderer/runtime").glob("*") if p.is_file())
    tsx = [p for p in (ROOT / "client/studio/src").rglob("*") if p.suffix in (".ts", ".tsx")]
    facts["studio source"] = {"files": len(tsx), "lines": sum(len(p.read_text(encoding="utf-8", errors="replace").splitlines()) for p in tsx), "pages": [p.stem for p in sorted((ROOT / "client/studio/src/pages").glob("*.tsx"))]}
    facts["browser suites (studio/e2e, not helpers)"] = len([p for p in (ROOT / "client/studio/e2e").glob("*.mjs") if not p.name.startswith("_") and p.name != "common.mjs"])
    facts["pytest files"] = len(list((ROOT / "tests").glob("test_*.py")))
    facts["pytest functions"] = sum(len(re.findall(r"^\s*(?:async )?def test_", p.read_text(encoding="utf-8", errors="replace"), re.M)) for p in (ROOT / "tests").glob("test_*.py"))

    return facts


def fmt(v: object) -> str:
    if isinstance(v, dict):
        return ", ".join(f"{k}: {fmt(x)}" for k, x in v.items())
    if isinstance(v, (list, tuple)):
        return ", ".join(fmt(x) for x in v)
    return str(v)


def to_markdown(facts: dict[str, object]) -> str:
    """The table docs/STATUS.md embeds between its facts markers; scripts/check_docs.py fails when the two differ."""
    rows = ["| What | Measured from the code |", "|---|---|"] + [f"| {k} | {fmt(v)} |" for k, v in facts.items() if k not in ("pytest functions",)]
    return "\n".join(rows)


def main() -> None:
    facts = measure()
    out = ROOT / "docs" / "evidence" / "facts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(facts, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(to_markdown(facts))


if __name__ == "__main__":
    main()
