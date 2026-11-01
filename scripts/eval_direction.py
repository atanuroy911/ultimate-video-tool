"""Measure our videos the same way the example reels were measured, and print the numbers side by side (docs/ROADMAP.md P4-12, P4-01).

    python scripts/eval_direction.py                          # the reels, and every acceptance video that has its script
    python scripts/eval_direction.py --video out.mp4 --script my_script.txt
    python scripts/eval_direction.py --write                  # also docs/evidence/<date>/direction-baseline.md
    python scripts/eval_direction.py --seed                   # (re)write tests/direction_set/ from docs/research/reels

What is compared is rhythm, not meaning: how often the picture changes, how long the longest still is, when the first change comes, how many words and sentences each picture carries. The
reels' numbers come from `docs/research/reels/*.json` (made by scripts/analyze_reels.py); ours are measured by the same two functions of that script, on the finished video.

Not measured here (and so not claimed): whether each change lands on the right *word*. That needs the owner's marks of two reels (tests/direction_set/marks.template.json): until they are
filled in the "which word" test is pending, and `--marks` reports it as such.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
REELS = ROOT / "docs" / "research" / "reels"
SET = ROOT / "tests" / "direction_set"
SCRIPTS = ROOT / "tests" / "acceptance" / "scripts"
BUSY = 10                                                     # a reel with fewer picture changes than this is a talking head, not a model for a made video


def sentences(text: str) -> int:
    return max(1, len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]))


def words(text: str) -> int:
    return len(re.findall(r"[\w$%']+", text))


def gap(events: list[float]) -> float:
    """The middle time between one picture change and the next (seconds); 0 when there are fewer than two."""
    g = [b - a for a, b in zip(events, events[1:])]
    return statistics.median(g) if g else 0.0


def row(name: str, *, duration: float, swaps: int, median: float, longest: float, first: float | None, n_words: int, n_sent: int, source: str, events: list[float] | None = None) -> dict:
    return {"name": name, "source": source, "duration": round(duration, 1), "changes": swaps, "changes_per_min": round(swaps / duration * 60, 1) if duration else 0.0,
            "median_gap_s": round(gap(events or []), 2), "median_motion": round(median, 2), "longest_still_s": round(longest, 2), "first_change_s": None if first is None else round(first, 2),
            "words": n_words, "sentences": n_sent, "words_per_change": round(n_words / swaps, 1) if swaps else None, "changes_per_sentence": round(swaps / n_sent, 2) if n_sent else None}


def reference_rows() -> list[dict]:
    out = []
    for f in sorted(REELS.glob("reel*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if "change" not in d:
            continue
        ch, sp = d["change"], d.get("speech") or {}
        text = sp.get("text", "")
        ev = ch.get("swap_events") or []
        out.append(row(f.stem, duration=d["duration"], swaps=ch.get("swaps", len(ev)), median=ch.get("median_change", 0.0), longest=ch.get("longest_still_s", 0.0), first=ev[0] if ev else None,
                       n_words=sp.get("words") or words(text), n_sent=sentences(text) if text else 0, source="reel", events=ev))
    return out


def measure_video(video: Path, script: Path | None, name: str | None = None) -> dict:
    import analyze_reels as A

    info = A.probe(video)
    diff, fps = A.change_series(video)
    st = A.change_stats(diff, fps)
    text = script.read_text(encoding="utf-8") if script and script.exists() else ""
    ev = st.get("swap_events") or []
    return row(name or video.stem, duration=info["duration"], swaps=st.get("swaps", len(ev)), median=st.get("median_change", 0.0), longest=st.get("longest_still_s", 0.0), first=ev[0] if ev else None,
               n_words=words(text) if text else 0, n_sent=sentences(text) if text else 0, source="ours", events=ev)


def our_rows(videos: list[tuple[Path, Path | None]]) -> list[dict]:
    return [measure_video(v, s) for v, s in videos]


def default_videos() -> list[tuple[Path, Path | None]]:
    found = []
    for v in sorted((ROOT / "docs" / "evidence").glob("*/acceptance/A*.mp4")):
        s = next(iter(sorted(SCRIPTS.glob(f"{v.stem}-*.txt"))), None)
        found.append((v, s))
    return found


def med(rows: list[dict], key: str) -> float | None:
    vals = [r[key] for r in rows if r.get(key) is not None]
    return round(statistics.median(vals), 2) if vals else None


def table(rows: list[dict]) -> str:
    head = ["name", "length s", "changes", "per min", "median gap s", "longest still s", "first change s", "words/change", "changes/sentence"]
    keys = ["name", "duration", "changes", "changes_per_min", "median_gap_s", "longest_still_s", "first_change_s", "words_per_change", "changes_per_sentence"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        lines.append("| " + " | ".join("-" if r.get(k) is None else str(r[k]) for k in keys) + " |")
    return "\n".join(lines)


def compare(refs: list[dict], ours: list[dict]) -> list[str]:
    """One plain line per measure: where ours sit against the busy reels (the model for a made video)."""
    busy = [r for r in refs if r["changes"] >= BUSY]
    notes = []
    if not busy or not ours:
        return ["Nothing to compare yet."]
    for label, key, lower_is_better in (("how often the picture changes (per minute)", "changes_per_min", None), ("the longest a picture stays (s)", "longest_still_s", True),
                                       ("the middle time between changes (s)", "median_gap_s", None), ("when the first change comes (s)", "first_change_s", True),
                                       ("words under one picture", "words_per_change", None), ("changes for each sentence", "changes_per_sentence", None)):
        lo = min((r[key] for r in busy if r.get(key) is not None), default=None)
        hi = max((r[key] for r in busy if r.get(key) is not None), default=None)
        mine = med(ours, key)
        if lo is None or mine is None:
            notes.append(f"- {label}: not measured for ours")
            continue
        where = "inside" if lo <= mine <= hi else "below" if mine < lo else "above"
        notes.append(f"- {label}: ours {mine}, the busy reels {lo} to {hi} (median {med(busy, key)}): **{where} the range**")
    return notes


def marks_status() -> str:
    f = SET / "marks.json"
    if not f.exists():
        return "The 'which word' test is **pending**: the owner has not marked any reel yet (fill tests/direction_set/marks.template.json and save it as marks.json)."
    marks = json.loads(f.read_text(encoding="utf-8"))
    done = [m for m in marks if m.get("word")]
    return f"{len(done)} of {len(marks)} sentences are marked; the match with the director's change word is not computed yet (needs a plan for the same script)."


def seed() -> None:
    SET.mkdir(parents=True, exist_ok=True)
    refs = reference_rows()
    (SET / "reels.json").write_text(json.dumps(refs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    template = []
    for f in sorted(REELS.glob("reel*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        sp = d.get("speech") or {}
        if (d.get("change") or {}).get("swaps", 0) < BUSY or not sp.get("text"):
            continue
        for i, s in enumerate([x for x in re.split(r"(?<=[.!?])\s+", sp["text"]) if x.strip()], 1):
            template.append({"reel": f.stem, "sentence_no": i, "sentence": s, "word": "", "note": ""})
    (SET / "marks.template.json").write_text(json.dumps(template, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (SET / "README.md").write_text(
        "# The direction set\n\nStarted 2026-10-28 from the ten example reels (P4-12). Not the 20-recording set of P4-01 yet.\n\n"
        "* `reels.json`: the measured rhythm of each reel (changes, lengths, first change, words per change), made by `python scripts/eval_direction.py --seed`.\n"
        "* `marks.template.json`: every sentence of the busy reels with an empty `word`. **The owner marks the word each picture should change on** (two reels are enough to start), "
        "then saves the file as `marks.json`. That is the 'which word' test.\n* Still missing for P4-01: about 20 short recordings with an editor's cuts (audio and `marks.json` per recording).\n"
        "\nRun `python scripts/eval_direction.py` to see our numbers beside the reels'.\n", encoding="utf-8")
    print(f"wrote {SET}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", action="append", default=[], help="a finished video of ours (repeatable)")
    ap.add_argument("--script", action="append", default=[], help="its script, in the same order (for words and sentences)")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--seed", action="store_true")
    a = ap.parse_args()
    if a.seed:
        seed()
        return 0
    refs = reference_rows()
    if a.video:
        vids = [(Path(v), Path(a.script[i]) if i < len(a.script) else None) for i, v in enumerate(a.video)]
    else:
        vids = default_videos()
    ours = our_rows(vids)
    out = ["# Our rhythm against the example reels", "", f"Measured {date.today().isoformat()} by `scripts/eval_direction.py`. Rhythm only, not meaning.", "", "## The reels", "", table(refs), "",
           f"The *busy* reels (at least {BUSY} picture changes) are the model for a made video: " + ", ".join(r["name"] for r in refs if r["changes"] >= BUSY) + ".", "", "## Ours", "",
           table(ours) if ours else "No video of ours found: render one (scripts/run_acceptance.py) or pass --video.", "", "## Against the busy reels", "", *compare(refs, ours), "", "## Which word", "", marks_status(), ""]
    text = "\n".join(out)
    print(text)
    if a.write:
        dest = ROOT / "docs" / "evidence" / date.today().isoformat() / "direction-baseline.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
