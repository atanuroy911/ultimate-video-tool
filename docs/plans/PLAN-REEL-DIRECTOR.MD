# Plan: the reel director (script or voice in, a video that holds attention out)

Status: the first end-to-end version runs ([evidence](../evidence/2026-10-27/reel-pipeline.md), [voiced by VoiceStudio](../evidence/2026-10-28/voicestudio-install.md)). This page is the complete design of what it should become, grounded in the owner's nine example reels ([research/REELS-ANALYSIS.md](../research/REELS-ANALYSIS.md)). Owner's rules that govern it: the **director decides from the content**, not from a cut count; audio is the master; nothing on screen is invented; something changes at least every 3 s (a moving picture counts); AI first with rule fallbacks; everything is a module the director can call; the person sees an editable plan before anything expensive runs.

## 1. What makes the example reels work (and so what the director must read)
Read from the transcripts and frames, not from view counts (none were available):
1. **A hook that opens a loop in the first sentence** (a surprising claim, a question people care about, a prohibition), about money, sex, fear, safety or status, with no greeting.
2. **A promise of hidden knowledge** ("the secret", "the wealthiest families understood this").
3. **A shape**: claim -> stakes -> mechanism in plain steps -> a turn ("but", "is it legal?") -> a one-line payoff -> the ask.
4. **Concrete things**: numbers and nouns that a picture can show.
5. **One look and one figure** for the whole video; **a second visual family** for facts (cards, diagrams) in a long story.
6. **Text as a second channel**: one huge word, the key word grown and coloured, or two to four words with one lit.
7. **Pace follows content and length**: about 2.3 s a picture in 60 s reels, about 5 s in a 12-minute story; steps get a held figure and a step counter; a story with days gets a title card at each jump.
8. **A last card that asks** ("FOLLOW FOR MORE", Subscribe), or a completion card ("DAY 08 COMPLETE").
9. **No dead start**: subject on screen and first word at 0.0 s. (Ours already do this.)

## 2. The pipeline, stage by stage (each stage is a module the director can call)
| # | Stage | What it does | Module (existing or new) | Artifact |
|---|---|---|---|---|
| 1 | Understand the request | goal, audience, length target, language, platform | `direct.set_direction` (exists) | `direction.json` |
| 2 | **Read the script** | kind (steps, story, explanation, argument, list, opinion), hook type and strength, per-sentence draw note and key word, turns, chapter jumps | `understand.read_script` (built as `server/vt/reel/reading.py`; to register) | `reel_reading.json` |
| 3 | **Improve the hook** (optional, shown to the person) | if the first line is weak (strength < 0.4), propose 2 rewrites that keep every fact; never applied silently | `direct.improve_hook` (new) | in the plan sheet |
| 4 | **Cast the voice** | choose or design a voice from the content and language (a calm woman for a health explainer, a brisk man for steps); the person's own consented voices first | `voice.pick` (new) using `server/vt/comfy/voicing.py` | `voice.json` |
| 5 | **Direct the delivery** | per-sentence direction and sound events for voices that can follow them | `voice_direction.suggest` (built) | notes in `script.json` |
| 6 | **Speak, sentence by sentence** | real lengths and word times first (audio-first) | `voice.speak_script` (new module over `tts.synthesize`) | `audio.master`, `script.json` |
| 7 | Clean and cut the audio | existing stages (silence, retakes, tighten) | existing modules | `cuts.json` |
| 8 | **Set one look** | style (cartoon, line art, comic, photo), the recurring figure, palette; a style bible stored as an artifact so every prompt inherits it | `direct.set_style` (new; presets in `server/vt/reel/style.py`) | `style.json` |
| 9 | **Make slots** | group sentences by kind and length; chapter jumps become cards; long videos hold pictures longer | `cut.reel_slots` (built as `server/vt/reel/slots.py`) | `slots.json` |
| 10 | **Fill slots** | the cheapest medium that carries the sentence: a drawn picture (Z-Image), a card (title, value, steps, day counter), a stock or the speaker's own picture, a still with a push-in; **a 3-4 s silent clip (LTX or Wan) only for the few hero moments the budget allows** | `fill.generated_still` (built as `server/vt/comfy/still.py`), `fill.card`, `fill.stock`, `gen.video_from_image` | `media/`, `scenes.json` |
| 11 | **Captions** | the preset the content wants: *word* (one huge centre word), *keyword* (key word grown and coloured), *lines* (2 to 4 words, one lit), *type* (kinetic typography) | `compose.captions` (presets to build, P4-11) | in `scenes.json` |
| 12 | **Hook treatment and end card** | first 2 s: biggest text, strongest picture, a sound hit; last 2 s: the ask or completion card | `compose.hook`, `fill.end_card` (new) | in `scenes.json` |
| 13 | Motion and sound | plain cuts on the word, a push-in on every still, music ducked under speech, sound effects on turns | existing compose and mux | `composition/` |
| 14 | **Judge** | every claim is in the speech; each picture change lands within 100 ms of a spoken word; nothing is still for more than 3 s; captions readable; first frame has content; loudness near -14 LUFS | `judge.facts`, `judge.impact_alignment`, `judge.retention`, `judge.loudness` | `judgement.json` |
| 15 | **Show the plan, then run** | the plan sheet lists the moments, the medium chosen for each with why, the estimate of GPU time, and what is locked; **Start** runs it | plan review (Phase 6) | `plan.json` |

## 3. Rules the director applies (content decides)
| Kind | Pictures per sentence group | Longest a picture may stay | Default style | Cards | Captions |
|---|---|---|---|---|---|
| steps | about 9 words | 4.5 s | cartoon or kinetic type | "STEP N" card at each step | keyword |
| story | about 7 words (11 over 3 min) | 3.2 s (5.1 s over 3 min) | comic or cartoon, one hero | day or place card at each jump; blueprint-style fact cards | lines |
| explanation (science, health) | about 8 words | 3.8 s | line art, one idea per picture, a slow push-in | none | lines with one lit word |
| argument | about 9 words | 4.2 s | kinetic type with props | term cards | type |
| list | about 7 words | 3.4 s | cartoon | numbered cards | keyword |
| opinion | about 8 words | 3.8 s | photo or cartoon | none | lines |
These numbers are today's defaults in `server/vt/reel/slots.py::PACE`; they are *starting points the reading may override* (a very tense passage tightens, a reflective one loosens) and they are measured against the reels in the test plan, never presented as laws.

## 4. A consistent figure (the biggest visual gap)
Today the figure is a text description repeated in every prompt, so its face and size drift. Plan, cheapest first:
1. **A reference picture**: draw the hero once (a chosen picture the person approves), then condition every later picture on it with ComfyUI's reference-image nodes (the installed Z-Image pack has `TextEncodeZImageOmni` with image inputs; Qwen-Image-Edit style editing is the alternative). Workflow `zimage_t2i_ref.json`, kind `image`, with the reference as an input.
2. **A fixed seed per scene type** and a fixed composition cue ("medium shot", "close-up") from the reading, so shots vary on purpose, not by accident.
3. **A character sheet check**: after drawing, a vision model (Ollama `qwen2.5vl`) compares each picture's figure against the reference and flags drifts; a flagged picture is redrawn once.

## 5. Captions, hook and end card (specifications)
* **Presets** in `server/renderer/runtime/vt-media.js` / `vt.js` and `server/vt/compose/composer.py`: `word` (one word, 120 px, yellow with a black outline, centred, bounces in on its word start), `keyword` (the sentence small, the lit word 1.6 times bigger and coloured), `lines` (today's pill), `type` (whole lines of type, the key word red). Chosen by the reading; changeable in the editor's Text panel.
* **Hook treatment**: if the hook strength is 0.4 or more the first picture is the strongest of the video (drawn first, redrawn on a weak frame check); the first word is captioned in the biggest preset; a short sound hit at 0.0 s.
* **End card**: the last 2 s show the ask (`follow for more`, Subscribe, a completion card). The text comes from the project's options (default none: nothing is added without being asked) and the spoken line stays the author's.

## 6. Long form (the 12-minute story)
* Chapters from the reading's jumps; **an establishing wide picture at each chapter start**, then closer pictures; pictures held 1.6 times longer than in a short.
* **Fact cards** in a second visual family (blueprint blue) for counts, supplies and rules; the reading marks a sentence as a *fact list* when it lists three or more quantities.
* **Memory**: the plan is made chapter by chapter (the AI sees the previous chapter's summary), with the figure and palette fixed once; drawing is resumable (cached by prompt) so a power cut never loses the pictures already made.
* **Time budget**: the estimate in the plan sheet is shown before Start; a 12-minute story is about 90 pictures, about 25 minutes of GPU on the V100.

## 7. Tasks
| Id | Task | Files | Gate |
|---|---|---|---|
| R1 | Register the reel stages as modules (`understand.read_script`, `cut.reel_slots`, `fill.generated_still`, `direct.set_style`) | `server/vt/modules/defs/reel.py` | lint clean; each callable over MCP and CLI **DONE 2026-10-28:** `understand.read_script`, `cut.reel_slots`, `direct.set_style`, `fill.generated_still` in `server/vt/modules/defs/reel.py` (`tests/test_reel.py`) |
| R2 | Style bible artifact and editor control | `server/vt/reel/style.py`, `client/studio/src/editor/*` | the person can change the look and redraw |
| R3 | Caption presets (word, keyword, lines, type) | `server/renderer/runtime/*`, `server/vt/compose/composer.py` | four renders looked at **PARTLY DONE 2026-10-28:** `word`, `keyword` and `pop` are built and chosen by the kind of script (`server/vt/compose/composer.py::reel_caption_preset`); `type` (kinetic) is not; picked in the editor's Text tool |
| R4 | Hook treatment and end card | `server/vt/reel/plan.py`, `server/renderer/runtime/*` | first frame and last frame checked in the judge **PARTLY DONE 2026-10-28:** the end card (option `end_card`, nothing added unless asked) is built; the hook treatment (strongest first picture, a sound hit) is not |
| R5 | Fact cards and step/day counter cards in the reel fill | `server/vt/director/archetypes.py`, `server/vt/reel/plan.py` | a story with supplies makes a card |
| R6 | Reference-image figure (section 4) | `server/assets/comfy/workflows/zimage_t2i_ref.json`, `server/vt/comfy/still.py` | the drift check passes on a 20-picture video **RESEARCHED, NOT BUILT 2026-10-28:** the ComfyUI here has `TextEncodeZImageOmni`, but it needs the Z-Image Omni model, which is not installed and whose ComfyUI file and workflow could not be confirmed by search (sources in [BEST-MODELS.md](../research/BEST-MODELS.md)); alternatives are a trained character LoRA or Flux Kontext / Qwen image edit |
| R7 | Budgeted clips: pick up to N hero moments for a 3-4 s clip | `server/vt/reel/plan.py`, `server/vt/comfy/generate.py` | a reel with 3 clips, each on a chosen sentence |
| R8 | Hook improvement proposals shown in the plan sheet | `server/vt/reel/hook.py` | two rewrites keep every fact (checked by `judge.facts`) **DONE 2026-10-28:** `server/vt/reel/hook.py`, module `direct.improve_hook`, `GET/POST /api/projects/{id}/hook`, the editor's AI tool shows the proposals (`tests/test_hook.py`) |
| R9 | Voice cast from the reading | `server/vt/comfy/voicing.py`, `server/vt/reel/reading.py` | a reel gets a voice chosen from its content **DONE 2026-10-28 for ComfyUI voices:** voice `design:auto` is cast from the kind of script (`server/vt/comfy/voicing.py::cast`) |
| R10 | Long-form chaptering and resumable drawing | `server/vt/reel/plan.py` | a 5-minute script survives a killed server |
| R11 | Bangla end to end (voice, captions, picture prompts translated) | `server/vt/reel/reading.py`, `server/vt/tts.py` | one Bangla reel judged by a Bangla speaker |
| R12 | The plan sheet and live board | Phase 6 | nothing runs before Start |
| R13 | The judge modules wired in | `server/vt/modules/defs/judge.py` | a video that fails a rule says which **DONE 2026-10-28:** `judge.video` module, run after every autopilot render, the Result page card ([evidence](../evidence/2026-10-28/acceptance.md)) |
| R14 | Measure against the nine reels: words per picture, swaps a minute, longest still, first change, loudness | `scripts/analyze_reels.py`, `scripts/eval_direction.py` | our numbers beside theirs in the evidence, within the ranges set in the test plan **PARTLY DONE 2026-10-28:** the judges measure our videos the way `scripts/analyze_reels.py` measures theirs; the side-by-side table is not written yet |
