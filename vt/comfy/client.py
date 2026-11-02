"""ComfyUI's HTTP API, nothing more: the routes documented at docs.comfy.org/development/comfyui-server/comms_routes.

The browser never talks to ComfyUI; only the Video Tool backend does. Every method raises ComfyError with a plain-words message
(server not reachable, the graph was rejected and why, the run failed on node X with this error) so the Studio can show it.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

CONNECT_TIMEOUT = 6.0
REQUEST_TIMEOUT = 30.0
POLL_SECONDS = 1.5
MAX_DOWNLOAD_BYTES = 400 * 1024 * 1024


class ComfyError(RuntimeError):
    """Anything that stops a clip: unreachable server, rejected graph, failed run, timeout, cancel."""

    def __init__(self, message: str, *, kind: str = "error", detail: Any = None):
        super().__init__(message)
        self.kind = kind            # unreachable | rejected | failed | timeout | cancelled | error
        self.detail = detail


class ComfyClient:
    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self._http = httpx.Client(base_url=self.url, timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT))

    def close(self) -> None:
        self._http.close()

    def _call(self, method: str, path: str, **kw) -> httpx.Response:
        try:
            return self._http.request(method, path, **kw)
        except httpx.TimeoutException as e:
            raise ComfyError(f"ComfyUI at {self.url} did not answer in time.", kind="unreachable") from e
        except httpx.HTTPError as e:
            raise ComfyError(f"ComfyUI at {self.url} is not reachable ({type(e).__name__}).", kind="unreachable") from e

    # ------------------------------------------------------------------ what the server is and has
    def system_stats(self) -> dict:
        r = self._call("GET", "/system_stats")
        if r.status_code != 200:
            raise ComfyError(f"ComfyUI answered HTTP {r.status_code} to /system_stats.", kind="unreachable")
        return r.json()

    def object_info(self, node_class: Optional[str] = None) -> dict:
        r = self._call("GET", f"/object_info/{node_class}" if node_class else "/object_info", timeout=120)
        if r.status_code != 200:
            raise ComfyError(f"ComfyUI answered HTTP {r.status_code} to /object_info.", kind="error")
        return r.json()

    def free_memory(self) -> None:
        """Ask ComfyUI to unload its cached models and free GPU memory (best effort): the next run starts from a known state."""
        try:
            self._call("POST", "/free", json={"unload_models": True, "free_memory": True})
        except ComfyError:
            pass

    def relieve_memory(self, min_free_gb: float = 10.0) -> bool:
        """Unload ComfyUI's cached models when the server's own RAM runs low. A model too big for the card is parked in system RAM between
        runs; on a 30 GB machine that left 3 GB free and the box swapped until it fell over (the owner's GPU server, 2026-11-01).
        Reloading costs seconds; a crash costs the whole video. Returns True when it asked for memory back."""
        try:
            ram_free = float(self.system_stats().get("system", {}).get("ram_free", 0)) / 1e9
        except (ComfyError, ValueError, TypeError):
            return False
        if 0 < ram_free < min_free_gb:
            self.free_memory()
            return True
        return False

    def queue(self) -> dict:
        return self._call("GET", "/queue").json()

    def status(self) -> dict:
        """What Settings shows: reachable?, version, GPUs and free memory, queue length. Never raises."""
        try:
            stats = self.system_stats()
            queue = self.queue()
        except ComfyError as e:
            return {"ok": False, "url": self.url, "error": str(e)}
        devices = [{"name": d.get("name"), "vram_total": d.get("vram_total"), "vram_free": d.get("vram_free"), "type": d.get("type")} for d in stats.get("devices", [])]
        return {"ok": True, "url": self.url, "version": stats.get("system", {}).get("comfyui_version"), "devices": devices,
                "queue_running": len(queue.get("queue_running", [])), "queue_pending": len(queue.get("queue_pending", []))}

    # ------------------------------------------------------------------ running a graph
    def upload_image(self, path: Path, name: str, overwrite: bool = True) -> str:
        """Put a still into ComfyUI's input folder; returns the filename a LoadImage node must name."""
        with Path(path).open("rb") as f:
            r = self._call("POST", "/upload/image", files={"image": (name, f, "image/png")}, data={"overwrite": "true" if overwrite else "false", "type": "input"}, timeout=120)
        if r.status_code != 200:
            raise ComfyError(f"ComfyUI refused the picture (HTTP {r.status_code}).", kind="rejected", detail=r.text[:300])
        return r.json().get("name", name)

    def upload_file(self, path: Path, name: str, mime: str = "application/octet-stream", overwrite: bool = True) -> str:
        """Put any file (a reference recording) into ComfyUI's input folder; returns the filename a LoadAudio node must name."""
        with Path(path).open("rb") as f:
            r = self._call("POST", "/upload/image", files={"image": (name, f, mime)}, data={"overwrite": "true" if overwrite else "false", "type": "input"}, timeout=120)
        if r.status_code != 200:
            raise ComfyError(f"ComfyUI refused the file (HTTP {r.status_code}).", kind="rejected", detail=r.text[:300])
        return r.json().get("name", name)

    def submit(self, prompt: dict, client_id: str = "video-tool") -> str:
        """Queue an API-format graph. A graph ComfyUI refuses comes back as ComfyError(kind="rejected") naming the nodes and fields."""
        r = self._call("POST", "/prompt", json={"prompt": prompt, "client_id": client_id})
        if r.status_code == 200:
            return r.json()["prompt_id"]
        try:
            body = r.json()
        except ValueError:
            raise ComfyError(f"ComfyUI answered HTTP {r.status_code}: {r.text[:200]}", kind="rejected")
        raise ComfyError(describe_rejection(body), kind="rejected", detail=body)

    def history(self, prompt_id: str) -> Optional[dict]:
        r = self._call("GET", f"/history/{prompt_id}")
        if r.status_code != 200:
            return None
        return (r.json() or {}).get(prompt_id)

    def interrupt(self, prompt_id: Optional[str] = None) -> None:
        """Stop our run. If it is the one running, interrupt the server; if it is only waiting, take it out of the queue (never kill someone else's run)."""
        if prompt_id is None:
            self._call("POST", "/interrupt")
            return
        queue = self.queue()
        if prompt_id in [item[1] for item in queue.get("queue_running", [])]:
            self._call("POST", "/interrupt")
        else:
            self._call("POST", "/queue", json={"delete": [prompt_id]})

    def wait(self, prompt_id: str, on_progress: Optional[Callable[[float, str], None]] = None, cancelled: Callable[[], bool] = lambda: False,
             timeout: float = 3600.0) -> dict:
        """Poll until the run is finished; returns its history entry. Raises ComfyError for a failed run, a timeout or a cancel."""
        started = time.time()
        while True:
            if cancelled():
                self.interrupt(prompt_id)
                raise ComfyError("Cancelled.", kind="cancelled")
            entry = self.history(prompt_id)
            if entry:
                status = entry.get("status", {})
                if any(m[0] == "execution_interrupted" for m in status.get("messages", [])):
                    raise ComfyError("The run was stopped on the ComfyUI server before it finished.", kind="cancelled", detail=status)
                if status.get("status_str") == "error" or any(m[0] == "execution_error" for m in status.get("messages", [])):
                    raise ComfyError(describe_failure(entry), kind="failed", detail=status)
                if status.get("completed") or entry.get("outputs"):
                    return entry
            if time.time() - started > timeout:
                self.interrupt(prompt_id)
                raise ComfyError(f"The clip was not finished after {int(timeout / 60)} minutes.", kind="timeout")
            if on_progress:
                queue = self.queue()
                running = [item[1] for item in queue.get("queue_running", [])]
                pending = [item[1] for item in queue.get("queue_pending", [])]
                if prompt_id in running:
                    on_progress(0.0, "Generating")
                elif prompt_id in pending:
                    on_progress(0.0, f"Waiting in ComfyUI's queue ({pending.index(prompt_id) + 1} ahead)")
            time.sleep(POLL_SECONDS)

    def download(self, filename: str, subfolder: str, kind: str, dest: Path) -> Path:
        """Fetch one output file to `dest`, refusing anything over MAX_DOWNLOAD_BYTES."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        try:
            with self._http.stream("GET", "/view", params={"filename": filename, "subfolder": subfolder, "type": kind}, timeout=httpx.Timeout(300, connect=CONNECT_TIMEOUT)) as r:
                if r.status_code != 200:
                    raise ComfyError(f"ComfyUI could not give back {filename} (HTTP {r.status_code}).", kind="error")
                with dest.open("wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        total += len(chunk)
                        if total > MAX_DOWNLOAD_BYTES:
                            raise ComfyError("The generated file is larger than 400 MB.", kind="error")
                        f.write(chunk)
        except httpx.HTTPError as e:
            raise ComfyError(f"The download from ComfyUI failed ({type(e).__name__}).", kind="unreachable") from e
        except ComfyError:
            dest.unlink(missing_ok=True)
            raise
        return dest


def output_files(entry: dict, node_id: Optional[str] = None) -> list[dict]:
    """The files a finished run produced: [{filename, subfolder, type}], from the named node or from any node (videos, gifs or images)."""
    found = []
    for nid, out in (entry.get("outputs") or {}).items():
        if node_id is not None and nid != str(node_id):
            continue
        for key in ("videos", "gifs", "images", "audio"):
            for item in out.get(key, []) or []:
                if isinstance(item, dict) and item.get("filename"):
                    found.append({"filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": item.get("type", "output")})
    return found


def describe_rejection(body: dict) -> str:
    """ComfyUI's 400 body → a sentence: which node and which input it did not accept."""
    parts = []
    err = body.get("error") or {}
    if err.get("message"):
        parts.append(str(err["message"]))
    for nid, node in (body.get("node_errors") or {}).items():
        for e in node.get("errors", []):
            extra = (e.get("extra_info") or {}).get("input_name")
            parts.append(f"node {nid} ({node.get('class_type', '?')}): {e.get('message', 'invalid')}{f' [{extra}]' if extra else ''}: {str(e.get('details', ''))[:120]}")
    return "ComfyUI rejected the workflow: " + ("; ".join(parts) if parts else json.dumps(body)[:300])


def describe_failure(entry: dict) -> str:
    """A failed run → a sentence: the node, the exception, and a hint for the common causes."""
    for msg in entry.get("status", {}).get("messages", []):
        if msg[0] == "execution_error":
            data = msg[1]
            text = f"{data.get('node_type', 'a node')} (node {data.get('node_id')}) failed: {data.get('exception_type', '')}: {str(data.get('exception_message', '')).strip()[:300]}"
            lower = text.lower()
            if "out of memory" in lower or "oom" in lower:
                text += " The GPU ran out of memory: try a smaller size or fewer frames."
            elif "no kernel image" in lower:
                text += " This PyTorch build has no kernels for the server's GPU (a V100 needs a build that includes sm_70)."
            return text
    return "The run failed in ComfyUI (see the server log)."
