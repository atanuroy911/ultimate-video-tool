"""Per-video working folder: projects/<id>/ with one JSON file per stage output."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from . import paths
from .schema import Beats, Cuts, PlanRequest, ProjectMeta, ScenesFile, Theme, Transcript
from .util import now_iso, read_json, slugify, write_json


class Project:
    def __init__(self, pid: str, root: Optional[Path] = None):
        self.id = pid
        self.dir = (root or paths.PROJECTS) / pid

    # ---- files
    @property
    def meta_path(self) -> Path: return self.dir / "project.json"
    @property
    def input_audio(self) -> Path:
        for p in sorted(self.dir.glob("input.*")):
            return p
        return self.dir / "input.wav"
    @property
    def master(self) -> Path: return self.dir / "audio.master.wav"
    @property
    def asr_wav(self) -> Path: return self.dir / "audio.asr.wav"
    @property
    def cut_audio(self) -> Path: return self.dir / "audio.cut.wav"
    @property
    def preview_audio(self) -> Path: return self.dir / "audio.preview.m4a"

    def ensure_preview_audio(self) -> Optional[Path]:
        """A small AAC copy of the cut audio for the Studio's preview player (the WAV is ~10 MB per minute)."""
        if not self.cut_audio.exists():
            return None
        if not self.preview_audio.exists() or self.preview_audio.stat().st_mtime < self.cut_audio.stat().st_mtime:
            import os
            import uuid

            from .util import find_tool, run
            # every writer encodes into its own temp file and swaps it in: the server (listing projects) and the pipeline can both
            # decide to build the preview at the same moment, and two FFmpegs writing one file produced a corrupt, silent preview
            tmp = self.preview_audio.with_name(f"audio.preview.{uuid.uuid4().hex[:8]}.tmp.m4a")
            try:
                run([find_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-i", str(self.cut_audio), "-ac", "1", "-ar", "32000",
                     "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(tmp)])
                os.replace(tmp, self.preview_audio)
            except Exception:
                tmp.unlink(missing_ok=True)
                return self.cut_audio
        return self.preview_audio
    @property
    def cuts_path(self) -> Path: return self.dir / "cuts.json"
    @property
    def raw_transcript_path(self) -> Path: return self.dir / "transcript.raw.json"
    @property
    def transcript_path(self) -> Path: return self.dir / "transcript.json"
    @property
    def beats_path(self) -> Path: return self.dir / "beats.json"
    @property
    def scenes_path(self) -> Path: return self.dir / "scenes.json"
    @property
    def comp_dir(self) -> Path: return self.dir / "composition"
    @property
    def exports_dir(self) -> Path: return self.dir / "exports"
    @property
    def requests_dir(self) -> Path: return self.dir / "requests"
    @property
    def glossary_path(self) -> Path: return self.dir / "glossary.json"

    # ---- create / load
    @classmethod
    def create(cls, title: str, audio: Path, *, language: str = "bn", aspect: str = "9:16", theme: str = "paper",
               pace: str = "normal", options: Optional[dict] = None, pid: Optional[str] = None) -> "Project":
        base = pid or f"{now_iso()[:10]}-{slugify(title)}"
        pid = base
        n = 2
        while (paths.PROJECTS / pid).exists():
            pid = f"{base}-{n}"
            n += 1
        proj = cls(pid)
        proj.dir.mkdir(parents=True, exist_ok=True)
        ext = audio.suffix.lower() or ".wav"
        shutil.copyfile(audio, proj.dir / f"input{ext}")
        meta = ProjectMeta(id=pid, title=title, language=language, aspect=aspect, theme=theme, pace=pace,
                           created_at=now_iso(), **({"options": options} if options else {}))
        proj.save_meta(meta)
        return proj

    @property
    def script_path(self) -> Path:
        return self.dir / "script.json"

    @classmethod
    def create_from_script(cls, title: str, script: str, *, voice_engine: str = "edge", voice: str = "en-US-AndrewNeural", rate: float = 1.0,
                           language: str = "en", aspect: str = "9:16", theme: str = "paper", pace: str = "normal",
                           options: Optional[dict] = None) -> "Project":
        """A project whose voice is synthesised from `script` by the first pipeline stage ('voice').
        The script is spoken in the language of its letters whatever was asked: an English script read by a Bangla voice (or the other way
        round) is never right, so the language and the voice are corrected to match the text."""
        import tempfile

        from . import tts

        if voice_engine == 'auto':
            from . import langdetect
            language = langdetect.from_text(script, default='en')
            voice_engine, voice = tts.recommended_voice(language)
        language, voice = tts.match_script(script, language, voice_engine, voice)

        import numpy as np
        import soundfile as sf

        with tempfile.TemporaryDirectory() as d:
            ph = Path(d) / "placeholder.wav"
            sf.write(str(ph), np.zeros(4800, dtype="float32"), 24000)
            proj = cls.create(title, ph, language=language, aspect=aspect, theme=theme, pace=pace, options=options)
        proj.update_meta(source="script")
        write_json(proj.script_path, {"text": script, "engine": voice_engine, "voice": voice, "rate": rate})
        return proj

    @classmethod
    def list_all(cls) -> list["Project"]:
        if not paths.PROJECTS.exists():
            return []
        return [cls(p.name) for p in sorted(paths.PROJECTS.iterdir()) if (p / "project.json").exists()]

    def exists(self) -> bool:
        return self.meta_path.exists()

    def meta(self) -> ProjectMeta:
        data = read_json(self.meta_path)
        if data is None:
            raise FileNotFoundError(f"project '{self.id}' not found")
        return ProjectMeta.model_validate(data)

    def save_meta(self, meta: ProjectMeta) -> None:
        write_json(self.meta_path, meta.model_dump())

    def update_meta(self, **kw) -> ProjectMeta:
        m = self.meta()
        for k, v in kw.items():
            setattr(m, k, v)
        self.save_meta(m)
        return m

    # ---- stage bookkeeping
    def stage_done(self, name: str, input_hash: str) -> bool:
        st = self.meta().stages.get(name)
        return bool(st and st.get("hash") == input_hash)

    def mark_stage(self, name: str, input_hash: str, **info) -> None:
        m = self.meta()
        m.stages[name] = {"hash": input_hash, "done_at": now_iso(), **info}
        self.save_meta(m)

    def invalidate_from(self, name: str, order: list[str]) -> None:
        m = self.meta()
        if name in order:
            for s in order[order.index(name):]:
                m.stages.pop(s, None)
        self.save_meta(m)

    # ---- typed data
    def transcript(self) -> Transcript:
        d = read_json(self.transcript_path)
        return Transcript.model_validate(d) if d else Transcript()

    def save_transcript(self, t: Transcript) -> None:
        write_json(self.transcript_path, t.model_dump())

    def beats(self) -> Beats:
        d = read_json(self.beats_path)
        return Beats.model_validate(d) if d else Beats()

    def cuts(self) -> Optional[Cuts]:
        d = read_json(self.cuts_path)
        if not d:
            return None
        try:
            return Cuts.model_validate(d)
        except Exception:
            return None

    def scenes(self) -> Optional[ScenesFile]:
        d = read_json(self.scenes_path)
        return ScenesFile.model_validate(d) if d else None

    def save_scenes(self, sf: ScenesFile) -> None:
        write_json(self.scenes_path, sf.model_dump(exclude_none=True))

    def glossary(self) -> dict[str, str]:
        g = dict(read_json(paths.GLOBAL_GLOSSARY, {}) or {})
        g.update(read_json(self.glossary_path, {}) or {})
        g.update(self.meta().options.glossary)
        return g

    # ---- plan requests (MCP queue)
    def requests(self) -> list[PlanRequest]:
        out = []
        if self.requests_dir.exists():
            for f in sorted(self.requests_dir.glob("*.json")):
                if f.name.endswith(".alternatives.json"):
                    continue
                out.append(PlanRequest.model_validate(read_json(f)))
        return out

    def save_request(self, r: PlanRequest) -> None:
        write_json(self.requests_dir / f"{r.id}.json", r.model_dump())

    def theme(self, name: str) -> Theme:
        """Keep a project portable even when its custom theme library is missing."""
        snapshot = self.dir / "theme.snapshot.json"
        try:
            theme = load_theme(name)
        except FileNotFoundError:
            # Older projects already embed the complete theme in their preview.
            candidates = [snapshot, *sorted(self.comp_dir.glob("*/data.json"))]
            for candidate in candidates:
                data = read_json(candidate, {}) or {}
                raw = data.get("theme", data)
                if raw.get("name") == name:
                    theme = Theme.model_validate(raw)
                    break
            else:
                raise
        write_json(snapshot, theme.model_dump(exclude_none=True))
        return theme


def load_theme(name: str) -> Theme:
    if not isinstance(name, str) or not name.strip() or name in (".", "..") or any(c in name for c in ("/", "\\", ":", "\x00")):
        raise ValueError("Choose a theme from this server's theme list.")
    p = paths.THEMES / name / "theme.json"
    if not p.resolve().is_relative_to(paths.THEMES.resolve()):
        raise ValueError("The theme must stay inside this server's theme library.")
    if not p.exists():
        raise FileNotFoundError(f"theme '{name}' not found")
    return Theme.model_validate(read_json(p))


def list_themes() -> list[Theme]:
    return [load_theme(p.name) for p in sorted(paths.THEMES.iterdir()) if (p / "theme.json").exists()]
