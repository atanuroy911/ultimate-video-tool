import json

import httpx
import pytest
from PIL import Image

from test_api import client  # noqa: F401  (the API test client fixture)
from vt.director import stock
from vt.project import Project


@pytest.fixture()
def proj(projects_dir):
    import numpy as np
    import soundfile as sf
    sf.write(str(projects_dir / "a.wav"), np.zeros(1600, dtype="float32"), 16000)
    return Project.create("s", projects_dir / "a.wav")


@pytest.fixture()
def providers(monkeypatch, tmp_path):
    """Pexels and Pixabay stand-ins: canned search answers and a real (tiny) JPEG to download."""
    img = tmp_path / "dl.jpg"
    Image.new("RGB", (640, 480), (30, 120, 200)).save(img)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        calls.append((u, dict(request.headers)))
        if "api.pexels.com/v1/search" in u:
            if request.headers.get("authorization") != "pk":
                return httpx.Response(401)
            return httpx.Response(200, json={"photos": [{"id": 7, "width": 4000, "height": 3000, "url": "https://pexels.com/p/7", "photographer": "Ana",
                                                           "src": {"medium": "https://images.pexels.com/m.jpg", "large": "https://images.pexels.com/l.jpg",
                                                                   "large2x": "https://images.pexels.com/dl.jpg"}}]})
        if "api.pexels.com/videos/search" in u:
            return httpx.Response(200, json={"videos": [{"id": 9, "duration": 12, "image": "https://images.pexels.com/v.jpg", "url": "https://pexels.com/v/9",
                                                           "user": {"name": "Bo"},
                                                           "video_files": [{"file_type": "video/mp4", "width": 1080, "height": 1920, "link": "https://videos.pexels.com/f.mp4"}]}]})
        if "pixabay.com/api/" in u and "videos" not in u:
            return httpx.Response(200, json={"hits": [{"id": 3, "imageWidth": 1600, "imageHeight": 900, "webformatURL": "https://pixabay.com/w.jpg",
                                                         "largeImageURL": "https://pixabay.com/dl.jpg", "user": "Cy", "pageURL": "https://pixabay.com/p/3"}]})
        if u.startswith("https://images.pexels.com/dl.jpg") or u.startswith("https://pixabay.com/dl.jpg"):
            return httpx.Response(200, content=img.read_bytes())
        return httpx.Response(404)

    monkeypatch.setattr(stock, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True))
    monkeypatch.setattr(stock, "keys", lambda: {"pexels": "pk", "pixabay": "xk"})
    return calls


def test_search_merges_providers_and_records_licences(providers):
    res = stock.search("market", kind="image", aspect="9:16")
    assert {r["provider"] for r in res} == {"pexels", "pixabay"}
    p = next(r for r in res if r["provider"] == "pexels")
    assert p["credit"] == "Ana" and "attribution not required" in p["licence"] and p["url"].endswith("dl.jpg")
    assert any("orientation=portrait" in u for u, _ in providers) and any("orientation=vertical" in u for u, _ in providers)
    v = stock.search("market", kind="video", provider="pexels")
    assert v[0]["kind"] == "video" and v[0]["duration"] == 12 and v[0]["url"].endswith("f.mp4")


def test_the_key_goes_only_to_its_own_provider(providers):
    stock.search("x", provider="pexels")
    assert all("xk" not in u and "xk" not in json.dumps(h) for u, h in providers)
    stock.search("x", provider="pixabay")
    assert not any(h.get("authorization") == "pk" for u, h in providers if "pixabay" in u)


def test_missing_or_wrong_keys_and_errors_are_explained(monkeypatch, providers):
    monkeypatch.setattr(stock, "keys", lambda: {"pexels": "", "pixabay": ""})
    with pytest.raises(stock.StockError, match="Add a free"):
        stock.search("x")
    monkeypatch.setattr(stock, "keys", lambda: {"pexels": "wrong", "pixabay": ""})
    with pytest.raises(stock.StockError, match="refused the API key"):
        stock.search("x")
    assert stock.search("   ") == []


def test_download_lands_in_the_media_bin_with_credit_and_a_credits_file(proj, providers):
    item = stock.search("market", provider="pexels")[0]
    m = stock.add_to_project(proj, item, caption="market")
    assert m.source == "pexels" and m.credit == "Ana" and (proj.dir / m.file).exists() and m.width == 640
    txt = stock.credits_text(proj)
    assert "Ana" in txt and "Pexels" in txt
    own = proj.dir / "own.jpg"
    Image.new("RGB", (30, 30), "red").save(own)
    from vt.director.media import add_media
    add_media(proj, own)
    assert txt == stock.credits_text(proj)                                  # the user's own pictures never need credit


def test_downloads_are_limited_to_the_providers(proj, providers):
    for bad in ("http://pexels.com/x.jpg", "https://evil.example.com/x.jpg", "file:///etc/passwd", ""):
        with pytest.raises(stock.StockError):
            stock.add_to_project(proj, {"url": bad, "kind": "image", "id": "x"})
    assert proj.meta().media == []


def test_api_never_returns_the_keys(client, monkeypatch, providers):
    monkeypatch.setattr(stock, "status", lambda: {"pexels": True, "pixabay": False})
    assert client.get("/api/stock/status").json() == {"pexels": True, "pixabay": False}
    r = client.get("/api/projects/reference/stock/search", params={"q": "market"})
    assert r.status_code == 200 and r.json()
    a = client.post("/api/projects/reference/stock/add", json={"item": r.json()[0], "caption": "m"})
    assert a.status_code == 200 and a.json()["source"] in ("pexels", "pixabay")
    assert client.get("/api/projects/reference/stock/search", params={"q": "x", "kind": "gif"}).status_code == 400


def test_stock_errors_are_reported_not_crashed(client, monkeypatch):
    monkeypatch.setattr(stock, "keys", lambda: {"pexels": "", "pixabay": ""})
    r = client.get("/api/projects/reference/stock/search", params={"q": "market"})
    assert r.status_code == 502 and "Add a free" in r.json()["detail"]


def test_settings_api_never_echoes_keys(client, tmp_path, monkeypatch):
    from vt.server import app as srv
    monkeypatch.setattr(srv, "SETTINGS_PATH", tmp_path / "settings.json")
    r = client.put("/api/settings", json={"pexels_key": "SECRET123", "default_theme": "auto"})
    assert "SECRET123" not in r.text and r.json()["stock_keys"] == {"pexels": True}
    got = client.get("/api/settings")
    assert "SECRET123" not in got.text and got.json()["default_theme"] == "auto"
    assert "SECRET123" in (tmp_path / "settings.json").read_text(encoding="utf-8")        # kept on disk
    client.put("/api/settings", json={"default_pace": "fast"})                           # saving other settings must not erase the key
    assert "SECRET123" in (tmp_path / "settings.json").read_text(encoding="utf-8")
    assert client.put("/api/settings", json={"pexels_key": ""}).json()["stock_keys"] == {"pexels": False}


def test_suggestions_come_from_the_script_and_skip_common_words(proj):
    from vt.schema import Transcript, Word
    words = "the farmer carried the harvest to the village market and they were happy".split()
    proj.save_transcript(Transcript(words=[Word(id=f"w{i}", text=w, start=i * 0.3, end=i * 0.3 + 0.25) for i, w in enumerate(words)]))
    got = stock.suggest(proj)
    assert "harvest" in got and "village" in got or "farmer" in got
    assert not {"they", "were", "the", "happy"} & set(got) or "happy" in got
    assert all(g not in ("the", "and", "they", "were") for g in got)


def test_clipart_search_uses_only_pixabay_vectors(providers):
    res = stock.search("black hole", kind="clipart", aspect="9:16")
    assert {r["provider"] for r in res} == {"pixabay"} and all(r["kind"] == "image" for r in res)
    urls = [u for u, _ in providers]
    assert any("image_type=vector" in u and "orientation=all" in u for u in urls) and not any("pexels" in u for u in urls)
