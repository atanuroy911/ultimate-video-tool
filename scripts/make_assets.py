"""Synthesises the bundled SFX and music loops with numpy (original work, released as CC0 with this project).
They are deliberately simple beds meant to sit under a voice at low volume.
Usage: python scripts/make_assets.py   (needs ffmpeg with libmp3lame)"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
MUSIC = ROOT / "assets" / "music"
SFX = ROOT / "assets" / "sfx"
SR = 44100
RNG = np.random.default_rng(11)


def t_axis(sec: float) -> np.ndarray:
    return np.arange(int(sec * SR)) / SR


def env_exp(n: int, decay: float, attack: float = 0.004) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / decay)


def lowpass_fast(x: np.ndarray, cutoff: float) -> np.ndarray:
    """Zero-phase-ish smoothing through FFT; fast for long pads."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1.0 / (1.0 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def norm(x: np.ndarray, peak: float = 0.8) -> np.ndarray:
    m = np.max(np.abs(x)) + 1e-9
    return x * (peak / m)


def save_wav(path: Path, x: np.ndarray) -> None:
    sf.write(str(path), x.astype(np.float32), SR, subtype="PCM_16")


# ----------------------------------------------------------------------------- SFX


def sfx_pop() -> np.ndarray:
    n = int(0.14 * SR)
    t = np.arange(n) / SR
    f = 720 * np.exp(-t * 14) + 260
    ph = 2 * np.pi * np.cumsum(f) / SR
    return norm(np.sin(ph) * env_exp(n, 0.035, 0.002), 0.7)


def sfx_whoosh() -> np.ndarray:
    n = int(0.42 * SR)
    noise = RNG.normal(0, 1, n)
    t = np.arange(n) / SR
    # sweep a band by modulating a simple resonant filter through mixing low/high passes
    lo = lowpass_fast(noise, 900)
    hi = noise - lowpass_fast(noise, 2500)
    sweep = np.sin(np.pi * np.clip(t / 0.42, 0, 1)) ** 2
    y = (lo * (1 - t / 0.42) + hi * (t / 0.42) * 0.6) * sweep
    return norm(y, 0.6)


def sfx_click() -> np.ndarray:
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * 1800 * t) * env_exp(n, 0.008, 0.0005)
    return norm(y, 0.5)


def sfx_ding() -> np.ndarray:
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * 1320 * t) * 0.6 + np.sin(2 * np.pi * 1980 * t) * 0.3 + np.sin(2 * np.pi * 2640 * t) * 0.12
    return norm(y * env_exp(n, 0.25, 0.002), 0.6)


# ----------------------------------------------------------------------------- music


def midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def add(buf: np.ndarray, start: int, snd: np.ndarray) -> None:
    """Add snd at start, wrapping the tail around the loop end so the loop is seamless."""
    L = len(buf)
    idx = (start + np.arange(len(snd))) % L
    np.add.at(buf, idx, snd)


def tone(freq: float, dur: float, decay: float, kind: str = "sine", attack: float = 0.005) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == "sine":
        w = np.sin(2 * np.pi * freq * t)
    elif kind == "saw":
        w = 2 * ((freq * t) % 1.0) - 1
    elif kind == "tri":
        w = 2 * np.abs(2 * ((freq * t) % 1.0) - 1) - 1
    else:
        w = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(4 * np.pi * freq * t)
    return w * env_exp(n, decay, attack)


def kick() -> np.ndarray:
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    f = 50 + 110 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.09, 0.001)


def hat(open_: bool = False) -> np.ndarray:
    n = int((0.16 if open_ else 0.05) * SR)
    nz = RNG.normal(0, 1, n)
    nz = nz - lowpass_fast(nz, 6000)
    return nz * env_exp(n, 0.07 if open_ else 0.015, 0.0005) * 0.5


def snare() -> np.ndarray:
    n = int(0.18 * SR)
    nz = RNG.normal(0, 1, n)
    nz = lowpass_fast(nz, 5000) - lowpass_fast(nz, 300)
    return (nz * env_exp(n, 0.07, 0.001) + 0.5 * tone(190, 0.18, 0.05)) * 0.8


def make_track(spec: dict) -> np.ndarray:
    bpm, bars = spec["bpm"], spec["bars"]
    beat = 60.0 / bpm
    bar = beat * 4
    L = int(bar * bars * SR)
    buf = np.zeros(L)
    prog = spec["chords"]  # list of (root_midi, intervals)
    for b in range(bars):
        root, iv = prog[b % len(prog)]
        t0 = int(b * bar * SR)
        notes = [root + i for i in iv]
        if spec.get("pad"):
            for nt in notes:
                for det in (-0.07, 0.07):
                    s = tone(midi(nt + 12 + det), bar * 1.15, 3.0, "saw", attack=0.25)
                    add(buf, t0, s * spec["pad"] * 0.22)
        if spec.get("bass"):
            for k in range(spec.get("bass_hits", 2)):
                at = t0 + int(k * bar / spec.get("bass_hits", 2) * SR)
                add(buf, at, tone(midi(root - 12), bar / spec.get("bass_hits", 2), 0.5) * spec["bass"] * 0.7)
        if spec.get("arp"):
            steps = spec.get("arp_steps", 8)
            pattern = spec.get("arp_pattern", [0, 1, 2, 1, 0, 2, 1, 2])
            for k in range(steps):
                nt = notes[pattern[k % len(pattern)] % len(notes)] + 12 + spec.get("arp_oct", 12)
                at = t0 + int(k * bar / steps * SR)
                add(buf, at, tone(midi(nt), 0.5, 0.16, spec.get("arp_kind", "tri")) * spec["arp"] * 0.5)
        if spec.get("drums"):
            style = spec["drums"]
            for k in range(4):
                at = t0 + int(k * beat * SR)
                if style in ("four", "lofi"):
                    if style == "four" or k in (0, 2):
                        add(buf, at, kick() * 0.9)
                if k in (1, 3) and style in ("lofi", "four"):
                    add(buf, at, snare() * (0.45 if style == "lofi" else 0.3))
                for h in range(2):
                    add(buf, at + int(h * beat / 2 * SR), hat(open_=(h == 1 and style == "four")) * (0.35 if style == "four" else 0.25))
            if style == "pulse":
                for k in range(8):
                    add(buf, t0 + int(k * beat / 2 * SR), tone(midi(root - 24), 0.3, 0.1) * 0.7)
    if spec.get("noise"):
        nz = RNG.normal(0, 1, L)
        nz = lowpass_fast(nz, 3000) * spec["noise"] * 0.02
        buf += nz
    if spec.get("lp"):
        buf = lowpass_fast(buf, spec["lp"])
    buf = norm(buf, 0.85)
    # gentle stereo: slight delay on one channel
    d = int(0.012 * SR)
    left = buf
    right = np.roll(buf, d)
    return np.stack([left, right], axis=1)


MAJ, MIN, MAJ7, MIN7, SUS = [0, 4, 7], [0, 3, 7], [0, 4, 7, 11], [0, 3, 7, 10], [0, 5, 7]
TRACKS = [
    {"id": "calm-01", "title": "Soft Morning", "mood": "calm", "bpm": 72, "bars": 16, "pad": 1.0, "bass": 0.5, "bass_hits": 1,
     "arp": 0.35, "arp_steps": 4, "arp_pattern": [0, 2, 1, 2], "chords": [(60, MAJ7), (57, MIN7), (53, MAJ7), (55, SUS)], "lp": 3500},
    {"id": "upbeat-01", "title": "Quick Start", "mood": "upbeat", "bpm": 112, "bars": 16, "pad": 0.5, "bass": 0.8, "bass_hits": 4,
     "arp": 0.8, "arp_steps": 8, "arp_kind": "tri", "drums": "four", "chords": [(60, MAJ), (67, MAJ), (57, MIN), (65, MAJ)], "lp": 7000},
    {"id": "lofi-01", "title": "Late Notes", "mood": "lofi", "bpm": 80, "bars": 16, "pad": 0.7, "bass": 0.7, "bass_hits": 2,
     "arp": 0.4, "arp_steps": 8, "arp_kind": "sine", "drums": "lofi", "noise": 1.0, "chords": [(62, MIN7), (55, MAJ7), (60, MAJ7), (57, MIN7)], "lp": 3000},
    {"id": "corporate-01", "title": "Clear Plan", "mood": "corporate", "bpm": 100, "bars": 16, "pad": 0.6, "bass": 0.6, "bass_hits": 2,
     "arp": 0.7, "arp_steps": 8, "arp_kind": "sine", "arp_pattern": [0, 1, 2, 1], "chords": [(65, MAJ), (60, MAJ), (62, MIN), (67, SUS)], "lp": 5500},
    {"id": "tense-01", "title": "Open Question", "mood": "tense", "bpm": 90, "bars": 16, "pad": 0.9, "bass": 0.5, "bass_hits": 1,
     "drums": "pulse", "chords": [(57, MIN), (56, [0, 3, 6]), (53, MAJ), (52, [0, 3, 7])], "lp": 2800},
]


def to_mp3(wav: Path, mp3: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "128k", str(mp3)], check=True)
    wav.unlink()


def main() -> None:
    SFX.mkdir(parents=True, exist_ok=True)
    MUSIC.mkdir(parents=True, exist_ok=True)
    for name, fn in {"pop": sfx_pop, "whoosh": sfx_whoosh, "click": sfx_click, "ding": sfx_ding}.items():
        save_wav(SFX / f"{name}.wav", fn())
        print("sfx", name)
    index = []
    for spec in TRACKS:
        x = make_track(spec)
        w = MUSIC / f"{spec['id']}.wav"
        sf.write(str(w), x.astype(np.float32), SR, subtype="PCM_16")
        to_mp3(w, MUSIC / f"{spec['id']}.mp3")
        index.append({"id": spec["id"], "title": spec["title"], "mood": spec["mood"], "bpm": spec["bpm"],
                      "seconds": round(len(x) / SR, 1), "loop": True, "file": f"{spec['id']}.mp3",
                      "license": "CC0 1.0 (synthesised for this project)"})
        print("music", spec["id"], round(len(x) / SR, 1), "s")
    (MUSIC / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "assets" / "LICENSES.md").write_text(
        "# Bundled audio\n\nAll files in `assets/sfx` and `assets/music` are synthesised by `scripts/make_assets.py` "
        "(numpy, no samples) and released under CC0 1.0. They are simple loops intended as quiet beds under speech.\n"
        "Add your own tracks to `assets/music/user/` (not distributed).\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
