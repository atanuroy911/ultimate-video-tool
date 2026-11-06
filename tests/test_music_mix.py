"""The sound mix controls (vt/render/mux.py): ducking on/off/strength, loudness target and music fades all give a valid filter graph and a playable file."""
import shutil
import subprocess

import pytest

from vt.render.mux import find_tool, mix_and_mux

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") and not find_tool("ffmpeg"), reason="ffmpeg is not installed")


@pytest.fixture()
def media(tmp_path):
    ff = find_tool("ffmpeg")
    def run(*a):
        subprocess.run([ff, "-v", "error", "-y", *a], check=True)
    run("-f", "lavfi", "-i", "color=c=black:s=320x180:d=4", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(tmp_path / "v.mp4"))
    run("-f", "lavfi", "-i", "sine=f=300:d=2", "-f", "lavfi", "-i", "anullsrc=d=2", "-filter_complex", "[0][1]concat=n=2:v=0:a=1", str(tmp_path / "voice.wav"))
    run("-f", "lavfi", "-i", "sine=f=220:d=4", str(tmp_path / "music.wav"))
    return tmp_path


@pytest.mark.parametrize("kw", [dict(), dict(duck=False), dict(duck_amount=1.0, duck_release=1.2), dict(target_lufs=-20, music_fade_in=0, music_fade_out=0)])
def test_every_mix_setting_renders(media, kw):
    out = media / "out.mp4"
    mix_and_mux(media / "v.mp4", media / "voice.wav", out, duration=4.0, music=media / "music.wav", music_volume=0.1, gpu=False, **kw)
    assert out.stat().st_size > 1000
