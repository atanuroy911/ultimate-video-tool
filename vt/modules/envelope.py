"""The small, stable result returned to any director surface."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CallResult(BaseModel):
    ok: bool = Field(description="Whether the call produced a valid result.")
    status: Literal["ok", "running", "failed", "needs_input", "refused", "cancelled"] = Field(description="Call state.")
    summary: str = Field(description="One short sentence for the director and the person.")
    output: dict[str, Any] | None = Field(default=None, description="Validated, small module output.")
    artifacts: list[dict[str, Any]] = Field(default_factory=list, description="Typed project files written by this call.")
    warnings: list[str] = Field(default_factory=list, description="Nonfatal problems.")
    cost: dict[str, float] = Field(default_factory=dict, description="Measured seconds and other resources spent.")
    ticket: str | None = Field(default=None, description="Asynchronous ticket for a running call.")
    fix: str | None = Field(default=None, description="Actionable correction for a failed or refused call.")
    cached: bool = Field(default=False, description="Whether an earlier identical result was reused.")
