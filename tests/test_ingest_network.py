"""Real downloads. Skipped when offline, and when YT_TESTS=0. Uses public-domain material only (LibriVox on archive.org, NASA)."""
import os
import socket

import pytest

from vt import ingest

pytestmark = pytest.mark.slow


def online() -> bool:
    try:
        socket.create_connection(("archive.org", 443), timeout=4).close()
        return os.environ.get("YT_TESTS", "1") != "0"
    except OSError:
        return False


@pytest.fixture(scope="module", autouse=True)
def need_net():
    if not online():
        pytest.skip("no internet")


LIBRIVOX = "https://archive.org/download/art_of_war_librivox/art_of_war_01-02_sun_tzu_64kb.mp3"
NASA = "https://www.youtube.com/watch?v=wymMn-SmALY"                    # 22 s NASA animation (public domain)


def test_a_direct_audio_link_downloads_and_makes_a_project(projects_dir):
    p = ingest.create_project(LIBRIVOX, language="en", title="Laying plans")
    m = p.meta()
    assert m.title == "Laying plans" and m.origin["url"] == LIBRIVOX and m.origin["subtitles"] is False
    assert any(p.dir.glob("input.*")) and next(p.dir.glob("input.*")).stat().st_size > 500_000


def test_a_missing_file_gives_a_plain_message():
    with pytest.raises(ingest.IngestError, match="404"):
        ingest.fetch("https://archive.org/download/art_of_war_librivox/definitely-not-here.mp3", __import__("pathlib").Path(__import__("tempfile").mkdtemp()))


def test_a_youtube_link_gives_audio_and_a_title(tmp_path):
    got = ingest.fetch(NASA, tmp_path, language="en", want_subs=True)
    assert got["audio"].exists() and got["audio"].stat().st_size > 2_000 and got["title"] and got["duration"] > 5
