"""The model downloader: pinned table, resume after an interruption, size and hash checks, nothing torn left behind."""
import hashlib
import threading

import pytest

from vt import models as M
from vt import paths


class Resp:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def raise_for_status(self): pass
    def iter_bytes(self, n):
        for i in range(0, len(self.data), 100):
            yield self.data[i:i + 100]


@pytest.fixture()
def tiny(tmp_path, monkeypatch):
    import httpx

    body = bytes(range(256)) * 4
    f = M.File("sub/a.bin", len(body), "http://x/a.bin", hashlib.sha256(body).hexdigest())
    m = M.Model("tiny", "Tiny", "tinyfolder", "MIT", (f,))
    monkeypatch.setitem(M.MODELS, "tiny", m)
    monkeypatch.setattr(paths, "MODELS", tmp_path / "models")
    seen = []

    def stream(method, url, headers=None, **k):
        seen.append(dict(headers or {}))
        start = int((headers or {}).get("Range", "bytes=0-")[6:-1])
        return Resp(body[start:], 206 if start else 200)
    monkeypatch.setattr(httpx, "stream", stream)
    return m, body, seen


def test_the_table_is_pinned_and_sound():
    for m in M.MODELS.values():
        assert m.files and m.total > 0 and m.licence
        for f in m.files:
            assert f.bytes > 0 and f.url.startswith("https://") and not f.rel.startswith("/")
            assert len(f.sha256) in (0, 64)
    t = M.get("chatterbox-turbo")
    assert len(t.files) == 9 and t.total == 1_123_738_092 and all(f.sha256 for f in t.files)
    assert all("d21799bd0354adb85e348b8a0442a8405110a2cf" in f.url for f in t.files)           # pinned commit, never "main"
    with pytest.raises(M.ModelError):
        M.get("nope")


def test_a_download_lands_whole_and_a_second_call_downloads_nothing(tiny):
    m, body, seen = tiny
    assert not M.ready("tiny") and M.missing_bytes("tiny") == len(body)
    got = []
    d = M.ensure("tiny", lambda f, msg: got.append(f))
    assert (d / "sub" / "a.bin").read_bytes() == body and M.ready("tiny") and got[-1] == 1.0
    n = len(seen)
    M.ensure("tiny")
    assert len(seen) == n and not list(d.rglob("*.part"))


def test_an_interrupted_download_is_resumed_with_a_range_and_checked(tiny):
    m, body, seen = tiny
    part = m.dir / "sub" / "a.bin.part"
    part.parent.mkdir(parents=True)
    part.write_bytes(body[:300])
    M.ensure("tiny")
    assert seen[-1] == {"Range": "bytes=300-"} and (m.dir / "sub" / "a.bin").read_bytes() == body


def test_a_damaged_file_is_refused_and_removed(tiny, monkeypatch):
    import httpx

    m, body, _ = tiny
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: Resp(b"\x00" * len(body)))              # right size, wrong content
    with pytest.raises(M.ModelError, match="damaged"):
        M.ensure("tiny")
    assert not list(m.dir.rglob("*")) or not any(p.is_file() for p in m.dir.rglob("*")) and not M.ready("tiny")


def test_a_cancelled_download_stops(tiny):
    ev = threading.Event()
    ev.set()
    with pytest.raises(M.ModelError, match="cancelled"):
        M.ensure("tiny", cancel=ev)
