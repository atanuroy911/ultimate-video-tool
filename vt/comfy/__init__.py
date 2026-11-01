"""Generated motion clips from a ComfyUI server: a still becomes a few seconds of silent B-roll in the project's media bin.

client.py     talks to ComfyUI's HTTP API (status, node catalogue, upload, queue, history, download)
workflows.py  loads a versioned API-format workflow, checks it against the live server, patches only the approved inputs
still.py      one picture from a prompt (the reels' stills), cached and with provenance
generate.py   the whole job: upload the still, run, wait, download, normalise to silent H.264, verify it decodes, add it to the bin
"""
from .client import ComfyClient, ComfyError
from .generate import generate_clip
from .still import generate_still
from .workflows import Workflow, list_workflows, load_workflow

__all__ = ["ComfyClient", "ComfyError", "Workflow", "generate_clip", "generate_still", "list_workflows", "load_workflow"]
