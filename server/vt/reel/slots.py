"""Slots: the stretches of the cut audio that each get one picture.

A slot is one or more whole sentences. How many follows from what is being said, not from a setting: a story moves faster than steps; a new point
or a "Step 2" starts a new slot; a very long sentence is one slot (its picture keeps moving). Variable lengths are the point.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# kind -> (target words per picture, longest a picture may stay, fewest words worth a picture of their own)
PACE = {"steps": (9, 3.0, 4), "story": (7, 3.0, 3), "explanation": (8, 3.0, 4), "argument": (9, 3.0, 4), "list": (7, 3.0, 3), "opinion": (8, 3.0, 4)}   # nothing holds over 3 s: the three-second rule


LONG_FORM_SECONDS = 180.0


@dataclass
class Slot:
    id: str
    beats: list[Any]
    card: str = ""                      # a chapter jump ("DAY 26", "STEP 2") shown as a title card for this slot
    turn: bool = False
    words: int = 0
    start: float = 0.0
    end: float = 0.0
    notes: list[Any] = field(default_factory=list)
    emphasis_id: str = ""               # the word the picture changes on and the caption lights up, when the person chose it in the plan

    @property
    def seconds(self) -> float:
        return self.end - self.start


def build_slots(beats: list[Any], reading) -> list[Slot]:
    target, longest, fewest = PACE.get(reading.kind, PACE["explanation"])
    if beats and beats[-1].end - beats[0].start > LONG_FORM_SECONDS:        # a long story breathes: the long-form example holds a picture about 5 s, a short reel about 2.3 s
        target, longest = round(target * 1.6), longest * 1.6
    jump = {j.beat: j.label for j in reading.jumps}
    slots: list[Slot] = []
    cur: list[Any] = []

    def close() -> None:
        nonlocal cur
        if cur:
            note = [reading.note(b.id) for b in cur]
            slots.append(Slot(id=f"s{len(slots) + 1}", beats=cur, card=jump.get(cur[0].id, ""), turn=bool(note[0] and note[0].turn),
                              words=sum(len(b.text.split()) for b in cur), start=cur[0].start, end=cur[-1].end, notes=[n for n in note if n]))
        cur = []

    for b in beats:
        n = len(b.text.split())
        note = reading.note(b.id)
        have = sum(len(x.text.split()) for x in cur)
        opens = b.id in jump or (note is not None and note.turn and have >= fewest)
        too_long = cur and (b.end - cur[0].start > longest or have + n > target * 1.4)
        if cur and (opens or too_long or have >= target):
            close()
        cur.append(b)
    close()
    # a slot too short to read as a picture joins its neighbour, unless it is a chapter card
    merged: list[Slot] = []
    for s in slots:
        if merged and s.words < fewest and not s.card and merged[-1].seconds + s.seconds <= longest:
            prev = merged[-1]
            prev.beats += s.beats
            prev.words += s.words
            prev.end = s.end
            prev.notes += s.notes
        else:
            merged.append(s)
    for i, s in enumerate(merged, 1):
        s.id = f"s{i}"
    return merged
