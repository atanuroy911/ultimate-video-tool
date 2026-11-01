"""The L1 director (docs/plans/PLAN-DIRECTOR-MODULES.MD section 3.2, 3.3): one structured plan of module calls, checked as a whole before anything runs.

    make_plan(project)   ->  DirectorPlan   (the language AI proposes; the rules answer when it cannot or is wrong)
    validate(plan, ...)  ->  [sentences]    (an empty list means it may run)
    run(plan, ...)       ->  results        (calls in order, each logged with the director's `why`)

Nothing here trusts the model: a plan is data, every call is checked against the module registry (the id exists, the inputs validate, the toolbox allows it, the things it needs exist or are
made earlier in the plan, the order has no cycle, the time fits the budget), and a plan that fails is retried once with the problems named, then replaced by the recipe. The result is
always something that runs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

PLAN_VERSION = 1
REF = re.compile(r"^@([A-Za-z0-9_]+)(?:\.([A-Za-z0-9_.\[\]]+))?$")        # @a  or  @a.field.sub
RECIPES = Path(__file__).resolve().parents[1] / "recipes"
CHECKPOINTS = ("after_listen", "after_direction", "after_cutplan", "after_fill", "after_assemble", "after_judge")


class PlanCall(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,23}$")
    module: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    after: list[str] = Field(default_factory=list)
    why: str = Field(default="", max_length=300)


class DirectorPlan(BaseModel):
    plan_version: int = PLAN_VERSION
    goal: str = Field(default="", max_length=300)
    style: str = Field(default="", max_length=200)
    calls: list[PlanCall] = Field(min_length=1, max_length=40)
    checkpoints: list[str] = Field(default_factory=list)
    source: str = "rules"                                               # "ai" or "rules" (a recipe)


# ----------------------------------------------------------------------------- recipes
def load_recipe(name: str) -> DirectorPlan:
    """A stored plan (L0): a recipe is a plan nobody had to ask a model for."""
    path = RECIPES / f"{name}.json"
    if not path.exists():
        raise KeyError(f"there is no recipe called '{name}'")
    raw = json.loads(path.read_text(encoding="utf-8"))
    calls = [PlanCall(id=c["id"], module=c["module"], inputs=c.get("inputs", {}), after=c.get("after", []), why=c.get("why", "")) for c in raw["calls"]]
    return DirectorPlan(goal=raw.get("goal", ""), style=raw.get("style", ""), calls=calls, checkpoints=raw.get("checkpoints", []), source="rules")


def recipe_names() -> list[str]:
    return sorted(p.stem for p in RECIPES.glob("*.json"))


def recipe_for(project) -> str:
    """Which recipe suits this project, from facts only (no model): a reel, a recording with a face, a script."""
    meta = project.meta()
    if meta.options.look == "reel":
        return "image-story"
    if getattr(meta, "source", "") == "script":
        return "impact-explainer"
    return "classic"


# ----------------------------------------------------------------------------- checking
def _artifact_exists(ws, kind: str) -> bool:
    try:
        return bool(ws.exists(kind))
    except Exception:                                                                   # noqa: BLE001
        return False


def validate(plan: DirectorPlan, *, ws=None, toolbox: str = "autonomous", budget_seconds: Optional[float] = None) -> list[str]:
    """Every problem in the plan, as sentences the director (or a person) can act on. Empty = it may run."""
    from ..modules.defs import load
    from ..modules.registry import get_module

    load()
    problems: list[str] = []
    ids = [c.id for c in plan.calls]
    for dup in {i for i in ids if ids.count(i) > 1}:
        problems.append(f"Two calls are named '{dup}'. Each call needs its own id.")
    known = set(ids)
    produced: set[str] = set()
    total = 0.0
    done: set[str] = set()
    for c in plan.calls:
        try:
            spec = get_module(c.module)
        except KeyError:
            problems.append(f"Call '{c.id}': there is no module called '{c.module}'. Use meta.catalog to see the real ones.")
            done.add(c.id)
            continue
        if toolbox not in spec.toolboxes:
            problems.append(f"Call '{c.id}': {c.module} is not in the {toolbox} toolbox.")
        for a in c.after:
            if a not in known:
                problems.append(f"Call '{c.id}' comes after '{a}', which is not in the plan.")
            elif a not in done:
                problems.append(f"Call '{c.id}' comes after '{a}', but '{a}' is listed later: the order has a loop or is backwards.")
        literal = {}
        for k, v in c.inputs.items():
            if isinstance(v, str) and REF.match(v):
                ref = REF.match(v).group(1)                                         # type: ignore[union-attr]
                if ref not in done and ref not in ("goal", "project"):
                    problems.append(f"Call '{c.id}' uses @{ref} for '{k}', which has not run before it.")
            else:
                literal[k] = v
        try:                                                                     # the literal inputs must fit the module; a reference is checked when it is filled in
            fields = spec.inputs.model_fields
            unknown = [k for k in literal if k not in fields]
            if unknown:
                problems.append(f"Call '{c.id}': {c.module} has no input called {', '.join(repr(u) for u in unknown)}. It takes: {', '.join(fields) or 'nothing'}.")
            else:
                spec.inputs.model_validate({**{k: _placeholder(fields[k]) for k, v in c.inputs.items() if k not in literal}, **literal})
        except ValidationError as e:
            problems.append(f"Call '{c.id}': the inputs for {c.module} are not right: {str(e.errors()[0].get('msg'))} ({'.'.join(str(x) for x in e.errors()[0].get('loc', []))}).")
        except Exception as e:                                                      # noqa: BLE001
            problems.append(f"Call '{c.id}': {type(e).__name__}: {str(e)[:160]}")
        for need in spec.requires:
            if need not in produced and not (ws is not None and _artifact_exists(ws, need)):
                maker = next((m.id for m in _all() if need in m.produces and need not in m.requires), None)
                problems.append(f"Call '{c.id}' needs {need}, which nothing before it makes" + (f": add {maker} first." if maker else "."))
        produced.update(spec.produces)
        try:
            total += spec.cost.estimate(spec.inputs.model_construct(**literal))
        except Exception:                                                           # noqa: BLE001
            total += float(spec.cost.est_seconds) if not callable(spec.cost.est_seconds) else 0.0
        done.add(c.id)
    for cp in plan.checkpoints:
        if cp not in CHECKPOINTS:
            problems.append(f"'{cp}' is not a checkpoint. Choose from: {', '.join(CHECKPOINTS)}.")
    if budget_seconds is not None and total > budget_seconds:
        problems.append(f"The plan takes about {total:.0f} s but the budget is {budget_seconds:.0f} s. Drop the most expensive calls or use cheaper ones.")
    return problems


def _all():
    from ..modules.registry import list_modules

    return list_modules()


def _placeholder(field) -> Any:
    """A value of the right kind for a field the plan gives by reference, so the rest of the inputs can be checked now."""
    ann = field.annotation
    name = getattr(ann, "__name__", str(ann))
    if field.default is not None and not field.is_required():
        return field.get_default(call_default_factory=True)
    return {"str": "x", "int": 1, "float": 1.0, "bool": False, "list": [], "dict": {}}.get(name, None)


def estimate(plan: DirectorPlan) -> float:
    from ..modules.registry import get_module

    total = 0.0
    for c in plan.calls:
        try:
            spec = get_module(c.module)
            total += spec.cost.estimate(spec.inputs.model_construct(**{k: v for k, v in c.inputs.items() if not (isinstance(v, str) and REF.match(v))}))
        except Exception:                                                           # noqa: BLE001
            pass
    return round(total, 1)


# ----------------------------------------------------------------------------- asking a model
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "goal": {"type": "string"}, "style": {"type": "string"},
        "calls": {"type": "array", "minItems": 1, "maxItems": 40, "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "module": {"type": "string"}, "inputs": {"type": "object"}, "after": {"type": "array", "items": {"type": "string"}}, "why": {"type": "string"}},
            "required": ["id", "module"]}},
        "checkpoints": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["calls"],
}


def prompt_text(version: str = "director-v1") -> str:
    from .agent import load_prompt

    return load_prompt(version)


def ask_model(project, *, recipe: DirectorPlan, catalog: str, goal: str = "", chat=None) -> Optional[DirectorPlan]:
    """One structured call: the model sees the standing prompt, what exists, the one-line catalogue and the recipe it may adapt. Returns None when it cannot answer."""
    try:
        if chat is None:
            from ..ai import complete_json
            from ..ai.providers import ai_enabled

            if not ai_enabled():
                return None
            chat = lambda system, user, schema: complete_json(user, schema, system=system, retries=0, max_tokens=2500, temperature=0.2)      # noqa: E731
        user = (f"Goal from the person: {goal or 'make the best video of this script'}\n\nThe catalogue (module, what it does, cost):\n{catalog}\n\n"
                f"A plan that already works for this kind of video. Change only what the goal needs:\n{recipe.model_dump_json(exclude={'source'})}\n\nAnswer with the plan.")
        data = chat(prompt_text(), user, PLAN_SCHEMA)
        plan = DirectorPlan.model_validate({**data, "source": "ai"})
        return plan
    except Exception:                                                               # noqa: BLE001
        return None


def catalogue_lines(toolbox: str = "autonomous") -> str:
    return "\n".join(f"{m.id} · {m.summary[:90]} · {m.cost.kind}" for m in _all() if toolbox in m.toolboxes)


def make_plan(project, *, goal: str = "", toolbox: str = "autonomous", budget_seconds: Optional[float] = None, chat=None, recipe: str = "") -> tuple[DirectorPlan, list[str]]:
    """The plan to run, and the notes about how it was got (what the model got wrong, whether the recipe was used). It always returns something that validates."""
    from ..modules.workspace import Workspace

    ws = Workspace(project.dir)
    base = load_recipe(recipe or recipe_for(project))
    notes: list[str] = []
    attempt = ask_model(project, recipe=base, catalog=catalogue_lines(toolbox), goal=goal, chat=chat)
    for round_ in range(2):
        if attempt is None:
            notes.append("No language AI answered: the stored recipe is used." if round_ == 0 else "The AI's plan could not be repaired: the stored recipe is used.")
            break
        problems = validate(attempt, ws=ws, toolbox=toolbox, budget_seconds=budget_seconds)
        if not problems:
            return attempt, notes
        notes.append(f"The AI's plan had {len(problems)} problem{'s' if len(problems) != 1 else ''}: {problems[0]}")
        if round_ == 1:
            notes.append("The AI's plan could not be repaired: the stored recipe is used.")
            break
        attempt = _repair(project, attempt, problems, chat)
        if attempt is None:
            notes.append("The AI could not correct its plan: the stored recipe is used.")
    problems = validate(base, ws=ws, toolbox=toolbox, budget_seconds=budget_seconds)
    if problems:
        notes.append("The stored recipe itself needs: " + "; ".join(problems[:2]))
    return base, notes


def _repair(project, plan: DirectorPlan, problems: list[str], chat) -> Optional[DirectorPlan]:
    try:
        if chat is None:
            from ..ai import complete_json

            chat = lambda system, user, schema: complete_json(user, schema, system=system, retries=0, max_tokens=2500, temperature=0.1)      # noqa: E731
        user = "Your plan has these problems:\n- " + "\n- ".join(problems[:8]) + f"\n\nYour plan:\n{plan.model_dump_json(exclude={'source'})}\n\nAnswer with the corrected plan."
        return DirectorPlan.model_validate({**chat(prompt_text(), user, PLAN_SCHEMA), "source": "ai"})
    except Exception:                                                               # noqa: BLE001
        return None


# ----------------------------------------------------------------------------- running
def project_facts(project) -> dict[str, Any]:
    """What every plan may refer to as @project.<name>: the length of the cut speech, the title, the shape and the language."""
    meta = project.meta()
    try:
        words = [w for w in project.transcript().words if not w.cut]
        duration = round(max((w.end for w in words), default=0.0), 2)
    except Exception:                                                                   # noqa: BLE001
        duration = 0.0
    return {"duration": duration, "title": meta.title, "aspect": meta.aspect, "language": meta.language}


def resolve(value: Any, results: dict[str, dict], goal: str, facts: Optional[dict[str, Any]] = None) -> Any:
    """@goal is the person's goal; @project.duration is a fact about the project; @a is call a's whole output; @a.field.sub walks into it."""
    if isinstance(value, str):
        m = REF.match(value)
        if not m:
            return value
        if m.group(1) == "goal":
            return goal
        cur: Any = (facts or {}) if m.group(1) == "project" else results.get(m.group(1), {})
        for part in (m.group(2) or "").split(".") if m.group(2) else []:
            cur = cur.get(part) if isinstance(cur, dict) else None
        return cur
    if isinstance(value, dict):
        return {k: resolve(v, results, goal, facts) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, results, goal, facts) for v in value]
    return value


GROUPS = {"after_listen": ("audio.", "asr.", "text.", "understand."), "after_direction": ("direct.",), "after_cutplan": ("cut.",), "after_fill": ("fill.", "gen."),
          "after_assemble": ("timeline.", "sound.", "render."), "after_judge": ("judge.",)}


def checkpoint_call(plan: DirectorPlan, event: str) -> Optional[str]:
    """The id of the last call of the plan that belongs to this checkpoint's group: when it finishes, the checkpoint fires."""
    last = None
    for c in plan.calls:
        if c.module.startswith(GROUPS.get(event, ())):
            last = c.id
    return last


def run(plan: DirectorPlan, project, *, caller: str = "director", goal: str = "", stop_on_failure: bool = False, on_checkpoint=None) -> dict[str, Any]:
    """Run the calls in order through the executor. A failed call is logged with its fix and the plan goes on unless `stop_on_failure` (later calls that need it will say so)."""
    from ..modules.executor import Executor

    ex = Executor(project.dir)
    results: dict[str, dict] = {}
    report: list[dict[str, Any]] = []
    facts = project_facts(project)
    for c in plan.calls:
        res = ex.call(c.module, resolve(c.inputs, results, goal or plan.goal, facts), caller=caller, why=c.why or f"Step {c.id} of the director's plan.")
        results[c.id] = res.output or {}
        report.append({"id": c.id, "module": c.module, "ok": res.ok, "status": res.status, "summary": res.summary, "fix": res.fix})
        if not res.ok and stop_on_failure:
            break
        if on_checkpoint:
            for event in plan.checkpoints:
                if checkpoint_call(plan, event) == c.id:
                    on_checkpoint(event, results)
    return {"ok": all(r["ok"] for r in report), "calls": report, "results": results}
