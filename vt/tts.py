"""Text -> speech for the "I only have a script" workflow.

The script is split into sentences, each is spoken by the chosen engine, and the sentences are joined with natural pauses.
Because we know the exact text, the transcript comes straight from the script (no speech recognition): word times are spread
over each sentence's real speech by letter count and nudged to the nearest dip in loudness. Everything downstream (cuts,
captions, scene planning, music, rendering) is unchanged.

Engines
  edge  Microsoft's neural voices through the keyless `edge-tts` library. Best Bangla quality, needs internet.
  mms   Meta MMS-TTS Bengali (VITS) through `transformers`. Works offline once downloaded (~140 MB). Licence CC-BY-NC 4.0:
        fine for personal and non-commercial videos only.
"""
from __future__ import annotations

import asyncio
import os
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import soundfile as sf

from . import voice_direction as VD
from . import voice_lock as VL
from . import paths
from .util import CREATE_NO_WINDOW, ProgressFn, find_tool, noop_progress

SR = 24000
SENTENCE_GAP = 0.32
PARAGRAPH_GAP = 0.65
MAX_CHARS = 5000
VOICE_SEED = 1                     # one seed for every sentence: the same take of the same voice, every time
RATE_SWING = 0.05                  # a delivery note may change one sentence's speed by this much, no more: bigger jumps sound like another reader
STEADY_DELIVERY = "the same natural, steady narration as the rest of the script"   # a plain sentence in a directed script

ENGINES: list[dict] = [
    {"id": "edge", "label": "Natural voices (online)", "offline": False, "licence": "Microsoft Edge online voices, free, no key",
     "voices": [
         {"id": "bn-BD-NabanitaNeural", "label": "Nabanita (Bangla, female)", "lang": "bn"},
         {"id": "bn-BD-PradeepNeural", "label": "Pradeep (Bangla, male)", "lang": "bn"},
         {"id": "bn-IN-TanishaaNeural", "label": "Tanishaa (Bangla India, female)", "lang": "bn"},
         {"id": "bn-IN-BashkarNeural", "label": "Bashkar (Bangla India, male)", "lang": "bn"},
         {"id": "en-US-AriaNeural", "label": "Aria (English, female)", "lang": "en"},
         {"id": "en-US-GuyNeural", "label": "Guy (English, male)", "lang": "en"},
         {"id": "en-GB-SoniaNeural", "label": "Sonia (British English, female)", "lang": "en"},
         {"id": "en-IN-NeerjaNeural", "label": "Neerja (Indian English, female)", "lang": "en"},
         {"id": "hi-IN-SwaraNeural", "label": "Swara (Hindi, female)", "lang": "hi"},
     ]},
    {"id": "kokoro", "label": "Offline voices (Kokoro, English and Hindi)", "offline": True, "licence": "Apache 2.0 (model weights: Apache 2.0), free for any use",
     "voices": [
         {"id": "af_heart", "label": "Heart (English, female)", "lang": "en"}, {"id": "af_bella", "label": "Bella (English, female)", "lang": "en"},
         {"id": "af_nicole", "label": "Nicole (English, female, calm)", "lang": "en"}, {"id": "am_michael", "label": "Michael (English, male)", "lang": "en"},
         {"id": "am_adam", "label": "Adam (English, male, deep)", "lang": "en"}, {"id": "bf_emma", "label": "Emma (British English, female)", "lang": "en"},
         {"id": "bm_george", "label": "George (British English, male)", "lang": "en"},
         {"id": "hf_alpha", "label": "Alpha (Hindi, female)", "lang": "hi"}, {"id": "hm_omega", "label": "Omega (Hindi, male)", "lang": "hi"},
     ]},
    {"id": "clone", "label": "My own voice (cloned, English)", "offline": True, "licence": "Chatterbox (MIT). Only voices you added with the speaker's consent",
     "voices": []},
    {"id": "voicestudio", "label": "My voice server (VoiceStudio)", "offline": False, "licence": "VoiceStudio runs on your own server; each voice model has its own licence, shown in Settings, Engines",
     "voices": []},
    {"id": "vtengine", "label": "Another Video Tool computer", "offline": False, "licence": "The voices of that computer, each with its own licence", "voices": []},
    {"id": "comfyvoice", "label": "Voices on my ComfyUI server (Breeze TTS 2, OmniVoice)", "offline": False,
     "licence": "Each voice model has its own licence (Breeze TTS 2: research and non-commercial). The server is yours.", "voices": []},
    {"id": "mms", "label": "Offline voice (Meta MMS)", "offline": True, "licence": "CC-BY-NC 4.0, non-commercial use only",
     "voices": [{"id": "ben", "label": "Bangla (one voice)", "lang": "bn"}]},
]


class TTSError(RuntimeError):
    pass


# --------------------------------------------------------------------------- text
_SPLIT = re.compile(r"(?<=[।?!॥])\s+|(?<=\.)(?<!\d\.)\s+(?=\S)|\n+")
_TAKA = re.compile(r"৳\s*([০-৯0-9][০-৯0-9,\.]*)")


def clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def speakable(text: str) -> str:
    """What the voice should say: '৳১০০' becomes '১০০ টাকা', stray symbols are dropped."""
    t = _TAKA.sub(lambda m: f"{m.group(1)} টাকা", text)
    t = t.replace("%", " শতাংশ " if re.search(r"[ঀ-৿]", t) else " percent ").replace("&", " and ")
    t = re.sub(r"[*_#`~^|<>\[\]{}]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


_LABEL = re.compile(r"^\s*([^\W\d_][\w\u0980-\u09FF .'\-]{0,19}?)\s*[:：]\s+(\S.*)$")


def parse_dialogue(text: str) -> Optional[list[tuple[str, str]]]:
    """'Riya: hello' lines -> [(speaker, text)] when at least two different names speak; otherwise None (plain script)."""
    blocks: list[tuple[str, str]] = []
    for line in clean(text).split("\n"):
        if not line.strip():
            continue
        m = _LABEL.match(line)
        if m and not re.match(r"https?", m.group(2)):
            blocks.append((m.group(1).strip(), m.group(2).strip()))
        elif blocks:
            blocks[-1] = (blocks[-1][0], blocks[-1][1] + " " + line.strip())      # a continuation line belongs to the same speaker
        else:
            return None
    names = {b[0] for b in blocks}
    return blocks if len(names) >= 2 and len(blocks) >= 2 else None


def split_script(text: str) -> list[dict]:
    """[{"text", "para_end", "speaker"}] sentences in order; a blank line marks a paragraph end (longer pause). Dialogue keeps who speaks."""
    dlg = parse_dialogue(text)
    if dlg:
        out: list[dict] = []
        for who, said in dlg:
            for s in split_script(said):
                out.append({**s, "speaker": who, "para_end": False})
            out[-1]["para_end"] = True
        return out
    out = []
    for para in re.split(r"\n\s*\n", clean(text)):
        parts = [p.strip() for p in _SPLIT.split(para) if p and p.strip()]
        for i, p in enumerate(parts):
            if len(p) > 220:                                        # very long sentence: break at commas so the voice breathes
                chunks = re.split(r"(?<=[,;،])\s+", p)
                buf = ""
                for c in chunks:
                    if buf and len(buf) + len(c) > 200:
                        out.append({"text": buf.strip(), "para_end": False, "speaker": None})
                        buf = ""
                    buf += c + " "
                p = buf.strip()
            if p:
                out.append({"text": p, "para_end": False, "speaker": None})
        if out:
            out[-1]["para_end"] = True
    return out


# --------------------------------------------------------------------------- engines
def _ffmpeg_to_wav(src: Path, dst: Path) -> None:
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", str(SR), str(dst)], capture_output=True, text=True)
    if r.returncode != 0:
        raise TTSError("ffmpeg could not convert the synthesized audio: " + r.stderr[-300:])


def _rate_pct(rate: float) -> str:
    return f"{round((rate - 1.0) * 100):+d}%"


def _synth_edge(text: str, voice: str, rate: float, out_wav: Path) -> None:
    try:
        import edge_tts
    except ImportError as e:
        raise TTSError("The online voices need the 'edge-tts' package (pip install edge-tts).") from e

    async def run(mp3: Path) -> None:
        comm = edge_tts.Communicate(text, voice, rate=_rate_pct(rate))
        await comm.save(str(mp3))

    last: Optional[Exception] = None
    with tempfile.TemporaryDirectory() as d:
        mp3 = Path(d) / "s.mp3"
        for attempt in range(3):
            try:
                asyncio.run(run(mp3))
                if mp3.exists() and mp3.stat().st_size > 800:
                    _ffmpeg_to_wav(mp3, out_wav)
                    return
                last = TTSError("the service returned no audio")
            except Exception as e:                                   # network, throttling...
                last = e
        raise TTSError(f"The online voice could not be reached ({type(last).__name__}). Check the internet connection, or choose the offline voice.") from last


_mms = {}


def _synth_mms(text: str, voice: str, rate: float, out_wav: Path) -> None:
    try:
        import torch
        from transformers import AutoTokenizer, VitsModel
    except ImportError as e:
        raise TTSError("The offline voice needs transformers and torch (installed with the speech extra).") from e
    import os

    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    if "m" not in _mms:
        name = f"facebook/mms-tts-{voice}"
        try:
            _mms["tok"] = AutoTokenizer.from_pretrained(name)
            _mms["m"] = VitsModel.from_pretrained(name).eval()
        except Exception as e:
            raise TTSError("The offline voice has to be downloaded once (about 140 MB). Connect to the internet and try again.") from e
    model, tok = _mms["m"], _mms["tok"]
    model.speaking_rate = float(rate)
    inputs = tok(text, return_tensors="pt")
    if inputs["input_ids"].shape[1] == 0:
        raise TTSError("nothing speakable in: " + text[:40])
    with torch.no_grad():
        wav = model(**inputs).waveform[0].cpu().numpy().astype("float32")
    sr = int(model.config.sampling_rate)
    if sr != SR:
        import math
        from scipy.signal import resample_poly

        g = math.gcd(sr, SR)
        wav = resample_poly(wav, SR // g, sr // g).astype("float32")
    sf.write(str(out_wav), wav, SR)


KOKORO_FILES = {"kokoro-v1.0.int8.onnx": (92361271, "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx"),
                "voices-v1.0.bin": (28214398, "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin")}
_kokoro: dict = {}


def kokoro_ready() -> bool:
    from . import paths

    return all((paths.MODELS / "kokoro" / n).exists() and (paths.MODELS / "kokoro" / n).stat().st_size == sz for n, (sz, _) in KOKORO_FILES.items())


def ensure_kokoro(progress: Optional[Callable[[float, str], None]] = None) -> Path:
    """The Kokoro model (about 120 MB), downloaded once into the models folder; size and SHA-256 are checked."""
    from . import models

    try:
        return models.ensure("kokoro", progress)
    except models.ModelError as e:
        raise TTSError(f"The offline voice has to be downloaded once (about 120 MB). Connect to the internet and try again. ({e})") from e


def _synth_kokoro(text: str, voice: str, rate: float, out_wav: Path) -> None:
    try:
        from kokoro_onnx import Kokoro
    except ImportError as e:
        raise TTSError("The Kokoro voices need the kokoro-onnx package (pip install kokoro-onnx).") from e
    if "k" not in _kokoro:
        d = ensure_kokoro()
        os.environ.setdefault("ONNX_PROVIDER", "CPUExecutionProvider")          # the 8-bit model is made for the CPU, and "all providers" would also try TensorRT
        _kokoro["k"] = Kokoro(str(d / "kokoro-v1.0.int8.onnx"), str(d / "voices-v1.0.bin"))
    k = _kokoro["k"]
    if voice not in k.get_voices():
        raise TTSError(f"unknown Kokoro voice '{voice}'")
    lang = {"h": "hi", "b": "en-gb"}.get(voice[0], "en-us")
    wav, sr = k.create(text, voice=voice, speed=max(0.5, min(2.0, float(rate))), lang=lang)
    wav = np.asarray(wav, dtype="float32")
    if sr != SR:
        import math
        from scipy.signal import resample_poly

        g = math.gcd(sr, SR)
        wav = resample_poly(wav, SR // g, sr // g).astype("float32")
    sf.write(str(out_wav), wav, SR)


def _synth_clone(text: str, voice: str, rate: float, out_wav: Path) -> None:
    from . import voices as V

    raw = out_wav.with_suffix(".raw.wav")
    try:
        V.say(text, voice, raw)
    except V.VoiceError as e:
        raise TTSError(str(e)) from e
    try:
        tempo = max(0.5, min(2.0, float(rate)))
        cmd = [find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(raw), "-ac", "1", "-ar", str(SR)] + (["-filter:a", f"atempo={tempo:.3f}"] if abs(tempo - 1.0) > 0.01 else []) + [str(out_wav)]
        r = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        if r.returncode != 0:
            raise TTSError("the cloned voice could not be converted: " + r.stderr[-120:])
    finally:
        raw.unlink(missing_ok=True)


def _synth_vtengine(text: str, voice: str, rate: float, out_wav: Path) -> None:
    """`voice` is "<engine>:<voice>" as listed by the other computer. Its answer is converted to this app's sample rate."""
    import hashlib

    from .engines import registry, vtengine

    ep = registry.endpoint("vtengine")
    engine, _, name = voice.partition(":")
    cache = out_wav.parent / f".vt_{hashlib.sha1(f'{voice}|{rate:.3f}|{text}'.encode('utf-8')).hexdigest()[:20]}.wav"
    if not cache.exists():
        try:
            vtengine.speak(ep, text, cache, engine=engine, voice=name, rate=rate)
        except Exception as e:                                                      # noqa: BLE001
            raise TTSError(f"the other computer could not speak: {e}") from e
    r = subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(cache), "-ac", "1", "-ar", str(SR), str(out_wav)], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0:
        raise TTSError("the voice from the other computer could not be converted: " + r.stderr[-120:])


def _synth_voicestudio(text: str, voice: str, rate: float, out_wav: Path, instruction: str = "", seed: int = VOICE_SEED) -> None:
    """`voice` is "<engine>:<preset voice>", "profile:<id>", or "auto" (the server's own default). The sentence is cached by what it says, who says it and the seed.

    The seed is always sent: without one a zero-shot engine picks a new take, and often a new person, on every request.
    """
    import hashlib

    from .voicestudio import VoiceStudioError, client_for

    key = hashlib.sha1(f"{voice}|{rate:.3f}|{instruction}|{seed}|{text}".encode("utf-8")).hexdigest()[:20]
    cache = out_wav.parent / f".vs_{key}.wav"
    if not cache.exists():
        kind, _, name = voice.partition(":")
        kw: dict = {"speed": rate, "seed": seed}
        if instruction:
            kw["instruct"] = instruction
        if kind == "profile":
            kw["profile_id"] = name
        elif name:
            kw.update(engine=kind, preset_voice=name)
        client = client_for()
        try:
            cache.write_bytes(client.speak(text, **kw))
        except VoiceStudioError as e:
            raise TTSError(str(e)) from e
        finally:
            client.close()
    cmd = [find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(cache), "-ac", "1", "-ar", str(SR), str(out_wav)]
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0:
        raise TTSError("the voice server's sound could not be converted: " + r.stderr[-120:])


def _comfy_voice_servers() -> dict[str, str]:
    """{voice workflow id: url of a ComfyUI server that can run it}, over the main server and its workers. Never raises: no server means an empty answer."""
    from .comfy import ComfyClient, list_workflows
    from .engines import registry

    ep = registry.endpoint("comfy")
    if ep.mode == "off" or not ep.url:
        return {}
    capable: dict[str, list[str]] = {}
    for url in ep.all_urls():
        try:
            nodes = ComfyClient(url).object_info()
        except Exception:                                         # noqa: BLE001 - a worker that is down is skipped
            continue
        for w in list_workflows("audio"):
            if not w.problems(nodes):
                capable.setdefault(w.id, []).append(url)
    # Breeze needs bf16 (an RTX 30 series or newer): the workers are the extra cards, the main server is the older one, so Breeze prefers the last server; the rest take the first
    return {wid: (urls[-1] if wid.startswith("breeze") else urls[0]) for wid, urls in capable.items()}


def _comfy_voice_plan(voice: str, language: str, wants_direction: bool) -> tuple[Optional[str], set[str]]:
    """(the workflow that would speak this voice, the voice workflows some server can run)."""
    from .comfy import voicing

    servers = _comfy_voice_servers()
    return voicing.pick(voice, language, set(servers), wants_direction=wants_direction), set(servers)


def dialect_for(engine: str, voice: str, language: str = "en", wants_direction: bool = False) -> str:
    """Which direction dialect (vt/voice_direction.py) this voice speaks: the model behind a ComfyUI or VoiceStudio voice decides."""
    if engine == "comfyvoice":
        from .comfy import voicing

        return voicing.dialect(_comfy_voice_plan(voice, language, wants_direction)[0])
    if engine == "breeze":
        return "breeze"
    if engine != "voicestudio":
        return "none"
    kind = voice.partition(":")[0]
    if kind in VD.DIALECT_OF:
        return VD.DIALECT_OF[kind]
    if kind in ("profile", "auto", ""):
        try:
            from .voicestudio import client_for

            c = client_for()
            try:
                return VD.DIALECT_OF.get(c.tts_engines().get("active", ""), "none")
            finally:
                c.close()
        except Exception:                                     # noqa: BLE001 - not knowing the dialect only costs the direction, never the sentence
            return "none"
    return "none"


def _synth_comfyvoice(text: str, voice: str, rate: float, out_wav: Path, instruction: str = "", language: str = "en", *, anchor=None,
                      direct: Optional[bool] = None, seed: int = VOICE_SEED) -> None:
    """`voice` is "me:<saved voice id>" (cloned from a consented recording) or "design:<description>". The model is chosen by language and direction (vt/comfy/voicing.py).

    `anchor` (a vt/voice_lock.py::Anchor) turns a designed voice into a cloned one: the sentence is spoken by cloning the reference take, so every sentence is the
    same person. `direct` is decided once for the whole script, so the model never switches between a directed and a plain workflow from one sentence to the next.
    """
    from . import voices as V
    from .comfy import ComfyClient, ComfyError, load_workflow, voicing
    from .comfy import voice as CV

    kind, rest = voicing.split_voice(voice)
    wants_direction = bool(instruction) if direct is None else direct
    servers = _comfy_voice_servers()
    wid = None
    if kind == "design" and anchor is not None:                                       # the designed voice, cast once, now cloned for every sentence
        wid = voicing.pick("me:anchor", language, set(servers), wants_direction=wants_direction)
        if wid is not None:
            kind = "anchor"
    wid = wid or voicing.pick(voice, language, set(servers), wants_direction=wants_direction)
    if wid is None:
        raise TTSError("No voice model is installed on your ComfyUI server for this voice and language. See Settings, Engines (docs/ops/comfyui-voice-nodes.md).")
    wf = load_workflow(wid)
    ref, ref_text = None, ""
    if kind == "me":
        try:
            ref = V.ref_path(rest)
            ref_text = V.ref_text(rest)
        except V.VoiceError as e:
            raise TTSError(str(e)) from e
    elif kind == "anchor":
        ref, ref_text = anchor.path, anchor.text
    if kind == "design":
        instr = rest
    else:
        instr = instruction or (STEADY_DELIVERY if wants_direction and wid.endswith("direction") else "")
    client = ComfyClient(servers[wid])
    try:
        CV.speak(client, wf, text, out_wav, instruction=instr, ref_audio=ref, ref_text=ref_text, seed=seed, cache_dir=paths.DATA / "voice_cache", checked=True)
    except ComfyError as e:
        raise TTSError(str(e)) from e
    finally:
        client.close()
    if abs(rate - 1.0) > 0.01:
        tmp = out_wav.with_suffix(".rate.wav")
        out_wav.replace(tmp)
        tempo = max(0.5, min(2.0, float(rate)))
        r = subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(tmp), "-filter:a", f"atempo={tempo:.3f}", str(out_wav)], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        tmp.unlink(missing_ok=True)
        if r.returncode != 0:
            raise TTSError("the voice could not be sped up: " + r.stderr[-120:])


def synth_sentence(engine: str, voice: str, text: str, rate: float, out_wav: Path, instruction: str = "", language: str = "en", **lock) -> None:
    """`lock` (comfyvoice: anchor, direct, seed; voicestudio: seed) carries vt/voice_lock.py's choices to the engines that need them."""
    if engine == "comfyvoice":
        return _synth_comfyvoice(text, voice, rate, out_wav, instruction, language, **lock)
    if engine == "vtengine":
        return _synth_vtengine(text, voice, rate, out_wav)
    if engine == "voicestudio":
        return _synth_voicestudio(text, voice, rate, out_wav, instruction, **{k: v for k, v in lock.items() if k == "seed"})
    if engine == "clone":
        return _synth_clone(text, voice, rate, out_wav)
    if engine == "kokoro":
        return _synth_kokoro(text, voice, rate, out_wav)
    if engine == "edge":
        return _synth_edge(text, voice, rate, out_wav)
    if engine == "mms":
        return _synth_mms(text, voice, rate, out_wav)
    raise TTSError(f"unknown voice engine '{engine}'")


# --------------------------------------------------------------------------- word timing
def _frame_db(x: np.ndarray, hop: int = 240) -> np.ndarray:
    n = len(x) // hop
    if n == 0:
        return np.array([-90.0])
    f = x[: n * hop].reshape(n, hop)
    return 20 * np.log10(np.sqrt((f ** 2).mean(axis=1)) + 1e-7)


def word_times(words: list[str], audio: np.ndarray, sr: int = SR) -> list[tuple[float, float]]:
    """Start/end (seconds, relative to this clip) for each word, from the clip's own speech.

    The speech span is found by loudness; words share it in proportion to their speakable letters, with a little extra
    weight after punctuation; each inner boundary then snaps to the quietest 10 ms frame within 70 ms.
    """
    if not words:
        return []
    hop = sr // 100
    db = _frame_db(audio, hop)
    thr = max(np.percentile(db, 95) - 38, -70.0)
    voiced = np.where(db > thr)[0]
    a, b = (int(voiced[0]), int(voiced[-1]) + 1) if len(voiced) else (0, len(db))
    t0, t1 = a * 0.01, b * 0.01
    weights = []
    for w in words:
        n = max(1, len(re.sub(r"[^\w]", "", speakable(w))))
        weights.append(n + (2.5 if re.search(r"[,;:।\.?!]$", w) else 0.0))
    cum = np.cumsum(weights) / float(sum(weights))
    bounds = [t0 + c * (t1 - t0) for c in cum[:-1]]
    snapped = []
    for t in bounds:
        i = int(round(t / 0.01))
        lo, hi = max(a, i - 7), min(b - 1, i + 7)
        j = lo + int(np.argmin(db[lo:hi + 1])) if hi > lo else i
        snapped.append(j * 0.01)
    edges = [t0] + snapped + [t1]
    out = []
    for k in range(len(words)):
        s, e = edges[k], edges[k + 1]
        if k < len(words) - 1:
            e = max(s + 0.04, e - 0.01)                              # tiny gap so neighbouring words never overlap
        out.append((round(s, 3), round(max(e, s + 0.04), 3)))
    return out


# --------------------------------------------------------------------------- whole script
def assign_voices(engine: str, base_voice: str, speakers: list[str]) -> dict[str, str]:
    """A different voice for each speaker: the chosen voice first, then the opposite gender in the same language, then the rest."""
    eng = next((e for e in ENGINES if e["id"] == engine), None)
    if not eng:
        return {s: base_voice for s in speakers}
    base = next((v for v in eng["voices"] if v["id"] == base_voice), eng["voices"][0])
    same = [v for v in eng["voices"] if v["lang"] == base["lang"]]
    male = lambda v: bool(re.search(r"\bmale\b", v["label"].lower())) and "female" not in v["label"].lower()          # noqa: E731
    order = [base] + [v for v in same if v is not base and male(v) != male(base)] + [v for v in same if v is not base and male(v) == male(base)]
    return {s: order[i % len(order)]["id"] for i, s in enumerate(speakers)}


def synthesize(text: str, out_wav: Path, *, engine: str = "edge", voice: str = "bn-BD-NabanitaNeural", rate: float = 1.0,
               progress: ProgressFn = noop_progress, direction: bool = True, notes: Optional[dict[int, dict]] = None, language: str = "") -> dict:
    """Speak `text` into out_wav. Returns {"engine","voice","rate","duration","sentences":[{text,start,end,words:[{text,start,end}]}]}."""
    text = clean(text)
    if not text:
        raise TTSError("The script is empty.")
    if engine == "comfyvoice" and voice == "design:auto":                              # the director casts the voice from the content
        from .comfy import voicing as _voicing

        voice = _voicing.cast(text)
    if len(text) > MAX_CHARS:
        raise TTSError(f"The script is too long ({len(text)} characters). Keep it under {MAX_CHARS}, or split it into two videos.")
    sents = split_script(text)
    if not sents:
        raise TTSError("The script has no sentences.")
    if not language:
        from . import langdetect

        language = langdetect.from_text(text, default="en")
    speakers = list(dict.fromkeys(x["speaker"] for x in sents if x.get("speaker")))
    voices = assign_voices(engine, voice, speakers) if speakers else {}

    # read every sentence first: whether the script is directed at all is decided once, so the model never switches mode between sentences
    lines: list[dict] = []
    for i, s in enumerate(sents):
        dr = VD.parse(s["text"])
        note = (notes or {}).get(i) or {}
        if note.get("instruction") and not dr.instruction:                               # the director's delivery for a sentence the author left plain
            dr.instruction = note["instruction"]
        if note.get("before") in VD.EVENTS:
            dr.parts.insert(0, ("event", note["before"]))
        if note.get("after") in VD.EVENTS:
            dr.parts.append(("event", note["after"]))
        vid = voices.get(s.get("speaker"), voice)
        dialect = dialect_for(engine, vid, language, bool(dr.instruction))
        rendered = VD.render(dr, dialect, direction_on=direction, text_fn=speakable)
        if re.search(r"\w", re.sub(r"\[[^\]]*\]|\([^)]*\)", "", rendered.spoken)):
            lines.append({"s": s, "dr": dr, "vid": vid, "dialect": dialect, "rendered": rendered})
    if not lines:
        raise TTSError("Nothing speakable was found in the script.")
    directed = any(ln["rendered"].instruction for ln in lines)

    with tempfile.TemporaryDirectory() as d:
        locked, unlocked_why = _lock_voices(engine, lines, language, progress)

        def speak(k: int, seed: Optional[int] = None) -> np.ndarray:
            ln = lines[k]
            r = ln["rendered"]
            vid, extra = locked.get(ln["vid"], (ln["vid"], {}))
            extra = dict(extra)
            if seed is not None:
                extra["seed"] = seed
            if engine == "comfyvoice":
                extra.update(language=language, direct=directed)
            wav = Path(d) / f"s{k}_{seed}.wav"
            pace = min(max(r.rate, 1 - RATE_SWING), 1 + RATE_SWING)
            synth_sentence(engine, vid, r.spoken, rate * pace, wav, **({"instruction": r.instruction} if r.instruction else {}), **extra)
            x, sr = sf.read(str(wav), dtype="float32", always_2d=False)
            if x.ndim > 1:
                x = x.mean(axis=1)
            if sr != SR:
                from scipy.signal import resample_poly

                g = np.gcd(sr, SR)
                x = resample_poly(x, SR // g, sr // g).astype("float32")
            # trim the engine's own leading/trailing silence so our pauses are the only pauses
            db = _frame_db(x, SR // 100)
            v = np.where(db > max(db.max() - 45, -75))[0]
            if len(v):
                x = x[max(0, (v[0] - 2) * (SR // 100)): (v[-1] + 3) * (SR // 100)]
            return x

        takes = []
        for k in range(len(lines)):
            progress("voice", 0.1 + 0.75 * k / len(lines), f"Speaking sentence {k + 1} of {len(lines)}")
            takes.append(speak(k))
        steadiness = _keep_one_voice(engine, lines, takes, locked, speak, progress)
        if unlocked_why:
            steadiness["not_locked"] = unlocked_why

    pieces: list[np.ndarray] = []
    meta_s: list[dict] = []
    t = 0.0
    for ln, x in zip(lines, takes):
        s, dr, r = ln["s"], ln["dr"], ln["rendered"]
        x = VL.level(x, SR)
        words = dr.text.split()
        wt = word_times(words, x, SR)
        meta_s.append({"text": dr.text, "direction": {"instruction": dr.instruction, "events": dr.events, "dialect": ln["dialect"], "dropped": r.dropped} if (dr.instruction or dr.events) else None, "start": round(t, 3), "end": round(t + len(x) / SR, 3), "speaker": s.get("speaker"),
                       "words": [{"text": w, "start": round(t + a, 3), "end": round(t + b, 3), "speaker": s.get("speaker")} for w, (a, b) in zip(words, wt)]})
        pieces.append(x)
        gap = PARAGRAPH_GAP if s["para_end"] else SENTENCE_GAP
        pieces.append(np.zeros(int(gap * SR), dtype="float32"))
        t += len(x) / SR + gap
    audio = np.concatenate(pieces[:-1])                              # no trailing pause
    peak = float(np.abs(audio).max()) or 1.0
    audio = audio * (0.89 / peak)
    sf.write(str(out_wav), audio, SR)
    progress("voice", 1.0, "done")
    return {"engine": engine, "voice": voice, "rate": rate, "duration": round(len(audio) / SR, 3), "sentences": meta_s, "voices": voices, "steadiness": steadiness}


def _lock_voices(engine: str, lines: list[dict], language: str, progress: ProgressFn) -> tuple[dict[str, tuple[str, dict]], list[str]]:
    """({voice id: (the voice id to speak with, extra engine arguments)}, why some voice was not locked) for the voices the model would otherwise invent
    per sentence (vt/voice_lock.py).

    A designed ComfyUI voice gets a reference take that every sentence is cloned from; VoiceStudio's default voice gets a profile made from one.
    When a reference cannot be made the voice is spoken as before, and the reason is kept: a missing lock never stops the video.
    """
    out: dict[str, tuple[str, dict]] = {}
    why: list[str] = []
    cache = paths.DATA / "voice_cache"
    for vid in dict.fromkeys(ln["vid"] for ln in lines):
        if not VL.locks(engine, vid):
            continue
        text = VL.anchor_text([speakable(ln["dr"].text) for ln in lines if ln["vid"] == vid])
        progress("voice", 0.05, "Casting the voice once for the whole script")
        try:
            if engine == "comfyvoice":
                anchor = VL.make_anchor(engine, vid, text, language, lambda p: _synth_comfyvoice(text, vid, 1.0, p, language=language), cache)
                out[vid] = (vid, {"anchor": anchor})
            elif engine == "voicestudio":
                anchor = VL.make_anchor(engine, vid, text, language, lambda p: _synth_voicestudio(text, vid, 1.0, p), cache)
                out[vid] = (f"profile:{VL.profile_for(anchor, cache, lambda a: _voicestudio_profile(a, language))}", {})
        except Exception as e:                                                       # noqa: BLE001 - the unlocked voice still speaks
            why.append(f"{vid}: the voice could not be cast once ({e}); each sentence was voiced on its own")
    return out, why


def _voicestudio_profile(anchor, language: str) -> str:
    from .voicestudio import client_for

    c = client_for()
    try:
        pr = c.clone(f"Video Tool voice {anchor.key[:8]}", anchor.path, ref_text=anchor.text, language=language)
    finally:
        c.close()
    pid = pr.get("id") or (pr.get("profile") or {}).get("id")
    if not pid:
        raise TTSError("the voice server made no profile from the reference")
    return str(pid)


def _keep_one_voice(engine: str, lines: list[dict], takes: list[np.ndarray], locked: dict, speak: Callable[..., np.ndarray], progress: ProgressFn) -> dict:
    """Listen to every take; speak the ones that sound like another person again with other seeds, keeping the closest. Changes `takes` in place.

    Returns what was heard: {"checked", "respoken": [sentence index], "still_off": [sentence index], "scores": [per sentence, 1.0 = at the floor]}.
    """
    sigs = [VL.signature(x, SR) for x in takes]
    anchors = {v: extra["anchor"] for v, (_, extra) in locked.items() if "anchor" in extra}
    ref = None
    if len(anchors) == 1 and len({ln["vid"] for ln in lines}) == 1:                  # one narrator with a reference: judge against the reference itself
        a, sr = sf.read(str(next(iter(anchors.values())).path), dtype="float32", always_2d=False)
        ref = VL.signature(a.mean(axis=1) if a.ndim > 1 else a, sr)
    respoken, still_off = [], []
    for vid in dict.fromkeys(ln["vid"] for ln in lines):                             # each speaker is judged against their own sentences
        idx = [k for k, ln in enumerate(lines) if ln["vid"] == vid]
        group_ref = ref if len(idx) == len(lines) else None
        bad = [idx[j] for j in VL.outliers([sigs[k] for k in idx], group_ref)]
        if not bad or not VL.reseeds(engine):
            still_off += bad
            continue
        target = group_ref if group_ref is not None else np.median(np.array([sigs[k] for k in idx if sigs[k] is not None]), axis=0)
        for k in bad:
            progress("voice", 0.9, f"Sentence {k + 1} sounded like someone else: speaking it again")
            best, best_score = takes[k], VL.score(sigs[k], target)
            for n in range(1, VL.RETRIES + 1):
                try:
                    x = speak(k, seed=VOICE_SEED + 100 * n)
                except TTSError:
                    break
                sig = VL.signature(x, SR)
                if sig is not None and VL.score(sig, target) < best_score:
                    best, best_score, sigs[k] = x, VL.score(sig, target), sig
                if best_score <= 1.0:
                    break
            takes[k] = best
            respoken.append(k)
            if best_score > 1.0:
                still_off.append(k)
    centre = ref if ref is not None else (np.median(np.array([s for s in sigs if s is not None]), axis=0) if any(s is not None for s in sigs) else None)
    scores = [round(VL.score(s, centre), 2) if s is not None and centre is not None else None for s in sigs]
    return {"checked": sum(s is not None for s in sigs), "locked": sorted(v for v in locked), "respoken": respoken, "still_off": sorted(set(still_off)), "scores": scores}


def raw_transcript(script: dict, language: str = "bn") -> dict:
    """The same shape the speech recogniser returns, built from the script's known text and measured timings."""
    words = [{"text": w["text"], "start": w["start"], "end": w["end"], "conf": 1.0, **({"speaker": w["speaker"]} if w.get("speaker") else {})}
             for s in script["sentences"] for w in s["words"]]
    return {"language": language, "model": f"tts:{script['engine']}", "duration": script["duration"], "chunks": [], "chunks_without_speech": 0, "words": words}


def _vtengine_listing(e: dict) -> tuple[dict, bool, str]:
    """The voices of a paired Video Tool computer. Never raises."""
    from .engines import registry, vtengine

    ep = registry.endpoint("vtengine")
    if ep.mode == "off" or not ep.url:
        return e, False, "pair another Video Tool computer in Settings, Engines"
    h = registry.health("vtengine")
    if not h.ok or not ep.key:
        return e, False, h.why_not or h.note or "the other computer does not answer"
    try:
        return {**e, "voices": vtengine.voices(ep)}, True, ""
    except Exception as err:                                                         # noqa: BLE001
        return e, False, str(err)


def _voicestudio_listing(e: dict) -> tuple[dict, bool, str]:
    """The voices of the connected VoiceStudio: the preset voices of each ready engine, then the person's own profiles. Never raises."""
    from .engines import registry
    from .voicestudio import VoiceStudioError, client_for

    ep = registry.endpoint("voicestudio")
    if ep.mode == "off" or not ep.url:
        return e, False, "connect your voice server in Settings, Engines"
    h = registry.health("voicestudio")
    if not h.ok:
        return e, False, h.why_not or "the voice server does not answer"
    voices: list[dict] = [{"id": "auto", "label": "The server's own voice", "lang": "en"}]
    try:
        client = client_for()
        try:
            for b in client.tts_engines().get("backends", []):
                if b.get("available") and b.get("preset_voices"):
                    for v in b["preset_voices"]:
                        voices.append({"id": f"{b['id']}:{v}", "label": f"{b.get('display_name', b['id']).split(' (')[0]}: {v}", "lang": "en"})
            for pr in client.profiles():
                voices.append({"id": f"profile:{pr.get('id')}", "label": f"{pr.get('name', 'Voice')} (mine)", "lang": (pr.get("language") or "en")[:2].lower() or "en"})
        finally:
            client.close()
    except VoiceStudioError as err:
        return e, False, str(err)
    return {**e, "voices": voices}, True, h.note if "licence" in h.note else ""


DESIGN_PRESETS = [
    ("design:A warm, confident adult man with a clear voice and an even, friendly pace.", "A confident man, warm and clear"),
    ("design:A calm, thoughtful woman with a clear voice and a gentle, reflective delivery.", "A calm woman, gentle and thoughtful"),
    ("design:A bright, energetic young narrator, quick and upbeat, like a short-video host.", "An energetic young narrator"),
    ("design:A deep, serious older man speaking slowly, like a documentary narrator.", "A deep documentary narrator"),
]


def _comfyvoice_listing(e: dict) -> tuple[dict, bool, str]:
    """Voices a ComfyUI server can speak now: described voices (always), and the person's saved voices (cloned from a recording they may use). Never raises."""
    from . import voices as V

    wid, ready = _comfy_voice_plan("design:x", "en", False)
    if not ready:
        return e, False, "no voice model is installed on your ComfyUI server yet (Settings, Engines)"
    voices = ([{"id": "design:auto", "label": "Let the director choose from the script", "lang": "en"}] + [{"id": vid, "label": label, "lang": "en"} for vid, label in DESIGN_PRESETS]) if any(w.endswith("design") for w in ready) else []
    for v in V.list_voices():
        voices.append({"id": f"me:{v['id']}", "label": f"{v['name']} (my voice)", "lang": "en"})
    return {**e, "voices": voices}, bool(voices), "" if voices else "add a voice first"


def list_engines() -> list[dict]:
    out = []
    for e in ENGINES:
        ok, why = True, ""
        if e["id"] == "edge":
            try:
                import edge_tts  # noqa: F401
            except ImportError:
                ok, why = False, "edge-tts is not installed"
        elif e["id"] == "clone":
            from . import voices as V

            mine = [{"id": v["id"], "label": v["name"], "lang": "en"} for v in V.list_voices()]
            e = {**e, "voices": mine}
            if not V.available():
                ok, why = False, "voice cloning cannot run here (ONNX Runtime is missing)"
            elif not mine:
                ok, why = False, "add a voice first: a few seconds of your own voice, in Settings"
        elif e["id"] == "vtengine":
            e, ok, why = _vtengine_listing(e)
        elif e["id"] == "voicestudio":
            e, ok, why = _voicestudio_listing(e)
        elif e["id"] == "comfyvoice":
            e, ok, why = _comfyvoice_listing(e)
        elif e["id"] == "kokoro":
            try:
                import kokoro_onnx  # noqa: F401

                if not kokoro_ready():
                    why = "the voice model (about 120 MB) is downloaded the first time you use it"
            except ImportError:
                ok, why = False, "kokoro-onnx is not installed"
        else:
            try:
                import transformers, torch  # noqa: F401, E401
            except ImportError:
                ok, why = False, "transformers/torch are not installed"
        out.append({**e, "available": ok, "note": why})
    return out


def match_script(script: str, language: str, engine: str, voice: str) -> tuple[str, str]:
    """(language, voice) that fit the script's letters: English text gets English and an English voice of the same engine, Bangla text
    Bangla and a Bangla voice. A voice that already fits is kept, so a chosen voice is never replaced without need."""
    from . import langdetect

    want = langdetect.from_text(script, default="en")
    want = want if want in ("en", "bn") else language if language in ("en", "bn") else "en"
    try:
        voices = next(e for e in list_engines() if e["id"] == engine)["voices"]
    except (StopIteration, KeyError):
        return want, voice
    if any(v["id"] == voice and v["lang"].startswith(want) for v in voices) or voice.lower().startswith(want + "-"):
        return want, voice                                              # a voice of that language, listed or not (en-US-AndrewNeural), is kept
    return want, next((v["id"] for v in voices if v["lang"].startswith(want)), voice)
