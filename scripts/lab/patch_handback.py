"""Round 2: text and cards over a picture hand the frame back. Elements get an end (`until`): the director's `until_word`, else, over a
picture, the end of the sentence that brought them in, held 1.5 to 3 s (craft rule pacing.dwell). The renderer animates the exit."""
from pathlib import Path

R = Path(__file__).resolve().parents[2]


def sub(path, old, new):
    p = R / path
    s = p.read_text(encoding="utf-8")
    assert old in s, (path, old[:80])
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


sub("vt/schema.py", '''    at_word: str = Field(description="id of the spoken word at which this element animates in")
''', '''    at_word: str = Field(description="id of the spoken word at which this element animates in")
    until_word: Optional[str] = Field(default=None, description="id of the spoken word after which it leaves; over a picture it leaves by itself "
                                                                "after its sentence (1.5 to 3 s) so the picture gets the frame back")
''')
sub("vt/schema.py", '''            elif el.at_word not in wset:
                errs.append(f"scene {sc.id}: at_word '{el.at_word}' is outside this scene's beats")''', '''            elif el.at_word not in wset:
                errs.append(f"scene {sc.id}: at_word '{el.at_word}' is outside this scene's beats")
            if el.until_word is not None:
                if el.until_word not in words:
                    errs.append(f"scene {sc.id}: element until_word '{el.until_word}' is not a transcript word")
                elif el.at_word in words and words[el.until_word].start < words[el.at_word].start:
                    errs.append(f"scene {sc.id}: until_word '{el.until_word}' comes before its at_word")''')

sub("vt/compose/composer.py", '''    starts = scene_starts(sf, beats)
    scenes_out = []''', '''    starts = scene_starts(sf, beats)
    sentence_end = {wid: words_by_id[b.word_ids[-1]].end for b in beats.beats for wid in b.word_ids if b.word_ids and b.word_ids[-1] in words_by_id}
    scenes_out = []''')
sub("vt/compose/composer.py", '''            d["at"] = round(at, 3)
            d.pop("at_word", None)
            els.append(d)''', '''            d["at"] = round(at, 3)
            d.pop("at_word", None)
            uw = d.pop("until_word", None)
            if uw in words_by_id:
                d["until"] = round(words_by_id[uw].end + 0.15, 3)
            elif sc.backdrop is not None:                  # over a picture: leave after its sentence so the picture is seen again (pacing.dwell)
                d["until"] = round(min(at + HOLD_MAX, max(at + HOLD_MIN, sentence_end.get(el.at_word, at) + 0.2)), 3)
            if d.get("until", end) >= end - 0.35:          # the scene cuts first: no exit of its own
                d.pop("until", None)
            els.append(d)''')
sub("vt/compose/composer.py", '''def resolve_composition(''', '''HOLD_MIN, HOLD_MAX = 1.5, 3.0                      # pacing.dwell: the main thing for 1.5 to 3 s, then the picture behind it again


def resolve_composition(''')

sub("renderer/runtime/vt.js", '''        if (inst.hideInit) inst.hideInit.forEach((x) => x && gsap.set(x, { opacity: 0 }));
      });''', '''        if (inst.hideInit) inst.hideInit.forEach((x) => x && gsap.set(x, { opacity: 0 }));
        if (typeof e.until === "number" && e.until < sc.end - 0.3) {
          // its line is over: it leaves and the picture behind gets the frame back (pacing.dwell; it used to stay until the scene ended)
          const out = Math.max(at + 0.6, e.until);
          tl.to(w, { opacity: 0, scale: 0.96, duration: 0.28, ease: "power2.in" }, out);
          tl.set(w, { visibility: "hidden" }, out + 0.29);
        }
      });''')
print("ok")
