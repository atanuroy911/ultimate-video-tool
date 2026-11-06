"""The interface is English only (owner, 2026-11-06: "remove bengali i18n in ui. It sucks.. No need. Just language in video is fine.").
Bangla stays a language for videos: the script, the voice, the captions, the transcription. This guard keeps a translation and a language switch from coming back."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "client" / "studio" / "src"
BANGLA = re.compile("[ঀ-৿]")
LANGUAGE_NAMES = ('"tf.lang.speech"', '"tf.lang.script.bn"')           # the two lines that name the video language "বাংলা" inside an English sentence


def test_the_dictionary_is_english_only_and_has_no_way_to_switch():
    text = (SRC / "i18n.ts").read_text(encoding="utf-8")
    assert "const bn" not in text and "dicts" not in text and "setLanguage" not in text
    for line in text.splitlines():
        if BANGLA.search(line):
            assert line.strip().startswith(LANGUAGE_NAMES), f"Bangla text in the interface dictionary: {line.strip()[:80]}"


def test_nothing_keeps_an_interface_language():
    for f in SRC.rglob("*.ts*"):
        text = f.read_text(encoding="utf-8")
        assert "ui_language" not in text and "vt-lang" not in text, f"{f.relative_to(SRC)} still keeps an interface language"
        assert not re.search(r'import\s*\{[^}]*setLanguage[^}]*\}\s*from\s*"[./]+/i18n"', text), f"{f.relative_to(SRC)} imports setLanguage from the dictionary"


def test_the_shell_and_the_settings_page_offer_no_language_for_the_app():
    assert "বাং" not in (SRC / "Shell.tsx").read_text(encoding="utf-8")
    settings = (SRC / "pages" / "Settings.tsx").read_text(encoding="utf-8")
    assert "App language" not in settings and "বাংলা" not in settings


def test_bangla_is_still_a_language_for_videos():
    options = (SRC / "pages" / "NewOptions.tsx").read_text(encoding="utf-8")
    assert 'title="বাংলা"' in options and "Bangla, including English words mixed in." in options
    assert "hasBangla" in (SRC / "pages" / "New.tsx").read_text(encoding="utf-8")                 # a script written in Bangla is recognised as one
