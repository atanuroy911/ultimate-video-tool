"""Provider tool declarations derived from the registered module contract."""
from __future__ import annotations

from typing import Any, Literal

from .registry import ModuleSpec, get_module


Provider = Literal["openai", "anthropic", "gemini", "mcp"]


def export_tool(spec: ModuleSpec, provider: Provider) -> dict[str, Any]:
    """Expose one input schema without maintaining four provider-specific copies."""
    schema = spec.inputs.model_json_schema()
    if provider == "openai":
        return {"type": "function", "name": spec.id, "description": spec.summary,
                "parameters": schema, "strict": False}
    if provider == "anthropic":
        return {"name": spec.id, "description": spec.summary, "input_schema": schema}
    if provider == "gemini":
        return {"name": spec.id, "description": spec.summary, "parametersJsonSchema": schema}
    if provider == "mcp":
        return {"name": spec.id, "description": spec.summary, "inputSchema": schema}
    raise ValueError(f"unknown tool provider: {provider}")


def export_module(module_id: str, provider: Provider) -> dict[str, Any]:
    from .defs import load

    load()
    return export_tool(get_module(module_id), provider)
