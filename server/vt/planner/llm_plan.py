"""Scene planning by a local language model (Ollama), used automatically when Claude is not connected.

The rule planner draws the base plan (layout, numbers, transitions). The model then does the one thing it is good at: for every
sentence it chooses WHICH words deserve a picture and WHICH picture fits the word in its sentence. Each word comes with a short
list of real candidates from the visual library, and the reply is forced into a fixed JSON shape in which a picture can only be
one of those candidates, so the model can choose well but cannot invent or break anything. Code then builds the scene elements.
A scene the model fails on keeps the rule planner's version.
"""
from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Optional

from .. import art, llm
from ..house_rules import prompt as house_rules
from ..schema import Beats, Scene, ScenesFile, Transcript, Word, validate_scenes
from ..stages.words import norm_token
from ..visuals import emoji as emo
from .catalogue import all_icon_names
from .rules import _group_beats, plan_rules

MOODS = ["story", "finance", "business", "tech", "education", "health", "kids", "motivation", "news", "nature", "food", "sports", "other"]
CHUNK = 3                                   # scenes per model call

BRIEF_SCHEMA = {
    "type": "object",
    "properties": {"topic": {"type": "string", "maxLength": 60}, "summary": {"type": "string", "maxLength": 300},
                   "mood": {"type": "string", "enum": MOODS}, "characters": {"type": "array", "items": {"type": "string", "maxLength": 30}, "maxItems": 5},
                   "place": {"type": "string", "maxLength": 40}},
    "required": ["topic", "summary", "mood"],
}


def story_brief(tr: Transcript, language: str) -> dict:
    """What the video is about, in one call. Gives every later call the story's context."""
    text = " ".join(w.text for w in tr.words)[:6000]
    msgs = [
        {"role": "system", "content": "You read the transcript of a short explainer or story video and describe it. Answer in English as JSON."},
        {"role": "user", "content": f"Transcript ({'Bangla/Banglish' if language == 'bn' else 'English'}):\n{text}\n\nGive the topic, a one-sentence summary, the overall mood/category, "
                                    "the main characters (people or animals, if any) and the place (if any)."},
    ]
    return llm.chat_json(msgs, BRIEF_SCHEMA, max_tokens=500, temperature=0.1)


def _content_words(ws: list[Word], limit: int = 9) -> list[Word]:
    from ..visuals.picker import is_content

    out, seen = [], set()
    for w in ws:
        t = norm_token(w.text)
        if t in seen or not is_content(w):
            continue
        seen.add(t)
        out.append(w)
    return out[:limit]


def _options(words: list[Word], sentence: str) -> dict[str, list[dict]]:
    """Per word id: the real pictures it could mean. Found by the word alone AND by the word in its sentence, so 'watch' in
    'bring me the watch' offers the wrist watch as well as the eyes."""
    import numpy as np

    from ..visuals.lexicon import Lexicon
    from ..visuals.picker import _embedder
    from ..visuals.search import search

    lex, emb = Lexicon.get(), _embedder()
    sv = emb.encode([sentence[:400]], prefix="query: ", max_len=96)[0] if emb is not None and lex.ok else None
    out: dict[str, list[dict]] = {}
    for w in words:
        key = norm_token(w.text)
        ids: list[str] = []
        m = None
        try:
            m = lex.lookup(w.text)                                   # the dictionary's own answer first: it is the default
            if m and m.usable():
                if m.sticker:
                    ids.append(f"emoji:{m.sticker}")
            if emb is not None and lex.ok:
                wv = emb.encode([key], prefix="query: ", max_len=16)[0]
                q = wv + 0.6 * sv if sv is not None else wv
                q = q / (np.linalg.norm(q) + 1e-9)
                for vec in (wv, q):                                  # by the word alone, and by the word in its sentence; weak matches are dropped
                    ids += [v for v, _, z in lex.nearest(vec, 5, "sticker") if z >= 3.6]
        except Exception:
            pass
        seen, opts = set(), []
        for vid in ids:
            if vid in seen:
                continue
            seen.add(vid)
            if vid.startswith("emoji:"):
                k = emo.emoji_key(vid[6:])
                label = emo.label(k) if k else ""
                if k and not (ROLE.search(label) and not ROLE.search(key)):      # no singers/astronauts/etc. for a plain "man"
                    opts.append({"id": k, "kind": "sticker", "label": label})
            else:
                opts.append({"id": vid, "kind": "icon", "label": vid.split(":", 1)[1].replace("-", " ")})
        if not opts and m and m.usable() and m.line and m.z_line >= 6.0 and m.line not in seen:     # line icons only when no colour picture exists
            opts.append({"id": m.line, "kind": "icon", "label": m.line.split(":", 1)[1].replace("-", " ")})
        if opts:
            opts[0] = {**opts[0], "label": opts[0]["label"] + " (default)"}
        out[w.id] = opts[:8]
    return out


def _worth(word: str, topics) -> bool:
    """A word gets a picture when it is a key term, or when the dictionary is sure of its picture ("lazy" -> sleepy face). "okay", "close", "glowing" get none."""
    from ..visuals import terms as T
    from ..visuals.lexicon import Lexicon
    from ..visuals.picker import STRONG_Z

    if T.is_key_term(word, topics):
        return True
    m = Lexicon.get().lookup(word)
    return bool(m and m.usable() and (m.source == "seed" or m.best >= STRONG_Z))


UNPICTURABLE = set("black white red blue green yellow orange purple pink brown grey gray area areas region regions part parts kind sort type types".split())   # colours and vague nouns draw nothing useful

ROLE = re.compile(r"\b(singer|artist|scientist|astronaut|firefighter|pilot|judge|farmer|cook|mechanic|technologist|office worker|health worker|factory worker|"
                  r"teacher|student|mage|fairy|genie|vampire|zombie|elf|ninja|superhero|villain|santa|mx claus|person in tuxedo|bride|prince|princess|merperson|merman|mermaid)\b", re.I)


def _schema(beat_ids: list[str], word_ids: list[str], choice_ids: list[str]) -> dict:
    pic = {"type": "object", "properties": {"word_id": {"type": "string", "enum": word_ids}, "choice": {"type": "string", "enum": choice_ids + ["text"]}},
           "required": ["word_id", "choice"]}
    sent = {"type": "object", "properties": {"beat": {"type": "string", "enum": beat_ids}, "pictures": {"type": "array", "maxItems": 3, "items": pic}},
            "required": ["beat", "pictures"]}
    return {"type": "object", "properties": {"sentences": {"type": "array", "minItems": len(beat_ids), "maxItems": len(beat_ids), "items": sent}}, "required": ["sentences"]}


SYSTEM = """You are the picture editor of a faceless story/explainer video. A voice reads each sentence while pictures appear on screen.
For every sentence decide which words to SHOW as a picture and which option is the right picture.

Rules
- Pick up to 3 words per sentence: people (son, father), things (watch, cupboard), places (village, market), feelings and qualities
  (lazy, worried, careless), actions that can be drawn (run, sleep). Show every important idea, in the order spoken: "His son was lazy and
  careless" -> son, lazy, careless (three pictures).
- Each word lists OPTIONS as id=name. Choose the option that matches the meaning IN THIS SENTENCE ("watch" next to "cupboard" is the wrist
  watch, not eyes; "called his son" is shouting, not a phone). Never choose an option that only shares a letter or a loose idea.
- The first option is the dictionary's default; keep it unless another clearly fits this sentence better.
- If the word matters but NO option clearly depicts it, answer "text" (the word is shown in big letters) - never force a loose match. If it does not matter, leave it out.
- Skip filler words, pronouns, numbers and words that cannot be pictured. Never pick the same word twice.

""" + house_rules("plan")


def _els_for(chosen: list[dict], pattern: int, words: dict[str, Word], long_scene: bool) -> list[dict]:
    from .rules import _visual_elements

    els: list[dict] = []
    for n, pw in enumerate(chosen):
        txt = pw["text"]
        if pw["choice"] == "text":
            els.append({"type": "keyword", "text": txt[:30], "style": ("underline", "highlight", "stamp")[(pattern + n) % 3], "at_word": pw["word_id"]})
        elif n == 0:
            st = pw["choice"] if pw["kind"] == "sticker" else None
            line = pw["choice"] if pw["kind"] == "icon" else None
            els += _visual_elements(SimpleNamespace(text=txt, word_id=pw["word_id"], sticker=st, line=line, kind="sticker" if st else "icon"),
                                    pattern, words[pw["word_id"]], long_scene)
        else:
            els.append({"type": "sticker", "emoji": pw["choice"], "label": txt[:26], "at_word": pw["word_id"]} if pw["kind"] == "sticker"
                       else {"type": "icon", "name": pw["choice"], "label": txt[:26], "at_word": pw["word_id"]})
    return els


def plan_llm(tr: Transcript, beats: Beats, theme: str, language: str, audio=None, progress=None, brief: Optional[dict] = None,
             base: Optional[ScenesFile] = None, picks=None) -> ScenesFile:
    """Rule plan as the base; the model chooses the pictures. Raises LLMUnavailable if the model stops answering."""
    say = progress or (lambda f, m: None)
    from ..visuals.picker import pick_visuals

    if base is None:
        picks = picks or pick_visuals(tr, beats, audio)
        base = plan_rules(tr, beats, theme, audio=audio, picks=picks, language=language)
    words = tr.by_id()
    from ..visuals import terms as T

    topics = T.topic_counts(w.text for w in words.values())
    beat_by = {b.id: b for b in beats.beats}
    scenes = [s.model_dump(exclude_none=True) for s in base.scenes]
    groups = [[beat_by[b] for b in s["beats"] if b in beat_by] for s in scenes]       # the base plan's own scenes, whoever drew it
    if any(not g for g in groups):
        return base
    icons = all_icon_names()
    brief = brief or story_brief(tr, language)
    brief_txt = f"Story: {brief.get('summary', '')} Characters: {', '.join(brief.get('characters', []) or []) or 'none'}. Place: {brief.get('place', '') or 'n/a'}."

    numeric = {i for i, s in enumerate(scenes) if any(e["type"] in ("value_card", "big_number", "compare") for e in s.get("elements", []))}
    todo = [i for i in range(len(groups)) if i not in numeric and scenes[i].get("archetype") in (None, "picture")]   # charts, cartoons, media... keep their rule-built design
    prev: list[str] = []
    designed, failed = 0, 0
    for ci in range(0, len(todo), CHUNK):
        chunk = todo[ci: ci + CHUNK]
        say(0.05 + 0.9 * ci / max(1, len(todo)), f"Choosing pictures, scenes {chunk[0] + 1}-{chunk[-1] + 1} of {len(groups)}")
        sent_lines, opt_lines, beat_ids, word_ids, choice_ids = [], [], [], [], []
        opts_by_word: dict[str, list[dict]] = {}
        for gi in chunk:
            for b in groups[gi]:
                ws = [words[w] for w in b.word_ids if w in words]
                cw = _content_words(ws)
                pairs = {}                                            # "black hole", "solar system": one drawing, offered on the second word
                for w1, w2 in zip(ws, ws[1:]):
                    key = art.lookup(f"{w1.text} {w2.text}")
                    if key:
                        pairs[w2.id] = key
                        cw = [w for w in cw if w.id != w1.id]
                        if all(w.id != w2.id for w in cw):
                            cw.append(w2)
                cw = [w for w in cw if norm_token(w.text) not in UNPICTURABLE and (w.id in pairs or _worth(w.text, topics))]
                if not cw:
                    continue
                o = _options(cw, b.text)
                for wid, key in pairs.items():
                    if wid in o or any(w.id == wid for w in cw):
                        o[wid] = [{"id": key, "kind": "sticker", "label": art.label(key) + " (default)"}] + [x for x in o.get(wid, []) if x["id"] != key][:5]
                opts_by_word.update(o)
                beat_ids.append(b.id)
                sent_lines.append(f"[{b.id}] {b.text}")
                for w in cw:
                    if o.get(w.id):
                        word_ids.append(w.id)
                        opt_lines.append(f"  [{b.id}] {w.id}:{w.text.strip(' ,.।?!')} -> " + ", ".join(f"{x['id']}={x['label']}" for x in o[w.id]))
                        choice_ids += [x["id"] for x in o[w.id] if x["id"] not in choice_ids]
        if not beat_ids or not word_ids:
            continue
        user = (f"{brief_txt}\n\nSENTENCES:\n" + "\n".join(sent_lines) + "\n\nWORDS AND OPTIONS (sentence, word id:word -> option id=name):\n" +
                "\n".join(opt_lines) + f"\n\nAnswer for each of the {len(beat_ids)} sentences, in order.")
        resp = None
        for _ in range(2):
            try:
                resp = llm.chat_json([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], _schema(beat_ids, word_ids, choice_ids), max_tokens=1200)
                break
            except llm.LLMUnavailable:
                continue
        if not resp:
            failed += 1
            if failed >= 2:
                raise llm.LLMUnavailable("The local AI stopped answering.")
            continue
        by_beat = {s.get("beat"): s.get("pictures", []) for s in resp.get("sentences", [])}
        for gi in chunk:
            chosen: list[dict] = []
            for b in groups[gi]:
                for p in by_beat.get(b.id, []):
                    wid, ch = p.get("word_id"), p.get("choice")
                    if wid not in b.word_ids or any(c["word_id"] == wid for c in chosen):
                        continue
                    opt = next((x for x in opts_by_word.get(wid, []) if x["id"] == ch), None)
                    if ch != "text" and not opt:
                        continue                                          # not one of this word's real options
                    if ch == "text" and not T.is_key_term(words[wid].text, topics):
                        continue                                          # big type is for key terms only ("radiation", not "fine")
                    if opt and (opt["id"] in prev[-3:] or any(c["choice"] == opt["id"] for c in chosen)):
                        continue
                    chosen.append({"word_id": wid, "text": words[wid].text.strip(" ,.।?!"), "choice": ch, "kind": opt["kind"] if opt else "text"})
            chosen = chosen[:3]
            if not chosen:
                continue
            chosen.sort(key=lambda c: words[c["word_id"]].start)
            dur = beat_by[groups[gi][-1].id].end - beat_by[groups[gi][0].id].start
            els = _els_for(chosen, gi, words, dur >= 6.5)
            els.sort(key=lambda e: words[e["at_word"]].start)
            cand = dict(scenes[gi])
            cand["elements"] = els[:5]
            cand["caption"] = {"highlight_words": [chosen[0]["word_id"]]}
            try:
                Scene.model_validate(cand)
                trial = ScenesFile.model_validate({"theme": theme, "planner": "llm", "scenes": [cand if k == gi else scenes[k] for k in range(len(scenes))]})
            except Exception:
                continue
            if validate_scenes(trial, tr, beats, icons):
                continue
            scenes[gi] = cand
            designed += 1
            prev += [c["choice"] for c in chosen if c["choice"] != "text"]
    if failed and not designed:
        raise llm.LLMUnavailable("The local AI did not answer.")
    say(1.0, f"{designed} of {len(groups)} scenes designed by the local AI")
    return ScenesFile.model_validate({"theme": theme, "planner": "llm" if designed else "rules", "scenes": scenes})
