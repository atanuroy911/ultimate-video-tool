"""Typed artifact references over the project's existing file names."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any


ARTIFACT_PATHS = {
    "project.meta": "project.json",
    "source.info": "source.json",
    "script.text": "script.json",
    "audio.master": "audio.master.wav",
    "audio.asr": "audio.asr.wav",
    "audio.silences": "cuts.silence.json",
    "audio.retakes": "retakes.json",
    "audio.tighten": "tighten.json",
    "audio.edits": "audio_edits.json",
    "audio.cuts": "cuts.json",
    "audio.cut": "audio.cut.wav",
    "transcript.raw": "transcript.raw.json",
    "transcript": "transcript.json",
    "text.polish": "polish.json",
    "beats": "beats.json",
    "audio.events": "sounds_events.json",
    "audio.prosody": "prosody.json",
    "audio.emphasis": "emphasis.json",
    "audio.saliency": "saliency.json",
    "audio.sentence": "speech/sentence.wav",
    "context": "context.json",
    "impact.map": "impact.json",
    "direction": "direction.json",
    "direct.report": "director.json",
    "cutplan": "cutplan.json",
    "media.bin": "media",
    "script.video": "video_script.json",
    "aroll": "media/aroll.mp4",
    "scenes": "scenes.json",
    "reel.reading": "reel_reading.json",
    "composition": "composition",
    "timeline.thumbs": "thumbs",
    "render.snapshots": "snapshots",
    "render.silent": "exports/module-silent.mp4",
    "render.preview": "exports/module-preview.mp4",
    "sound.mix": "exports/module-mix.mp4",
    "render.final": "exports",
    "layers": "layers.json",
    "publish.kit": "publish.json",
    "publish.credits": "exports/credits.txt",
    "judge.scorecard": "scorecard.json",
    "judge.qa": "qa.json",
    "craft": "craft.json",
    "plan.draft": "plan.json",
    "plan.doc": "plan_doc.json",
    "human.request": "human_request.json",
    "finish.report": "finish.json",
    "shorts.candidates": "shorts_candidates.json",
    "gen.clips": "comfy_clips.json",
    "gen.fit": "media/fitted-clip.mp4",
}
KNOWN_ARTIFACTS = set(ARTIFACT_PATHS) | {
    "source.audio", "source.video", "media.tags",
    
    "log.calls", "log.technical",
}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def _digest(path: Path) -> str:
    sha = hashlib.sha256()
    files = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
    for file in files:
        if file.is_symlink():
            raise ValueError(f"artifact contains a symlink: {file}")
        if path.is_dir():
            sha.update(str(file.relative_to(path)).replace("\\", "/").encode("utf-8"))
            sha.update(b"\0")
        with file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                sha.update(chunk)
    return sha.hexdigest()


def _bytes(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file()) if path.is_dir() else path.stat().st_size


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for attempt in range(20):                                    # Windows refuses to replace a file someone is reading at that instant
            try:
                os.replace(temp, path)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        temp.unlink(missing_ok=True)


class Workspace:
    def __init__(self, project_dir: Path):
        self.root = Path(project_dir).resolve()
        self.index_path = self.root / "artifacts.json"
        self.redo_path = self.root / ".artifact_redo.json"

    def path_for(self, artifact_type: str) -> Path:
        if artifact_type in ("source.audio", "source.video"):
            paths = sorted(self.root.glob("input.*"))
            if artifact_type == "source.video":
                paths = [path for path in paths if path.suffix.lower() in VIDEO_SUFFIXES]
            if paths:
                path = paths[0]
                if not path.resolve().is_relative_to(self.root):
                    raise ValueError("artifact path leaves the project")
                return path
            raise FileNotFoundError(f"project has no {artifact_type} input file")
        if artifact_type not in ARTIFACT_PATHS:
            raise KeyError(f"artifact type has no single file path: {artifact_type}")
        path = self.root / ARTIFACT_PATHS[artifact_type]
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("artifact path leaves the project")
        return path

    def exists(self, artifact_type: str) -> bool:
        try:
            return self.path_for(artifact_type).exists()
        except (KeyError, FileNotFoundError):
            return False

    def read_json(self, artifact_type: str) -> Any:
        return json.loads(self.path_for(artifact_type).read_text(encoding="utf-8"))

    def index(self) -> dict[str, list[dict[str, Any]]]:
        if not self.index_path.exists():
            return {}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def ref(self, artifact_type: str) -> dict[str, Any] | None:
        if not self.exists(artifact_type):
            return None
        path = self.path_for(artifact_type)
        entries = self.index().get(artifact_type, [])
        digest = _digest(path)
        known = next((entry for entry in reversed(entries) if entry["hash"] == digest), None)
        return {"type": artifact_type, "path": str(path), "hash": digest,
                "ref": f"{artifact_type}@{digest[:12]}", "bytes": _bytes(path),
                "produced_by": known.get("produced_by") if known else None,
                "inputs": known.get("inputs", {}) if known else {}}

    def put_json(self, artifact_type: str, value: Any, *, call_id: str,
                 inputs: dict[str, str] | None = None) -> dict[str, Any]:
        path = self.path_for(artifact_type)
        if path.exists():
            previous = _digest(path)
            versions = self.root / ".artifact_versions" / artifact_type
            if not versions.resolve().is_relative_to(self.root):
                raise ValueError("artifact history leaves the project")
            versions.mkdir(parents=True, exist_ok=True)
            saved = versions / f"{previous}.json"
            if not saved.exists():
                shutil.copy2(path, saved)
            for old in sorted(versions.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[20:]:
                old.unlink()
        _atomic_json(path, value)
        ref = self.ref(artifact_type)
        assert ref is not None
        index = self.index()
        entry = {"hash": ref["hash"], "path": path.name, "produced_by": call_id,
                 "inputs": inputs or {}, "version": 1 + len(index.get(artifact_type, []))}
        index.setdefault(artifact_type, []).append(entry)
        index[artifact_type] = index[artifact_type][-20:]
        _atomic_json(self.index_path, index)
        self._clear_redo(artifact_type)
        return self.ref(artifact_type) or ref

    def _clear_redo(self, artifact_type: str) -> None:
        redo = json.loads(self.redo_path.read_text(encoding="utf-8")) if self.redo_path.exists() else {}
        if artifact_type in redo:
            redo.pop(artifact_type, None)
            _atomic_json(self.redo_path, redo)

    def undo(self, artifact_type: str) -> dict[str, Any]:
        """Restore the preceding file version and retain its provenance."""
        index = self.index()
        entries = index.get(artifact_type, [])
        if len(entries) < 2:
            raise ValueError(f"no previous version of {artifact_type}")
        previous = entries[-2]
        path = self.path_for(artifact_type)
        suffix = ".dir" if path.is_dir() else path.suffix
        saved = self.root / ".artifact_versions" / artifact_type / f"{previous['hash']}{suffix}"
        if not saved.resolve().is_relative_to(self.root):
            raise ValueError("artifact history leaves the project")
        if not saved.exists():
            raise FileNotFoundError(f"saved version missing: {artifact_type}@{previous['hash'][:12]}")
        current = _digest(path)
        current_saved = saved.with_name(f"{current}{suffix}")
        if not current_saved.exists():
            shutil.copytree(path, current_saved) if path.is_dir() else shutil.copy2(path, current_saved)
        if path.is_dir():
            shutil.rmtree(path)
            shutil.copytree(saved, path)
        else:
            shutil.copy2(saved, path)
        removed = entries[-1]
        index[artifact_type] = entries[:-1]
        _atomic_json(self.index_path, index)
        redo = json.loads(self.redo_path.read_text(encoding="utf-8")) if self.redo_path.exists() else {}
        redo.setdefault(artifact_type, []).append(removed)
        redo[artifact_type] = redo[artifact_type][-20:]
        _atomic_json(self.redo_path, redo)
        return self.ref(artifact_type) or previous

    def redo(self, artifact_type: str) -> dict[str, Any]:
        """Restore the version most recently removed by undo."""
        redo = json.loads(self.redo_path.read_text(encoding="utf-8")) if self.redo_path.exists() else {}
        entries = redo.get(artifact_type, [])
        if not entries:
            raise ValueError(f"no later version of {artifact_type}")
        target = entries.pop()
        path = self.path_for(artifact_type)
        suffix = ".dir" if path.is_dir() else path.suffix
        saved = self.root / ".artifact_versions" / artifact_type / f"{target['hash']}{suffix}"
        if not saved.exists():
            raise FileNotFoundError(f"saved version missing: {artifact_type}@{target['hash'][:12]}")
        if path.is_dir():
            shutil.rmtree(path)
            shutil.copytree(saved, path)
        else:
            shutil.copy2(saved, path)
        index = self.index()
        index.setdefault(artifact_type, []).append(target)
        index[artifact_type] = index[artifact_type][-20:]
        _atomic_json(self.index_path, index)
        redo[artifact_type] = entries
        _atomic_json(self.redo_path, redo)
        return self.ref(artifact_type) or target

    def snapshot_existing(self, artifact_type: str) -> None:
        """Save a stage-owned file before its unchanged implementation may overwrite it."""
        if not self.exists(artifact_type):
            return
        path = self.path_for(artifact_type)
        ref = self.record_existing(artifact_type, call_id="preexisting")
        versions = self.root / ".artifact_versions" / artifact_type
        if not versions.resolve().is_relative_to(self.root):
            raise ValueError("artifact history leaves the project")
        versions.mkdir(parents=True, exist_ok=True)
        saved = versions / f"{ref['hash']}{'.dir' if path.is_dir() else path.suffix}"
        if not saved.exists():
            shutil.copytree(path, saved) if path.is_dir() else shutil.copy2(path, saved)
        for old in sorted(versions.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True)[20:]:
            shutil.rmtree(old) if old.is_dir() else old.unlink()

    def record_existing(self, artifact_type: str, *, call_id: str,
                        inputs: dict[str, str] | None = None) -> dict[str, Any]:
        """Index an existing stage output without changing any of its bytes."""
        ref = self.ref(artifact_type)
        if ref is None:
            raise FileNotFoundError(artifact_type)
        index = self.index()
        entries = index.setdefault(artifact_type, [])
        if not entries or entries[-1]["hash"] != ref["hash"]:
            entries.append({"hash": ref["hash"], "path": self.path_for(artifact_type).name,
                            "produced_by": call_id, "inputs": inputs or {}, "version": len(entries) + 1})
            index[artifact_type] = entries[-20:]
            _atomic_json(self.index_path, index)
            self._clear_redo(artifact_type)
        return self.ref(artifact_type) or ref

    def stale(self, artifact_type: str) -> bool:
        ref = self.ref(artifact_type)
        if ref is None:
            return False
        for input_type, old_hash in ref["inputs"].items():
            current = self.ref(input_type)
            if current is None or current["hash"] != old_hash:
                return True
        return False
