"""One spoken sentence from a ComfyUI audio workflow (Breeze TTS 2, OmniVoice ...): text (and optionally a reference recording and a direction) in, a WAV out.

Voices live on the same server as the pictures and clips, so a person who runs ComfyUI and Ollama has everything. The workflow says which nodes it needs; `problems()` names
anything the server lacks before a single second is spent. Results are cached by what was asked, so asking twice never renders twice.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional

from ..util import CREATE_NO_WINDOW, find_tool
from .client import ComfyClient, ComfyError, output_files
from .workflows import Workflow, patched_audio


def request_key(workflow: Workflow, text: str, instruction: str, ref_hash: str, ref_text: str, seed: Optional[int]) -> str:
    raw = "|".join([workflow.id, str(workflow.version), text.strip(), instruction.strip(), ref_hash, ref_text.strip(), str(seed)])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def speak(client: ComfyClient, workflow: Workflow, text: str, out_wav: Path, *, instruction: str = "", ref_audio: Optional[Path] = None, ref_text: str = "",
          seed: Optional[int] = 1, cache_dir: Optional[Path] = None, progress: Callable[[float, str], None] = lambda f, m: None,
          cancelled: Callable[[], bool] = lambda: False, timeout: float = 900.0, checked: bool = False) -> dict:
    """Write the sentence to `out_wav` (mono 24 kHz WAV). Returns {"seconds_taken", "cached", "prompt_id", "seed"}. Raises ComfyError in words."""
    import time

    if workflow.kind != "audio":
        raise ComfyError(f"{workflow.label} does not make speech.", kind="rejected")
    needs_ref = "ref_audio" in workflow.manifest
    if needs_ref and (ref_audio is None or not Path(ref_audio).exists()):
        raise ComfyError(f"{workflow.label} needs a reference recording of the voice.", kind="rejected")
    started = time.time()
    ref_hash = hashlib.sha1(Path(ref_audio).read_bytes()).hexdigest()[:16] if needs_ref else ""
    key = request_key(workflow, text, instruction, ref_hash, ref_text, seed)
    if cache_dir is not None:
        cached = Path(cache_dir) / f"voice_{key}.wav"
        if cached.exists():
            out_wav.write_bytes(cached.read_bytes())
            return {"seconds_taken": 0.0, "cached": True, "prompt_id": "", "seed": seed}
    if not checked:
        problems = workflow.problems(client.object_info())
        if problems:
            raise ComfyError(f"{workflow.label} cannot run on this server: " + "; ".join(problems[:4]), kind="rejected", detail=problems)
    values: dict = {"text": text, "seed": seed}
    if "instruction" in workflow.manifest:
        if workflow.id.startswith("omnivoice"):                       # a fixed vocabulary, not free text
            from .voicing import omnivoice_instruct

            instruction = omnivoice_instruct(instruction, design=workflow.id.endswith("design"))
        values["instruction"] = instruction or ("" if workflow.id.endswith("clone") else None)
    if needs_ref:
        values["ref_audio"] = client.upload_file(Path(ref_audio), f"vt_ref_{ref_hash}.wav", "audio/wav")
        values["ref_text"] = ref_text
    graph, used = patched_audio(workflow, values)
    progress(0.05, "Queued")
    prompt_id = client.submit(graph)
    entry = client.wait(prompt_id, lambda f, m: progress(0.1 + 0.8 * f, m), cancelled, timeout)
    files = output_files(entry, workflow.output) or output_files(entry)
    if not files:
        raise ComfyError("ComfyUI finished but produced no sound.", kind="failed", detail=entry.get("outputs"))
    with tempfile.TemporaryDirectory() as work:
        raw = client.download(files[0]["filename"], files[0]["subfolder"], files[0]["type"], Path(work) / Path(files[0]["filename"]).name)
        r = subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(raw), "-ac", "1", "-ar", "24000", str(out_wav)], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        if r.returncode != 0:
            raise ComfyError("The sound from ComfyUI could not be read: " + r.stderr[-120:], kind="failed")
    if cache_dir is not None:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        (Path(cache_dir) / f"voice_{key}.wav").write_bytes(out_wav.read_bytes())
    progress(1.0, "Done")
    return {"seconds_taken": round(time.time() - started, 1), "cached": False, "prompt_id": prompt_id, "seed": used.get("seed")}
