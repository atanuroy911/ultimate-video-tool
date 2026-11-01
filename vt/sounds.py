"""Sounds that are not speech: laughter, applause, music, rain, a dog, a crying baby ... found in the voice track and turned into events with a meaning.

An audio tagger (the Audio Spectrogram Transformer trained on Google's AudioSet, 527 kinds of sound; it runs through `transformers`, on the GPU when there is one) listens to
overlapping 3-second windows. Its labels are grouped into a few dozen *concepts* (see CONCEPTS: each has a caption, an emoji and a search phrase for pictures), neighbouring
windows with the same concept are merged into events, and the events are saved as `sounds_events.json` next to the project. The planners use them to put a fitting picture on screen
where the sound happens; a recording with no speech at all gets captions such as "[Baby laughing]" so it can still become a video.
"""
from __future__ import annotations

import threading
from typing import Any, Optional

import numpy as np

from .util import read_json, write_json

MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"
SR = 16000
WIN, HOP = 3.0, 1.5
_lock = threading.Lock()
_pipe: Any = None

# concept -> (caption, emoji hex, picture search phrase, AudioSet labels that mean it)
CONCEPTS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "laughter": ("People laughing", "1f602", "people laughing", ("Laughter", "Giggle", "Snicker", "Belly laugh", "Chuckle, chortle")),
    "baby_laughter": ("Baby laughing", "1f476", "baby laughing", ("Baby laughter",)),
    "baby": ("Baby sounds", "1f476", "baby", ("Babbling", "Baby cry, infant cry", "Child speech, kid speaking")),
    "crying": ("Someone crying", "1f622", "person crying", ("Crying, sobbing", "Whimper", "Wail, moan")),
    "applause": ("Crowd applauding", "1f44f", "audience applauding", ("Applause", "Clapping")),
    "cheering": ("Crowd cheering", "1f389", "crowd cheering", ("Cheering", "Hubbub, speech noise, speech babble", "Yell", "Shout")),
    "music": ("Music playing", "1f3b5", "musician playing", ("Music", "Musical instrument", "Pop music", "Hip hop music", "Rock music", "Electronic music", "Classical music", "Ambient music", "Background music", "Theme music", "Soundtrack music", "Jazz", "Folk music", "Piano", "Guitar", "Violin, fiddle", "Drum", "Singing", "Song")),
    "rain": ("Rain falling", "1f327", "rain falling", ("Rain", "Raindrop", "Rain on surface", "Pink noise", "Stream", "Waterfall")),
    "thunder": ("Thunder rumbling", "26c8", "thunderstorm", ("Thunder", "Thunderstorm")),
    "wind": ("Wind blowing", "1f4a8", "wind blowing trees", ("Wind", "Wind noise (microphone)", "Rustling leaves")),
    "water": ("Water flowing", "1f30a", "ocean waves", ("Ocean", "Waves, surf", "Water", "Splash, splatter", "Gurgling")),
    "dog": ("Dog barking", "1f415", "dog", ("Dog", "Bark", "Howl", "Bow-wow", "Growling")),
    "cat": ("Cat meowing", "1f408", "cat", ("Cat", "Meow", "Purr")),
    "bird": ("Birds singing", "1f426", "birds singing", ("Bird", "Bird vocalization, bird call, bird song", "Chirp, tweet", "Crow", "Rooster", "Owl")),
    "farm": ("Farm animals", "1f404", "farm animals", ("Cattle, bovinae", "Moo", "Pig", "Oink", "Sheep", "Horse", "Neigh, whinny", "Livestock, farm animals, working animals")),
    "insects": ("Insects chirping", "1f997", "crickets night", ("Insect", "Cricket", "Mosquito", "Bee, wasp, etc.", "Buzz")),
    "traffic": ("Traffic passing", "1f697", "city traffic", ("Vehicle", "Car", "Traffic noise, roadway noise", "Car passing by", "Truck", "Engine", "Motor vehicle (road)", "Honk", "Vehicle horn, car horn, honking")),
    "train": ("Train passing", "1f686", "train", ("Train", "Railroad car, train wagon", "Rail transport", "Train horn")),
    "aircraft": ("Aircraft flying", "2708", "airplane", ("Aircraft", "Aircraft engine", "Airplane", "Helicopter", "Jet engine")),
    "boat": ("Boat sailing", "26f5", "boat on water", ("Boat, Water vehicle", "Ship", "Motorboat, speedboat")),
    "bell": ("Bell ringing", "1f514", "bell ringing", ("Bell", "Church bell", "Ding", "Chime", "Doorbell")),
    "phone": ("Phone ringing", "1f4de", "phone ringing", ("Telephone", "Telephone bell ringing", "Ringtone", "Alarm clock", "Alarm")),
    "kitchen": ("Kitchen sounds", "1f373", "cooking in kitchen", ("Frying (food)", "Sizzle", "Boiling", "Cutlery, silverware", "Dishes, pots, and pans", "Chopping (food)", "Microwave oven")),
    "typing": ("Keys typing", "2328", "typing on keyboard", ("Typing", "Computer keyboard", "Typewriter", "Mouse click")),
    "footsteps": ("Footsteps walking", "1f463", "walking", ("Walk, footsteps", "Run", "Shuffle")),
    "door": ("Door closing", "1f6aa", "door opening", ("Door", "Slam", "Knock", "Creak", "Squeak")),
    "gunfire": ("Loud bang", "1f4a5", "explosion", ("Gunshot, gunfire", "Explosion", "Boom", "Fireworks", "Firecracker", "Bang")),
    "fire": ("Fire crackling", "1f525", "campfire", ("Fire", "Crackle", "Fire crackle")),
    "whistle": ("Whistle blowing", "1f3b6", "whistle", ("Whistle", "Whistling")),
    "cough": ("Person coughing", "1f637", "person coughing", ("Cough", "Sneeze", "Throat clearing", "Sniff")),
    "crowd": ("Crowd noise", "1f465", "crowd of people", ("Children playing", "Children shouting", "Chatter", "Crowd")),
    "silence": ("", "", "", ("Silence",)),
}
LABEL2CONCEPT = {lab.lower(): c for c, (_, _, _, labs) in CONCEPTS.items() for lab in labs}
IGNORE = {"speech", "male speech, man speaking", "female speech, woman speaking", "narration, monologue", "conversation", "inside, small room", "inside, large room or hall",
          "outside, urban or manmade", "outside, rural or natural", "sound effect", "noise", "white noise", "static", "mains hum", "hum", "environmental noise",
          "background noise", "speech synthesizer", "whispering", "silence"}
LABEL_FLOOR = 0.08               # a label below this is noise
MIN_SCORE = 0.3                  # a concept (its labels added up) must reach this to count
MIN_EVENT = 1.0                  # seconds: shorter than this is not an event
UNDER_SPEECH = 0.5               # while someone is speaking, a sound needs this much
HUMAN = {"laughter", "baby_laughter", "applause", "cheering", "crying"}      # sounds people make together with, or instead of, speech keep the normal bar
SPEECH = {"speech", "male speech, man speaking", "female speech, woman speaking", "narration, monologue", "conversation"}
MUSIC_NEEDS = 0.4                # music is only an event when it is the main thing (it is often just under speech)


def concept_of(label: str) -> Optional[str]:
    return LABEL2CONCEPT.get(label.lower())


def _pipeline():
    global _pipe
    with _lock:
        if _pipe is None:
            import torch
            from transformers import pipeline

            _pipe = pipeline("audio-classification", model=MODEL, device=0 if torch.cuda.is_available() else -1)
    return _pipe


def available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401

        return True
    except Exception:
        return False


def windows(n_samples: int, sr: int = SR, win: float = WIN, hop: float = HOP) -> list[tuple[int, int]]:
    w, h = int(win * sr), int(hop * sr)
    if n_samples <= w:
        return [(0, n_samples)]
    out = [(a, a + w) for a in range(0, n_samples - w + 1, h)]
    if out[-1][1] < n_samples - sr // 2:                       # the tail
        out.append((n_samples - w, n_samples))
    return out


def classify(x: np.ndarray, sr: int = SR, progress=None) -> list[dict]:
    """Per window: the five best AudioSet labels. Returns [{"t0", "t1", "labels": [(label, score), ...]}]."""
    pipe = _pipeline()
    spans = windows(len(x), sr)
    out = []
    batch = 8
    for i in range(0, len(spans), batch):
        chunk = spans[i:i + batch]
        res = pipe([{"raw": x[a:b], "sampling_rate": sr} for a, b in chunk], top_k=12, batch_size=batch)
        if len(chunk) == 1 and res and isinstance(res[0], dict):
            res = [res]
        for (a, b), labs in zip(chunk, res):
            out.append({"t0": a / sr, "t1": b / sr, "labels": [(r["label"], float(r["score"])) for r in labs]})
        if progress:
            progress(min(1.0, (i + batch) / len(spans)))
    return out


def to_events(rows: list[dict], total: float) -> list[dict]:
    """Group the windows' labels into concepts and merge windows that agree into events."""
    per: list[tuple[float, float, dict[str, float]]] = []
    for r in rows:
        best: dict[str, float] = {}
        for lab, sc in r["labels"]:
            if lab.lower() in IGNORE or sc < LABEL_FLOOR:
                continue
            c = concept_of(lab)
            if c and c != "silence":
                best[c] = best.get(c, 0.0) + sc                  # AudioSet labels are independent probabilities: "Laughter 0.27 + Giggle 0.18 + Belly laugh 0.15" is laughter
        if "baby_laughter" in best and "laughter" in best:      # laughter heard from a baby is one thing, and it is the more specific one
            best["baby_laughter"] += best.pop("laughter")
        speech = max((sc for lab, sc in r["labels"] if lab.lower() in SPEECH), default=0.0)
        bar = MIN_SCORE if speech < 0.3 else UNDER_SPEECH                        # a voice makes "oink" and "cough" appear: they must be much surer then
        best = {c: min(1.0, v) for c, v in best.items() if v >= (bar if c not in HUMAN else MIN_SCORE)}
        if HUMAN & best.keys() or "baby" in best:               # a baby's laughter or babble sounds like an animal to the model: do not draw the cow
            for c in ("farm", "dog", "cat", "cough"):
                best.pop(c, None)
        if "music" in best and best["music"] < MUSIC_NEEDS:
            best.pop("music")
        per.append((r["t0"], r["t1"], best))
    events: list[dict] = []
    for c in {c for _, _, b in per for c in b}:
        cur: Optional[dict] = None
        for t0, t1, b in per:
            if c in b:
                if cur and t0 <= cur["end"] + 0.01:
                    cur["end"] = max(cur["end"], t1)
                    cur["score"] = max(cur["score"], b[c])
                    cur["n"] += 1
                else:
                    if cur:
                        events.append(cur)
                    cur = {"concept": c, "start": t0, "end": t1, "score": b[c], "n": 1}
        if cur:
            events.append(cur)
    out = []
    for e in sorted(events, key=lambda e: e["start"]):
        if e["end"] - e["start"] < MIN_EVENT:
            continue
        cap, emoji, query, _ = CONCEPTS[e["concept"]]
        out.append({"concept": e["concept"], "label": cap, "emoji": emoji, "query": query, "start": round(max(0.0, e["start"]), 2),
                    "end": round(min(total, e["end"]), 2), "score": round(e["score"], 2)})
    return out


def analyze_array(x: np.ndarray, sr: int = SR, progress=None) -> list[dict]:
    if sr != SR:
        import scipy.signal as ss

        x = ss.resample_poly(x, SR, sr).astype("float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    return to_events(classify(x.astype("float32"), SR, progress), len(x) / SR)


def path(project):
    return project.dir / "sounds_events.json"


def load(project) -> Optional[dict]:
    return read_json(path(project))


def analyze_project(project, progress=None, force: bool = False) -> dict:
    """Listen to the project's voice track (output time, after cuts) and save the events."""
    import soundfile as sf

    from .util import file_hash

    wav = project.cut_audio if project.cut_audio.exists() else project.master
    h = file_hash(wav, extra=f"sounds-v1|{MODEL}")
    old = load(project)
    if old and old.get("hash") == h and not force:
        return old
    x, sr = sf.read(str(wav), dtype="float32", always_2d=False)
    events = analyze_array(x, sr, progress)
    doc = {"hash": h, "model": MODEL, "duration": round(len(x) / sr, 2), "events": events}
    write_json(path(project), doc)
    return doc


def caption_words(events: list[dict], speech: list[tuple[float, float]] | None = None) -> list[dict]:
    """For a recording with no speech: one caption per event, like closed captions for the deaf ('[Baby laughing]'). Returns raw-transcript style words."""
    words = []
    for e in events:
        toks = e["label"].split()
        if not toks:
            continue
        toks[0] = "[" + toks[0]
        toks[-1] = toks[-1] + "]"
        span = max(0.3, e["end"] - e["start"] - (0.6 if e["end"] - e["start"] >= 1.5 else 0.0))      # a pause after the caption, so each sound is a sentence (a scene) of its own
        step = span / len(toks)
        for i, t in enumerate(toks):
            words.append({"text": t, "start": round(e["start"] + i * step, 3), "end": round(e["start"] + (i + 1) * step - 0.01, 3), "conf": round(float(e.get("score", 0.5)), 2)})
    return words


# ---------------------------------------------------------------- the planners' use of the events
VISUAL_SKIP = {"music", "silence", "crowd", "wind", "traffic", "insects", "footsteps", "door", "typing", "kitchen"}      # background sounds that need no picture of their own


LABEL_BN = {"laughter": "হাসি", "baby_laughter": "শিশুর হাসি", "baby": "শিশুর শব্দ", "crying": "কান্না", "applause": "হাততালি", "cheering": "উল্লাস",
            "music": "গান বাজছে", "rain": "বৃষ্টি", "thunder": "বজ্রপাত", "wind": "বাতাস", "water": "পানির শব্দ", "dog": "কুকুরের ডাক", "cat": "বিড়ালের ডাক",
            "bird": "পাখির ডাক", "farm": "পশুর ডাক", "insects": "ঝিঁঝিঁ পোকা", "traffic": "গাড়ির শব্দ", "train": "ট্রেন", "aircraft": "উড়োজাহাজ",
            "boat": "নৌকা", "bell": "ঘণ্টা", "phone": "ফোন বাজছে", "kitchen": "রান্নার শব্দ", "typing": "টাইপিং", "footsteps": "পায়ের শব্দ",
            "door": "দরজার শব্দ", "fire": "আগুন", "whistle": "বাঁশি", "cough": "কাশি", "crowd": "ভিড়ের শব্দ"}


def label_for(concept: str, english: str, language: str) -> str:
    """The sticker's label in the video's language: an English label in a Bangla video reads as a mistake. No translation: no label."""
    if language == "en":
        return english
    return LABEL_BN.get(concept, "") if language == "bn" else ""


def add_stickers(sf, events: list[dict], tr, beats, max_total: int = 12):
    """Put an emoji on screen where a sound happens (laughter, applause, a dog barking...). Works on a plan in place and returns how many were added.
    Each event goes to the scene that is showing at its start (or the nearest one when it falls in a gap), at the word spoken then; a scene never gets two of the same emoji
    or more than four elements."""
    from .schema import Sticker

    words = [w for w in tr.words if not w.cut]
    if not words or not events:
        return 0
    bmap = {b.id: b for b in beats.beats}

    def span(sc):
        bs = [bmap[b] for b in sc.beats if b in bmap]
        return (min(b.start for b in bs), max(b.end for b in bs)) if bs else (0.0, 0.0)

    spans = [(sc, *span(sc)) for sc in sf.scenes]
    added = 0
    for e in sorted(events, key=lambda e: (e["concept"] not in HUMAN, -e["score"])):         # people first: laughter and applause before a barking dog
        if added >= max_total or e["concept"] in VISUAL_SKIP or not e.get("emoji"):
            continue
        mid = e["start"]
        # the scene showing at that moment, else the nearest one with room (a scene holds five elements at most; four keeps it readable)
        order = sorted(spans, key=lambda s: 0.0 if s[1] - 0.05 <= mid <= s[2] + 0.05 else min(abs(s[1] - mid), abs(s[2] - mid)))
        dist = lambda a, b: 0.0 if a - 0.05 <= mid <= b + 0.05 else min(abs(a - mid), abs(b - mid))      # noqa: E731
        if any(dist(a, b) <= 3.0 and any(getattr(x, "type", "") == "sticker" and getattr(x, "emoji", "") == e["emoji"] for x in sc2.elements) for sc2, a, b in spans):
            continue                                                                                   # this sound already has its picture
        pick = next(((sc, a, b) for sc, a, b in order if len(sc.elements) < 4 and (0.0 if a - 0.05 <= mid <= b + 0.05 else min(abs(a - mid), abs(b - mid))) <= 3.0
                     and not any(getattr(x, "type", "") == "sticker" and getattr(x, "emoji", "") == e["emoji"] for x in sc.elements)), None)
        if pick is None:
            continue
        sc, a, b = pick
        ids = {w for bid in sc.beats if bid in bmap for w in bmap[bid].word_ids}
        cand = [w for w in words if w.id in ids] or words
        w = min(cand, key=lambda w: abs(w.start - mid))
        sc.elements.append(Sticker(at_word=w.id, emoji=e["emoji"], label=label_for(e["concept"], e["label"], tr.language)[:26]))
        added += 1
    return added


def plan_from_sounds(sf, events: list[dict], tr, beats):
    """A recording that is only sounds: every scene shows the emoji of the sound that plays during it (and nothing else). Returns (the plan, how many scenes were set)."""
    from .schema import Sticker

    from .scene_ops import split_scene

    for _ in range(len(beats.beats)):                         # one scene per sound
        multi = next((sc for sc in sf.scenes if len(sc.beats) > 1), None)
        if multi is None:
            break
        sf = split_scene(sf, beats, multi.id, multi.beats[1])
    bmap = {b.id: b for b in beats.beats}
    n = 0
    for sc in sf.scenes:
        bs = [bmap[b] for b in sc.beats if b in bmap]
        if not bs:
            continue
        a, b = min(x.start for x in bs), max(x.end for x in bs)
        best = max(events, key=lambda e: min(b, e["end"]) - max(a, e["start"]), default=None)
        if not best or min(b, best["end"]) - max(a, best["start"]) <= 0 or not best.get("emoji"):
            continue
        sc.elements = [Sticker(at_word=bs[0].word_ids[0], emoji=best["emoji"], label=label_for(best["concept"], best["label"], tr.language)[:26])]
        sc.layout = "hero"
        n += 1
    return sf, n
