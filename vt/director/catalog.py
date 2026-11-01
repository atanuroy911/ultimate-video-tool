"""A maintainable catalogue of free media (videos, pictures, music, speech) with licences, attribution and a validation status.

`assets/media_catalog.json` is the one place that names outside files. Every entry was found through a documented API (Internet Archive, Wikimedia
Commons), accepted only if its licence allows reuse (public domain, CC0, CC BY), and is re-checkable: `validate` downloads the file (size-limited),
asks ffprobe what it is and decodes it. Links that stop working are marked `failed`, never silently kept as good. The Studio and CLI read this file;
nothing else in the app hardcodes a URL.

    vt catalog refresh     discover new entries and validate everything
    vt catalog validate    re-check the existing entries only
    vt catalog list
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from .. import paths
from ..util import find_tool, now_iso, read_json, write_json

CATALOG = paths.ASSETS / "media_catalog.json"
def _ua() -> dict[str, str]:
    """Wikimedia asks every client to say who is calling (a URL or an email). Set `catalog_contact` in settings.json or VT_CATALOG_CONTACT; the default only names the app."""
    import os

    contact = os.environ.get("VT_CATALOG_CONTACT") or (read_json(paths.SETTINGS, {}) or {}).get("catalog_contact") or "https://github.com/video-tool/video-tool; local desktop app"
    return {"User-Agent": f"VideoTool-catalog/1.0 ({contact})"}


UA = _ua()
MAX_MB = {"video": 60, "audio": 40, "image": 15}
KINDS = ("video", "audio", "image")
ROLES = ("clip", "speech", "music", "sfx", "picture")

# Licences that allow reuse of the file as is. Attribution is recorded for every entry; CC BY needs it, the others do not require it.
OK_LICENCE = re.compile(r"(public domain|cc0|cc-0|pdm|publicdomain|cc by(?!-nc)(?!-nd)(?! nc)(?! nd)|cc-by(?!-nc)(?!-nd)|attribution(?!-noncommercial))", re.I)
BAD_LICENCE = re.compile(r"(nc|noncommercial|non-commercial|nd|noderivs|no derivatives|sa\b.*gpl|all rights reserved)", re.I)


class CatalogError(RuntimeError):
    pass


def load() -> list[dict]:
    return read_json(CATALOG, []) or []


def save(entries: list[dict]) -> None:
    write_json(CATALOG, sorted(entries, key=lambda e: (e["kind"], e.get("role", ""), e["id"])))


def licence_ok(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if re.search(r"\b(by-nc|by-nd|nc-|nd-|noncommercial)", t, re.I) or re.search(r"\bnc\b|\bnd\b", t, re.I):
        return False
    if re.search(r"\bsa\b|share-?alike", t, re.I):          # share-alike would put conditions on the finished video: left out
        return False
    return bool(OK_LICENCE.search(t))


# --------------------------------------------------------------------------- looking at a file
def ffprobe(path: Path) -> dict:
    r = subprocess.run([find_tool("ffprobe"), "-v", "error", "-show_entries", "format=format_name,duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
                        "-of", "json", str(path)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise CatalogError("ffprobe could not read the file: " + (r.stderr or "")[-160:])
    j = json.loads(r.stdout or "{}")
    streams = j.get("streams", [])
    v = next((s for s in streams if s["codec_type"] == "video"), None)
    a = next((s for s in streams if s["codec_type"] == "audio"), None)
    fr = 0.0
    if v and v.get("r_frame_rate") and "/" in v["r_frame_rate"]:
        n, d = v["r_frame_rate"].split("/")
        fr = round(float(n) / float(d), 2) if float(d) else 0.0
    return {
        "container": (j.get("format", {}).get("format_name") or "").split(",")[0], "duration": round(float(j.get("format", {}).get("duration") or 0), 2),
        "bytes": int(j.get("format", {}).get("size") or 0),
        "video": {"codec": v["codec_name"], "width": v.get("width"), "height": v.get("height"), "fps": fr} if v else None,
        "audio": {"codec": a["codec_name"], "sample_rate": int(a.get("sample_rate") or 0), "channels": a.get("channels")} if a else None,
    }


def decodes(path: Path, seconds: int = 20) -> Optional[str]:
    """None when the first seconds decode cleanly, else the error text."""
    r = subprocess.run([find_tool("ffmpeg"), "-v", "error", "-t", str(seconds), "-i", str(path), "-f", "null", "-"], capture_output=True, text=True, timeout=180)
    return (r.stderr or "").strip()[-200:] or None if r.returncode != 0 or (r.stderr or "").strip() else None


def download(url: str, dest: Path, max_mb: int, progress: Optional[Callable[[float], None]] = None) -> int:
    """Stream a file to `dest` (redirects followed, size limited). Returns the bytes written."""
    got = 0
    with httpx.stream("GET", url, follow_redirects=True, timeout=60, headers=_ua()) as r:
        if r.status_code != 200:
            raise CatalogError(f"HTTP {r.status_code}")
        total = int(r.headers.get("content-length") or 0)
        if total and total > max_mb * 1_000_000:
            raise CatalogError(f"larger than {max_mb} MB ({total / 1e6:.0f} MB)")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f:
            for chunk in r.iter_bytes(1 << 18):
                got += len(chunk)
                if got > max_mb * 1_000_000:
                    raise CatalogError(f"larger than {max_mb} MB")
                f.write(chunk)
                if progress and total:
                    progress(got / total)
    return got


def validate(entry: dict, keep: Optional[Path] = None) -> dict:
    """Download the file and check it: reachable, decodable, and what the entry claims. Sets status ok / failed and the real format."""
    e = dict(entry)
    e["validated_at"] = now_iso()
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / ("file" + (Path(e["url"].split("?")[0]).suffix or ".bin"))
        try:
            n = download(e["url"], f, MAX_MB.get(e["kind"], 40))
            info = ffprobe(f)
            if e["kind"] == "video" and not info["video"]:
                raise CatalogError("no video stream")
            if e["kind"] == "audio" and not info["audio"]:
                raise CatalogError("no audio stream")
            if e["kind"] != "image":
                bad = decodes(f)
                if bad:
                    raise CatalogError("does not decode cleanly: " + bad)
            e.update(format=info, bytes=n, status="ok", error="")
            if keep:
                keep.parent.mkdir(parents=True, exist_ok=True)
                f.replace(keep)
        except (CatalogError, httpx.HTTPError, subprocess.TimeoutExpired, OSError) as ex:
            e.update(status="failed", error=str(ex)[:200])
    return e


# --------------------------------------------------------------------------- discovery: Internet Archive
def _get(url: str, params: Optional[dict] = None) -> Any:
    for attempt in range(3):
        try:
            r = httpx.get(url, params=params, timeout=40, headers=_ua(), follow_redirects=True)
            if r.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            time.sleep(1.5)
    raise CatalogError(f"could not reach {url}")


def discover_archive(query: str, kind: str, role: str, limit: int = 3, exts: tuple[str, ...] = (".mp4",), max_mb: Optional[int] = None) -> list[dict]:
    """Items of the Internet Archive that match `query`, whose licence allows reuse. The derivative file (small mp4/mp3) is the one catalogued."""
    mt = {"video": "movies", "audio": "audio", "image": "image"}[kind]
    j = _get("https://archive.org/advancedsearch.php", {"q": f"({query}) AND mediatype:{mt}", "fl[]": ["identifier", "title", "licenseurl", "creator"], "rows": 25, "output": "json"})
    out: list[dict] = []
    for d in j["response"]["docs"]:
        if len(out) >= limit:
            break
        lic_url = d.get("licenseurl") if isinstance(d.get("licenseurl"), str) else (d.get("licenseurl") or [""])[0]
        meta = _get(f"https://archive.org/metadata/{d['identifier']}")
        lic = lic_url or (meta.get("metadata", {}).get("licenseurl") or "")
        if isinstance(lic, list):
            lic = lic[0]
        pd = "publicdomain" in lic or "creativecommons.org/licenses/by/" in lic
        if not pd:
            continue
        files = [f for f in meta.get("files", []) if f.get("name", "").lower().endswith(exts) and f.get("source") in ("derivative", "original") and int(f.get("size") or 0) > 20_000]
        files = [f for f in files if int(f.get("size") or 0) <= (max_mb or MAX_MB[kind]) * 1_000_000]
        if not files:
            continue
        files.sort(key=lambda f: int(f.get("size") or 0))
        f = files[min(len(files) - 1, 0 if kind == "audio" else len(files) // 2)]
        title = (d.get("title") if isinstance(d.get("title"), str) else str(d.get("title")))[:90]
        creator = d.get("creator") if isinstance(d.get("creator"), str) else ", ".join(d.get("creator") or [])[:80]
        short = "CC0 / Public domain" if "publicdomain" in lic else "CC BY 4.0"
        out.append({
            "id": "ia-" + re.sub(r"[^a-z0-9]+", "-", d["identifier"].lower())[:50], "kind": kind, "role": role, "title": title, "source": "archive.org",
            "page_url": f"https://archive.org/details/{d['identifier']}", "url": f"https://archive.org/download/{d['identifier']}/{f['name']}",
            "licence": short, "licence_url": lic, "creator": creator or "unknown", "attribution": f"“{title}” by {creator or 'unknown'}, via the Internet Archive ({short})",
            "tags": role and [role],
        })
    return out


# --------------------------------------------------------------------------- discovery: Wikimedia Commons
def discover_commons(search: str, kind: str, role: str, limit: int = 3, mimes: tuple[str, ...] = ("video/webm", "video/ogg", "video/mp4")) -> list[dict]:
    j = _get("https://commons.wikimedia.org/w/api.php", {"action": "query", "generator": "search", "gsrsearch": search, "gsrnamespace": 6, "gsrlimit": 30, "prop": "imageinfo",
                                                           "iiprop": "url|mime|size|extmetadata", "format": "json", "formatversion": 2})
    out: list[dict] = []
    for pg in sorted(j.get("query", {}).get("pages", []), key=lambda p: p.get("index", 0)):
        if len(out) >= limit:
            break
        ii = (pg.get("imageinfo") or [{}])[0]
        if ii.get("mime") not in mimes or not ii.get("url"):
            continue
        if ii.get("size", 0) > MAX_MB[kind] * 1_000_000 or ii.get("size", 0) < 20_000:
            continue
        md = ii.get("extmetadata", {})
        lic = (md.get("LicenseShortName", {}).get("value") or "")
        if not licence_ok(lic):
            continue
        artist = re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value") or "unknown").strip()[:80]
        title = pg["title"].removeprefix("File:").rsplit(".", 1)[0][:90]
        out.append({
            "id": "wc-" + re.sub(r"[^a-z0-9]+", "-", title.lower())[:50].strip("-"), "kind": kind, "role": role, "title": title, "source": "commons.wikimedia.org",
            "page_url": ii.get("descriptionurl", ""), "url": ii["url"], "licence": lic, "licence_url": md.get("LicenseUrl", {}).get("value", ""), "creator": artist,
            "attribution": f"“{title}” by {artist}, via Wikimedia Commons ({lic})", "tags": [role],
        })
    return out


# --------------------------------------------------------------------------- the catalogue
AUDIO_MIMES = ("audio/ogg", "application/ogg", "audio/mpeg", "audio/flac", "audio/wav", "audio/x-wav", "audio/x-flac")
QUERIES: list[dict] = [
    {"via": "archive", "q": "collection:prelinger AND licenseurl:*publicdomain*", "kind": "video", "role": "clip", "limit": 4, "exts": (".mp4",), "max_mb": 40},
    {"via": "archive", "q": "collection:nasa AND licenseurl:*publicdomain*", "kind": "video", "role": "clip", "limit": 2, "exts": (".mp4",), "max_mb": 40},
    {"via": "archive", "q": "collection:opensource_movies AND licenseurl:*publicdomain*", "kind": "video", "role": "clip", "limit": 2, "exts": (".mp4",), "max_mb": 25},
    {"via": "archive", "q": "collection:librivoxaudio AND licenseurl:*publicdomain*", "kind": "audio", "role": "speech", "limit": 4, "exts": (".mp3",), "max_mb": 15},
    {"via": "archive", "q": "collection:opensource_audio AND subject:music AND licenseurl:*publicdomain*", "kind": "audio", "role": "music", "limit": 4, "exts": (".mp3",), "max_mb": 12},
    {"via": "commons", "q": "filetype:video nature", "kind": "video", "role": "clip", "limit": 3},
    {"via": "commons", "q": "filetype:video animation", "kind": "video", "role": "clip", "limit": 2},
    {"via": "commons", "q": "filetype:audio ambient", "kind": "audio", "role": "music", "limit": 3, "mimes": AUDIO_MIMES},
    {"via": "commons", "q": "filetype:audio sound effect", "kind": "audio", "role": "sfx", "limit": 3, "mimes": AUDIO_MIMES},
]


def refresh(progress: Callable[[str], None] = lambda m: None, discover: bool = True, only_failed: bool = False) -> list[dict]:
    """Discover new entries (when `discover`), then validate every entry that is new, failed or older than 30 days. Writes the catalogue."""
    entries = {e["id"]: e for e in load() if licence_ok(e.get("licence", ""))}          # an entry whose licence no longer passes the filter is dropped
    if discover:
        for q in QUERIES:
            try:
                found = (discover_archive(q["q"], q["kind"], q["role"], q["limit"], q.get("exts", (".mp4",)), q.get("max_mb")) if q["via"] == "archive"
                         else discover_commons(q["q"], q["kind"], q["role"], q["limit"], q.get("mimes", ("video/webm", "video/ogg", "video/mp4"))))
            except CatalogError as e:
                progress(f"search failed: {q['q'][:40]}: {e}")
                continue
            for e in found:
                entries.setdefault(e["id"], e)
            progress(f"{q['via']}: {len(found)} candidates for {q['role']}")
    stale = time.time() - 30 * 86400
    for k, e in list(entries.items()):
        age = time.mktime(time.strptime(e["validated_at"][:19], "%Y-%m-%dT%H:%M:%S")) if e.get("validated_at") else 0
        if only_failed and e.get("status") != "failed":
            continue
        if e.get("status") != "ok" or age < stale or only_failed:
            progress(f"checking {k}")
            entries[k] = validate(e)
    out = list(entries.values())
    save(out)
    return out


def summary(entries: Optional[list[dict]] = None) -> dict:
    es = entries if entries is not None else load()
    return {"total": len(es), "ok": sum(1 for e in es if e.get("status") == "ok"), "failed": sum(1 for e in es if e.get("status") == "failed"),
            "by_role": {r: sum(1 for e in es if e.get("role") == r and e.get("status") == "ok") for r in ROLES}}


# --------------------------------------------------------------------------- using an entry
PUBLIC = ("id", "kind", "role", "title", "source", "page_url", "licence", "licence_url", "creator", "attribution", "status", "validated_at", "format", "bytes", "error", "tags")


def public(e: dict) -> dict:
    return {k: e.get(k) for k in PUBLIC}


def find(entry_id: str) -> dict:
    e = next((x for x in load() if x["id"] == entry_id), None)
    if not e:
        raise CatalogError(f"no catalogue entry '{entry_id}'")
    return e


def _fetch(e: dict, dest: Path) -> None:
    """Download an entry that is believed good; if the link has gone bad the entry is re-marked failed so the next list shows it."""
    try:
        download(e["url"], dest, MAX_MB.get(e["kind"], 40))
    except (CatalogError, httpx.HTTPError, OSError) as ex:
        entries = load()
        for x in entries:
            if x["id"] == e["id"]:
                x.update(status="failed", error=str(ex)[:200], validated_at=now_iso())
        save(entries)
        raise CatalogError(f"could not download '{e['title']}' ({ex}). The catalogue now marks it as failed.") from ex


def install_media(project, entry_id: str):
    """Add a catalogued clip or picture to a project's media bin, with its source and licence recorded (they appear in the export's credits file)."""
    from .media import add_media, add_sound

    e = find(entry_id)
    if e["kind"] not in ("video", "image", "audio"):
        raise CatalogError("this entry cannot be added to a project")
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / (re.sub(r"[^A-Za-z0-9]+", "-", e["id"])[:40] + (Path(e["url"].split("?")[0]).suffix or (".mp3" if e["kind"] == "audio" else ".mp4")))
        _fetch(e, f)
        if e["kind"] == "audio":                                                  # a track for the layers' audio tracks
            return add_sound(project, f, caption=e["title"][:80], source=e["source"], credit=e["attribution"][:160], licence=e["licence"])
        return add_media(project, f, caption=e["title"][:80], tags=[t for t in (e.get("tags") or []) if t], source=e["source"], credit=e["attribution"][:160], licence=e["licence"])


def install_music(entry_id: str) -> str:
    """Download a catalogued track into the user's music folder (next to a credit note). Returns the music id the export uses."""
    e = find(entry_id)
    if e["kind"] != "audio":
        raise CatalogError("this entry is not audio")
    ext = Path(e["url"].split("?")[0]).suffix.lower() or ".mp3"
    ext = {".oga": ".ogg", ".opus": ".ogg"}.get(ext, ext)                       # the music list knows these suffixes
    if ext not in (".mp3", ".wav", ".m4a", ".ogg", ".flac"):
        ext = ".mp3"
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", e["id"]) + ext
    paths.USER_MUSIC.mkdir(parents=True, exist_ok=True)
    dest = paths.USER_MUSIC / name
    if not dest.exists():
        _fetch(e, dest)
    write_json(dest.with_suffix(dest.suffix + ".credit.json"), {"title": e["title"], "attribution": e["attribution"], "licence": e["licence"], "page_url": e["page_url"]})
    return f"user/{name}"


def music_credit(music_id: Optional[str]) -> str:
    """The credit line for a user music track installed from the catalogue ('' for anything else)."""
    if not music_id or not music_id.startswith("user/"):
        return ""
    f = paths.USER_MUSIC / (music_id.removeprefix("user/") + ".credit.json")
    d = read_json(f, None) if f.exists() else None
    return f"Music: {d['attribution']} {d.get('page_url', '')}".strip() if d else ""
