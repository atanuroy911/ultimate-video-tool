"""What does each sentence DO in the video? Rule-based, bilingual (Bangla and English), deterministic.

For every beat (sentence) we extract facts (numbers, years, a definition, a contrast, a list, a quote, people, a place, a pose, a mood) and
a primary role (hook, question, definition, cta, price, quote, step, contrast, recap, proof, feature, problem, number, story, claim).
The archetype selector then decides how to show it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..planner.rules import _number_items
from ..schema import Beat, Beats, Transcript, Word
from ..stages.words import norm_token

BN = re.compile(r"[ঀ-৿]")
BN_DIG = {ord(c): str(i) for i, c in enumerate("০১২৩৪৫৬৭৮৯")}


def _lex(s: str) -> set[str]:
    return {w for w in s.split() if w}


# ------------------------------------------------------------------ cue lexicons (English words match exactly, Bangla words as prefixes)
QUESTION_EN = _lex("what why how who whom whose when where which is are do does did can could should would will")
CTA = _lex("subscribe buy order call visit click download join follow share try start get grab book register shop tap "
           "কিনুন অর্ডার কল ভিজিট ক্লিক ডাউনলোড সাবস্ক্রাইব ফলো শেয়ার যোগ চেষ্টা বুক রেজিস্টার আজই এখনই দেখুন করুন")
CTA_PHRASE = ["sign up", "learn more", "get yours", "don't miss", "limited time", "link in", "call us", "order now", "buy now", "আজই", "এখনই", "মিস করবেন না", "লিংকে"]
PRICE = _lex("price cost only just offer discount off sale free deal pay save priced "
             "দাম মূল্য মাত্র অফার ছাড় ডিসকাউন্ট ফ্রি সেল সাশ্রয় টাকায়")
PROOF = _lex("customers users rated rating reviews review trusted award awarded satisfied recommend "
             "গ্রাহক ব্যবহারকারী মানুষ রিভিউ রেটিং বিশ্বস্ত পুরস্কার সন্তুষ্ট স্টার")
FEATURE = _lex("feature features includes include comes built-in offers offer supports lets allows works powerful fast easy simple "
               "ফিচার সুবিধা আছে পাবেন যুক্ত সহজ দ্রুত শক্তিশালী ব্যবহার")
PROBLEM = _lex("problem problems struggle struggling tired hard difficult pain waste frustrating annoying slow expensive stuck "
               "সমস্যা কষ্ট ঝামেলা কঠিন ক্লান্ত বিরক্ত ধীর ব্যয়বহুল")
EXPLAIN = ["because", "causes", "caused by", "we call", "is called", "are called", "known as", "types of", "kinds of", "type of", "due to", "this is why", "as a result", "scientists", "researchers",
           "is born when", "is formed", "form when", "made of", "made up of", "consists of", "for example", "for instance", "in other words", "যার ফলে", "কারণ", "উদাহরণ", "বিজ্ঞানী", "বলা হয়"]
RECAP = ["in summary", "to sum up", "in short", "remember", "key takeaway", "the lesson", "so basically", "to conclude", "moral",
         "সংক্ষেপে", "মোট কথা", "মনে রাখবেন", "সারকথা", "শিক্ষা", "তাহলে"]
STEP_WORDS = _lex("first second third fourth next then finally lastly step firstly secondly thirdly "
                  "প্রথমে প্রথমত দ্বিতীয়ত তৃতীয়ত এরপর তারপর অবশেষে সবশেষে ধাপ")
CONTRAST = _lex("but however although though yet while whereas instead কিন্তু তবে অন্যদিকে যদিও অথচ বরং")
TREND = _lex("grow grew growth rise rose rising increase increased decrease decreased decline declined drop dropped fell fall doubled tripled "
             "বাড়ে বাড়ছে বেড়েছে বৃদ্ধি কমে কমছে কমেছে হ্রাস দ্বিগুণ")
DEFINE_EN = re.compile(r"^(?P<term>.{2,40}?)\s+(?:is|are|means|refers to|stands for|is called|are called|is known as)\s+(?P<meaning>.{6,})$", re.I)
DEFINE_BN = re.compile(r"^(?P<term>.{2,30}?)\s+(?:মানে|হলো|হল|বলতে|অর্থ)\s+(?P<meaning>.{4,})$")
LIST_VERBS = _lex("has have includes include contains contain consists consist are is with of: namely like such")
PREDICATE = _lex("are is was were will can could should would have has had do does did am be been being get gets became become")
CYCLE_CUES = ["cycle", "loop", "again and again", "repeat", "round and round", "circular", "চক্র", "বারবার", "আবার একই"]
HIER_CUES = ["types of", "kinds of", "categories", "consists of", "divided into", "made up of", "split into", "branches into", "ধরনের", "প্রকার", "ভাগে বিভক্ত", "ভাগে ভাগ"]
VENN_CUES = ["both", "in common", "overlap", "shared", "share ", "similarities", "intersection", "উভয়", "মিল আছে", "কমন"]
FUNNEL_CUES = ["funnel", "conversion", "drop off", "drop-off", "narrow", "filtered down", "ফানেল", "কনভার্সন"]
PYRAMID_CUES = ["pyramid", "tiers", "layers", "levels of", "hierarchy of", "foundation", "পিরামিড", "স্তর"]
MATRIX_CUES = ["quadrant", "matrix", "four boxes", "high and low", "2x2", "ম্যাট্রিক্স", "চার ভাগ"]
GAUGE_CUES = ["score", "rating", "risk level", "level of", "scale", "meter", "dial", "speed", "মাত্রা", "স্কোর", "রেটিং"]
FLOW_SPLIT = re.compile(r"\s*(?:\bthen\b|\bleads? to\b|\bresults? in\b|\bafter that\b|\bwhich means\b|→|->|তারপর|ফলে|এরপর)\s*", re.I)
RATIO = re.compile(r"(?P<a>[\d০-৯]+)\s*(?:out of|in every|in|of every|of)\s*(?P<b>[\d০-৯]+)\b", re.I)
RATIO_BN = re.compile(r"(?P<b>[\d০-৯]+)\s*(?:জনের|টির|টা)?\s*মধ্যে\s*(?P<a>[\d০-৯]+)")
WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "half": 1}
RATIO_WORDS = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine)\s+(?:out of|in)\s+(?:every\s+)?(two|three|four|five|six|seven|eight|nine|ten|twenty)\b", re.I)
PRONOUN = _lex("it he she this that they there we you i these those what who which")
DETERMINERS = _lex("the a an this that these those my your his her our their")

# ------------------------------------------------------------------ story lexicons
PERSON = {
    "man": "man", "men": "man", "guy": "man", "father": "man", "dad": "man", "husband": "man", "king": "man", "merchant": "man", "shopkeeper": "man",
    "customer": "man", "farmer": "worker", "villager": "man", "brother": "man", "uncle": "man",
    "woman": "woman", "lady": "woman", "mother": "woman", "mom": "woman", "wife": "woman", "queen": "woman", "sister": "woman", "aunt": "woman",
    "boy": "boy", "son": "boy", "child": "boy", "kid": "boy", "student": "boy", "girl": "girl", "daughter": "girl",
    "grandfather": "elder", "grandmother": "elder", "grandpa": "elder", "grandma": "elder", "old": "elder", "elder": "elder", "watchman": "elder",
    "worker": "worker", "labourer": "worker", "laborer": "worker", "builder": "worker", "driver": "worker",
    "teacher": "teacher", "professor": "teacher", "doctor": "doctor", "nurse": "doctor", "robot": "robot", "ai": "robot",
    "বাবা": "man", "পিতা": "man", "ছেলে": "boy", "ছেলেটা": "boy", "বাচ্চা": "boy", "শিশু": "boy", "মেয়ে": "girl", "মা": "woman", "মহিলা": "woman",
    "নারী": "woman", "পুরুষ": "man", "মানুষ": "man", "লোক": "man", "দোকানদার": "man", "ব্যবসায়ী": "man", "ক্রেতা": "man", "গ্রাহক": "man",
    "বুড়ো": "elder", "বৃদ্ধ": "elder", "দাদা": "elder", "দাদি": "elder", "নানা": "elder", "নানি": "elder", "শ্রমিক": "worker", "কৃষক": "worker",
    "শিক্ষক": "teacher", "ডাক্তার": "doctor", "রোবট": "robot", "ভাই": "man", "বোন": "woman", "বন্ধু": "man", "রাজা": "man", "রানি": "woman",
}
PLACE = {
    "village": "village", "farm": "village", "field": "village", "গ্রাম": "village", "গ্রামে": "village", "মাঠ": "village",
    "market": "market", "bazaar": "market", "বাজার": "market", "হাট": "market",
    "shop": "shop", "store": "shop", "দোকান": "shop", "দোকানে": "shop",
    "home": "home", "house": "home", "room": "home", "kitchen": "home", "বাড়ি": "home", "বাড়িতে": "home", "ঘর": "home", "ঘরে": "home", "বাসা": "home",
    "office": "office", "company": "office", "work": "office", "অফিস": "office", "অফিসে": "office", "কোম্পানি": "office",
    "school": "classroom", "class": "classroom", "classroom": "classroom", "university": "classroom", "স্কুল": "classroom", "ক্লাস": "classroom", "কলেজ": "classroom",
    "street": "street", "road": "street", "city": "street", "town": "street", "রাস্তা": "street", "রাস্তায়": "street", "শহর": "street", "শহরে": "street",
    "forest": "nature", "river": "nature", "mountain": "nature", "garden": "nature", "park": "nature", "jungle": "nature", "বন": "nature", "জঙ্গল": "nature",
    "নদী": "nature", "পাহাড়": "nature", "বাগান": "nature", "studio": "studio", "stage": "studio", "স্টুডিও": "studio",
}
POSE = {
    "point": "point", "show": "point", "showed": "point", "explain": "point", "said": "point", "told": "point", "দেখাল": "point", "দেখিয়ে": "point", "বলল": "point", "বললেন": "point",
    "think": "think", "thought": "think", "wonder": "think", "wondered": "think", "confused": "think", "ভাবল": "think", "ভাবতে": "think", "ভাবছে": "think",
    "go": "walk", "went": "walk", "walk": "walk", "walked": "walk", "run": "walk", "ran": "walk", "came": "walk", "come": "walk", "গেল": "walk", "যায়": "walk", "হাঁটল": "walk", "এল": "walk", "আসল": "walk",
    "hello": "wave", "wave": "wave", "waved": "wave", "greet": "wave", "greeted": "wave", "নমস্কার": "wave", "সালাম": "wave", "হাই": "wave",
    "happy": "celebrate", "laughed": "celebrate", "smiled": "celebrate", "won": "celebrate", "celebrate": "celebrate", "success": "celebrate", "হাসল": "celebrate", "খুশি": "celebrate", "জিতল": "celebrate",
    "sad": "sad", "cry": "sad", "cried": "sad", "lost": "sad", "ashamed": "sad", "embarrassed": "sad", "কাঁদল": "sad", "দুঃখ": "sad", "লজ্জা": "sad", "কষ্ট": "sad",
    "shrug": "shrug", "careless": "shrug", "dont": "shrug", "don't": "shrug", "unsure": "shrug", "জানি না": "shrug", "অবহেলা": "shrug",
    "sat": "sit", "sit": "sit", "sitting": "sit", "বসল": "sit", "বসে": "sit",
}
EXPRESSION = {
    "happy": "happy", "laughed": "happy", "smiled": "happy", "joy": "happy", "pleased": "happy", "proud": "happy", "খুশি": "happy", "হাসল": "happy", "আনন্দ": "happy", "গর্ব": "happy",
    "sad": "sad", "cry": "sad", "cried": "sad", "upset": "sad", "embarrassed": "sad", "ashamed": "sad", "worried": "sad", "দুঃখ": "sad", "কাঁদল": "sad", "চিন্তিত": "sad", "লজ্জা": "sad",
    "angry": "angry", "furious": "angry", "shouted": "angry", "রাগ": "angry", "রেগে": "angry",
    "surprised": "surprised", "shocked": "surprised", "amazed": "surprised", "suddenly": "surprised", "অবাক": "surprised", "হঠাৎ": "surprised",
    "confused": "thinking", "wondered": "thinking", "thought": "thinking", "puzzled": "thinking", "ভাবল": "thinking", "বুঝতে": "thinking",
}


def _has(tokens: list[str], lex: set[str]) -> bool:
    for t in tokens:
        if t in lex:
            return True
        if BN.search(t) and len(t) >= 3 and any(t.startswith(x) for x in lex if BN.search(x) and len(x) >= 3):
            return True
    return False


def _has_phrase(text: str, phrases: list[str]) -> bool:
    return any(p in text for p in phrases)


def _lookup(tokens: list[str], table: dict[str, str]) -> list[str]:
    out = []
    for t in tokens:
        v = table.get(t)
        if not v and BN.search(t):
            # a Bangla word with a case ending: নদীতে -> নদী
            for n in range(len(t) - 1, 1, -1):
                v = table.get(t[:n])
                if v:
                    break
        if v and v not in out:
            out.append(v)
    return out


@dataclass
class Facts:
    beat: Beat
    words: list[Word]
    text: str
    dur: float
    role: str = "claim"
    roles: set[str] = field(default_factory=set)
    numbers: list[dict] = field(default_factory=list)
    years: list[tuple[str, Word]] = field(default_factory=list)
    question: bool = False
    definition: Optional[tuple[str, str, Word]] = None
    contrast: Optional[tuple[str, str, Word]] = None
    items: list[tuple[str, Word]] = field(default_factory=list)
    quote: Optional[str] = None
    persons: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    place: Optional[str] = None
    pose: str = "stand"
    expression: str = "neutral"
    speaker: Optional[str] = None
    trend: bool = False
    ratio: Optional[tuple[int, int]] = None
    cues: set[str] = field(default_factory=set)
    flow: list[str] = field(default_factory=list)
    first: bool = False
    last: bool = False


def _split_items(ws: list[Word]) -> list[tuple[str, Word]]:
    """'rent, costs and profit' -> [('rent', w), ('costs', w), ('profit', w)] (needs 3+ short items)."""
    parts: list[list[Word]] = [[]]
    for w in ws:
        t = norm_token(w.text)
        parts[-1].append(w)
        if w.text.rstrip().endswith((",", "،", ";")):
            parts.append([])
        elif t in ("and", "or", "এবং", "আর", "ও", "অথবা") and len(parts[-1]) > 1:
            parts[-1].pop()
            parts.append([])
    parts = [p for p in parts if p]
    if len(parts) < 3:
        return []
    items = []
    for k, p in enumerate(parts):
        if k == 0 and len(p) > 2:                    # "The pyramid has goals" / "types of investing: savings": the list starts after the verb or the colon
            colon = next((i for i, w in enumerate(p) if w.text.endswith(":")), None)
            verb = max((i for i, w in enumerate(p[:-1]) if norm_token(w.text) in LIST_VERBS), default=None)
            cut = colon if colon is not None else verb
            if cut is not None and cut < len(p) - 1:
                p = p[cut + 1:] if colon is None else p[cut + 1:]
        if k == len(parts) - 1:                      # "... and fuel are all affected": the last item stops where the predicate starts
            cut = next((i for i, w in enumerate(p) if i > 0 and norm_token(w.text) in PREDICATE), None)
            if cut:
                p = p[:cut]
        core = [w for w in p if norm_token(w.text) not in DETERMINERS]
        if not core or len(core) > 4:
            return []
        items.append((" ".join(w.text.strip(" ,.।?!;،") for w in core), core[0]))
    return items


def analyse(tr: Transcript, beats: Beats, language: str = "bn") -> list[Facts]:
    words = tr.by_id()
    out: list[Facts] = []
    n = len(beats.beats)
    for bi, b in enumerate(beats.beats):
        ws = [words[i] for i in b.word_ids if i in words]
        toks = [norm_token(w.text) for w in ws]
        text = b.text.strip()
        low = text.lower()
        f = Facts(beat=b, words=ws, text=text, dur=b.end - b.start, first=bi == 0, last=bi == n - 1, speaker=getattr(b, "speaker", None))
        f.question = "?" in text or "؟" in text or (bool(toks) and toks[0] in QUESTION_EN and text[:1].isupper() and not BN.search(text)) or \
            bool(re.search(r"(কি|কী|কেন|কীভাবে|কিভাবে|কত|কোথায়|কখন|কে|কাকে)[\s?]*$", text)) or (BN.search(text) is not None and "?" in text)
        # numbers (years are kept apart)
        nums = _number_items(ws, language)
        for it in nums:
            plain = re.sub(r"[^\d]", "", it["disp"].translate(BN_DIG))
            if it["kind"] == "plain" and plain.isdigit() and 1500 <= int(plain) <= 2100 and len(plain) == 4:
                f.years.append((it["disp"], it["word"]))
            else:
                f.numbers.append(it)
        # definition
        m = (DEFINE_BN if BN.search(text) else DEFINE_EN).match(text.rstrip(" .।!"))
        if m and not f.question and text[:1].isupper() and m.group("term").split()[0].lower() not in {"and", "but", "so", "or", "of", "because", "which", "then"}:
            term_words = m.group("term").split()
            if 1 <= len(term_words) <= 4 and norm_token(term_words[0]) not in PRONOUN and not (f.numbers and len(term_words) > 3):
                core = [t for t in term_words if t.lower() not in DETERMINERS]
                if core:
                    first = next((w for w in ws if norm_token(w.text) == norm_token(core[0])), ws[0])
                    f.definition = (" ".join(core)[:28], m.group("meaning").strip()[:90], first)
        # contrast: "A, but B" inside one sentence, or a sentence that starts with "but ..." against the one before it
        for i, t in enumerate(toks):
            if t in CONTRAST and 2 <= i <= len(ws) - 3:
                left = " ".join(w.text for w in ws[:i]).strip(" ,.।")
                right = " ".join(w.text for w in ws[i + 1:]).strip(" ,.।")
                f.contrast = (left[:60], right[:60], ws[i])                 # tidied (word boundaries, no hanging words) by the builder
                break
            if t in CONTRAST and i == 0 and out and len(ws) >= 3:
                f.contrast = (out[-1].text.strip(" ,.।?!")[:60], " ".join(w.text for w in ws[1:]).strip(" ,.।")[:60], ws[0])
                break
        f.items = _split_items(ws)
        q = re.search(r"[“\"‘]([^”\"’]{12,90})[”\"’]", text)
        if q:
            f.quote = q.group(1).strip()
        f.persons = _lookup(toks, PERSON)
        f.place = (_lookup(toks, PLACE) or [None])[0]
        poses = _lookup(toks, POSE)
        f.pose = poses[0] if poses else "stand"
        exp = _lookup(toks, EXPRESSION)
        f.expression = exp[0] if exp else "neutral"
        if language != "bn":
            f.names = [w.text.strip(" ,.!?;:'\"") for i, w in enumerate(ws) if i > 0 and w.text[:1].isupper() and norm_token(w.text) not in PRONOUN
                       and len(w.text.strip(" ,.!?;:")) > 2 and norm_token(w.text) not in {"i", "the", "a"}][:2]
        f.trend = _has(toks, TREND)
        for name, lex in (("cycle", CYCLE_CUES), ("hierarchy", HIER_CUES), ("venn", VENN_CUES), ("funnel", FUNNEL_CUES), ("pyramid", PYRAMID_CUES), ("matrix", MATRIX_CUES),
                          ("gauge", GAUGE_CUES)):
            if _has_phrase(low, lex):
                f.cues.add(name)
        m = RATIO.search(text.translate(BN_DIG)) or RATIO_BN.search(text.translate(BN_DIG))
        if m:
            a, b = int(m.group("a")), int(m.group("b"))
            if 0 < a < b <= 1000:
                f.ratio = (a, b)
        else:
            mw = RATIO_WORDS.search(text)
            if mw and WORD_NUM[mw.group(1).lower()] < WORD_NUM.get(mw.group(2).lower(), 20 if mw.group(2).lower() == "twenty" else 0):
                f.ratio = (WORD_NUM[mw.group(1).lower()], WORD_NUM.get(mw.group(2).lower(), 20))
        chunks = [c.strip(" ,.।") for c in FLOW_SPLIT.split(text) if c.strip(" ,.।")]
        if len(chunks) >= 3 and not f.question:
            f.flow = chunks[:5]

        roles: set[str] = set()
        if f.question:
            roles.add("question")
        if f.definition:
            roles.add("definition")
        english = not BN.search(text)
        imperative = bool(toks) and (toks[0] in CTA or (len(toks) > 1 and toks[0] in {"please", "now", "and", "just"} and toks[1] in CTA))
        if (imperative if english else _has(toks, CTA)) or _has_phrase(low, CTA_PHRASE):
            roles.add("cta")
        if _has(toks, PRICE) and (any(n["kind"] == "money" for n in f.numbers) or "free" in toks or "ফ্রি" in toks):
            roles.add("price")
        if f.quote:
            roles.add("quote")
        if _has(toks, STEP_WORDS):
            roles.add("step")
        if f.contrast:
            roles.add("contrast")
        if _has_phrase(low, RECAP):
            roles.add("recap")
        if _has_phrase(low, EXPLAIN):
            roles.add("explain")
        if _has(toks, PROOF):
            roles.add("proof")
        if _has(toks, FEATURE):
            roles.add("feature")
        if _has(toks, PROBLEM):
            roles.add("problem")
        if f.numbers:
            roles.add("number")
        if f.years:
            roles.add("date")
        if f.items:
            roles.add("list")
        if f.persons or f.place:
            roles.add("story")
        f.roles = roles
        for r in ("question", "definition", "cta", "price", "quote", "step", "contrast", "recap", "proof", "list", "date", "number", "feature", "problem", "story"):
            if r in roles:
                f.role = r
                break
        else:
            f.role = "claim"
        if f.first and f.role in ("claim", "story", "problem"):
            f.role = "hook"
        out.append(f)
    return out
