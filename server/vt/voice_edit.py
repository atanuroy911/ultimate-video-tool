"""A scene voice replacement is one reversible edit, without re-cutting the video."""
from __future__ import annotations
from . import audio_edit as AE, layers as L
from .util import read_json, write_json

FILES=("audio_edits.json","audio_hist.json","layers.json","layers.history.json","edits.json","edits.prev.json","transcript.json","beats.json","beats.prev.json")


def snapshot(project):
    return {name:read_json(project.dir/name,None) for name in FILES}


def restore(project,state):
    for name in FILES:
        if state[name] is None:
            (project.dir/name).unlink(missing_ok=True)
        else:
            write_json(project.dir/name,state[name])


def render_voice(project):
    from .stages import audio
    audio.apply_cuts(project.master,project.cuts(),project.cut_audio)
    AE.apply_to_cut_audio(project.cut_audio,project.cuts(),AE.load(project))
    project.ensure_preview_audio()


def apply(project,document,start,end,text,scene,mute=True):
    from . import transcript_edit as TE
    from .pipeline import Pipeline,compose_all
    before=snapshot(project)
    try:
        if mute:
            AE.save(project,AE.set_mute(AE.load(project),project.cuts(),start,end,True))
            render_voice(project)
        L.save(project,document)
        if scene and project.raw_transcript_path.exists():
            words=[(w.id,w.text) for w in project.transcript().words if start <= (w.start+w.end)/2 < end]
            if words:
                edits=read_json(project.dir/'edits.json',{'words':{}}) or {'words':{}}
                write_json(project.dir/'edits.prev.json',edits)
                changes=TE.align(words,text)
                # Hidden captions must retain their word IDs: visuals can still
                # be anchored to those moments after a shorter replacement.
                changes={wid:({"cut":True} if change.get("drop") else {**change,"cut":False})
                         for wid,change in changes.items()}
                for wid,_ in words:
                    changes.setdefault(wid,{"cut":False})
                write_json(project.dir/'edits.json',TE.merge(edits,changes))
                Pipeline(project).stage_words(preserve_structure=True)
        compose_all(project)
        if scene:
            write_json(project.dir/'voice_replacement_undo.json',{'scene':scene,'before':before,'after':snapshot(project)})
    except Exception:
        restore(project,before)
        render_voice(project)
        compose_all(project)
        raise


def undo(project,scene):
    from .pipeline import compose_all
    saved=read_json(project.dir/'voice_replacement_undo.json',{}) or {}
    if saved.get('scene')!=scene:
        raise ValueError('No voice replacement to undo for this scene.')
    if snapshot(project)!=saved['after']:
        raise ValueError('The voice, captions or tracks changed afterwards. Undo those edits first.')
    try:
        restore(project,saved['before'])
        render_voice(project)
        compose_all(project)
    except Exception:
        restore(project,saved['after'])
        render_voice(project)
        compose_all(project)
        raise
    (project.dir/'voice_replacement_undo.json').unlink(missing_ok=True)
