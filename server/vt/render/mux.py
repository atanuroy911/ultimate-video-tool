"""Audio mix (voice + ducked music + SFX) and final mux with the rendered video."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from .. import paths
from ..util import find_tool, run

LEVEL_TIER = {"off": 0, "subtle": 1, "normal": 2, "rich": 3}
LEVEL_DB = {"subtle": -2.0, "normal": 0.0, "rich": -1.0}   # rich plays more sounds, so each is a touch quieter
# built-in synthesised fallback when no curated library has been built: role -> file in assets/sfx
FALLBACK = {"pop": "pop", "click": "click", "chime": "ding", "success": "ding", "money": "ding", "whoosh": "whoosh",
            "impact": "pop", "subdrop": "whoosh", "riser": "whoosh", "glitch": "click", "camera": "click"}


def sfx_level(options) -> str:
    """The effective density: the new `sfx_level`, with the old boolean `sfx` switching everything off."""
    return "off" if not getattr(options, "sfx", True) else getattr(options, "sfx_level", "normal")


def _read(path: Path, sr: int) -> Optional[np.ndarray]:
    try:
        x, s = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception:
        return None
    if s != sr:
        return None
    return np.repeat(x, 2, axis=1) if x.shape[1] == 1 else x[:, :2]


def build_sfx_track(cues: list[dict], duration: float, out: Path, level: str = "normal", seed: str = "vt") -> Optional[Path]:
    """Place sound effects at cue times into one stereo wav (None when nothing plays).

    Each cue names a *role*; the clip is picked from the curated library with a seeded RNG, never repeating the last few
    clips of that role, so a video sounds varied but identical renders stay identical.
    """
    import random

    from ..sfxlib import ROLES, Library

    tier = LEVEL_TIER.get(level, 2)
    if tier == 0 or not cues:
        return None
    lib = Library()
    rng = random.Random(seed)
    sr = 44100
    total = int((duration + 2.0) * sr)
    buf = np.zeros((total, 2), dtype=np.float32)
    recent: dict[str, list[str]] = {}
    cache: dict[str, Optional[np.ndarray]] = {}
    placed = 0
    for c in cues:
        if c.get("tier", 2) > tier:
            continue
        role = c.get("role") or c.get("kind", "pop")
        snd = None
        gain_db = ROLES.get(role, ROLES["misc"])["gain_db"] + LEVEL_DB.get(level, 0.0)
        clip = lib.pick(role, rng, avoid=set(recent.get(role, [])), short=(c.get("tier", 2) == 3 and role in ("pop", "click"))) if lib.available else None
        if clip is not None:
            if clip.id not in cache:
                cache[clip.id] = _read(lib.path(clip), sr)
            snd = cache[clip.id]
            recent.setdefault(role, []).append(clip.id)
            recent[role] = recent[role][-4:]
        if snd is None:                                    # no library (or unreadable clip): built-in synthesised sound
            f = paths.SFX / f"{FALLBACK.get(role, 'pop')}.wav"
            if f.exists():
                if f.name not in cache:
                    cache[f.name] = _read(f, sr)
                snd = cache[f.name]
                gain_db -= 1.0
        if snd is None or len(snd) == 0:
            continue
        i = int(max(0.0, c["t"]) * sr)
        if i >= total:
            continue
        seg = snd[: total - i]
        buf[i: i + len(seg)] += seg * (10 ** (gain_db / 20))
        placed += 1
    if not placed:
        return None
    np.clip(buf, -1.0, 1.0, out=buf)
    sf.write(str(out), buf, sr, subtype="PCM_16")
    return out


def resolve_music(music_id: Optional[str]) -> Optional[Path]:
    """A bundled track id from assets/music/index.json, a file in assets/music/user, or an absolute path."""
    if not music_id:
        return None
    p = Path(music_id)
    if p.is_absolute() and p.exists():
        return p
    for cand in (paths.MUSIC / f"{music_id}.mp3", paths.MUSIC / music_id, paths.USER_MUSIC / music_id.removeprefix("user/")):
        if cand.exists():
            return cand
    return None


TARGET_LUFS, TARGET_TP = -14.0, -1.5
H264_LEVEL = "4.2"                  # 1080p at up to 60 fps


def _measure(cmd: list[str], graph: list[str], duration: float, target_lufs: float = TARGET_LUFS) -> Optional[dict]:
    """First loudnorm pass over the same mix (audio inputs only)."""
    import json
    import re

    probe = [c for c in cmd]
    g = graph + ["[mx]loudnorm=I=%s:TP=%s:LRA=11:print_format=json[a]" % (target_lufs, TARGET_TP)]
    probe = [x for x in probe if x not in ("-loglevel", "error")]
    probe += ["-filter_complex", ";".join(g), "-map", "[a]", "-t", f"{duration:.3f}", "-f", "null", "-"]
    out = run(probe, check=False)
    mm = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", out or "", re.S)
    if not mm:
        return None
    try:
        d = json.loads(mm.group(0))
    except json.JSONDecodeError:
        return None
    return None if d.get("input_i") in ("-inf", "inf") else d


# one switch for a rough recording: rumble out, hiss and room noise down, a little presence, levels evened out. Applied to the voice only (music and sounds are left alone).
VOICE_CLEAN = ("highpass=f=90,afftdn=nr=25:nf=-40:tn=1,agate=threshold=0.02:ratio=2.5:attack=8:release=200:range=0.15,equalizer=f=3200:t=q:w=1.2:g=2.5,"
               "acompressor=threshold=-22dB:ratio=2.5:attack=8:release=160:makeup=2,alimiter=limit=0.9:level=disabled")      # measured on real speech with added hiss and hum: +13 dB between the words


def mix_and_mux(video: Path, voice: Path, out: Path, *, duration: float, music: Optional[Path] = None,
                music_volume: float = 0.10, sfx: Optional[Path] = None, short_side: Optional[int] = None,
                gpu: bool = True, layer_audio: Optional[list[dict]] = None, clean_voice: bool = False,
                duck: bool = True, duck_amount: float = 0.4, duck_release: float = 0.35,
                target_lufs: float = TARGET_LUFS, music_fade_in: float = 1.0, music_fade_out: float = 2.0) -> Path:
    """voice (+ looped music ducked under the voice) (+ sfx) -> AAC, muxed with the silent video."""
    from .. import gpu as gpu_choice
    gpu = gpu and gpu_choice.usable()                              # no card allowed: the processor encodes
    ff = find_tool("ffmpeg")
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(video), "-i", str(voice)]
    n = 2
    music_idx = sfx_idx = None
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        music_idx = n
        n += 1
    if sfx:
        cmd += ["-i", str(sfx)]
        sfx_idx = n
        n += 1

    layer_idx: list[int] = []
    for la in layer_audio or []:                          # the owner's audio layers: each its own input, placed in time below
        cmd += ["-i", la["path"]]
        layer_idx.append(n)
        n += 1

    f = [f"[1:a]{VOICE_CLEAN + ',' if clean_voice else ''}aresample=48000,aformat=channel_layouts=stereo[v0]"]
    mix_inputs = ["[v]"]
    if music_idx is not None:
        f.append("[v0]asplit=2[v][vkey]" if duck else "[v0]anull[v]")
        fade_out = max(0.0, duration - music_fade_out)
        f.append(f"[{music_idx}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{duration:.3f},asetpts=N/SR/TB,"
                 f"volume={music_volume},afade=t=in:d={max(music_fade_in, 0.01):.2f},afade=t=out:st={fade_out:.3f}:d={max(music_fade_out, 0.01):.2f}[m0]")
        if duck:                                           # amount 0..1 -> ratio 1.5..20: higher = the music sinks further under the voice
            ratio = 1.5 + 18.5 * max(0.0, min(1.0, duck_amount))
            f.append(f"[m0][vkey]sidechaincompress=threshold=0.03:ratio={ratio:.2f}:attack=20:release={int(max(0.05, min(2.0, duck_release)) * 1000)}:makeup=1[m]")
        else:
            f.append("[m0]anull[m]")
        mix_inputs.append("[m]")
    else:
        f.append("[v0]anull[v]")
    if sfx_idx is not None:
        f.append(f"[{sfx_idx}:a]aresample=48000,aformat=channel_layouts=stereo[s]")
        mix_inputs.append("[s]")
    for k, (i, la) in enumerate(zip(layer_idx, layer_audio or [])):
        fi, fo, d = min(la["fade_in"], la["dur"] / 2), min(la["fade_out"], la["dur"] / 2), la["dur"]
        chain = f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=start={la['in']:.3f}:duration={d:.3f},asetpts=PTS-STARTPTS,volume={la['volume']}"
        if fi > 0.01:
            chain += f",afade=t=in:d={fi:.3f}"
        if fo > 0.01:
            chain += f",afade=t=out:st={max(0.0, d - fo):.3f}:d={fo:.3f}"
        ms = int(round(la["start"] * 1000))
        f.append(f"{chain},adelay={ms}|{ms}[l{k}]")
        mix_inputs.append(f"[l{k}]")
    f.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:normalize=0,alimiter=limit=0.95:level=disabled[mx]")
    # social platforms play everything at about -14 LUFS and clip above -1 dBTP: measure the finished mix, then set it there exactly (linear, no pumping)
    m = _measure(cmd, f, duration, target_lufs)
    if m:
        f.append(f"[mx]loudnorm=I={target_lufs}:TP={TARGET_TP}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
                 f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=48000[a]")
    else:
        f.append(f"[mx]loudnorm=I={target_lufs}:TP={TARGET_TP}:LRA=11,aresample=48000[a]")

    if short_side:  # downscale (e.g. 1080p -> 720p): the video must be re-encoded
        vf = f"scale='if(gt(iw,ih),-2,{short_side})':'if(gt(iw,ih),{short_side},-2)':flags=lanczos"
        encoders = (["-c:v", "h264_nvenc", *gpu_choice.nvenc_device(), "-preset", "p5", "-cq", "21", "-pix_fmt", "yuv420p"] if gpu
                    else ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p"])
        vcodec = ["-vf", vf, *encoders, "-profile:v", "high", "-level:v", H264_LEVEL]
    else:
        # the renderer may label a 1080x1920 stream as level 3.1 (a 720p level); some platforms and phones reject that, so the header is corrected
        vcodec = ["-c:v", "copy", "-bsf:v", f"h264_metadata=level={H264_LEVEL}"]
    cmd += ["-filter_complex", ";".join(f), "-map", "0:v:0", "-map", "[a]", "-t", f"{duration:.3f}",
            *vcodec, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    try:
        run(cmd)
    except RuntimeError:
        if not (short_side and gpu):
            raise
        return mix_and_mux(video, voice, out, duration=duration, music=music, music_volume=music_volume,
                           sfx=sfx, short_side=short_side, gpu=False, layer_audio=layer_audio, clean_voice=clean_voice,
                           duck=duck, duck_amount=duck_amount, duck_release=duck_release,
                           target_lufs=target_lufs, music_fade_in=music_fade_in, music_fade_out=music_fade_out)
    return out
