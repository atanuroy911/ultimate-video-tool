"""AI Highlight & Virality Detector for Shorts.

Adapted from Anil-matcha/AI-Youtube-Shorts-Generator virality framework, enhanced with
Video Tool's word-level boundary snapping, multi-provider LLM execution (vt.ai.providers),
and heuristic safety fallback.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .. import pausesplit, prosody, saliency
from ..ai import providers
from .prompts import (
    CONTENT_TYPE_PROMPT,
    CONTENT_TYPE_SCHEMA,
    HIGHLIGHTS_SCHEMA,
    HIGHLIGHT_SYSTEM_PROMPT,
    VIRALITY_CRITERIA,
)

CHUNK_SIZE_SECONDS = 1200       # 20-minute chunks for long videos
LONG_VIDEO_THRESHOLD = 1800     # chunk videos > 30 minutes
CHUNK_OVERLAP_SECONDS = 60
SENTENCE_PUNCT = (".", "!", "?", "।", "\n")


@dataclass
class SentenceUnit:
    text: str
    start: float
    end: float
    words: list[dict]


def group_words_into_sentences(words: list[dict]) -> list[SentenceUnit]:
    """Group word-level tokens into sentence-like units using punctuation and pauses."""
    if not words:
        return []

    sentences: list[SentenceUnit] = []
    curr_words: list[dict] = []
    curr_text: list[str] = []
    pause_threshold = pausesplit.pause_threshold([max(0.0, float(words[i + 1].get("start", 0.0)) - float(words[i].get("end", 0.0))) for i in range(len(words) - 1)])

    for i, w in enumerate(words):
        t = str(w.get("text", "")).strip()
        if not t:
            continue
        curr_words.append(w)
        curr_text.append(t)

        is_last = (i == len(words) - 1)
        has_punct = any(t.endswith(p) for p in SENTENCE_PUNCT)
        next_pause = 0.0
        if not is_last and i + 1 < len(words):
            next_start = float(words[i + 1].get("start", 0.0))
            curr_end = float(w.get("end", 0.0))
            next_pause = max(0.0, next_start - curr_end)

        # Cut sentence on sentence punctuation, or a pause above this speaker's own threshold (vt/pausesplit.py), or max ~25 words
        if has_punct or next_pause >= pause_threshold or len(curr_words) >= 28 or is_last:
            s_start = float(curr_words[0].get("start", 0.0))
            s_end = float(curr_words[-1].get("end", 0.0))
            sentence_text = " ".join(curr_text).strip()
            if sentence_text:
                sentences.append(SentenceUnit(
                    text=sentence_text,
                    start=round(s_start, 2),
                    end=round(s_end, 2),
                    words=list(curr_words),
                ))
            curr_words = []
            curr_text = []

    return sentences


def build_transcript_text(sentences: list[SentenceUnit]) -> str:
    """Format sentences with timestamps for LLM ingestion."""
    lines = []
    for s in sentences:
        lines.append(f"[{s.start:.1f}s - {s.end:.1f}s] {s.text}")
    return "\n".join(lines)


def detect_content_type(sentences: list[SentenceUnit]) -> dict[str, str]:
    """Analyze the opening minutes to classify genre and information density."""
    sample_text = " ".join(s.text for s in sentences[:30])[:3500]
    prompt = f"{CONTENT_TYPE_PROMPT}\n\nTranscript sample:\n{sample_text}"
    try:
        res = providers.complete_json(prompt, CONTENT_TYPE_SCHEMA)
        if isinstance(res, dict) and "content_type" in res:
            return {
                "content_type": str(res.get("content_type", "monologue")),
                "density": str(res.get("density", "medium")),
            }
    except Exception:
        pass
    return {"content_type": "monologue", "density": "medium"}


def dedupe_highlights(highlights: list[dict], max_overlap_ratio: float = 0.45) -> list[dict]:
    """Drop any highlight that overlaps >45% with a higher-scoring highlight already kept."""
    # Sort descending by viral score
    sorted_h = sorted(highlights, key=lambda x: int(x.get("score", 0)), reverse=True)
    kept: list[dict] = []

    for cand in sorted_h:
        c_start = float(cand.get("start_time", 0.0))
        c_end = float(cand.get("end_time", 0.0))
        c_dur = max(0.1, c_end - c_start)
        overlaps = False

        for k in kept:
            k_start = float(k.get("start_time", 0.0))
            k_end = float(k.get("end_time", 0.0))
            overlap_start = max(c_start, k_start)
            overlap_end = min(c_end, k_end)
            overlap_dur = max(0.0, overlap_end - overlap_start)

            if overlap_dur > 0 and (overlap_dur / c_dur) > max_overlap_ratio:
                overlaps = True
                break

        if not overlaps:
            kept.append(cand)

    return kept


def snap_to_sentence_boundaries(
    highlights: list[dict],
    sentences: list[SentenceUnit],
    duration: float,
) -> list[dict]:
    """Refine LLM timestamps to align cleanly to sentence starts and ends (no cut-off words)."""
    if not sentences:
        return highlights

    snapped: list[dict] = []
    for h in highlights:
        raw_start = float(h.get("start_time", 0.0))
        raw_end = float(h.get("end_time", 0.0))
        if raw_end <= raw_start:
            continue

        # Find closest sentence start
        best_start = raw_start
        min_start_diff = float("inf")
        for s in sentences:
            diff = abs(s.start - raw_start)
            if diff < min_start_diff and diff < 8.0:
                min_start_diff = diff
                best_start = s.start

        # Find closest sentence end
        best_end = raw_end
        min_end_diff = float("inf")
        for s in sentences:
            diff = abs(s.end - raw_end)
            if diff < min_end_diff and diff < 8.0:
                min_end_diff = diff
                best_end = s.end

        # Ensure valid length (between 15s and 95s)
        if best_end - best_start < 15.0:
            # Expand forward
            for s in sentences:
                if s.end - best_start >= 25.0:
                    best_end = s.end
                    break

        best_start = max(0.0, round(best_start, 2))
        best_end = min(duration, round(best_end, 2))

        if best_end > best_start + 12.0:
            h_copy = dict(h)
            h_copy["start_time"] = best_start
            h_copy["end_time"] = best_end
            h_copy["duration"] = round(best_end - best_start, 2)
            snapped.append(h_copy)

    return snapped


def candidate_windows(sentences: list[SentenceUnit], target_seconds: float = 45.0, min_seconds: float = 20.0) -> list[tuple[int, int]]:
    """Sentence index ranges [i, j) that make a short of about `target_seconds`, one starting at every sentence."""
    out = []
    for i in range(len(sentences)):
        j = i
        while j < len(sentences) and sentences[j].end - sentences[i].start < target_seconds:
            j += 1
        if sentences[min(j, len(sentences)) - 1].end - sentences[i].start >= min_seconds:
            out.append((i, j))
    return out


def measured_signals(sentences: list[SentenceUnit], windows: list[tuple[int, int]], audio_path=None, sound_events=None) -> dict[str, list[float]]:
    """Per window: transcript centrality (LexRank, mean of the window's sentences), prosodic arousal (z-score), and the share of
    the window with laughter or applause. These are the measured signals that Rhapsody (arXiv 2505.19429) found to add to any
    transcript model; the AI's own virality score is the fourth."""
    centrality = saliency.lexrank([s.text for s in sentences])
    spans = [(sentences[i].start, sentences[j - 1].end) for i, j in windows]
    out = {"centrality": [sum(centrality[i:j]) / max(1, j - i) for i, j in windows]}
    words = [w for s in sentences for w in s.words]
    out["arousal"] = prosody.arousal_for(Path(audio_path), spans, words) if audio_path else [0.0] * len(windows)
    reactions = [(float(e.get("start", 0)), float(e.get("end", 0))) for e in (sound_events or []) if e.get("concept") in ("laughter", "applause", "cheering")]
    out["reaction"] = [sum(max(0.0, min(e1, b) - max(e0, a)) for e0, e1 in reactions) / max(0.1, b - a) for a, b in spans]
    return out


def fuse_scores(ai_score: list[float], signals: dict[str, list[float]], weights=(0.5, 0.2, 0.2, 0.1)) -> list[float]:
    """One 0-100 score per window: AI judgement, transcript centrality, arousal, audience reaction. The AI alone is barely
    better than a heuristic on podcasts (Rhapsody: GPT-4o zero-shot ≈ frequency baseline), so the measured signals share the weight."""
    n = len(ai_score)
    if n == 0:
        return []

    def scaled(values: list[float]) -> list[float]:
        lo, hi = min(values), max(values)
        return [(v - lo) / (hi - lo) if hi > lo else 0.5 for v in values]

    parts = [scaled([float(a) for a in ai_score]), scaled(signals["centrality"]), scaled(signals["arousal"]), scaled(signals["reaction"])]
    return [round(100 * sum(w * p[i] for w, p in zip(weights, parts)), 1) for i in range(n)]


def pick_diverse(highlights: list[dict], sentences: list[SentenceUnit], num_clips: int, lam: float = 0.7) -> list[dict]:
    """The final shorts: Maximal Marginal Relevance over time overlap and text similarity, so five shorts are five different moments."""
    if not highlights:
        return []
    texts = []
    for h in highlights:
        inside = [s.text for s in sentences if s.start >= float(h["start_time"]) - 0.01 and s.end <= float(h["end_time"]) + 0.01]
        texts.append(" ".join(inside) or str(h.get("hook_sentence", "")))
    text_sim = saliency.similarity_matrix(texts)
    n = len(highlights)
    sim = [[0.0] * n for _ in range(n)]
    for a in range(n):
        for b in range(n):
            s0, e0 = float(highlights[a]["start_time"]), float(highlights[a]["end_time"])
            s1, e1 = float(highlights[b]["start_time"]), float(highlights[b]["end_time"])
            overlap = max(0.0, min(e0, e1) - max(s0, s1)) / max(0.1, min(e0 - s0, e1 - s1))
            sim[a][b] = max(overlap, text_sim[a][b])
    order = saliency.mmr_select([float(h.get("score", 0)) for h in highlights], sim, num_clips, lam)
    return [highlights[i] for i in order]


def rule_fallback_highlights(
    sentences: list[SentenceUnit],
    duration: float,
    num_clips: int = 4,
    audio_path=None,
    sound_events=None,
) -> list[dict]:
    """Highlights without an AI: windows ranked by measured signals (centrality, arousal, reactions) plus rhetorical cues."""
    if not sentences:
        return []
    windows = candidate_windows(sentences)
    if windows:
        signals = measured_signals(sentences, windows, audio_path, sound_events)
        cue_scores = []
        for i, j in windows:
            text = " ".join(s.text for s in sentences[i:j]).lower()
            cue_scores.append(8 * text.count("?") + 5 * text.count("!") + 10 * sum(k in text for k in ("secret", "mistake", "never", "truth", "কেন", "কীভাবে")))
        fused = fuse_scores(cue_scores, signals)
        candidates = []
        for (i, j), score, arousal in zip(windows, fused, signals["arousal"]):
            hook = sentences[i].text
            candidates.append({
                "title": " ".join(hook.split()[:6]).strip(".,!? ") or f"Highlight at {int(sentences[i].start)}s",
                "start_time": round(sentences[i].start, 2), "end_time": round(sentences[j - 1].end, 2),
                "duration": round(sentences[j - 1].end - sentences[i].start, 2), "score": score, "hook_sentence": hook,
                "virality_reason": "central to the talk" + (", the speaker is animated" if arousal > 0.5 else "") + "; measured, not judged by an AI",
                "signals": {"centrality": round(signals["centrality"][windows.index((i, j))], 2), "arousal": round(arousal, 2)},
            })
        return pick_diverse(dedupe_highlights(candidates), sentences, num_clips)

    # Score each sentence window based on hooks, exclamation marks, question marks, and cadence
    candidates: list[dict] = []
    window_target_dur = 45.0  # target 45 seconds

    i = 0
    while i < len(sentences):
        w_start = sentences[i].start
        j = i
        text_parts = []
        score = 50

        while j < len(sentences) and (sentences[j].end - w_start) < window_target_dur:
            s_text = sentences[j].text
            text_parts.append(s_text)
            # Question marks provoke curiosity
            if "?" in s_text:
                score += 8
            # Exclamation marks indicate energy
            if "!" in s_text or "।" in s_text:
                score += 5
            # Catchy hook words
            lower = s_text.lower()
            if any(k in lower for k in ("secret", "mistake", "why", "how to", "never", "always", "truth", "dollar", "money", "হলো", "কেন", "কীভাবে")):
                score += 10
            j += 1

        w_end = sentences[min(j - 1, len(sentences) - 1)].end
        dur = w_end - w_start
        if dur >= 20.0:
            full_text = " ".join(text_parts)
            hook = sentences[i].text
            title = " ".join(hook.split()[:6]).strip(".,!? ")
            candidates.append({
                "title": title or f"Highlight at {int(w_start)}s",
                "start_time": round(w_start, 2),
                "end_time": round(w_end, 2),
                "duration": round(dur, 2),
                "score": min(95, max(40, score)),
                "hook_sentence": hook,
                "virality_reason": "High-density conversational peak with strong rhetorical cues.",
            })

        i = max(i + 1, j - 2)

    return dedupe_highlights(candidates)[:num_clips]


def detect_highlights(
    transcript: dict,
    num_clips: int = 4,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    audio_path: Optional[Path] = None,
    sound_events: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """Main highlight detection engine.

    Args:
        transcript: Dict with {"words": [...]} or {"segments": [...]} and "duration"
        num_clips: Number of top highlights to output
        progress_cb: Optional progress callback (0.0 to 1.0, message)

    Returns:
        Dict: {"highlights": [...], "content_info": {...}, "total_duration": float}
    """
    if progress_cb:
        progress_cb(0.1, "Grouping transcript into semantic sentences")

    raw_words = transcript.get("words", [])
    duration = float(transcript.get("duration", 0.0))
    if not duration and raw_words:
        duration = float(raw_words[-1].get("end", 0.0))

    sentences = group_words_into_sentences(raw_words)
    if not sentences:
        return {"highlights": [], "content_info": {}, "total_duration": duration}

    if progress_cb:
        progress_cb(0.25, "Analyzing content genre and conversational density")

    content_info = detect_content_type(sentences)

    if progress_cb:
        progress_cb(0.4, f"Extracting viral candidate shorts (virality framework)")

    min_clips = max(num_clips, 4)
    system_prompt = HIGHLIGHT_SYSTEM_PROMPT.format(
        virality_criteria=VIRALITY_CRITERIA,
        content_type=content_info.get("content_type", "monologue"),
        density=content_info.get("density", "medium"),
        min_clips=min_clips + 2,
    )

    detected: list[dict] = []

    # Check if video is very long (>30 min) -> chunking
    if duration >= LONG_VIDEO_THRESHOLD:
        start_t = 0.0
        chunk_idx = 0
        total_chunks = max(1, int(duration // (CHUNK_SIZE_SECONDS - CHUNK_OVERLAP_SECONDS)) + 1)

        while start_t < duration:
            end_t = min(start_t + CHUNK_SIZE_SECONDS, duration)
            chunk_sentences = [
                s for s in sentences
                if s.start >= start_t and s.end <= end_t + CHUNK_OVERLAP_SECONDS
            ]
            if chunk_sentences:
                chunk_text = build_transcript_text(chunk_sentences)
                prompt = f"{system_prompt}\n\nTranscript Chunk:\n{chunk_text}"
                try:
                    res = providers.complete_json(prompt, HIGHLIGHTS_SCHEMA)
                    if isinstance(res, dict) and "highlights" in res:
                        detected.extend(res["highlights"])
                except Exception as e:
                    pass
            chunk_idx += 1
            if progress_cb:
                progress_cb(
                    0.4 + 0.35 * (chunk_idx / total_chunks),
                    f"Processed chunk {chunk_idx}/{total_chunks}",
                )
            start_t += (CHUNK_SIZE_SECONDS - CHUNK_OVERLAP_SECONDS)
    else:
        full_text = build_transcript_text(sentences)
        prompt = f"{system_prompt}\n\nFull Video Transcript:\n{full_text}"
        try:
            res = providers.complete_json(prompt, HIGHLIGHTS_SCHEMA)
            if isinstance(res, dict) and "highlights" in res:
                detected.extend(res["highlights"])
        except Exception as e:
            # Fall back to rule-based candidates if AI provider is not reachable
            detected = rule_fallback_highlights(sentences, duration, num_clips=num_clips * 2, audio_path=audio_path, sound_events=sound_events)

    if not detected:
        detected = rule_fallback_highlights(sentences, duration, num_clips=num_clips * 2, audio_path=audio_path, sound_events=sound_events)

    if progress_cb:
        progress_cb(0.85, "Snapping cut boundaries to clean sentence endings")

    snapped = snap_to_sentence_boundaries(detected, sentences, duration)
    deduped = dedupe_highlights(snapped)

    if progress_cb:
        progress_cb(0.9, "Measuring the talk: centrality, how animated the speaker is, laughter")
    # the AI's judgement is fused with measured signals (see fuse_scores), then the most different moments are picked (MMR)
    windows = []
    for h in deduped:
        first = next((k for k, s in enumerate(sentences) if s.start >= float(h["start_time"]) - 0.01), 0)
        last = max(first, max((k for k, s in enumerate(sentences) if s.end <= float(h["end_time"]) + 0.01), default=first))
        windows.append((first, last + 1))
    if deduped:
        signals = measured_signals(sentences, windows, audio_path, sound_events)
        for h, score, idx in zip(deduped, fuse_scores([float(h.get("score", 0)) for h in deduped], signals), range(len(deduped))):
            h["ai_score"] = h.get("score", 0)
            h["score"] = score
            h["signals"] = {k: round(v[idx], 2) for k, v in signals.items()}
    final_highlights = pick_diverse(deduped, sentences, num_clips)

    if progress_cb:
        progress_cb(1.0, f"Found {len(final_highlights)} viral shorts candidates")

    return {
        "highlights": final_highlights,
        "content_info": content_info,
        "total_duration": duration,
    }
