"""A scene the director wrote as characters acting (a stick timeline) becomes a cartoon scene. A cartoon the director wrote itself is used as written."""
from ..schema import Cartoon, CastMember, CartoonCue
from ..story.motifs import extras_for

POSES = {'idle':'idle','walk':'walk','enter':'walk','exit':'walk','run':'run','point':'point','explain':'point','think':'think',
         'wave':'wave','greet':'wave','celebrate':'celebrate','jump':'celebrate','cheer':'celebrate','sit':'sit','shrug':'shrug','sad':'sad',
         'laugh':'laugh','giggle':'laugh','count':'count','confused':'confused','ride':'ride','cycle':'ride'}
PLACES = {'park':'nature','forest':'nature','mountain':'nature','river':'nature','school':'classroom','room':'home','bedroom':'home',
          'kitchen':'home','city':'street','road':'street','bus_stop':'street','lab':'office','workshop':'office','store':'shop'}


def apply_story_kit(plan, script, tr, beats, style, motifs=True):
    if script.kind != 'cartoon': return plan
    for scene in plan.scenes:                     # repair_script gives every scene a default actor: it must not act over, or replace, the director's own cartoon
        if scene.stick and any(e.type == 'cartoon' for e in scene.elements):
            scene.stick = None
            scene.archetype = 'cartoon'
    if style == 'illustrated': return plan
    envs = set(Cartoon.model_fields['set'].annotation.__args__)
    poses = set(CastMember.model_fields['pose'].annotation.__args__)
    expressions = set(CastMember.model_fields['expression'].annotation.__args__)
    by_beat = {b.id:b for b in beats.beats}
    words = tr.by_id()
    written = {s.id: s for s in getattr(script, 'scenes', [])}
    for scene in plan.scenes:
        timeline = scene.stick
        if not timeline: continue
        mine = written.get(scene.id)
        if mine is not None and not mine.actions and scene.elements:   # the director wrote this scene with no one acting in it: repair's default actor does not get to appear
            scene.stick = None
            continue
        # Animal stories retain their dedicated animal rigs rather than turning an animal into a person.
        used = {a.get('who') for a in timeline.get('actions',[])}
        cast = [c for c in timeline.get('cast',[]) if not used or c.get('id') in used]
        if any(c.get('kind') == 'emoji' or c.get('role') in ('animal','object') for c in cast) or len(cast)>3: continue
        if not cast: continue
        members=[]
        for i,c in enumerate(cast):
            role=c.get('role','')
            look=c.get('style') or {}
            feminine = look.get('hair') in ('long','pony','bun')
            who = ('girl' if feminine else 'boy') if look.get('height') == 'child' else ('old_woman' if feminine else 'elder') if look.get('height')=='elder' or role=='elder' else 'teacher' if role in ('teacher','expert') else 'woman' if feminine else 'man'
            if role in ('robot','doctor','worker','teacher'): who=role
            members.append(CastMember(who=who,name=(c.get('name') or c['id'])[:14],x=(i+1)/(len(cast)+1),clothes=look.get('shirt') or ''))
        index={c['id']:i for i,c in enumerate(cast)}
        cues=[]
        for a in timeline.get('actions',[]):
            if a.get('who') not in index: continue
            start=float(a.get('start',0));end=max(start+.01,float(a.get('end',start+.2)))
            verb=a.get('do','stand');pose=verb if verb in poses else next((v for k,v in POSES.items() if k in verb),'stand')
            mood=a.get('emotion') or 'neutral';mood=mood if mood in expressions else 'neutral'
            cues.append(CartoonCue(actor=index[a['who']],start=start,end=end,pose=pose,expression=mood,count=a.get('count')))
        setting=timeline.get('set') or {}
        place=setting.get('kind','plain');place=place if place in envs else PLACES.get(place,'plain')
        time=setting.get('time','day');lighting='night' if time=='night' else 'sunset' if time in ('evening','sunset','golden') else 'day'
        first=by_beat[scene.beats[0]]
        scene_words=[words[w] for b in scene.beats for w in by_beat[b].word_ids if w in words]
        cartoon=Cartoon(at_word=first.word_ids[0],set=place,cast=members,character_style=style,lighting=lighting,
                        camera='push',framing='scene',world='3d',cues=cues,edited=False,extras=extras_for(scene_words,shown=frozenset(e.type for e in scene.elements if e.type not in ('cartoon','speaker_card'))) if motifs else [])      # the zip's word-timed props
        scene.elements=[cartoon,*[e for e in scene.elements if e.type not in ('cartoon','speaker_card')]]
        scene.stick=None
        scene.archetype='cartoon'
        scene.layout='hero'
    return plan
