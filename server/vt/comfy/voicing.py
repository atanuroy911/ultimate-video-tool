"""Which ComfyUI voice workflow speaks a sentence: the best model that is installed, for this language and this much direction.

The ranking (docs/research/BEST-MODELS.md): Breeze TTS 2 is the most expressive open voice model (free-text direction, vocal events) but speaks English and Chinese only and needs a
GPU with bf16 (RTX 30 series or newer); OmniVoice speaks 600+ languages (Bangla included) in fp16 on older cards. So: English or Chinese with direction -> Breeze, everything else -> OmniVoice,
and when only one family is installed, that one. A voice id is `me:<saved voice>` (cloned from a consented recording) or `design:<a description of the voice>`.
"""
from __future__ import annotations

import re
from typing import Optional

BREEZE_LANGS = ("en", "zh")
DIALECT_OF_WORKFLOW = {"breeze_design": "breeze", "breeze_clone": "breeze", "breeze_direction": "breeze",
                       "omnivoice_design": "omnivoice", "omnivoice_clone": "omnivoice"}


def split_voice(voice: str) -> tuple[str, str]:
    kind, _, rest = voice.partition(":")
    return (kind, rest) if kind in ("me", "design") else ("design", voice)


def pick(voice: str, language: str, available: set[str], *, wants_direction: bool = False) -> Optional[str]:
    """The workflow id to use, or None when nothing installed can speak this."""
    kind, _ = split_voice(voice)
    lang = (language or "en")[:2].lower()
    order: list[str]
    if kind == "design":
        order = (["breeze_design"] if lang in BREEZE_LANGS else []) + ["omnivoice_design"]
    else:
        breeze = (["breeze_direction"] if wants_direction else []) + ["breeze_clone"]
        order = (breeze if lang in BREEZE_LANGS else []) + ["omnivoice_clone"]
    return next((w for w in order if w in available), None)


# OmniVoice accepts only a fixed vocabulary for a designed voice (the server's own error lists it); free text is mapped onto it
_OMNI_ACCENT = {"british": "british accent", "uk": "british accent", "american": "american accent", "us": "american accent", "australian": "australian accent", "canadian": "canadian accent",
                "indian": "indian accent", "chinese": "chinese accent", "japanese": "japanese accent", "korean": "korean accent", "portuguese": "portuguese accent", "russian": "russian accent"}


def omnivoice_instruct(description: str, *, design: bool = True) -> str:
    """'A deep, serious older man speaking slowly' -> 'male, elderly, low pitch'. For a cloned voice only `whisper` is meaningful (the recording sets the rest)."""
    import re

    words = set(re.findall(r"[a-z]+", description.lower()))
    items: list[str] = []
    if "whisper" in description.lower() or "whispering" in words:
        items.append("whisper")
    if not design:
        return ", ".join(items)
    male, female = bool(words & {"male", "man", "men", "boy", "gentleman", "father"}), bool(words & {"female", "woman", "women", "girl", "lady", "mother"})
    if female and not male:
        items.insert(0, "female")
    elif male or not items:
        items.insert(0, "male" if male else "female")
    age = ("child" if words & {"child", "kid", "little"} else "teenager" if words & {"teen", "teenager"} else "elderly" if words & {"elderly", "old", "older", "senior", "aged"}
           else "middle-aged" if "middle" in words or "adult" in words and "young" not in words else "young adult" if words & {"young", "youthful"} else "")
    if age:
        items.append(age)
    deep, high = words & {"deep", "low", "bass", "baritone", "gravelly"}, words & {"high", "bright", "squeaky", "light"}
    very = "very" in words
    if deep:
        items.append("very low pitch" if very else "low pitch")
    elif high:
        items.append("very high pitch" if very else "high pitch")
    elif words & {"moderate", "medium", "even", "natural"}:
        items.append("moderate pitch")
    for k, v in _OMNI_ACCENT.items():
        if k in words:
            items.append(v)
            break
    return ", ".join(dict.fromkeys(items))


CAST = {                      # kind of script -> the voice a director would cast (the descriptions the Voices list offers)
    "steps": "design:A bright, energetic young narrator, quick and upbeat, like a short-video host.",
    "list": "design:A bright, energetic young narrator, quick and upbeat, like a short-video host.",
    "story": "design:A deep, serious older man speaking slowly, like a documentary narrator.",
    "explanation": "design:A calm, thoughtful woman with a clear voice and a gentle, reflective delivery.",
    "argument": "design:A warm, confident adult man with a clear voice and an even, friendly pace.",
    "opinion": "design:A warm, confident adult man with a clear voice and an even, friendly pace.",
}
AUTO_VOICE = "design:auto"


def cast(script: str) -> str:
    """The voice the content calls for (R9): chosen from the kind of script, never from a person's name. The reading's rules are the same ones the reel director uses."""
    from ..reel.reading import rules_kind

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
    return CAST.get(rules_kind(sentences), CAST["explanation"])


def dialect(workflow_id: Optional[str]) -> str:
    return DIALECT_OF_WORKFLOW.get(workflow_id or "", "none")
