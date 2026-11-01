"""Make a video from a link: download the audio (and the subtitles, when the page has them) with yt-dlp.

Works for YouTube and the other sites yt-dlp understands, and for direct links to audio files. Only use material you have the right to reuse
(your own, Creative Commons, public domain): the project remembers where it came from and the export's credits file names the source.

The subtitles are optional but valuable: when they exist the words and their timing come from them (no speech recognition needed, and the text
is what the author wrote). Auto-generated YouTube captions carry word timings; ordinary captions are cue-level, so their words are spread over
each cue and later snapped to the real speech by the normal pipeline.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

MAX_MINUTES = 60
MAX_BYTES = 250 * 1024 * 1024
LANG_FALLBACK = {"bn": ["bn", "bn-BD", "bn-IN"], "en": ["en", "en-US", "en-GB", "en-orig"]}


class IngestError(RuntimeError):
    """Something the user can act on (bad link, private video, too long). The message is shown as is."""


def check_url(url: str) -> str:
    """Only public http(s) addresses: no local files, no addresses inside the user's own network."""
    url = (url or "").strip()
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise IngestError("Paste a full link that starts with http:// or https://")
    host = u.hostname
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise IngestError("That address could not be found. Check the link and the internet connection.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise IngestError("Links to this computer or to your own network are not allowed.")
    return url


class _Quiet:
    """yt-dlp prints its own errors; ours are translated for people, so its logger is silenced."""
    def debug(self, m): pass
    def info(self, m): pass
    def warning(self, m): pass
    def error(self, m): pass


def _opts(dest: Path, langs: list[str], want_subs: bool, hook: Optional[Callable[[dict], None]], want_video: bool = False) -> dict:
    from .util import find_tool

    o: dict[str, Any] = {
        "format": (
            "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
            if want_video else
            "bestaudio[filesize<250M]/bestaudio/best"
        ),
        "outtmpl": str(dest / "src.%(ext)s"),
        "noplaylist": True, "quiet": True, "logger": _Quiet(), "no_warnings": True, "noprogress": True,
        "socket_timeout": 20, "retries": 3, "max_filesize": MAX_BYTES,
        "match_filter": _too_long,
        "restrictfilenames": True, "windowsfilenames": True,
        "ffmpeg_location": str(Path(find_tool("ffmpeg")).parent),
    }
    if want_video:
        o["merge_output_format"] = "mp4"
    try:
        node = find_tool("node")
    except RuntimeError:
        node = None
    if node:                                                # recent YouTube needs a JavaScript runtime to unlock every audio format
        o["js_runtimes"] = {"node": {"path": node}}
    if want_subs:
        o.update({"writesubtitles": True, "writeautomaticsub": True, "subtitleslangs": langs, "subtitlesformat": "json3/vtt/best"})
    if hook:
        o["progress_hooks"] = [hook]
    return o


def _too_long(info: dict, *, incomplete: bool = False) -> Optional[str]:
    d = info.get("duration")
    if d and d > MAX_MINUTES * 60:
        return f"The video is {d / 60:.0f} minutes long; the limit is {MAX_MINUTES} minutes. Paste a shorter one."
    if info.get("is_live"):
        return "Live streams cannot be imported."
    return None


def _friendly(e: Exception) -> IngestError:
    m = re.sub(r"\x1b\[[0-9;]*m", "", str(e))
    low = m.lower()
    if "private video" in low or "sign in" in low or "login" in low:
        return IngestError("This video is private or needs a sign-in, so it cannot be downloaded.")
    if "unsupported url" in low:
        return IngestError("This kind of link is not supported. Use a YouTube link or a direct link to an audio or video file.")
    if "http error 404" in low or "http error 410" in low:
        return IngestError("Nothing was found at this address (404). Check the link.")
    if "http error 403" in low or "http error 401" in low:
        return IngestError("The site refused the download (it may need a sign-in).")
    if "video unavailable" in low or "not available" in low or "removed" in low:
        return IngestError("This video is not available (removed, blocked in your country or private).")
    if "too long" in low or "minutes long" in low:
        return IngestError(m.split("ERROR:")[-1].strip())
    if "urlopen" in low or "getaddrinfo" in low or "timed out" in low or "network" in low:
        return IngestError("The download could not be completed. Check the internet connection and try again.")
    return IngestError("The download failed: " + m.split("ERROR:")[-1].strip()[:240])


def fetch(url: str, dest: Path, *, language: str = "en", want_subs: bool = True, want_video: bool = False, progress: Optional[Callable[[float, str], None]] = None) -> dict:
    """Download into `dest`. Returns {audio: Path, video: Path|None, title, uploader, duration, license, url, subs: Path|None, subs_lang}."""
    import yt_dlp

    url = check_url(url)
    dest.mkdir(parents=True, exist_ok=True)
    langs = LANG_FALLBACK.get(language, [language]) + ([] if language == "en" else [])

    def hook(d: dict) -> None:
        if progress and d.get("status") == "downloading":
            tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            label = "Downloading video footage" if want_video else "Downloading the audio"
            progress(min(0.99, d.get("downloaded_bytes", 0) / tot) if tot else 0.0, label)

    try:
        with yt_dlp.YoutubeDL(_opts(dest, langs, want_subs, hook, want_video=want_video)) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        # a missing subtitle track must never fail the whole import
        if want_subs and "subtitle" in str(e).lower():
            return fetch(url, dest, language=language, want_subs=False, want_video=want_video, progress=progress)
        raise _friendly(e)
    except Exception as e:                                  # network resets, ffmpeg problems...
        raise _friendly(e)
    if not info:
        raise IngestError("Nothing could be downloaded from this link.")
    if info.get("_type") == "playlist":
        entries = [x for x in (info.get("entries") or []) if x]
        if not entries:
            raise IngestError("This link has no videos in it.")
        info = entries[0]
    video = next((p for p in sorted(dest.glob("src.*")) if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")), None) if want_video else None
    audio = next((p for p in sorted(dest.glob("src.*")) if p.suffix.lower() not in (".vtt", ".json3", ".srt", ".json", ".part", ".ytdl")), None)
    media = video or audio
    if not media or media.stat().st_size < 2000:
        raise IngestError("The download finished but no media was found.")
    subs = next(iter(sorted(dest.glob("src.*.json3"))), None) or next(iter(sorted(dest.glob("src.*.vtt"))), None)
    return {"audio": media, "video": video, "title": (info.get("title") or "Imported video")[:120], "uploader": info.get("uploader") or info.get("channel") or "",
            "duration": float(info.get("duration") or 0), "license": info.get("license") or "", "url": url, "subs": subs,
            "subs_lang": (subs.name.split(".")[-2] if subs else ""), "automatic": bool(subs and subs.name.split(".")[-2] in (info.get("automatic_captions") or {}) and
                                                                                    subs.name.split(".")[-2] not in (info.get("subtitles") or {}))}


# --------------------------------------------------------------------------- subtitles -> words
def _clean(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\[[^\]]{1,30}\]|\([^)]{1,30}\)|♪+", " ", t)        # [Music], (applause)
    return re.sub(r"\s+", " ", t).strip()


def _split_cue(text: str, start: float, end: float) -> list[dict]:
    words = text.split()
    if not words or end <= start:
        return []
    weights = [max(1, len(w)) for w in words]
    total = sum(weights)
    out, t = [], start
    for w, wt in zip(words, weights):
        d = (end - start) * wt / total
        out.append({"text": w, "start": round(t, 3), "end": round(t + d, 3), "conf": 0.9})
        t += d
    return out


def words_from_json3(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[dict] = []
    for ev in data.get("events", []):
        segs = ev.get("segs") or []
        if not segs:
            continue
        t0 = ev.get("tStartMs", 0) / 1000
        t1 = t0 + ev.get("dDurationMs", 0) / 1000
        timed = [s for s in segs if s.get("utf8", "").strip()]
        if len(segs) > 1 and any("tOffsetMs" in s for s in segs):      # automatic captions: every word has its own offset (the first one omits it)
            for i, s in enumerate(timed):
                txt = _clean(s["utf8"])
                if not txt:
                    continue
                a = t0 + s.get("tOffsetMs", 0) / 1000
                nxt = t0 + timed[i + 1].get("tOffsetMs", 0) / 1000 if i + 1 < len(timed) else t1
                out.append({"text": txt, "start": round(a, 3), "end": round(max(a + 0.05, min(nxt, a + 1.2)), 3), "conf": 0.95})
        else:
            txt = _clean("".join(s.get("utf8", "") for s in segs))
            out += _split_cue(txt, t0, t1)
    return _dedupe(out)


_VTT_TIME = re.compile(r"(?:(\d+):)?(\d+):(\d+)[.,](\d+)\s+-->\s+(?:(\d+):)?(\d+):(\d+)[.,](\d+)")


def words_from_vtt(path: Path) -> list[dict]:
    out, lines, i = [], path.read_text(encoding="utf-8", errors="replace").splitlines(), 0
    sec = lambda h, m, s, ms: int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000
    while i < len(lines):
        m = _VTT_TIME.search(lines[i])
        i += 1
        if not m:
            continue
        a, b = sec(*m.group(1, 2, 3, 4)), sec(*m.group(5, 6, 7, 8))
        text = []
        while i < len(lines) and lines[i].strip():
            text.append(lines[i])
            i += 1
        out += _split_cue(_clean(" ".join(text)), a, b)
    return _dedupe(out)


def _dedupe(words: list[dict]) -> list[dict]:
    """Rolling captions repeat the previous line inside the next cue; keep each spoken word once and in order."""
    out: list[dict] = []
    for w in sorted(words, key=lambda x: x["start"]):
        if out and w["start"] < out[-1]["end"] - 0.02:
            if w["text"] == out[-1]["text"] and abs(w["start"] - out[-1]["start"]) < 0.6:
                continue
            out[-1]["end"] = round(max(out[-1]["start"] + 0.04, w["start"]), 3)
        out.append(w)
    return [w for w in out if w["end"] > w["start"]]


def raw_transcript_from_subs(path: Path, language: str, duration: float) -> Optional[dict]:
    """The same shape the speech recogniser writes (raw_transcript.json), or None when the subtitles hold too little text to trust."""
    try:
        words = words_from_json3(path) if path.suffix == ".json3" else words_from_vtt(path)
    except (OSError, ValueError, KeyError):
        return None
    if len(words) < 8 or (duration and words[-1]["end"] < duration * 0.25):
        return None
    return {"language": language, "model": "subtitles", "duration": duration or words[-1]["end"], "chunks": [], "chunks_without_speech": 0, "words": words}


def create_project(url: str, *, language: str = "en", title: str = "", use_subs: "str | bool" = "auto", want_video: bool = False, progress: Optional[Callable[[float, str], None]] = None, **kw):
    """Download, then make an ordinary project from the audio or video (and keep the subtitle words next to it)."""
    from .project import Project
    from .util import write_json

    with tempfile.TemporaryDirectory() as d:
        mode = ("auto" if use_subs is True else "off" if use_subs is False else use_subs)
        if language == "auto":                 # subtitles are fetched per language; with no language given, listen instead and let the speech stage decide
            mode = "off"
        got = fetch(url, Path(d), language="en" if language == "auto" else language, want_subs=mode != "off", want_video=want_video, progress=progress)
        media_src = got.get("video") or got["audio"]
        p = Project.create(title.strip() or got["title"], media_src, language=language, **kw)
        # automatic English captions make many mistakes ("black doors"); the local speech model is better. Other languages have no better option.
        trusted = got["subs"] and (mode == "any" or not got["automatic"] or language != "en")
        raw = raw_transcript_from_subs(got["subs"], language, got["duration"]) if trusted else None
        if raw:
            write_json(p.dir / "subs.raw.json", raw)
    p.update_meta(origin={"url": got["url"], "title": got["title"], "uploader": got["uploader"], "license": got["license"], "subtitles": bool(raw),
                          "automatic_captions": got["automatic"] if raw else False, "video": bool(got.get("video"))})
    return p
