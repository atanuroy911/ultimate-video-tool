"""Script rules from the owner's reference script (Why Do Billionaires Pay Less Tax Than You?, 2026-11-01): the title spoken first, two
characters, a question chain, toy numbers, one takeaway line per scene, and above all easy words. Three of them measured on the transcript."""
from pathlib import Path

R = Path(__file__).resolve().parents[2]
p = R / "vt/craft.py"
s = p.read_text(encoding="utf-8")


def sub(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)


sub('''    # the hook: the first three seconds decide whether the rest is seen
''', '''    # the script: how the words are written (owner's reference script, 2026-11-01: "the entire script should be easy")
    {"area": "script", "id": "script.title_first", "measured": True, "source": "owner's reference script, 2026-11-01",
     "rule": "The video opens by saying its title out loud, as a question or a promise ('Why do billionaires pay less tax than you?').",
     "why": "The first spoken line is the hook and the title at once: the viewer knows in two seconds what they will get."},
    {"area": "script", "id": "script.easy", "measured": True, "source": "owner, 2026-11-01: 'easy as fuck'",
     "rule": "Easy words in short sentences: about 12 words a sentence on average, none over 20, everyday words; every term is said in "
             "plain words the moment it appears ('the price the tax counts from resets', not 'a step-up in basis').",
     "why": "A viewer who has to decode a sentence scrolls; a short video has no time to re-read."},
    {"area": "script", "id": "script.questions", "measured": True, "source": "owner's reference script, 2026-11-01",
     "rule": "A question chain: each part ends on the question the viewer is now asking ('But then how does he buy a mansion?') and the next "
             "part answers it; at least one question every 40 s.",
     "why": "An open question is the reason to keep watching; answering it opens the next one."},
    {"area": "script", "id": "script.characters", "measured": False, "source": "owner's reference script, 2026-11-01",
     "rule": "Ideas happen to people: one everyday person the viewer is (Jack, a salary) and one contrast (Mr. Rich, shares), with names, "
             "so every idea becomes something that happens to them. Give them a look once (plan cast) so every picture shows the same two.",
     "why": "People remember stories about people; an abstract rule is forgotten."},
    {"area": "script", "id": "script.toy_numbers", "measured": False, "source": "owner's reference script, 2026-11-01",
     "rule": "Show the mechanism with a toy example in round numbers (one share, 100 dollars, then 200), then the real facts, which are only "
             "the ones given or sourced; never invent a figure.",
     "why": "Round numbers can be followed by ear; the real figures then land as proof."},
    {"area": "script", "id": "script.takeaway", "measured": False, "source": "owner's reference script, 2026-11-01",
     "rule": "Each part ends on one short takeaway line; that line is the one put on screen as a full-frame card (it leaves after its line), "
             "and the video ends on the biggest question, not a summary.",
     "why": "The takeaway is what gets screenshotted and remembered; a closing question invites comments and the next video."},
    # the hook: the first three seconds decide whether the rest is seen
''')
sub('''ABSENT = re.compile(''', '''SENT_END = re.compile(r"(?<=[.!?।])\\s+")
LONG_WORD = 10                                    # letters: an English word this long is rarely an everyday word


def script_problems(text: str, title: str = "", seconds: float = 0.0, language: str = "en") -> list[dict]:
    """The measurable script rules on the spoken text (rules script.title_first, script.easy, script.questions)."""
    out: list[dict] = []
    sents = [x.strip() for x in SENT_END.split(re.sub(r"\\s+", " ", text or "").strip()) if x.strip()]
    if not sents:
        return out
    words_in = lambda x: re.findall(r"[\\w'$%]+", x)                           # noqa: E731
    tw = [w.lower() for w in words_in(title) if len(w) > 3]
    first = {w.lower() for w in words_in(sents[0])}
    if tw and sum(w in first for w in tw) < 0.6 * len(tw):
        out.append({"rule": "script.title_first", "says": f"The first line ('{sents[0][:60]}') is not the title said out loud.",
                    "fix": f"Open with the title as a question or a promise: '{title}'."})
    lens = [len(words_in(x)) for x in sents]
    avg = sum(lens) / len(lens)
    if avg > 14:
        out.append({"rule": "script.easy", "says": f"Sentences average {avg:.0f} words.", "fix": "Split them: about 12 words a sentence."})
    for x, n in zip(sents, lens):
        if n > 20:
            out.append({"rule": "script.easy", "says": f"A {n}-word sentence: '{x[:70]}...'", "fix": "Make it two or three short sentences."})
    if language == "en":
        ws = [w for w in words_in(text) if w.isalpha()]
        hard = sorted({w for w in ws if len(w) >= LONG_WORD})
        if ws and len([w for w in ws if len(w) >= LONG_WORD]) / len(ws) > 0.04:
            out.append({"rule": "script.easy", "says": f"Many long words ({', '.join(hard[:6])}).", "fix": "Say them in everyday words."})
    if seconds > 45:
        q = sum(x.endswith("?") for x in sents)
        if q < seconds / 40:
            out.append({"rule": "script.questions", "says": f"{q} question(s) in {seconds:.0f} s.",
                        "fix": "End each part on the question the viewer now has; the next part answers it."})
    return out


ABSENT = re.compile(''')
sub('''    # ending.no_fluff ----''', '''    # script.*: how the words are written -----------------------------------------------------------------------------------------------------
    sp = script_problems(" ".join(b.text for b in beats.beats), getattr(meta, "title", ""), end - start, meta.language)
    for x in sp:
        bad(x["rule"], 0.0, 0.0, x["says"], x["fix"], "minor")
    for rid in ("script.title_first", "script.easy", "script.questions"):
        if not any(x["rule"] == rid for x in sp):
            passed.append(rid)
    # ending.no_fluff ----''')
p.write_text(s, encoding="utf-8")
print("ok")
