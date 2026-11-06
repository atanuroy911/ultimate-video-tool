# B7: prove it, for every style a director can write

Done on 2026-11-06 (plan decision 1).

`tests/test_director_authority.py` now covers every style a director can write, and fails if the old guard is restored:
- **Explainer, stick, emoji and cartoon** (the four kinds of Video Script): a script with one scene far more crowded than a screen holds (seven overlays, or six emoji and keywords) is compiled the way the app does and composed for each of the three AI planners (`llm`, `claude`, `assistant`). 24 checks: every element placed is in `data.json` (same count, same types, every scene marked `directed`, none cleared), and on the real page every element is shown at some moment, the guard changed nothing (`shrunk` and `dropped` never appear for an AI's plan, only `would-...`), and the same crowd planned by the rules has the same elements on the page.
- **Story (Cartoon 2):** the director is told, not silently served: B5 (`tests/test_story_repairs.py`).
- **Picture video (reel):** the director's own document, nothing overrides it, approving with checks open is written down: B6 (`tests/test_reel_authority.py`).
- Layout crowds of the four kinds the guard judges (cut off, optional elements cut off, letters too small, one on top of another), a prop the shot cuts, a scene over a person, the facts, the composer flag, the Quality-check report: B2 and B3 (89 checks in the file in all).

Mutation checks that restore the old behaviour, 4 of 4 caught by the style tests: the guard ignores the directed flag (the old guard); the composer never marks a scene directed; set decoration is not recognised; a director's named prop is hidden again.

A finding that came with it: in 9:16 almost every stick video loses a classroom's board, door and window to the frame, so reporting each cut prop was noise and keeping them half-drawn for an AI would have been worse than before. The composer now marks decoration that nothing names as scenery, and the page leaves it out for every plan (see B3).
