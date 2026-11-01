"""Craft rules for short explainer videos, and a check of a project against the ones that can be measured.

The rules come from three places, each named on its rule: the owner's eight high-retention reels (docs/research/REELS-ANALYSIS.md), the
i-hate-editing studio skill (github.com/ranahaani/i-hate-editing: HARD-RULES.md and rules/*.md, measured on real reels), and the
retention-pass method of animated-explainer-skills (github.com/BusyBee3333/animated-explainer-skills), plus the short-form skills listed in
github.com/zhuyansen/awesome-claude-video-skills. Retention is the measure every rule serves.

    rules(area)       the rules Claude (or any director) follows while planning: vt craft rules, MCP module craft.rules
    check(project)    which measurable rules a planned video breaks, with times and a fix each: vt craft check, module craft.check
    fix_hook(...)     the one fix done without asking: the first frame shows what the video is about
"""
from __future__ import annotations

import re
from typing import Any, Optional

# area, id, rule, why, measured (a check below) or not (a rule for the director's judgement), source
RULES: list[dict[str, Any]] = [
    # the hook: the first three seconds decide whether the rest is seen
    {"area": "hook", "id": "hook.frame0", "measured": True, "source": "reels; faceless-shorts make-short; retention-pass",
     "rule": "Frame 0 is fully composed and already shows the subject: something meaningful lands by 0.5 s. No fade from black, no logo, no intro.",
     "why": "Viewers decide in about 1.7 s; frame 0 is also the default thumbnail."},
    {"area": "hook", "id": "hook.topic", "measured": True, "source": "i-hate-editing rules/hooks.md; lab round 1",
     "rule": "The first picture is the topic itself (sleep for a sleep video), not a filler like a thinking face.",
     "why": "The visual, the spoken words and the text must make the same promise; conflicting cues cause an immediate skip."},
    {"area": "hook", "id": "hook.headline", "measured": False, "source": "i-hate-editing rules/hooks.md",
     "rule": "A hook headline of 3 to 5 words (6 at most), stacked, one claim word in the accent colour, arriving with motion within 0.3 s; "
             "it states a promise or a curiosity, not a description. It must make sense with the sound off.",
     "why": "Most viewers watch muted; 'About sleep' describes, 'Sleep is not lost time' promises."},
    {"area": "hook", "id": "hook.type", "measured": False, "source": "i-hate-editing rules/hooks.md",
     "rule": "Pick the hook type first: problem then solution, contrarian ('Everyone says X, but Y'), mistake, numbered list (3 to 7, deliver "
             "exactly N), time-based, or a question that challenges what the viewer thinks. Never 'This changed everything'.",
     "why": "Vague hooks promise nothing specific."},
    {"area": "hook", "id": "hook.loop", "measured": False, "source": "animated-explainer-skills retention-pass",
     "rule": "The hook opens a question that the peak (the second-to-last beat) answers, with the same picture language; the peak names it.",
     "why": "A hook whose loop never closes is the biggest structural leak in explainers."},
    # say it = show it
    {"area": "sync", "id": "sync.numbers_true", "measured": True, "source": "owner rule: never invent facts; lab round 1",
     "rule": "Every number on screen is a number that was said. Never show a figure the voice did not say.",
     "why": "A wrong figure costs trust for the whole video (round 1 showed 4% for 'eighty four percent')."},
    {"area": "sync", "id": "sync.numbers_shown", "measured": True, "source": "retention-pass VO-sync; i-hate-editing rules/proof.md",
     "rule": "Every number that is said is shown within 1.5 s of being said.",
     "why": "When the narrator names something and nothing on screen reacts, retention drops quietly."},
    {"area": "sync", "id": "sync.names_shown", "measured": True, "source": "retention-pass VO-sync; i-hate-editing rules/proof.md",
     "rule": "Every named thing (a company, a person, a place, a product) gets its own picture or label within 1.5 s of its first mention.",
     "why": "Say it = show it."},
    {"area": "sync", "id": "sync.literal", "measured": False, "source": "i-hate-editing rules/hooks.md, rules/scenes.md",
     "rule": "Every picture is the literal object in the line ('country' gets a map), never a metaphor; a picture whose meaning is unsure is "
             "replaced by the spoken word in big type.",
     "why": "A wrong-sense picture (a movie camera for 'screen') reads as an error."},
    # pacing
    {"area": "pacing", "id": "pacing.change", "measured": True, "source": "reels (a picture every 2.3 s); i-hate-editing rules/motion.md",
     "rule": "Something new appears at least every 3 s, inside a scene as well as between scenes; about one picture per 7 spoken words.",
     "why": "A frame that holds still for more than about 3 s loses attention."},
    {"area": "pacing", "id": "pacing.one_at_a_time", "measured": True, "source": "i-hate-editing rules/motion.md",
     "rule": "Never reveal two independent things at the same moment: one thing, a short pause (at least 0.35 s), then the next.",
     "why": "The eye cannot track both, so it tracks neither."},
    {"area": "pacing", "id": "pacing.dwell", "measured": False, "source": "i-hate-editing rules/motion.md",
     "rule": "Everything placed on screen stays at least 1.5 s and at most 3 s as the main thing, except the final card.",
     "why": "Under 1.5 s is a flicker nobody reads; over 3 s is a hold."},
    {"area": "pacing", "id": "pacing.variety", "measured": True, "source": "i-hate-editing rules/motion.md",
     "rule": "Vary the form: never the same scene layout more than 3 times in a row (statement, list, full-frame number, picture, chart...).",
     "why": "Repeating one layout reads as a template even when the words differ."},
    {"area": "pacing", "id": "pacing.interrupts", "measured": False, "source": "retention-pass round 3",
     "rule": "Put one pattern interrupt near 30 % and near 60 % of the runtime: a mood flip, a full-frame number, a direction change.",
     "why": "These are the predicted drop points of a retention curve."},
    {"area": "pacing", "id": "pacing.breath", "measured": False, "source": "lemo-opuscar DIRECTOR.md §7",
     "rule": "Vary the pace: alternate fast and slow, one clear acceleration or slow-down, and one held breath before the turn or the peak.",
     "why": "A film at one even speed has failed."},
    {"area": "pacing", "id": "pacing.read_time", "measured": False, "source": "lemo-opuscar DIRECTOR.md §7",
     "rule": "Text that is meant to be read stays at least (letters / 15 + 1.5) s after it finishes arriving (English); a title card at least 4 s "
             "unless the voice reads it; fast comes from fewer words per screen, never from cutting before people finish reading.",
     "why": "Text cut before it is read is noise."},
    {"area": "facts", "id": "look.legible", "measured": False, "source": "lemo-opuscar DIRECTOR.md §10; design-auditor contrast",
     "rule": "At key moments the subject fills at least a third of the frame height, away from the edges; never a colour on the same colour; "
             "text contrast 4.5:1 or more; captions never cover the subject.",
     "why": "The failures seen most: subject too small, too dark, red on red, subtitles over the subject."},
    {"area": "motion", "id": "style.native_move", "measured": False, "source": "lemo-opuscar DIRECTOR.md §3",
     "rule": "With a film style, use one of its native moves (a fold that becomes a transition, ink that blooms into the next scene) at the peak, "
             "and keep every scene in the style's look; the style's demo film shows grammar, never something to copy.",
     "why": "One move only this medium can do is what people remember."},
    # captions
    {"area": "captions", "id": "captions.chunks", "measured": True, "source": "i-hate-editing rules/captions.md",
     "rule": "Two or three words a caption line, four at most; break at punctuation or a pause of 0.35 s; never end a line on 'the', 'your', 'and'; "
             "no lone word; never split a number from its noun.",
     "why": "Most viewers are muted: the captions are the delivery."},
    {"area": "captions", "id": "captions.timing", "measured": False, "source": "i-hate-editing rules/captions.md",
     "rule": "A caption line appears just after its first word is heard, never before. One emphasis word per line at most, larger and in the accent.",
     "why": "Early captions read as broken sync; when everything is emphasised nothing is."},
    {"area": "captions", "id": "captions.safe", "measured": False, "source": "faceless-shorts brand.md; i-hate-editing rules/framing.md",
     "rule": "On 9:16 keep captions centred near 78 % of the height; nothing important in the bottom 340 px or the right 160 px (platform buttons).",
     "why": "The platform's own interface covers those areas."},
    # motion
    {"area": "motion", "id": "motion.large", "measured": False, "source": "i-hate-editing rules/motion.md",
     "rule": "Err large: a held zoom on a key word 1.18 to 1.20, held 1.3 to 1.6 s; a slow drift on a still 1.00 to 1.05. Never linear easing.",
     "why": "A move the viewer is not sure happened is worse than no move."},
    {"area": "motion", "id": "motion.land_on_word", "measured": False, "source": "i-hate-editing rules/motion.md",
     "rule": "A move lands (finishes) on the word it illustrates; start it early enough.",
     "why": "Landing late feels accidental."},
    # ending
    {"area": "ending", "id": "ending.no_fluff", "measured": True, "source": "faceless-shorts make-short; retention-pass",
     "rule": "End on the payoff. No 'comment below', 'like and subscribe', 'finally', 'that's it' and nothing that announces the end early.",
     "why": "Wrap-up signals make viewers leave before the end; a clean end lets the video loop."},
    {"area": "ending", "id": "ending.loop", "measured": False, "source": "faceless-shorts make-short",
     "rule": "Where it fits, the last frame resolves back into the first so the short replays seamlessly.",
     "why": "Rewatches count as retention."},
    # sound
    {"area": "sound", "id": "sound.bed", "measured": False, "source": "i-hate-editing rules/hooks.md, rules/sound.md",
     "rule": "A quiet continuous bed under the voice; at most one or two stings in the first 4 s, each on a picture change; master near -14 LUFS.",
     "why": "Stings on every word turn into noise."},
    # facts
    {"area": "facts", "id": "facts.never_fabricate", "measured": False, "source": "owner rule; i-hate-editing rules/proof.md",
     "rule": "Never invent a fact, a figure, a quote or a screenshot. A real page, number or product beats any designed card; "
             "a designed card never imitates a screenshot of something real.",
     "why": "A fabricated receipt costs more trust than a missing one."},
]

AREAS = ("hook", "sync", "pacing", "captions", "motion", "ending", "sound", "facts")
FLUFF = re.compile(r"\b(comment below|like and subscribe|subscribe for more|smash (that|the) like|let me know in the comments|that'?s it for today|"
                   r"thanks for watching|see you next time|in conclusion|finally)\b", re.I)


def rules(area: str = "") -> list[dict[str, Any]]:
    return [r for r in RULES if not area or r["area"] == area]


def brief() -> str:
    """The rules as one text for a director's prompt."""
    out = []
    for a in AREAS:
        out.append(a.upper() + ":")
        out += [f"- {r['rule']}" for r in rules(a)]
    return "\n".join(out)


# ----------------------------------------------------------------------------- reading a plan
HIDDEN = {"type", "at_word", "id", "emoji", "name", "style", "color", "src", "media", "props", "set", "pose", "expression", "who", "icon", "shape"}
SHOWN_NUMBERS = {"value", "values", "number", "percent", "amount", "price", "n", "target", "count"}     # numeric fields that are drawn as figures
CODE = re.compile(r"^[0-9a-f]{4,6}(-[0-9a-f]{4,6})*$")                                                   # an emoji code, not text


def _strings(obj: Any, key: str = "") -> list[str]:
    """The text an element shows (layout numbers such as x or scale, emoji codes and props are not shown text)."""
    if isinstance(obj, str):
        return [] if CODE.match(obj) else [obj]
    if isinstance(obj, dict):
        return [s for k, v in obj.items() if k not in HIDDEN for s in _strings(v, k)]
    if isinstance(obj, list):
        return [s for v in obj for s in _strings(v, key)]
    if isinstance(obj, (int, float)) and not isinstance(obj, bool) and key in SHOWN_NUMBERS:
        return [f"{obj:g}"]
    return []


def _numbers_in(texts: list[str]) -> set[float]:
    out = set()
    for t in texts:
        for m in re.finditer(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)", t.translate(str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789"))):
            try:
                out.add(float(m.group(1).replace(",", "")))
            except ValueError:
                pass
    return out


def _shown(sf, words: dict) -> list[dict]:
    """Every element as {t, scene, type, texts, numbers}, in time order."""
    out = []
    for sc in sf.scenes:
        for e in sc.elements:
            w = words.get(getattr(e, "at_word", None))
            if w is None:
                continue
            d = e.model_dump()
            texts = _strings(d)
            out.append({"t": w.start, "scene": sc.id, "type": d.get("type", ""), "texts": texts, "numbers": _numbers_in(texts)})
    return sorted(out, key=lambda x: x["t"])


def _spoken_numbers(tr, beats, language: str) -> list[dict]:
    from .director import roles as RL

    out = []
    for f in RL.analyse(tr, beats, language):
        for n in f.numbers + [{"disp": d, "word": w, "val": None} for d, w in f.years]:
            v = n.get("val")
            if v is None:
                try:
                    v = float(re.sub(r"[^\d.]", "", str(n["disp"]).translate(str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789"))))
                except ValueError:
                    continue
            out.append({"t": n["word"].start, "val": float(v), "disp": n["disp"], "kind": n.get("kind", "year")})
    return out


def _forms(v: float) -> set[float]:
    """A number can be shown scaled: 47 billion as 47, 47,000,000,000 or 47.0; 84 % as 84 or 0.84."""
    s = {v, round(v, 2)}
    for k in (1e3, 1e5, 1e6, 1e7, 1e9, 1e12, 100):                       # thousand, lakh, million, crore, billion, trillion, percent
        s |= {round(v / k, 2), round(v * k, 2)}
    return s


# ----------------------------------------------------------------------------- the check
def check(project) -> dict[str, Any]:
    """The measurable rules this planned video breaks: {"score", "violations": [...], "passed": [...], "skipped": [...]}."""
    from . import context as CX
    from .compose.composer import FUNCTION_WORDS, build_caption_chunks, _is_numberish
    from .visuals import terms as T

    sf = project.scenes()
    tr, beats = project.transcript(), project.beats()
    if sf is None or not sf.scenes:
        return {"score": None, "violations": [], "passed": [], "skipped": ["no plan yet"]}
    meta = project.meta()
    words = {w.id: w for w in tr.kept()}
    kept = tr.kept()
    shown = _shown(sf, words)
    v: list[dict] = []
    passed: list[str] = []

    def bad(rule: str, t0: float, t1: float, says: str, fix: str, severity: str = "major") -> None:
        v.append({"rule": rule, "t0": round(t0, 2), "t1": round(t1, 2), "severity": severity, "says": says, "fix": fix})

    start = kept[0].start if kept else 0.0
    end = kept[-1].end if kept else 0.0
    # hook.frame0 ---------------------------------------------------------------------------------------------------------------------
    first = shown[0]["t"] - start if shown else 99.0
    if first > 0.6:
        bad("hook.frame0", 0.0, first, f"Nothing is on screen until {first:.1f} s.", "Anchor the first picture on the first spoken word.", "critical")
    else:
        passed.append("hook.frame0")
    # hook.topic ----------------------------------------------------------------------------------------------------------------------
    opening = [w.text for w in kept[:14]]
    topic = T.topic_terms((w.text for w in kept), opening, 2)
    ctx = CX.load(project)
    names = [e.name for e in (ctx.entities if ctx else [])]
    keys = {T._stem(T.norm(x)) for x in topic + names}
    early = [s for s in shown if s["t"] - start <= 1.2]
    about = any(T._stem(T.norm(w)) in keys for s in early for t in s["texts"] for w in t.split())
    if topic and not about:
        bad("hook.topic", 0.0, 1.2, f"The first picture is not about the topic ({', '.join(topic)}).",
            f"Open on '{topic[0]}': its picture, or the word in big type, from the first frame.", "critical")
    else:
        passed.append("hook.topic")
    # sync.numbers_true / sync.numbers_shown -------------------------------------------------------------------------------------------
    spoken = _spoken_numbers(tr, beats, meta.language)
    said = set().union(*[_forms(n["val"]) for n in spoken]) if spoken else set()
    for s in shown:
        for x in s["numbers"]:
            if x not in said and round(x, 2) not in said and x not in (0.0, 1.0):
                bad("sync.numbers_true", s["t"], s["t"] + 1.5, f"Scene {s['scene']} shows {x:g}, which was never said.",
                    "Show only the figures the voice says; fix the element or the transcript.", "critical")
    if not any(x["rule"] == "sync.numbers_true" for x in v):
        passed.append("sync.numbers_true")
    for n in spoken:
        near = [s for s in shown if abs(s["t"] - n["t"]) <= 1.5 and (_forms(n["val"]) & s["numbers"])]
        if not near:
            bad("sync.numbers_shown", n["t"], n["t"] + 1.5, f"'{n['disp']}' is said at {n['t']:.1f} s but not shown.",
                "Add a number card (value, big number or chart) on that word.",
                "major" if n["kind"] in ("percent", "money") or n["val"] >= 100 else "minor")     # "ten years ago" in a story need not be a card
    if spoken and not any(x["rule"] == "sync.numbers_shown" for x in v):
        passed.append("sync.numbers_shown")
    # sync.names_shown -----------------------------------------------------------------------------------------------------------------
    for e in (ctx.entities if ctx else []):
        t0 = words[e.mentions[0]].start if e.mentions and e.mentions[0] in words else None
        if t0 is None:
            continue
        key = T.norm(e.name)
        if not any(abs(s["t"] - t0) <= 1.5 and any(key in T.norm(t) for t in s["texts"]) for s in shown):
            bad("sync.names_shown", t0, t0 + 1.5, f"'{e.name}' is named at {t0:.1f} s but nothing on screen names it.",
                "Show its logo, picture or name on that word.")
    if not any(x["rule"] == "sync.names_shown" for x in v):
        passed.append("sync.names_shown")
    # pacing.change ---------------------------------------------------------------------------------------------------------------------
    times = sorted({start} | {s["t"] for s in shown} | {end})
    for a, b in zip(times, times[1:]):
        if b - a > 3.0:
            bad("pacing.change", a, b, f"Nothing new for {b - a:.1f} s.", "Add the next picture, a number or the key word in type inside this stretch.")
    if not any(x["rule"] == "pacing.change" for x in v):
        passed.append("pacing.change")
    # pacing.one_at_a_time ----------------------------------------------------------------------------------------------------------------
    for a, b in zip(shown, shown[1:]):
        if 0 <= b["t"] - a["t"] < 0.35 and a["scene"] == b["scene"]:
            bad("pacing.one_at_a_time", a["t"], b["t"], f"Two things arrive together at {a['t']:.1f} s.", "Move the second to the next word.", "minor")
    if not any(x["rule"] == "pacing.one_at_a_time" for x in v):
        passed.append("pacing.one_at_a_time")
    # pacing.variety --------------------------------------------------------------------------------------------------------------------
    run, prev = 0, None
    for sc in sf.scenes:
        run = run + 1 if sc.layout == prev else 1
        prev = sc.layout
        if run == 4:
            bad("pacing.variety", 0.0, 0.0, f"Four '{sc.layout}' scenes in a row (up to {sc.id}).", "Change the form of one: a list, a big number, a full-frame picture.", "minor")
    if not any(x["rule"] == "pacing.variety" for x in v):
        passed.append("pacing.variety")
    # captions.chunks ---------------------------------------------------------------------------------------------------------------------
    for c in build_caption_chunks(kept, 4, 28, set()):
        ws = [w["text"] for w in c["words"]]
        last = ws[-1].strip(" ,.;:!?\"'").lower()
        if len(ws) > 4 or (len(ws) > 1 and last in FUNCTION_WORDS and not ws[-1].rstrip().endswith((",", ".", "!", "?"))):
            bad("captions.chunks", c["start"], c["end"], f"Caption line '{' '.join(ws)}' breaks the phrase.", "Re-split the line (the composer does it).", "minor")
    if not any(x["rule"] == "captions.chunks" for x in v):
        passed.append("captions.chunks")
    # ending.no_fluff -------------------------------------------------------------------------------------------------------------------
    tail = " ".join(w.text for w in kept[int(len(kept) * 0.8):])
    m = FLUFF.search(tail)
    if m:
        bad("ending.no_fluff", end - 3, end, f"The ending says '{m.group(0)}'.", "End on the payoff line instead.")
    else:
        passed.append("ending.no_fluff")
    weight = {"critical": 20, "major": 8, "minor": 3}
    score = max(0, 100 - sum(weight[x["severity"]] for x in v))
    _ = _is_numberish
    return {"score": score, "violations": sorted(v, key=lambda x: (["critical", "major", "minor"].index(x["severity"]), x["t0"])),
            "passed": passed, "skipped": [r["id"] for r in RULES if not r["measured"]]}


# ----------------------------------------------------------------------------- automatic fixes
def fix_numbers(sf, tr, beats, language: str) -> list[str]:
    """Never show a figure nobody said (owner rule; facts.never_fabricate). Every number an element shows that was not spoken is replaced by
    the spoken number nearest in time (within 3 s, same kind: a percent for a percent); with none near, the element loses that figure
    (a card keeps its label) or, if the figure was all it showed, is removed. Returns what changed."""
    from .schema import Scene

    words = {w.id: w for w in tr.kept()}
    spoken = _spoken_numbers(tr, beats, language)
    said = set().union(*[_forms(n["val"]) for n in spoken]) if spoken else set()
    changed: list[str] = []

    def fmt(v: float) -> str:
        return f"{v:g}" if v < 1e5 else f"{v:,.0f}"

    for sc in sf.scenes:
        keep = []
        for e in sc.elements:
            w = words.get(getattr(e, "at_word", None))
            d = e.model_dump()
            shown = _numbers_in(_strings(d))
            wrong = [x for x in shown if x not in said and round(x, 2) not in said and x not in (0.0, 1.0)]
            if not wrong or w is None:
                keep.append(e)
                continue
            near = sorted((n for n in spoken if abs(n["t"] - w.start) <= 3.0), key=lambda n: abs(n["t"] - w.start))

            def swap(obj, key=""):
                if isinstance(obj, str):
                    def rep(m):
                        x = float(m.group(1).replace(",", ""))
                        if x in said or x in (0.0, 1.0):
                            return m.group(0)
                        pct = obj[m.end():m.end() + 1] == "%"
                        cand = [n for n in near if (n["disp"].endswith("%")) == pct] or near
                        return fmt(cand[0]["val"]) if cand else ""
                    return re.sub(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)", rep, obj)
                if isinstance(obj, dict):
                    return {k: (v if k in HIDDEN else swap(v, k)) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [swap(v, key) for v in obj]
                if isinstance(obj, (int, float)) and not isinstance(obj, bool) and key in SHOWN_NUMBERS and obj not in said and obj not in (0, 1):
                    return near[0]["val"] if near else None
                return obj
            new = swap(d)
            try:
                fixed = type(e).model_validate({k: v for k, v in new.items() if v is not None})
            except Exception:                                                           # noqa: BLE001
                fixed = None
            if fixed is not None and _numbers_in(_strings(fixed.model_dump())) and not [
                    x for x in _numbers_in(_strings(fixed.model_dump())) if x not in said and x not in (0.0, 1.0)]:
                keep.append(fixed)
                changed.append(f"{sc.id}: {sorted(wrong)} -> said figures")
            else:
                changed.append(f"{sc.id}: removed a {d.get('type')} showing unsaid {sorted(wrong)}")
        sc.elements = keep
        if not sc.elements:                                                             # a scene needs something on screen: the spoken key word
            first = next((words[i] for b in sc.beats for bb in beats.beats if bb.id == b for i in bb.word_ids if i in words), None)
            if first is not None:
                from .schema import Keyword

                sc.elements = [Keyword(at_word=first.id, text=first.text.strip(" ,.;:!?।")[:24], style="underline")]
    _ = Scene
    return changed


# ----------------------------------------------------------------------------- the hook fix
def fix_hook(sf, tr, project=None) -> Optional[str]:
    """When the first picture is not about the topic, open on the topic in big type, anchored on the first spoken word (a named thing said in
    the opening, else the strongest topic word). Returns what was added, or None."""
    from .schema import Keyword
    from .visuals import terms as T

    kept = tr.kept()
    if not kept or not sf.scenes:
        return None
    words = {w.id: w for w in kept}
    topic = T.topic_terms((w.text for w in kept), [w.text for w in kept[:14]], 1)
    try:                                                          # a named thing said in the opening ("power bank") beats a single word ("smallest")
        from . import context as CX

        ctx = CX.load(project) if project is not None else None
        opening_ids = {w.id for w in kept[:14]}
        named = [e.name for e in (ctx.entities if ctx else []) if set(e.mentions) & opening_ids]
        if named:
            topic = [named[0]]
    except Exception:
        pass
    if not topic:
        return None
    key = T._stem(T.norm(topic[0]))
    sc = sf.scenes[0]
    early = [e for e in sc.elements if getattr(e, "at_word", None) in words and words[e.at_word].start - kept[0].start <= 1.2]
    if any(key in {T._stem(T.norm(w)) for t in _strings(e.model_dump()) for w in t.split()} for e in early):
        return None
    if sc.stick or sc.backdrop is not None or len(sc.elements) >= 4:
        return None
    if any(getattr(e, "type", "") not in ("sticker", "keyword", "icon", "title", "tag") for e in sc.elements):
        return None          # a cartoon, chart or card is the opening picture; a typed word added to it would sit above it for the whole scene
    label = topic[0][:24]
    el = Keyword(at_word=kept[0].id, text=label, style="underline")   # the topic in big type: a dictionary picture can take the wrong sense ("yield" -> a road sign)
    sc.elements.insert(0, el)
    return f"{el.type} '{label}'"
