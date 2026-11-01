"""Reads every shot recipe card of the vendored video-shotcraft library and writes third_party/video-shotcraft/index.json (name, category, one-line description, when to use, duration, energy,
reference implementation folder). The cards are written in Chinese; this index is the English-neutral handle the port work and the planner catalogue refer to."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "third_party" / "video-shotcraft"


def card(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8")
    fm = {}
    m = re.match(r"---\n(.*?)\n---", txt, re.S)
    for ln in (m.group(1).splitlines() if m else []):
        if ":" in ln:
            k, v = ln.split(":", 1)
            fm[k.strip()] = v.strip()
    demo = re.search(r"demos/[\w\-/]+/", txt)
    secs = re.findall(r"^## (.+)$", txt, re.M)
    return {"name": fm.get("name") or path.stem, "category": path.parent.name, "summary_zh": fm.get("一句话", ""), "use_zh": fm.get("适用", ""), "duration_zh": fm.get("时长", ""),
            "energy_zh": fm.get("能量", ""), "demo": demo.group(0) if demo else "", "sections": secs, "card": str(path.relative_to(BASE)).replace("\\", "/")}


def main() -> None:
    cards = [card(p) for p in sorted((BASE / "references" / "shots").glob("*/*.md"))]
    (BASE / "index.json").write_text(json.dumps({"source": "video-shotcraft 43bd349", "count": len(cards), "cards": cards}, ensure_ascii=False, indent=1), encoding="utf-8")
    cats: dict[str, int] = {}
    for c in cards:
        cats[c["category"]] = cats.get(c["category"], 0) + 1
    print(len(cards), "cards", cats)


if __name__ == "__main__":
    main()
