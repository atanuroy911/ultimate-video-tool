# Ported unchanged from story-engine.zip planner/rules.py (Cartoon 2). Our adapter is vt/story/plan.py; keep this file close to upstream.
"""Rule-based story planner: captions -> full story spec, no AI needed.
Works for Bengali and English narration. Everything is driven by the lexicons below, so you can
teach it new motifs by adding words + a builder in BUILDERS, without touching the renderer."""
import re
from .engine_common import wrap

# ---------------------------------------------------------------- lexicons
ROLES = {  # id: (words, display name, preset)
    'mother': (['মা', 'মায়ের', 'মাকে', 'আম্মু', 'আম্মা', 'mother', 'mom', 'mum'], 'মা', 'mother'),
    'father': (['বাবা', 'আব্বু', 'আব্বা', 'father', 'dad'], 'বাবা', 'father'),
    'grandfather': (['দাদা', 'নানা', 'grandfather', 'grandpa'], 'দাদা', 'grandfather'),
    'grandmother': (['দাদি', 'নানি', 'grandmother', 'grandma'], 'দাদি', 'grandmother'),
    'teacher': (['স্যার', 'শিক্ষক', 'ম্যাডাম', 'teacher', 'sir', 'boss', 'বস'], 'স্যার', 'teacher'),
    'friend': (['বন্ধু', 'friend'], 'বন্ধু', 'friend'),
    'sister': (['বোন', 'আপু', 'sister'], 'বোন', 'sister'),
    'wife': (['স্ত্রী', 'বউ', 'wife'], 'স্ত্রী', 'sister'),
    'husband': (['স্বামী', 'husband'], 'স্বামী', 'friend'),
}
SUFFIX = ['', 'র', 'এর', 'ের', 'কে', 'ও', 'ই', 'রা', 'দের', 'য়ের', 'টা', 'টি', "'s", 's']
PRESETS = {
    'hero_m': dict(skin='#A0663A', ear='#8F5A33', shirt='#5F9D7A', pants='#2b3150', hair='#141010'),
    'hero_f': dict(skin='#A86D40', ear='#97603A', shirt='#7a5c8f', pants='#3b2a20', hair='#17120f', lungi='#3b4466', bun=True, orna='#E8B84A'),
    'mother': dict(skin='#9C653D', ear='#8A5733', shirt='#B5543A', pants='#3b2a20', hair='#17120f', lungi='#7A2E3A', bun=True, orna='#E8B84A'),
    'father': dict(skin='#946037', ear='#84552f', shirt='#9DBBD6', pants='#2b2f3f', hair='#9a9a9a', glasses=True),
    'grandfather': dict(skin='#8E5B34', ear='#7d4d2b', shirt='#EFE3C8', pants='#444', hair='#8d8d8d', lungi='#8f98a0', glasses=True, mustache='#8d8d8d', long=True),
    'grandmother': dict(skin='#8E5B34', ear='#7d4d2b', shirt='#EFE3C8', pants='#444', hair='#bdbdbd', lungi='#F1EBDD', bun=True, orna='#d9cbb2'),
    'teacher': dict(skin='#8A5530', ear='#7a4a2a', shirt='#F1EBDD', pants='#3a3a44', hair='#1b140f', glasses=True, mustache='#1b140f'),
    'friend': dict(skin='#A86D40', ear='#97603A', shirt='#D9A93A', pants='#3a4660', hair='#1b140f'),
    'sister': dict(skin='#A0663A', ear='#8F5A33', shirt='#2C483B', pants='#3b2a20', hair='#17120f', lungi='#C8451E', bun=True, orna='#F6EFE8'),
}
EXTRA_SHIRTS = ['#c97f4a', '#6E96BB', '#8f98a0', '#B5677A']

# motif -> trigger roots (substring match, lower-case). Order = priority.
MOTIFS = [
    ('hug', ['জড়িয়ে', 'hug', 'embrace']),
    ('door', ['দরজা', 'door', 'knock']),
    ('phonecall', ['ফোনে', 'on the phone', 'called', 'কল কর']),
    ('phone', ['মোবাইল', 'screen', 'স্ক্রিন', 'ফোন', 'phone', 'message', 'মেসেজ', 'roll number', 'result প্রকাশ', 'website']),
    ('number', ['দশমিক', 'gpa', 'নম্বর পেয়', 'percent', 'শতাংশ']),
    ('paper', ['কাগজ', 'sheet', 'চিঠি', 'letter', 'document', 'certificate', 'সার্টিফিকেট', 'রিপোর্ট']),
    ('clock', ['সকাল দশটা', 'টায়', 'o\'clock', 'ঘড়ি', 'clock']),
    ('calendar', [' দিন ', ' মাস', ' বছর', ' days', ' months', ' years', ' week']),
    ('heart', ['বুক', 'হৃদয়', 'ধক', 'heart', 'ভালোবাস', 'love']),
    ('crowd', ['সবাই', 'আত্মীয়', 'লোকজন', 'everyone', 'people', 'relatives', 'বন্ধুরা', 'পাড়া']),
    ('money', ['টাকা', 'money', 'বেতন', 'salary', 'দাম']),
    ('office', ['ছুটি', 'leave', 'office', 'অফিস']),
    ('lie', ['মিথ্যা', 'lie', 'lied']),
    ('arrive', ['ফিরলেন', 'ফিরল', 'এলেন', 'এল ', 'ঢুকল', 'arrived', 'came home', 'returned']),
    ('think', ['জানে', 'জানত', 'ভাব', 'মনে পড়', 'স্বপ্ন', 'think', 'thought', 'remember', 'dream', 'knew']),
    ('idea', ['বুঝল', 'বুঝলাম', 'বুঝেছিল', 'শিখল', 'শিক্ষা', 'realiz', 'understood', 'learned', 'lesson']),
    ('silent', ['চুপ', 'silent', 'quiet']),
]
EMOTIONS = [
    ('cry', ['কাঁদ', 'কেঁদে', 'কান্না', 'cry', 'cried', 'tears']),
    ('scared', ['ভয়', 'কাঁপ', 'scared', 'afraid', 'fear', 'trembl']),
    ('shock', ['অবাক', 'চমকে', 'ধক', 'নিঃশ্বাস', 'shock', 'surpris', 'froze']),
    ('sad', ['খারাপ', 'কষ্ট', 'দুঃখ', 'হয়নি', 'পারিনি', 'মাথা নিচু', 'sad', 'failed', 'upset', 'নাড়ে']),
    ('smile', ['হাস', 'খুশি', 'আনন্দ', 'smile', 'happy', 'laugh', 'ভালো লাগ']),
    ('angry', ['রাগ', 'angry', 'shout', 'চিৎকার']),
]
TIMES = [('morning', ['সকাল', 'morning']), ('evening', ['সন্ধ্যা', 'বিকেল', 'evening', 'sunset']), ('night', ['রাত', 'night', 'midnight'])]
PLACES = [('office', ['অফিস', 'office']), ('classroom', ['স্কুল', 'ক্লাস', 'কলেজ', 'school', 'class', 'college']),
          ('shop', ['দোকান', 'চায়ের', 'shop', 'tea stall', 'cafe']), ('street', ['রাস্তা', 'street', 'road', 'গলি']),
          ('park', ['পার্ক', 'মাঠ', 'park', 'field']), ('exterior', ['বাড়ি ফির', 'came home', 'বাড়ির সামনে'])]
FLASHBACK = ['ভেবেছিলাম', 'তখন', 'ছোটবেলা', 'years ago', 'back then', 'when i was', 'ফিরিনি']
TAG_BN = {'morning': 'সকাল', 'evening': 'সন্ধ্যা', 'night': 'রাত', 'office': 'অফিসে', 'classroom': 'ক্লাসে', 'shop': 'দোকানে',
          'street': 'রাস্তায়', 'park': 'মাঠে', 'exterior': 'বাড়ি', 'flashback': 'অতীত', 'room': 'ঘরে'}
TAG_EN = {'morning': 'Morning', 'evening': 'Evening', 'night': 'Night', 'office': 'Office', 'classroom': 'Class', 'shop': 'Shop',
          'street': 'Street', 'park': 'Park', 'exterior': 'Home', 'flashback': 'Flashback', 'room': 'Room'}
STOP = set('''সে তার তাকে আমি আমার আমাকে তুমি তোমার তুই তোর তোকে কিন্তু তারপর সেদিন আজ কাল এক একটা একটু সেই যে কারণ আর এবং না কি কী কেউ
সবাই এই ওই অবশেষে কিছুক্ষণ বলল বললেন বলে করে হয়ে হলো ছিল আছে গেল দিল থেকে জন্য সেটা সেখানে নিজের এসে শুধু খুব আবার কয়েক যখন তখন
the a an and but or so to of in on at for with he she it they i you we his her their my your was were is are be been has have had said asked that this then when'''.split())
NUM_BN = {'শূন্য': 0, 'এক': 1, 'দুই': 2, 'তিন': 3, 'চার': 4, 'পাঁচ': 5, 'ছয়': 6, 'সাত': 7, 'আট': 8, 'নয়': 9, 'দশ': 10, 'এগারো': 11, 'বারো': 12}
NUM_EN = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12}
BN_DIG = str.maketrans('0123456789', '০১২৩৪৫৬৭৮৯')


def hits(text, table):
    t = ' ' + text.lower() + ' '
    return [k for k, words in table if any(w.lower() in t for w in words)]


def strip_p(w):
    return re.sub(r'^[“"«(\-]+|[”"»),।?!.:;\-]+$', '', w)


# ---------------------------------------------------------------- characters
def detect_characters(caps, hero_female=False):
    text = ' '.join(c['t'] for c in caps)
    toks = [strip_p(w) for w in text.split()]
    roles = {}
    for rid, (words, name, preset) in ROLES.items():
        for w in toks:
            if any(w.lower() == r.lower() + s for r in words for s in SUFFIX):
                roles[rid] = (name, preset, words); break
    # proper names: frequent sentence-initial tokens that are not stop/role words
    starts = {}
    for c in caps:
        w = strip_p(c['t'].split()[0]) if c['t'].split() else ''
        if w and w.lower() not in STOP and not any(w.lower().startswith(r.lower()) for v in ROLES.values() for r in v[0]):
            starts[w] = starts.get(w, 0) + 1
    counts = {w: sum(1 for t in toks if t == w or (t.startswith(w) and t[len(w):] in SUFFIX)) for w in starts}
    lexwords = [x.strip().lower() for _, ws in MOTIFS + EMOTIONS + TIMES + PLACES for x in ws]
    def is_lex(w):
        return any(w.lower().startswith(x) or x.startswith(w.lower()) for x in lexwords if len(x) >= 2)
    names = [w for w, n in sorted(counts.items(), key=lambda x: -x[1]) if n >= 3 and len(w) >= 2 and not is_lex(w)][:2]
    chars, lex = {}, {}
    if names:
        hero = names[0]
        chars['hero'] = dict(PRESETS['hero_f' if hero_female else 'hero_m'], name=hero); lex['hero'] = [hero]
    else:
        chars['hero'] = dict(PRESETS['hero_f' if hero_female else 'hero_m'], name=''); lex['hero'] = ['আমি', 'I ']
    for i, n in enumerate(names[1:]):
        chars[f'p{i}'] = dict(PRESETS['friend'], shirt=EXTRA_SHIRTS[i % 4], name=n); lex[f'p{i}'] = [n]
    for rid, (name, preset, words) in roles.items():
        chars[rid] = dict(PRESETS[preset], name=name); lex[rid] = words
    return chars, lex


def mentions(text, lex):
    """character ids in order of first appearance in text"""
    found = []
    toks = [strip_p(w).lower() for w in text.split()]
    for i, w in enumerate(toks):
        for cid, roots in lex.items():
            if cid not in [f for f, _ in found] and any(w == r.lower().strip() + s for r in roots for s in SUFFIX):
                found.append((cid, i))
    return [c for c, _ in sorted(found, key=lambda x: x[1])]


# ---------------------------------------------------------------- captions
def highlight(t):
    """wrap 1-2 key words in {}: motif/emotion trigger words first, else the longest content word"""
    words = t.split()
    keys = [w for k, ws in MOTIFS + EMOTIONS for w in ws]
    picked = []
    for i, w in enumerate(words):
        core = strip_p(w)
        if len(core) >= 2 and any(core.lower().startswith(k.strip().lower()) for k in keys if len(k.strip()) >= 2):
            picked.append(i)
    if not picked:
        cand = [(len(strip_p(w)), i) for i, w in enumerate(words) if strip_p(w).lower() not in STOP and len(strip_p(w)) >= 3]
        if cand:
            picked = [max(cand)[1]]
    picked = picked[:1] if len(t) < 22 else picked[:2]
    for i in picked:
        w = words[i]; core = strip_p(w)
        if core:
            words[i] = w.replace(core, '{' + core + '}', 1)
    return ' '.join(words)


def resolve_speakers(caps, lex, chars):
    last = None
    for i, c in enumerate(caps):
        if not c.get('quote'):
            ms = mentions(c['t'], lex)
            if ms:
                last = ms[0]
            c['speaker'] = None
        else:
            prev = caps[i - 1] if i else None
            if prev and not prev.get('quote'):
                ms = mentions(prev['t'], lex)
                c['speaker'] = ms[0] if ms else last
            else:
                c['speaker'] = prev.get('speaker') if prev else last
        if c.get('quote') and c.get('speaker'):
            c['who'] = chars[c['speaker']].get('name') or None


# ---------------------------------------------------------------- numbers
def spoken_number(t):
    d = re.search(r'[\d০-৯]+([.,][\d০-৯]+)?', t)
    if d:
        return d.group(0)
    toks = [strip_p(w).lower() for w in t.split()]
    out, started = '', False
    for w in toks:
        if w in NUM_BN or w in NUM_EN:
            out += str(NUM_BN.get(w, NUM_EN.get(w))); started = True
        elif w in ('দশমিক', 'point') and started:
            out += '.'
        elif started:
            break
    return out if started and any(ch.isdigit() for ch in out) else ''


def clock_hour(t):
    m = re.search(r'(\S+)টা', t)
    if m and m.group(1) in NUM_BN:
        return NUM_BN[m.group(1)]
    m = re.search(r'(\d+)\s*(o\'clock|am|pm)', t.lower())
    return int(m.group(1)) if m else None


def count_before(t, unit_words):
    toks = [strip_p(w).lower() for w in t.split()]
    for i, w in enumerate(toks[1:], 1):
        if any(w.startswith(u) for u in unit_words):
            p = toks[i - 1]
            if p in NUM_BN: return NUM_BN[p]
            if p in NUM_EN: return NUM_EN[p]
            if p.isdigit(): return int(p)
    return None


def short_quote(t, n=12):
    q = re.sub(r'[“”"{}\n]', '', t).strip()
    if q.endswith('?') and len(q) > n:
        return '?'
    words, out = q.split(), ''
    for w in words:
        if len(out) + len(w) + 1 > n:
            break
        out = (out + ' ' + w).strip()
    return (out or q[:n]).rstrip(',।') + ('…' if len(out) < len(q) else '')


# ---------------------------------------------------------------- layout helpers
SIT_Y, STAND_Y, S = 560, 520, 0.8
def person(cid, x, pose='sit', flip=False, expr='neutral', arm=None, **kw):
    e = dict(type='person', char=cid, x=x, y=SIT_Y if pose == 'sit' else STAND_Y, s=S, pose=pose, flip=flip, expr=expr)
    if arm: e['arm'] = arm
    e.update(kw); return e


def furniture(bg_type, xs):
    if bg_type in ('room',):
        return [dict(type='bed', x=min(xs) + 40, y=652, w=max(240, max(xs) - min(xs) + 160))]
    if bg_type in ('living', 'split'):
        return [dict(type='sofa', x=sum(xs) / len(xs) + 20, y=615, w=max(230, max(xs) - min(xs) + 170))]
    if bg_type == 'office':
        return [dict(type='desk', x=360, y=654), dict(type='monitor', x=380, y=446)]
    return []


def head_y(pose):  # top of head bubble position for S=0.8
    return (SIT_Y if pose == 'sit' else STAND_Y) - 330


# ---------------------------------------------------------------- planner
def plan(caps, total, lang='bn', hero_female=False, page_name=''):
    chars, lex = detect_characters(caps, hero_female)
    resolve_speakers(caps, lex, chars)
    for c in caps:
        c['t'] = wrap(highlight(c['t'].replace('"', '“', 1) if c['t'].startswith('"') else c['t']).replace('"', '”'))
    # ---- segmentation
    scenes, cur = [], [caps[0]]
    def setting(c):
        if c.get('quote'):
            return (None, None)
        tx = re.sub(r'[{}]', '', c['t']).replace('\n', ' ')
        return (hits(tx, PLACES) or [None])[0], (hits(tx, TIMES) or [None])[0]
    for c in caps[1:]:
        dur, gap = c['e'] - cur[0]['s'], c['s'] - cur[-1]['e']
        p0, p1 = setting(c), setting(cur[-1])
        mot_new, mot_cur = hits(c['t'], MOTIFS), hits(' '.join(x['t'] for x in cur), MOTIFS)
        new = False
        if (p0[0] or p0[1]) and p0 != p1 and dur > 1.5: new = True
        elif cur[-1].get('quote') and not c.get('quote') and dur > 2.0: new = True
        elif dur > 7.0: new = True
        elif gap >= 0.55 and dur > 3.6: new = True
        elif mot_new and mot_cur and mot_new[0] != mot_cur[0] and dur > 2.6 and not c.get('quote'): new = True
        if new:
            scenes.append(cur); cur = [c]
        else:
            cur.append(c)
    scenes.append(cur)
    # ---- timing (cut in the middle of pauses)
    bounds = [0.0] + [round((scenes[i][-1]['e'] + scenes[i + 1][0]['s']) / 2, 2) for i in range(len(scenes) - 1)] + [total]
    out_scenes, tags, sfx, speak = [], [], [], {}
    state = dict(time='day', place='room', last_tpl=[], last_tag=None)
    TAG = TAG_BN if lang == 'bn' else TAG_EN
    for si, group in enumerate(scenes):
        s, e = bounds[si], bounds[si + 1]
        text = ' '.join(re.sub(r'[{}]', '', c['t']).replace('\n', ' ') for c in group)
        narr = ' '.join(re.sub(r'[{}]', '', c['t']).replace('\n', ' ') for c in group if not c.get('quote'))
        motifs = hits(text, MOTIFS); emos = hits(text, EMOTIONS)
        t_hit, p_hit = hits(narr, TIMES), hits(narr, PLACES)
        if t_hit: state['time'] = t_hit[0]
        if p_hit: state['place'] = p_hit[0]
        elif state['place'] in ('exterior', 'street', 'park') and 'arrive' not in motifs: state['place'] = 'room'
        flash = any(w in text.lower() for w in FLASHBACK)
        ms = mentions(text, lex)
        hero = 'hero'
        others = [m for m in ms if m != hero]
        quotes = [c for c in group if c.get('quote') and c.get('speaker')]
        for c in quotes:
            speak.setdefault(c['speaker'], []).append([c['s'], c['e']])
        progress = s / total
        tpl, els, bg = build_scene(group, s, e, motifs, emos, state, hero, others, quotes, chars, progress, flash, sfx)
        # avoid the same template three times in a row
        state['last_tpl'] = (state['last_tpl'] + [tpl])[-3:]
        out_scenes.append(dict(s=s, e=e, bg=bg, elements=els, note=f'{tpl}: {text[:60]}'))
        tag_key = 'flashback' if flash else (state['place'] if state['place'] != 'room' else state['time'] if state['time'] != 'day' else None)
        if tag_key and tag_key != state['last_tag'] and tpl not in ('emotion',):
            tags.append(dict(s=s, e=e, tag=TAG[tag_key])); state['last_tag'] = tag_key
        elif tags and tags[-1]['e'] == s and tag_key == state['last_tag'] and tpl not in ('emotion',):
            tags[-1]['e'] = e
    for c in caps:
        c.pop('quote', None); c.pop('speaker', None); c.pop('srt_s', None)
        if not c.get('who'): c.pop('who', None)
    sfx.sort(key=lambda x: x[1])
    return dict(meta=dict(total=total, pageName=page_name, lang=lang), characters=chars, captions=caps, speak=speak, tags=tags, sfx=sfx, scenes=out_scenes)


def build_scene(group, s, e, motifs, emos, st, hero, others, quotes, chars, progress, flash, sfx):
    time, place = st['time'], st['place']
    dark_emo = [x for x in emos if x in ('scared', 'shock', 'cry')]
    expr = {'cry': 'cry', 'scared': 'scared', 'shock': 'shock', 'sad': 'sad', 'smile': 'smile', 'angry': 'angry'}.get(emos[0], 'neutral') if emos else 'neutral'
    bgt = {'room': 'room', 'office': 'office', 'classroom': 'classroom', 'shop': 'shop', 'street': 'street', 'park': 'park', 'exterior': 'exterior'}[place]
    bg = dict(type=bgt, time=time if time != 'day' else 'day')
    if flash: bg.update(tint='#a07a3c', tintOpacity=0.25, dark=0.15)
    els = []
    first = group[0]
    def pop(at, kind='pop', v=0.3): sfx.append([kind, round(at, 2), v])
    other = others[0] if others else None
    speaker = quotes[0]['speaker'] if quotes else None
    m0 = motifs[0] if motifs else None
    recent = st['last_tpl']

    # ---------- HUG
    if m0 == 'hug' and other:
        bg = dict(type='plain', color='#E2C49E', glow='#ffd98a')
        pat = any('মাথায়' in c['t'] or 'head' in c['t'].lower() for c in group)
        els += [person(other, 330, 'stand', True, 'sad', 'hug', s=0.85, exprs=[{'t': s, 'expr': 'sad'}, {'t': s + (e - s) * 0.6, 'expr': 'smile'}],
                       arms=[{'t': s + (e - s) * 0.55, 'arm': 'headPat'}] if pat else None),
                person(hero, 190, 'stand', False, 'cry', 'hug', y=540, s=0.74),
                dict(type='particles', kind='hearts', x=270, y=420, count=6)]
        return 'hug', [x for x in els if x is not None], bg

    # ---------- ENDING: lesson card for the last ~10% of the story
    if progress > 0.9 and not quotes:
        m0 = 'idea'
    # ---------- EMOTIONAL CLOSE-UP (dark)
    if dark_emo and not quotes and m0 not in ('door', 'phone', 'paper', 'number', 'idea') and 'emotion' not in recent[-1:]:
        bg = dict(type='plain', color='#1C1917' if dark_emo[0] != 'cry' else '#22284A')
        if m0 == 'heart':
            beats = [round(c['s'] + 0.3, 2) for c in group]
            els += [dict(type='heart', x=270, y=380, s=3.0, beats=beats + [b + 0.5 for b in beats]), dict(type='ecg', x=270, y=600, at=s)]
            for b in beats: pop(b, 'stamp', 0.4)
            return 'emotion', els, dict(type='plain', color='#3B1B22')
        els.append(person(hero, 190, 'stand', False, dark_emo[0] if dark_emo[0] != 'shock' else 'shock', s=1.0, y=555, loop='none' if dark_emo[0] == 'shock' else 'breathe'))
        icon_at = round(first['s'] + 0.3, 2)
        els.append(dict(type='icon', name='exclaim', x=420, y=260, s=1.4, at=icon_at, loop='shake', loopAmp=0.5)); pop(icon_at)
        if dark_emo[0] == 'shock':
            els.append(dict(type='lines', x=190 + 30, y=555 - 280, at=icon_at))
        return 'emotion', els, bg

    # ---------- CLOSE-UPS of objects (variety: not when the last scene was also a close-up)
    has_num = any(spoken_number(re.sub(r'[{}]', '', c['t'])) for c in group)
    if m0 in ('phone', 'number') and not quotes and ('closeup' not in recent[-1:] or has_num):
        num = next((spoken_number(re.sub(r'[{}]', '', c['t'])) for c in group if spoken_number(re.sub(r'[{}]', '', c['t']))), '')
        numc = next((c for c in group if spoken_number(re.sub(r'[{}]', '', c['t']))), None)
        dark = bool(num) or bool(dark_emo)
        ph = dict(type='phone', x=270, y=390, dark=dark, header='Result' if 'result' in ' '.join(c['t'] for c in group).lower() else 'Message', enter='slideUp')
        if num and numc:
            at = round(numc['s'] + (numc['e'] - numc['s']) * 0.5, 2)
            ph.update(big=num.translate(BN_DIG) if BN_DIG and re.search('[ঀ-৿]', numc['t']) else num, bigAt=at, loading=[round(numc['s'], 2), at])
            pop(at, 'stamp', 0.5)
        typ = next((c for c in group if 'number' in c['t'].lower() or 'নম্বর' in c['t'] or 'roll' in c['t'].lower()), None)
        if typ and not num:
            ph['typing'] = dict(text='123456', at=round(typ['s'] + 0.2, 2), cps=4, label='Roll No.')
        if 'কাঁপা' in ' '.join(c['t'] for c in group) or 'scared' in emos:
            ph.update(loop='shake', loopAmp=0.8)
        els.append(ph)
        if dark: els.insert(0, dict(type='spotlight', x=270, y=390, r=280, color='#9fd0f2'))
        return 'closeup', els, dict(type='plain', color='#1C1917' if dark else '#DDCFB7')
    if m0 == 'paper' and 'closeup' not in recent[-1:] and not quotes:
        chunks = [x.strip() for x in re.findall(r'[A-Za-z][A-Za-z.\- ]+', ' '.join(re.sub(r'[{}\n]', ' ', c['t']) for c in group))]
        latin = next((x for x in chunks if len(x.split()) >= 2), '')
        els.append(dict(type='paper', x=270, y=420, title=latin[:22] or '', sub='', footer='', enter='slideUp', loop='sway', loopAmp=0.3))
        short = [c for c in group[1:] if len(re.sub(r'[{}\n]', '', c['t'])) <= 22]
        if short:
            c = short[-1]; txt = re.sub(r'[{}\n।,!]', '', c['t']).strip()
            els.append(dict(type='stamp', x=290, y=590, rot=-10, text=txt, font='latin' if re.match('[A-Za-z]', txt) else 'serif', size=26, at=round(c['s'] + 0.1, 2), enter='stamp'))
            pop(c['s'] + 0.1, 'stamp', 0.5)
        return 'closeup', els, dict(type='plain', color='#2C483B')
    if m0 == 'clock' and len(group) <= 2:
        h = next((clock_hour(re.sub(r'[{}]', '', c['t'])) for c in group if clock_hour(re.sub(r'[{}]', '', c['t']))), 10)
        els.append(dict(type='clock', x=270, y=330, hour=h, minute=0, enter='pop'))
        if len(group) > 1:
            c = group[1]; kw = re.findall(r'\{([^}]+)\}', c['t'])
            if kw:
                els.append(dict(type='pill', x=270, y=560, text=' '.join(kw[:2]), size=40, at=round(c['s'], 2))); pop(c['s'])
        return 'closeup', els, dict(type='plain', color='#E6DDCB')
    if m0 == 'calendar':
        n = next((count_before(re.sub(r'[{}]', '', c['t']), ['দিন', 'মাস', 'বছর', 'day', 'month', 'year', 'week']) for c in group), None)
        if n:
            n = min(n, 12)
            els.append(dict(type='calendar', x=270 - (min(n, 6) * 70 - 12) / 2, y=190, count=n, at=round(first['s'] + 0.3, 2), interval=0.35))
    # ---------- CROWD
    if m0 == 'crowd' and not quotes:
        els += [dict(type='crowd', x=270, y=600, count=5, texts=['…', '?', '…'], at=round(first['s'], 2), laugh='smile' in emos)]
        return 'crowd', els, dict(type='living')
    # ---------- IDEA / LESSON (story ending)
    if (m0 == 'idea' or progress > 0.9) and not quotes:
        kws = [k for c in group for k in re.findall(r'\{([^}]+)\}', c['t'])]
        els += [dict(type='mini', char=hero, x=150, y=640, s=2.1),
                dict(type='icon', name='bulb', x=150, y=330, at=round(first['s'] + 0.2, 2), loop='glow')]
        if other:
            els += [dict(type='mini', char=other, x=400, y=640, s=2.5, flip=True), dict(type='heart', x=400, y=260, s=1.3, at=round(group[-1]['s'], 2), loop='pulse')]
        elif kws:
            els.append(dict(type='title', text='{' + kws[-1] + '}', x=330, y=280, size=56, at=round(group[-1]['s'], 2), enter='fade'))
        pop(first['s'] + 0.2)
        return 'lesson', els, dict(type='plain', color='#E6DDCB')

    # ---------- CHARACTER SCENES (dialogue / solo with props)
    standing = m0 in ('door', 'arrive') or place in ('street', 'park', 'exterior')
    pose = 'stand' if standing else 'sit'
    ppl = [hero] + ([speaker] if speaker and speaker != hero else ([other] if other else []))
    ppl = list(dict.fromkeys([p for p in ppl if p]))[:2]
    if speaker == hero and other and other not in ppl: ppl.append(other)
    xs = [130, 430] if len(ppl) == 2 else [160]
    if m0 == 'door':
        door_close = any('বন্ধ' in c['t'] or 'close' in c['t'].lower() or 'shut' in c['t'].lower() for c in group)
        knock = next((c for c in group if 'knock' in c['t'].lower() or 'ঠক' in c['t']), None)
        dc = next((c for c in group if 'বন্ধ' in c['t'] or 'close' in c['t'].lower()), None)
        door = dict(type='door', x=420, y=610)
        if door_close and dc: door['closeAt'] = round(dc['s'] + 0.2, 2); pop(dc['s'] + 0.1, 'whoosh', 0.3); pop(dc['s'] + 0.7, 'stamp', 0.5)
        els.append(door)
        actor = speaker if (knock and speaker) else (other if knock and other else hero)
        arm = 'knock' if knock else 'reach'
        els.append(person(actor, 200 if knock else 130, 'stand', False, expr if actor == hero else 'neutral', arm))
        if knock:
            for k in range(2):
                at = round(knock['s'] + 0.4 + k * 0.9, 2)
                els.append(dict(type='bubble', text='ঠক ঠক' if re.search('[ঀ-৿]', knock['t']) else 'knock knock', x=470, y=300 - k * 60, at=at, until=round(at + 1.4, 2)))
                pop(at, 'stamp', 0.25); pop(at + 0.3, 'stamp', 0.25)
        for q in quotes:
            els.append(dict(type='bubble', text=short_quote(q['t']), x=280, y=220, at=round(q['s'], 2)))
        return 'door', els, dict(bg, type='room' if bgt in ('room',) else bgt, window=False)
    if m0 == 'arrive' and (others or speaker):
        walker = (others or [speaker])[0]
        bg = dict(type='exterior', time=time if time != 'day' else 'evening')
        els += [person(walker, -60, 'stand', False, 'neutral', loop='walk', move=[{'t': round(first['s'] + 1.6, 2), 'x': 250}], at=s, enter='none'),
                dict(type='bag', x=-50, y=568, move=[{'t': round(first['s'] + 1.6, 2), 'x': 260}], at=s, enter='none')]
        pop(first['s'], 'whoosh', 0.25)
        return 'arrive', els, bg
    for i, p in enumerate(ppl):
        flip = i == 1
        arm = None
        if m0 == 'phonecall' and p == (speaker or (others[0] if others else hero)) : arm = 'phoneEar'
        elif m0 == 'phone' and p == hero: arm = 'phone'
        elif pose == 'sit': arm = 'lap'
        e_ = expr if p == hero else ('smile' if 'smile' in emos else 'neutral')
        el = person(p, xs[i], pose, flip, e_, arm)
        if m0 == 'phonecall' and p == speaker and quotes:
            el['exprs'] = [{'t': s, 'expr': 'neutral'}, {'t': quotes[0]['s'], 'expr': 'sad' if 'sad' in emos else 'neutral'}]
        els.append(el)
        if arm == 'phone':
            els.append(dict(type='phone', x=xs[i] + (120 * S if not flip else -120 * S), y=(SIT_Y if pose == 'sit' else STAND_Y) - 116 * S))
        if arm == 'phoneEar':
            els.append(dict(type='phone', x=xs[i] + (14 * S if not flip else -14 * S), y=(SIT_Y if pose == 'sit' else STAND_Y) - 262 * S, glow=False))
    els = furniture(bgt, xs) + els
    # bubbles for quotes, "?" for questions, "…" for silence, "!" for surprise
    for qi, q in enumerate(quotes):
        idx = ppl.index(q['speaker']) if q['speaker'] in ppl else 0
        bx = xs[idx] + (60 if idx == 0 else -60)
        nxt = quotes[qi + 1]['s'] - 0.15 if qi + 1 < len(quotes) else None
        b = dict(type='bubble', text=short_quote(q['t']), x=min(max(bx, 80), 460), y=head_y(pose) - 10, tail='l' if idx == 0 else 'r', at=round(q['s'], 2), dark='sad' in emos)
        if nxt: b.update(until=round(nxt, 2), exit='fade')
        els.append(b)
        pop(q['s'])
    if m0 == 'silent' and len(ppl) > 1:
        c = next(c for c in group if hits(c['t'], [('silent', dict(MOTIFS)['silent'])]))
        els.append(dict(type='bubble', text='…', x=xs[-1] - 60, y=head_y(pose) - 10, tail='r', at=round(c['s'], 2), until=round(c['e'] + 0.5, 2)))
    if 'shock' in emos:
        c = next((c for c in group if hits(c['t'], [('x', dict(EMOTIONS)['shock'])])), first)
        els.append(dict(type='bubble', text='!', x=xs[0] + 70, y=head_y(pose) - 10, at=round(c['s'] + 0.2, 2))); pop(c['s'] + 0.2)
    if m0 == 'think':
        c = next((c for c in group if hits(c['t'], [('t', dict(MOTIFS)['think'])])), first)
        kw = re.findall(r'\{([^}]+)\}', ' '.join(x['t'] for x in group))
        th = dict(type='thought', x=370, y=260, text=kw[-1] if kw else '?', icon='x' if 'sad' in emos else None, at=round(c['s'] + 0.3, 2))
        if len(ppl) > 1: th.update(x=270, y=190, w=150, h=110, size=24, iconScale=0.7, tailX=-60)
        els.append(th)
        pop(c['s'] + 0.3)
    if m0 == 'lie':
        c = next((c for c in group if 'মিথ্যা' in c['t'] or 'lie' in c['t'].lower()), first)
        els.append(dict(type='icon', name='cross', x=420 if len(ppl) == 1 else 270, y=330 if len(ppl) == 1 else 180, at=round(c['e'], 2))); pop(c['e'])
    if m0 == 'office':
        c = next((c for c in group if 'ছুটি' in c['t'] or 'leave' in c['t'].lower()), group[-1])
        els.append(dict(type='stamp', x=380, y=230, text='ছুটি ✔' if re.search('[ঀ-৿]', c['t']) else 'LEAVE ✔', color='#2C483B', rot=-12, at=round(c['s'] + (c['e'] - c['s']) * 0.6, 2), enter='stamp'))
        pop(c['s'] + (c['e'] - c['s']) * 0.6, 'stamp', 0.4)
    if m0 == 'money':
        els.append(dict(type='icon', name='money', x=400, y=230, at=round(first['s'] + 0.3, 2), loop='float')); pop(first['s'] + 0.3)
    if m0 == 'heart':
        els.append(dict(type='heart', x=420, y=230, s=1.2, beats=[round(c['s'] + 0.3, 2) for c in group], at=round(first['s'], 2)))
    if dark_emo or flash or time in ('night',):
        bg['dark'] = max(bg.get('dark', 0), 0.12)
    return 'dialogue' if quotes else 'solo', els, bg
