"""AI providers behind one call.

`complete_json(prompt, schema, images=None)` asks the selected provider for JSON that matches `schema`, validates it (JSON Schema, and a
Pydantic model if given), retries once with the exact error list, and raises AIUnavailable when nothing usable comes back so that callers
fall back to the rule engine. Answers are cached on disk by (provider, model, prompt, schema, images). The answer is untrusted data.

Settings (settings.json): ai_provider "auto" | "ollama" | "claude_cli" | "best" | "openai" | "anthropic" | "off"; openai_url, openai_key, openai_model;
anthropic_key, anthropic_model; claude_cli_path, claude_cli_model, claude_cli_daily_cap. "auto" = the local Ollama server (the existing `llm_mode` / `ollama_*` settings).
"claude_cli" = Claude through the installed, logged-in Claude Code program in its non-interactive mode (no API key); "best" = that when it is logged in, else the local model.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

import httpx
import jsonschema

from .. import llm, paths
from ..util import CREATE_NO_WINDOW, now_iso, read_json, write_json


class AIUnavailable(RuntimeError):
    """No provider could give a valid answer (the caller falls back to rules)."""


Image = bytes | Path | str


def _image_bytes(im: Image) -> bytes:
    return im if isinstance(im, bytes) else Path(im).read_bytes()


def _b64(im: Image) -> str:
    return base64.b64encode(_image_bytes(im)).decode("ascii")


def parse_json(text: str) -> Any:
    """JSON from a model reply, tolerating code fences and chatter around it."""
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        a, b = t.find("{"), t.rfind("}")
        if a >= 0 and b > a:
            return json.loads(t[a:b + 1])
        raise


# --------------------------------------------------------------------------- providers
class Provider:
    name = "base"
    cacheable = True
    supports_images = False

    def model(self) -> str:
        return ""

    def available(self) -> bool:
        return True

    def complete(self, system: str, prompt: str, schema: dict, images: Sequence[Image], max_tokens: int, timeout: float, temperature: float) -> str:
        raise NotImplementedError


class OllamaProvider(Provider):
    name = "ollama"
    supports_images = True

    def __init__(self, model: Optional[str] = None):
        self._model = model

    def model(self) -> str:
        return self._model or llm.model_name()

    def available(self) -> bool:
        return llm.settings()["llm_mode"] != "off" and llm.reachable()

    def complete(self, system, prompt, schema, images, max_tokens, timeout, temperature):
        s = llm.settings()
        if s["llm_mode"] == "off":
            raise AIUnavailable("The local AI is turned off in Settings.")
        user: dict[str, Any] = {"role": "user", "content": prompt}
        if images:
            user["images"] = [_b64(i) for i in images]
        msgs = ([{"role": "system", "content": system}] if system else []) + [user]
        body = {"model": self.model(), "messages": msgs, "stream": False, "think": False, "format": schema, "keep_alive": "10m",
                "options": {"temperature": temperature, "num_ctx": 16384, "num_predict": max_tokens}}
        try:
            llm.make_room(s["ollama_url"])                             # one card: the pictures' models step aside while the AI reads
            r = httpx.post(s["ollama_url"] + "/api/chat", json=body, timeout=timeout)
            r.raise_for_status()
            return r.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise AIUnavailable(f"The local AI did not answer ({type(e).__name__}: {str(e)[:120]}).") from e


class OpenAIProvider(Provider):
    """Any OpenAI-compatible chat endpoint (OpenAI, LM Studio, vLLM, OpenRouter, ...). Needs the user's key unless the server is local."""

    name = "openai"
    supports_images = True

    def __init__(self, url: str = "", key: str = "", model: str = ""):
        s = read_json(paths.SETTINGS, {}) or {}
        self.url = (url or s.get("openai_url") or "https://api.openai.com/v1").rstrip("/")
        self.key = key or s.get("openai_key") or ""
        self._model = model or s.get("openai_model") or "gpt-4o-mini"

    def model(self) -> str:
        return self._model

    def available(self) -> bool:
        return bool(self.key) or llm.is_local(self.url)

    def complete(self, system, prompt, schema, images, max_tokens, timeout, temperature):
        content: Any = prompt
        if images:
            content = [{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + _b64(i)}} for i in images]
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": content}]
        body = {"model": self._model, "messages": msgs,
                "response_format": {"type": "json_schema", "json_schema": {"name": "answer", "schema": schema}}}
        # Current OpenAI reasoning models reject max_tokens and non-default temperature.
        # Keep the older request shape for third-party OpenAI-compatible endpoints.
        modern_openai = self.url.startswith("https://api.openai.com/") and (
            self._model.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4"))
        )
        if modern_openai:
            body["max_completion_tokens"] = max_tokens
        else:
            body["max_tokens"] = max_tokens
            body["temperature"] = temperature
        try:
            r = httpx.post(self.url + "/chat/completions", json=body, timeout=timeout,
                           headers={"Authorization": f"Bearer {self.key}"} if self.key else {})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise AIUnavailable(f"The AI service did not answer ({type(e).__name__}: {str(e)[:120]}).") from e


class AnthropicProvider(Provider):
    """Claude through the Messages API with a forced tool call whose input schema is ours. Needs the user's key."""

    name = "anthropic"
    supports_images = True

    def __init__(self, key: str = "", model: str = ""):
        s = read_json(paths.SETTINGS, {}) or {}
        self.key = key or s.get("anthropic_key") or ""
        self._model = model or s.get("anthropic_model") or "claude-sonnet-5-5"

    def model(self) -> str:
        return self._model

    def available(self) -> bool:
        return bool(self.key)

    def complete(self, system, prompt, schema, images, max_tokens, timeout, temperature):
        content: Any = prompt
        if images:
            content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _b64(i)}} for i in images] + [{"type": "text", "text": prompt}]
        body = {"model": self._model, "max_tokens": max_tokens, "temperature": temperature, "system": system or "Answer with the tool.",
                "messages": [{"role": "user", "content": content}],
                "tools": [{"name": "answer", "description": "Return the answer.", "input_schema": schema}],
                "tool_choice": {"type": "tool", "name": "answer"}}
        try:
            r = httpx.post("https://api.anthropic.com/v1/messages", json=body, timeout=timeout,
                           headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"})
            r.raise_for_status()
            for blk in r.json()["content"]:
                if blk.get("type") == "tool_use":
                    return json.dumps(blk["input"])
            raise KeyError("no tool_use block")
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise AIUnavailable(f"Claude did not answer ({type(e).__name__}: {str(e)[:120]}).") from e


# --------------------------------------------------------------------------- Claude through the logged-in Claude Code program
_cli_lock = threading.Lock()                       # one call at a time: a person's plan has usage limits, and the answers are cached anyway
_login_cache: dict = {"t": 0.0, "v": None}
CLI_SCHEMA_ARG_MAX = 6000                          # a longer schema goes into the prompt: a Windows command line is limited to about 32,000 characters


def find_claude() -> Optional[str]:
    """The `claude` program: the path in Settings, PATH, or the places the installers put it."""
    s_ = read_json(paths.SETTINGS, {}) or {}
    cands = [s_.get("claude_cli_path"), shutil.which("claude"), shutil.which("claude.exe")]
    home = Path.home()
    for rel in (".local/bin/claude.exe", ".local/bin/claude", "AppData/Roaming/npm/claude.cmd", ".claude/local/claude", "/usr/local/bin/claude"):
        cands.append(str(home / rel) if not rel.startswith("/") else rel)
    for c in cands:
        if c and Path(c).exists():
            return str(c)
    return None


def _cli_env() -> dict:
    """The program's own login is used: an API key left in the environment would silently switch it to per-token billing."""
    return {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX")}


def login_status(force: bool = False) -> dict:
    """{found, logged_in, plan, method, reason}; cached for a minute. The account's e-mail and ids are never kept."""
    now = time.time()
    if not force and _login_cache["v"] is not None and now - _login_cache["t"] < 60:
        return _login_cache["v"]
    exe = find_claude()
    if not exe:
        v = {"found": False, "logged_in": False, "plan": "", "method": "", "reason": "Claude Code is not installed. Install it from claude.com/claude-code, then run `claude auth login` once."}
    else:
        try:
            r = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, encoding="utf-8", timeout=30, cwd=tempfile.gettempdir(), env=_cli_env(), creationflags=CREATE_NO_WINDOW)
            d = json.loads(r.stdout or "{}")
            ok = bool(d.get("loggedIn"))
            v = {"found": True, "logged_in": ok, "plan": str(d.get("subscriptionType") or ""), "method": str(d.get("authMethod") or ""),
                 "reason": "" if ok else "Claude Code is not logged in. Run `claude auth login` in a terminal once."}
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            v = {"found": True, "logged_in": False, "plan": "", "method": "", "reason": f"Claude Code did not answer ({type(e).__name__})."}
    _login_cache.update(t=now, v=v)
    return v


def usage_path() -> Path:
    return paths.DATA / "claude_usage.json"


def usage_today() -> dict:
    d = read_json(usage_path(), {}) or {}
    return d.get(time.strftime("%Y-%m-%d"), {"calls": 0, "cost_usd": 0.0, "seconds": 0.0})


def _record_usage(cost: float, seconds: float) -> None:
    d = read_json(usage_path(), {}) or {}
    day = time.strftime("%Y-%m-%d")
    cur = d.get(day, {"calls": 0, "cost_usd": 0.0, "seconds": 0.0})
    cur = {"calls": cur["calls"] + 1, "cost_usd": round(cur["cost_usd"] + cost, 4), "seconds": round(cur["seconds"] + seconds, 1)}
    d = {k: v for k, v in sorted(d.items())[-30:] if k != day}
    d[day] = cur
    try:
        write_json(usage_path(), d)
    except OSError:
        pass


class ClaudeCLIProvider(Provider):
    """Claude through the person's own logged-in Claude Code (`claude -p`, its non-interactive mode): no API key, the answer is checked against our schema like every provider's.
    Runs in an empty temporary folder with every tool, skill and MCP server switched off, so it can only answer: it cannot read the project or touch a file."""

    name = "claude-cli"
    supports_images = False

    def __init__(self, model: str = ""):
        s_ = read_json(paths.SETTINGS, {}) or {}
        self._model = model or s_.get("claude_cli_model") or "sonnet"

    def model(self) -> str:
        return self._model

    def available(self) -> bool:
        st = login_status()
        return st["found"] and st["logged_in"]

    def command(self, system_file: Path, schema: dict) -> tuple[list[str], bool]:
        """(argument list without the program, whether the schema is inside the prompt)."""
        args = ["-p", "--output-format", "json", "--no-session-persistence", "--tools", "", "--disable-slash-commands", "--strict-mcp-config",
                "--model", self._model, "--system-prompt-file", str(system_file)]
        sj = json.dumps(schema)
        if len(sj) <= CLI_SCHEMA_ARG_MAX:
            return args + ["--json-schema", sj], False
        return args, True

    def complete(self, system, prompt, schema, images, max_tokens, timeout, temperature):
        exe = find_claude()
        st = login_status()
        if not exe or not st["logged_in"]:
            raise AIUnavailable(st["reason"] or "Claude Code is not available.")
        cap = int((read_json(paths.SETTINGS, {}) or {}).get("claude_cli_daily_cap") or 200)
        if usage_today()["calls"] >= cap:
            raise AIUnavailable(f"The daily limit of {cap} Claude calls is reached (Settings > AI assistants). It resets tomorrow.")
        tmp = Path(tempfile.mkdtemp(prefix="vt_claude_"))
        try:
            sysf = tmp / "system.txt"
            sysf.write_text(system or "You answer only with the requested JSON, no other text.", encoding="utf-8")
            args, inline = self.command(sysf, schema)
            stdin = prompt + (("\n\nAnswer with ONE JSON object only (no prose, no code fence) that matches this JSON Schema:\n" + json.dumps(schema)) if inline else "")
            t0 = time.time()
            with _cli_lock:
                r = subprocess.run([exe, *args], input=stdin, capture_output=True, text=True, encoding="utf-8", timeout=timeout, cwd=str(tmp), env=_cli_env(), creationflags=CREATE_NO_WINDOW)
            took = time.time() - t0
            try:
                d = json.loads(r.stdout)
            except ValueError:
                raise AIUnavailable(f"Claude Code gave no JSON answer (exit {r.returncode}): {(r.stderr or r.stdout)[:160]}")
            _record_usage(float(d.get("total_cost_usd") or 0.0), took)
            if d.get("is_error"):
                raise AIUnavailable(f"Claude said: {str(d.get('result') or d.get('subtype') or 'error')[:200]}")
            so = d.get("structured_output")
            if so is not None:
                return json.dumps(so)
            return str(d.get("result") or "")
        except subprocess.TimeoutExpired as e:
            raise AIUnavailable(f"Claude did not answer within {int(timeout)} s.") from e
        except OSError as e:
            raise AIUnavailable(f"Claude Code could not be started ({type(e).__name__}).") from e
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class FakeProvider(Provider):
    """Deterministic provider for tests: `responses` is a list of replies (dict/str/Exception), or a function (system, prompt, schema, images)."""

    name = "fake"
    cacheable = False
    supports_images = True

    def __init__(self, responses: Any = None):
        self.responses = responses
        self.calls: list[dict] = []

    def model(self) -> str:
        return "fake"

    def complete(self, system, prompt, schema, images, max_tokens, timeout, temperature):
        self.calls.append({"system": system, "prompt": prompt, "schema": schema, "images": list(images)})
        r = self.responses(system, prompt, schema, images) if callable(self.responses) else (
            self.responses.pop(0) if self.responses else AIUnavailable("fake provider has no more replies"))
        if isinstance(r, BaseException):
            raise r
        return r if isinstance(r, str) else json.dumps(r)


# --------------------------------------------------------------------------- selection
_override: list[Provider] = []
_lock = threading.Lock()


def current_provider() -> Provider:
    if _override:
        return _override[-1]
    choice = (read_json(paths.SETTINGS, {}) or {}).get("ai_provider", "auto")
    if choice == "off":
        raise AIUnavailable("AI is turned off in Settings.")
    if choice == "openai":
        return OpenAIProvider()
    if choice == "anthropic":
        return AnthropicProvider()
    if choice == "claude_cli":
        return ClaudeCLIProvider()
    if choice == "best":                                         # Claude through the person's login when it is logged in, else the local model
        c = ClaudeCLIProvider()
        return c if c.available() else OllamaProvider()
    return OllamaProvider()


@contextmanager
def use_provider(p: Provider):
    """Force a provider inside the block (tests, one-off jobs)."""
    with _lock:
        _override.append(p)
    try:
        yield p
    finally:
        with _lock:
            _override.remove(p)


def ai_enabled() -> bool:
    """Is any AI meant to be used? (The chosen provider is not "off"; for the local model, the local AI is not turned off.)"""
    try:
        p = current_provider()
    except AIUnavailable:
        return False
    return llm.settings()["llm_mode"] != "off" if isinstance(p, OllamaProvider) else True


def ensure_ai(progress: Optional[Callable[[str, float, str], None]] = None) -> Provider:
    """The one gate every pipeline stage goes through before asking an AI: the chosen provider, made ready. Only the local model is
    started or installed (Ollama); Claude (login or key) and OpenAI-compatible servers are only checked. Raises AIUnavailable."""
    p = current_provider()
    if isinstance(p, OllamaProvider):
        if llm.settings()["llm_mode"] == "off":
            raise AIUnavailable("The local AI is turned off in Settings.")
        try:
            llm.ensure_ready(progress or (lambda *a: None))
        except Exception as e:
            raise AIUnavailable(str(e)) from e
    elif not p.available():
        raise AIUnavailable(f"{p.name} is not ready. See Settings > AI.")
    return p


def fingerprint() -> str:
    """Which brain would answer now, for stage hashes: a different provider or model re-runs the AI stages."""
    try:
        p = current_provider()
        return f"{p.name}:{p.model()}" if ai_enabled() else "off"
    except AIUnavailable:
        return "off"


def provider_status() -> dict:
    try:
        p = current_provider()
        return {"provider": p.name, "model": p.model(), "available": p.available(), "images": p.supports_images}
    except AIUnavailable as e:
        return {"provider": "off", "model": "", "available": False, "images": False, "reason": str(e)}


# --------------------------------------------------------------------------- the call
def _cache_dir() -> Path:
    return paths.DATA / "ai_cache"


def _key(p: Provider, system: str, prompt: str, schema: dict, images: Sequence[Image], temperature: float) -> str:
    h = hashlib.sha256()
    for part in (p.name, p.model(), system, prompt, json.dumps(schema, sort_keys=True), f"{temperature:.2f}"):
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    for im in images:
        h.update(hashlib.sha256(_image_bytes(im)).digest())
    return h.hexdigest()[:40]


def validate(data: Any, schema: dict, model_cls: Any = None) -> list[str]:
    """Plain-language problems with `data` (empty = fine)."""
    errs = [f"{'/'.join(str(x) for x in e.absolute_path) or 'answer'}: {e.message[:160]}"
            for e in sorted(jsonschema.Draft202012Validator(schema).iter_errors(data), key=lambda e: list(map(str, e.absolute_path)))][:8]
    if not errs and model_cls is not None:
        try:
            model_cls.model_validate(data)
        except Exception as e:
            errs = [str(e)[:400]]
    return errs


def complete_json(prompt: str, schema: dict, images: Optional[Sequence[Image]] = None, *, system: str = "", model_cls: Any = None,
                  provider: Optional[Provider] = None, retries: int = 1, cache: bool = True, max_tokens: int = 4096, timeout: float = 300,
                  temperature: float = 0.2, repair: Optional[Callable[[Any], Any]] = None, check: Optional[Callable[[Any], list[str]]] = None) -> dict:
    """Ask for JSON matching `schema`. `repair` may fix common mistakes in the parsed reply before validation.
    `check` returns extra (semantic) problems after the schema passes.
    Raises AIUnavailable if no valid answer arrives after `retries` extra tries (each retry shows the model its errors)."""
    p = provider or current_provider()
    images = list(images or [])
    if images and not p.supports_images:
        raise AIUnavailable(f"{p.name} cannot look at pictures.")
    ck = _key(p, system, prompt, schema, images, temperature) if cache and p.cacheable else None
    cf = _cache_dir() / f"{ck}.json" if ck else None
    if cf is not None and cf.exists():
        try:
            return json.loads(cf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    ask, last = prompt, ""
    for attempt in range(retries + 1):
        raw = p.complete(system, ask, schema, images, max_tokens, timeout, temperature)
        try:
            data = parse_json(raw)
            if repair is not None:
                data = repair(data)
            errs = validate(data, schema, model_cls)
            if not errs and check is not None:
                errs = check(data)[:10]
        except (ValueError, TypeError) as e:
            data, errs = None, [f"the reply was not valid JSON ({str(e)[:100]})"]
        if not errs:
            if cf is not None:
                try:
                    write_json(cf, data)
                except OSError:
                    pass
            return data
        last = "; ".join(errs)
        ask = (f"{prompt}\n\nYour previous answer had these problems, fix exactly them and answer again with the complete JSON:\n- " + "\n- ".join(errs))
    raise AIUnavailable(f"{p.name} gave no valid answer: {last[:300]}")


_VISION_PREFER = [r"llama3\.2-vision", r"qwen2\.5vl:7b", r"qwen2\.5vl", r"gemma[34].*(vision|it)?",     # llama3.2-vision first: best at our frame checks (scripts/eval_vision.py, 2026-10-24)
                   r"minicpm-v", r"llava", r"moondream", r"smolvlm"]


def vision_provider() -> Provider:
    """A provider that can look at pictures: the chosen cloud provider, else a vision model on the Ollama server (setting ollama_vision_model, or the best installed)."""
    if _override:
        return _override[-1]
    s = read_json(paths.SETTINGS, {}) or {}
    choice = s.get("ai_provider", "auto")
    if choice == "off":
        raise AIUnavailable("AI is turned off in Settings.")
    if choice == "openai":
        return OpenAIProvider()
    if choice == "anthropic":
        return AnthropicProvider()
    chosen = s.get("ollama_vision_model") or ""
    if not chosen and llm.settings()["llm_mode"] != "off":
        have = llm.installed_models()
        vis = [m for m in have if re.search(r"(vl|vision|llava|moondream|smolvlm|minicpm-v|gemma[34])", m, re.I) and "embed" not in m]
        for pat in _VISION_PREFER:
            hit = next((m for m in vis if re.search(pat, m, re.I)), None)
            if hit:
                chosen = hit
                break
    return OllamaProvider(chosen or None)
