"""The L2 director: an agent loop over the module catalogue (docs/plans/PLAN-DIRECTOR-MODULES.MD section 3.2, 3.3, 3.5).

    observe (the state card + the last result)  ->  one module call  ->  observe ...  ->  finish

The model is a function you pass in: `step(system, state, last, working_set) -> {"call": {"module", "inputs", "why"}} | {"finish": "..."}`; `ollama_step` and the MCP surface are two ways to
provide one, and the tests provide a scripted one. The loop owns everything that keeps a model honest: a step cap, a wall-time cap, a no-progress detector (the same call with the same
answer twice stops it), a state card that is always under 600 tokens, and working-set tool schemas (only the modules already used plus the hints, never all of them at once).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

PROMPTS = Path(__file__).resolve().parent / "prompts"
CARD_TOKENS = 600
SECTIONS = ("# Your job", "# The grounding rule", "# Reading results", "# Budget and cost", "# Checkpoints", "# Cutting from the audio", "# Your toolbox", "# Worked traces")


def load_prompt(version: str = "director-v1") -> str:
    p = PROMPTS / f"{version}.md"
    if not p.exists():
        raise KeyError(f"there is no director prompt called '{version}'")
    return p.read_text(encoding="utf-8")


def tokens(text: str) -> int:
    """A cheap, safe overestimate (four characters a token is the usual average; this counts three)."""
    return -(-len(text) // 3)


class Limits(BaseModel):
    steps: int = Field(default=30, ge=1, le=200)
    seconds: float = Field(default=900.0, ge=1)
    repeat: int = Field(default=2, ge=2, description="the same call with the same answer this many times in a row ends the run")


class Step(BaseModel):
    n: int
    module: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    why: str = ""
    ok: bool = True
    status: str = ""
    summary: str = ""
    fix: str = ""
    seconds: float = 0.0


class Run(BaseModel):
    ended: str = "finished"                       # finished | step_cap | time_cap | no_progress | refused | no_answer
    finish: str = ""
    steps: list[Step] = Field(default_factory=list)


def state_card(project, steps: list[Step], limits: Limits, started: float, budget_left: Optional[float] = None) -> str:
    """Everything the director needs to know now, in under 600 tokens: the project, what exists, what is stale, the budget, the last five calls, open warnings."""
    from ..modules.workspace import KNOWN_ARTIFACTS, Workspace

    ws = Workspace(project.dir)
    meta = project.meta()
    have = sorted(k for k in KNOWN_ARTIFACTS if _safe(ws.exists, k))
    stale = sorted(k for k in have if _safe(ws.stale, k))
    lines = [f"project: {meta.title[:40]} · {meta.aspect} · look {meta.options.look} · language {meta.language}",
             f"artifacts: {', '.join(have) or 'none yet'}"]
    if stale:
        lines.append(f"stale: {', '.join(stale)}")
    left = limits.seconds - (time.monotonic() - started) if budget_left is None else budget_left
    lines.append(f"budget: {max(0, limits.steps - len(steps))} steps, {max(0, left):.0f} s left")
    if steps:
        lines.append("last calls:")
        lines += [f"  {s.n}. {s.module} -> {'ok' if s.ok else s.status}: {s.summary[:90]}" for s in steps[-5:]]
    warn = [f"{s.module}: {s.fix[:100]}" for s in steps[-5:] if s.fix]
    if warn:
        lines.append("open problems: " + " | ".join(warn[-2:]))
    card = "\n".join(lines)
    while tokens(card) > CARD_TOKENS and len(lines) > 3:                  # never over: the oldest of the last calls goes first, then the rest from the bottom
        drop = next((i for i, line in enumerate(lines) if line.startswith("  ")), None)
        lines.pop(drop if drop is not None else len(lines) - 1)
        card = "\n".join(lines)
    return card[: CARD_TOKENS * 3]


def _safe(fn, *a) -> bool:
    try:
        return bool(fn(*a))
    except Exception:                                                                   # noqa: BLE001
        return False


def working_set(steps: list[Step], hints: tuple[str, ...] = ()) -> list[str]:
    """The modules whose full schema is shown: the ones already used, plus a few hints for what usually comes next. Everything else is one catalogue line away."""
    recent = []
    for s in reversed(steps):
        if s.ok and s.module == "meta.describe" and s.inputs.get("module_id"):
            recent.append(s.inputs["module_id"])
        recent.append(s.module)
    return list(dict.fromkeys(recent + list(hints) + ["meta.describe", "meta.catalog"]))[:12]


def hints_for(project, steps: list[Step]) -> tuple[str, ...]:
    """Phase hints, not restrictions: a fresh project suggests listening; after a plan exists, filling."""
    done = {s.module for s in steps if s.ok}
    if not done:
        return ("understand.read_script", "plan.make", "meta.catalog")
    if "plan.make" in done and "plan.start" not in done:
        return ("plan.edit", "plan.estimate", "meta.ask_human", "plan.start")
    if "plan.start" in done:
        return ("judge.facts", "meta.finish")
    return ("meta.catalog", "meta.finish")


def run_agent(project, step: Callable[..., dict], *, limits: Optional[Limits] = None, toolbox: str = "autonomous", caller: str = "director", goal: str = "",
              prompt: Optional[str] = None) -> Run:
    """Drive `step` until it finishes or a cap stops it. Every call goes through the executor, so each one is in the log with its `why`."""
    from ..modules.executor import Executor
    from ..modules.registry import get_module

    limits = limits or Limits()
    ex = Executor(project.dir)
    system = prompt if prompt is not None else load_prompt()
    from .plan_director import catalogue_lines
    system += "\n\nAvailable capabilities (ask meta.describe for exact inputs):\n" + catalogue_lines(toolbox)
    run = Run()
    started = time.monotonic()
    last: dict[str, Any] = {}
    seen: list[tuple[str, str, str]] = []
    while True:
        if len(run.steps) >= limits.steps:
            run.ended = "step_cap"
            break
        if time.monotonic() - started > limits.seconds:
            run.ended = "time_cap"
            break
        card = state_card(project, run.steps, limits, started)
        try:
            answer = step(system, card, last, working_set(run.steps, hints_for(project, run.steps)), goal)
        except Exception as e:                                                          # noqa: BLE001 - a model that errors ends the run, it does not crash the app
            run.ended, run.finish = "no_answer", f"{type(e).__name__}: {str(e)[:160]}"
            break
        if not isinstance(answer, dict):
            run.ended = "no_answer"
            break
        if "finish" in answer:
            run.finish = str(answer["finish"])[:500]
            run.ended = "finished"
            break
        call = answer.get("call") or {}
        mid = str(call.get("module", ""))
        try:
            spec = get_module(mid)
        except KeyError:
            last = {"error": f"there is no module '{mid}'. Use meta.catalog to see the real ones."}
            run.steps.append(Step(n=len(run.steps) + 1, module=mid or "?", inputs={}, ok=False, status="unknown", fix=last["error"]))
            continue
        if toolbox not in spec.toolboxes:
            last = {"error": f"{mid} is not in the {toolbox} toolbox."}
            run.steps.append(Step(n=len(run.steps) + 1, module=mid, inputs=call.get("inputs") or {}, ok=False, status="refused", fix=last["error"]))
            if sum(1 for s in run.steps[-3:] if s.status == "refused") >= 3:
                run.ended = "refused"
                break
            continue
        t0 = time.monotonic()
        res = ex.call(mid, call.get("inputs") or {}, caller=caller, why=str(call.get("why", ""))[:300] or f"Step {len(run.steps) + 1} of the director.")
        st = Step(n=len(run.steps) + 1, module=mid, inputs=call.get("inputs") or {}, why=str(call.get("why", ""))[:300], ok=res.ok, status=res.status, summary=res.summary or "", fix=res.fix or "",
                  seconds=round(time.monotonic() - t0, 2))
        run.steps.append(st)
        # Discovery is the model's only way to learn unfamiliar inputs. Cutting it at
        # 600 characters hid nearly the entire catalogue and most nested schemas.
        output = res.output if mid in ("meta.catalog", "meta.describe") else _small(res.output)
        last = {"module": mid, "ok": res.ok, "summary": res.summary or "", "fix": res.fix or "", "output": output}
        key = (mid, json.dumps(call.get("inputs") or {}, sort_keys=True, default=str), (res.summary or "") + (res.fix or ""))
        seen.append(key)
        if len(seen) >= limits.repeat and all(k == seen[-1] for k in seen[-limits.repeat:]):
            run.ended = "no_progress"                                                   # the same call with the same answer: more of it will not help
            break
    return run


def _small(output: Any, limit: int = 600) -> Any:
    """What the director gets back is small on purpose: a short summary of the output, never the output itself."""
    text = json.dumps(output, default=str, ensure_ascii=False) if output is not None else ""
    return text[:limit] + ("…" if len(text) > limit else "")


def ollama_step(model: str = "", temperature: float = 0.2) -> Callable[..., dict]:
    """A `step` function backed by the language AI the app already uses (vt.ai.complete_json); the answer is checked against the one schema below, never trusted as text."""
    schema = {"type": "object", "properties": {"call": {"type": "object", "properties": {"module": {"type": "string"}, "inputs": {"type": "object"}, "why": {"type": "string"}}, "required": ["module"]},
                                               "finish": {"type": "string"}}}

    def step(system: str, card: str, last: dict, working: list[str], goal: str) -> dict:
        from ..ai import complete_json
        from ..modules.registry import get_module
        from ..modules.toolspec import export_tool

        tools = []
        for m in working:
            try:
                tools.append(export_tool(get_module(m), "mcp"))
            except KeyError:
                pass
        user = (f"Goal: {goal or 'make the best video of this project'}\n\nState:\n{card}\n\nLast result:\n{json.dumps(last, ensure_ascii=False)}\n\n"
                f"Full schemas for your current working set (other capabilities remain available through meta.describe):\n{json.dumps(tools, ensure_ascii=False)}\n\nAnswer with one call, or finish.")
        return complete_json(user, schema, system=system, retries=0, max_tokens=700, temperature=temperature)

    return step
