import pytest
from vt import tts


def choices():
    return [{'id':'comfyvoice','available':True,'voices':[]},
            {'id':'edge','available':True,'voices':[{'id':'en-test','lang':'en'},{'id':'bn-test','lang':'bn'}]}]


def test_best_voice_uses_a_ready_expressive_workflow(monkeypatch):
    monkeypatch.setattr(tts,'_comfy_voice_plan',lambda *args:('breeze_design',{'breeze_design'}))
    assert tts.recommended_voice('en',choices())==('comfyvoice','design:auto')


def test_best_voice_respects_language_and_unavailable_models(monkeypatch):
    monkeypatch.setattr(tts,'_comfy_voice_plan',lambda *args:(None,set()))
    assert tts.recommended_voice('bn',choices())==('edge','bn-test')
    with pytest.raises(tts.TTSError):
        tts.recommended_voice('fr',choices())


def test_automatic_voice_is_resolved_and_recorded_on_project_creation(ref,monkeypatch):
    from vt.project import Project
    from vt.util import read_json
    monkeypatch.setattr(tts,'recommended_voice',lambda lang:('comfyvoice','design:auto'))
    monkeypatch.setattr(tts,'match_script',lambda text,lang,engine,voice:(lang,voice))
    project=Project.create_from_script('Best voice test','Run each day.',voice_engine='auto',voice='auto',language='en')
    saved=read_json(project.script_path)
    assert saved['engine']=='comfyvoice' and saved['voice']=='design:auto'
