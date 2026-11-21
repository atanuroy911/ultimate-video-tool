"""What the person pointed at (W13.2), written into an assistant's message the same way everywhere: the Claude Code tab (client/desktop/acp-instructions.js,
toPrompt) and the Director chat (this file). Both must produce byte-identical text; tests/fixtures/refs.json holds the shared cases."""
from __future__ import annotations

import math
from typing import Any

KINDS = ("scene", "time", "range", "element", "word", "region", "layer")


def _num(x: Any) -> str:
    """A number as JavaScript prints it in a template string (9 not 9.0)."""
    f = float(x)
    return str(int(f)) if f.is_integer() else repr(f)


def _clock(t: Any) -> str:
    from decimal import ROUND_HALF_UP, Decimal

    s = max(0.0, float(t or 0))
    tenth = Decimal(s % 60).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)        # as JavaScript's toFixed(1): half up on the exact value
    return f"{math.floor(s / 60)}:{str(tenth).rjust(4, '0')}"


def _span(r: dict) -> str:
    return f" · {_clock(r['from'])}–{_clock(r['to'])}" if r.get("from") is not None and r.get("to") is not None else ""


def _line(r: dict, i: int) -> str:
    k = r.get("kind")
    if k == "scene":
        where = f"scene {r.get('scene')}{_span(r)} · vt://scene/{r.get('scene')}"
    elif k == "time":
        where = f"time {_clock(r.get('t'))} · vt://t/{_num(r.get('t'))}"
    elif k == "range":
        where = f"time {_clock(r.get('from'))}–{_clock(r.get('to'))} · vt://range/{_num(r.get('from'))}/{_num(r.get('to'))}"
    elif k == "element":
        idx = r.get("index")
        where = f"element {r.get('scene')}#{'' if idx is None else idx}{_span(r)} · vt://element/{r.get('scene')}/{0 if idx is None else idx}"
    elif k == "word":
        where = f"word {r.get('word')}"
    elif k == "layer":
        where = f"layer {r.get('layer')}"
    else:
        where = f"a region of scene {r.get('scene')}"
    label = r.get("label")
    return f"[{i + 1}] {where}" + (f' · "{label}"' if label else "")


def clean(refs: Any) -> list[dict]:
    """Keep only well-formed references (at most 8), with short strings and finite numbers."""
    out: list[dict] = []
    for r in (refs or [])[:8]:
        if not isinstance(r, dict) or r.get("kind") not in KINDS:
            continue
        c: dict = {"kind": r["kind"]}
        for key in ("scene", "element", "layer", "word"):
            if r.get(key) is not None:
                c[key] = str(r[key])[:64]
        for key in ("t", "from", "to", "index"):
            v = r.get(key)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
                c[key] = v
        if r.get("label") is not None:
            c["label"] = str(r["label"])[:200]
        out.append(c)
    return out


def with_refs(text: str, refs: Any) -> str:
    refs = clean(refs)
    if not refs:
        return text
    return f"{text}\n\n<video_references>\n" + "\n".join(_line(r, i) for i, r in enumerate(refs)) + "\n</video_references>"
