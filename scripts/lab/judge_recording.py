"""Judge an edited recording against its original. Prints measured facts and writes a contact grid next to the video.
    python scripts/lab/judge_recording.py <edited.mp4> <original.mp4> [--srt edited.srt]
Checks: duration kept; black flashes the edit introduced (the original is the reference); loudness; how loud the music is next to the speech (levels in 0.5 s
windows: the loudest quarter = speech, the quietest tenth that is not silence = music alone); caption count and the longest gap without a caption; a 4 x 4 contact grid.
Runs ffmpeg on the computer it is started on (decode only: no GPU, no render)."""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

FF = next((p for p in (Path(r"C:\Users\Roy\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin"),) if p.exists()), None)
ffmpeg = str(FF / "ffmpeg.exe") if FF else "ffmpeg"
ffprobe = str(FF / "ffprobe.exe") if FF else "ffprobe"


def duration(p: Path) -> float:
    return float(subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True).stdout.strip())


def blacks(p: Path) -> list[tuple[float, float]]:
    out = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", str(p), "-vf", "blackdetect=d=0.1:pix_th=0.12", "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:[\d.]+ black_duration:([\d.]+)", out)]


def levels(p: Path, win: float = 0.5) -> np.ndarray:
    raw = subprocess.run([ffmpeg, "-v", "error", "-i", str(p), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.float32)
    n = int(16000 * win)
    w = a[: len(a) // n * n].reshape(-1, n)
    return 20 * np.log10(np.sqrt((w ** 2).mean(axis=1)) + 1e-9)


def lufs(p: Path) -> float:
    out = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", out)
    return float(m[-1]) if m else float("nan")


def grid(p: Path, out: Path, d: float) -> None:
    from PIL import Image

    tiles = []
    for i in range(16):
        f = out.with_name(f"_t{i}.png")
        subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", f"{d * (i + 0.5) / 16:.2f}", "-i", str(p), "-frames:v", "1", "-vf", "scale=480:-1", str(f)])
        tiles.append(Image.open(f).convert("RGB"))
    w, h = tiles[0].size
    g = Image.new("RGB", (w * 4, h * 4))
    for i, t in enumerate(tiles):
        g.paste(t, ((i % 4) * w, (i // 4) * h))
    g.save(out)
    for i in range(16):
        out.with_name(f"_t{i}.png").unlink(missing_ok=True)


def srt_times(p: Path) -> list[tuple[float, float]]:
    t = p.read_text(encoding="utf-8", errors="replace")
    f = lambda s: sum(float(x) * k for x, k in zip(re.split(r"[:,]", s), (3600, 60, 1, 0.001)))      # noqa: E731
    return [(f(a), f(b)) for a, b in re.findall(r"(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)", t)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("edited")
    ap.add_argument("original")
    ap.add_argument("--srt", default="")
    a = ap.parse_args()
    e, o = Path(a.edited), Path(a.original)
    de, do = duration(e), duration(o)
    print(f"duration: {de:.1f} s edited, {do:.1f} s original ({do - de:+.1f} s cut)")
    bo, be = blacks(o), blacks(e)
    new = [(s, d) for s, d in be if not any(abs(s - s2) < 1.0 for s2, _ in bo)]
    print(f"black flashes: original {len(bo)}, edited {len(be)}; INTRODUCED by the edit: {len(new)}", ("at " + ", ".join(f"{s:.1f}s" for s, _ in new)) if new else "")
    L = levels(e)
    speech = np.percentile(L, 75)
    quiet = L[(L < np.percentile(L, 12)) & (L > -70)]
    music = float(np.median(quiet)) if len(quiet) else float("nan")
    print(f"loudness: {lufs(e):.1f} LUFS; speech windows ~{speech:.1f} dB, music-alone windows ~{music:.1f} dB -> music sits {speech - music:.0f} dB under the speech "
          f"({'audible and low: good' if 12 <= speech - music <= 30 else 'check it: too loud' if speech - music < 12 else 'barely there or silent'})")
    srt = Path(a.srt) if a.srt else e.with_suffix(".srt")
    if srt.exists():
        ts = srt_times(srt)
        gaps = [b2 - a1 for (_, a1), (b2, _) in zip(ts, ts[1:])]
        print(f"captions: {len(ts)} cues, longest gap between cues {max(gaps) if gaps else 0:.1f} s")
    g = e.with_name(e.stem + ".grid.png")
    grid(e, g, de)
    print("contact grid:", g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
