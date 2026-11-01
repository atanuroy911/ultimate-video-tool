import subprocess
import threading

import numpy as np
import soundfile as sf

from vt.project import Project
from vt.util import find_tool


def test_concurrent_preview_builds_leave_one_valid_file(projects_dir):
    """The server (project list) and the pipeline can both build the preview at once; the result must still decode cleanly."""
    sf.write(str(projects_dir / "a.wav"), (0.2 * np.sin(2 * np.pi * 220 * np.arange(48000 * 8) / 48000)).astype("float32"), 48000)
    p = Project.create("x", projects_dir / "a.wav")
    sf.write(str(p.cut_audio), (0.2 * np.sin(2 * np.pi * 220 * np.arange(48000 * 8) / 48000)).astype("float32"), 48000)
    threads = [threading.Thread(target=Project(p.id).ensure_preview_audio) for _ in range(5)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert p.preview_audio.exists() and [f.name for f in p.dir.glob("audio.preview*")] == ["audio.preview.m4a"]
    r = subprocess.run([find_tool("ffmpeg"), "-v", "error", "-i", str(p.preview_audio), "-f", "null", "-"], capture_output=True, text=True)
    assert r.returncode == 0 and r.stderr.strip() == ""
