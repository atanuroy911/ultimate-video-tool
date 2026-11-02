"""One card, two programs: before the local AI answers, ComfyUI on the same computer lets go of the card when it is holding most of it
(the mirror of llm.release() before pictures). Seen 2026-11-01: ComfyUI held 8.8 GB of the 3060, so gemma4 ran 87 % on the processor."""
from pathlib import Path

R = Path(__file__).resolve().parents[2]


def sub(path, old, new):
    p = R / path
    s = p.read_text(encoding="utf-8")
    assert old in s, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


sub("vt/llm.py", '''def release(url: Optional[str] = None) -> list[str]:''', '''_ROOM = {"at": 0.0}
ROOM_GB = 6.0                                       # the language model and its context need about this much of the card


def make_room(url: Optional[str] = None) -> bool:
    """Before the local AI answers: when ComfyUI runs on the same computer and leaves less than ROOM_GB of the card free, ask it to unload
    (the next picture loads its model again, ~40 s from an SSD). At most once a minute. Returns True when it asked."""
    if time.time() - _ROOM["at"] < 60:
        return False
    _ROOM["at"] = time.time()
    host = urllib.parse.urlparse(url or settings()["ollama_url"]).hostname or ""
    comfy = str((read_json(paths.SETTINGS, {}) or {}).get("comfy_url") or "")
    chost = urllib.parse.urlparse(comfy).hostname or ""
    same = host == chost or (is_local(f"http://{host}") and is_local(f"http://{chost}"))
    if not comfy or not same:
        return False
    try:
        devs = [d for d in httpx.get(comfy.rstrip("/") + "/system_stats", timeout=3).json().get("devices", []) if d.get("type") == "cuda"]
        if devs and min(float(d.get("vram_free", 0)) for d in devs) / 1e9 < ROOM_GB:
            httpx.post(comfy.rstrip("/") + "/free", json={"unload_models": True, "free_memory": True}, timeout=10)
            return True
    except Exception:                                                   # noqa: BLE001
        pass
    return False


def release(url: Optional[str] = None) -> list[str]:''')
sub("vt/llm.py", '''        r = httpx.post(s["ollama_url"] + "/api/chat", json=body, timeout=timeout)''', '''        make_room(s["ollama_url"])                                     # one card: the pictures' models step aside while the AI reads
        r = httpx.post(s["ollama_url"] + "/api/chat", json=body, timeout=timeout)''')
sub("vt/ai/providers.py", '''            r = httpx.post(s["ollama_url"] + "/api/chat", json=body, timeout=timeout)''', '''            llm.make_room(s["ollama_url"])                             # one card: the pictures' models step aside while the AI reads
            r = httpx.post(s["ollama_url"] + "/api/chat", json=body, timeout=timeout)''')
print("ok")
