"""Looks at the videos qa_generate.py produced (qa_out/*.mp4) and checks what a viewer would notice: is the music really in the mix, do picture and sound end together,
is the first frame empty, are there black or frozen stretches, do the modes look different from each other, are the files standard (H.264 High, yuv420p, AAC 48 kHz, faststart).

    python scripts/qa_analyze.py qa_out
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vt.util import find_tool  # noqa: E402

FF, FP = find_tool("ffmpeg"), find_tool("ffprobe")


def pcm(path: Path) -> np.ndarray:
    r = subprocess.run([FF, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def stream_durations(path: Path) -> tuple[float, float]:
    j = json.loads(subprocess.run([FP, "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", str(path)], capture_output=True, text=True).stdout)
    d = {s["codec_type"]: float(s.get("duration") or 0) for s in j["streams"]}
    return d.get("video", 0), d.get("audio", 0)


def filt(path: Path, vf: str) -> str:
    return subprocess.run([FF, "-hide_banner", "-nostats", "-i", str(path), "-vf", vf, "-an", "-f", "null", "-"], capture_output=True, text=True).stderr


def faststart(path: Path) -> bool:
    head = path.read_bytes()[:200000]
    return head.find(b"moov") != -1 and (head.find(b"mdat") == -1 or head.find(b"moov") < head.find(b"mdat"))


def frame_hash(path: Path, t: float) -> str:
    r = subprocess.run([FF, "-v", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1", "-vf", "scale=64:-2,format=gray", "-f", "rawvideo", "-"], capture_output=True)
    return hashlib.md5(r.stdout).hexdigest()[:10] + f"/{int(np.frombuffer(r.stdout, dtype=np.uint8).std() if r.stdout else 0)}"


def main(d: Path) -> int:
    rows = json.loads((d / "report.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    by = {(r["mode"], r["aspect"], r["music"] != "none"): r for r in rows}
    print(f"{'mode':9} {'asp':5} {'music':5} {'dur':>6} {'v-a':>6} {'MB':>5} {'LUFS':>6} {'peak':>6} {'musicΔdB':>9} {'black':>5} {'freeze':>6} faststart std-format")
    for r in rows:
        f = Path(r["file"])
        vd, ad = stream_durations(f)
        black = len(re.findall(r"black_start", filt(f, "blackdetect=d=0.4:pix_th=0.05")))
        freeze = len(re.findall(r"freeze_start", filt(f, "freezedetect=n=-60dB:d=4")))
        pj = json.loads(subprocess.run([FP, "-v", "error", "-show_entries", "stream=codec_type,codec_name,pix_fmt,sample_rate", "-of", "json", str(f)], capture_output=True, text=True).stdout)["streams"]
        v = next(x for x in pj if x["codec_type"] == "video")
        a = next((x for x in pj if x["codec_type"] == "audio"), {})
        std = v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p" and a.get("codec_name") == "aac" and int(a.get("sample_rate", 0)) == 48000
        fs = faststart(f)
        mdb = ""
        if r["music"] != "none":
            other = by.get((r["mode"], r["aspect"], False))
            if other:
                a, b = pcm(f), pcm(Path(other["file"]))
                n = min(len(a), len(b))
                diff = a[:n] - b[:n]
                rms = lambda x: float(np.sqrt(np.mean(x ** 2)))              # noqa: E731
                mdb = f"{20 * np.log10(max(1e-6, rms(diff)) / max(1e-6, rms(b[:n]))):.1f}"
                if float(np.sqrt(np.mean(diff ** 2))) < 0.003:
                    problems.append(f"{f.name}: the music is not audible in the mix")
        first = frame_hash(f, 0.1)
        print(f"{r['mode']:9} {r['aspect']:5} {str(r['music'] != 'none'):5} {r['duration']:6.2f} {vd - ad:6.2f} {r['mb']:5.1f} {r.get('lufs', 0):6.1f} {r.get('peak_db', 0):6.1f} {mdb:>9} {black:5d} {freeze:6d} {fs!s:9} {std}")
        if abs(vd - ad) > 0.25:
            problems.append(f"{f.name}: picture and sound end {vd - ad:+.2f} s apart")
        if black:
            problems.append(f"{f.name}: {black} black stretch(es)")
        if freeze:
            problems.append(f"{f.name}: {freeze} frozen stretch(es) longer than 4 s")
        if not std:
            problems.append(f"{f.name}: not H.264/yuv420p/AAC 48 kHz")
        if not fs:
            problems.append(f"{f.name}: moov atom is not at the front (no fast start)")
        if first.endswith("/0") or first.endswith("/1"):
            problems.append(f"{f.name}: the first frame looks empty ({first})")
        if r["music"] != "none" and not (-17 <= r.get("lufs", -99) <= -11):
            problems.append(f"{f.name}: loudness {r.get('lufs')} LUFS is outside -14 +/- 3")
        if r.get("peak_db", -99) > -0.9:
            problems.append(f"{f.name}: true peak {r.get('peak_db')} dBTP is too hot")
    # the modes must not return the same picture
    sigs = {}
    for r in rows:
        if r["music"] == "none":
            continue
        f = Path(r["file"])
        sigs[(r["mode"], r["aspect"])] = [frame_hash(f, r["duration"] * q) for q in (0.2, 0.5, 0.8)]
    modes = sorted(sigs)
    for i, a in enumerate(modes):
        for b in modes[i + 1:]:
            if a[1] == b[1] and sigs[a] == sigs[b]:
                problems.append(f"{a[0]} and {b[0]} ({a[1]}) produced identical frames")
    print("\nframe signatures (hash/contrast) at 20/50/80 %:")
    for k in modes:
        print(" ", k, sigs[k])
    print("\nPROBLEMS:" if problems else "\nno problems found")
    for p in problems:
        print("  -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "qa_out")))
