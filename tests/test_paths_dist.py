"""The product folder: the program's own ffmpeg / node are found before anything on PATH, a missing tool gives a readable error."""
import os
import sys

import pytest

from vt import util


def fake_tool(d, name):
    f = d / (name + (".exe" if sys.platform == "win32" else ""))
    f.write_bytes(b"x")
    f.chmod(0o755)
    return f


def test_the_programs_own_bin_comes_before_path(tmp_path, monkeypatch):
    own = tmp_path / "own"
    other = tmp_path / "other"
    own.mkdir()
    other.mkdir()
    a, b = fake_tool(own, "ffmpeg"), fake_tool(other, "ffmpeg")
    monkeypatch.delenv("VT_BIN", raising=False)
    monkeypatch.setenv("PATH", str(other) + os.pathsep + os.environ["PATH"])
    assert os.path.normcase(util.find_tool("ffmpeg")) == os.path.normcase(str(b))   # nothing of ours: PATH
    monkeypatch.setenv("VT_BIN", str(own))
    assert util.find_tool("ffmpeg") == str(a)                                     # ours wins
    assert util.find_tool("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg") == str(a)


def test_a_product_layout_is_found_by_position(tmp_path, monkeypatch):
    from vt import paths

    (tmp_path / "app").mkdir()
    (tmp_path / "bin").mkdir()
    n = fake_tool(tmp_path / "bin", "node")
    monkeypatch.setattr(paths, "ROOT", tmp_path / "app")
    monkeypatch.delenv("VT_BIN", raising=False)
    assert util.find_tool("node") == str(n)
    assert util.tool_dirs() == [tmp_path / "bin"]
    n.unlink()  # On Linux the executable itself is named node; replace the fixture with the unpacked layout.
    (tmp_path / "bin" / "node").mkdir()
    n2 = fake_tool(tmp_path / "bin" / "node", "npx")
    assert util.find_tool("npx") == str(n2)                                           # node is unpacked whole into bin/node


def test_several_folders_in_vt_bin_and_a_missing_tool(tmp_path, monkeypatch):
    d1, d2 = tmp_path / "a", tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    t = fake_tool(d2, "sometool")
    monkeypatch.setenv("VT_BIN", os.pathsep.join([str(d1), str(d2), str(tmp_path / "nope")]))
    assert util.find_tool("sometool") == str(t)
    with pytest.raises(RuntimeError, match="was not found"):
        util.find_tool("no-such-tool-anywhere")


def test_the_renderer_is_pointed_at_the_products_own_ffmpeg_ffprobe_and_chrome(tmp_path, monkeypatch):
    from vt.render import hyperframes as H

    exe = ".exe" if os.name == "nt" else ""
    (tmp_path / "chrome" / "x" / "y").mkdir(parents=True)
    for n in ("ffmpeg", "ffprobe"):
        (tmp_path / f"{n}{exe}").write_bytes(b"x")
    (tmp_path / "chrome" / "x" / "y" / f"chrome-headless-shell{exe}").write_bytes(b"x")
    monkeypatch.setenv("VT_BIN", str(tmp_path))
    for k in ("HYPERFRAMES_FFMPEG_PATH", "HYPERFRAMES_FFPROBE_PATH", "HYPERFRAMES_BROWSER_PATH", "PRODUCER_HEADLESS_SHELL_PATH"):
        monkeypatch.setenv(k, "")                                                         # records what the variable was, even when it was absent: use_product_binaries sets os.environ directly, and a bare delenv of an absent variable records nothing, so the fake Chrome used to outlive this test and broke every later render
        monkeypatch.delenv(k)
    got = H.use_product_binaries()
    assert got["HYPERFRAMES_FFMPEG_PATH"].endswith(f"ffmpeg{exe}") and got["HYPERFRAMES_FFPROBE_PATH"].endswith(f"ffprobe{exe}")
    assert "chrome-headless-shell" in got["HYPERFRAMES_BROWSER_PATH"] and os.environ["PRODUCER_HEADLESS_SHELL_PATH"] == got["HYPERFRAMES_BROWSER_PATH"]
    monkeypatch.setenv("VT_BIN", str(tmp_path / "nothing"))
    for k in got:
        monkeypatch.delenv(k, raising=False)
    fallback = H.use_product_binaries()                                                       # nothing of ours: ffmpeg/ffprobe fall back to the system's, Chrome is left to HyperFrames
    assert "HYPERFRAMES_BROWSER_PATH" not in fallback and not any(str(tmp_path) in v for v in fallback.values())


def test_the_fake_chrome_of_the_test_above_does_not_outlive_it():
    """pytest runs this straight after the test above. A path into pytest's temp folder here is the leak that once made every later render test fail with
    `spawn .../chrome-headless-shell EACCES`: use_product_binaries sets os.environ directly, so a bare monkeypatch.delenv of an absent variable restored nothing."""
    for k in ("HYPERFRAMES_FFMPEG_PATH", "HYPERFRAMES_FFPROBE_PATH", "HYPERFRAMES_BROWSER_PATH", "PRODUCER_HEADLESS_SHELL_PATH"):
        assert "pytest-of" not in os.environ.get(k, ""), f"{k} still points into a finished test's temp folder: {os.environ[k]}"
