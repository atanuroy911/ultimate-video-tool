"""Optional stock pictures and clips from Pexels and Pixabay, with the user's OWN free API keys (Settings). Nothing is bundled or redistributed:
files are downloaded into the project's media bin on request, with provider, photographer and licence recorded (and written to a credits file
next to every export). Keys live in settings.json on this computer and are only ever sent to the provider they belong to."""
from __future__ import annotations

import logging

import re
import tempfile
from pathlib import Path
from typing import Any, Optional

import httpx

from .. import paths
from ..util import read_json

TIMEOUT = 20
LICENCES = {
    "pexels": "Pexels License: free to use, attribution not required, not to imply endorsement or be sold unmodified",
    "pixabay": "Pixabay Content License: free to use, attribution not required, not to be redistributed as standalone files",
}
MAX_DOWNLOAD = 150 * 1024 * 1024


class StockError(RuntimeError):
    pass


def keys() -> dict[str, str]:
    s = read_json(paths.SETTINGS, {}) or {}
    return {"pexels": (s.get("pexels_key") or "").strip(), "pixabay": (s.get("pixabay_key") or "").strip()}


def status() -> dict[str, bool]:
    k = keys()
    return {p: bool(v) for p, v in k.items()}


def _client() -> httpx.Client:
    """One place to build the HTTP client, so tests can stand in for the providers."""
    return httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": "video-tool"})


def _check(r: httpx.Response, provider: str) -> dict:
    if r.status_code in (401, 403):
        raise StockError(f"{provider.title()} refused the API key. Check it in Settings.")
    if r.status_code == 429:
        raise StockError(f"{provider.title()} says too many requests. Wait a minute and try again.")
    if r.status_code >= 400:
        raise StockError(f"{provider.title()} answered with an error ({r.status_code}).")
    try:
        return r.json()
    except ValueError:
        raise StockError(f"{provider.title()} sent something unexpected.")


def _orient(aspect: str) -> str:
    return {"9:16": "portrait", "1:1": "square", "16:9": "landscape"}[aspect]


def search_pexels(q: str, kind: str, aspect: str, limit: int, key: str) -> list[dict]:
    with _client() as c:
        if kind == "video":
            j = _check(c.get("https://api.pexels.com/videos/search", params={"query": q, "per_page": limit, "orientation": _orient(aspect)}, headers={"Authorization": key}), "pexels")
            out = []
            for v in j.get("videos", []):
                files = sorted((f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width")), key=lambda f: abs(f["width"] - 1080))
                if files:
                    out.append({"id": f"pexels-{v['id']}", "provider": "pexels", "kind": "video", "thumb": v.get("image"), "url": files[0]["link"], "width": files[0]["width"],
                                "height": files[0].get("height", 0), "duration": v.get("duration", 0), "credit": (v.get("user") or {}).get("name", ""), "page": v.get("url", ""),
                                "licence": LICENCES["pexels"]})
            return out
        j = _check(c.get("https://api.pexels.com/v1/search", params={"query": q, "per_page": limit, "orientation": _orient(aspect)}, headers={"Authorization": key}), "pexels")
        return [{"id": f"pexels-{p['id']}", "provider": "pexels", "kind": "image", "thumb": (p.get("src") or {}).get("medium"), "url": (p.get("src") or {}).get("large2x") or (p.get("src") or {}).get("large"),
                 "width": p.get("width", 0), "height": p.get("height", 0), "duration": 0, "credit": p.get("photographer", ""), "page": p.get("url", ""), "licence": LICENCES["pexels"]}
                for p in j.get("photos", []) if (p.get("src") or {}).get("large")]


def search_pixabay(q: str, kind: str, aspect: str, limit: int, key: str) -> list[dict]:
    with _client() as c:
        if kind == "video":
            j = _check(c.get("https://pixabay.com/api/videos/", params={"key": key, "q": q, "per_page": max(3, limit)}), "pixabay")
            out = []
            for v in j.get("hits", []):
                vs = (v.get("videos") or {})
                f = vs.get("large") or vs.get("medium") or vs.get("small") or {}
                if f.get("url"):
                    out.append({"id": f"pixabay-{v['id']}", "provider": "pixabay", "kind": "video", "thumb": f"https://i.vimeocdn.com/video/{v.get('picture_id')}_295x166.jpg" if v.get("picture_id") else None,
                                "url": f["url"], "width": f.get("width", 0), "height": f.get("height", 0), "duration": v.get("duration", 0), "credit": v.get("user", ""),
                                "page": v.get("pageURL", ""), "licence": LICENCES["pixabay"]})
            return out[:limit]
        j = _check(c.get("https://pixabay.com/api/", params={"key": key, "q": q, "image_type": "vector" if kind == "clipart" else "photo", "orientation": "all" if kind == "clipart" else {"9:16": "vertical", "1:1": "all", "16:9": "horizontal"}[aspect],
                                                              "per_page": max(3, limit), "safesearch": "true"}), "pixabay")
        return [{"id": f"pixabay-{p['id']}", "provider": "pixabay", "kind": "image", "thumb": p.get("webformatURL"), "url": p.get("largeImageURL") or p.get("webformatURL"),
                 "width": p.get("imageWidth", 0), "height": p.get("imageHeight", 0), "duration": 0, "credit": p.get("user", ""), "page": p.get("pageURL", ""),
                 "licence": LICENCES["pixabay"]} for p in j.get("hits", [])][:limit]


def search(query: str, *, kind: str = "image", aspect: str = "9:16", provider: Optional[str] = None, limit: int = 12) -> list[dict]:
    """Pictures or clips for a query. Uses every provider that has a key (or just the one asked for)."""
    q = re.sub(r"\s+", " ", query).strip()[:80]
    if not q:
        return []
    ks = keys()
    providers = [p for p in ("pexels", "pixabay") if ks[p] and (provider in (None, p)) and not (kind == "clipart" and p == "pexels")]   # only Pixabay has vector clipart
    if not providers:
        raise StockError("No stock-photo key is set. Add a free Pexels or Pixabay API key in Settings.")
    out: list[dict] = []
    errors: list[str] = []
    for p in providers:
        try:
            out += (search_pexels if p == "pexels" else search_pixabay)(q, "image" if (kind == "clipart" and p == "pexels") else kind, aspect, limit, ks[p])
        except StockError as e:
            errors.append(str(e))
        except httpx.HTTPError:
            errors.append(f"{p.title()} could not be reached. Check the internet connection.")
    if not out and errors:
        raise StockError(" ".join(errors))
    # interleave providers so both show up in the first results
    return out[:limit * 2]


def add_to_project(project, item: dict, caption: str = "") -> Any:
    """Download one search result into the project's media bin (records provider, credit and licence)."""
    from . import media as M

    url = item.get("url") or ""
    if not re.match(r"^https://", url):
        raise StockError("This result has no safe download address.")
    host = re.match(r"^https://([^/]+)/", url + "/")
    if not host or not re.search(r"(pexels\.com|pixabay\.com|vimeocdn\.com)$", host.group(1)):
        raise StockError("Downloads are only allowed from Pexels and Pixabay.")
    ext = ".mp4" if item.get("kind") == "video" else ".jpg"
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / f"{re.sub(r'[^a-z0-9-]', '', str(item.get('id', 'stock')).lower())}{ext}"
        try:
            with _client() as c, c.stream("GET", url) as r:
                if r.status_code >= 400:
                    raise StockError(f"The download failed ({r.status_code}).")
                got = 0
                with dest.open("wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        got += len(chunk)
                        if got > MAX_DOWNLOAD:
                            raise StockError("The file is larger than 150 MB.")
                        f.write(chunk)
        except httpx.HTTPError as e:
            raise StockError("The download could not be completed. Check the internet connection.") from e
        try:
            return M.add_media(project, dest, caption=caption or item.get("query", ""), source=item.get("provider", "stock"), credit=item.get("credit", ""),
                               licence=item.get("licence", ""))
        except M.MediaError as e:
            raise StockError(str(e)) from e


def credits_text(project) -> str:
    """Who to thank, for the media from stock sites used in this project (empty when everything is the user's own)."""
    lines = []
    for m in project.meta().media:
        if m.source not in ("upload", ""):                 # stock sites and the free catalogue: everything that is not the user's own
            lines.append(f"- {m.kind} '{m.id}': {m.credit or 'unknown'} via {m.source}. {m.licence}")
    return ("Media credits\n" + "\n".join(lines) + "\n") if lines else ""


def suggest(project, limit: int = 6) -> list[str]:
    """Search phrases worth trying for this video, from its own script: the scenes' icon/keyword words first, then the rarest content words
    (rare words are the specific ones: 'harvest' beats 'thing'). No network is used; the Studio runs the searches."""
    from ..schema import ScenesFile
    from ..util import read_json

    out: list[str] = []
    sf = read_json(project.dir / "scenes.json", None)
    if sf:
        try:
            for s in ScenesFile.model_validate(sf).scenes:
                for e in s.elements:
                    for key in ("icon", "keyword", "text", "label"):
                        v = getattr(e, key, None)
                        if isinstance(v, str) and re.fullmatch(r"[A-Za-z][A-Za-z -]{2,24}", v.strip()):
                            out.append(v.strip().lower())
        except Exception as _e:  # noqa: BLE001 — stock search words from the context are optional
            logging.getLogger(__name__).warning("stock search words from the context are optional: %s", _e, exc_info=True)
            pass
    try:
        from wordfreq import zipf_frequency

        words = [w.text.strip(".,!?;:\"'").lower() for w in project.transcript().words]
        cand = {w for w in words if re.fullmatch(r"[a-z]{4,}", w)}
        out += sorted(cand, key=lambda w: zipf_frequency(w, "en"))[:limit * 2]
    except Exception as _e:  # noqa: BLE001 — word frequencies are optional
        logging.getLogger(__name__).warning("word frequencies are optional: %s", _e, exc_info=True)
        pass
    seen: list[str] = []
    for q in out:
        if q not in seen and zipf_ok(q):
            seen.append(q)
    return seen[:limit]


def zipf_ok(q: str) -> bool:
    """Skip filler and junk: very common words and tokens that are not real words make poor searches."""
    try:
        from wordfreq import zipf_frequency

        f = zipf_frequency(q.split()[0], "en")
        return 2.0 <= f <= 5.2
    except Exception as _e:  # noqa: BLE001 — word frequencies are optional; any query is allowed
        logging.getLogger(__name__).warning("word frequencies are optional; any query is allowed: %s", _e, exc_info=True)
        return True
