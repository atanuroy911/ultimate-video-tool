import pytest

from vt import llm, paths
from vt.pipeline import Pipeline
from vt.project import Project
from vt.visuals.lexicon import Lexicon

from test_llm_plan import FakeModel
from test_tts import fake_engine

pytestmark = pytest.mark.skipif(not Lexicon.get().ok, reason="visual lexicon not built")
SCRIPT = "The boy opened the cupboard. He took the watch to the market. The father smiled gently. Then everybody went home."


def make(projects_dir, monkeypatch, theme="auto"):
    fake_engine(monkeypatch)
    return Project.create_from_script("ai", SCRIPT, voice_engine="edge", language="en", theme=theme)


def test_plan_stage_uses_the_local_ai_and_designs_the_video_automatically(projects_dir, monkeypatch):
    p = make(projects_dir, monkeypatch)
    p.update_meta(usecase="general")                     # picture scenes are the ones the model refines (cartoons, charts keep their rule design)
    monkeypatch.setattr(llm, "settings", lambda: {"llm_mode": "auto", "ollama_url": "http://x", "ollama_model": "m", "llm_auto_download": False})
    monkeypatch.setattr(llm, "ensure_ready", lambda *a, **k: "m")
    monkeypatch.setattr(llm, "chat_json", FakeModel())
    Pipeline(p).run(to_stage="plan")
    meta = p.meta()
    assert meta.theme.startswith("auto-") and (paths.THEMES / meta.theme / "theme.json").exists()   # a look was designed for this video
    assert p.scenes().planner == "llm" and p.scenes().theme == meta.theme
    notice = p.dir / "ai_notice.json"
    assert notice.exists() and "message" in notice.read_text(encoding="utf-8")


def test_without_a_model_the_video_still_plans_and_says_why(projects_dir, monkeypatch):
    p = make(projects_dir, monkeypatch)
    monkeypatch.setattr(llm, "settings", lambda: {"llm_mode": "auto", "ollama_url": "http://x", "ollama_model": "m", "llm_auto_download": False})
    def down(*a, **k):
        raise llm.LLMUnavailable("The Ollama server at http://x does not answer.")
    monkeypatch.setattr(llm, "ensure_ready", down)
    Pipeline(p).run(to_stage="plan")
    assert p.scenes().planner == "rules" and p.meta().theme.startswith("auto-")
    assert "does not answer" in (p.dir / "ai_notice.json").read_text(encoding="utf-8")


def test_ai_off_never_contacts_a_model(projects_dir, monkeypatch):
    p = make(projects_dir, monkeypatch, theme="paper")
    monkeypatch.setattr(llm, "settings", lambda: {"llm_mode": "off", "ollama_url": "", "ollama_model": "", "llm_auto_download": False})
    monkeypatch.setattr(llm, "ensure_ready", lambda *a, **k: pytest.fail("must not be called when the AI is off"))
    Pipeline(p).run(to_stage="plan")
    assert p.scenes().planner == "rules" and p.meta().theme == "paper"
