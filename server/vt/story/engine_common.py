"""Text helpers from the story engine's planner/common.py (the audio alignment there is not needed: our words already carry their times)."""
import re


def norm_words(s):
    """normalised word list used to prove captions == SRT words"""
    s = re.sub(r'[{}“”"«»\n]', ' ', s)
    s = re.sub(r'([।,?!.;:])', ' ', s)
    return s.split()


# ---------------- audio ----------------


def wrap(t, width=26):
    t = t.strip()
    if len(t.replace('{', '').replace('}', '')) <= width:
        return t
    mid = len(t) // 2
    spaces = [i for i, c in enumerate(t) if c == ' ']
    if not spaces:
        return t
    cut = min(spaces, key=lambda i: abs(i - mid))
    return t[:cut] + '\n' + t[cut + 1:]
