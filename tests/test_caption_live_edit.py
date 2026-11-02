"""A caption correction must reach the files used by preview and export."""
from vt.util import read_json


def test_caption_edit_recovers_theme_from_existing_preview(ref):
    from vt import paths
    from vt.pipeline import compose_all
    from vt.server.app import edit_word, WordEdit

    compose_all(ref)
    theme = ref.scenes().theme or ref.meta().theme
    # Simulate an older project moved without its custom theme library.
    (ref.dir / "theme.snapshot.json").unlink()
    (paths.THEMES / theme / "theme.json").unlink()
    word = ref.transcript().kept()[0]
    edit_word(ref.id, word.id, WordEdit(text="PortableCaption"))
    data = read_json(ref.comp_dir / "9x16" / "data.json")
    assert any(w["text"] == "PortableCaption" for c in data["captions"] for w in c["words"])
    assert read_json(ref.dir / "theme.snapshot.json")["name"] == theme


def test_word_correction_reaches_every_preview_format(ref):
    from vt.server.app import edit_word, WordEdit
    from vt.compose import FORMATS

    word = ref.transcript().kept()[0]
    edit_word(ref.id, word.id, WordEdit(text="CorrectedCaption"))
    assert next(w for w in ref.transcript().words if w.id == word.id).text == "CorrectedCaption"
    for fmt in FORMATS.values():
        folder = ref.comp_dir / fmt["tag"]
        data = read_json(folder / "data.json")
        assert any(w["text"] == "CorrectedCaption" for c in data["captions"] for w in c["words"])
        assert "CorrectedCaption" in (folder / "index.html").read_text(encoding="utf-8")
