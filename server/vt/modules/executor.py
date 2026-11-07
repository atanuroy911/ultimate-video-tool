"""Validate, cache, run and record a module without changing its wrapped function."""
from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from .calls import append_call, append_technical, capture_technical, redact
from .budget import Budget
from .envelope import CallResult
from .registry import get_module, list_modules
from .resources import acquire
from .workspace import Workspace, _atomic_json, _digest
from ..util import Cancelled


class Executor:
    def __init__(self, project_dir: Path, pipeline: Any = None,
                 on_event: Callable[[dict[str, Any]], None] | None = None):
        from .defs import load

        load()
        self.ws = Workspace(project_dir)
        self.ws.pipeline = pipeline
        self.on_event = on_event
        self.cache_path = self.ws.root / ".module_cache.json"

    def call(self, module_id: str, values: dict[str, Any] | None = None, *, caller: str = "person",
             why: str = "", force: bool = False, max_seconds: float | None = None,
             raise_errors: bool = False, auto_prerequisites: bool = True,
             budget: Budget | None = None, cancel_event: threading.Event | None = None,
             skip_prerequisites: bool = False) -> CallResult:
        spec = get_module(module_id)
        call_id = "c" + uuid.uuid4().hex[:12]
        started = time.monotonic()
        raw_inputs = values or {}
        if self.on_event is not None:
            self.on_event({"type": "call_started", "id": call_id, "module": spec.id,
                           "caller": caller})

        engines_used: dict[str, str] = {}

        def finish(result: CallResult) -> CallResult:
            record = append_call(self.ws.root, {
                **({"engines": dict(engines_used)} if engines_used else {}),
                "id": call_id, "module": spec.id, "module_version": spec.version,
                "caller": {"kind": caller, "who": caller}, "why": why,
                "inputs": raw_inputs, "status": result.status, "cached": result.cached,
                "cost": result.cost, "wrote": [a["ref"] for a in result.artifacts],
                "summary": result.summary, "fix": result.fix,
                "level": "ok" if result.ok else "warn" if result.status in ("needs_input", "refused") else "error",
                "plain": result.summary,
            })
            if self.on_event is not None:
                self.on_event({"type": "call", "entry": record})
            return result

        try:
            inputs = spec.inputs.model_validate(raw_inputs)
        except ValidationError as exc:
            return finish(CallResult(ok=False, status="failed", summary="The step's inputs need a correction.",
                                     fix=str(exc)[:1200]))
        required_refs = {}
        for artifact_type in (() if skip_prerequisites else spec.requires):
            ref = self.ws.ref(artifact_type)
            if ref is None or self.ws.stale(artifact_type):
                # The classic recipe is the default producer for its native
                # artifacts. Reuse its unchanged stage methods and ordering.
                if auto_prerequisites and (self.ws.root / "project.json").exists():
                    from .recipes import load_classic
                    from .registry import get_module as producer_spec
                    from ..pipeline import Pipeline
                    from ..project import Project

                    producer = next((name for name in load_classic()
                                     if artifact_type in producer_spec(f"pipeline.{name}").produces), None)
                    if producer is not None:
                        try:
                            native = producer_spec(f"pipeline.{producer}")
                            ready = all(self.ws.ref(kind) is not None and not self.ws.stale(kind)
                                        for kind in native.requires)
                            if ready:
                                defaults = native.examples[0].inputs if native.examples else {}
                                made = self.call(native.id, defaults, caller="rules",
                                                 why=f"Needed {artifact_type} first.",
                                                 auto_prerequisites=False)
                                if not made.ok:
                                    raise RuntimeError(made.fix or made.summary)
                            else:
                                Pipeline(Project(self.ws.root.name, self.ws.root.parent)).run(to_stage=producer)
                        except Exception:
                            pass  # return the actionable needs_input result below
                        ref = self.ws.ref(artifact_type)
                        if ref is not None and not self.ws.stale(artifact_type):
                            required_refs[artifact_type] = ref["hash"]
                            continue
                producer = next((module.id for module in list_modules() if artifact_type in module.produces), None)
                fix = f"Make {artifact_type} first" + (f" with {producer}." if producer else ".")
                return finish(CallResult(ok=False, status="needs_input", summary=f"Needs {artifact_type}.", fix=fix))
            required_refs[artifact_type] = ref["hash"]
        estimate = spec.cost.estimate(inputs)
        if (max_seconds is not None and estimate > max_seconds) or (budget is not None and not budget.allows(estimate)):
            return finish(CallResult(ok=False, status="refused", summary="The step exceeds the time budget.",
                                     fix=f"Allow at least {estimate:.1f} seconds or choose a cheaper step."))

        if spec.engines and not getattr(inputs, "url", None):   # a server named in the call itself is the caller's choice; otherwise an engine is chosen by what it can do, never by its name: the call says which one answered
            from ..engines import registry as engine_registry

            for capability in spec.engines:
                found = engine_registry.resolve(capability)
                if found is None:
                    fix = f"No connected engine can do '{capability}'. Connect or set one up in Settings, Engines" + (f", or use {spec.fallback} instead." if spec.fallback else ".")
                    return finish(CallResult(ok=False, status="needs_input", summary=f"{spec.plain_name} needs a server that is not answering.", fix=fix))
                engines_used[capability] = found
        project_settings = self.ws.root / "project.json"
        settings_hash = _digest(project_settings) if project_settings.is_file() else None
        key_data = [spec.id, spec.version, inputs.model_dump(mode="json"), required_refs, settings_hash]
        cache_key = hashlib.sha256(json.dumps(key_data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        cache = json.loads(self.cache_path.read_text(encoding="utf-8")) if self.cache_path.exists() else {}
        cached = cache.get(cache_key)
        cache_safe = spec.effects == "none" or bool(spec.produces)
        if cache_safe and not spec.native_outputs and not force and cached and all(self.ws.exists(kind) and not self.ws.stale(kind) and
                                        self.ws.ref(kind)["hash"] == digest
                                        for kind, digest in cached.get("artifacts", {}).items()):
            return finish(CallResult(ok=True, status="ok", summary=cached["summary"],
                                     output=cached["output"], artifacts=[self.ws.ref(kind) for kind in spec.produces],
                                     cost={"seconds": 0.0}, cached=True))

        try:
            with acquire(spec.cost.resources):
                if cancel_event is not None and cancel_event.is_set():
                    if budget is not None:
                        budget.charge(time.monotonic() - started)
                    return finish(CallResult(ok=False, status="cancelled", summary="The step was cancelled."))
                if spec.native_outputs and spec.version_outputs:
                    for kind in spec.produces:
                        self.ws.snapshot_existing(kind)
                with capture_technical(self.ws.root, spec.id):
                    output = spec.outputs.model_validate(spec.run(self.ws, inputs))
                if cancel_event is not None and cancel_event.is_set():
                    if budget is not None:
                        budget.charge(time.monotonic() - started)
                    return finish(CallResult(ok=False, status="cancelled", summary="The step was cancelled."))
            artifacts = ([self.ws.record_existing(kind, call_id=call_id,
                                                   inputs={key: value for key, value in required_refs.items() if key not in spec.produces})
                          for kind in spec.produces if self.ws.exists(kind)] if spec.native_outputs else
                         [self.ws.put_json(kind, output.model_dump(mode="json"), call_id=call_id,
                                           inputs={key: value for key, value in required_refs.items() if key not in spec.produces})
                          for kind in spec.produces])
            summary = spec.log_line(inputs, output)
            elapsed = time.monotonic() - started
            if budget is not None:
                budget.charge(elapsed)
            cache[cache_key] = {"summary": summary, "output": output.model_dump(mode="json"),
                                "artifacts": {ref["type"]: ref["hash"] for ref in artifacts}}
            _atomic_json(self.cache_path, cache)
            return finish(CallResult(ok=True, status="ok", summary=summary,
                                     output=output.model_dump(mode="json"), artifacts=artifacts,
                                     cost={"seconds": round(elapsed, 4)}))
        except Cancelled:
            if budget is not None:
                budget.charge(time.monotonic() - started)
            result = finish(CallResult(ok=False, status="cancelled", summary="The step was cancelled."))
            if raise_errors:
                raise
            return result
        except Exception as exc:
            if budget is not None:
                budget.charge(time.monotonic() - started)
            append_technical(self.ws.root, f"{spec.id}: {type(exc).__name__}: {exc}")
            if raise_errors:
                finish(CallResult(ok=False, status="failed", summary=f"{spec.plain_name} failed.",
                                  fix=redact(str(exc))[:1200], cost={"seconds": round(time.monotonic() - started, 4)}))
                raise
            return finish(CallResult(ok=False, status="failed", summary=f"{spec.plain_name} failed.",
                                     fix=redact(str(exc))[:1200], cost={"seconds": round(time.monotonic() - started, 4)}))

    def call_async(self, module_id: str, values: dict[str, Any] | None = None, **kwargs: Any) -> CallResult:
        """Run a JSON-producing module in the background; native stages remain synchronous."""
        from .tickets import submit

        spec = get_module(module_id)
        if spec.native_outputs:
            return CallResult(ok=False, status="refused", summary="This stage must run synchronously.",
                              fix="Use call() so its existing file writes finish before the next stage.")
        ticket = submit(lambda event: self.call(module_id, values, cancel_event=event, **kwargs))
        return CallResult(ok=True, status="running", summary=f"Started {spec.plain_name.lower()}.", ticket=ticket)
