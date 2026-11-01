"""Studio API for the first-run setup: what this computer is, the person's choices, a plan before anything is downloaded, the install as a job, and a sample of each engine."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..engines import hardware, installers, setup

router = APIRouter(prefix="/api/setup", tags=["setup"])


class SetupBody(BaseModel):
    step: Optional[str] = None
    choices: Optional[dict[str, str]] = None
    bundles: Optional[list[str]] = None
    models_dir: Optional[str] = Field(default=None, max_length=400)
    done: Optional[bool] = None


class InstallBody(BaseModel):
    engines: list[str] = Field(min_length=1, max_length=4)
    bundles: list[str] = Field(default_factory=lambda: ["pictures"])


@router.get("")
def get_setup() -> dict[str, Any]:
    return setup.overview()


@router.put("")
def put_setup(body: SetupBody) -> dict[str, Any]:
    try:
        return setup.save(**body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/hardware")
def get_hardware() -> dict[str, Any]:
    return hardware.detect()


@router.get("/plan")
def get_plan(engines: str = "ollama,comfy", bundles: str = "pictures") -> list[dict[str, Any]]:
    names = [e for e in engines.split(",") if e]
    if any(e not in installers.INSTALLERS for e in names):
        raise HTTPException(404, "unknown engine in the plan")
    return setup.plans(names, [b for b in bundles.split(",") if b])


@router.post("/install")
def install(body: InstallBody) -> dict[str, Any]:
    from .app import jobs

    if any(e not in installers.INSTALLERS for e in body.engines):
        raise HTTPException(404, "unknown engine")
    problems = [p for plan in setup.plans(body.engines, body.bundles) for p in plan["problems"]]
    if problems:
        raise HTTPException(409, " ".join(problems))

    def work(cb):
        return setup.run_install(body.engines, body.bundles, lambda stage, f, m="": cb(stage, f, m))

    return jobs.submit("setup", None, "Setting up " + ", ".join(body.engines), work, when_busy="reuse").public()


@router.post("/try/{engine_id}")
def try_engine(engine_id: str) -> dict[str, Any]:
    try:
        return setup.try_it(engine_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
