# Cartoon 2 (story engine) — plan and checklist

Source: `story-engine.zip` (Remotion + Python planner, 540x960 SVG design space). Owner's words: incorporate it completely as a new style; keep the
existing cartoon (Cartoon 1) and take enhancements from the zip; characters must be acceptable to any viewer; after the timeline is generated every
component of every layer is editable.

## How it fits our vision
- **One renderer:** HyperFrames stays the only renderer. The engine's React/SVG code is kept nearly verbatim in `server/renderer/story/src/`
  (Remotion replaced by a 60-line shim `rt.ts`: interpolate, spring, Easing, frame context). esbuild bundles it into `server/renderer/runtime/vt-story.js`,
  which the composition loads; one GSAP tween per scene calls `draw(t)`, so seeking is frame exact (same pattern as the stick engine).
- **One document:** a Cartoon 2 scene is a normal `Scene` holding one `story` element (`vt/schema.py: Story`): `bg`, `items` (the engine's elements,
  flat props), `tag`, `speak`, `push`. Times inside a story are **absolute video seconds** (the engine's own contract), because they follow the spoken words
  and the voice never moves when a scene is retimed. Characters live once per video in `ScenesFile.story_cast` (edit a look -> every scene follows).
- **One Director:** `options.look = "story"` routes `Pipeline.stage_plan` to `vt/story/plan.py`: our words -> clause captions -> the engine's rule planner
  (always runs, the fallback) -> optional per-scene AI design with the engine's own `scene_designer.md` prompt through the chosen director's provider ->
  the engine's validator -> our ScenesFile. The director that actually answered is recorded (`directors.record`).
- **One editor:** the Studio shows a story scene with a live stage (the same engine source imported into the client), every item as a layer:
  select, drag, scale, rotate, timing, enter/exit/loop, keyframes at the playhead, every type-specific prop from a catalog (`vt/story/catalog.py`,
  `GET /api/story/catalog`), background, scene tag, cast looks, plus a raw-JSON fallback so nothing is out of reach.
- **Sound:** engine sfx names map to our library roles (tick->click, pop->pop, stamp->impact, whoosh->whoosh, printer->typing) as `scene.sfx` cues.
- **Captions:** ours (caption styles keep working); the engine's caption chrome is not used. Tag chip, vignette and grain are drawn by the runtime.
- **Formats:** 9:16 native; 16:9 / 1:1 widen the stage (backgrounds fill the full width, content stays centred).
- **Language:** digits and the currency sign follow the video language (Bangla digits only for Bangla).

## Checklist (status 2026-11-05 00:30)
1. [x] engine source + shim (`src/rt.ts`) + entry + `build.mjs` -> `runtime/vt-story.js` (194 KB, React bundled); catalog example checked in 9:16 and 16:9
2. [x] schema: `Story`, `StoryItem` (flat, extra=allow, checked against the catalog), `StoryCharacter`, `ScenesFile.story_cast`, `Options.look += "story"`,
       `Cartoon.extras` (Cartoon 1 overlay)
3. [x] composer: `scene.story`, `scene.story_overlay`, `story_cast`, `story_fonts`, runtime file copied, voice envelope drives mouths
4. [x] planner `vt/story/`: `engine_rules.py`/`engine_validate.py` (zip, unchanged), `plan.py` (words -> clause captions -> scenes), `designer.py`
       (per-scene AI with the zip's prompt + house rules), `service.py`; `Pipeline._plan_story` routes `look=story` through the chosen director
5. [x] API (`server/story_routes.py`: catalog, cast PUT, story-task, story POST) + MCP `get_story_task` / `submit_story`; `directors.client_story_prompt`
6. [x] Studio: New video "Cartoon 1" / "Cartoon 2" (card thumbnail drawn by the engine), `review/story/StoryEditor.tsx` (live stage with drag / wheel
       scale / Alt+wheel turn / arrows, layers, add/duplicate/delete/order, forms for every catalog property, movement points, who-talks-when,
       background, tag, cast, JSON), live preview of story edits (`Preview.tsx`)
7. [x] Cartoon 1: `vt/story/motifs.py` adds word-timed story items (numbers count up, money/bulb/cross icons, beating heart, clock, calendar days,
       thought cloud, impact lines, sparkles) over cartoon scenes; edited with the same editor ("Story-engine extras")
8. [x] every element of every style: a JSON tab per element and a whole-scene JSON view; `scene_ops.patch_scene` accepts every scene field except
       id/beats/start (which have split/merge/move)
9. [x] characters: nose, eye light, warm cheeks and a clearer smile, angry has its own brows/mouth; house rules in the designer prompt (dignity, no
       stereotypes, no violence)
10. [ ] end-to-end on the GPU server (first try failed in the ComfyUI Breeze voice node, owner's install: CPU/CUDA tensor mismatch; retry with Kokoro)

## Known gaps
- The stdio MCP tests and `tests/test_story_kit.py` assume a working directory (`server/`); they pass from there, fail from the repo root (not new).
- Browser-checked only on stills of the runtime; the StoryEditor has not been clicked through on a real project yet.
