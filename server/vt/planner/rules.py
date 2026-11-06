"""Rule-based planner: a valid, reasonable plan with no AI. Used as the first draft and as the offline fallback."""
from __future__ import annotations

import re
from typing import Optional

from ..schema import Beats, ScenesFile, Transcript, Word
from ..stages.words import norm_token

BN_DIGITS = "০১২৩৪৫৬৭৮৯"
TO_BN = {ord(str(i)): BN_DIGITS[i] for i in range(10)}
NUM_WORDS = {
    "দুই": 2, "তিন": 3, "চার": 4, "পাঁচ": 5, "ছয়": 6, "সাত": 7, "আট": 8, "নয়": 9, "দশ": 10,
    "বিশ": 20, "ত্রিশ": 30, "চল্লিশ": 40, "পঞ্চাশ": 50, "ষাট": 60, "সত্তর": 70, "আশি": 80, "নব্বই": 90,
    "একশো": 100, "একশ": 100, "দুইশো": 200, "তিনশো": 300, "পাঁচশো": 500, "হাজার": 1000,
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
EN_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
EN_UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
SYMBOLS = {
    "টাকা": "৳", "টাকার": "৳", "টাকায়": "৳", "taka": "৳", "tk": "৳", "৳": "৳",
    "rupee": "₹", "rupees": "₹", "rs": "₹", "inr": "₹", "রুপি": "₹", "রুপিতে": "₹", "₹": "₹",
    "ডলার": "$", "ডলারে": "$", "dollar": "$", "dollars": "$", "usd": "$", "bucks": "$", "$": "$",
    "euro": "€", "euros": "€", "€": "€", "pound": "£", "pounds": "£", "£": "£", "yen": "¥", "¥": "¥",
}
CURRENCY = set(SYMBOLS)
PERCENT = {"শতাংশ", "শতাংশে", "পার্সেন্ট", "percent", "%"}
COMPARE_KW = {"চেয়ে", "বনাম", "vs", "versus", "তুলনায়"}
STOP = set("""এই এটা এটাকে সেটা সেটাই যে যেটা কি কী না আর এবং তো হয় হলো করে করা একটা একটি আমি আপনি আমরা তুমি ধরুন মানে
কিন্তু তাহলে যদি থেকে জন্য দিয়ে দিয়া বলে হবে থাকবে আছে নেই ও বা তার তাদের আমার আপনার এক একটু খুব সেই ওই কেন কীভাবে কিভাবে
যখন তখন কত কতো হচ্ছে পাচ্ছেন the a an is are of to and in it that this for on with as""".split())
ICON_KEYWORDS = {
    "টাকা": "coins", "টাকার": "coins", "ব্যাংক": "landmark", "ব্যাঙ্ক": "landmark", "বাড়ি": "house", "বাসা": "house",
    "ফ্ল্যাট": "building-2", "দোকান": "store", "ব্যবসা": "store", "সময়": "clock", "বছর": "calendar", "মাস": "calendar-days",
    "লাভ": "trending-up", "ক্ষতি": "trending-down", "খরচ": "receipt", "সঞ্চয়": "piggy-bank", "বিনিয়োগ": "chart-line",
    "কার্ড": "credit-card", "ফোন": "smartphone", "ঝুঁকি": "triangle-alert", "নিরাপদ": "shield-check", "লক্ষ্য": "target",
    "profit": "trending-up", "loss": "trending-down", "risk": "triangle-alert", "bank": "landmark", "time": "clock",
}
QUANTIFIERS = {"than", "more", "over", "about", "only", "just", "almost", "nearly", "around", "approximately", "roughly", "up", "at", "least", "most", "under", "below", "above"}
TRANSITIONS = ["slide_up", "fade", "zoom", "slide_left", "wipe"]


TO_ASCII = {ord(BN_DIGITS[i]): str(i) for i in range(10)}


def localize_digits(s: str, language: str) -> str:
    """Digits in the script of the speaker's language: Bangla digits for Bangla speech, 0-9 for English."""
    return s.translate(TO_BN) if language == "bn" else s.translate(TO_ASCII)


def detect_currency(tr: Transcript, language: str, default: str = "৳") -> str:
    """The money symbol the speaker actually used (taka/rupees/dollars...), else a sensible default for the language."""
    from collections import Counter

    c = Counter(SYMBOLS[t] for t in (norm_token(w.text) for w in tr.words) if t in SYMBOLS)
    if c:
        return c.most_common(1)[0][0]
    return default if language == "bn" else "$"


EN_STOP = set("""i me my we our you your he him his she her it its they them their this that these those there here what which who whom whose
am is are was were be been being have has had do does did will would shall should can could may might must not no nor so than too very just also
and or but if then else when while where why how all any both each few more most other some such only own same about above after again against
as at because before between by down during for from in into of off on once out over through to under until up with without well really actually
now like even still yet already ever never always often much many one two get got gets make makes made going gone say says said know knows
we're they're it's that's there's i'm you're he's she's don't doesn't didn't isn't aren't wasn't won't can't couldn't wouldn't shouldn't i've we've they've you've
i'll we'll they'll you'll let's thing things something anything everything way ways kind lot bit""".split())


def _is_stop(w: Word) -> bool:
    t = norm_token(w.text)
    return t in STOP or t in EN_STOP or t.replace("’", "'") in EN_STOP


def parse_number(word: Word, language: str = "bn") -> Optional[tuple[str, float]]:
    """(display, numeric value) for digits or common Bangla/English number words."""
    t = norm_token(word.text)
    sym = re.fullmatch(r"([$€£¥₹৳])([0-9০-৯][0-9০-৯,.]*)", t)       # "$19", "৳১০০": the symbol is part of the word
    if sym:
        inner = parse_number(Word(id="x", text=sym.group(2), start=0, end=0), language)
        return (sym.group(1) + inner[0], inner[1]) if inner else None
    digits = re.fullmatch(r"[0-9০-৯][0-9০-৯,.]*", t)
    if digits:
        disp = localize_digits(t, language)
        try:
            val = float(t.translate({ord(BN_DIGITS[i]): str(i) for i in range(10)}).replace(",", ""))
        except ValueError:
            val = 0.0
        return disp, val
    pct = re.fullmatch(r"([0-9০-৯.]+)%", t)
    if pct:
        return localize_digits(pct.group(1), language) + "%", 0.0
    if t in NUM_WORDS:
        n = NUM_WORDS[t]
        return localize_digits(str(n), language), float(n)
    hy = re.fullmatch(r"([a-z]+)-([a-z]+)", t)                     # "eighty-four"
    if hy and hy.group(1) in EN_TENS and hy.group(2) in EN_UNITS:
        n = EN_TENS[hy.group(1)] + EN_UNITS[hy.group(2)]
        return localize_digits(str(n), language), float(n)
    return None


SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000, "trillion": 1_000_000_000_000,
          "শত": 100, "শো": 100, "হাজার": 1_000, "লাখ": 100_000, "লক্ষ": 100_000, "কোটি": 10_000_000}


def _scaled(disp: str, val: float, scale_word: str, language: str) -> tuple[str, float]:
    """'three' + 'thousand' -> ('3,000', 3000); '1' + 'trillion' -> ('1 trillion', 1e12); Bangla keeps its own words ('৩ হাজার')."""
    k = SCALES[scale_word]
    v = val * k
    if re.search(r"[ঀ-৿]", scale_word):
        return f"{disp} {scale_word}", v
    if k <= 1_000 and v < 1_000_000 and float(v).is_integer():
        return localize_digits(f"{int(v):,}", language), v
    return f"{disp} {scale_word}", v


def _number_items(ws: list[Word], language: str = "bn") -> list[dict]:
    out = []
    skip = set()
    for i, w in enumerate(ws):
        if i in skip:
            continue
        p = parse_number(w, language)
        if not p:
            continue
        disp, val = p
        t0 = norm_token(w.text)
        if t0 in EN_TENS and i + 1 < len(ws) and norm_token(ws[i + 1].text) in EN_UNITS and not w.text.rstrip().endswith((",", ".")):
            val = float(EN_TENS[t0] + EN_UNITS[norm_token(ws[i + 1].text)])            # "eighty four" is 84, not 80 and 4
            disp = localize_digits(str(int(val)), language)
            skip.add(i + 1)
            i += 1
        if i + 1 < len(ws) and norm_token(ws[i + 1].text) in SCALES and not disp.endswith("%") and disp[:1] not in "$€£¥₹৳":
            disp, val = _scaled(disp, val, norm_token(ws[i + 1].text), language)     # "three thousand light years" is one number
            skip.add(i + 1)
            ws_rest = ws[i + 1:]
            i_for_next = i + 1
            if SCALES[norm_token(ws[i + 1].text)] in (100, 1_000) and re.fullmatch(r"\d[\d,]*", disp) and not ws[i + 1].text.rstrip().endswith((",", ".")):   # "two hundred and fifty five" is 255
                j = i + 2
                if j < len(ws) and norm_token(ws[j].text) == "and":
                    j += 1
                rest, tok = 0, norm_token(ws[j].text) if j < len(ws) else ""
                if tok in EN_TENS:
                    rest, j = EN_TENS[tok], j + 1
                    if j < len(ws) and norm_token(ws[j].text) in EN_UNITS and not ws[j - 1].text.rstrip().endswith((",", ".")):
                        rest, j = rest + EN_UNITS[norm_token(ws[j].text)], j + 1
                elif tok in EN_UNITS or (tok in NUM_WORDS and NUM_WORDS[tok] < 20 and tok.isascii()):
                    rest, j = EN_UNITS.get(tok) or NUM_WORDS[tok], j + 1
                if rest:
                    val += rest
                    disp = localize_digits(f"{int(val):,}", language)
                    skip.update(range(i + 2, j))
                    i_for_next = j - 1
        else:
            i_for_next = i
        nxt = norm_token(ws[i_for_next + 1].text) if i_for_next + 1 < len(ws) else ""
        prv = norm_token(ws[i - 1].text) if i > 0 else ""
        kind = "plain"
        if disp[:1] in "$€£¥₹৳":
            kind = "money"
        elif nxt in CURRENCY or prv in CURRENCY:
            disp, kind = SYMBOLS[nxt if nxt in CURRENCY else prv] + disp, "money"
        elif nxt in PERCENT or disp.endswith("%"):
            disp, kind = (disp if disp.endswith("%") else disp + "%"), "percent"
        label = ""
        if kind == "plain" and i_for_next + 1 < len(ws):      # "10000 creators", "4.8 stars": a plain number is usually named by the word after it
            nx = ws[i_for_next + 1]
            if not _is_stop(nx) and parse_number(nx) is None and norm_token(nx.text) not in CURRENCY | PERCENT and norm_token(nx.text) not in QUANTIFIERS:
                label = nx.text.strip(" ,.।?!")
                if i_for_next + 2 < len(ws) and not nx.text.rstrip().endswith((",", ".")):      # "3,000 light years": a singular word + a plural noun is one name
                    n2 = norm_token(ws[i_for_next + 2].text)
                    if n2.endswith("s") and not norm_token(nx.text).endswith("s") and not _is_stop(ws[i_for_next + 2]) and len(label) + len(n2) < 18:
                        from ..visuals.terms import noun_share

                        if noun_share(n2) >= 0.8:
                            label = f"{label} {ws[i_for_next + 2].text.strip(' ,.।?!')}"
        if not label:
            for j in range(i - 1, max(-1, i - 4), -1):
                if not _is_stop(ws[j]) and parse_number(ws[j]) is None and norm_token(ws[j].text) not in CURRENCY and norm_token(ws[j].text) not in QUANTIFIERS:
                    label = ws[j].text.strip(" ,.।?!")
                    break
        out.append({"i": i, "word": w, "disp": disp, "kind": kind, "label": label, "val": val})
    return out


def _keyword(ws: list[Word], topics=None) -> Optional[Word]:
    """The key term of these words (a noun-like, specific, often-repeated word), or None when there is none worth a headline."""
    from ..visuals import terms as T

    cands = [w for w in ws if not _is_stop(w) and parse_number(w) is None and len(norm_token(w.text)) >= 3 and T.is_key_term(w.text, topics)]
    if not cands:
        return None
    return max(cands, key=lambda w: T.score(w.text, topics))


def _icon_for(ws: list[Word]) -> Optional[str]:
    for w in ws:
        ic = ICON_KEYWORDS.get(norm_token(w.text))
        if ic:
            return ic
    return None


def _group_beats(beats: Beats, lo: float = 5.0, hi: float = 10.0) -> list[list]:
    groups: list[list] = []
    cur: list = []
    for b in beats.beats:
        if cur and (b.end - cur[0].start > hi or (cur[-1].end - cur[0].start) >= lo):
            groups.append(cur)
            cur = []
        cur.append(b)
    if cur:
        groups.append(cur)
    return groups


def _visual_elements(pick, pattern: int, ws_pick: Word, long_scene: bool) -> list[dict]:
    """Elements that show the stressed word and its picture. `pattern` rotates the look so scenes do not repeat."""
    text = pick.text[:30]
    at = pick.word_id
    st, ic = pick.sticker, pick.line
    if pick.kind == "text" or (not st and not ic):
        style = ("underline", "highlight", "stamp")[pattern % 3]
        return [{"type": "keyword", "text": text, "style": style, "at_word": at}]
    if pattern % 4 == 0 and st:
        return [{"type": "sticker", "emoji": st, "label": text[:26], "at_word": at}]
    if pattern % 4 == 1:
        el = {"type": "keyword", "text": text, "style": "underline", "at_word": at}
        el.update({"emoji": st} if st else {"icon": ic})
        return [el]
    if pattern % 4 == 2:
        el = {"type": "keyword", "text": text, "style": "highlight", "at_word": at}
        el.update({"icon": ic} if ic else {"emoji": st})
        return [el]
    if st:
        return [{"type": "sticker", "emoji": st, "at_word": at}, {"type": "keyword", "text": text, "style": "stamp", "at_word": at}] if long_scene \
            else [{"type": "sticker", "emoji": st, "label": text[:26], "at_word": at}]
    return [{"type": "icon", "name": ic, "label": text[:26], "at_word": at}]


def plan_rules(tr: Transcript, beats: Beats, theme: str = "paper", audio=None, picks=None, language: str = "bn") -> ScenesFile:
    """A complete, valid plan without AI. Every scene shows the word the speaker stressed (found from the audio) with the
    visual that fits it in context, or a number card when numbers are spoken. Claude can improve on it through MCP."""
    from collections import Counter

    if picks is None:
        try:
            from ..visuals.picker import pick_visuals

            picks = pick_visuals(tr, beats, audio)
        except Exception:        # no dictionary/model available: fall back to typography-only keyword scenes
            picks = {}
    words = tr.by_id()
    beat_by = {b.id: b for b in beats.beats}
    groups = _group_beats(beats)
    scenes = []
    last_kind = ""
    pattern = 0
    for si, grp in enumerate(groups):
        ws: list[Word] = [words[wid] for b in grp for wid in b.word_ids if wid in words]
        if not ws:
            continue
        els: list[dict] = []
        nums = _number_items(ws, language)
        compare = len(nums) >= 2 and any(norm_token(w.text) in COMPARE_KW for w in ws)
        scene_picks = sorted((picks[b.id] for b in grp if b.id in picks), key=lambda k: -k.score)
        primary = scene_picks[0] if scene_picks else None
        dur = beat_by[grp[-1].id].end - beat_by[grp[0].id].start

        if compare:
            a_, b_ = nums[0], nums[1]
            els.append({"type": "compare", "left": {"title": a_["label"][:20], "value": a_["disp"][:12]},
                        "right": {"title": b_["label"][:20], "value": b_["disp"][:12]}, "at_word": a_["word"].id})
            last_kind = "compare"
        elif nums:
            n = nums[0]
            if n["kind"] == "percent" and last_kind != "big_number":
                els.append({"type": "big_number", "value": n["disp"].rstrip("%"), "unit": "%", "label": n["label"][:40], "at_word": n["word"].id})
                last_kind = "big_number"
            else:
                els.append({"type": "value_card", "value": n["disp"][:14], "label": n["label"][:36], "at_word": n["word"].id})
                last_kind = "value_card"
            if len(nums) >= 2 and nums[1]["kind"] == n["kind"]:
                els.append({"type": "arrow", "direction": "down", "at_word": nums[1]["word"].id})
                els.append({"type": "tag", "text": nums[1]["disp"][:28], "at_word": nums[1]["word"].id})
            elif primary and primary.sticker and primary.word_id != n["word"].id and len(els) < 3:
                els.append({"type": "sticker", "emoji": primary.sticker, "at_word": primary.word_id})
        elif primary:
            els = _visual_elements(primary, pattern, words[primary.word_id], dur >= 6.5)
            pattern += 1
            last_kind = els[0]["type"]
            # one sentence often carries several ideas ("his son was lazy and careless"): show each as its own picture, in speech order
            used = {primary.sticker or primary.line}
            for k in (x for b in grp for x in (picks.get(b.id).extras if picks.get(b.id) else [])):
                vid = k["sticker"] or k["line"]
                if len(els) >= 3 or vid in used:
                    continue
                used.add(vid)
                els.append({"type": "sticker", "emoji": k["sticker"], "label": k["text"][:26], "at_word": k["word_id"]} if k["sticker"] else
                           {"type": "icon", "name": k["line"], "label": k["text"][:26], "at_word": k["word_id"]})
            els.sort(key=lambda e: words[e["at_word"]].start)
            # a long scene gets a second, smaller visual for another stressed word so something changes every few seconds
            if dur >= 7.5 and len(scene_picks) > 1 and len(els) < 3:
                other = next((k for k in scene_picks[1:] if k.word_id != primary.word_id and k.kind != "text"), None)
                if other and (other.line or other.sticker):
                    els.append({"type": "icon", "name": other.line, "label": other.text[:26], "at_word": other.word_id} if other.line else
                               {"type": "sticker", "emoji": other.sticker, "label": other.text[:26], "at_word": other.word_id})
        else:   # no pick (dictionary unavailable): the longest content word as typography
            kw = _keyword(ws)
            if kw:
                els.append({"type": "keyword", "text": kw.text.strip(" ,.।?!")[:30], "style": ("underline", "highlight", "stamp")[pattern % 3], "at_word": kw.id})
                pattern += 1

        hl: list[str] = []
        if nums:
            hl = [nums[0]["word"].id]
        elif primary:
            hl = [primary.word_id]
        else:
            tail = [w for w in ws[-5:] if not _is_stop(w)]
            if tail:
                hl = [max(tail, key=lambda w: len(norm_token(w.text))).id]

        scenes.append({
            "id": f"s{si + 1}",
            "beats": [b.id for b in grp],
            "layout": "stack",
            "transition_in": "cut" if si == 0 else TRANSITIONS[(si - 1) % len(TRANSITIONS)],
            "elements": els[:5],
            "tone": si % 4,
            "caption": {"highlight_words": hl},
        })
    return ScenesFile.model_validate({"theme": theme, "planner": "rules", "scenes": scenes})
