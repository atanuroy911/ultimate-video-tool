"""A workflow is a ComfyUI graph in API format plus a manifest saying which inputs the app may change.

assets/comfy/workflows/<id>.json:
    {"id": "wan22_i2v", "label": "Wan 2.2 (14B)", "version": 1, "status": "verified" | "unverified",
     "frame_rule": {"fps": 16, "step": 4, "offset": 1},       # frames = step*k + offset at this frame rate
     "sizes": {"9:16": [320, 512], "16:9": [512, 320]},          # [width, height] presets, multiples the model accepts
     "manifest": {"image": [["201", "image"]], "prompt": [["93", "text"]], "width": [["98", "width"]], ...},
     "output": "203",                                            # the node whose file is the clip
     "graph": { ...the API-format graph... }}

Only manifest fields are ever written, so a graph that was benchmarked is the graph that runs. `problems()` checks the graph against the live
server (every node class exists, every model filename is installed) before anything is queued: a missing model is reported by name, not as a
late failure inside ComfyUI.
"""
from __future__ import annotations

import copy
import json
import random
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .. import paths

WORKFLOW_DIR = paths.ASSETS / "comfy" / "workflows"
LINK_TYPES = {"IMAGE", "MASK", "LATENT", "MODEL", "CLIP", "VAE", "CONDITIONING", "VIDEO", "NOISE", "GUIDER", "SAMPLER", "SIGMAS", "AUDIO", "CLIP_VISION", "CONTROL_NET"}


@dataclass
class Workflow:
    id: str
    label: str
    version: int
    status: str
    frame_rule: dict
    sizes: dict
    manifest: dict
    output: str
    graph: dict
    notes: str = ""
    kind: str = "video"                      # "video" (a still in, a clip out) or "image" (a prompt in, a picture out)

    def frames_for(self, seconds: float) -> tuple[int, float]:
        """(frames, fps) for a clip of about `seconds`: the nearest count the model accepts (step*k + offset)."""
        fps = float(self.frame_rule["fps"])
        step, offset = int(self.frame_rule["step"]), int(self.frame_rule["offset"])
        k = max(1, round((seconds * fps - offset) / step))
        return step * k + offset, fps

    def size_for(self, aspect: str) -> tuple[int, int]:
        if aspect not in self.sizes:
            raise KeyError(f"{self.label} has no size for {aspect}")
        w, h = self.sizes[aspect]
        return int(w), int(h)

    def public(self) -> dict:
        return {"id": self.id, "label": self.label, "version": self.version, "status": self.status, "sizes": self.sizes,
                "fps": self.frame_rule["fps"], "notes": self.notes, "kind": self.kind}

    def problems(self, object_info: dict) -> list[str]:
        """What would stop this graph on the connected server: unknown nodes, models that are not installed."""
        out = []
        for nid, node in self.graph.items():
            cls = node["class_type"]
            spec = object_info.get(cls)
            if spec is None:
                out.append(f"the server has no node '{cls}' (node {nid})")
                continue
            fields = {**spec.get("input", {}).get("required", {}), **spec.get("input", {}).get("optional", {})}
            for name, value in node["inputs"].items():
                definition = fields.get(name)
                if definition is None or isinstance(value, list):
                    continue
                choices = definition[0] if isinstance(definition, (list, tuple)) and definition else None
                if isinstance(choices, list) and choices and isinstance(value, str) and value not in choices and name != "image":
                    out.append(f"'{value}' is not installed for {cls}.{name} (node {nid})")
        return out

    def patched(self, *, image: str, prompt: str, aspect: str, seconds: float, seed: Optional[int] = None, negative: Optional[str] = None,
                prefix: str = "video_tool/clip") -> tuple[dict, dict]:
        """A copy of the graph with this request written into it, and the values used (frames, fps, width, height, seed)."""
        graph = copy.deepcopy(self.graph)
        width, height = self.size_for(aspect)
        frames, fps = self.frames_for(seconds) if self.kind == "video" else (1, 1.0)
        seed = int(seed) if seed is not None else random.randrange(1, 2**31)
        values: dict[str, Any] = {"image": image, "prompt": prompt, "width": width, "height": height, "frames": frames, "fps": fps, "seed": seed}
        if negative is not None:
            values["negative"] = negative
        for field, value in values.items():
            for node_id, input_name in self.manifest.get(field, []):
                graph[str(node_id)]["inputs"][input_name] = value
        for node_id, input_name in self.manifest.get("prefix", []):
            graph[str(node_id)]["inputs"][input_name] = f"{prefix}_{uuid.uuid4().hex[:8]}"
        return graph, {"frames": frames, "fps": fps, "width": width, "height": height, "seed": seed}


def patched_audio(workflow: Workflow, values: dict, *, prefix: str = "video_tool/voice") -> tuple[dict, dict]:
    """A copy of an audio workflow with the request written into it: only fields the manifest names are touched. A seed is made when none is given."""
    graph = copy.deepcopy(workflow.graph)
    values = dict(values)
    if values.get("seed") is None:
        values["seed"] = random.randrange(1, 2**31)
    for field, value in values.items():
        if value is None:
            continue
        for node_id, input_name in workflow.manifest.get(field, []):
            graph[str(node_id)]["inputs"][input_name] = value
    for node_id, input_name in workflow.manifest.get("prefix", []):
        graph[str(node_id)]["inputs"][input_name] = f"{prefix}_{uuid.uuid4().hex[:8]}"
    return graph, values


def _read(path: Path) -> Workflow:
    d = json.loads(path.read_text(encoding="utf-8"))
    return Workflow(id=d["id"], label=d["label"], version=int(d.get("version", 1)), status=d.get("status", "unverified"), frame_rule=d["frame_rule"], sizes=d["sizes"],
                    manifest=d["manifest"], output=str(d["output"]), graph=d["graph"], notes=d.get("notes", ""), kind=d.get("kind", "video"))


def list_workflows(kind: Optional[str] = "video") -> list[Workflow]:
    """The workflows of one kind (the clip workflows by default; `None` lists every kind)."""
    if not WORKFLOW_DIR.exists():
        return []
    found = [_read(p) for p in sorted(WORKFLOW_DIR.glob("*.json"))]
    return [w for w in found if kind is None or w.kind == kind]


def load_workflow(workflow_id: str) -> Workflow:
    path = WORKFLOW_DIR / f"{workflow_id}.json"
    if not path.exists() or path.resolve().parent != WORKFLOW_DIR.resolve():
        raise KeyError(f"no workflow '{workflow_id}'")
    return _read(path)


def picture_workflow(recipe: str = "", object_info: Optional[dict] = None) -> Workflow:
    """The picture graph with the loaders of one picture set (vt/engines/fit.py). With no set named: the one saved for the picture server, else,
    when the server's node catalogue is given, the best set whose files it already has, else the graph as written."""
    from ..engines import fit

    r = fit.BY_ID.get(recipe or str((_settings().get("picture_recipe") or "")))
    if r is None and object_info:                                     # the best set whose files (and nodes) the server already has
        r = next((x for x in fit.PICTURES if not w_with(load_workflow(x.workflow), x).problems(object_info)), None)
    return w_with(load_workflow(r.workflow), r) if r else load_workflow("zimage_t2i")


def w_with(w: Workflow, recipe) -> Workflow:
    out = copy.deepcopy(w)
    for nid, inputs in recipe.graph_inputs().items():
        out.graph[nid]["inputs"].update(inputs)
    out.label = f"{w.label}: {recipe.label}"
    return out


def _settings() -> dict:
    try:
        return json.loads(paths.SETTINGS.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}
