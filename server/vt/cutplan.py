"""Audio-first impact combination and editable visual cut slots."""
from __future__ import annotations

from typing import Any


def combine(words: list[dict], emphasis: dict, prosody: Any, events: Any, saliency: Any) -> list[dict]:
    """Combine existing audio evidence at word onsets without adding semantic claims."""
    points: dict[float, dict] = {}
    emph = emphasis.get("scores", emphasis) if isinstance(emphasis, dict) else {}
    for word in words:
        strength = float(emph.get(word.get("id"), 0.0)) if isinstance(emph, dict) else 0.0
        if strength > 0:
            t = round(float(word["start"]), 3)
            points[t] = {"time": t, "word_id": word.get("id"), "kind": "stress", "strength": min(1.0, strength), "why": "spoken stress"}
    sources = ((prosody, "prosody"), (events, "sound"), (saliency, "saliency"))
    for source, kind in sources:
        rows = source.get("points", source.get("events", source.get("scores", []))) if isinstance(source, dict) else source or []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            time = row.get("time", row.get("start"))
            if time is None:
                continue
            strength = float(row.get("strength", row.get("score", 0.5)))
            t = round(float(time), 3)
            old = points.get(t)
            if old is None or strength > old["strength"]:
                points[t] = {"time": t, "word_id": row.get("word_id"), "kind": kind,
                             "strength": min(1.0, max(0.0, strength)), "why": row.get("label") or kind}
    return sorted(points.values(), key=lambda point: point["time"])


def propose(impacts: list[dict], duration: float, max_hold: float = 3.0, min_slot: float = 0.5) -> list[dict]:
    """Choose strong impact points while guaranteeing a visible change at least every max_hold seconds."""
    candidates = sorted(impacts, key=lambda row: row["time"])
    cuts, cursor, index = [0.0], 0.0, 1
    while cursor + max_hold < duration:
        limit = min(duration, cursor + max_hold)
        viable = [row for row in candidates if cursor + min_slot <= row["time"] <= limit]
        chosen = max(viable, key=lambda row: row.get("strength", 0.0))["time"] if viable else limit
        if chosen <= cursor:
            chosen = min(duration, cursor + max_hold)
        cuts.append(round(chosen, 3)); cursor = chosen
    cuts.append(round(duration, 3))
    slots = []
    for start, end in zip(cuts, cuts[1:]):
        impact = min(candidates, key=lambda row: abs(row["time"] - start)) if candidates else {"time": start, "kind": "pace", "strength": 0.0, "why": "heartbeat"}
        slots.append({"id": f"sl{index}", "start": start, "end": end, "impact": impact})
        index += 1
    return slots


def validate(slots: list[dict], duration: float, max_hold: float = 3.0, min_slot: float = 0.1) -> list[str]:
    errors, cursor = [], 0.0
    for index, slot in enumerate(slots):
        start, end = float(slot.get("start", -1)), float(slot.get("end", -1))
        if abs(start - cursor) > 0.02:
            errors.append(f"slot {index + 1} does not start at the previous boundary")
        if end - start < min_slot:
            errors.append(f"slot {index + 1} is too short")
        if end - start > max_hold + 0.02:
            errors.append(f"slot {index + 1} holds longer than {max_hold:g} seconds")
        impact = float((slot.get("impact") or {}).get("time", start))
        if not start - 0.001 <= impact <= end + 0.001:
            errors.append(f"slot {index + 1} impact lies outside the slot")
        cursor = end
    if abs(cursor - duration) > 0.05:
        errors.append("slots do not cover the complete audio")
    return errors


def snap_quiet(time: float, quiet: list[tuple[float, float]], tolerance: float = 0.25) -> float:
    candidates = [edge for span in quiet for edge in span if abs(edge - time) <= tolerance]
    return round(min(candidates, key=lambda edge: abs(edge - time)), 3) if candidates else round(time, 3)
