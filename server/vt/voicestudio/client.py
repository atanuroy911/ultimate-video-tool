from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Optional

import httpx

CONNECT_TIMEOUT = 6.0
SPEAK_TIMEOUT = 900.0                 # the first request after a restart loads the model


class VoiceStudioError(RuntimeError):
    """Something the person should be told in words. `kind`: unreachable | auth | licence | missing | failed."""

    def __init__(self, message: str, *, kind: str = "failed", detail: Any = None):
        super().__init__(message)
        self.kind, self.detail = kind, detail


def _plain(r: httpx.Response) -> tuple[str, str]:
    try:
        body = r.json()
    except ValueError:
        return f"VoiceStudio answered HTTP {r.status_code}", "failed"
    err = body.get("error") if isinstance(body, dict) else None
    detail = body.get("detail") if isinstance(body, dict) else None
    code = (err or {}).get("code") or (detail.get("code") if isinstance(detail, dict) else "") or ""
    msg = (err or {}).get("message") or (detail.get("message") if isinstance(detail, dict) else detail if isinstance(detail, str) else "") or f"HTTP {r.status_code}"
    if code == "model_licence_required":
        return str(msg), "licence"
    if r.status_code in (401, 403) or "API key" in str(msg):
        return "VoiceStudio needs its API key: add it in Settings, Engines.", "auth"
    return str(msg)[:300], "failed"


class VoiceStudioClient:
    def __init__(self, url: str, key: str = ""):
        self.url = url.rstrip("/")
        self.key = key
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        self._http = httpx.Client(base_url=self.url, headers=headers, timeout=httpx.Timeout(60, connect=CONNECT_TIMEOUT), follow_redirects=True)

    def close(self) -> None:
        self._http.close()

    def _call(self, method: str, path: str, *, timeout: Optional[float] = None, **kw) -> httpx.Response:
        try:
            r = self._http.request(method, path, timeout=timeout or 60, **kw)
        except httpx.HTTPError as e:
            raise VoiceStudioError(f"VoiceStudio at {self.url} does not answer ({type(e).__name__}).", kind="unreachable") from e
        if r.status_code >= 400:
            msg, kind = _plain(r)
            raise VoiceStudioError(msg, kind=kind, detail=r.text[:500])
        return r

    # ------------------------------------------------------------------ state
    def health(self) -> dict:
        return {"status": self._call("GET", "/health", timeout=CONNECT_TIMEOUT + 4).status_code}

    def tts_engines(self) -> dict:
        return self._call("GET", "/engines/tts").json()

    def models(self) -> list[dict]:
        return self._call("GET", "/models").json().get("models", [])

    def install_model(self, repo_id: str) -> dict:
        return self._call("POST", "/models/install", json={"repo_id": repo_id}).json()

    def profiles(self) -> list[dict]:
        data = self._call("GET", "/profiles").json()
        return data if isinstance(data, list) else data.get("profiles", [])

    # ------------------------------------------------------------------ speech
    def speak(self, text: str, *, engine: Optional[str] = None, profile_id: Optional[str] = None, preset_voice: Optional[str] = None,
              language: Optional[str] = None, speed: float = 1.0, duration: Optional[float] = None, seed: Optional[int] = None) -> bytes:
        """One sentence as WAV bytes. `duration` (seconds) asks the engine to land on that length when it supports it."""
        form: dict[str, Any] = {"text": text, "speed": str(speed)}
        for k, v in (("engine", engine), ("profile_id", profile_id), ("preset_voice", preset_voice), ("language", language), ("duration", duration), ("seed", seed)):
            if v not in (None, ""):
                form[k] = str(v)
        r = self._call("POST", "/generate", timeout=SPEAK_TIMEOUT, data=form)
        if r.content[:4] != b"RIFF":
            raise VoiceStudioError("VoiceStudio did not return sound: " + r.text[:200])
        return r.content

    def transcribe(self, audio: Path, language: Optional[str] = None) -> dict:
        mime = mimetypes.guess_type(str(audio))[0] or "audio/wav"
        with Path(audio).open("rb") as f:
            data = {"language": language} if language else {}
            return self._call("POST", "/v1/audio/transcriptions", timeout=SPEAK_TIMEOUT, files={"file": (Path(audio).name, f, mime)}, data=data).json()

    def clone(self, name: str, audio: Path, ref_text: str = "", language: str = "") -> dict:
        """A voice profile from a short recording of the speaker (with their consent). Returns the new profile."""
        with Path(audio).open("rb") as f:
            return self._call("POST", "/profiles", timeout=300, files={"ref_audio": (Path(audio).name, f, "audio/wav")},
                              data={"name": name, "ref_text": ref_text, "language": language, "kind": "clone"}).json()

    def design(self, name: str, description: str, language: str = "") -> dict:
        return self._call("POST", "/profiles", timeout=120, data={"name": name, "instruct": description, "language": language, "kind": "design"}).json()


def client_for(engine_id: str = "voicestudio") -> VoiceStudioClient:
    """A client for the connected VoiceStudio, or a VoiceStudioError saying how to connect one."""
    from ..engines import registry

    ep = registry.endpoint(engine_id)
    if ep.mode == "off" or not ep.url:
        raise VoiceStudioError("VoiceStudio is not connected: add its address in Settings, Engines.", kind="unreachable")
    return VoiceStudioClient(ep.url, ep.key)
