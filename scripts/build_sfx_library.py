"""Indexes a raw sound-effects folder into a curated, role-based library.

    python scripts/build_sfx_library.py [--src SFX] [--per-role 28]

Writes (under assets/sfx/):
  lib/<role>/*.ogg   trimmed, faded, peak-normalised clips (only the best per role; the originals stay where they are)
  library.json      the index used at mix time (vt/sfxlib.py)
  CATALOG.md        EVERY source file with its role, measurements and whether it was selected, and why not if not
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from vt.sfxlib import AUTO_ROLES, DISABLED_ROLES, ROLES, classify, flag  # noqa: E402

AUDIO_EXT = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".opus"}
SR = 44100


def decode(path: Path, seconds: float, mono: bool = True, sr: int = 22050) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-t", str(seconds), "-ac", "1" if mono else "2", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, timeout=60).stdout
    x = np.frombuffer(raw, dtype=np.float32)
    x = np.array(x)                                         # frombuffer is read-only; callers edit in place
    return x if mono else x.reshape(-1, 2)


def db(x: float) -> float:
    return 20 * np.log10(max(float(x), 1e-9))


def analyse(path: Path) -> dict:
    """Duration, peak, active loudness, onset, tail, clipping, spectral centroid."""
    try:
        x = decode(path, 60)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:80]}
    if len(x) < 400:
        return {"error": "empty"}
    sr = 22050
    peak = float(np.max(np.abs(x)))
    hop = 220
    n = len(x) // hop
    frames = x[: n * hop].reshape(n, hop)
    rms = np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1) + 1e-12)
    rdb = 20 * np.log10(rms)
    active = rdb > (db(peak) - 40)
    if not active.any():
        return {"error": "silent"}
    first = int(np.argmax(active))
    last = n - 1 - int(np.argmax(active[::-1]))
    seg = x[first * hop: (last + 1) * hop]
    win = np.hanning(1024)
    cents = []
    if len(seg) < 1024:                                   # clips shorter than one analysis window
        seg = np.pad(seg, (0, 1024 - len(seg)))
    for i in range(0, max(1, len(seg) - 1023), 1024):
        spec = np.abs(np.fft.rfft(seg[i: i + 1024] * win))
        if spec.sum() > 1e-6:
            cents.append(float((spec * np.arange(len(spec))).sum() / spec.sum() * sr / 1024))
    return {
        "duration": round(len(x) / sr, 3), "active": round((last - first + 1) * hop / sr, 3), "onset": round(first * hop / sr, 3),
        "peak_db": round(db(peak), 1), "rms_db": round(float(np.mean(rdb[first:last + 1])), 1),
        "clipped": round(float((np.abs(x) > 0.999).mean()), 4), "centroid": round(float(np.median(cents)) if cents else 0.0),
        "long": len(x) / sr >= 59.9,
    }


def score(role: str, a: dict) -> float:
    lo, ideal, hard = ROLES[role]["target"]
    d = a["active"]
    if d > hard or d < lo:
        return -1.0
    s = 1.0 - max(0.0, d - ideal) / max(hard - ideal, 1e-6) * 0.6          # prefer up to the ideal length
    s += 0.3 if a["rms_db"] > -34 else -0.3                               # audible
    s -= 5 * a["clipped"]
    return s


def export(src: Path, dst: Path, role: str, a: dict) -> float:
    spec = ROLES[role]
    hard = spec["target"][2]
    x = decode(src, hard + a["onset"] + 0.5, mono=spec["mono"], sr=SR)
    x = x[:, None] if x.ndim == 1 else x
    start = max(0, int((a["onset"] - 0.008) * SR))
    x = x[start: start + int(hard * SR)]
    env = np.abs(x).max(axis=1)
    keep = np.where(env > 10 ** (-55 / 20) * max(env.max(), 1e-6))[0]
    if len(keep):
        x = x[: keep[-1] + 1]
    fade = min(len(x) // 2, int(0.03 * SR))
    if fade > 1:
        x[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    x = x / max(float(np.abs(x).max()), 1e-6) * 10 ** (-1 / 20)             # peak -1 dBFS; role gain is applied at mix time
    dst.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dst), x[:, 0] if x.shape[1] == 1 else x, SR, format="OGG", subtype="VORBIS")
    return len(x) / SR


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48] or "clip"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "SFX"))
    ap.add_argument("--out", default=str(ROOT / "server" / "assets" / "sfx"))
    ap.add_argument("--per-role", type=int, default=32)
    args = ap.parse_args()
    src, out = Path(args.src), Path(args.out)
    files = sorted(p for p in src.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXT and p.stat().st_size > 1500)
    print(f"{len(files)} audio files under {src}")
    rows = []
    for p in files:
        rel = p.relative_to(src).as_posix()
        role, why = classify(rel)
        rows.append({"rel": rel, "path": p, "role": role, "why": why})
    with ThreadPoolExecutor(max_workers=8) as ex:
        for r, a in zip(rows, ex.map(lambda r: analyse(r["path"]), rows)):
            r["a"] = a
    print("analysed; curating...")

    by_role: dict[str, list[dict]] = {}
    for r in rows:
        a = r["a"]
        r["flag"] = flag(r["rel"])
        if "error" in a:
            r["status"] = f"unreadable ({a['error']})"
        elif r["flag"]:
            r["status"] = f"EXCLUDED: {r['flag']}"
        elif r["role"] in DISABLED_ROLES:
            r["status"] = "disabled role (weapon)"
        elif r["role"] not in AUTO_ROLES and r["role"] != "funny":
            r["status"] = "not used automatically"
        elif a.get("long"):
            r["status"] = "too long"
        else:
            r["score"] = score(r["role"], a)
            if r["score"] < 0:
                lo, _, hard = ROLES[r["role"]]["target"]
                r["status"] = f"length {a['active']}s outside {lo}-{hard}s"
            elif a["clipped"] > 0.01:
                r["status"] = "clipped"
            else:
                by_role.setdefault(r["role"], []).append(r)
                r["status"] = "candidate"

    clips = []
    for role, cand in sorted(by_role.items()):
        cand.sort(key=lambda r: -r["score"])
        pool = cand[: max(args.per_role * 3, args.per_role)]
        pool.sort(key=lambda r: r["a"]["centroid"])                 # spread picks across the spectrum for variety
        step = max(1, len(pool) / args.per_role)
        chosen = [pool[int(i * step)] for i in range(min(args.per_role, len(pool)))]
        for r in cand:
            r["status"] = "not selected (cap)"
        for i, r in enumerate(chosen, 1):
            cid = f"{role}-{i:02d}-{slug(Path(r['rel']).stem)}"
            fname = f"{role}/{cid}.ogg"
            dur = export(r["path"], out / "lib" / fname, role, r["a"])
            r["status"] = f"SELECTED as {cid}"
            clips.append({"id": cid, "role": role, "file": fname, "duration": round(dur, 3), "peak_db": -1.0,
                          "centroid": r["a"]["centroid"], "source": r["rel"], "tags": [r["why"]]})
        print(f"  {role:9s} {len(cand):3d} candidates -> {len(chosen)} selected")

    (out / "library.json").write_text(json.dumps({"version": 1, "roles": {k: v["doc"] for k, v in ROLES.items()}, "clips": clips},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")

    # human-readable catalogue of EVERY file
    lines = ["# Sound-effects catalogue", "", f"{len(rows)} source files indexed from `{src.name}/`. "
             f"{len(clips)} curated clips are used by the app (`lib/`). Everything else stays where it is.", "",
             "Roles: " + ", ".join(f"**{k}** ({v['doc']})" for k, v in ROLES.items()), ""]
    summary: dict[str, list[int]] = {}
    for r in rows:
        s = summary.setdefault(r["role"], [0, 0])
        s[0] += 1
        s[1] += r["status"].startswith("SELECTED")
    lines += ["| role | files | selected |", "|---|---:|---:|"] + [f"| {k} | {v[0]} | {v[1]} |" for k, v in sorted(summary.items())] + [""]
    for role in sorted(summary):
        lines += [f"## {role}", f"*{ROLES[role]['doc']}*", "", "| file | s | peak dB | centroid Hz | status | why this role |", "|---|---:|---:|---:|---|---|"]
        for r in sorted((x for x in rows if x["role"] == role), key=lambda x: x["rel"].lower()):
            a = r["a"]
            lines.append(f"| `{r['rel']}` | {a.get('duration', '')} | {a.get('peak_db', '')} | {a.get('centroid', '')} | {r['status']} | {r['why']} |")
        lines.append("")
    (out / "CATALOG.md").write_text("\n".join(lines), encoding="utf-8")
    size = sum(f.stat().st_size for f in (out / "lib").rglob("*.ogg")) / 1e6
    print(f"wrote {len(clips)} clips ({size:.1f} MB), library.json, CATALOG.md")


if __name__ == "__main__":
    main()
