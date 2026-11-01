"""Environment checks, shared by `vt doctor` and the Studio settings page."""
from __future__ import annotations

import sys

from . import paths
from .util import find_tool, run


def run_checks() -> list[dict]:
    rows: list[dict] = []

    def check(name: str, fn, fix: str = "") -> None:
        try:
            ok, info = fn()
        except Exception as e:  # noqa: BLE001
            ok, info = False, str(e).splitlines()[0][:100]
        rows.append({"name": name, "ok": bool(ok), "detail": info, "fix": "" if ok else fix})

    check("Python 3.11", lambda: (sys.version_info[:2] == (3, 11), sys.version.split()[0]), "use the project's .venv")
    check("FFmpeg", lambda: (True, run([find_tool("ffmpeg"), "-version"]).splitlines()[0][:70]), "install FFmpeg and add it to PATH")
    check("FFmpeg NVENC", lambda: ("h264_nvenc" in run([find_tool("ffmpeg"), "-hide_banner", "-encoders"]), "GPU video encoding"),
          "optional: without NVENC renders use the CPU encoder")
    check("Node 20+", lambda: (int(run([find_tool("node"), "-v"]).strip().lstrip("v").split(".")[0]) >= 20, run([find_tool("node"), "-v"]).strip()),
          "install Node 20 or newer")
    check("HyperFrames", lambda: ((paths.RENDERER / "node_modules" / "hyperframes").exists(), "renderer/node_modules"), "cd renderer && npm install")
    check("Fonts", lambda: ((paths.FONTS / "fonts.css").exists(), "design/fonts"), "cd renderer && node scripts/build-fonts.mjs")
    check("Icons", lambda: ((paths.ICONS / "lucide.json").exists(), "design/icons"), "cd renderer && node scripts/build-icons.mjs")
    check("Music + SFX", lambda: ((paths.MUSIC / "index.json").exists() and (paths.SFX / "pop.wav").exists(), "assets/"),
          "python scripts/make_assets.py")

    def gpu():
        from .stages import asr
        return asr.cuda_available(), "CUDA for speech recognition"

    check("CUDA (CTranslate2)", gpu, "optional: install the CUDA build of PyTorch, otherwise transcription runs on the CPU")

    def build():
        from . import gpu_detect

        want = gpu_detect.decide()
        try:
            import torch
            have = (torch.version.cuda or "").replace(".", "")[:3]
            have = f"cu{have}" if have else "cpu"
        except Exception:                                                                # noqa: BLE001
            have = "none"
        return have == want.flavour, f"{have} installed; this computer fits {want.flavour}: {want.why}"

    check("GPU build", build, "run the installer again: it installs the build that fits this computer (scripts/setup.ps1 or setup.sh)")

    def mods():
        from .stages import asr
        have = [m["key"] for m in asr.list_models() if m["installed"]]
        return bool(have), ", ".join(have) or "none downloaded yet"

    check("ASR model", mods, "vt models pull bn-medium")
    def lexicon():
        from .visuals.lexicon import Lexicon
        lx = Lexicon.get()
        return lx.ok, f"{len(lx.words):,} English words mapped to pictures" if lx.ok else "not built"

    check("Picture dictionary", lexicon, "python scripts/build_visual_lexicon.py")

    def local_ai():
        from . import llm
        st = llm.status()
        if st["llm_mode"] == "off":
            return True, "turned off (rules only)"
        return st["reachable"] and st["model_ready"], (f"{st['model']} at {st['ollama_url']}" if st["reachable"] else f"no server at {st['ollama_url']}")

    check("Local AI (scene planner)", local_ai, "Settings > Local AI planner > Set up, or point it at an Ollama server")

    def voice():
        from . import tts
        ok = [e["id"] for e in tts.list_engines() if e["available"]]
        return bool(ok), ", ".join(ok) or "none"

    check("Voices (script to speech)", voice, "pip install edge-tts   (or the speech extra for the offline voice)")
    check("Studio build", lambda: ((paths.ROOT / "studio" / "dist" / "index.html").exists(), "studio/dist"), "cd studio && npm install && npm run build")
    return rows
