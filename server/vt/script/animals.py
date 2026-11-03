"""Animals are not played by people: a cast member who is an animal becomes an animal actor drawn from its picture.

The director (an AI or the rules) sometimes casts "the lion" or "নেকড়ে" as a stick figure. After any script is written, every person
whose name, id or role names an animal (English or Bangla) is turned into an emoji actor of that animal; the stick engine then
draws the animal and moves it with the same verbs (walks, jumps, bounces...). In the cartoon style the dog then becomes the
illustrated dog (vt/art/toon.toonify).
"""
from __future__ import annotations

import re

# word (English, Bangla spellings) -> emoji code point (Twemoji names in assets)
ANIMALS: dict[str, str] = {}
for code, words in {
    "1f981": "lion সিংহ", "1f42d": "mouse rat ইঁদুর ইদুর", "1f43a": "wolf নেকড়ে নেকড়", "1f426": "bird crane heron crow sparrow বক কাক পাখি চড়ুই",
    "1f412": "monkey ape বানর বাদর বাঁদর", "1f415": "dog puppy কুকুর", "1f408": "cat kitten বিড়াল বেড়াল", "1f98a": "fox jackal শিয়াল শেয়াল",
    "1f407": "rabbit hare খরগোশ", "1f405": "tiger বাঘ", "1f418": "elephant হাতি", "1f404": "cow bull ox গরু ষাঁড়", "1f410": "goat ছাগল",
    "1f40e": "horse ঘোড়া", "1f40d": "snake সাপ", "1f438": "frog ব্যাঙ", "1f41f": "fish মাছ", "1f43b": "bear ভালুক", "1f98c": "deer হরিণ",
    "1f422": "tortoise turtle কচ্ছপ", "1f41c": "ant পিঁপড়া পিপড়া", "1f41d": "bee মৌমাছি", "1f989": "owl পেঁচা প্যাঁচা", "1f986": "duck হাঁস",
    "1f414": "hen chicken rooster মুরগি মোরগ", "1f416": "pig শূকর", "1f411": "sheep lamb ভেড়া", "1f42b": "camel উট", "1f40a": "crocodile কুমির",
    "1f985": "eagle ঈগল", "1f99c": "parrot টিয়া", "1f98b": "butterfly প্রজাপতি", "1f40c": "snail শামুক", "1f42c": "dolphin ডলফিন",
}.items():
    for w in words.split():
        ANIMALS[w] = code
_LATIN = re.compile(r"\b(" + "|".join(sorted((w for w in ANIMALS if w.isascii()), key=len, reverse=True)) + r")(?:e?s)?\b", re.I)


def animal_of(text: str) -> str | None:
    """The emoji code of the animal a name names ("the old lion", "নেকড়েটা", "Mouse"), or None."""
    t = text or ""
    m = _LATIN.search(t)
    if m:
        return ANIMALS[m.group(1).lower()]
    for w, code in ANIMALS.items():
        if not w.isascii() and w in t:
            return code
    return None


def animalize(script):
    """Turn every animal in the cast into an animal actor. Returns (script, how many were changed)."""
    s = script.model_copy(deep=True)
    n = 0
    for c in s.cast:
        if c.kind != "person":
            continue
        code = animal_of(f"{c.name} {c.id.replace('_', ' ')}") or (animal_of(c.role) if c.role == "animal" else None)
        if code:
            c.kind, c.emoji = "emoji", code
            n += 1
    return s, n
