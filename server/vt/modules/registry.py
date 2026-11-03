"""A small, import-light registry for capabilities the director may call."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Type

CostKind = Literal["instant", "fast", "slow", "heavy"]
Effect = Literal["none", "writes_artifact", "writes_timeline", "external_api", "external_post"]
Determinism = Literal["pure", "seeded", "external"]
Toolbox = Literal["autonomous", "studio", "full"]


@dataclass(frozen=True)
class Cost:
    kind: CostKind
    resources: tuple[str, ...] = ()
    est_seconds: float | Callable[[BaseModel], float] = 0.0

    def estimate(self, inputs: BaseModel) -> float:
        value = self.est_seconds(inputs) if callable(self.est_seconds) else self.est_seconds
        if value < 0:
            raise ValueError("cost estimate cannot be negative")
        return float(value)


@dataclass(frozen=True)
class Example:
    inputs: dict[str, Any]
    outputs: dict[str, Any]


@dataclass(frozen=True)
class ModuleSpec:
    id: str
    version: int
    summary: str
    when_to_use: str
    when_not_to_use: str
    inputs: Type[BaseModel]
    outputs: Type[BaseModel]
    requires: tuple[str, ...]
    produces: tuple[str, ...]
    cost: Cost
    effects: Effect
    determinism: Determinism
    grounding: tuple[str, ...]
    fallback: str | None
    fallback_reason: str
    examples: tuple[Example, ...]
    toolboxes: tuple[Toolbox, ...]
    plain_name: str
    log_line: Callable[[BaseModel, BaseModel], str] = field(repr=False, compare=False)
    run: Callable[..., Any] = field(repr=False, compare=False)
    preview: Callable[..., Any] | None = field(default=None, repr=False, compare=False)
    native_outputs: bool = False
    version_outputs: bool = True
    engines: tuple[str, ...] = ()          # capabilities an engine must answer (image.generate, video.generate, voice.speak...): resolved before the call and recorded in it


_REGISTRY: dict[str, ModuleSpec] = {}
_ID = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


def module(**details: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a function once; imports of the function's heavy dependencies stay in its body."""
    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        spec = ModuleSpec(run=fn, **details)
        if spec.id in _REGISTRY:
            raise ValueError(f"duplicate module id: {spec.id}")
        _REGISTRY[spec.id] = spec
        return fn
    return decorate


def get_module(module_id: str) -> ModuleSpec:
    return _REGISTRY[module_id]


def list_modules() -> list[ModuleSpec]:
    return [_REGISTRY[key] for key in sorted(_REGISTRY)]


def lint_registry(*, known_artifacts: set[str] | None = None) -> list[str]:
    """Return actionable contract errors; callers decide whether to raise or report."""
    from pydantic import BaseModel

    problems: list[str] = []
    for spec in list_modules():
        prefix = spec.id + ": "
        if not _ID.fullmatch(spec.id):
            problems.append(prefix + "id must be group.name in lowercase")
        if spec.version < 1:
            problems.append(prefix + "version must be positive")
        if not spec.summary or len(spec.summary) > 120 or "\n" in spec.summary:
            problems.append(prefix + "summary must be one line of at most 120 characters")
        for name in ("when_to_use", "when_not_to_use", "plain_name", "fallback_reason"):
            if not getattr(spec, name).strip():
                problems.append(prefix + f"{name} is required")
        if not spec.examples:
            problems.append(prefix + "at least one example is required")
        if not spec.toolboxes:
            problems.append(prefix + "at least one toolbox is required")
        if not issubclass(spec.inputs, BaseModel) or not issubclass(spec.outputs, BaseModel):
            problems.append(prefix + "inputs and outputs must be Pydantic models")
            continue
        for model in (spec.inputs, spec.outputs):
            for name, field_info in model.model_fields.items():
                if not (field_info.description or "").strip():
                    problems.append(prefix + f"{model.__name__}.{name} needs a description")
        if known_artifacts is not None:
            for artifact in (*spec.requires, *spec.produces):
                if artifact not in known_artifacts:
                    problems.append(prefix + f"unknown artifact type {artifact}")
        for index, example in enumerate(spec.examples):
            try:
                validated_inputs = spec.inputs.model_validate(example.inputs)
                validated_outputs = spec.outputs.model_validate(example.outputs)
                line = spec.log_line(validated_inputs, validated_outputs)
                if not isinstance(line, str) or not line.strip() or "\n" in line:
                    raise ValueError("log_line must render one sentence")
            except Exception as exc:
                problems.append(prefix + f"example {index + 1}: {exc}")
    return problems
