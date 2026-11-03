"""Context: one shared reading of the whole video that every other part of the app uses.

Without it each feature guesses on its own from a single word: "Amazon" became a superhero emoji, a scene kept two thirds of its frame empty, a baby's babble became "farm animals".
`context.json` holds what the video is about (topic, field), the named things in it (with their type and where they are said), one line per sentence (idea, role, importance, what
it continues or contrasts with, what a picture should show), the sections, and the facts the speaker really said (numbers, dates, lists).

Two layers, both always saved with their `source`:
  * rules  - always available, offline: the roles analysis, word statistics, capitalised names, number and list extraction;
  * ai     - when an AI is available (Ollama, Claude, OpenAI): one structured request per window of the transcript, then a strict check: an entity must really be said where it says it is
             said, a fact must be in the transcript, a sentence must exist. Anything that fails is dropped and the rules reading stays. The AI can never add a fact that was not said.
The owner's corrections (an entity that is really a place, a name that is not a name) are kept in `context.overrides.json` and applied on top of every rebuild.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any, Optional

from pydantic import BaseModel, Field

from .schema import Beats, Transcript
from .util import now_iso, read_json, write_json

ENTITY_TYPES = ["company", "product", "person", "place", "country", "language", "organisation", "event", "concept", "name"]
ROLES = ["hook", "claim", "question", "definition", "number", "date", "list", "step", "contrast", "recap", "proof", "problem", "story", "feature", "price", "quote", "cta", "personal", "example", "opinion"]
RELATIONS = ["none", "continues", "explains", "contrasts", "example", "answers"]
MOODS = ["story", "finance", "business", "tech", "education", "health", "kids", "motivation", "news", "nature", "food", "sports", "other"]
WINDOW_BEATS = 45                         # sentences read per AI request
OVERLAP = 4


class Entity(BaseModel):
    name: str
    type: str = "name"
    mentions: list[str] = Field(default_factory=list)          # word ids where it is said (first word of each mention)
    note: str = ""
    source: str = "rules"


class SentenceCtx(BaseModel):
    beat: str
    idea: str = ""
    role: str = "claim"
    importance: int = 1                                        # 0 filler, 1 normal, 2 important, 3 the point of the video
    relation: str = "none"
    rel_to: Optional[str] = None
    intent: str = ""                                           # what a picture should show to help this sentence
    source: str = "rules"


class Section(BaseModel):
    start_beat: str
    end_beat: str
    title: str = ""


class Fact(BaseModel):
    kind: str                                                  # number | date | list | name
    text: str
    word_ids: list[str] = Field(default_factory=list)


class Context(BaseModel):
    version: int = 1
    source: str = "rules"                                      # rules | ai
    language: str = "en"
    topic: str = ""
    summary: str = ""
    domain: list[str] = Field(default_factory=list)
    mood: str = "other"
    entities: list[Entity] = Field(default_factory=list)
    sentences: list[SentenceCtx] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)             # what could not be done and why (AI unavailable, window rejected ...)
    generated_at: str = ""
    hash: str = ""                                             # of the transcript it was made from: when it differs, the reading is out of date

    def entity(self, name: str) -> Optional[Entity]:
        n = _key(name)
        return next((e for e in self.entities if _key(e.name) == n), None)

    def sentence(self, beat: str) -> Optional[SentenceCtx]:
        return next((s for s in self.sentences if s.beat == beat), None)

    def section_of(self, beat: str) -> Optional[int]:
        order = [s.beat for s in self.sentences]
        if beat not in order:
            return None
        i = order.index(beat)
        for k, sec in enumerate(self.sections):
            if sec.start_beat in order and sec.end_beat in order and order.index(sec.start_beat) <= i <= order.index(sec.end_beat):
                return k
        return None

    def to_brief(self) -> dict:
        """The shape the planners already take as `brief` (topic, summary, mood, characters, place)."""
        people = [e.name for e in self.entities if e.type == "person"][:5]
        place = next((e.name for e in self.entities if e.type in ("place", "country")), "")
        b = {"topic": self.topic[:60], "summary": self.summary[:300], "mood": self.mood if self.mood in MOODS else "other", "characters": people}
        if place:
            b["place"] = place[:40]
        return b


def _key(s: str) -> str:
    return re.sub(r"[^\wঀ-৿]+", " ", unicodedata.normalize("NFC", s).casefold()).strip()


# ----------------------------------------------------------------------------------------------------------------------- rules
CONNECTORS = ("and", "also", "then", "so", "because", "but", "plus", "which", "that's", "this is why", "and then", "as a result", "however", "for example", "for instance")
SECTION_MARKERS = ("first", "second", "third", "next", "finally", "lastly", "moving on", "now let's", "now let us", "let's talk about", "step one", "step two", "number one", "number two", "chapter")
STOP_CAPS = {"i", "i'm", "i've", "i'll", "i'd", "the", "a", "an", "and", "but", "so", "or", "if", "when", "while", "this", "that", "these", "those", "it", "its", "we", "you", "they", "he", "she",
             "my", "our", "your", "their", "his", "her", "what", "why", "how", "who", "where", "which", "yes", "no", "okay", "ok", "well", "now", "then", "there", "here", "in", "on", "at", "to", "for",
             "of", "with", "from", "by", "as", "is", "are", "was", "were", "be", "do", "did", "does", "can", "could", "would", "should", "will", "just", "actually", "however", "also", "because",
             "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
             "november", "december"}
DOMAINS = {
    "finance": {"money", "profit", "revenue", "income", "price", "cost", "invest", "investment", "bank", "tax", "salary", "budget", "loan", "savings", "financial", "financially", "dollar", "dollars",
                "taka", "stock", "stocks", "inflation", "interest", "wealth", "cash", "payment", "expenses", "margin", "টাকা", "ব্যাংক", "দাম", "লাভ", "বিনিয়োগ", "আয়"},
    "e-commerce": {"amazon", "ebay", "shop", "shopping", "sell", "selling", "buy", "buying", "order", "orders", "product", "products", "store", "ecommerce", "customer", "customers", "shipping",
                   "listing", "listings", "seller", "marketplace", "inventory", "daraz", "পণ্য", "বিক্রি", "অর্ডার", "দোকান"},
    "tech": {"software", "app", "apps", "code", "computer", "internet", "ai", "data", "algorithm", "website", "digital", "online", "phone", "technology", "program", "cloud", "server", "টেক", "ইন্টারনেট"},
    "health": {"health", "doctor", "disease", "medicine", "body", "exercise", "diet", "sleep", "hospital", "patient", "stress", "বাস্থ্য", "স্বাস্থ্য", "ডাক্তার", "রোগ"},
    "education": {"learn", "learning", "student", "students", "school", "teacher", "study", "lesson", "course", "exam", "university", "শিক্ষা", "ছাত্র", "স্কুল", "পড়া"},
    "food": {"food", "cook", "cooking", "recipe", "eat", "meal", "restaurant", "kitchen", "খাবার", "রান্না"},
    "travel": {"travel", "trip", "tour", "hotel", "flight", "country", "city", "visit", "journey", "ভ্রমণ"},
    "business": {"business", "company", "startup", "customer", "market", "marketing", "brand", "employee", "team", "manager", "ব্যবসা", "কোম্পানি"},
    "sports": {"game", "team", "player", "match", "score", "goal", "win", "season", "football", "cricket", "খেলা"},
    "story": {"once", "story", "king", "village", "boy", "girl", "mother", "father", "grandmother", "forest", "গল্প", "রাজা", "গ্রাম"},
}
DOMAIN_MOOD = {"finance": "finance", "e-commerce": "business", "business": "business", "tech": "tech", "health": "health", "education": "education", "food": "food", "sports": "sports", "story": "story", "travel": "other"}


def term_ok(t: str, topics=None) -> bool:
    """A word that can stand for a topic or a picture: not a function word, not a contraction, not among the most common words of the language."""
    from .visuals import terms as T

    t = T.norm(t)
    if len(t) < 3 or "'" in t or "’" in t or t in STOP_CAPS:
        return False
    if re.search(r"[ঀ-৿]", t):
        return True
    return T.zipf(t) < 6.2 and T.is_key_term(t, topics)


def _words_of(tr: Transcript) -> dict:
    return {w.id: w for w in tr.kept()}


def find_names(tr: Transcript, beats: Beats) -> list[Entity]:
    """Capitalised words and runs of them in the middle of a sentence (or said more than once): names of companies, people and places in text that is written with capitals."""
    words = _words_of(tr)
    cands: list[tuple[str, str, str]] = []                      # (name, first word id, beat id)
    for b in beats.beats:
        seq = [words[i] for i in b.word_ids if i in words]
        i = 0
        while i < len(seq):
            t = seq[i].text.strip(" ,.;:!?\"'()[]")
            low = t.lower()
            camel = t[:1].islower() and any(c.isupper() for c in t[1:]) and len(t) > 3          # eBay, iPhone, bKash: written with a capital inside
            if (t[:1].isupper() or camel) and len(t) > 1 and low not in STOP_CAPS and not re.search(r"[ঀ-৿]", t):
                j = i
                run = [t]
                while j + 1 < len(seq):
                    n = seq[j + 1].text.strip(" ,.;:!?\"'()[]")
                    if n[:1].isupper() and len(n) > 1 and n.lower() not in STOP_CAPS and not seq[j].text.rstrip().endswith((",", ".", ";", ":", "!", "?")):
                        run.append(n)
                        j += 1
                    else:
                        break
                cands.append((" ".join(run), seq[i].id, b.id))
                i = j + 1
            else:
                i += 1
    from .visuals import terms as T

    firsts = set()                                              # first words of sentences: of a beat, or after . ! ?
    for b in beats.beats:
        seq = [i for i in b.word_ids if i in words]
        for n_, i in enumerate(seq):
            if n_ == 0 or words[seq[n_ - 1]].text.rstrip().endswith((".", "!", "?", "।")):
                firsts.add(i)
    count = Counter(_key(n) for n, _, _ in cands)
    always_first = {k for k in count if all(w in firsts for n, w, _ in cands if _key(n) == k)}
    out: dict[str, Entity] = {}
    for name, wid, bid in cands:
        k = _key(name)
        sentence_start = wid in firsts
        if sentence_start and count[k] < 2 and len(name.split()) < 2:
            continue                                            # "Amazon" at the start of a sentence, said once: probably just a capital letter
        if k in always_first and len(name.split()) < 2 and T.zipf(name.lower()) >= 3.0 and T.noun_share(name.lower()) < 0.4:
            continue                                            # "Skip one night ... Skip a week": a verb that only ever starts a sentence ("Amazon" is a noun and stays)
        e = out.setdefault(k, Entity(name=name, type="name"))
        e.mentions.append(wid)
    return list(out.values())


def _intent(f, key_term: Optional[str]) -> str:
    if f.numbers:
        n = f.numbers[0]
        return f"a big number card: {n['disp']}" + (f" ({n['label']})" if n.get("label") else "")
    if f.items:
        return "the items as a list: " + ", ".join(t for t, _ in f.items[:4])
    if f.question:
        return "the question as big text"
    if f.definition:
        return f"the term '{f.definition[0]}' and its meaning"
    if key_term:
        return f"a picture of {key_term}"
    return ""


def rules_context(tr: Transcript, beats: Beats, language: str = "en") -> Context:
    from .director import roles as RL
    from .visuals import terms as T

    words = _words_of(tr)
    tokens = [T.norm(w.text) for w in words.values()]
    topics = T.topic_counts(w.text for w in words.values())
    # topic and field ------------------------------------------------------------------------------------------------------------------
    opening = [words[i].text for i in beats.beats[0].word_ids if i in words] if beats.beats else []
    key = T.topic_terms((w.text for w in words.values()), opening, 3)
    dom_score = {d: sum(1 for t in tokens if t in lex) for d, lex in DOMAINS.items()}
    domain = [d for d, n in sorted(dom_score.items(), key=lambda kv: -kv[1]) if n >= 2][:3]
    first = beats.beats[0].text.strip() if beats.beats else ""
    ctx = Context(source="rules", language=language, topic=("about " + ", ".join(key)) if key else "", summary=" ".join(b.text.strip() for b in beats.beats[:2])[:240], domain=domain,
                  mood=DOMAIN_MOOD.get(domain[0], "other") if domain else "other", generated_at=now_iso())
    ctx.entities = find_names(tr, beats)
    # sentences ------------------------------------------------------------------------------------------------------------------------
    facts = RL.analyse(tr, beats, language)
    prev: Optional[str] = None
    for f in facts:
        low = f.text.lower().lstrip(" \"'")
        rel, rel_to = "none", None
        if f.contrast:
            rel, rel_to = "contrasts", prev
        elif any(low.startswith(c + " ") or low == c for c in CONNECTORS) and prev:
            rel, rel_to = "continues", prev
        kt = next((w.text.strip(" ,.;:!?।") for w in f.words if term_ok(w.text, topics)), None)
        imp = 2 if (f.first or f.role in ("hook", "definition", "number", "contrast", "question", "cta", "price", "proof")) else 1
        if f.role == "recap" or f.last:
            imp = max(imp, 2)
        ctx.sentences.append(SentenceCtx(beat=f.beat.id, idea=f.text[:90], role=f.role, importance=imp, relation=rel, rel_to=rel_to, intent=_intent(f, kt)))
        for it in f.numbers:
            ctx.facts.append(Fact(kind="number", text=it["disp"], word_ids=[it["word"].id]))
        for disp, w in f.years:
            ctx.facts.append(Fact(kind="date", text=disp, word_ids=[w.id]))
        if f.items:
            ctx.facts.append(Fact(kind="list", text=", ".join(t for t, _ in f.items), word_ids=[w.id for _, w in f.items]))
        prev = f.beat.id
    ctx.sections = find_sections(tr, beats, ctx.sentences)
    return ctx


def find_sections(tr: Transcript, beats: Beats, sentences: list[SentenceCtx]) -> list[Section]:
    """New section where the vocabulary changes (a window of sentences shares few words with the one before) or the speaker says so ('next', 'finally', 'step two')."""
    from .visuals import terms as T

    words = _words_of(tr)
    bags = []
    for b in beats.beats:
        bags.append({T.norm(words[i].text) for i in b.word_ids if i in words and len(T.norm(words[i].text)) > 3})
    cuts = [0]
    for i in range(3, len(beats.beats) - 2):
        if i - cuts[-1] < 4:
            continue
        before = set().union(*bags[max(0, i - 3):i])
        after = set().union(*bags[i:i + 3])
        union = before | after
        marker = any(beats.beats[i].text.lower().lstrip(" \"'").startswith(m) for m in SECTION_MARKERS)
        if marker or (union and len(before & after) / len(union) < 0.04 and len(before) >= 6 and len(after) >= 6):
            cuts.append(i)
    out = []
    for k, start in enumerate(cuts):
        end = (cuts[k + 1] - 1) if k + 1 < len(cuts) else len(beats.beats) - 1
        out.append(Section(start_beat=beats.beats[start].id, end_beat=beats.beats[end].id, title=""))
    return out


# ----------------------------------------------------------------------------------------------------------------------- AI pass
AI_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string", "maxLength": 40, "description": "what the video is about as a short noun phrase of 2 to 5 words (a title, e.g. 'Why sleep matters'); never a sentence about the video"},
        "summary": {"type": "string", "maxLength": 300},
        "domain": {"type": "array", "items": {"type": "string", "maxLength": 24}, "maxItems": 4},
        "mood": {"type": "string", "enum": MOODS},
        "entities": {"type": "array", "maxItems": 40, "items": {"type": "object", "properties": {
            "name": {"type": "string", "maxLength": 60}, "type": {"type": "string", "enum": ENTITY_TYPES},
            "word_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 12}, "note": {"type": "string", "maxLength": 80}}, "required": ["name", "type", "word_ids"]}},
        "sentences": {"type": "array", "items": {"type": "object", "properties": {
            "beat": {"type": "string"}, "idea": {"type": "string", "maxLength": 100}, "importance": {"type": "integer", "minimum": 0, "maximum": 3},
            "relation": {"type": "string", "enum": RELATIONS}, "rel_to": {"type": "string"}, "intent": {"type": "string", "maxLength": 120}}, "required": ["beat", "idea", "importance"]}},
        "sections": {"type": "array", "items": {"type": "object", "properties": {
            "start_beat": {"type": "string"}, "end_beat": {"type": "string"}, "title": {"type": "string", "maxLength": 60}}, "required": ["start_beat", "end_beat"]}},
    },
    "required": ["topic", "summary", "entities", "sentences", "sections"],
}

SYSTEM = ("You read the transcript of a video and describe what it is about so that pictures can be chosen well. Answer only with JSON. "
          "Use only what the speaker actually says: never add a fact, a name or a number that is not in the text. "
          "Entities are named things (companies, products, people, places, countries, languages). For each entity give the ids of the words where it is said "
          "(the ids in square brackets) and decide its type from the whole video: 'Amazon' in a video about selling online is a company, in a video about rainforests a place. "
          "For each sentence give its idea in a few words, an importance from 0 (filler) to 3 (the point of the video), how it relates to an earlier sentence, "
          "and what a picture should show to help the viewer understand it (a concrete thing, never a vague mood). Sections are runs of sentences about one subject. Always list the entities (an empty list when there are none) and the sections.")


def _window_prompt(tr: Transcript, beats: list, carried: str, language: str) -> str:
    words = _words_of(tr)
    lines = []
    for b in beats:
        lines.append(f"{b.id}: " + " ".join(f"{words[i].text}[{i}]" for i in b.word_ids if i in words))
    head = f"Language: {'Bangla/Banglish' if language == 'bn' else 'English'}.\n"
    if carried:
        head += f"What the whole video is about so far: {carried}\n"
    return head + "Transcript, one sentence per line (sentence id, then each word with its id in brackets):\n" + "\n".join(lines) + "\n\nDescribe it."


def repair_window(data: Any, tr: Transcript, beats: list) -> Any:
    """Models often answer with the sentence's text, or a bare number, where the id ('b7') was asked for. Map those back to the right sentence; leave anything else alone (the check decides)."""
    if not isinstance(data, dict):
        return data
    words = _words_of(tr)
    ids = {b.id for b in beats}
    text = {b.id: _key(" ".join(words[i].text for i in b.word_ids if i in words)) for b in beats}

    def fix(v: Any) -> Any:
        if not isinstance(v, str) or v in ids:
            return v
        t = v.strip()
        if re.fullmatch(r"\d+", t) and f"b{t}" in ids:
            return f"b{t}"
        if re.fullmatch(r"[Bb]\s*-?\d+", t) and "b" + re.sub(r"\D", "", t) in ids:
            return "b" + re.sub(r"\D", "", t)
        lead = re.match(r"\s*[Bb]\s*-?(\d+)\b", t)                  # "b1-your brain washes away ...": the id, then the sentence
        if lead and f"b{lead.group(1)}" in ids:
            return f"b{lead.group(1)}"
        k = _key(t)
        if len(k) >= 6:
            hit = [i for i, tx in text.items() if tx.startswith(k[:40]) or k.startswith(tx[:40]) or (len(k) >= 12 and k[:40] in tx)]
            if len(hit) == 1:
                return hit[0]
        return v
    for s in data.get("sentences", []) or []:
        if isinstance(s, dict):
            s["beat"] = fix(s.get("beat"))
            if s.get("rel_to"):
                s["rel_to"] = fix(s["rel_to"])
    for sec in data.get("sections", []) or []:
        if isinstance(sec, dict):
            sec["start_beat"], sec["end_beat"] = fix(sec.get("start_beat")), fix(sec.get("end_beat"))
    if isinstance(data.get("sections"), list):                      # sections are optional: one that points nowhere is dropped, not a reason to throw the answer away
        data["sections"] = [s for s in data["sections"] if isinstance(s, dict) and s.get("start_beat") in ids and s.get("end_beat") in ids]
    return data


def check_window(data: dict, tr: Transcript, beats: list) -> list[str]:
    """Everything the AI claims must be true of the transcript. Returns the problems found (an empty list: accepted)."""
    words = _words_of(tr)
    ids = {b.id for b in beats}
    bag = {b.id: " ".join(words[i].text for i in b.word_ids if i in words) for b in beats}
    allw = {i for b in beats for i in b.word_ids}
    errs: list[str] = []
    for e in data.get("entities", []):
        bad = [w for w in e.get("word_ids", []) if w not in allw]
        if bad:
            errs.append(f"entity '{e['name']}' uses word ids that are not in this part: {bad[:3]}")
            continue
        said = " ".join(_key(words[w].text) for w in e.get("word_ids", []) if w in words)
        nm = _key(e["name"]).split()
        if nm and not all(any(t == s or s.startswith(t) or t.startswith(s) for s in said.split()) for t in nm[:2]):
            errs.append(f"entity '{e['name']}' is not said at the words given ({said[:40]!r})")
    for s in data.get("sentences", []):
        if s["beat"] not in ids:
            errs.append(f"sentence {s['beat']} does not exist")
    for sec in data.get("sections", []):
        if sec["start_beat"] not in ids or sec["end_beat"] not in ids:
            errs.append(f"section {sec['start_beat']}-{sec['end_beat']} does not exist")
    return errs[:10]


def _merge_ai(ctx: Context, part: dict, tr: Transcript, beats: list) -> Context:
    words = _words_of(tr)
    ids = {b.id for b in beats}
    allw = {i for b in beats for i in b.word_ids}
    if part.get("topic") and not ctx.topic.startswith("AI:"):
        ctx.topic = part["topic"]
    if part.get("summary"):
        ctx.summary = part["summary"]
    if part.get("domain"):
        ctx.domain = part["domain"][:4]
    if part.get("mood") in MOODS:
        ctx.mood = part["mood"]
    for e in part.get("entities", []):
        wids = [w for w in e.get("word_ids", []) if w in allw]
        if not wids:
            continue
        have = ctx.entity(e["name"])
        if have:                                              # the AI decides the type; the mentions from both are kept
            have.type, have.source, have.note = e["type"], "ai", e.get("note", "")
            have.mentions = sorted(set(have.mentions) | set(wids), key=lambda w: int(re.sub(r"\D", "", w) or 0))
        else:
            ctx.entities.append(Entity(name=e["name"], type=e["type"], mentions=wids, note=e.get("note", ""), source="ai"))
    by = {s.beat: s for s in ctx.sentences}
    for s in part.get("sentences", []):
        if s["beat"] not in ids or s["beat"] not in by:
            continue
        cur = by[s["beat"]]
        cur.idea = s.get("idea") or cur.idea
        cur.importance = int(s.get("importance", cur.importance))
        if s.get("relation") in RELATIONS:
            cur.relation = s["relation"]
        rt = s.get("rel_to")
        cur.rel_to = rt if rt in by and rt != cur.beat else cur.rel_to
        if s.get("intent"):
            cur.intent = s["intent"]
        cur.source = "ai"
    if part.get("sections"):
        order = [x.beat for x in ctx.sentences]
        keep = [x for x in ctx.sections if not (x.start_beat in ids and x.end_beat in ids)]
        add = [Section(**{k: sec[k] for k in ("start_beat", "end_beat", "title") if k in sec}) for sec in part["sections"] if sec["start_beat"] in order and sec["end_beat"] in order]
        ctx.sections = sorted(keep + add, key=lambda x: order.index(x.start_beat))
    return ctx


def ai_context(ctx: Context, tr: Transcript, beats: Beats, language: str, provider=None) -> Context:
    """Improve the rules reading with the AI, window by window; a window the check rejects is kept as the rules had it (and noted)."""
    from .ai import complete_json

    bl = beats.beats
    if not bl:
        return ctx
    step = WINDOW_BEATS - OVERLAP
    carried = ""
    ok = 0
    for start in range(0, len(bl), step):
        part_beats = bl[start:start + WINDOW_BEATS]
        prompt = _window_prompt(tr, part_beats, carried, language)
        try:
            data = complete_json(prompt, AI_SCHEMA, system=SYSTEM, provider=provider, retries=1, max_tokens=3500, temperature=0.1, repair=lambda d, pb=part_beats: repair_window(d, tr, pb),
                                 check=lambda d, pb=part_beats: check_window(d, tr, pb))
        except Exception as e:
            ctx.notes.append(f"AI window {start // step + 1} skipped: {type(e).__name__}: {str(e)[:120]}")
            continue
        _merge_ai(ctx, data, tr, part_beats)
        ok += 1
        carried = f"{ctx.topic}. {ctx.summary}"[:300]
        if start + WINDOW_BEATS >= len(bl):
            break
    if ok:
        ctx.source = "ai"
        ctx.entities = [e for e in ctx.entities if e.source != "rules" or len(e.mentions) >= 2]          # a capitalised word the AI did not confirm and that is said once: just a capital letter
    return ctx


# ----------------------------------------------------------------------------------------------------------------------- overrides and files
def apply_overrides(ctx: Context, ov: Optional[dict]) -> Context:
    """The owner's corrections: {"entities": {"<name key>": {"type": "place"} | {"remove": true}}, "topic": "..."}; they win over rules and AI, on every rebuild."""
    if not ov:
        return ctx
    if ov.get("topic"):
        ctx.topic = ov["topic"]
    for name, fix in (ov.get("entities") or {}).items():
        e = ctx.entity(name)
        if fix.get("remove"):
            ctx.entities = [x for x in ctx.entities if _key(x.name) != _key(name)]
        elif e and fix.get("type") in ENTITY_TYPES:
            e.type, e.source = fix["type"], "owner"
        elif not e and fix.get("type") in ENTITY_TYPES and fix.get("word_ids"):
            ctx.entities.append(Entity(name=name, type=fix["type"], mentions=list(fix["word_ids"]), source="owner"))
    return ctx


def build(tr: Transcript, beats: Beats, language: str, *, use_ai: bool = True, overrides: Optional[dict] = None, provider=None) -> Context:
    ctx = rules_context(tr, beats, language)
    if use_ai:
        try:
            ctx = ai_context(ctx, tr, beats, language, provider)
        except Exception as e:                                    # no AI, or it failed: the rules reading stands
            ctx.notes.append(f"AI not used: {type(e).__name__}: {str(e)[:120]}")
    return apply_overrides(ctx, overrides)


def current_hash(project) -> str:
    from .util import file_hash

    return file_hash(project.transcript_path, project.beats_path, overrides_path(project))


def is_stale(project, ctx: Optional[Context]) -> bool:
    return bool(ctx) and bool(ctx.hash) and ctx.hash != current_hash(project)


def path(project):
    return project.dir / "context.json"


def overrides_path(project):
    return project.dir / "context.overrides.json"


def load(project) -> Optional[Context]:
    d = read_json(path(project))
    if not d:
        return None
    try:
        return Context.model_validate(d)
    except Exception:
        return None


def save(project, ctx: Context) -> None:
    write_json(path(project), ctx.model_dump())
