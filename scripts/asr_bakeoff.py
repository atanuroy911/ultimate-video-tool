"""M0 benchmark: compare ASR models through the SAME pipeline code the app uses (chunking, word snapping, script policy).
Usage: python scripts/asr_bakeoff.py bn-medium,large-v3 samples/audio/banglish.mp3 [more clips]
Reports word error rate (all / Bangla words / English words), speed (x realtime) and word-timing sanity.
The built-in references match the synthetic clips from scripts/make_sample_audio.py; for your own recordings put the
true text in <clip>.txt next to the audio. Synthetic speech is only a sanity check; real recordings are what matter."""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from vt.stages import align, asr, audio as A  # noqa: E402
from vt.stages.chunks import plan_chunks  # noqa: E402
from vt.stages.terms import to_policy  # noqa: E402
from vt.stages.words import detect_lang  # noqa: E402

REFS = {
    "bn_plain": "ইয়েল্ড মানে কী ধরুন দোকানের দাম একশো টাকা বছরে ভাড়া পাচ্ছেন তিন টাকা এটাকে বলে গ্রস ইয়েল্ড চার শতাংশ কিন্তু খরচ বাদ দিয়া পকেটে যেটা থাকবে সেটাই আসল নেট ইয়েল্ড",
    "banglish": "আজকের টপিক হলো রিয়েল এস্টেট ইনভেস্টমেন্ট ধরুন আপনি একটা flat কিনলেন পঞ্চাশ লাখ টাকায় মাসে পঁচিশ হাজার টাকা rent পাচ্ছেন তাহলে gross yield হবে ছয় শতাংশ কিন্তু maintenance আর tax বাদ দিলে net yield কমে চার শতাংশ হয়ে যায়",
}


def toks(s: str, policy: str = "mixed") -> list[str]:
    """Normalise both sides the same way: NFC, no punctuation, English terms in Latin letters (the default script policy)."""
    s = unicodedata.normalize("NFC", s).lower()
    t = [x for x in re.sub(r"[.,;:!?।\"'()\-–—]", " ", s).split() if x]
    return [to_policy(x, policy).lower() for x in t]


def edit_ops(ref, hyp):
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]))
    ops, i, j = [], n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            ops.append(("ok" if ref[i - 1] == hyp[j - 1] else "sub", ref[i - 1], hyp[j - 1]))
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            ops.append(("del", ref[i - 1], None))
            i -= 1
        else:
            ops.append(("ins", None, hyp[j - 1]))
            j -= 1
    return ops[::-1]


def wer(ref, hyp, lang=None):
    errs = tot = 0
    for op, r, h in edit_ops(ref, hyp):
        if r is not None and lang and detect_lang(r) != lang:
            continue
        if r is None and lang and h and detect_lang(h) != lang:
            continue
        if r is not None:
            tot += 1
        if op != "ok":
            errs += 1
    return (errs / tot if tot else 0.0), tot


def main() -> None:
    models = sys.argv[1].split(",")
    for clip in map(Path, sys.argv[2:]):
        ref_text = (clip.with_suffix(".txt").read_text(encoding="utf-8") if clip.with_suffix(".txt").exists() else REFS.get(clip.stem))
        wav = Path(tempfile.mkdtemp()) / "a.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip), "-ar", "16000", "-ac", "1", str(wav)], check=True)
        sil, dur, thr, db = A.find_silences(wav, 0.2, None, return_db=True)
        chunks = plan_chunks(dur, sil, db)
        for model in models:
            t0 = time.time()
            res = asr.transcribe(wav, model=model, language="bn", chunks=chunks)
            dt = time.time() - t0
            words, dropped = align.snap_words(res["words"], sil, dur)
            hyp = toks(" ".join(w["text"] for w in words))
            print(f"\n[{clip.stem} | {model}] {dur:.1f}s audio in {dt:.1f}s (x{dur / max(dt, 1e-3):.1f} realtime), {len(words)} words, {dropped} dropped")
            print("   HYP:", " ".join(to_policy(w["text"], "mixed") for w in words))
            if ref_text:
                ref = toks(ref_text)
                a, n = wer(ref, hyp)
                b, nb = wer(ref, hyp, "bn")
                e, ne = wer(ref, hyp, "en")
                print(f"   WER all {a:.0%} ({n} words)   Bangla {b:.0%} ({nb})   English {e:.0%} ({ne})")
            over = [w for a_, w in zip(words, words[1:]) if a_["end"] > w["start"] + 1e-6]
            print(f"   timing: first word {words[0]['start']:.2f}s, last word ends {words[-1]['end']:.2f}s, overlaps {len(over)}")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
