"""Engines: the services the app uses (language AI, pictures and clips, voices, recognition), each one local, remote or off.

model.py     the shapes: EngineSpec, Endpoint, Health
store.py     reads and writes the engines block of settings.json, migrates the old ollama_url / comfy_url, keeps keys private
specs.py     the known engines and how to ask each one how it is (health, models, capabilities)
registry.py  the list, one health check per engine (cached for a few seconds), and `resolve(capability)`

A module asks for a capability ("voice.speak"); the registry names the engine that answers it. See docs/plans/PLAN-ENGINES-AND-SETUP.MD.
"""
from .model import Endpoint, EngineSpec, Health
from .registry import engines, health, resolve, spec

__all__ = ["Endpoint", "EngineSpec", "Health", "engines", "health", "resolve", "spec"]
