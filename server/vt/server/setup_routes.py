"""Studio API for the first-run setup: what this computer is, the person's choices, a plan before anything is downloaded, the install as a job, and a sample of each engine."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..engines import hardware, installers, setup

router = APIRouter(prefix="/api/setup", tags=["setup"])


class SetupBody(BaseModel):
    step: Optional[str] = None
    choices: Optional[dict[str, str]] = None
    bundles: Optional[list[str]] = None
    models_dir: Optional[str] = Field(default=None, max_length=400)
    install_dir: Optional[str] = Field(default=None, max_length=400)
    gpu: Optional[int] = Field(default=None,ge=0,le=16)
    done: Optional[bool] = None
    picture_model: Optional[str] = Field(default=None, max_length=60)
    language_model: Optional[str] = Field(default=None, max_length=60)


class InstallBody(BaseModel):
    engines: list[str] = Field(min_length=1, max_length=4)
    bundles: list[str] = Field(default_factory=lambda: ["pictures"])
    models_dir: Optional[str] = Field(default=None,max_length=400)
    install_dir: Optional[str] = Field(default=None,max_length=400)
    gpu: Optional[int] = Field(default=None,ge=0,le=16)
    picture_model: Optional[str] = Field(default=None, max_length=60)
    language_model: Optional[str] = Field(default=None, max_length=60)


@router.post('/ollama-model')
def install_language_model():
    """Add the recommended model through the chosen existing Ollama's own API."""
    from .. import llm
    from ..engines import registry
    from ..util import read_json,write_json
    from .. import paths
    from .app import jobs
    endpoint=registry.endpoint('ollama')
    if endpoint.mode=='off' or not llm.reachable(endpoint.url):
        raise HTTPException(409,'Connect an Ollama engine on the processing server first.')
    model=llm.choose_installed(llm.installed_models(endpoint.url)) or llm.recommend_model()
    def work(cb):
        if not llm.has_model(model,endpoint.url):
            llm.pull(model,lambda s,f,m='':cb('model',f,m),url=endpoint.url)
        settings=read_json(paths.SETTINGS,{}) or {};settings['ollama_model']=model;write_json(paths.SETTINGS,settings)
        registry.forget('ollama')
        return {'model':model,'url':endpoint.url}
    return jobs.submit('setup',None,'Add the recommended language model',work,when_busy='refuse').public()


@router.get("")
def get_setup(request: Request) -> dict[str, Any]:
    # the person sits at this computer when the request comes from loopback (the client app on the same PC forwards from 127.0.0.1)
    host = request.client.host if request.client else ""
    return setup.overview(same_computer=host in ("127.0.0.1", "::1", "localhost"))


@router.get("/folders")
def get_folders(path: str = "") -> dict[str, Any]:
    """Folder names on this server for the folder picker: drives first, then one folder at a time. No file names."""
    try:
        return setup.folders(path)
    except ValueError as e:
        raise HTTPException(422, str(e))


class NewFolderBody(BaseModel):
    parent: str = Field(max_length=400)
    name: str = Field(max_length=120)


@router.post("/folders")
def make_folder(body: NewFolderBody) -> dict[str, Any]:
    try:
        return setup.new_folder(body.parent, body.name)
    except (ValueError, OSError) as e:
        raise HTTPException(422, str(e))


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
def get_plan(engines: str = "ollama,comfy", bundles: str = "pictures", models_dir: Optional[str] = None, install_dir: Optional[str] = None, gpu: Optional[int] = None,
             picture_model: Optional[str] = None, language_model: Optional[str] = None) -> list[dict[str, Any]]:
    names = [e for e in engines.split(",") if e]
    if any(e not in installers.INSTALLERS for e in names):
        raise HTTPException(404, "unknown engine in the plan")
    config=setup.state()
    if gpu is not None:config['gpu']=gpu
    for key,value in [('picture_model',picture_model),('language_model',language_model)]:
        if value:config[key]=value
    try:
        for key,value in [('models_dir',models_dir),('install_dir',install_dir)]:
            if value is not None:config[key]=setup.storage_path(value)
    except ValueError as e:raise HTTPException(422,str(e))
    return setup.plans(names, [b for b in bundles.split(",") if b],config)


@router.post("/install")
def install(body: InstallBody) -> dict[str, Any]:
    from .app import jobs

    if any(e not in installers.INSTALLERS for e in body.engines):
        raise HTTPException(404, "unknown engine")
    config = setup.state()
    if body.gpu is not None:config['gpu']=body.gpu
    for key in ('picture_model','language_model'):
        if getattr(body,key):config[key]=getattr(body,key)
    try:
        for key in ('models_dir','install_dir'):
            value=getattr(body,key)
            if value is not None:config[key]=setup.storage_path(value)
    except ValueError as e:raise HTTPException(422,str(e))
    try:setup.save(models_dir=config['models_dir'],install_dir=config['install_dir'],gpu=config.get('gpu'),picture_model=body.picture_model,language_model=body.language_model)
    except ValueError as e:raise HTTPException(422,str(e))
    problems = [p for plan in setup.plans(body.engines, body.bundles,config) for p in plan["problems"]]
    if problems:
        raise HTTPException(409, " ".join(problems))

    def work(cb):
        return setup.run_install(body.engines, body.bundles, lambda stage, f, m="": cb(stage, f, m),config)

    return jobs.submit("setup", None, "Setting up " + ", ".join(body.engines), work, when_busy="reuse").public()


@router.get("/test-picture")
def test_picture():
    """The picture the setup check drew (setup.try_it), shown in the wizard."""
    from fastapi.responses import FileResponse

    p = setup.test_picture_path()
    if not p.exists():
        raise HTTPException(404, "No test picture yet.")
    return FileResponse(p, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/try/{engine_id}")
def try_engine(engine_id: str) -> dict[str, Any]:
    try:
        return setup.try_it(engine_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
