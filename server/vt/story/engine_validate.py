# Ported unchanged from story-engine.zip planner/validate.py (Cartoon 2); the CLI part is left out.
"""Validate + auto-fix a story spec (from any planner: LLM, rules or hand-written).
Returns (fixed_spec, errors, warnings). Errors = must be fixed (LLM gets them back for a retry)."""
import copy, json, os, re, sys
from .engine_common import norm_words

ELEMENTS = {'person', 'mini', 'crowd', 'bubble', 'thought', 'text', 'title', 'pill', 'card', 'quote', 'badge', 'stamp', 'steps', 'paper', 'note',
            'counter', 'gauge', 'progress', 'bars', 'calendar', 'clock', 'heart', 'eyes', 'icon', 'phone', 'monitor', 'door', 'window', 'bed', 'sofa',
            'desk', 'chair', 'lamp', 'books', 'cup', 'bag', 'plant', 'tree', 'house', 'car', 'particles', 'overlay', 'ecg', 'arrow', 'lines',
            'spotlight', 'shape', 'image', 'group'}
BGS = {'plain', 'gradient', 'room', 'living', 'split', 'street', 'exterior', 'office', 'classroom', 'shop', 'park', 'nightsky'}
SFX = {'tick', 'pop', 'stamp', 'printer', 'whoosh', 'pad'}
TOP, BOTTOM = 112, 800   # design-space safe zone (tag chip above, captions below)


def validate(spec, srt_text=None, fix=True, notes=None):
    """`notes` (when given) receives every change this makes to the story as {scene, says, meaning}: meaning True when it dropped or replaced something the director wrote
    (an element type, a background, a speaker, a sound), False when it only closed a small gap or moved a time. Scene numbers in the notes count from 1; element numbers are the
    place in the scene's `elements` list. (The older warnings keep counting scenes from 0, as the spec's own `scenes` list does.)"""
    def note(says, meaning=True, scene=None):
        if notes is not None:
            notes.append({"scene": scene, "says": (f"scene {scene}: " if scene else "") + says, "meaning": meaning})

    s = copy.deepcopy(spec)
    err, warn = [], []
    for k in ('meta', 'characters', 'captions', 'scenes'):
        if k not in s:
            err.append(f'missing top-level key "{k}"')
    if err:
        return s, err, warn
    s.setdefault('speak', {}); s.setdefault('tags', []); s.setdefault('sfx', [])
    total = float(s['meta'].get('total', 0))
    if total <= 0:
        err.append('meta.total must be > 0')
    # captions must be the narration words, unchanged
    if srt_text is not None:
        a, b = norm_words(srt_text), norm_words(' '.join(c['t'] for c in s['captions']))
        if a != b:
            err.append('caption words differ from the SRT (only {highlight} braces and line breaks may be added)')
    for i, c in enumerate(s['captions']):
        if c['e'] <= c['s']:
            err.append(f'caption {i} ends before it starts')
        lines = c['t'].split('\n')
        if len(lines) > 2:
            warn.append(f'caption {i} has >2 lines')
        if any(len(l.replace('{', '').replace('}', '')) > 32 for l in lines):
            warn.append(f'caption {i} line too long')
    # scenes: sorted, contiguous, cover 0..total
    sc = sorted(s['scenes'], key=lambda x: x['s'])
    if not sc:
        err.append('no scenes')
        return s, err, warn
    if fix:
        if sc[0]['s'] != 0.0:
            note(f"the first scene started at {sc[0]['s']:g} s, so it starts at 0", False, 1)
        sc[0]['s'] = 0.0
        for i in range(len(sc) - 1):
            if abs(sc[i]['e'] - sc[i + 1]['s']) > 0.001:
                if abs(sc[i]['e'] - sc[i + 1]['s']) < 0.6:
                    note(f"it ended at {sc[i]['e']:g} s and the next scene starts at {sc[i + 1]['s']:g} s, so it now ends where the next one starts", False, i + 1)
                    sc[i]['e'] = sc[i + 1]['s']
                else:
                    err.append(f'gap/overlap between scene {i} and {i + 1}')
        if sc[-1]['e'] != total:
            note(f"the last scene ended at {sc[-1]['e']:g} s, so it ends with the video at {total:g} s", False, len(sc))
        sc[-1]['e'] = total
    for i, x in enumerate(sc):
        if x['e'] - x['s'] < 0.5:
            warn.append(f'scene {i} shorter than 0.5 s')
        bg = x.get('bg') or {'type': 'plain'}
        if bg.get('type') not in BGS:
            (warn if fix else err).append(f'scene {i}: unknown bg "{bg.get("type")}" -> plain')
            if fix:
                note(f'the background "{bg.get("type")}" does not exist, so it is a plain background', True, i + 1)
                x['bg'] = {'type': 'plain', 'color': '#E6DDCB'}
        good = []
        for j, el in enumerate(x.get('elements', [])):
            t = el.get('type')
            if t not in ELEMENTS:
                warn.append(f'scene {i} element {j}: unknown type "{t}" dropped')
                note(f'element {j} is a "{t}", which cannot be drawn, so it was left out', True, i + 1)
                continue
            if t in ('person', 'mini') and el.get('char') and el['char'] not in s['characters']:
                err.append(f'scene {i}: character "{el["char"]}" is not defined in characters')
            for key in ('x', 'y', 's', 'rot', 'at', 'until'):
                if key in el and not isinstance(el[key], (int, float)):
                    err.append(f'scene {i} element {j}: "{key}" must be a number')
            # words the drawing reads as text: a number written by the director (e.g. steps 3, 6, 9) is the same words as text; anything else goes back
            for key in ('text', 'title', 'big'):
                if el.get(key) is not None and not isinstance(el[key], str):
                    if fix and isinstance(el[key], (int, float)) and not isinstance(el[key], bool):
                        note(f'element {j} ({t}): its {key} {el[key]!r} was a number, so it is written as text', False, i + 1)
                        el[key] = f"{el[key]:g}"
                    else:
                        err.append(f'scene {i} element {j}: "{key}" must be text')
            for key in ('items', 'texts', 'labels'):
                if key in el and isinstance(el[key], list) and any(not isinstance(v, str) for v in el[key]):
                    if fix and all(isinstance(v, (str, int, float)) and not isinstance(v, bool) for v in el[key]):
                        note(f'element {j} ({t}): some of its {key} were numbers, so they are written as text', False, i + 1)
                        el[key] = [v if isinstance(v, str) else f"{v:g}" for v in el[key]]
                    else:
                        err.append(f'scene {i} element {j}: every one of "{key}" must be text')
            if fix and 'at' in el and isinstance(el['at'], (int, float)):
                at = min(max(el['at'], x['s']), x['e'] - 0.1)
                if at != el['at']:
                    note(f'element {j} ({t}) appears at {el["at"]:g} s, which is outside its scene, so it appears at {at:g} s', False, i + 1)
                el['at'] = at
            # safe-zone check for characters
            if t == 'person' and isinstance(el.get('y'), (int, float)):
                sc_ = el.get('s', 1); top = el['y'] - 345 * sc_
                feet = el['y'] + (184 if el.get('pose', 'sit') == 'sit' else 214) * sc_
                if top < TOP - 20: warn.append(f'scene {i}: person "{el.get("char")}" head above safe zone (y-345*s={top:.0f})')
                if feet > BOTTOM + 40: warn.append(f'scene {i}: person "{el.get("char")}" feet inside caption zone ({feet:.0f})')
            elif t in ('text', 'title', 'pill', 'badge', 'stamp', 'icon', 'bubble', 'counter') and isinstance(el.get('y'), (int, float)):
                if el['y'] < TOP + 10 or el['y'] > 730:
                    warn.append(f'scene {i}: {t} at y={el["y"]} outside content zone ({TOP + 10}-730)')
            good.append(el)
        x['elements'] = good
    s['scenes'] = sc
    for k, w in list(s['speak'].items()):
        if k not in s['characters']:
            warn.append(f'speak: unknown character {k}'); s['speak'].pop(k)
            note(f'"{k}" speaks but is not in the characters, so its speech was left out')
    kept_sfx = [f for f in s['sfx'] if isinstance(f, list) and len(f) == 3 and f[0] in SFX]
    if fix and len(kept_sfx) != len(s['sfx']):
        left = [f[0] if isinstance(f, list) and f else f for f in s['sfx'] if f not in kept_sfx]
        note(f'the sound(s) {", ".join(repr(str(x)) for x in left)} are not in the sound library (one of: {", ".join(sorted(SFX))}), so they were left out')
    s['sfx'] = kept_sfx if fix else s['sfx']
    for tg in s['tags']:
        if len(tg['tag']) > 16:
            warn.append(f'tag "{tg["tag"]}" is long (keep 1-3 words)')
    return s, err, warn

