---
name: video-tool
description: Plan, edit and render faceless explainer videos with the local Video Tool app (Bangla / Banglish voice recordings). Use when the user mentions pending video requests, scene plans, transcripts, themes, or rendering a video from a recording.
---

# Video Tool

A local app turns a voice recording into a motion-graphics video. It cuts silences, transcribes (GPU, Bangla fine-tune),
splits the speech into sentences ("beats"), and shows elements (cards, arrows, coins, comparisons...) on screen in a design
theme. **You are the planner**: you decide which elements appear when. You never draw anything; you pick from a catalogue.

## Tools (MCP server `video-tool`)
- Planning: `list_pending_requests` -> `get_planning_task` -> `submit_scenes` (repeat until `ok`).
- Projects: `list_projects`, `create_project`, `run_pipeline`, `project_status`, `job_status`.
- Editing: `get_transcript`, `fix_word`, `add_glossary_term`, `get_scenes`, `update_scene`, `request_regenerate`.
- Design: `list_components`, `list_themes`, `get_theme`, `update_theme` (built-in themes need `save_as`).
- Output: `get_preview_frame` (a PNG so you can look at the result), `render`.

## Planning rules that matter
- Cover every beat exactly once, in order. Scenes are 1-3 beats (about 3-8 seconds). Never leave 6+ seconds without a new element.
- `at_word` must be a word id inside the scene; the element appears when that word is spoken. Anchor on the word that names the thing.
- Max 5 elements per scene (1-4 is ideal). Respect each field's length limit; shorten rather than overflow.
- Use the speaker's own words and numbers. Never translate. Keep the speaker's script: Bangla digits and the taka sign (৳১০০, ৪%)
  for Bangla speech; English terms stay in Latin letters unless the project's `script_policy` is `bangla`.
- Choose visuals that carry information: money -> `value_card`/`big_number`; A vs B -> `compare`; repeated units -> `icon_row`;
  cause -> effect -> `arrow`; rule or formula -> `tag`/`equation`; steps -> `list`; one idea -> `icon`.
- Do not repeat the caption text inside an element. Vary the main component and the transition between scenes.
- `caption.highlight_words`: one or two key word ids per scene.

## Checking your work
After a full plan, call `get_preview_frame` at a few times. Look for text that is cut off, elements that overlap the caption area, and
scenes that look empty. Fix with `update_scene`.

## Word ids, scene ids, beat ids
`w17` word, `s3` scene, `b5` beat. Word ids are stable when the user fixes spellings or the audio is re-cut.
