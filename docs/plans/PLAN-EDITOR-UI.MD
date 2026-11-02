# Plan: the everyday editor (a CapCut-style Studio for ordinary people)

**2026-11-03 update:** The owner superseded the two-editor design below. There is now one editor at /p/:id; /pro redirects to it. All tracks stay editable. Current implementation and acceptance limits: [responsive editor plan](PLAN-RESPONSIVE-EDITOR.MD) and [current audit](../AUDIT-2026-11-03.md). The original sections below are historical design context, not instructions to restore a second editor.

Owner (2026-10-27): "The UI is not user friendly. It has a lot of options for the regular user. Even the timeline feels cluttering, as if there is a learning curve. You can clone CapCut's UI completely." Built the same day at `/p/:id`; the dense editor stays at `/p/:id/pro`. Evidence: [docs/research/ui-before-editor.png](../research/ui-before-editor.png), [ui-after-editor.png](../research/ui-after-editor.png), `studio/e2e/editor_simple.mjs` (19 passed).

## 1. Principles
1. **One screen, four regions, like CapCut:** a thin top bar, a tool rail with one panel at a time on the left, the preview in the middle, the few controls of the selection on the right, a small timeline at the bottom.
2. **A person never sees a menu bar.** The top bar has the title, the shape, one **Export** button, a **More** menu and **Details** (the director's log, Phase 3).
3. **Three tracks, not nine:** pictures (with thumbnails), captions, voice. Everything else (layers, sounds, every element) is in the full editor.
4. **Plain words, large targets, no jargon**; every control has a name for a screen reader; the phone layout stacks (tested at 390 px).
5. **The director's work is visible but quiet**: each scene can say *why* (Details), each decision can be redone (*Redo with AI*), each edit has one undo.

## 2. What is built
`studio/src/editor/EditorPage.tsx`, `SimpleTimeline.tsx`, `editor.css`: Story, Media, Text and AI tools; a scene's picture layout (seven choices) and how it comes in; word fixing and highlighted words; split at the playhead, delete with a question, join with the next, undo and redo, zoom, keyboard (Space, J, K, S, Delete, Ctrl+Z, Ctrl+Enter); More -> video options, find shorts, open the full editor.

## 3. What is next (each is a task with a gate)
| Id | Task | Gate |
|---|---|---|
| U1 | **Drag the edges of a picture** to change when it changes (snaps to a word start), one undo step | `studio/e2e/editor_simple.mjs` drags an edge and the scene boundary moves to a word |
| U2 | **Music and sound tracks** shown under the voice (the bundled music, the sound effects the mixer chose), with volume per track and a mute | a person lowers the music from the timeline |
| U3 | **Caption styles** in the Text tool (word, keyword, lines, type: [PLAN-REEL-DIRECTOR.MD](PLAN-REEL-DIRECTOR.MD) section 5) with a live preview | the four presets render and are chosen from the panel **PARTLY DONE 2026-10-28:** the Text tool has *Caption look* (automatic, short lines, one big word, key word, boxed) saved on the project; the live preview in the panel is not |
| U4 | **Change the voice of one sentence** and **its delivery** ([PLAN-VOICE-DIRECTION.MD](PLAN-VOICE-DIRECTION.MD) VD-2): a *Delivery* field, sound chips, *Say it again* | one sentence re-spoken and spliced, one undo |
| U5 | **Replace a picture**: *Draw again* (new seed), *Describe it differently* (edit the prompt), *Use my picture* (the media bin); a small gallery of the last three tries | a picture swapped without redoing the video **DONE 2026-10-28 for reels:** *Draw again*, *Describe it differently*, the last tries, *Use my picture* (`vt/server/reel_routes.py`, `studio/src/editor/PictureTools.tsx`, `tests/test_reel_routes.py`) |
| U6 | **The plan sheet before Start** and the live board ([modules plan](PLAN-DIRECTOR-MODULES.MD) section 8) | nothing expensive runs before Start |
| U7 | **Overlay track** (a person's own picture, text, sticker over the video) in the simple timeline, hidden until used | the layer tests pass on the new track |
| U8 | **Templates and looks**: a handful of whole-video looks (clean cartoon, line art, comic, photo, kinetic type) as large cards in the Story tool | choosing one redraws with it (needs the style bible, R2) |
| U9 | **Phone first**: the editor usable with thumbs (bottom sheets, 44 px targets) | `editor_simple.mjs` at 390 px completes an edit |
| U10 | **Bangla and English interface** for every string of the editor | all strings in `studio/src/i18n.ts` |
| U11 | **Port the older browser suites** to `/p/:id/pro` or to the new editor (P10-06) | the suites pass or are deleted with a reason |
| U12 | **Accessibility pass** with axe and keyboard-only use | axe clean, a full edit by keyboard |

## 4. Tests
[TEST-PLAN.md](../TEST-PLAN.md) layer L5; each task above adds to `editor_simple.mjs` or a new suite, and a screenshot is looked at before the task is called done.
