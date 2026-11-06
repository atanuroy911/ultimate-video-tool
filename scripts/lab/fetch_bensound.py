"""Put free Bensound tracks into the music library of this computer (the owner's request, 2026-11-05), each with its credit and mood.

Run on the server: python fetch_bensound.py <user-music folder>. Bensound's free licence asks for a credit: vt/director/catalog.music_credit gives the line,
and the export's description carries it. The tracks stay in the owner's library; they are not part of the app or its installers.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

TRACKS = [("floating-garden-dreamy-lo-fi", "Floating Garden", "Aventure", "lofi"), ("moonlight-drive-lo-fi-relaxing", "Moonlight Drive", "Yunior Arronte", "lofi"),
          ("long-night-calm-warm", "Long Night", "Aventure", "calm"), ("aeon-calm-reflective", "Aeon", "Theatre Of Delays", "calm"),
          ("cozy-coffeehouse-shiny-chill", "Cozy Coffeehouse", "Lunar Years", "playful"), ("rhythm-magnet-happy-organ", "Rhythm Magnet", "Marcus P.", "playful"),
          ("on-repeat-shiny-uplifting", "On Repeat", "Marcus P.", "upbeat"), ("keep-it-real-positive-energetic", "Keep It Real", "Nick Petrov", "upbeat"),
          ("new-frontier-emotional-hopeful", "New Frontier", "Lunar Years", "corporate"), ("silent-waves-positive-chill", "Silent Waves", "Nick Petrov", "corporate"),
          ("prism-ambient-suspenseful", "Prism", "Theatre Of Delays", "tense"), ("silent-suspicions-dark-tense", "Silent Suspicions", "FoePound", "tense")]
AGENT = {"User-Agent": "Mozilla/5.0"}


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=120) as r:
        return r.read()


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for slug, title, artist, mood in TRACKS:
        page_url = f"https://www.bensound.com/royalty-free-music/track/{slug}"
        dest = folder / f"bensound-{slug}.mp3"
        try:
            if not dest.exists():
                found = re.search(r'"download_url":"([^"]+)"', get(page_url).decode("utf-8", "replace"))
                if not found:
                    print("no free file on the page:", title)
                    continue
                data = get(found.group(1).replace("\\/", "/"))
                if len(data) < 200_000:
                    print("too small to be the track:", title, len(data))
                    continue
                dest.write_bytes(data)
            note = {"title": title, "attribution": f"{title} by {artist}, Bensound.com", "licence": "Bensound free licence, credit required", "page_url": page_url, "mood": mood}
            dest.with_suffix(".mp3.credit.json").write_text(json.dumps(note, indent=1), encoding="utf-8")
            print("ok", title, mood, dest.stat().st_size)
        except Exception as e:
            print("failed", title, type(e).__name__, str(e)[:120])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
