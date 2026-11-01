"""Prompts and schemas for AI Virality & Shorts Highlight Detection.

Incorporate proven criteria from Anil-matcha/AI-Youtube-Shorts-Generator:
1. Hook moments (curiosity gap, high contrast, contrarian statements)
2. Emotional peaks (surprise, laughter, anger, excitement)
3. Opinion bombs (polarizing, strong takes)
4. Revelation moments (surprising facts, mindset shifts)
5. Conflict / tension (pushback, dilemma, confronting problems)
6. Quotable one-liners (punchy memorable takeaway)
7. Story peaks (climax or twist of an anecdote)
8. Practical value (actionable tip/hack)
"""

CONTENT_TYPE_PROMPT = """Analyze this video transcript sample and classify the content type.
Choose one: podcast, interview, tutorial, lecture, commentary, debate, vlog, monologue, other.
Also estimate content density: low (mostly filler/chit-chat), medium, or high (dense info/stories).
Respond with JSON only: {"content_type": "...", "density": "..."}"""

CONTENT_TYPE_SCHEMA = {
    "type": "object",
    "required": ["content_type", "density"],
    "properties": {
        "content_type": {"type": "string"},
        "density": {"type": "string"},
    },
}

VIRALITY_CRITERIA = """
Virality signals to prioritize (ranked by impact):
1. HOOK MOMENTS — statements that create immediate curiosity ("The secret is...", "Nobody talks about...", "I was completely wrong about...")
2. EMOTIONAL PEAKS — genuine surprise, laughter, vulnerability, excitement; raw unscripted reactions
3. OPINION BOMBS — strong, polarizing or counter-intuitive statements that trigger agree/disagree
4. REVELATION MOMENTS — surprising facts, stats, or confessions that reframe how the viewer thinks
5. CONFLICT/TENSION — disagreement, pushback, or a problem being confronted head-on
6. QUOTABLE ONE-LINERS — a sentence that works as a standalone quote card
7. STORY PEAKS — the climax or twist of an anecdote; the payoff moment
8. PRACTICAL VALUE — a concrete tip, hack, or insight the viewer can immediately apply
"""

HIGHLIGHT_SYSTEM_PROMPT = """You are an elite short-form video editor who has studied thousands of viral clips on TikTok, Instagram Reels, and YouTube Shorts. You know exactly what makes viewers stop scrolling, watch to the end, and share.

{virality_criteria}

Content type: {content_type} | Density: {density}

Your task: identify the top {min_clips} most viral-worthy highlights from the transcript.

Rules:
- Every highlight must open with a strong HOOK — a line that grabs attention within the first 3 seconds
- Duration sweet spot: 30-75 seconds. Go shorter (20-29s) only for a punchy standalone one-liner. Go longer (76-90s) only when a story arc needs full context to land
- Never cut mid-sentence or mid-thought — each clip must feel complete and self-contained
- Clips must not overlap significantly with each other
- Score 0-100 on viral potential (not general quality)
- For each highlight, identify the single best "hook_sentence" — the opening line that would make someone stop scrolling
- Explain in one sentence why this clip is viral ("virality_reason")
- Give each highlight a punchy, click-worthy "title" (3-7 words)

Respond ONLY with valid JSON matching this schema:
{{"highlights":[{{"title":"string","start_time":float,"end_time":float,"score":int,"hook_sentence":"string","virality_reason":"string"}}]}}
"""

HIGHLIGHTS_SCHEMA = {
    "type": "object",
    "required": ["highlights"],
    "properties": {
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "start_time", "end_time", "score", "hook_sentence", "virality_reason"],
                "properties": {
                    "title": {"type": "string"},
                    "start_time": {"type": "number"},
                    "end_time": {"type": "number"},
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "hook_sentence": {"type": "string"},
                    "virality_reason": {"type": "string"},
                },
            },
        }
    },
}
