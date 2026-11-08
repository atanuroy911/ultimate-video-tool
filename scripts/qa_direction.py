"""Render scene voice/caption replacement and undo on an isolated synthetic project."""
from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
import numpy as np
import soundfile as sf
from PIL import Image
from vt import paths, voice_edit, layers
from vt.project import Project
from vt.schema import ProjectMeta, Cuts, ScenesFile
from vt.pipeline import Pipeline, compose_all
from vt.compose import FORMATS
from vt.render.hyperframes import snapshot
from vt.util import write_json


def main():
    out = ROOT / 'docs/evidence/direction-render'
    out.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix='direction-', dir=out))
    paths.SETTINGS = scratch / 'settings.json'
    paths.GLOBAL_GLOSSARY = scratch / 'glossary.json'
    write_json(paths.SETTINGS, {'llm_mode': 'off', 'autopilot': False})
    project = Project('caption-check', scratch)
    project.dir.mkdir(parents=True)
    project.save_meta(ProjectMeta(id=project.id, title='Caption replacement QA', language='en', source='script'))
    sf.write(str(project.master), np.zeros(24000*4, dtype='float32'), 24000)
    write_json(project.cuts_path, Cuts(source_duration=4, keep=[(0,4)]).model_dump())
    write_json(project.raw_transcript_path, {'words': [
        {'text': word, 'start': .2+i*.6, 'end': .7+i*.6}
        for i,word in enumerate(['Walk', 'each', 'day.'])]})
    Pipeline(project).stage_words()
    project.save_scenes(ScenesFile.model_validate({'scenes': [{'id':'s1',
        'beats':[b.id for b in project.beats().beats], 'elements':[
            {'type':'title', 'at_word':'w1', 'text':'Small habits'}]}]}))
    voice_edit.render_voice(project)
    compose_all(project)
    before=voice_edit.snapshot(project)
    voice_edit.apply(project, layers.load(project), 0, 4, 'Run every day.', 's1')
    assert project.transcript().words[0].text=='Run'
    frames=[]
    for aspect, spec in FORMATS.items():
        comp=project.comp_dir/spec['tag']
        frames.append(snapshot(comp,out/spec['tag'],[.45],gpu=False)[0])
    sheet=Image.new('RGB',(960,360),'#e4e4e8')
    for i,frame in enumerate(frames):
        picture=Image.open(frame).convert('RGB')
        picture.thumbnail((310,350))
        sheet.paste(picture,(i*320+(320-picture.width)//2,(360-picture.height)//2))
    sheet.save(out/'contact-sheet.png')
    voice_edit.undo(project,'s1')
    assert voice_edit.snapshot(project)==before
    (out/'result.json').write_text(json.dumps({'caption':'Run every day.','formats':list(FORMATS),'undo':'exact restoration'},indent=2),encoding='utf-8')
    print('Caption replacement rendered in all three formats; undo restores the original data.')


if __name__=='__main__':
    main()
