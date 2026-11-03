"""The rule director: a story from the words, not a rotation of gestures.

From the transcript, its beats and the shared context reading (Phase 10) it decides, in this order, and writes it as a Video Script:
  1. the cast: every named person is a character with a look of their own; other people come from the words that name them ("the old man", "the owner", "her mother"); animals and things that
     act become emoji actors; a video with no one in it gets a host and a curious learner so that people can talk to each other;
  2. the places: from the words and the topic, a different place for a different part of the story, with time of day and weather when the words say so;
  3. what happens in every sentence: events anchored to the exact word that makes them ("ran" -> a run, "gave it back" -> a hand-over to the other person, "afraid" -> hiding, a number -> a sign),
     with who does it and to whom worked out from the names and pronouns;
  4. the gaps: any stretch longer than GAP seconds with nothing new gets a varied reaction, never the same thing twice in a row, never only talking;
  5. camera, transitions and sound: varied, and tied to what happens (a new place -> a whip, a number -> a zoom, the end -> a pull back).
The same structure is what the AI passes fill in (vt/script/director.py); this version needs no AI and is deterministic for a given text.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

from ..schema import Beats, ScenesFile, Transcript
from . import catalogue as C
from .models import Action, Camera, Character, CharStyle, ScriptScene, SetDef, SfxCue, VideoScript

GAP = 2.2                                   # seconds: the longest stretch with nothing new (the owner's rule is 3 s; this leaves room for where words fall)
MAX_ACTIONS = 22

# ----------------------------------------------------------------------------------------------------------------------- word banks
MOTION = {"ran": "run", "run": "run", "running": "run", "rushed": "run", "hurried": "run", "raced": "run", "sprinted": "run", "chased": "chase", "walked": "walk_to", "went": "walk_to", "came": "walk_to",
          "arrived": "walk_to", "entered": "walk_to", "left": "walk_out", "exited": "walk_out", "jumped": "jump", "jump": "jump", "leaped": "jump", "climbed": "jump", "fell": "fall", "tripped": "fall",
          "slipped": "fall", "crept": "sneak", "sneaked": "sneak", "tiptoed": "sneak", "followed": "follow", "hid": "hide", "hide": "hide", "peeked": "peek", "flew": "fly", "danced": "dance", "dance": "dance"}
FEEL = {"laughed": "laugh", "laugh": "laugh", "laughing": "laugh", "giggled": "laugh", "funny": "laugh", "smiled": "react:happy", "happy": "react:happy", "joy": "react:happy", "glad": "react:happy",
        "proud": "react:happy", "delighted": "celebrate", "won": "celebrate", "win": "celebrate", "success": "celebrate", "celebrated": "celebrate", "cheered": "celebrate", "clapped": "clap",
        "applause": "clap", "cried": "cry", "cry": "cry", "crying": "cry", "sad": "react:sad", "sadly": "react:sad", "lost": "react:sad", "angry": "argue", "argued": "argue", "fought": "argue",
        "shouted": "argue", "mad": "argue", "scared": "react:scared", "afraid": "react:scared", "fear": "react:scared", "terrified": "react:scared", "surprised": "react:surprised",
        "shocked": "react:surprised", "amazed": "react:surprised", "suddenly": "mark:exclaim", "wow": "mark:exclaim", "confused": "react:confused", "wondered": "think", "thought": "think",
        "think": "think", "wonder": "think", "idea": "mark:idea", "decided": "mark:idea", "realised": "mark:idea", "realized": "mark:idea", "tired": "yawn", "sleepy": "yawn", "slept": "yawn",
        "sleep": "yawn", "yawned": "yawn", "hugged": "hug", "hug": "hug", "thanked": "bow", "thank": "bow", "thanks": "bow", "bowed": "bow", "hello": "wave", "hi": "wave", "welcome": "wave",
        "bye": "wave", "goodbye": "wave", "waved": "wave", "love": "mark:heart", "loved": "mark:heart", "worried": "mark:sweat", "nervous": "mark:sweat", "problem": "mark:sweat",
        "careful": "mark:sweat", "danger": "mark:exclaim", "warning": "mark:exclaim"}
DOING = {"found": "lift", "picked": "lift", "lifted": "lift", "carried": "carry", "gave": "give", "give": "give", "handed": "give", "returned": "give", "passed": "give", "sold": "give", "paid": "give",
         "took": "lift", "bought": "carry", "threw": "throw", "tossed": "throw", "ate": "eat", "eat": "eat", "eating": "eat", "drank": "eat", "tasted": "eat", "cooked": "eat", "called": "phone",
         "phoned": "phone", "typed": "type", "wrote": "write_board", "pointed": "point", "showed": "point", "looked": "look_at", "saw": "look_at", "watched": "look_at", "pushed": "push",
         "pulled": "pull", "counted": "count", "explained": "explain", "shook": "handshake", "agreed": "handshake", "met": "handshake", "asked": "say", "said": "say", "replied": "say", "told": "say"}
PLACES = {  # word -> set kind
    "kitchen": "kitchen", "cook": "kitchen", "cooked": "kitchen", "cooking": "kitchen", "meal": "kitchen", "recipe": "kitchen", "dinner": "kitchen", "lunch": "kitchen", "breakfast": "kitchen",
    "school": "classroom", "class": "classroom", "classroom": "classroom", "teacher": "classroom", "lesson": "classroom", "student": "classroom", "students": "classroom", "learn": "classroom",
    "playground": "school_yard", "football": "school_yard", "game": "school_yard", "play": "school_yard", "played": "school_yard", "sport": "school_yard", "sports": "school_yard",
    "bank": "bank", "loan": "bank", "savings": "bank", "account": "bank", "money": "bank", "interest": "bank",
    "hospital": "hospital", "doctor": "hospital", "sick": "hospital", "medicine": "hospital", "nurse": "hospital", "health": "hospital", "patient": "hospital",
    "shop": "shop_inside", "store": "shop_inside", "bought": "shop_inside", "buy": "shop_inside", "customer": "shop_inside", "price": "shop_inside", "sale": "shop_inside",
    "market": "market", "bazaar": "market", "vendor": "market", "vegetables": "market",
    "factory": "factory", "machine": "factory", "workers": "factory", "production": "factory", "manufacture": "factory",
    "farm": "farm", "farmer": "farm", "crops": "farm", "harvest": "farm", "cow": "farm", "village": "farm",
    "airport": "airport", "plane": "airport", "flight": "airport", "travel": "airport", "passport": "airport",
    "city": "city", "town": "city", "building": "city", "skyscraper": "city", "traffic": "city",
    "mountain": "mountain", "hill": "mountain", "climb": "mountain", "summit": "mountain", "peak": "mountain",
    "island": "island", "beach": "island", "sea": "island", "ocean": "island", "boat": "island", "sail": "island",
    "court": "courtroom", "judge": "courtroom", "law": "courtroom", "lawyer": "courtroom", "trial": "courtroom",
    "office": "office", "boss": "office", "meeting": "office", "job": "office", "work": "office", "company": "office", "business": "office", "manager": "office",
    "computer": "screen_world", "app": "screen_world", "software": "screen_world", "website": "screen_world", "online": "screen_world", "internet": "screen_world", "data": "screen_world", "phone": "screen_world",
    "home": "home", "house": "home", "family": "home", "bed": "home", "mother": "home", "father": "home", "sofa": "home",
    "street": "street", "road": "street", "wallet": "street", "car": "street", "walk": "street", "bus": "street",
    "forest": "nature", "river": "nature", "tree": "nature", "garden": "nature", "grapes": "nature", "animals": "nature", "nature": "nature", "park": "nature", "vine": "nature", "flowers": "nature",
    "space": "space", "planet": "space", "star": "space", "stars": "space", "moon": "space", "rocket": "space", "galaxy": "space", "gravity": "space", "universe": "space",
    "science": "lab", "experiment": "lab", "lab": "lab", "chemical": "lab", "molecule": "lab", "atom": "lab", "energy": "lab", "research": "lab",
    "stage": "stage", "speech": "stage", "audience": "stage", "present": "stage", "presentation": "stage", "concert": "stage",
}
DOMAIN_PLACE = {"finance": ["bank", "office"], "business": ["office", "shop_inside"], "tech": ["screen_world", "office"], "education": ["classroom", "lab"], "health": ["hospital", "home"],
                "kids": ["school_yard", "home"], "motivation": ["mountain", "stage"], "news": ["city", "stage"], "nature": ["nature", "farm"], "food": ["kitchen", "market"],
                "sports": ["school_yard", "stage"], "story": ["street", "home"], "other": ["classroom", "street"]}
NIGHT = {"night", "dark", "midnight", "evening", "bedtime", "moonlight", "late"}
DAWN = {"morning", "dawn", "sunrise", "breakfast"}
RAIN = {"rain", "raining", "storm", "stormy", "thunder"}
SNOW = {"snow", "snowing", "winter", "cold", "snowy"}
ROLE_WORDS = {  # words that name a person, with the role and look they suggest
    "owner": ("elder", {"height": "elder", "accessory": "beard"}), "old": ("elder", {"height": "elder"}), "elder": ("elder", {"height": "elder", "accessory": "beard"}),
    "grandmother": ("elder", {"height": "elder", "hair": "bun"}), "grandfather": ("elder", {"height": "elder", "accessory": "beard"}), "grandpa": ("elder", {"height": "elder", "accessory": "beard"}),
    "grandma": ("elder", {"height": "elder", "hair": "bun"}),
    "child": ("child", {"height": "child"}), "kid": ("child", {"height": "child", "accessory": "headband"}), "boy": ("child", {"height": "child", "hair": "short"}),
    "girl": ("child", {"height": "child", "hair": "long", "accessory": "bow"}), "children": ("child", {"height": "child"}), "baby": ("child", {"height": "child"}),
    "teacher": ("teacher", {"accessory": "glasses"}), "doctor": ("doctor", {"accessory": "labcoat"}), "nurse": ("doctor", {"hair": "bun"}), "farmer": ("farmer", {"accessory": "hat"}),
    "cook": ("cook", {"accessory": "apron"}), "chef": ("cook", {"accessory": "apron", "hair": "short"}), "police": ("police", {"accessory": "cap"}), "thief": ("thief", {"accessory": "mask"}),
    "king": ("king", {"accessory": "crown"}), "queen": ("king", {"accessory": "crown", "hair": "long"}), "boss": ("boss", {"accessory": "tie"}), "manager": ("boss", {"accessory": "tie"}),
    "worker": ("worker", {"accessory": "helmet"}), "seller": ("seller", {"accessory": "hat"}), "shopkeeper": ("seller", {"accessory": "hat"}), "customer": ("customer", {"accessory": "scarf"}),
    "driver": ("driver", {"accessory": "cap"}), "scientist": ("scientist", {"accessory": "labcoat", "hair": "curly"}), "student": ("student", {"accessory": "backpack"}),
    "friend": ("friend", {}), "mother": ("elder", {"hair": "bun"}), "father": ("worker", {}), "mom": ("elder", {"hair": "bun"}), "dad": ("worker", {}), "man": ("friend", {}), "woman": ("friend", {"hair": "long"}),
    "stranger": ("thief", {"accessory": "hat"}), "artist": ("artist", {"accessory": "headband"}), "athlete": ("athlete", {"accessory": "headband"}), "robot": ("robot", {"accessory": "helmet"}),
}
ANIMALS = {"fox", "crow", "dog", "cat", "lion", "tiger", "bird", "fish", "horse", "cow", "monkey", "rabbit", "mouse", "elephant", "bear", "wolf", "duck", "frog", "snake", "turtle", "owl", "bee", "ant",
           "sheep", "goat", "pig", "chicken", "deer", "dolphin", "whale", "butterfly", "spider", "crab", "parrot", "camel", "panda", "kangaroo", "penguin", "eagle"}
NAMES = set("""rafi maya sam ben tom anna ana raj lee kim mia tina john jack sara sarah ali omar ahmed karim rahim salma fatima nadia rina rita mina sumi nila tania anika arif asif imran hasan
hossain jamal kabir sohel rubel shuvo tuhin nabil farhan tariq zara emma liam noah olivia ava sophia lucas ethan mason henry alex chris dan david mike mary lisa linda peter paul james robert william
daniel joe amy eva eve ravi amit priya neha rohan arjun dev anil sunil nina leo max zoe ella lily ruby jay jon ken bob sue pat amina bilal yusuf maria carlos juan pedro sofia hana yuki ken""".split())
SHIRTS = ["#3b82f6", "#b45309", "#10b981", "#ef4444", "#a855f7", "#f97316", "#0ea5e9", "#14b8a6", "#facc15", "#ec4899"]
SKINS = [None, "#f1c27d", "#e0ac69", "#c68642", "#8d5524", "#ffdbac"]
HAIRS = ["short", "long", "bun", "curly", "short", "none"]
GIVE_BACK = {"it", "them", "this", "that", "back", "him", "her", "to", "the", "a", "an", "his", "her", "their", "some", "up", "away", "out", "his", "its", "my", "your", "our"}
STOP = GIVE_BACK | {"and", "then", "but", "so", "was", "were", "is", "are", "be", "had", "has", "have", "he", "she", "they", "we", "i", "you", "with", "for", "on", "in", "at", "of", "by", "from", "as", "it's"}
PRONOUN_FEM = {"she", "her", "hers", "herself"}
PRONOUN_MASC = {"he", "him", "his", "himself"}


def _norm(w: str) -> str:
    return re.sub(r"[^\w']+", "", w.casefold())


def _lemma(w: str) -> str:
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


# ----------------------------------------------------------------------------------------------------------------------- working state
@dataclass
class Who:
    id: str
    name: str
    role: str = "narrator"
    style: dict = field(default_factory=dict)
    kind: str = "person"
    emoji: Optional[str] = None
    female: Optional[bool] = None
    first: Optional[str] = None             # word id where it first appears
    entered: bool = False
    aliases: set = field(default_factory=set)
    auto: bool = False                       # a default character (host, learner, friend) that no word of the text names


@dataclass
class Ev:
    t: float
    who: str
    do: str
    params: dict
    at_word: str


def _seed(tr: Transcript) -> int:
    return int(hashlib.sha1(" ".join(w.text for w in tr.words).encode("utf-8")).hexdigest()[:8], 16)


class Rng:
    def __init__(self, seed: int):
        self.s = seed or 1

    def next(self) -> float:
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return self.s / 0x7FFFFFFF

    def pick(self, items):
        return items[int(self.next() * len(items)) % len(items)]


# ----------------------------------------------------------------------------------------------------------------------- 1. the cast
def build_cast(tr: Transcript, beats: Beats, ctx, rng: Rng) -> list[Who]:
    words = [(w, _norm(w.text)) for w in tr.words]
    text = " ".join(n for _, n in words)
    cast: list[Who] = []
    used_shirts: list[str] = []

    def look(role: str, extra: dict, name_hint: str = "") -> dict:
        shirt = next((c for c in SHIRTS if c not in used_shirts), rng.pick(SHIRTS))
        used_shirts.append(shirt)
        st = {"shirt": shirt, "color": "#1f2937" if len(cast) % 2 == 0 else "#374151", "head": rng.pick(["round", "round", "oval", "square"]), "hair": rng.pick(HAIRS), "skin": rng.pick(SKINS)}
        st.update({k: v for k, v in extra.items()})
        if not st.get("skin"):
            st.pop("skin", None)
        return st

    def add(name: str, role: str, extra: dict, female: Optional[bool] = None, aliases: Optional[set] = None) -> Who:
        wid = re.sub(r"[^a-z0-9_]", "", name.casefold().replace(" ", "_"))[:14] or f"p{len(cast) + 1}"
        if not wid[0].isalpha():
            wid = "p" + wid
        while any(c.id == wid for c in cast):
            wid = (wid[:12] + str(len(cast)))[:15]
        w = Who(id=wid, name=name[:14], role=role if role in C.ROLES else "friend", style=look(role, extra), female=female, aliases={_norm(name)} | (aliases or set()))
        cast.append(w)
        return w

    # named people from the reading of the video, in the order they are first said
    people = []
    try:
        from wordfreq import zipf_frequency as _zf
    except Exception:                                            # pragma: no cover
        _zf = None
    product_like = ctx is not None and ctx.mood in ("tech", "business", "finance")

    def person_like(e) -> bool:
        n = _norm(e.name.split()[0])
        if e.type == "person" or n in NAMES:
            return True
        if product_like:                                         # in a video about a product, a rare capitalised word is its name, not a person
            return False
        return _zf is None or _zf(n, "en") < 3.3

    if ctx is not None:
        for e in ctx.entities:
            if e.type in ("person", "name") and e.mentions and len(e.name) > 1 and _norm(e.name) not in STOP and _norm(e.name) not in ROLE_WORDS and person_like(e):
                first = min(e.mentions, key=lambda i: int(i[1:]) if i[1:].isdigit() else 0)
                people.append((int(first[1:]) if first[1:].isdigit() else 0, e))
    for _, e in sorted(people, key=lambda x: x[0])[:3]:
        add(e.name.split()[0], "friend", {})
    # names the reading of the video dropped because they are said once ("Rafi found a wallet"): a first name, or a rare capitalised word, is a person
    try:
        from wordfreq import zipf_frequency
    except Exception:                                    # pragma: no cover
        zipf_frequency = None
    from ..context import STOP_CAPS

    seen = {_norm(c.name) for c in cast}
    known = {_norm(e.name) for e in (ctx.entities if ctx is not None else []) if e.type not in ("person", "name")}
    for i, (w, n) in enumerate(words):
        if len([c for c in cast if c.kind == "person"]) >= 3:
            break
        t = w.text.strip(".,!?;:\"'()")
        if not (t[:1].isupper() and t.isalpha() and t.isascii() and len(t) > 2) or n in seen or n in known or n in STOP_CAPS:
            continue
        if n in ROLE_WORDS or n in ANIMALS or n in PLACES or n in MOTION or n in FEEL or n in DOING:
            continue
        if n in NAMES or (not product_like and zipf_frequency is not None and zipf_frequency(n, "en") < 3.3):
            seen.add(n)
            add(t, "friend", {})
    # people named by what they are ("the old man", "the owner", "her mother")
    for i, (w, n) in enumerate(words):
        if n in ROLE_WORDS and len(cast) < 3 and n not in ("old", "man", "woman", "friend", "child"):
            role, extra = ROLE_WORDS[n]
            if n in ("mother", "mom") and any(c.role == "elder" and "mother" in c.aliases for c in cast):
                continue
            if any(n in c.aliases or role == c.role and n in ("teacher", "doctor", "owner") for c in cast):
                continue
            if i > 0 and words[i - 1][1] in ("the", "a", "an", "his", "her", "their", "old", "young", "my", "our", "to", "with") or n in ("teacher", "doctor", "king", "queen", "thief", "farmer", "chef", "seller"):
                nm = n.capitalize() if n not in ("old",) else "Elder"
                add(nm, role, extra, female=n in ("woman", "girl", "mother", "mom", "queen", "grandmother", "grandma", "nurse"), aliases={n})
    # "the old man": an elder
    m = re.search(r"\b(old|elderly)\s+(man|woman|lady|gentleman)\b", text)
    if m and not any(c.style.get("height") == "elder" for c in cast) and len(cast) < 3:
        add("Elder", "elder", {"height": "elder", "accessory": "beard" if m.group(2) in ("man", "gentleman") else "none", "hair": "bun" if m.group(2) in ("woman", "lady") else "none"}, aliases={"man", "woman", "lady", "gentleman", "old"})
    # animals that are in the story become emoji actors (the ones said most often)
    counts = {}
    for _, n in words:
        if n in ANIMALS or _lemma(n) in ANIMALS:
            counts[_lemma(n)] = counts.get(_lemma(n), 0) + 1
    for an, k in sorted(counts.items(), key=lambda x: -x[1])[:2]:
        wid = (an + "_a")[:15]
        cast.append(Who(id=wid, name=an.capitalize(), role="animal", kind="emoji", emoji=an, aliases={an, an + "s"}))
    # a video with no one in it: a host and a curious learner, so that people can talk to each other
    persons = [c for c in cast if c.kind == "person"]
    if not persons and any(c.kind == "emoji" for c in cast):
        return cast[:8]                                   # a fable: the animals are the cast
    if not persons:
        cast.append(Who(id="host", name="Host", role="teacher", style={"accessory": "glasses", "shirt": SHIRTS[0], "hair": "short", "color": "#1f2937"}, aliases={"you"}, auto=True))
        cast.append(Who(id="sam", name="Sam", role="student", style={"height": "child", "accessory": "backpack", "shirt": SHIRTS[3], "hair": "bun", "color": "#374151"}, aliases={"we"}, auto=True))
    elif len(persons) == 1 and len(beats.beats) >= 3:
        other_role = "elder" if persons[0].style.get("height") != "elder" else "child"
        cast.append(Who(id="friend", name="Friend", role="friend", style={"shirt": SHIRTS[5], "hair": "long", "height": other_role if other_role == "child" else "adult", "accessory": "bow" if other_role == "child" else "none", "color": "#374151"}, aliases={"you", "friend"}, auto=True))
    return cast[:8]


# ----------------------------------------------------------------------------------------------------------------------- 2. places
def place_scores(text: str) -> dict:
    sc: dict[str, int] = {}
    for w in re.findall(r"[\w']+", text.casefold()):
        k = PLACES.get(w) or PLACES.get(_lemma(w))
        if k:
            sc[k] = sc.get(k, 0) + 1
    return sc


def time_weather(text: str) -> tuple[Optional[str], Optional[str]]:
    ws = set(re.findall(r"[\w']+", text.casefold()))
    t = "night" if ws & NIGHT else "dawn" if ws & DAWN else None
    wth = "rain" if ws & RAIN else "snow" if ws & SNOW else None
    return t, wth


def plan_places(scene_texts: list[str], ctx, domain: list[str]) -> list[dict]:
    """One place per scene: the word cues first, then the topic; a long story changes place now and then; a place is kept while nothing says otherwise."""
    mood = (ctx.mood if ctx is not None else "other") or "other"
    prefer = DOMAIN_PLACE.get(next((d for d in (domain or []) if d in DOMAIN_PLACE), mood), DOMAIN_PLACE["other"])
    out: list[dict] = []
    cur = None
    sections = ctx.sections if ctx is not None else []
    for i, text in enumerate(scene_texts):
        sc = place_scores(text)
        want = max(sc, key=lambda k: (sc[k], k == cur)) if sc else None
        if want and want != cur:
            cur = want
        elif cur is None:
            cur = prefer[0]
        elif not sc and len(scene_texts) >= 4 and i % 3 == 0 and i > 0:                  # nothing said where we are: after a few scenes, the next place of the topic
            cur = prefer[(prefer.index(cur) + 1) % len(prefer)] if cur in prefer else prefer[0]
        t, wth = time_weather(text)
        prev = out[-1] if out else {}
        out.append({"kind": cur, "time": t or prev.get("time") or "day", "weather": wth or ("none" if t else prev.get("weather", "none"))})
    return out


# ----------------------------------------------------------------------------------------------------------------------- 3. events from the words
class Story:
    def __init__(self, tr: Transcript, beats: Beats, cast: list[Who], rng: Rng, ctx=None):
        self.tr, self.beats, self.cast, self.rng, self.ctx = tr, beats, cast, rng, ctx
        self.persons = [c for c in cast if c.kind == "person"]
        self.last: Optional[Who] = self.persons[0] if self.persons else (cast[0] if cast else None)
        self.last_prop: Optional[str] = None
        self.recent: list[tuple[str, str]] = []
        self.use: dict[str, int] = {}
        self.slot = 0
        self.recent_people: list = []

    # who is a word talking about?
    def who_of(self, token: str) -> Optional[Who]:
        n = _norm(token)
        for c in self.cast:
            if n in c.aliases or n == _norm(c.name):
                return c
        if n in PRONOUN_FEM | PRONOUN_MASC:
            fem = n in PRONOUN_FEM
            ok = [c for c in self.persons if (c.female is None) or (c.female == fem)]
            if self.last in ok:
                return self.last
            return next((c for c in reversed(self.recent_people) if c in ok), ok[0] if ok else self.last)
        return None

    def other_than(self, who: Who) -> Optional[Who]:
        return next((c for c in self.cast if c is not who and c.kind == "person"), next((c for c in self.cast if c is not who), None))

    def avoid_repeat(self, who: str, do: str) -> bool:
        return bool(self.recent) and self.recent[-1] == (who, do)

    def note(self, who: str, do: str) -> None:
        self.recent.append((who, do))
        self.use[do] = self.use.get(do, 0) + 1


PROP_BAN = {"time", "day", "way", "lot", "bit", "thing", "things", "one", "something", "everything", "while", "moment"}


PREPS = {"on", "in", "at", "to", "from", "into", "onto", "near", "under", "over", "behind", "with", "for", "of", "by", "and", "then", "but", "so", "because", "when", "while", "after", "before"}


_KNOWN: dict = {}


def _known_things() -> tuple:
    """(names the stick engine draws itself, names of colour stickers): the words a prop can safely be."""
    if not _KNOWN:
        from .. import paths

        try:
            js = (paths.RUNTIME / "vt-stick.js").read_text(encoding="utf-8")
            m = re.search(r"const DRAW = [{](.*?)\n  [}];", js, re.S)
            drawn = set(re.findall(r"^\s{4}(\w+):", m.group(1), re.M)) if m else set()
        except OSError:
            drawn = set()
        try:
            from ..visuals.search import _docs

            stick = {str(d["en"]).split(";")[0].strip().lower() for d in _docs() if d["kind"] == "sticker"}
        except Exception:                                        # pragma: no cover
            stick = set()
        _KNOWN["v"] = (drawn, stick)
    return _KNOWN["v"]


def _prop_after(toks: list, i: int, st: "Story") -> Optional[str]:
    """The thing handed around or looked at: of the words of the noun phrase after the verb, the one that is a thing we can draw ("found a lost wallet" -> wallet,
    "saw grapes high on a vine" -> grape); else the last one."""
    got: list = []
    for t in toks[i + 1:i + 6]:
        n = _norm(t)
        if n in PREPS and got:
            break
        if n in STOP or n in PREPS or len(n) < 3 or n in PROP_BAN or n.isdigit():
            continue
        if n in ROLE_WORDS or any(n in c.aliases or n == _norm(c.name) for c in st.cast):
            if got:
                break
            continue
        if n in MOTION or n in FEEL or n in DOING or (n.endswith("ed") and len(n) > 4) or n.endswith("ing") or n in ("away", "back", "home", "out", "up", "down", "again", "later", "very"):
            if got:
                break
            continue
        got.append(_lemma(n)[:20])
    if not got:
        return None
    drawn, stick = _known_things()
    scored = sorted(range(len(got)), key=lambda j: (2 if got[j] in drawn else 1 if (got[j] in stick or got[j] + "s" in stick) else 0, j))
    return got[scored[-1]]


def events_for_beat(st: Story, beat, words: dict) -> list[Ev]:
    ids = [i for i in beat.word_ids if i in words]
    toks = [words[i].text for i in ids]
    norm = [_norm(t) for t in toks]
    evs: list[Ev] = []
    subject = st.last
    seen_cue = set()
    quote = re.search(r"[\"“”‘’']([^\"“”‘’']{4,70})[\"“”‘’']", beat.text)
    for k, (wid, n) in enumerate(zip(ids, norm)):
        w = words[wid]
        who = st.who_of(toks[k])
        if who is not None and who.kind in ("person", "emoji") and n not in PRONOUN_FEM | PRONOUN_MASC:
            subject = who
            st.last = who
            if who in st.recent_people:
                st.recent_people.remove(who)
            st.recent_people.append(who)
        elif n in PRONOUN_FEM | PRONOUN_MASC and who is not None:
            subject = who
        verb = MOTION.get(n) or DOING.get(n) or FEEL.get(n)
        nxt = norm[k + 1] if k + 1 < len(norm) else ""
        if n in ("says", "say", "thinks", "believes", "argues", "claims", "feels", "insists", "suggests") and subject is not None and subject.kind == "person" and k + 2 < len(ids):
            clause = [t for t in toks[k + 1:k + 12]]
            if clause and _norm(clause[0]) in ("that",):
                clause = clause[1:]
            say = " ".join(clause)[:70].strip(" ,.")
            if len(say) >= 6:
                evs.append(Ev(w.start, subject.id, "say", {"bubble": say}, wid))
            continue
        if n in ("gave", "give", "gives") and nxt in ("up", "in", "way"):
            verb = "react:sad"
        elif n in ("took", "take") and nxt in ("off", "care", "part", "place"):
            verb = None
        elif n in ("looked", "look") and nxt in ("for", "forward"):
            verb = "look_at"
        if not verb or (n, k // 4) in seen_cue or subject is None:
            continue
        seen_cue.add((n, k // 4))
        sub = subject
        params: dict = {}
        base, _, arg = verb.partition(":")
        other = st.other_than(sub)
        if base == "react":
            params = {"emotion": arg}
        elif base == "mark":
            params = {"mark": arg}
        elif base in ("run", "walk_to", "chase", "follow", "sneak", "fly"):
            if base in ("walk_to",) and n in ("arrived", "entered", "came") and not sub.entered:
                continue                                                       # the entrance is handled where the person first appears
            to = 0.75 if st.slot % 2 == 0 else 0.28
            st.slot += 1
            do = {"walk_to": "walk_to", "run": "run", "chase": "chase", "follow": "follow", "sneak": "sneak", "fly": "fly"}[base]
            params = {"to": to}
            evs.append(Ev(w.start, sub.id, do, params, wid))
            continue
        elif base == "walk_out":
            params = {"to_side": "right" if st.slot % 2 == 0 else "left"}
            st.slot += 1
        elif base in ("lift", "carry"):
            prop = _prop_after(toks, k, st) or st.last_prop
            if not prop:
                continue
            st.last_prop = prop
            params = {"prop": prop}
        elif base in ("give", "throw"):
            prop = _prop_after(toks, k, st) or st.last_prop
            tgt = None
            for j in range(k + 1, min(len(ids), k + 7)):                        # "gave it back to the owner", "gave him the ball"
                c = st.who_of(toks[j])
                if c is not None and c is not sub:
                    tgt = c
                    break
            tgt = tgt or other
            if not prop or tgt is None:
                continue
            st.last_prop = prop
            params = {"prop": prop, "target": tgt.id}
        elif base in ("hug", "handshake", "high_five"):
            tgt = None
            for j in range(k + 1, min(len(ids), k + 6)):
                c = st.who_of(toks[j])
                if c is not None and c is not sub:
                    tgt = c
                    break
            tgt = tgt or other
            if tgt is None:
                continue
            params = {"target": tgt.id}
        elif base == "hide":
            params = {"target": next((p for p in ("crate", "tree", "rock", "door", "desk", "table") if p), "crate")}
            hid = None
        elif base == "write_board":
            params = {"bubble": " ".join(toks[k + 1:k + 5])[:30] or "Notes", "target": "board"}
        elif base == "point":
            params = {"target": "viewer"}
        elif base == "look_at":
            thing = _prop_after(toks, k, st) if n in ("saw", "looked", "watched") else None
            if thing and thing not in ("street", "way", "road", "day"):
                st.last_prop = thing
                params = {"target": thing, "_thing": thing}
            else:
                params = {"target": other.id if other is not None else "viewer"}
        elif base in ("push", "pull"):
            params = {"target": "car"}
        elif base == "count":
            params = {"count": 3}
        elif base == "say":
            if not quote:
                continue
            params = {"bubble": quote.group(1)[:70]}
        elif base == "explain":
            pass
        evs.append(Ev(w.start, sub.id, base, params, wid))
    # numbers
    m = re.search(r"\d[\d,.]*\s?(?:%|percent|dollars?|taka|usd|k|m)?", beat.text)
    if m and ids and subject is not None:
        word = next((i for i in ids if re.search(r"\d", words[i].text)), ids[0])
        evs.append(Ev(words[word].start, subject.id, "hold_sign", {"bubble": m.group(0).strip()[:20]}, word))
    # a question: the learner asks it out loud when there is one, and whoever answers wonders
    if "?" in beat.text and ids and subject is not None and not any(e.do in ("think", "shrug") for e in evs):
        learner = next((c for c in st.cast if c.auto and c.kind == "person" and c.id != "host"), None)
        asker = learner or subject
        q = re.sub(r"\s+", " ", beat.text).strip()
        evs.append(Ev(words[ids[0]].start, asker.id, "say", {"bubble": q[:70]}, ids[0]))
        thinker = next((c for c in st.cast if c.kind == "person" and c is not asker), subject)
        j = min(2, len(ids) - 1)
        evs.append(Ev(words[ids[j]].start, thinker.id, "think", {}, ids[j]))
        evs.append(Ev(words[ids[min(j + 1, len(ids) - 1)]].start + 0.01, thinker.id, "mark", {"mark": "question"}, ids[min(j + 1, len(ids) - 1)]))
    return evs


# ----------------------------------------------------------------------------------------------------------------------- 4. the gaps, and 5. camera / transitions / sound
ACTOR_VERBS = {"jump", "bounce", "spin", "grow", "shake_head", "react", "walk_to", "run", "fly", "appear", "mark", "fall", "dance", "walk_in", "walk_out", "say", "chase", "follow", "turn", "idle"}
ACTOR_FALLBACK = {"laugh": "bounce", "celebrate": "jump", "clap": "bounce", "hug": "bounce", "wave": "bounce", "explain": "bounce", "nod": "bounce", "think": "grow", "yawn": "bounce", "cry": "shake_head",
                  "argue": "shake_head", "lift": "jump", "give": "bounce", "throw": "jump", "eat": "grow", "hold_sign": "grow", "hide": "fall", "peek": "bounce", "sneak": "walk_to", "point": "bounce",
                  "look_at": "bounce", "bow": "bounce", "dance": "dance"}
MARK_BY_ROLE = {"question": "question", "hook": "exclaim", "number": "sparkle", "price": "sparkle", "problem": "sweat", "contrast": "exclaim", "cta": "heart", "proof": "sparkle", "recap": "idea",
                "definition": "idea", "claim": "exclaim", "story": "exclaim", "step": "idea"}
AMBIENT_SOLO = ["nod", "explain", "mark", "shrug", "point", "think", "wave", "react"]
AMBIENT_PAIR = ["nod", "react", "look_at", "clap", "mark", "shrug", "wave_both"]


def _fix_for_actor(do: str, params: dict) -> tuple[str, dict]:
    if do in ACTOR_VERBS:
        return do, params
    nd = ACTOR_FALLBACK.get(do, "bounce")
    return nd, ({"to": 0.5} if nd in ("walk_to", "run", "fly", "chase", "follow") else {})


def ambient(st: Story, onstage: list, active: Optional[Who], sent_role: str) -> Optional[tuple]:
    """Something small that happens while nothing else does, never the same thing twice in a row and never only talking."""
    pair = len([c for c in onstage if c.kind == "person"]) >= 2
    cands = [c for c in onstage if c is not active] if pair else onstage
    cands = cands or onstage
    if not cands:
        return None
    who = cands[st.use.get("_turn", 0) % len(cands)]
    st.use["_turn"] = st.use.get("_turn", 0) + 1
    bank = AMBIENT_PAIR if (pair and who is not active) else AMBIENT_SOLO
    order = sorted(bank, key=lambda v: (st.use.get(v, 0), st.rng.next()))
    for do in order:
        if st.avoid_repeat(who.id, do):
            continue
        params: dict = {}
        if do == "mark":
            params = {"mark": MARK_BY_ROLE.get(sent_role, "exclaim")}
        elif do == "react":
            params = {"emotion": "happy" if sent_role in ("hook", "cta", "proof", "number", "price") else "surprised" if sent_role in ("contrast", "problem") else "confused" if sent_role == "question" else "happy"}
        elif do == "look_at":
            if active is None:
                continue
            params = {"target": active.id}
        elif do == "point":
            params = {"target": "viewer"}
        if who.kind == "emoji":
            do, params = _fix_for_actor(do, params)
        return who, do, params
    return None


def story_script(tr: Transcript, beats: Beats, sf: ScenesFile, *, kind: str = "stick", language: str = "en", aspect: str = "9:16", title: str = "", ctx=None) -> VideoScript:
    from .. import context as CX
    from .compile import script_from_scenes

    script = script_from_scenes(sf, language, aspect, title)
    script.planner = "rules"
    script.kind = kind  # type: ignore[assignment]
    words = tr.by_id()
    beats_by = {b.id: b for b in beats.beats}
    if ctx is None:
        ctx = CX.rules_context(tr, beats, language)
    rng = Rng(_seed(tr))
    cast = build_cast(tr, beats, ctx, rng)
    st = Story(tr, beats, cast, rng, ctx)
    for sc in script.scenes:                                          # the figures are the characters: no second (cartoon) character, no speaker card; a tall stack of emoji would crowd the heads
        sc.overlays = [o for o in sc.overlays if o.get("type") not in ("cartoon", "speaker_card")]
        for extra in [o for o in sc.overlays if o.get("type") == "sticker"][2:]:
            sc.overlays.remove(extra)
    scene_texts = [" ".join(beats_by[b].text for b in sc.beats) for sc in script.scenes]
    places = plan_places(scene_texts, ctx, ctx.domain or [])
    set_defs: dict = {}
    scene_set: list = []
    for pl in places:
        key = (pl["kind"], pl["time"], pl["weather"])
        if key not in set_defs:
            set_defs[key] = SetDef(id=f"{pl['kind'][:10]}{len(set_defs) + 1}", kind=pl["kind"], time=pl["time"], weather=pl["weather"], props=[])  # type: ignore[arg-type]
        scene_set.append(set_defs[key])
    onstage: list = []
    persons = [c for c in cast if c.kind == "person"]
    slots = [0.3, 0.7, 0.5, 0.15, 0.85]
    n = len(script.scenes)
    prev_place = None
    prev_cam = None
    transitions_used: list = []
    sections_seen = -1
    for i, sc in enumerate(script.scenes):
        scene_words = [w for b in sc.beats for w in beats_by[b].word_ids if w in words]
        t0, t1 = words[scene_words[0]].start, words[scene_words[-1]].end
        evs: list = []
        for b in sc.beats:
            evs += events_for_beat(st, beats_by[b], words)
        sp = scene_set[i]
        for e in evs:                                                 # the things the story hands around or looks at are props of the place
            thing = e.params.pop("_thing", None)
            for v in (e.params.get("prop"), thing):
                if v and v not in sp.props and len(sp.props) < 4:
                    sp.props.append(v)
        named: list = []                                              # who is in the scene: whoever acts, is named, or is the target of someone
        for wid in scene_words:
            c = st.who_of(words[wid].text)
            if c is not None and _norm(words[wid].text) not in PRONOUN_FEM | PRONOUN_MASC:
                named.append((words[wid].start, c))
        for e in evs:
            for c in cast:
                if c.id == e.who or c.id == e.params.get("target"):
                    named.append((e.t, c))
        if i == 0 and cast:
            named.insert(0, (t0, persons[0] if persons else cast[0]))
        for c in cast:                                                 # a default character that no word names: it comes in at the first question, else at the second scene
            if c.auto and c.kind == "person" and c not in onstage and c is not persons[0]:
                q = next((wid for b in sc.beats if "?" in beats_by[b].text for wid in beats_by[b].word_ids[:1] if wid in words), None)
                if q is not None or (i >= 1):
                    named.append((words[q].start if q is not None else t0, c))
        entries: list = []
        for t, c in sorted(named, key=lambda x: x[0]):
            if c in onstage:
                continue
            onstage.append(c)
            at = min(scene_words, key=lambda w: abs(words[w].start - max(t, t0)))
            if c.kind == "person":
                idx = persons.index(c)
                entries.append(Ev(max(t, t0) - 0.001, c.id, "walk_in", {"from": "left" if idx % 2 == 0 else "right", "to": slots[idx % len(slots)]}, at))
            else:
                entries.append(Ev(max(t, t0) - 0.001, c.id, "appear", {}, at))
            c.entered = True
        for e in evs:                                                 # someone who walks out is no longer on stage
            if e.do == "walk_out":
                who = next((c for c in cast if c.id == e.who), None)
                if who in onstage and len(onstage) > 1:
                    onstage.remove(who)
        props_here = set(C.SETS.get(sp.kind, ())) | set(sp.props)     # parameters that need the place
        cover = next((p for p in ("crate", "tree", "rock", "desk", "table", "door", "car", "bench", "counter", "machine") if p in props_here), None)
        fixed: list = []
        for e in evs:
            who = next((c for c in cast if c.id == e.who), None)
            if who is not None and who.kind == "emoji":
                e.do, e.params = _fix_for_actor(e.do, e.params)
            if e.do == "hide":
                if cover is None:
                    e.do, e.params = "sneak", {"to": 0.6}
                else:
                    e.params = {"target": cover}
            if e.do in ("push", "pull"):
                tg = next((p for p in ("car", "crate", "machine", "rock") if p in props_here), None)
                if tg is None:
                    continue
                e.params = {"target": tg}
            if e.do == "write_board" and "board" not in props_here:
                e.do, e.params = "explain", {}
            if e.do == "point" and e.params.get("target") not in ("viewer", None) and e.params.get("target") not in props_here:
                e.params = {"target": "viewer"}
            fixed.append(e)
        evs = entries + fixed
        evs.sort(key=lambda e: e.t)
        clean: list = []                                              # the same thing twice in a row for one person is dropped
        for e in evs:
            if clean and clean[-1].who == e.who and clean[-1].do == e.do and e.do not in ("walk_in", "mark"):
                continue
            clean.append(e)
        evs = clean
        role = "claim"
        if ctx is not None and sc.beats:
            s0 = ctx.sentence(sc.beats[0])
            role = s0.role if s0 else "claim"
        active = next((c for c in cast if evs and c.id == evs[0].who), onstage[0] if onstage else None)
        for _ in range(12):                                           # gaps: a stretch with nothing new gets a small, different thing
            points = sorted([t0, t1] + [e.t for e in evs] + [words[o["at_word"]].start for o in sc.overlays if o.get("at_word") in words])
            gap, a_t, b_t = max(((y - x, x, y) for x, y in zip(points, points[1:])), default=(0.0, 0.0, 0.0))
            if gap <= GAP or len(evs) >= MAX_ACTIONS or not onstage:
                break
            mid = a_t + gap / 2
            cand = [w for w in scene_words if a_t + 0.5 <= words[w].start <= b_t - 0.3] or scene_words
            at = min(cand, key=lambda w: abs(words[w].start - mid))
            res = ambient(st, onstage, active, role)
            if res is None:
                break
            who, do, params = res
            evs.append(Ev(words[at].start, who.id, do, params, at))
            evs.sort(key=lambda e: e.t)
            st.note(who.id, do)
        acting = {e.who for e in evs}                                 # the engine draws only those with an action in the scene: everyone on stage acts
        for c in onstage:
            if c.id not in acting:
                at = scene_words[min(len(scene_words) - 1, 1 + len(acting))]
                evs.append(Ev(words[at].start, c.id, "nod" if c.kind == "person" else "bounce", {}, at))
        if i == 0:
            first = next((e for e in evs if e.do == "walk_in"), None)
            if first is not None and not any(e.do == "wave" for e in evs) and len(scene_words) > 2:
                w = scene_words[min(2, len(scene_words) - 1)]
                if words[w].start > first.t:
                    evs.append(Ev(words[w].start, first.who, "wave", {}, w))
        evs.sort(key=lambda e: e.t)
        for e in evs:
            st.note(e.who, e.do)
        sc.actions = [Action.model_validate({"at_word": e.at_word, "who": e.who, "do": e.do, **e.params}) for e in evs[:MAX_ACTIONS]]
        sc.set = sp.id
        # camera, transition, sound
        pl = (sp.kind, sp.time, sp.weather)
        changed = prev_place is not None and pl != prev_place
        sec = ctx.section_of(sc.beats[0]) if ctx is not None else None
        new_section = sec is not None and sec != sections_seen and i > 0
        if sec is not None:
            sections_seen = sec
        important = bool(ctx is not None and any((ctx.sentence(b) is not None and ctx.sentence(b).importance >= 3) for b in sc.beats))
        shots = [("medium", "none"), ("medium", "follow"), ("close", "push_in"), ("wide", "none"), ("medium", "pan_left"), ("wide", "pan_right"), ("close", "none")]
        cam = shots[(i * 3 + 1) % len(shots)]
        focus = None
        if i == 0:
            cam = ("medium", "push_in")
        elif i == n - 1 and n > 2:
            cam = ("wide", "pull_out")
        elif changed:
            cam = ("wide", "pan_right" if i % 2 else "pan_left")
        elif important:
            fx = next((p for p in sp.props if p != "sign"), None) or (active.id if active is not None else None)
            cam, focus = (("close", "zoom_to") if fx else ("close", "push_in")), fx
        if cam == prev_cam and i < n - 1:
            cam = shots[(i * 3 + 2) % len(shots)]
        prev_cam = cam
        sc.camera = Camera(shot=cam[0], move=cam[1], focus=focus)  # type: ignore[arg-type]
        if i == 0:
            tr_in = "cut"
        elif changed:
            tr_in = "whip" if (not transitions_used or transitions_used[-1] != "whip") else "slide_left"
        elif new_section:
            tr_in = "slide_up" if (not transitions_used or transitions_used[-1] != "slide_up") else "zoom"
        else:
            tr_in = "fade" if (not transitions_used or transitions_used[-1] != "fade") else "cut"
        transitions_used.append(tr_in)
        sc.transition_in = tr_in  # type: ignore[assignment]
        cues: list = []
        last_t = -9.0
        for e in evs:
            sfx = "pop" if e.do in ("mark", "appear", "bounce", "grow") else "whoosh" if e.do in ("walk_in", "fly", "throw", "run") else "ding" if e.do in ("hold_sign", "celebrate", "give") else None
            if sfx and e.t - last_t > 0.5 and len(cues) < 5:
                cues.append(SfxCue(at_word=e.at_word, id=sfx))  # type: ignore[arg-type]
                last_t = e.t
        sc.sfx = cues
        prev_place = pl
    chars = []                                                        # the cast and the places, written into the script
    for c in cast:
        stl = {k: v for k, v in c.style.items() if k in CharStyle.model_fields and v not in (None, "")}
        if stl.get("hair") not in (None, *C.HAIRS):
            stl.pop("hair", None)
        chars.append(Character(id=c.id, role=c.role if c.role in C.ROLES else "friend", name=c.name, style=CharStyle.model_validate(stl) if c.kind == "person" else CharStyle(), kind=c.kind))  # type: ignore[arg-type]
    script.cast = chars
    script.sets = list(set_defs.values())[:8]
    known = {s.id for s in script.sets}
    for sc in script.scenes:                                          # more than 8 distinct places: the extra ones reuse the last one
        if sc.set not in known:
            sc.set = script.sets[-1].id
    script.meta.title = title or script.meta.title
    return script
