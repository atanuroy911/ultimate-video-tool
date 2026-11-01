> **HARD RULE (owner, 2026-10-23): something must happen on screen at least every 3 seconds, in every shape, or retention drops.** Enforced: heartbeat aims at 2.5 s tall / 2.6 s wide, the retention scorecard flags any gap over 3.0 s in every shape (it was 4 s for wide), tests assert the limit.

# Video Tool — End-to-End Plan

Turn a voice recording **or a typed script** (Bangla, English or Banglish) into a faceless motion-graphics explainer video. No timeline editor: it is automatic by default (look, pictures, sound), and everything can be reviewed and changed before rendering.

Reference look: title "ইয়েল্ড" in orange, tilted value card "৳১০০" with a label, arrow, a row of three coins with a label, a yellow highlighter tag "৪ = গ্রস", and a bottom caption box with one highlighted word ("থাকবে").

Last checked: 2026-10-22. Status: v1, Phase 2 and Phase 3 implemented, and (second round, same day) every step of H.9 below: see **H.10** for what was built, how it is tested, and what is still not done.
Next work, in this order (updated 2026-10-23 night): **Phase 15** (the app prompts Claude directly through the logged-in Claude Code CLI, no key) and **Phase 16** (one full-screen loading layer for every long operation), then **Phase 13** (a real creative director: cast, places, props, motion and a talk-to-the-director chat; stick mode was two figures talking) and **Phase 14** (a crazy-simple New project screen), then finish the Phase 7 gates, then the earlier order: **P9.2** (retention scorecard, measurement only), **Phase 10** (one shared context reading of the video), **P9.3 step 2** (no empty frames), then **Phase 7** (one Python environment and one installable product, see P7; cloning moves to Chatterbox Turbo ONNX). Then **Phase 8** (brand logos, flags and other named things, see P8), **Phase 12** (take in the open-source video-shotcraft library: 90+ motion recipes, sound effects and music, beat sync, QA rules, JianYing export; see P12; its Wave A and the arc profiles finish the rest of Phase 9), and last **Phase 11** (clean board, one launch script, one app per platform with Tauri, a very simple UI, test everything). Then **Phase 6** (multi-track editor, Concat features, sound-aware visuals, contrast, transcript panel; no Rust rewrite, see P6.1), with **P5.1** (timeline dragging) first, then **Phase 5** (A-roll, B-roll, motion graphics). Start with **HANDOVER** below (direction, UI redesign, status, testing, edge cases). Phase 4 (stick figures and the AI Video Script contract) is built except the StykAnimate/Pivot interop; see H.10.

---

## HANDOVER (2026-10-22): read this first

This section is written so another agent can take over without the chat history. It covers: the direction (AI-first), the UI redesign
(Final Cut Pro / Figma-like), what works and what does not today, how to run and test everything, and the edge cases that have bitten us.
Phase 4 (stick figures + Video Script contract) below is still valid and is the data foundation for this section.

### H.1 Direction: AI first, rules as the safety net

Decision by the owner (2026-10-22): the rule engine is not powerful enough to be the main designer. **Whenever an AI can do a step better,
the AI does it**; rules stay as (a) the offline fallback, (b) the validator/repairer of AI output, (c) the cheap first draft the AI improves.

Models available or planned (all optional, all local first):
| Model class | Where | Used for |
|---|---|---|
| Text LLM via Ollama (owner's server `http://192.168.123.47:11434`, model `gemma4:latest` today; any Ollama URL in Settings) | `vt/llm.py`, `vt/planner/llm_plan.py` | Picture choice today; next: the full Video Script (P4.1/P4.2) |
| Small **VLM** via Ollama (e.g. Gemma 3/4 vision, Qwen2.5-VL 3B/7B, MiniCPM-V, Moondream 2) | new `vt/ai/vision.py` | See H.2 |
| Claude via MCP (no key, the user's Claude Code) | `vt/mcp/server.py` | Best quality planning; same contract |
| Claude API / OpenAI-compatible (optional key) | planned `vt/ai/providers.py` | Same contract when Claude Code is not installed |
| Speech: faster-whisper large-v3 (English), bengaliAI whisper-medium (Bangla) | `vt/stages/asr.py` | Transcription |
| e5-small embeddings | `vt/visuals/embed.py` | Meaning search over the icon library |

### H.2 AI tasks to add, in priority order (each with its fallback)

1. **Video Script by LLM** (P4.1/P4.2): the whole plan (scene types, elements, stick actions, overlays) from one prompt + JSON schema.
   Fallback: current director. Acceptance: scores on `tests/script_eval/` beat the rule plan on at least 4 of 6 metrics.
2. **Visual QA by VLM** ("look at your own video"): after compose, render 1 frame per scene (`vt snapshot`), ask the VLM per frame:
   is anything cut off, overlapping, unreadable, empty, or unrelated to the sentence (given)? Return JSON `{ok, problems[], fix_hint}`.
   Failed scenes are re-planned (LLM gets the problems) or fall back to a simpler scene type. Fallback: the existing pixel checks
   (`tests/test_evaluation.py` logic moved into the pipeline: empty-screen and clipping detection).
3. **Picture judge by VLM**: render the 3 best icon/sticker candidates for a word and let the VLM choose the one that matches the sentence
   (fixes "point" -> pointing hand, "cleaner" -> plunger). Fallback: lexicon + embeddings (today).
4. **User media understanding by VLM**: caption/tag every photo, GIF and clip in the media bin (what is in it, where the subject is,
   is there text, faces), so matching to sentences uses meaning instead of file names/captions. Fallback: filename + user caption (today).
5. **Thumbnail / cover**: VLM picks the best frame and the LLM writes a 3-6 word hook title; exported as `cover.jpg` for social uploads.
6. **Title, description, hashtags** for YouTube/TikTok/Reels from the transcript (LLM), shown on the Export screen, copy buttons.
7. **Transcript polish by LLM** (Bangla/Banglish especially): fix recognition errors using context, never changing timings; every change is
   shown as a suggestion the user accepts. Fallback: glossary + manual edit (today).
8. **Image generation (later)**: SD-Turbo was evaluated and rejected (abstract ideas poor, noisy backgrounds). Re-evaluate SDXL-Turbo /
   FLUX-schnell on a bigger GPU; must produce clean cut-outs; drawn clipart (`vt/art/`) stays the default.

Engineering rules for every AI step:
* One interface: `vt/ai/` with `complete_json(prompt, schema, images=None) -> dict` and provider selection (Ollama, MCP, API).
* Always JSON-schema constrained, validated with Pydantic, auto-repaired, one retry with the error list, then fallback. Never crash the pipeline.
* Timeouts, cancel support, progress messages ("Checking scene 4 of 12"), and a cache keyed by (model, prompt hash, inputs hash).
* Record what made each decision (`provenance` per scene: rules / llm:<model> / claude / user) and show it in the UI.
* The AI's output is untrusted data: never executed, never used as a path or URL without validation.

### H.2b Any AI assistant as the designer, through MCP (Claude, ChatGPT and others)

The owner's direction: the user's own AI assistant (paid subscription, no API key in our app) should be able to do the heavy design work.
MCP is the shared door. Today `vt-mcp` speaks **stdio** and works with Claude Code (registered in `.mcp.json`). Plan:

| Client | Transport it needs | Plan |
|---|---|---|
| Claude Code (CLI, VS Code) | stdio (done) | keep; add the new tools below |
| Claude Desktop | stdio via `claude_desktop_config.json` | one-click "Connect Claude Desktop" button in Settings that writes the config entry |
| ChatGPT (connectors / developer mode) | **remote** MCP over HTTPS (streamable HTTP or SSE), with OAuth or a token | add an HTTP transport (`vt-mcp --http --port 8766`), a per-install secret token, and an optional tunnel (cloudflared / ngrok, user's choice) so ChatGPT in the cloud can reach the local app; show the URL + token in Settings with a warning that it exposes the local tools |
| Gemini CLI, Cursor, VS Code Copilot agent mode, Windsurf, LM Studio, Open WebUI | stdio or HTTP | document config snippets in Settings > AI assistants (copy buttons) |

Tool design so that any assistant (not just Claude) does good work:
* **Task tools return everything needed in one call**: `get_script_task(project)` returns the big prompt (P4.2) as `instructions`, the
  transcript with word ids, the catalogue, the JSON schema and 3 examples, so assistants without our context still produce valid output.
* `submit_script(project, script)` validates + repairs and answers with precise errors; `preview_frames(project, scenes=[...])` returns PNGs
  so a vision-capable assistant can check its own work (ChatGPT and Claude both accept images in tool results); `render(project, preset)`.
* Small, single-purpose tools with JSON-schema parameters and short descriptions (ChatGPT's tool picker and smaller models handle that best);
  no tool needs file paths from the assistant (uploads go through the app), which also keeps remote use safe.
* **Prompts and resources** (MCP `prompts/` and `resources/`): ship "Plan this video", "Make it a stick-figure video", "Improve scene N" as MCP
  prompts so the assistant shows them as one-click actions; expose the catalogue and schema as resources.
* **Safety for remote clients**: token required, read/write scoped to projects (no arbitrary file access, no shell), rate limits, every
  change recorded with provenance (`assistant: chatgpt|claude|...`) and undoable from the Studio; the user can revoke the token.
* **In-app status**: the Studio shows which assistant is connected, the pending task queue ("waiting for your assistant"), and lets the
  user copy a ready-made message for chat-only assistants (paste transcript + instructions, paste the JSON back) as a no-MCP fallback.
* Tests: the existing stdio MCP test pattern (`tests/test_mcp_stdio.py`) for every tool; an HTTP-transport test with the token (accept/deny);
  a conformance run with the official MCP Inspector; a manual end-to-end with ChatGPT developer mode and Claude Desktop, recorded in this plan.
* Order: after H.2 step 1 (the Video Script contract), because these tools hand out and accept that contract.

### H.3 UI redesign: a pro editor (Final Cut Pro / Figma style)

Problem today: the Studio grew page by page; Review has a two-row toolbar, many always-visible options, settings scattered across New,
Export, Settings, Design Studio. Goal: **one calm editing window**, options appear only where and when they are needed.

Design principles
* **Canvas first**: the video preview is the largest thing on screen; everything else is a quiet panel around it.
* **Progressive disclosure**: defaults are automatic; advanced controls live in the Inspector or behind a disclosure, never in toolbars.
* **One selection model** (like Figma): select a scene, an element, a word or a caption -> the Inspector shows only that thing's properties.
* **Direct manipulation**: drag elements on the canvas, drag scene edges on the timeline, drag an action chip to another word.
* **Keyboard-first** (like Final Cut): J/K/L shuttle, Space play, arrows nudge, Cmd/Ctrl+K command palette for every action.
* macOS-like visual language: SF/Inter, 13 px UI text, translucent sidebars (`backdrop-filter`), 8 px grid, hairline separators,
  segmented controls, no heavy borders, one accent colour, full light/dark parity, reduced motion respected.

Target layout (desktop >= 1280 px)
```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ● ● ●  Project name ▾          [ ▷ ]  00:12 / 01:40        Share/Export ▸   (AI ✦)   │  title bar (40 px)
├──────────────┬───────────────────────────────────────────────────┬───────────────────┤
│ Browser      │                                                   │ Inspector         │
│ ▸ Scenes     │                  CANVAS (preview)                 │ (context: scene / │
│ ▸ Media      │         safe-area + grid overlays on demand       │  element / word / │
│ ▸ Library    │                                                   │  caption / video) │
│   (icons,    │                                                   │                   │
│   clipart,   │                                                   │ tabs: Design ·    │
│   figures)   │                                                   │ Motion · Content  │
├──────────────┴───────────────────────────────────────────────────┴───────────────────┤
│ TIMELINE: ruler · scene track (thumbnails) · element track · word/caption track ·    │
│           audio waveform (voice / music / sfx) · playhead · zoom                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```
* **Title bar**: project switcher, play, timecode, aspect switch (9:16 · 1:1 · 16:9) as one small segmented control, Export, AI button.
* **Browser (left, collapsible)**: Scenes list, Media bin, Library (icons, drawn clipart, stick figures, sounds), searchable, drag to canvas/timeline.
* **Canvas**: WYSIWYG HyperFrames preview; click selects the element under the cursor; handles for position/scale; safe areas, grid and
  contrast warnings as toggleable overlays (View menu), not buttons.
* **Inspector (right)**: only the selection's properties. Scene: type ("Show as" gallery with live thumbnails), layout, transition, backdrop.
  Element: content fields with length counters, style, timing (anchor word). Word: spelling, cut, highlight. Nothing selected: video settings
  (look/theme, pace, music, captions style).
* **Timeline (bottom)**: tracks as in Final Cut; scenes are clips with thumbnails; words are tiny chips under the waveform; drag to retime
  (snaps to words); split/merge scenes; zoom with Ctrl+wheel; magnetic behaviour (no gaps).
* **AI panel (✦, slide-over)**: "Make it better", "Redo this scene", "Explain this choice", provider + model status, history of AI changes with
  per-change undo. Shows provenance.
* **Command palette (Ctrl+K)** and a **menu bar** (File, Edit, View, Scene, AI, Window, Help) on desktop (Electron native menu).
* **Home** becomes a simple grid of projects + a large "New video" card; **New video** becomes a 3-step sheet (Source -> Kind & look -> Create),
  with advanced options (speech model, fillers, speakers, subtitles mode) under one "Advanced" disclosure.
* **Export** becomes a sheet with presets: "TikTok / Reels / Shorts (9:16)", "YouTube (16:9)", "Square", "Custom"; shows loudness, size,
  the cover image and the AI-written title/description/hashtags.
* **Settings** becomes a macOS-style preferences window with sidebar sections (General, AI models, Speech, Stock & keys, Claude, Advanced).
* Responsive: below 1100 px the Browser collapses to icons; below 800 px Inspector becomes a bottom sheet; phone width shows canvas +
  bottom sheet only (review/approve flow, no full editing).

Implementation notes for the UI agent
* Stack stays React + Vite in `studio/`. Introduce a small design-system layer (`studio/src/ds/`: Button, Segmented, Field, Panel, Sheet,
  Popover, Menu, Toolbar, Slider, Tabs, Tooltip, Kbd) with tokens in CSS variables; migrate screen by screen.
* State: one store per project (`selection`, `playhead`, `zoom`, `panels`) next to the existing `store.ts`; undo/redo already exists
  server side (scene edits) and must stay the source of truth.
* Keep every existing API endpoint; the redesign is front-end only for the first milestone.
* Keep the existing e2e suites passing by updating selectors (prefer `getByRole` + accessible names, already used).
* Accessibility: every control has a name, focus rings visible, all actions reachable by keyboard, contrast AA in both themes.
* Milestones: (U1) design system + shell (title bar, panels, resizable splitters) -> (U2) canvas selection + inspector -> (U3) timeline with
  drag/retime -> (U4) command palette + menus + shortcuts sheet -> (U5) New/Export sheets + Settings window -> (U6) AI panel.
* Acceptance per milestone: screenshots of every screen light/dark at 1440/1100/800/390 px (`node studio/e2e/shots.mjs`), no horizontal
  scroll, Lighthouse a11y >= 95, e2e green, and a short screen recording reviewed by the owner.

### H.4 Status: what works today (verified 2026-10-22)

End to end, verified on real material (NASA YouTube videos, LibriVox audio-book, a Bangla YouTube clip, typed scripts, recordings):
* Inputs: browser recording, upload (wav/mp3/m4a/webm/ogg/opus/flac/aac/mp4/mov/mkv), typed script -> TTS (edge-tts online; MMS offline),
  `Name: text` dialogue scripts, **links** (YouTube or direct audio/video via yt-dlp; public addresses only; 40 min limit).
* Speech: Bangla, English, Banglish; silence cutting; filler removal; word timing with snapping; speaker detection for two clearly
  different voices (model-free, conservative); subtitles as transcript (author's subtitles; auto captions only for non-English by default).
* Planning: rules director with 5 profiles (general, product, story, discussion, education) and auto detection; 39 elements incl. charts,
  steps, timeline, definition, checklist, pros/cons, 9 diagrams, cartoons with lip sync, device mockups, media backdrops; local LLM picture
  chooser (Ollama); Claude via MCP (full planning tasks, submit with validation); key-term selection (WordNet noun shares + frequency +
  repetition); phrase tidying that rejects fragments; 31 drawn clipart concepts; contrast-aware text over photos/video; face-aware layout.
* Look: Design Studio (10 looks x 18 palettes x 11 backgrounds), auto theme per video, 9:16 / 1:1 / 16:9.
* Output: HyperFrames render -> MP4 H.264 High, level 4.2, yuv420p, faststart, AAC 48 kHz, **-14 LUFS / -1.5 dBTP**, SRT, credits file,
  first frame shows content, 9:16 safe areas (captions 420 px from bottom), GPU (NVENC) or CPU.
* Apps: Studio web UI (FastAPI + React), CLI `vt`, MCP server `vt-mcp`, Windows installer (Electron, unsigned), PWA.
* Tests: ~470 pytest (incl. slow render goldens, real-network ingest tests), 7 Playwright e2e suites, screenshot sweep.

### H.5 Status: what does not work or is weak (be honest with the owner)

* **Design quality is rule-limited**: pictures for abstract words are often generic emoji; scene choice is reasonable but not "designed";
  pros/cons semantics (✓/✗) are sometimes wrong for a mere contrast. -> H.2 items 1-3.
* **Stick figures** and the **AI Video Script contract**: built (H.10). Quality of stick motion was judged by contact sheets, not by an animator: expect to tune verbs by watching real renders.
* **VLM**: used for frame checks, picture judging, media captions and cover choice (H.10), tested with a fake model; quality on real material not measured.
* **Bangla**: no POS data for key-term choice (frequency + repetition only); definition/question detection for Bangla is pattern based and misses
  many forms ("তাকে বলে বাষ্পীভবন"); the Bangla UI strings are machine drafted.
* **Recognition quality on real noisy recordings is unmeasured** (benchmarks used synthetic speech). Short words at chunk starts were being
  dropped (fixed) — similar timing edge cases may remain.
* **Speaker detection** only for two clearly different voices; no diarisation model.
* **Language of a link** must be chosen by the user (not detected from the video).
* **Image generation** rejected for now (H.2-8). Maps, Lottie, external art packs: not built.
* **Installer**: Windows only verified, unsigned; macOS/Linux builds from CI never run by hand.
* **Flaky**: e2e `flows` check "Space plays and the preview follows the audio clock" fails occasionally right after a server restart (passes on
  re-run); not root-caused.
* **UI**: redesigned as an editor window (H.10); narrow-width layouts (below 800 px) stack the panels and hide the timeline below 600 px, which is usable but not polished.
* **Licence**: the repository has no licence file; decide before using GPL code (StykAnimate) or publishing.
* Music/SFX are synthesised loops, never auditioned; stock media need the user's own Pexels/Pixabay keys.

### H.6 How to run

```
.venv\Scripts\vt.exe studio --no-open            # Studio on http://127.0.0.1:8765 (rebuild UI: cd studio && npm.cmd run build)
.venv\Scripts\vt.exe link <url> --lang en         # or: vt new "Title" --audio file.wav  /  vt script "Title" -t "..."
.venv\Scripts\vt.exe run <project>                # cut -> transcribe -> words -> plan -> compose
.venv\Scripts\vt.exe render <project> --quality draft|looks|delivery [--aspect both]
.venv\Scripts\vt.exe snapshot <project> --at 0,3,9 # frames + contact sheet in projects/<id>/snapshots
cd desktop && set CSC_IDENTITY_AUTO_DISCOVERY=false && npm.cmd run dist   # installer (unset ELECTRON_RUN_AS_NODE first)
```
Windows notes: use `npm.cmd`; Python 3.11 venv in `.venv`; Node 22; ffmpeg on PATH; GPU RTX 4050 6 GB. In Git Bash, write patch scripts with a
file (heredocs mangle `\n` and backslashes). The Electron host sets `ELECTRON_RUN_AS_NODE`; unset it to launch Electron.

### H.7 Testing guidelines (must follow for every change)

Layers and commands
| Layer | Command | When |
|---|---|---|
| Fast unit/integration (no render) | `.venv\Scripts\python.exe -m pytest -q -m "not slow"` (~3 min) | every change |
| Render goldens + pixel checks | `pytest -q -m slow` (needs HyperFrames + Chrome) | any change in `renderer/`, composer, CSS, layouts |
| Update goldens | `VT_UPDATE_GOLDEN=1 pytest -m slow tests/test_render_golden.py tests/test_phase2_render.py` | only after LOOKING at the new images |
| Real network (yt-dlp, archive.org) | part of slow; skip with `YT_TESTS=0` | ingest changes |
| Browser e2e (Studio must run) | `node studio/e2e/<suite>.mjs` for flows, design, phase2, export, scroll, link (+ journey with a model); set `VT_PROJECT=reference` | any UI/API change |
| Screenshot sweep | `node studio/e2e/shots.mjs` -> `studio/e2e/out/shots` (light/dark x 1440/760/390) and review them | any UI change |
| Real-video review | render a real project, `vt snapshot`, or a per-scene contact sheet; look at every scene | any planning/design change |
| Upload check | `ffprobe` (h264 High, level >= 4.0, yuv420p, 30/60 fps CFR, AAC 48k) + `ffmpeg -af loudnorm=print_format=summary` (-14 ±1 LUFS, TP <= -1) | any mux/render change |

Rules
* A bug found by testing gets a regression test first (see `tests/test_align_terms.py`, `tests/test_director.py` for the style).
* Never weaken an assertion to make a test pass without writing down why (in the test and in this plan).
* AI steps are tested with a fake provider (deterministic JSON) in unit tests and with the real model in a separate, skippable eval.
* Tests must isolate state: use the `projects_dir` fixture (isolates projects and themes); `conftest.py` turns the local AI off and
  translation off by default.
* For visual work, the acceptance artefact is a picture the owner can see (contact sheet / screenshot), not only a passing test.

### H.8 Edge cases checklist (each should have a test or a documented decision)

Input / ingest
* Silent or near-silent file; music-only file; very short (< 2 s) and long (> 40 min) inputs; mono/8 kHz/odd sample rates; corrupt files;
  video files with no audio track; GIF as input (rejected with a clear message).
* Links: private, age-restricted, removed, geo-blocked, live stream, playlist URL (first item only), 404/403, localhost/LAN (refused),
  redirects to private IPs, very long titles with emoji, missing subtitles, subtitles in another language, rolling auto captions (duplicates).
* Scripts: empty, only punctuation, > TTS limit, mixed Bangla/English/digits, `Name: text` with 1 vs 3+ speakers, emoji in script.
Speech and words
* Soft first word after a pause (was dropped; fixed), unsure word inside speech (was dropped; fixed), hallucinated words in silence and at
  the end (must be dropped), numbers spoken as words ("three thousand", "১ লাখ"), currency/percent, years vs amounts, filler-only sentences,
  two speakers with similar voices (must stay one speaker), overlapping speech.
Planning and design
* No key term in a scene (fallback chain: key term -> topic picture -> sentence gist -> empty is a bug); one-word sentences; very long
  sentences (> 10 s); lists of 2 vs 6 items; contrast at sentence start ("However ...") vs inside; quotes with/without quotation marks;
  Bangla vs English digits and currency per language; repeated topic words; pronoun contractions ("They're") never as keywords;
  abstract words never get a loose emoji; two-word concepts ("black hole") drawn once; same picture not twice in a row.
* AI output: invalid JSON, unknown ids, wrong word ids, too-long text, empty scenes, model timeout/unavailable, slow model (> 2 min) —
  each must fall back without breaking the video.
Render and output
* Bangla conjuncts and fonts (golden test), very long words (shrink-to-fit), 1:1 and 16:9 overflow, captions inside 9:16 safe area,
  contrast over bright/busy/moving media, faces in media, 60 fps, 720p downscale, GPU encoder missing (CPU fallback), disk full,
  first frame not blank, last scene ends with the audio, loudness/peak targets, faststart, H.264 level.
UI
* Narrow widths (no horizontal scroll), dark mode, keyboard-only use, offline server (reconnect banner), long project names, projects with
  0 scenes, a job running while the user edits, undo after AI changes, two browser tabs on the same project.

### H.9 Suggested next steps for the next agent (in order) — all done on 2026-10-22, see H.10; the list stays as the record of the order

1. `vt/ai/` provider layer + fake provider for tests (H.2 rules).
2. Video Script schema + validator + repair + compiler (P4.1), with today's videos expressed in it.
2b. MCP for every assistant (H.2b): script tools, prompts/resources, HTTP transport with token, Claude Desktop / ChatGPT connection screens.
3. LLM full-plan step using the big prompt (P4.2) on the owner's Ollama; eval set + scores (P4.2).
4. VLM visual QA loop (H.2-2) and picture judge (H.2-3).
5. UI milestones U1-U3 (H.3).
6. Stick-figure engine (P4.3) and the `stick` kind.
7. Export presets + AI title/description/hashtags + cover (H.2-5/6, H.3 Export).

### H.10 Status of the handover steps (built 2026-10-22, second round)

All of H.9 steps 1-7 were built and tested in this round, in order. Facts first, then what is *not* done.

| H.9 step | Built | Where | How it is tested |
|---|---|---|---|
| 1. AI provider layer | `complete_json(prompt, schema, images)` with Ollama, OpenAI-compatible, Claude API and a Fake provider; JSON-schema + Pydantic validation, one retry that shows the model its exact errors, disk cache, `vision_provider()` picks the best installed vision model | `vt/ai/providers.py` | `tests/test_ai_providers.py` (fake provider) |
| 2. Video Script | schema (Pydantic -> JSON Schema), catalogue (rigs, 29 verbs, 10 sets with props, camera, sfx), `validate_script` with fixable messages, `repair_script` (synonyms, wrong word ids, over-long text, missing cast/set, missing/misordered beats, requested kind wins), compiler to `scenes.json` (+ `Scene.stick`, `Scene.sfx`), rule plans round-trip through the contract | `vt/script/` | `tests/test_script.py` |
| 3. AI writes the whole plan | one versioned prompt (role, craft rules, transcript, generated catalogue, 3 worked examples validated by a test, schema); `ai_script` -> repair -> validate -> fall back to `rules_stick`; scoring on 6 metrics; 10 eval transcripts | `vt/script/prompt.py`, `planner.py`, `score.py`, `rules_stick.py`, `tests/script_eval/` | unit tests + `VT_EVAL_MODEL=1 pytest tests/script_eval -s` against the owner's Ollama |
| 3b. MCP for every assistant | tools `get_script_task`, `submit_script`, `preview_frames`; MCP prompts (`plan_this_video`, `make_stick_figure_video`, `improve_scene`) and resources (`vt://catalogue`, `vt://script-schema`); HTTP transport with per-install token (`vt-mcp --http --port 8766`, constant-time check, rate limit, revoke); Settings screen with copy-paste config for Claude Code, Claude Desktop (one-click writer), Cursor, VS Code, Gemini CLI, ChatGPT notes; chat-only fallback (copy message, paste JSON back, errors returned as a list) | `vt/mcp/`, `vt/server/app.py`, `studio/src/pages/AIAssistants.tsx`, `review/ChatAssistant.tsx` | `tests/test_mcp_http.py` (token accept/deny/revoke, stdio script round trip), `tests/test_api.py` |
| 4. Vision model | per-scene frame check (cut off / overlap / unreadable / empty / unrelated) with pixel-check fallback, mild automatic fixes, picture judge between dictionary candidates (rendered by the real renderer), media bin captions/tags, cover frame choice | `vt/ai/vision.py`, `media_tags.py`, `publish.py` | `tests/test_vision.py`, `test_media_tags.py`, `test_publish.py` (fake VLM); slow QA test |
| 5. UI U1-U6 | design system `studio/src/ds/` (Button, Segmented, Panel, Tabs, Slider, Popover/Menu, Sheet, Tooltip, Kbd, Splitter + persisted sizes); editor window: title bar with File/Edit/View/Scene/Help menus, browser tabs (Scenes/Words/Media), canvas with click-to-select and outline, context inspector (video / scene / element), timeline (ruler, scene clips with pictures, element chips, stick actions, words, voice waveform, playhead, zoom, draggable scene edges that snap to sentences), command palette (Ctrl+K), shortcuts sheet, AI slide-over; Export presets + publishing kit; Settings sidebar; New video steps | `studio/src/ds/`, `pages/Review.tsx`, `review/Timeline.tsx` ... | `studio/e2e/editor.mjs` (24 checks), `flows` (26), `phase2` (10), `design`, `export`, `scroll` updated for the new layout |
| 6. Stick figures | clean-room engine: 15-joint rig with fixed bone lengths, 2-bone IK, feet stay on the floor, pure function of time (frame-exact), 29 verbs, two-figure handshake / high five, carry/drop props, 10 sets with ~35 prop drawings, speech bubbles and signs, board writing, thought mark, emotions, lip sync from the voice envelope, camera (shots, push/pull/pan/follow/shake), first frame already shows the figure, continuity across scenes, up to 8 figures, sound cues for jumps/falls/celebrations | `renderer/runtime/vt-stick.js/.css`, composer, `vt/cues.py` | `tests/test_stick.py` (+ slow render in all 3 shapes); contact sheets reviewed by eye |
| 7. Export presets + publishing kit | presets (TikTok/Reels/Shorts, YouTube, Square, Custom) with advanced options; AI title/description/hashtags/hook with rule fallback; cover = best frame (VLM or pixel score) with the hook drawn by the same browser (Bangla shaping correct) | `vt/ai/publish.py`, `pages/Export.tsx` | `tests/test_publish.py`, `e2e/export.mjs` |
| H.2-7 transcript polish | suggestions only, one word for one word, accept/reject per item or all, timings untouched | `vt/ai/polish.py` | `tests/test_polish.py` |

New background jobs and endpoints: `/api/ai/*`, `/api/projects/{id}/script/*`, `/qa`, `/publish`, `/polish`, `/media/describe`, `/api/mcp/connect`.
New settings: `ai_provider` (auto|openai|anthropic|off), `ai_script` (let the AI direct every video, not only stick figures), `openai_url/model/key`, `anthropic_model/key`, `ollama_vision_model`, `mcp_token`.

**Real-model evaluation of the prompt** (owner's Ollama, 10 transcripts, AI vs rule director; see `tests/script_eval`): AI output was valid on all 10 transcripts (after the automatic repair pass; one needed the repair step that drops an overlay the model could not fill correctly). Both the AI and the rules cover every beat with no idle gap. The AI wrote **more varied** plans on 8 of 10 transcripts (variety 0.80-1.00 against 0.58-0.92 for the rule director) and matched the sentence's role (question -> think, number -> sign/chart, definition -> point) as well as the rules on 9 of 10. It was **worse on number fidelity and fit on `product-app`** (it dropped a spoken number: 0.50 against 1.00) and slightly less varied on `bn-story`. Counting a transcript as won when the AI is at least as good on 4 of 6 metrics and better on one, it won 7 of 10 (`tests/script_eval`, the check asserts >= 60%). Model used: the server's preferred text model (gemma4). Metrics: valid, coverage, no_idle_gap, number_fidelity, variety, fit (the first four saturate for both, so the comparison really rests on variety and fit: read the table before trusting a single number). Re-run it after every prompt change.

**Not built / unverified (be honest with the owner)**
* StykAnimate/Pivot/Stick Nodes import and export (P4.8-7): **investigated and closed as not feasible without sample files** (2026-10-22). What the repository's own docs/source say: StykAnimate's native formats are `.styk` (project) and `.stkz` (single figure): a 56-byte header (`STYK`/`STKZ`, version 1, zlib flag, lengths, SHA-256) followed by zlib-compressed UTF-8 JSON, easy to write; but the JSON schema for figures is **not documented**, and the Pivot `.piv` v5 document it imports (`figure_types` with `segment_count`, keyframes with `objects[{unique_id, figure_type_id, scale, color_override_raw, field28, angles[], root_x, root_y}]`, `fps`, `canvas_*`, `backgrounds`) carries figure topology inside a binary file that cannot be authored from scratch. A stick figure of ours would need a figure type definition in exactly the format Pivot writes, which only a real `.piv`/`.stk` sample (or reading `codecs/piv_*.py` closely) can pin down. Bring one exported file and this becomes a one-day task: sample poses in the browser engine, map our 15 joints to the figure's segments, write the container. No exporter was written rather than guess.
* Accessibility: Lighthouse is not installed, so the same engine (axe-core, WCAG 2 A/AA + best practice) was run on every main screen, light and dark, 1440 and 390 px (`AXE=<axe.min.js> node e2e/a11y.mjs`): after fixes there are no serious or critical violations (contrast tokens, ARIA on splitters/meters/scene cards, keyboard access to code blocks). Moderate items remain (heading order on some pages, one empty table header in Settings).
* The Electron app got an "AI" menu (settings, command palette) but was not rebuilt or run after this round; the installer is still unsigned and Windows-only verified.
* The picture judge and the frame check were tested with a fake vision model and the plumbing was exercised on the real renderer; quality with `qwen2.5vl` on real videos was not measured.
* Stick figures: no crowds-specific behaviour beyond up to 8 independent figures with slots; no run cycle (walk speed only); props the engine cannot draw show a colour emoji found by name or a lettered circle.
* The ChatGPT connector path was not tried end to end (needs a public HTTPS tunnel and an account); the HTTP server, token and MCP handshake are tested locally.
* The first frame at exactly t = 0 in the editor preview is blank until the poster seek (pre-existing behaviour of the paused timeline); renders show content.

**Added after the first pass of this round**: editing stick-figure plans (`PATCH /api/projects/{id}/scenes/{sid}/actions/{n}` to re-time, change or delete an action
and `PATCH /api/projects/{id}/cast/{cid}` to restyle a character in every scene); splitting, merging, deleting and moving scene edges keep the actions with their words
(`scene_ops._restick`); the editor has a Characters panel, an action list and draggable action chips on the timeline (`studio/e2e/stick.mjs`, 9 checks); script
sounds and physical stick actions (jump, fall, celebrate, handshake...) make sound cues (`vt/cues.py`).

**Dashboard (user request, same day)**: the Projects screen is now a dashboard: summary strip (videos, minutes made, exported, working now, need attention), a "continue where you left off" card, quick-start tiles (Record, Upload, Type a script, From a link, opening New video on that tab), filters with counts (All, In progress, Ready to export, Exported, Needs attention), search (`/` focuses it, `n` starts a new video), style filter, sort (recently edited, newest, name, longest), grid and list views (remembered), cards with duration badge, style/planner/export badges, the export cover as picture when one exists, Edit and Export buttons, a menu (Open, Export, Rename, Duplicate, Show exports folder, Delete), multi-select with bulk delete. Backend: `updated_at`, `export_count`, `last_export(_url)`, `cover_url` in the project summary and `POST /api/projects/{id}/duplicate`. Tests: `studio/e2e/dashboard.mjs` (11 checks), `tests/test_api.py`.
Also: a `run` verb (29 verbs now) with wider strides and a forward lean; a stick scene with no action is no longer a validation error (an idle narrator is fine).

**Verification run on 2026-10-22** (everything below was run, not assumed): `pytest -m "not slow"` all green; `pytest -m slow` all green (render goldens, new stick render in 3 shapes, QA);
browser suites `flows` 26/26, `editor` 24/24, `stick` 9/9, `phase2` 10/10, `design` 16/16, `export` 8/8, `scroll` 8/8; `shots.mjs` found no sideways scroll at 1440/760/390 in light and dark.
The `link` suite (network) was not run. The `journey` suite (real speech model) was updated for the Words tab and passes 16/16 after relaxing one check: "scenes were drafted" now accepts 2 or more (the director plans the 4-sentence `bn_plain` clip as 2 scenes; the plan stage is unchanged for picture videos in this round, but this was not compared against the code from before the round, so treat the old threshold of 3 as possibly stale already).

### H.11 Full QA round (2026-10-22, third round): what was found, fixed and checked

**HTTP 405.** Root cause: the Studio on port 8765 was started before the new endpoints existed, so FastAPI answered `405 Method Not Allowed` for paths that matched a route with another method (e.g. `/api/projects/{id}/audio/cut`). Fixes: every unknown `/api/*` path now returns a JSON 404 (catch-all registered before the static files); `/api/health` carries `api_version` (now 4) and the Studio shows a banner when the server is older than the page (`EXPECTED_API` in `studio/src/api.ts`); a 405 in the UI says "restart the server". Regression tests in `tests/test_api.py` list every route and check that no documented method pair gives 405 and that unknown paths are 404.

**Other bugs found by driving the real app** (all fixed, each with a test): concurrent audio edits raced on Windows file replace (per-project lock, serial client queue, `read_json` retry); simultaneous composes collided (per-project lock, unique temp names); `JobBusy` was a 500 (now 409); stick videos also drew a cartoon (overlays stripped); emoji mode did not exist (added: stickers and keywords only, never the same emoji twice in a row); pictures and story gave the same video when the use case was left empty; stick stage overlapped the captions in 9:16 (stage moved up); a long stretch of noise or music before the first word gave an 8 s still opening without captions (stage_cuts trims it to 0.6 s before the first word, `LEAD_IN_MAX`/`LEAD_IN_KEEP` in `vt/pipeline.py`).

**Free media catalogue** (`vt catalog`, `/api/catalog`, `data/catalog/`): 23 entries found through the Internet Archive and Wikimedia Commons APIs, each downloaded and decoded before it is listed, with licence, author and source URL. Only CC0, public domain and CC BY are accepted (NC, ND and share-alike are refused in `licence_ok`). Credits are written into every export. Wikimedia requires a User-Agent with a contact URL: the contact comes from `catalog_contact` in settings.json or the `VT_CATALOG_CONTACT` environment variable (a URL or email); until the owner sets one the default only names the app.

**Real generation** (`scripts/qa_generate.py`, then `scripts/qa_analyze.py`; ffprobe, loudnorm, black/freeze detection, A/V end difference, first frame, music audibility): Bangla recording 9:16 and an English LibriVox sample with catalogue music 16:9 and 1:1, in pictures, story, product, stick and emoji. All H.264 High yuv420p, AAC 48 kHz, fast start, -14 LUFS, peak below -1.4 dBTP, picture and sound within 0.02 s. `scripts/qa_media_audio.py` adds two catalogue clips to a project (they become scene backdrops, captions stay readable) and checks that a 2 s cut shortens the export by 2.0 s, a mute leaves the range silent (0.001 rms) and -12 dB comes out as -12.0 dB.

**Browser suites** (run against an isolated server with `VT_DATA`, never the owner's settings): `flows` 26/26, `editor` 24/24, `edge` 23/23, `timeline` 23/23, `dashboard` 11/11, `crawl` 514 interactions with 0 problems (a 422 from a voice edit that is refused on purpose, e.g. splitting where an edge already is, is not counted), `a11y` with axe-core: no serious or critical violations (fixed: trim handles had an ARIA label without a role, the count badge on the active filter had low contrast). `stick` 9/9 (the delete-action check now selects scene 1 first, because undo can move the selection). The crawl found that the preview files could be read while they were being rewritten (404 / wrong length): `/media` now sends small files from memory and retries a locked file. A project that was planned but never composed (e.g. just built by a script) used to show raw JSON in the preview; `/media` now composes it on the first request (this was the cause of `flows` failing right after `build_reference.py`; it now passes right after a rebuild). The Bangla run was repeated with the final modes: 9:16, no problems, glyphs shaped correctly in captions and keywords. Full `pytest` (including the slow suite) passes. Scripts in `studio/package.json`: `e2e:timeline`, `e2e:edge`, `e2e:crawl` were added.

**Incident:** an early crawler run used the real `settings.json` and changed a setting. It was restored from the earlier content and the crawler and suites now always use `VT_DATA`.

**Not verified:** the ChatGPT connector, StykAnimate interop, the Electron rebuild (out of scope by request), real photos of people for the picture judge, Bangla in the stick and emoji modes by a native reader.

---

## Phase 11 plan (2026-10-23): one launch, every platform, a very simple UI - after a clean board and a full test

Owner: "after this entire build pass the software should be launchable from one script completely (then it becomes one EXE or launch file across platforms). You are welcome to port to other languages, use multiple languages and frameworks. UI should be amazingly simple. Test everything after cleaning up the board." This is the **last** phase: it runs after Phases 9, 10, 7, 8 and the rest of 9 are done (Phase 7 already gives one Python environment and a product folder for Windows; this phase makes it one launch on Windows, macOS and Linux and simplifies the UI).

### P11.0 What the board looks like today (measured 2026-10-23)

| Item | Size | What it is | Fate |
|---|---|---|---|
| `.venv` | 5.4 GB | the app's Python | rebuilt from `uv.lock` (Phase 7) |
| `.venv-voice` | 5.5 GB | cloning-only Python | deleted in Phase 7 |
| `models/` | 5.1 GB | downloaded models | moves to the user data folder |
| `desktop/` | 1.9 GB | the old Electron shell and its builds ("forget Electron") | replaced by the Tauri shell (P11.2), then deleted |
| `projects/` | 1.3 GB | the owner's real projects | moves to the user data folder (migration, tested on a copy) |
| `SFX/` | 648 MB | sound-effect source files at the repo root | check what the app uses (`assets/sfx` is the bundled set); keep the used ones in `assets/`, the rest out of the repo |
| `tools/concat` | 314 MB | optional Concat engine | an optional download in the product, not in the repo |
| `renderer/` | 288 MB | Node + HyperFrames + fonts/icons packages | stays, installed from `package-lock.json` |
| `studio/` | 145 MB | React Studio (mostly `node_modules`) | stays, built into the product |
| `qa_out*` (10 folders) | about 250 MB | QA renders from 2026-10-22/23 | deleted (the QA scripts recreate them in a temp folder) |
| `NVIDIA Corporation/`, `english sample.mp3`, `settings.json`, `translate_cache.json`, `ai_cache/`, `voices/` at the repo root | small | user data and stray files mixed with code | user data moves to the data folder; the stray folder is removed; the sample moves to `samples/` |

The app is started today by `scripts/start.ps1` (Windows only) after a manual `.venv` and `npm install` in two folders.

### P11.1 Architecture decision (what runs where, in which language)

* **Shell: Tauri 2 (Rust)** for the window, the installer and the auto-start of everything else. Reasons: one code base for Windows (.exe/.msi), macOS (.app/.dmg) and Linux (AppImage/.deb); the window is about 10 MB because it uses the system web view (WebView2 on Windows, WebKit on macOS/Linux), against Electron's 150+ MB Chromium; Tauri has first-class "sidecars" (programs bundled and started with the app) and an updater. Rust is also the language of Concat, so its engine can later run inside the same process if it replaces the ffmpeg path.
* **UI: the existing React Studio** (TypeScript), served to the Tauri window from the local server (unchanged API), simplified (P11.4).
* **Brain and pipeline: Python** stays (speech recognition, AI, audio, planning: this is where the ML libraries are; porting them would cost months and gain nothing). Shipped as **python-build-standalone + the locked packages** (Phase 7), started by the shell as a sidecar on a free local port with a random access token.
* **Renderer: Node + HyperFrames + Chrome** stays (Bangla shaping and the motion graphics depend on it), shipped as a sidecar (Node binary + `renderer/` + the Chrome HyperFrames downloads, put in place at build time).
* **Media tools: ffmpeg/ffprobe** shipped per platform (pinned builds).
* **What is ported, and why only this:** (1) the launcher logic (find free port, start Python, wait for health, start/stop children, show a clear error page if one fails) moves into the Rust shell; (2) a single cross-platform launch script (`videotool` / `videotool.cmd`, P11.3) for developers and for users who do not want the shell. Nothing else is ported unless a measured bottleneck asks for it (candidates noted for later: the people-mask geometry and the retention scorecard's frame analysis, if they show up as slow, could move to Rust inside the shell).

### P11.2 Step by step

**Step 1 - Clean the board (3-4 h)** - before any packaging, so what is packaged is only what is used.
1.1 Inventory with tools, not memory: `vulture vt scripts` (dead Python code, then each hit checked by hand before deletion), `ts-prune` / `knip` on `studio` (unused exports and files), `depcheck` on `studio` and `renderer` (unused npm packages), `deptry` on the Python project (unused and missing dependencies). Every removal is one commit-sized change with the tests run after it.
1.2 Separate code from data: `vt/paths.py` gets one user-data root per platform (Windows `%LOCALAPPDATA%\VideoTool`, macOS `~/Library/Application Support/VideoTool`, Linux `$XDG_DATA_HOME/videotool`), holding `projects/`, `models/`, `voices/`, `settings.json`, caches (`ai_cache/`, `translate_cache.json`); `VT_DATA` still overrides it (tests and QA keep using it). Migration: on first start, copy the old repo-root folders to the data root if the data root is empty, write a note, never delete the originals automatically. Tested on a copy of the owner's real `projects/` (1.3 GB) before it touches the real one.
1.3 Delete: `qa_out*`, `NVIDIA Corporation/`, `.venv-voice` (Phase 7), `desktop/` (after the Tauri shell works, step 3), the Concat copy in `tools/` (becomes an optional download with checksum, like models), sound files in `SFX/` that nothing references (`grep` + a test that every SFX id used in `vt/cues.py` and `vt/sfxlib.py` resolves to a bundled file).
1.4 One QA entry point: `scripts/qa_all.py` runs every real-media QA script (`qa_generate`, `qa_analyze`, `qa_media_audio`, `qa_layers`, `qa_sounds`, `qa_voices`, `qa_aroll`, `qa_entities`, the retention scorecard) into a temp folder against an isolated server it starts itself, and prints one summary table.
1.5 One test entry point: `scripts/test_all.py`: Python tests (fast + slow), TypeScript type check, Studio build, every e2e suite against an isolated server it starts (the reference project is rebuilt and the composition warmed up before each suite, the leaked headless browsers are killed after each suite: both were sources of flaky failures on 2026-10-23), axe accessibility; one summary, non-zero exit on any failure.
**Gate:** the repo (excluding `.venv`, `node_modules`) is under 150 MB; `test_all.py` and `qa_all.py` pass on the cleaned tree; `git status`-style listing of what was removed is recorded here.

**Step 2 - One launch script, all platforms (3 h)**
2.1 `videotool` (POSIX sh) and `videotool.cmd` (Windows), the same steps: (a) if `uv` is missing, download the pinned uv binary for the platform into `.tools/` (checksum); (b) `uv sync --frozen` (creates the one environment from the lock; downloads python-build-standalone if no matching Python); (c) `npm ci` in `renderer/` and `studio/` if `node_modules` is older than the lock, using a pinned Node downloaded into `.tools/node` when none is installed; (d) `npm run build` in `studio/` if `dist` is older than the sources; (e) ffmpeg: use a pinned download in `.tools/ffmpeg` when not found; (f) start the server on a free port, wait for `/api/health`, open the browser (or print the URL with `--no-open`).
2.2 First run downloads (uv, Python, Node, ffmpeg, Chrome for HyperFrames, about 1.5 GB plus the Python packages) show progress and can be resumed; every download is pinned and checksum-checked; nothing is installed system-wide, everything lives in `.tools/` and the user data folder.
2.3 `videotool --check` runs the doctor (GPU, disk space, ports, each tool's version) and exits; `videotool --test` runs `test_all.py`.
**Gate:** on fresh user accounts with nothing installed (Windows 11 here; Ubuntu 24.04 and macOS 14 in VMs or CI runners), `git clone` + `./videotool` reaches a working Studio and makes a video from `samples/audio/bn_plain.mp3` end to end; the time to first video is written down per platform.

**Step 3 - The app: one installer per platform (Tauri) (6-8 h)**
3.1 `app/` (new): Tauri 2 project; `src-tauri/main.rs` does what `videotool` step (f) does, natively: picks a free port, starts the Python sidecar with a random token (the server refuses requests without it; the Studio gets it through the window), waits for health with a splash screen, shows a readable error page with "copy the log" if a sidecar fails, stops all children on quit (no orphan Python/Node/Chrome/ffmpeg processes: tested by counting processes after quit).
3.2 Sidecars bundled per platform: the Python runtime + site-packages (Phase 7 step 6 layout), Node + `renderer/`, ffmpeg/ffprobe, the HyperFrames Chrome; Tauri's `externalBin`/resources configuration; models still download on first use into the data folder (first-run page from Phase 7 step 7).
3.3 Build in CI for the three platforms (GitHub Actions matrix: windows-latest, macos-14 (arm64) and macos-13 (x64), ubuntu-22.04); artifacts: `.msi` + `.exe` (NSIS), `.dmg`, `.AppImage` + `.deb`. Code signing is listed as not done unless the owner provides certificates (unsigned builds show OS warnings; written in the README).
3.4 Size and start budget, measured and recorded: installer size per platform, installed size, cold start to usable Studio (target under 10 s on this laptop after the first run).
**Gate:** on each platform the installer installs, the app opens, the smoke list (Phase 7 step 6) passes through the UI, quitting leaves no child processes, uninstall removes the program and keeps the user's projects.

**Step 4 - An amazingly simple UI (8-10 h)**
The current Studio is a full editor (menus, timeline, inspector, panels). Most videos should need none of it. Rebuilt around three screens; the full editor stays one click away for people who want it.
4.1 **Home = one action**: a single large drop area "Drop a video or a recording, or paste a link, or type a script" (one input that understands all four), the language picked automatically from the speech (shown, changeable), and below it the recent videos as large thumbnails. No settings on this screen.
4.2 **Making = one progress view**: a single progress bar with plain words ("Listening", "Writing captions", "Choosing pictures", "Rendering"), a live preview that fills in as scenes are ready, and the estimated time; nothing to decide.
4.3 **Result = watch and share**: the finished video playing, the retention check as one sentence ("Strong opening, no dull moments" or "2 slow moments: fix them"), and four buttons: **Download** (shapes for TikTok/Reels/Shorts and YouTube in one click), **Change the look** (6 large style cards: Clean, Bold, Story, Stick figures, Emoji, My speaker), **Fix a word** (the Script panel), **Edit everything** (opens the current editor).
4.4 Every other option moves to "Edit everything" or to Settings, which shrinks to: language, my voice, AI (on/off and which), storage location, about. Defaults decide the rest.
4.5 Design rules, checked by tests: at most one primary button per screen; no screen needs scrolling at 1280x720; every action reachable by keyboard; text at least 14 px; axe clean; works at 390 px wide (phone browser to the local server).
4.6 Usability check with real people is outside what an agent can do: written as the owner's task (three people making their first video without help, timed), with what to watch for.
**Gate:** new e2e suite `e2e/simple.mjs`: from an empty data folder, drop the sample recording, wait, watch, download 9:16 and 16:9, change the look, fix a word, all without opening the editor; total clicks counted and recorded (target: 3 clicks from drop to downloaded video); the existing editor suites still pass through "Edit everything".

**Step 5 - Test everything on the cleaned board (3-4 h)**
5.1 From a fresh clone on this machine: `./videotool --test` (all Python tests, type check, build, every e2e suite, axe) and `scripts/qa_all.py` (all real-media checks: the five modes, the owner's talking-head video, sounds, voices, layers, logos and flags, retention scorecard).
5.2 The installed app on Windows (from the `.msi`), plus the CI-built macOS and Linux packages in VMs/runners: the smoke list and `e2e/simple.mjs` against the installed app.
5.3 Resource checks after 10 videos in a row: no growth of temp folders, no orphan processes, memory back to baseline.
5.4 The report: every check with its result, everything not verified said plainly (e.g. code signing, macOS on real hardware if only CI was used, usability with real people).
**Gate:** all of 5.1-5.3 pass; the report is written into this section and handed over.

### P11.3 Order and estimate

Step 1 (clean) -> step 2 (one script) -> step 5.1 (test everything from a fresh clone) -> step 4 (simple UI, so it is tested on the clean board) -> step 3 (Tauri app and installers) -> step 5.2-5.4 (installed-app tests and the report).

**Estimate: 25-32 working hours**, after the earlier phases. Not included: code-signing certificates (the owner's purchase), real-user usability sessions (the owner's task), an auto-update server.

---

## Phase 10 plan (2026-10-23): context understanding - one shared reading of the video

Owner: "so I guess we need context understanding". Agreed: the failures seen so far are context failures. "Amazon" got a superhero emoji (word without topic), a scene kept two thirds of the frame empty (no idea what else the sentence was about), a baby's babble became "farm animals" (sound without topic), and Phases 5, 8 and 9 each plan their own small guess (narrative map, entity disambiguation, heartbeat choices). This phase builds **one** reading of the whole video that every other part uses.

### P10.0 What exists today (checked)

* Picker: each word is compared with its own sentence (multilingual embeddings) to choose an icon sense (`vt/visuals/picker.py`). No look beyond the sentence.
* Roles analysis (`vt/director/roles.py`): per-sentence role (hook, claim, number, step, ...) from rules.
* Local AI (Ollama `gemma4` on the LAN, Claude over MCP when connected): writes a short story brief (`story_brief`) used by the planners; not stored as structured data, not used by the picker, sounds or layouts.
* Topic counts (`vt/visuals/terms.py`): word frequency over the video, used for key terms.

### P10.1 The context document (`context.json`, produced by a new pipeline stage `context` after `words`)

One JSON per project, versioned, every field tied to word ids so it follows edits:
1. **Topic and domain**: one line ("selling on Amazon and eBay as a side business"), domain tags (e-commerce, personal finance), audience guess, language mix.
2. **Entities**: every named thing with its type and the spans where it is mentioned, including pronouns and short forms resolved to it ("Amazon ... it ... they" -> the company), with the evidence (P8's rules feed in here; the AI confirms or rejects ambiguous ones: "Amazon" here is the company, not the river, because the video is about selling online).
3. **Sentence map** (the P5.4 narrative map, now here): per sentence its idea in a few words, role, importance 0-3, and which earlier sentence it continues, explains or contrasts.
4. **Sections**: where the topic changes (for pattern interrupts, chapters, the A-roll returns).
5. **Facts**: numbers, dates, names and lists the speaker actually said, with their word ids (the only facts charts and labels may use).
6. **Visual intents** per sentence: what a picture should show to help this sentence ("a person packing a parcel", "the eBay logo", "a rising chart of 30 % growth"), used by B-roll search, the picker, logos/flags and the heartbeat, so every added picture is about what is being said.
7. **Sounds in context**: the sound events of P6.6 re-read with the topic (a babble in a parenting video is a baby; in a farm video it may really be animals).

### P10.2 How it is made

1. **Rules first, always available offline** (2-3 h): the existing roles, topic counts, entity table (P8), sentence embeddings for "continues / contrasts", numbers and lists from the transcript. This alone fills every field with lower-quality guesses and marks them `source: rules`.
2. **AI pass when an AI is available** (3-4 h): one structured request to the configured provider (Ollama gemma4 locally, or Claude/OpenAI when set) with the full transcript (word ids), the rule draft and a strict JSON schema; the existing `complete_json` with validation and repair is reused. The validator refuses any fact or entity not present in the transcript's words (no invented facts), any span that does not exist, and any change of the speaker's meaning. Long videos are read in overlapping windows of about 1,500 words with the topic carried over.
3. **Owner corrections**: a "What the video is about" panel in the Video inspector shows the topic, entities (with their pictures), sections; the owner can correct a wrong entity ("Amazon here is the river") or the topic, and everything downstream re-plans from the corrected context.
4. **Cache and edits**: the stage hash covers the transcript and the AI model; a word edit only re-reads the affected window.

### P10.3 Who uses it (changes in the other phases)

* Picker and logos/flags (P8): disambiguation by the context's entity types instead of local word rules; pronouns get the entity's picture when it is the subject.
* B-roll and motion graphics (Phase 5): search queries come from the visual intents; charts only from the facts list.
* Retention (P9): the heartbeat and pattern interrupts pick from the sentence's visual intent and the section boundaries; the hook uses the most important sentence of the map.
* Sounds (P6.6): labels re-read with the topic.
* A-roll (P5): the speaker is shown for sentences of type personal statement / opinion, graphics for facts and explanations.

### P10.4 Tests and gates

* `tests/test_context.py` with hand-written expected readings for five transcripts (the owner's talking-head video, the Bangla reference, the LibriVox sample, a script naming brands and countries, a sound-only recording): the topic line mentions the right subject; Amazon/eBay typed as companies, "the Amazon rainforest" typed as a place; every fact's words are in the transcript; sections split where a human would (within one sentence).
* An offline run (no AI) still produces a valid context and the video still renders.
* A/B on renders: the same five videos planned with and without context; contact sheets compared by a person once, and the P9 scorecard must not get worse on any of them.
**Gate:** the tests pass with the rules alone, and with the AI pass on the owner's Ollama; the owner's video shows the Amazon and eBay logos and no unrelated picture anywhere.

**Estimate: 10-14 working hours.** Order: build P10 before P8 step 2 (entity matching) and P9 step 2 (heartbeat), because both need its output; the P9 scorecard (measurement only) can come first since it does not depend on context.

---

## Phase 9 plan (2026-10-23): retention - keep viewers watching

Owner (with a screenshot of a 16:9 scene: a money emoji and "financially" on the left, the right two thirds empty "for a long time, till another icon fills it"): "it can hamper retention rate. Think about retention and build algorithms to keep people hooked through visuals. Think how you can beat the algorithms of popular media platforms."

### P9.0 What the platforms reward (and what we can and cannot do)

Nobody outside YouTube, TikTok, Instagram and Facebook can see or change their ranking code. What they reward is public and measurable: **viewers who stay past the first seconds** (TikTok/Reels/Shorts swipe-away rate, YouTube "stayed to watch" in Shorts), **average view duration and percentage viewed**, **completion and rewatches** (loops in Shorts/Reels), **shares, saves, comments**, and for long videos **click-through rate x average view duration**. We cannot game these (no fake views, no misleading thumbnails: platforms penalise both and it would hurt the owner's channel); we can make every video *earn* them: an opening that answers "why should I keep watching" in under 2 seconds, something new on screen often enough that the eye never has a reason to leave, no empty or dead stretch, a pay-off that rewards finishing, and an ending that loops or asks for a reply. Every rule below is measured on the rendered frames, not assumed.

### P9.1 The empty-space problem in the screenshot (root cause, to verify first)

In 16:9 the `grid`/`side` layouts reserve slots for elements that enter later in the scene (each element appears at its spoken word): the first element is placed in its final slot on the left and the others' slots stay empty until their words are spoken. For a scene whose second element comes 5 s later, two thirds of the frame is empty for 5 s. Fixes (P9.3 step 2): the layout is computed for the elements *visible now* and re-flows (animated) when the next one enters, so the first element starts centred and large and moves aside to make room; plus the "visual heartbeat" fills long gaps.

### P9.2 Measurements first: a retention scorecard for every render (`vt/retention.py`, 3 h)

Computed from the composition (`data.json`) and from frames of the rendered MP4, for each video and shape, saved next to the export and shown in the Export page ("Retention check"), so every later change is judged by numbers:
1. **Hook time**: seconds until the first frame that has (a) a picture or big text and (b) the topic word on screen. Target <= 1.0 s (Shorts/Reels decide in 1-2 s).
2. **Visual change interval**: the times when something new appears or moves noticeably (new element, scene change, punch-in, text reveal), from the timeline plus a frame-difference check every 0.1 s on the render (mean absolute difference of a 64 px grey thumbnail above a threshold). Report the longest gap and the share of gaps over 3 s. Target: no gap > 3.0 s in 9:16, > 4.0 s in 16:9; median 1.5-2.5 s.
3. **Empty frame ratio**: per frame, the share of the safe area that is plain background (no element, no picture, no person) from a saliency/edge map of the frame; report the seconds where more than 60 % is empty and the longest such stretch. Target: no stretch > 1.5 s (the screenshot would fail: about 5 s at about 65 % empty).
4. **Text density**: words on screen at once and their reading time; flag frames with more words than can be read in their time (about 3 words/s) and frames that only repeat the caption.
5. **Motion energy**: average frame difference per scene (too still = drop-off; too busy = fatigue); flag scenes outside a band learned from the owner's best videos.
6. **Audio retention checks** (from the existing loudness/silence analysis): dead air > 0.7 s, loudness dips.
7. **Ending**: does the last 2 s connect to the first 2 s (loop) or carry a question / call to comment.
8. **One number**: a "retention risk" score 0-100 as a weighted sum of the above, with the weights shown (not a black box), and the worst three moments with timestamps and "fix it" buttons (P9.4).
**Gate:** the scorecard runs on the five QA videos of 2026-10-22/23 and on the screenshot's project and its numbers match what a person sees (the screenshot's scene is reported as the longest empty stretch, with the right time).

**P9.2 status 2026-10-23: built and tested** (`vt/retention.py`, `tests/test_retention.py` 6/6 on videos with known answers, `e2e/retention.mjs` 8/8): computed after every export (saved as `<export>.retention.json`), `POST /api/projects/{id}/retention`, summary in `GET .../exports`, "Retention check" card on the Export page (score, verdict, moments with jump-to buttons). Measures hook time, change gaps, empty stretches (share of the area above the caption zone that is plain background), dead air, caption reading speed and motion; targets are labelled as defaults. **On the owner's screenshot case** (talking-head project, 16:9) it reports the scene 26.75-33.25 s as the empty stretch (a small sticker alone in the frame until the next element enters at 30.72 s) and two more the owner had not named (5.75-11.25 s and 44.5-53.0 s), all confirmed by looking at the frames; risk 56/100 ("Risky"). **Not done:** the "Retention" lane on the timeline, fix buttons per problem (P9.4), learning from the owner's analytics.

### P9.3 Algorithms that keep viewers watching (built after the scorecard can measure them)

**P9.3 step 2 status 2026-10-23: the layout half is built and verified; the heartbeat half waits for Phase 10.** Built in `renderer/runtime/vt.js` (`flowStages`): an element that has not entered yet takes no room; the first element of a scene starts alone, centred and up to 1.7x larger, and when the next one enters the ones on screen glide to their new places (tweens on the same seekable timeline); a scene with one element lets it grow to fill its stage (up to 1.6x). Verified by re-rendering the owner's talking-head project (16:9 and 9:16) and looking at the frames: the screenshot's scene (26.7-33.2 s) now shows the sticker alone and big until the second arrives, then both side by side; the scorecard no longer flags it (plain share 0.88 -> 0.76; the empty threshold is 0.80, calibrated by eye on these frames). **Still flagged, on purpose:** scenes that are one number or card for 5-8 s (5.75-11.25 s and 44.5-53 s in that project): they need a second, related visual (heartbeat) or a split at a sentence boundary, chosen by meaning, which Phase 10 provides. Risk went 56 -> 47 (16:9) and 38 (9:16).

**P9.3 step 2 completed 2026-10-23 (heartbeat, `vt/director/heartbeat.py`, `tests/test_heartbeat.py` 6/6):** where the gap between two visible changes in a still scene is longer than 2.5 s (tall) or 3.5 s (wide), one more thing is added at a word spoken in the gap: a picture for the word when the dictionary has one, else the word in type if it is a real content word, else nothing; never on scenes that move, never more than four elements; a scene that is still too still for want of a real word becomes a speaker scene when the project has the speaker's picture. Also in this step: in 16:9 the base element size went from 0.8 to 1.0 (the renderer still shrinks anything that does not fit). **Measured on the owner's talking-head project, 16:9, with real renders and the scorecard: risk 56 -> 32, longest wait for a change 8.3 s -> 2.5 s, longest empty stretch 8.5 s -> 5.0 s (one left: a lone "100 %").** 9:16: risk 41 (the speaker fills the crop, so the overlay elements are dropped there). The heartbeat uses the spoken words only; choosing its picture from the sentence's `intent` in `context.json` is not wired yet. **Not done:** splitting a long scene at a sentence boundary, the strongest-moment cold open, pacing profiles.

### P10 status 2026-10-23: first slice built (`vt/context.py`)
A pipeline stage *context* (after words, before plan) writes `context.json`: topic, domain, mood, named things with a type, one line per sentence (idea, role, importance, relation, what a picture should show), sections, facts. **Rules reading** always (roles analysis, word statistics, capitalised names including eBay/iPhone style, numbers and lists, vocabulary-shift and marker-based sections). **AI pass** (window by window, the topic carried over) with `repair_window` (the model often answers with the sentence text or a bare number instead of the id) and a strict `check_window` (an entity must be said at the words it names, sentences and sections must exist; anything else is refused and the rules reading stands, with a note); the AI cannot add a fact that was not said. On the owner's Ollama (gemma4) the AI pass took 24-37 s for a 60 s video and recognised **Amazon and eBay as companies** (the rules only had "name"), wrote section titles and concrete picture intents ("a profit graph or a stack of money"). The owner's corrections (`context.overrides.json`: an entity's type, remove, topic) win over both and survive rebuilds; the reading is marked out of date when the words change. API: `GET/POST /api/projects/{id}/context`, `PUT .../context/entity`, `PUT .../context/topic`; Studio: "What the video is about" panel in the video inspector. The planners take their story brief from it (one AI call fewer). Tests: `tests/test_context.py` 8/8 (rules, AI with scripted answers incl. refused ones, repair, windows, overrides, API), `e2e/context.mjs` 7/7. **Not done:** the other consumers (logos and flags matching in Phase 8, B-roll queries from intents, sound events re-read with the topic, speaker-vs-graphic choice from sentence roles, heartbeat pictures from intents), `facts` used by charts, per-edit incremental re-reading.

**Step 1 - The hook (2-3 h)**
* The first 1.5 s show the strongest picture of the whole video (the highest-scoring visual from the picker, or the speaker's most animated A-roll moment by motion and loudness) together with the topic in big text, from frame 1 (no fade-in from an empty frame; already partly done: "the opening picture is on screen at 0 s").
* Optional "cold open" (owner setting, off by default): the most striking sentence of the video (highest emphasis + a number or a surprising claim, from the narrative roles) is played first for 2-3 s, then the video starts. Uses the existing cut machinery, so the audio stays the speaker's own words.
* Title text for the first scene is shortened to at most 5 words, written as a promise or a question from the speaker's own words (the AI planners already produce a hook line; it is validated so it only uses facts from the transcript).

**Step 2 - No empty frame (3-4 h)**
* Re-flowing layouts (P9.1): elements take the space that is free *now* and move aside, with an animation, when the next element arrives. The first element of a scene starts centred and large.
* "Visual heartbeat": whenever the change interval would exceed the target (2.5 s in 9:16, 3.5 s in 16:9), the composer inserts a small change at the next word boundary, chosen in this order: highlight the spoken keyword in the on-screen text, a subtle push-in on the current picture or speaker (the A-roll punch rules apply: never two in a row), a secondary icon/sticker for the next content word that the picker scored (its `extras`), a number or label pop-up when a number is spoken, a gentle background drift. Never a random or unrelated picture.
* Scenes longer than 6 s with one element are split at the sentence boundary closest to the middle (the plan already has sentence boundaries), so a new picture arrives.

**Step 3 - Pace and pattern interrupts (2 h)**
* Per-video pacing profile from the content: tutorials calmer (change every 3 s), shorts and hooks faster (every 1.5-2 s). Owner setting: Calm / Normal / Social.
* A pattern interrupt every 20-40 s in long videos (a scene type not used in the last few scenes: a full-screen word, a speaker close-up, a chart), timed to the start of a new idea (topic change from the narrative map).
* Captions: word-by-word highlight is already there; the keyword pop on emphasised words is kept to at most one per sentence (more is noise).

**Step 4 - Reward finishing and rewatching (2 h)**
* An open loop: when the speaker says "later / at the end / the third reason", the scene shows a small "3 of 3" style counter or progress marker (only from the speaker's own words, never an invented teaser).
* A loopable ending for Shorts/Reels (owner setting): the last frame's layout matches the first frame's, so the replay looks continuous (platforms count loops as rewatches).
* A last-second question card in the speaker's own words when the video ends on a question, to invite comments (no generic "like and subscribe" unless the owner turns it on).

**Step 5 - Covers and titles (1-2 h)**
* The publish kit already makes a cover: score cover candidates by face visibility (P5 face data), contrast, a short big word, and choose the best; never a frame that is not in the video (honest thumbnails keep viewers, misleading ones get swiped and penalised).

**Step 6 - Learn from the owner's own results (3-4 h, needs the owner's data)**
* Import the retention curves the platforms give the creator (YouTube Studio "audience retention" CSV export, TikTok/Instagram analytics exports) for videos made with this app; line them up with the scorecard's per-second features (change interval, empty ratio, scene types, speaker vs graphic) and show which features came before drops. With enough videos (about 20+), fit a simple, readable model (logistic or gradient-boosted trees with feature importance shown) that predicts drop-off risk per second, and use it to weight the scorecard. No data is sent anywhere; the owner exports the files by hand.
* Until there is data, the rules above are the best-known defaults and are labelled as such in the UI.

### P9.4 In the editor

* Export page and timeline: a "Retention" lane showing risk per second (green / amber / red), the three worst moments with timestamps, and a button per problem that applies the fix the scorecard suggests (add the next picture earlier, split the scene, add a heartbeat). Each fix is a normal plan edit (undoable).
* Settings: pacing profile, cold open, loopable ending, question card.

### P9.5 Order and gates

1. P9.2 scorecard (gate above). 2. Re-flowing layouts + heartbeat; gate: the screenshot's project has no empty stretch over 1.5 s and no change gap over the target, in both shapes, and `e2e/contrast.mjs`, `e2e/flows.mjs` and the people check stay green. 3. Hook; gate: hook time <= 1.0 s on all QA videos. 4. Pacing profiles and interrupts; gate: the change-interval targets per profile are met and a person watching the contact sheets does not see random pictures (every added visual comes from a spoken word). 5. Ending and covers. 6. Learning from real analytics when the owner provides exports.

**Estimate: 16-22 working hours** for P9.2-P9.5 steps 1-5; step 6 depends on the owner's data. Suggested order with the other phases: P9.2 (scorecard) and P9.3 step 2 (no empty frame) first, because they fix what the owner saw today; then Phase 7 (one environment), Phase 8 (logos and flags), the rest of Phase 9.

---

## Phase 8 plan (2026-10-23): named things get their real picture (brand logos, flags, and more)

Owner: "if voices have some company name like Amazon, eBay we can use them [their logos]. Have all the world's company logos; languages can have flags too; if a word like France, the French flag. Think like this and expand the list." Today a spoken "Amazon" gets a generic emoji (the 2026-10-23 render of the owner's talking-head video showed a superhero emoji for "Amazon"), and "France" gets nothing specific.

### P8.0 Facts (checked in the code on 2026-10-23)

* The picker (`vt/visuals/picker.py`) chooses one picture per sentence from `Match(word, line, sticker, z_line, z_sticker, source)`; `source="seed"` means "an exact, trusted hit" and wins over meaning-based guesses (the clipart for "black hole" already works this way through `Lexicon.art()` and the `art-` sticker prefix).
* Stickers are keys resolved by `vt/visuals/emoji.py` (`emoji_key`, `svg`, `label`); the `art-` prefix already shows how a second picture source plugs in. The renderer draws whatever SVG the key resolves to; the composer copies used stickers into the page (`used_stickers`).
* **Flags are already in the bundled emoji set**: Twemoji has all country flags (e.g. France = `1f1eb-1f1f7`, regional-indicator pairs) and the subdivision flags England, Scotland, Wales. No new download is needed for flags.
* Not present: brand logos, a country/demonym/capital/language table, the `babel` package (CLDR data). `wordfreq` is installed (used to tell common words from names).

### P8.1 What "named things" means (the list, expanded)

| Kind | Examples (spoken) | Picture | Data source (licence) |
|---|---|---|---|
| Company / product brand | Amazon, eBay, Google, YouTube, bKash, Grameenphone, Daraz, Pathao, Toyota, Coca-Cola, Nike, Visa, PayPal, TikTok, WhatsApp, ChatGPT/OpenAI | the brand's logo in its own colour | Simple Icons (data CC0; logos are trademarks of their owners, shown to name the company, i.e. nominative use), about 3,300 brands; plus a hand-made list for local brands Simple Icons lacks (bKash, Nagad, Grameenphone, Robi, Banglalink, Daraz, Pathao, Foodpanda BD ...), drawn as a coloured text badge, never a fake logo |
| Country | France, Bangladesh, Japan, "United States", "UK", ফ্রান্স, বাংলাদেশ, ভারত | the country's flag | Twemoji flags (already bundled, CC-BY 4.0); names from mledoze/countries (ODbL: names, alternate spellings, demonyms, capitals, languages) and CLDR via `babel` (BSD/Unicode licence: country names in English and Bangla) |
| Demonym / nationality | French, Japanese, Bangladeshi, ফরাসি, জাপানি | the country's flag | mledoze demonyms (English, French), CLDR Bangla language names (which double as demonyms: ফরাসি) |
| Language | French, English, Bangla/Bengali, Hindi, Arabic, Spanish, ইংরেজি, আরবি | the flag of the language's home country (CLDR "likely subtags": fr -> FR, en -> US, es -> ES, pt -> BR, ar -> EG, zh -> CN, bn -> BD, hi -> IN), with an override table the owner can edit (e.g. English -> GB if preferred) | CLDR via `babel` |
| Capital / big city | Paris, Tokyo, Dhaka, London, Delhi, New York, ঢাকা | the country's flag (cities have no flag of their own in Twemoji) | mledoze capitals + a list of the 300 largest cities (GeoNames cities15000, CC-BY 4.0) |
| Currency | dollar, euro, taka, rupee, yen, টাকা | the currency's country flag only when the currency is unique to one country (taka -> BD, yen -> JP); otherwise the existing money emoji | ISO 4217 table in CLDR |
| Continents / unions | Europe, Africa, Asia, EU, UN | an emoji where one exists (🇪🇺 `1f1ea-1f1fa`, 🇺🇳 `1f1fa-1f1f3`, 🌍/🌏/🌎 by continent) | hand-made table |
| Apps / platforms (spoken as verbs too) | "Google it", "WhatsApp me" | the logo | Simple Icons aliases |

Not in this phase (written down so it is not forgotten): people (celebrities: rights and likeness issues), sports teams (logos are not in Simple Icons), universities and government bodies (no open, consistent logo set), cars by model, landmarks (the existing emoji covers some: 🗼 🗽).

### P8.2 Step by step

**Step 1 - Data, built once, stored in the repo (2-3 h)**
1.1 `pip install babel` and add `babel` to `pyproject.toml` (BSD; about 30 MB, pure Python, no conflict with anything in P7.0's table).
1.2 `scripts/build_entities.py` (re-runnable; the output is committed, the network is not needed at run time):
   * downloads the `simple-icons` npm package at a pinned version (`npm pack simple-icons@<version>`, SHA-512 from the registry checked), reads its JSON (title, slug, hex colour, aliases, guidelines URL) and SVGs; writes `design/icons/logos/<slug>.svg` with the path filled in the brand colour (white on the brand colour for very dark brands, so they read on dark themes) and `design/icons/logos.json` = {slug: {title, hex, aliases, source}};
   * downloads mledoze `countries.json` at a pinned commit (SHA-256 checked) for names, alternate spellings, demonyms, capitals, cca2;
   * reads CLDR through babel for country and language names in `en` and `bn`, likely subtags for language -> country, and currencies;
   * downloads GeoNames `cities15000` (pinned date, SHA-256 checked), keeps the 300 largest cities plus every capital and every Bangladeshi district headquarters (64), with English and (when GeoNames has it) Bangla names;
   * writes `design/icons/entities.json`: one flat list of `{"name": "france", "kind": "country", "sticker": "1f1eb-1f1f7", "label": "France", "lang": "en"}` rows for every spelling (lower-case, NFC, punctuation stripped), multi-word names kept as phrases ("united states", "new zealand", "coca cola", "south korea"), and `design/icons/entity_overrides.json` (hand-edited: English -> GB or US, local brands, words never to treat as names).
1.3 Licences: add the sources and their licences to `design/icons/LICENSE.txt` (Simple Icons CC0 data + trademark note, Twemoji CC-BY 4.0 already there, mledoze ODbL, CLDR Unicode licence, GeoNames CC-BY 4.0).
**Gate:** `entities.json` has at least 3,000 brand rows, 250 countries with an existing Twemoji flag key (every `sticker` in the file resolves through `emoji_key()`), at least 150 languages with a flag, and the Bangla rows for every country; a test asserts these counts and that no row points at a missing SVG.

**Step 2 - Matching names in what was said (3-4 h)**
2.1 `vt/visuals/entities.py`: loads the table once; `find(words) -> [(first_word_id, last_word_id, row)]` scans each sentence for the longest phrase first (up to 4 words; "coca cola" before "cola"), handles possessives and plurals ("Amazon's", "Indians"), Bangla case endings (ফ্রান্সের, বাংলাদেশে, জাপানের: strip the endings -এর, -র, -ে, -তে, -কে before lookup), and Banglish spellings already normalised by the glossary.
2.2 Ambiguity rules, because many brands are ordinary words (Apple, Shell, Target, Visa, Gap, Next, Zoom, Slack, Notion, Square, Meta, Line, Sprite, Dove, Amazon the river, Turkey the bird, China the porcelain, Jordan the name):
   * a brand or country whose name is a common English word (wordfreq zipf >= 4.0) counts only when the speaker said it as a name: the ASR capitalised it in the middle of a sentence, or a neighbouring word in the same sentence is from the same field (a company word: "company, app, brand, shop, order, buy, sell, stock, CEO, founded, website"; a place word: "country, visit, from, travel, people, capital, flag, government"), or it appears more than once in the video as a name;
   * a word on the "never" list in `entity_overrides.json` is never matched;
   * when a brand and a country share a name (Jordan), the field words decide; with no evidence, nothing is matched (an emoji or a word is shown as before);
   * Bangla text has no capitals: Bangla country/language names are matched without the capital rule (they are not ambiguous in Bangla), brand names in Bangla script (অ্যামাজন, গুগল) are matched through a transliteration list built from the brand titles (the Bangla keyword pipeline in `vt/visuals/terms.py` already handles Banglish spellings).
2.3 Picker integration (`picker.py`): entity hits become `Match(..., sticker=<logo-slug or flag key>, z_sticker=9.5, source="seed")` pinned to the hit's last word (like the two-word clipart), so they win over generic emoji; the same entity is not repeated in two sentences in a row (the existing `recent` rule); a sentence that names two things ("from France to Japan") gets both, the second as an `extra`.
2.4 `emoji.py`: a `logo-` prefix next to `art-` in `emoji_key`, `svg`, `label` (label = the brand title, e.g. "eBay", spelled as the brand spells it).
2.5 Tests (`tests/test_entities.py`) with expected answers, written before the code: "I sell on Amazon and eBay" -> amazon + ebay logos; "the Amazon rainforest" -> no logo; "I ate an apple" -> no logo, "Apple released a new phone" -> Apple logo; "Paris is the capital of France" -> French flag once; "she speaks French" -> French flag; "আমি ফ্রান্সে থাকি" -> French flag; "ইংরেজি শিখুন" -> the English-language flag from the override table; "bKash and Nagad" -> the two local badges; "Turkey is a country" -> Turkish flag, "we ate turkey" -> nothing; "United States" -> US flag on "States", not "United" alone; a sentence with no names -> exactly the picks of today (regression on the reference projects' picks).
**Gate:** all expected answers pass; the picks of the reference project and the three QA projects are unchanged except where a name was actually spoken (diff printed and checked by hand once).

**Step 3 - Drawing them well (2 h)**
3.1 A `logo` look for stickers with a `logo-` key: the logo on a white rounded tile with a soft shadow (logos are designed for white backgrounds; a dark-theme tile stays white), its title below in the theme's label style; flags keep the emoji look.
3.2 Contrast: the tile guarantees the logo's own colour reads (no need to recolour trademarks); the label goes through the P6.7 contrast rules.
3.3 People rule (P5, `vt/people.py`) applies unchanged: a logo or flag over a speaker goes in the free rectangle or is dropped.
3.4 Emoji videos (`kind: emoji`) and stick videos may use logos and flags as their stickers too (they are pictures of things, which those modes are for).
**Gate:** contact sheets of a test video naming 10 brands and 10 countries in 9:16 and 16:9 show every logo sharp (SVG), on its tile, readable; `e2e/contrast.mjs` stays green; the people check of `scripts/qa_aroll.py` stays at 0 % overlap.

**Step 4 - Editor and AI planners (1-2 h)**
4.1 Inspector: a sticker's picker gets a "Logos and flags" tab with search (by brand, country, language, city); `GET /api/entities?q=` returns matches with their SVG.
4.2 The AI script prompt (`vt/script/prompt.py`) and the MCP catalogue tell Claude/Ollama that `logo-<slug>` and flag emoji exist and when to use them (only for names actually spoken); the validator rejects a `logo-` key that is not in the table.
4.3 MCP tool `search_icons` also searches logos and flags.
**Gate:** an e2e step (in `e2e/editor.mjs`) finds "eBay" in the picker and puts it on a scene; a script submitted with an unknown `logo-xyz` is refused with a clear error.

**Step 5 - Real check and record (1 h)**
5.1 `scripts/qa_entities.py`: a script-to-video project whose text names brands, countries, languages and cities in English and Bangla (Kokoro / Edge voices), rendered in both shapes; it checks that every named thing got its picture at the time it was said (from `data.json` and frames) and nothing was pictured that was not said; plus the owner's talking-head video, where "Amazon" and "eBay" must now show their logos (not the superhero emoji).
5.2 Update this section with the counts, the numbers and what is still missing.
**Gate:** `qa_entities.py` prints "no problems found"; the owner's video shows the Amazon and eBay logos where they are said.

**Estimate: 9-12 working hours.** Order relative to Phase 7: Phase 8 does not touch the environment except adding `babel`, so it can run before or after Phase 7; doing Phase 7 first avoids adding a dependency to an environment that is about to be rebuilt.

---

## Phase 7 plan (2026-10-23): one environment, one product

Owner: "having two venvs is not good; eventually this ships as a single product". Everything below was measured on this machine on 2026-10-23 before writing it; estimates are working hours for one agent with this repo, including the testing each step demands. Each step ends with a **gate**: a command whose output must be exactly as stated before the next step starts. If a gate fails, fix it inside that step; do not carry a failure forward.

### P7.0 Facts (measured, not assumed)

| | `.venv` (the app) | `.venv-voice` (cloning only) |
|---|---|---|
| size on disk | 5.4 GB | 5.5 GB (mostly a second copy of torch) |
| numpy | 2.4.6 | 1.26.4 (pinned `<2` by chatterbox-tts) |
| transformers | 5.20.2 | 5.2.0 (pinned `==5.2.0`) |
| torch | 2.6.0+cu124 | 2.6.0+cu124 (forced back from the CPU build) |
| extra pins | | librosa 0.11.0, diffusers 0.29.0, gradio 6.8.0, safetensors 0.5.3, pykakasi, spacy-pkuseg, s3tokenizer, conformer |

* The two cannot be merged by installing chatterbox-tts into `.venv`: its pins (`numpy<2`, `transformers==5.2.0`, `safetensors==0.5.3`) would downgrade packages the app uses (AST sound tagger, MMS voice, VLM code, faster-whisper's ctranslate2 wheels built against numpy 2).
* **Chatterbox Turbo exists as ONNX** (ResembleAI/chatterbox-turbo-ONNX, MIT, pinned commit `d21799bd...`): 9 files, about 1.10 GB (language model 368 MB, speech encoder 355 MB, conditional decoder 327 MB, embed tokens 67 MB, tokenizer 3.5 MB). Concat runs exactly this bundle with ONNX Runtime; its Rust implementation (`concat-speech/src/chatterbox.rs`, about 600 lines of logic + 500 of tests: reference encoding, autoregressive token loop with repetition penalty and nucleus sampling, chunking of long text, decoding to 24 kHz, loudness normalisation) is the reference to port.
* `.venv` has `onnxruntime 1.31.0` **CPU only** (providers: Azure, CPU). `kokoro-onnx` pulls the CPU `onnxruntime` package; the GPU wheel is `onnxruntime-gpu`; both install the same `onnxruntime` module and **must not both be installed**.
* faster-whisper on the GPU fails in `.venv` with `cublas64_12.dll not found` (seen while testing on 2026-10-23); the app silently uses the CPU or the 4050's torch path elsewhere. The CUDA 12 runtime DLLs are not shipped in the venv.
* Other things a user currently has to have: Node + the HyperFrames renderer packages (`renderer/node_modules`), a Chrome (downloaded by HyperFrames), ffmpeg/ffprobe (found by `find_tool`), the built Studio (`studio/dist`), optional Ollama (separate server on the LAN), optional Concat (`tools/concat`, 314 MB), models downloaded on first use into `models/` (Whisper, AST, Kokoro, IS-Net, cloning).
* `pyproject.toml` pins `requires-python >=3.11,<3.12`; there is **no lock file** (`uv.lock` absent), so two installs on two days can differ.

### P7.1 Decision

1. **One Python environment.** Voice cloning moves from PyTorch Chatterbox (separate env) to **Chatterbox Turbo ONNX** run with ONNX Runtime inside the app's own environment, ported from Concat's Rust code. `.venv-voice` and `scripts/setup_voice.ps1` are deleted at the end.
2. **One ONNX Runtime:** `onnxruntime-gpu` (CUDA 12) is the only ONNX Runtime in the environment; `kokoro-onnx` is installed without its own dependency on the CPU package (`--no-deps` via an override in the lock). The code asks for `CUDAExecutionProvider` and falls back to CPU, so machines without NVIDIA still work.
3. **One lock file** (`uv.lock`, uv) for every Python dependency, CUDA runtime wheels included (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12` for faster-whisper and onnxruntime-gpu), so the GPU works without a separate CUDA install.
4. **One product folder** that contains its own Python (python-build-standalone 3.11, no system Python), the locked packages, ffmpeg, Node + the renderer, Chrome, the built Studio, and Concat as an optional part; models are still downloaded on first use (they are 4-5 GB together and most users need only some).
5. Not changed by this phase: features, the API, the Studio. This phase only changes how the app is installed and run. Every existing test suite must stay green at every gate.

### P7.2 Step by step

**Step 1 - Freeze the current state (0.5 h)**
1.1 Record the working baseline: `pytest -m "not slow"` count and result, `pytest -m slow` result, each e2e suite's pass count, and `scripts/qa_voices.py` output (clone similarity 0.99, Kokoro 0.80, the three key phrases heard). Write them into this section as "baseline".
1.2 Copy `.venv-voice`'s `pip freeze` and `.venv`'s `pip freeze` into `build/freeze-2026-10-23-{app,voice}.txt` (kept for comparison, not shipped).
1.3 Keep three reference outputs of the current PyTorch clone for the parity test of step 3: the same three sentences, same 12 s reference voice, saved as `tests/fixtures/clone_ref/{1,2,3}.wav` with the text next to them (`.txt`). The reference voice itself is the public-domain LibriVox clip already used (not the owner's voice).
**Gate:** the baseline numbers are written down; the three WAVs exist and are 2-8 s long each.

**Step 2 - One ONNX Runtime with the GPU (1.5 h)**
2.1 In `.venv`: `pip uninstall -y onnxruntime` then `pip install onnxruntime-gpu==1.22.*` (the newest release whose wheel supports CUDA 12 on Windows/Python 3.11; check the exact version on PyPI at the time and write it here).
2.2 `pip install --no-deps kokoro-onnx` again (so it does not bring the CPU wheel back); `pip install espeakng-loader phonemizer` (its real runtime needs).
2.3 Install the CUDA runtime wheels the GPU paths need: `nvidia-cublas-cu12`, `nvidia-cudnn-cu12` (versions matching onnxruntime-gpu's documented CUDA/cuDNN). Add `vt/gpu.py` with one function `add_cuda_dll_dirs()` that calls `os.add_dll_directory()` for each `site-packages/nvidia/*/bin` folder that exists; call it at the top of `vt/__init__.py` (Windows only, no-op elsewhere).
2.4 Change the three ONNX users to ask for the GPU and fall back: `vt/cutout.py` (already does), `vt/tts.py` (Kokoro: pass `providers` when the class accepts it, otherwise create the session ourselves), the new cloning module (step 3).
2.5 Fix faster-whisper's GPU path: `vt/stages/asr.py` must call `add_cuda_dll_dirs()` before loading CTranslate2, then try `device="cuda"`, and fall back to CPU int8 with a note in the job log if it fails (today it fails silently).
2.6 Tests: `tests/test_gpu.py`: `onnxruntime.get_available_providers()` contains `CUDAExecutionProvider` when `nvidia-smi` exists (skip otherwise); a cutout run reports the provider it used; faster-whisper `base.en` loads on `cuda` (skip without GPU). Re-run `tests/test_tts.py`, `tests/test_cutout.py` including the slow parts.
**Gate:** `python -c "import onnxruntime as o; print(o.get_available_providers())"` lists `CUDAExecutionProvider`; `pip list` shows exactly one of onnxruntime / onnxruntime-gpu; the whole `pytest -m "not slow"` is as in the baseline; Kokoro and cutout slow tests pass; a 30 s transcription runs on `cuda` (time it: it must be faster than the CPU time recorded in the baseline).

**Step 3 - Chatterbox Turbo in ONNX, in the app's own environment (8-12 h, the big step)**
3.1 `vt/models.py` (new): one table of downloadable models (id, file, bytes, sha256, url, licence) and one `ensure(id, progress)` that downloads to `models/<family>/`, checks size and SHA-256, and resumes with HTTP Range. Move the Kokoro and IS-Net download code onto it (they already check sizes). Add the 9 Chatterbox Turbo files from Concat's `manifest.toml` (urls pinned to commit `d21799bd0354adb85e348b8a0442a8405110a2cf`); take the SHA-256 values from the release's `manifest.json` or compute them once and pin them.
3.2 `vt/clone_onnx.py` (new), a straight port of `chatterbox.rs`, function by function, keeping its names so the two can be compared: `punc_norm`, `chunks`, `expected_tokens`, `norm_loudness`, `Rng` (same seeded generator, so a seed gives the same sampling), `sample_token` (temperature, top-p, repetition penalty exactly as in Rust), `next_token`, `spoken`, `with_prompt`, `Engine.load` (four `InferenceSession`s, CUDA then CPU), `Engine.hear` (reference audio -> speaker embedding, prompt tokens and features, the reference resampled to what the speech encoder expects), `Engine.write` (the autoregressive loop over the language model with its KV cache inputs and outputs, stop token, max tokens from `expected_tokens`), `Engine.decode` (tokens + voice -> 24 kHz samples), `Engine.speak(text, reference) -> samples` (chunks, joins with the same pause, loudness normalised). The tokenizer is `tokenizers` (already a transformers dependency) loading `tokenizer.json`.
3.3 Port Concat's own unit tests for these functions (`the_penalty_turns_a_written_token_away_and_the_best_is_picked`, `a_sample_stays_inside_the_nucleus`, `the_generator_is_uniform_and_repeatable`, `a_recording_is_brought_to_the_target_loudness`, the chunking and punctuation tests) into `tests/test_clone_onnx.py`, with the same inputs and expected outputs as in the Rust file.
3.4 Inspect the four ONNX graphs once (`onnx.load(...).graph.input/output` names, shapes, dtypes) and write them as a comment table at the top of `clone_onnx.py`; any name the Rust code uses that is not in the graph is a bug in the port, not in the model.
3.5 `vt/voices.py`: `say()` calls `clone_onnx.Engine` in-process (the engine is loaded once and kept, guarded by a lock), no subprocess, no `voice_python()`, no `VT_VOICE_PYTHON`, no `voice_worker.py`. `available()` = the model files are present or can be downloaded. Keep the public API (`list_voices`, `add_voice`, `say`, `remove_voice`) and the consent rule unchanged, so the endpoints and the Studio do not change.
3.6 Parity and quality checks, all automatic, against the three reference WAVs from step 1.3: (a) speech recognition (faster-whisper base.en) hears every key phrase of each sentence; (b) WavLM speaker similarity to the 12 s reference voice is >= 0.95 and higher than Kokoro's by >= 0.1 (baseline: 0.99 vs 0.80); (c) length within 25 % of the PyTorch output for the same sentence; (d) no clipping (peak < 0.99), loudness within 2 dB of the PyTorch output; (e) speed on the RTX 4050: real-time factor measured and written down (baseline PyTorch: about 6 s of speech in 37 s cold, faster warm); CPU-only run measured too.
3.7 `scripts/qa_voices.py` unchanged must still print "no problems found" through the Studio API.
**Gate:** `tests/test_clone_onnx.py` and `tests/test_voices.py` pass; 3.6 (a)-(d) pass for all three sentences; `qa_voices.py` passes; the numbers of 3.6 (e) are recorded here. If (b) fails (the Turbo model is a different model than the one used so far, so the voice may be a little less close), record the numbers and decide with the owner before deleting the PyTorch path; do not fake a pass by lowering the threshold silently.

**Step 4 - Remove the second environment (0.5 h)**
4.1 Delete `vt/voice_worker.py`, the subprocess code in `vt/voices.py`, `scripts/setup_voice.ps1`, the `voice_python` setting and the README "three commands" text; update README (cloning works out of the box; model about 1.1 GB on first use).
4.2 Delete `.venv-voice` (5.5 GB) and `%TEMP%\voicevenv` (the spike copy).
4.3 `grep -r "voice_python\|VT_VOICE_PYTHON\|voice_worker\|venv-voice" vt studio scripts tests README.md plan.md` returns only history lines in plan.md.
**Gate:** the grep is clean; the full `pytest` (slow included) passes; `qa_voices.py` passes with only `.venv` present.

**Step 5 - Lock every dependency (2 h)**
5.1 Move the project to `uv`: `uv lock` from `pyproject.toml`, with: `onnxruntime-gpu` in the main dependencies; `kokoro-onnx` with an override that drops its `onnxruntime` requirement (`[tool.uv] override-dependencies`); torch from the PyTorch CUDA 12.4 index (`[[tool.uv.index]]` + `[tool.uv.sources] torch = { index = "pytorch-cu124" }`), so a fresh install gets the GPU build without a manual reinstall; `yt-dlp`, `transformers`, `faster-whisper`, `tokenizers`, `soundfile`, `scipy`, `opencv-python-headless`, the `nvidia-*-cu12` runtime wheels.
5.2 Split extras that are truly optional so the default install stays smaller: `[project.optional-dependencies] dev = [pytest, playwright-core is Node, ruff]`. Everything a user needs is in the main list (no "install this extra to get feature X" for shipped features).
5.3 Rebuild the environment from the lock only: `uv sync --frozen` into a fresh `.venv`, run the whole test suite and the e2e suites.
**Gate:** `uv.lock` committed to the repo folder; a fresh `uv sync --frozen` + `pytest` + all e2e pass; `uv pip list` has no `onnxruntime` CPU package and torch reports `+cu124`.

**Step 6 - One self-contained product folder (4-6 h)**
6.1 `build/make_dist.py`, which produces `dist/VideoTool/` from nothing but the repo and the lock:
   * `python/`: python-build-standalone CPython 3.11 (install_only build, Windows x86_64; SHA-256 pinned in the script);
   * `python/Lib/site-packages`: `uv pip install --python python/python.exe --frozen -r` from the lock (no venv inside the product: one interpreter, one site-packages);
   * `app/`: the `vt` package, `design/`, `assets/`, `renderer/` (runtime + `node_modules` installed with `npm ci --omit=dev`), `studio/dist` (built with `npm ci && npm run build`);
   * `bin/`: ffmpeg + ffprobe (a pinned build, SHA-256 checked), Node (the official Windows zip, pinned version), and the Chrome that HyperFrames uses, downloaded into `bin/chrome` at build time so no download happens on the user's first render;
   * `tools/concat/`: optional, only when `--with-concat` is given (314 MB, AGPL-3.0 with its LICENSE and THIRD_PARTY_NOTICES copied into `licenses/`);
   * `VideoTool.cmd`: sets `PYTHONHOME`, `PATH` (bin, python, the nvidia DLL folders), `VT_DATA=%LOCALAPPDATA%\VideoTool` (user data outside the program folder: projects, models, voices, settings), then runs `python -m vt.cli studio`.
6.2 Path audit: `vt/paths.py` and `find_tool` must find ffmpeg/Node/Chrome in `bin/` first, then on PATH; `renderer/` must not assume a global `npx`. Add `tests/test_paths_dist.py` that builds a fake product layout in a temp folder and checks every lookup.
6.3 Licences: `licenses/` folder with the licence of every shipped binary and every model the app downloads (Whisper MIT, AST BSD-3, Kokoro Apache-2.0, IS-Net Apache-2.0, Chatterbox MIT, ffmpeg (state which build: LGPL or GPL), Node MIT, Chromium BSD, Concat AGPL-3.0 when included). The owner said licences are not a concern; this is still written down so it is known what is shipped.
**Gate:** on this machine, rename `.venv` away and take `ffmpeg`, `node` and `python` off PATH in a fresh terminal; `dist\VideoTool\VideoTool.cmd` starts the Studio; the smoke list passes through the UI and the API: make a video from `samples/audio/bn_plain.mp3`, render 9:16, add a voice and make a script video in it, cut out a picture, listen for sounds, import the owner's talking-head video and render it; `scripts/qa_analyze.py` on the renders reports no problems.

**Step 7 - Installer and first run (3-4 h)**
7.1 One installer (Inno Setup script `build/installer.iss`) that copies `dist/VideoTool` to `%LOCALAPPDATA%\Programs\VideoTool` (no admin rights), makes a Start menu entry and an uninstaller that removes the program but asks before deleting `%LOCALAPPDATA%\VideoTool` (projects).
7.2 First-run page in the Studio (`/welcome`): GPU found or not, disk space, which models are present, a "download everything now" button (sizes listed: Whisper large-v3 3 GB, Bangla model, AST 350 MB, Kokoro 120 MB, IS-Net 180 MB, cloning 1.1 GB) and the option to let them download when first needed (the default).
7.3 The Electron shell (`desktop/main.js`) is not used for this phase (the owner said "forget Electron for now"); the product opens the Studio in the default browser. Revisit Electron only if the owner asks.
**Gate:** on a clean Windows user account on this machine (or a Windows VM without Python, Node, ffmpeg, CUDA toolkit): install, run the smoke list of step 6, uninstall; nothing left in `Program Files`, the user's projects kept unless the owner chose to delete them.

**Step 8 - Record and hand over (0.5 h)**
8.1 Update this section with the measured numbers of every gate, the final download size of the installer, the installed size, and the cold-start time of the Studio.
8.2 README: install from the installer; developer setup is `uv sync --frozen` + `npm ci` in `renderer` and `studio`.

### P7.4 Status

**Step 1 done (2026-10-23).** Baseline: `pytest -m "not slow"` = 595 tests, all pass (655 collected in all, 60 slow). E2E on the QA server: editor 24/24, flows 26/26, timeline 23/23 (it failed 3 once in a full run from leftover state; two clean reruns passed), timeline3 13/13, script 11/11, layers 20/20, layers_media 11/11, contrast 14/14, retention 8/8, sounds 5/5, context 7/7, a11y clean. `qa_voices.py`: clone 0.99 vs Kokoro 0.80 speaker similarity, key phrases heard. Freezes: `build/freeze-2026-10-23-{app,voice}.txt`. Reference clones of the PyTorch model (12 s public reference voice `tests/fixtures/clone_ref/reference_12s.wav`): `1.wav` 3.5 s, `2.wav` 3.2 s, `3.wav` 2.8 s with their texts; the first took 75 s cold, the next two 16 s and 11 s warm (real-time factor about 3.5-5 on the 4050 with PyTorch).

**Step 2 done (2026-10-23).** `onnxruntime-gpu 1.31.0` is the only ONNX Runtime (`onnxruntime` removed; providers: TensorRT, CUDA, CPU). Finding that changes the plan: the separate `nvidia-*-cu12` wheels are **not needed** - torch's own `lib` folder already holds cuBLAS 12 / cuDNN 9, and ONNX Runtime, CTranslate2 and torch all run on it in one process (`tests/test_gpu.py`, 3 tests). They were installed to try and removed again (one set of CUDA libraries, 1 GB less). `vt/gpu.py` (`prepare()`, `onnx_providers()`) replaces the private DLL code in `asr.py`; cutout asks it for CUDA-then-CPU (TensorRT is never used: it builds engines on first run); Kokoro is pinned to the CPU provider (its 8-bit model is made for it). Faster-whisper falls back to CPU with a progress note when the GPU cannot be used. Measured: 30 s of Bangla with `bn-medium`: **GPU 5.2 s warm (8.9 s cold) vs CPU 30.7 s**. IS-Net 1024x1024 on CUDA: 0.10 s. `pytest -m "not slow"` all pass; slow tts/cutout/sounds pass.

**Step 3 done (2026-10-23).** `vt/models.py` (one table of 3 models: Chatterbox Turbo 9 files / 1.12 GB pinned to a commit with SHA-256 per file, IS-Net, Kokoro; Range-resume, size + hash check, `.part` then rename, cancel; cutout and Kokoro moved onto it; `tests/test_models.py` 5). `vt/clone_onnx.py` is the port of `chatterbox.rs` with the same function names (`punc_norm`, `chunks`, `expected_tokens`, `norm_loudness`, `Rng` xorshift64*, `next_token`, `sample_token`, `spoken`, `with_prompt`, `Engine.load/hear/write/decode/speak`); `tests/test_clone_onnx.py` (12) holds Concat's unit tests with the same inputs and outputs, a check that the four real graphs have the names the code feeds, and a slow end-to-end test with the real model (same seed gives the same length; too-short reference, empty text, cancel are refused). The real bundle downloaded through `ensure()` in 3 min and every hash matched. `vt/voices.py` now calls the engine in-process (loaded once under a lock; model fetched on first use; the public API and the consent rule unchanged; output brought to -19 dB RMS with a 0.95 peak because the ONNX model writes about -26 dB while the PyTorch path peaked at 0.99-1.0).
Gate 3.6 (`scripts/qa_clone_onnx.py`, three sentences against the PyTorch references, 12 s public reference voice): (a) speech recognition hears every sentence word for word; (b) speaker similarity **0.96 / 0.97 / 0.97** (PyTorch 0.99, Kokoro 0.80) - slightly less close than the PyTorch model as the plan warned, still well above the 0.95 gate; (c) lengths 3.2 / 3.2 / 3.0 s vs 3.5 / 3.2 / 2.8 s; (d) no clipping (peaks 0.73-0.89); (e) speed: **GPU (RTX 4050) 0.7-1.0x real time (faster than speaking), CPU 13.6x real time (about 40 s per 3 s sentence)**, against PyTorch on the same GPU at 3.5-5x slower than real time. Model load 15 s. Through the Studio API `scripts/qa_voices.py`: clone 0.98 vs Kokoro 0.80, all key phrases heard, "no problems found". Not judged by ear (no one listened): the owner should listen to `qa_out_clone_gpu/*.wav`.
**Step 4 done.** `vt/voice_worker.py`, `scripts/setup_voice.ps1`, the subprocess code, the `voice_python` setting / `VT_VOICE_PYTHON` / `VT_VOICE_WORKER` and the `.venv-voice` folder (5.5 GB) and the temp spike copy are deleted; README and the Settings banner no longer talk about a second environment; the grep over `vt scripts tests studio/src README.md` is clean. Full `pytest -m "not slow"` passes and the slow voice/tts/clone tests pass with only `.venv` present.

### P7.3 Risks, and what happens if they bite

* **The ONNX port gives a worse voice than the PyTorch model** (Turbo is a different, smaller model). Measured in step 3.6 (b). If it is clearly worse, the fallback is *not* a second venv: it is installing `chatterbox-tts --no-deps` plus only its real runtime needs (s3tokenizer, conformer, librosa, diffusers without gradio) into the one environment and testing that numpy 2 / transformers 5.20 work with it; if they do not, the owner decides between the Turbo quality and the extra 5 GB.
* **onnxruntime-gpu and torch disagree on cuDNN versions** (both load cuDNN DLLs into one process). Mitigation: torch's own CUDA libraries load first in the same process; check with a test that loads torch, runs the AST tagger, then runs an ONNX session on CUDA in the same process (`tests/test_gpu.py`). If they clash, ONNX sessions fall back to CPU for cutout and Kokoro (small models) and only the cloning engine needs the GPU.
* **Package size.** Expected: about 6-7 GB installed (torch CUDA about 2.5 GB, nvidia runtime wheels about 1 GB, Chrome about 300 MB, Node + renderer about 150 MB, ffmpeg about 150 MB, Python packages the rest) before models. Measure in step 6 instead of trusting this number. A "CPU edition" without torch CUDA and nvidia wheels is possible later but is not part of this phase.
* **The owner's real projects** live in the repo's `projects/` today; step 6 moves user data to `%LOCALAPPDATA%\VideoTool`. Add a one-time migration (copy, then leave the old folder alone) and test it on a copy of the real folder before running it on the real one.

**Total estimate: 20-27 working hours**, most of it step 3 (the ONNX port and its parity checks). Nothing in steps 2-8 starts before the gate of the previous step is met.

---

## Phase 6 plan (2026-10-23): a real multi-track editor, Concat's features, sound-aware visuals, readable colours, live transcript

Owner's request: take everything useful from Concat (https://github.com/jub0t/concat), fix the editing gaps (non-speech audio such as laughing babies gets no matching picture; text colours that do not stand out, e.g. green on white; no transcript panel to paste corrections; no way to add layers to the timeline), use Whisper, and migrate to Rust if that is the right call. Phase 6 comes **before** the A-roll work of Phase 5 except P5.1 (dragging), because Phase 5 needs the multi-track timeline built here.

### P6.0 What Concat is (read from its source, 2026-10-23)

* A native desktop editor ("open-source CapCut"), **Rust** workspace, Slint UI, wgpu GPU compositor, FFmpeg I/O. Crates: `concat-core` (time, frames, timeline model), `concat-project` (document, operations, undo), `concat-render`/`concat-export` (compositor, export H.264/HEVC/AV1 up to 4K60 10-bit), `concat-effects` (~100 effects, filters, transitions from manifests), `concat-text` (titles, rustybuzz shaping, ships Noto Sans Bengali), `concat-speech` (whisper.cpp captions, Kokoro TTS, Chatterbox Turbo voice cloning via ONNX Runtime), `concat-vision` (person/object cutout, brush-corrected masks, upscaler), `concat-api` + `concat-server` + `concat-mcp` (one JSON-RPC/MCP API: projects, edits, media, effects, exports, frames; `concat --mcp headless` runs the engine with no window).
* Models it downloads (`models/manifest.toml`, pinned by sha256): cutout-person, cutout-object, brush encoder/decoder, enhance-upscale, Kokoro multi-lang v1.0 (int8 and fp), Pocket-TTS, Chatterbox Turbo (4 ONNX parts), Whisper tiny … large.
* **Licence: AGPL-3.0-or-later, plus a CLA and a trademark policy.** Copying its code into Video Tool makes Video Tool AGPL (source must be offered to anyone who uses it, including over a network) and we may not call our product "Concat". The owner said licences are not a concern, so this is recorded, not a blocker. Using its downloaded models is governed by each model's own licence (listed in its `THIRD_PARTY_NOTICES.md`), not by AGPL.

### P6.1 Decision: no rewrite in Rust; Concat's engine joins as a sidecar, its features are added where they belong

**Decision.** Keep Python (AI, pipeline, server) + React (Studio) + HyperFrames (motion graphics). Do **not** port the app to Rust. Run **Concat's engine as a sidecar** (`concat --mcp headless` / `concat-server` JSON-RPC) for what a GPU video engine does better than us, and bring Concat's *features* (not its UI) into the Studio.

**Why not rewrite in Rust:**
1. What makes Video Tool different is the AI director (planning, scripts, roles, stick figures, emoji, validation, Ollama/Claude/MCP), ~40 HTML motion-graphic components with correct Bangla shaping, and the QA harness. That is ~25k lines of Python/TS/JS with tests; a Rust port would take months and reproduce, not add.
2. Concat already *is* the Rust engine, with an API built for agents. Calling it gives us its compositor, effects, cutout and fast export without owning that code.
3. The Python ML ecosystem (faster-whisper, VLMs, embeddings, sound tagging) is where the "no human intervention" brain lives.

**What would change this decision:** if the spike (P6.9 step 1) shows Concat's headless engine cannot be driven reliably on Windows, or cannot composite our graphics layers, we keep our own ffmpeg compositor (P6.3 fallback) and still take the models (Kokoro, Chatterbox, cutout) through onnxruntime in Python. Rust is never required for any feature in this plan.

**Whisper:** we already use Whisper — `faster-whisper` (CTranslate2, GPU) with large-v3 and a Bangla fine-tune (`vt/stages/asr.py`), per-word timestamps, merging, glossary hotwords. This is the same family Concat runs through whisper.cpp, usually more accurate for Bangla. Keep it. Add: model size choice in Settings (tiny … large-v3, plus the Bangla model) and a "fast captions" mode with a small model for long files; optionally whisper.cpp for CPU-only machines.

### P6.1b Concat sidecar spike (2026-10-23, done)

The Windows MSI (v0.2.8, SHA-256 checked against the release's SHA256SUMS) is unpacked without installing (`msiexec /a`) and `concat.exe --mcp headless` answers MCP over stdio in 0.3 s with **42 tools** (project, media, clips, tracks, titles, captions, keyframes, effects, templates, export). `scripts/spike_concat.py` (client in `vt/concat_client.py`) built a project, imported a 1080p video and a transparent PNG, put the video on the base lane, the PNG on a lane above (scaled and offset) and a title over both, and exported: **956 frames of 1080p in 34 s (about 28 fps), H.264 + AAC, audio kept; the red disc of the PNG appeared exactly at the placed position and only after its start time, the title was visible.** Verdict: the engine can be driven reliably on this machine, so the compositor interface in P6.3 can use it. **Not done:** the `Compositor` interface itself (Video Tool's own layers still render through HyperFrames + ffmpeg; Concat is not used by any export yet), an alpha-video hand-off from HyperFrames, effects/transitions from Concat's catalogue. The unpacked engine sits in `tools/concat` (314 MB, AGPL-3.0 with its own LICENSE and THIRD_PARTY_NOTICES); `tests/test_concat_client.py` runs the real engine when it is there.

### P6.2 Multi-track timeline (the core gap)

**Status 2026-10-23: first version built and tested ("layers").** What exists: `layers.json` (tracks, top layer first; clips of type text / media / audio; strict validation with every problem listed; one-step history; overlap on a track refused) in `vt/layers.py`; endpoints `GET/PUT /api/projects/{id}/layers`, `/layers/undo|redo`, `/sounds` (upload, list, delete; audio files are kept apart from the picture bin so planners never see them; catalogue music can be added); a video keeps its own sound as `media/<id>.audio.m4a`. Rendering: visual layers are drawn by `renderer/runtime/vt-layers.js` above the scenes and below captions (text with optional plate, pictures, video clips that follow the timeline; fades); audio layers and video sounds are mixed into the export (`mix_and_mux(layer_audio=...)`, delay, trim, fades, volume) and played in step with the voice in the Studio preview. Editor: visual tracks above Scenes, sound tracks below Voice; add track, add text at the playhead, **Add to timeline** from the media bin (pictures, video, sounds); move (also between tracks of the same kind), trim both edges (a sound keeps its place in the file), split at the playhead (Ctrl+B), duplicate, delete, right-click menu, per-track menu (rename, hide, mute, lock, reorder, delete), inspector (text, size, colours, plate, position, size, opacity, fit, fades, volume), snapping, and one undo history shared with scene and voice edits. Tests: `tests/test_layers.py` (validation, history, composition, real audio mix), `scripts/qa_layers.py` (a real export: picture, text plate and sound found where placed), `e2e/layers.mjs` 17/17, `e2e/layers_media.mjs` 11/11. **Added later the same day:** copy and paste of a layer clip (Ctrl+C / Ctrl+V at the playhead) and a motion preset per picture/text clip (slow zoom in/out, slide in from any side, gentle pulse; a start and an end value animated by the renderer). **Not done:** free keyframes and a curve lane, blend modes, speed and freeze frame, multi-select and group move, magnetic mode, drag from the bin onto a lane (buttons are used instead), waveform drawn in sound clips, moving the generated scenes themselves onto tracks (the scenes are still one fixed lane), alpha-video layers for the compositor, Concat's engine.

Today the timeline shows fixed lanes (Scenes, Elements, Actions, Words, Voice) and you cannot add a layer. Replace the scene-centric model with a **track model** that the planners also write:

* **Document:** `timeline.json` per project: `tracks: [{id, kind: video|graphics|text|audio|captions, name, locked, muted, hidden, height}]`, `clips: [{id, track, start, dur, source: {media|scene|tts|music|sfx|generated}, in, speed, volume, fades, keyframes: {x,y,scale,rotation,opacity,volume,crop,effect params}, effects:[], transition_in}]`. Modelled on `concat-core/timeline.rs` and `concat-project/model.rs` (read for semantics, written fresh in Python/TS so the doc stays ours). Undo as operations (Concat's `commands/` pattern) instead of whole-plan snapshots.
* **Compatibility:** the existing scene plan becomes the "Graphics" track (one clip per scene, still edited in the inspector); voice → "Voice" audio track; music → "Music"; captions → "Captions" track; stick/emoji unchanged inside their scene clips. Old projects are converted on open, losslessly (test).
* **Editor:** add / remove / rename / reorder / lock / mute / hide tracks; drop media from the bin onto any track or onto empty space below (creates a track); move clips between tracks; overlapping clips on one track are refused (or ripple, "magnetic" option like Concat); split, trim (live edges from P5.1), ripple delete, slip, speed, freeze frame, fades by dragging clip corners, keyframes on a curve lane, volume rubber band on audio clips; multi-select and group move; copy/paste; snapping to edges, playhead, markers, words.
* **Preview:** the composition renders all video/graphics tracks top to bottom with blend modes and opacity; audio tracks mixed live in WebAudio for preview, and by ffmpeg at export.
* **API/MCP:** the same operations as endpoints and MCP tools, so Claude and the local AI edit tracks exactly like the user (Concat's "one dispatcher" idea).

### P6.3 Rendering with layers

* Graphics, captions and text tracks render through HyperFrames as before, but per track into **alpha video** (VP9 `yuva420p` or ProRes 4444) when a track sits above real video; when the graphics are the whole picture nothing changes.
* Video tracks (A-roll, B-roll, media, cutouts) and the final composite go to **Concat's engine** if the sidecar is installed (GPU, effects, transitions, export codecs), else to our **ffmpeg filter graph** (`overlay`, `scale`, `crop`, `fade`, `xfade`, keyframes as expressions). Both are behind one `Compositor` interface with the same test suite (frame comparisons on fixtures).
* Export keeps today's checks (H.264 High, yuv420p, AAC 48 kHz, faststart, −14 LUFS) and adds HEVC/AV1 and 4K/60 when Concat is the engine.

### P6.4 Voices: TTS and voice cloning

**Status 2026-10-23: built and verified on real audio.** (1) **Kokoro** (`kokoro-onnx`, int8 model about 92 MB + voice bank 28 MB, downloaded on first use into the models folder with a size check) is an offline engine for English and Hindi in the text-to-speech list (`vt/tts.py`); a real script became a video whose spoken words matched the script exactly. Bangla is not supported by Kokoro and keeps the online Edge voices and the offline MMS voice. (2) **Voice cloning with Chatterbox** (MIT) runs in its own Python (`.venv-voice`, created by `scripts/setup_voice.ps1`, found automatically or through `VT_VOICE_PYTHON`) behind a helper process (`vt/voice_worker.py`, one JSON line per request; library log lines cannot break it). Voices are saved in `voices/<id>/` only with an explicit consent flag (refused otherwise, with a reason; too short, silent or clipped recordings are refused; the best 20 s is kept); API `GET/POST /api/my-voices`, `DELETE`, `GET .../sample`; Settings > My own voice (record or upload, consent checkbox, preview, delete); the engine "My own voice" appears in the New page's script tab. **Speaker check on a real run** (WavLM speaker verification against the 12 s reference recording): clone 0.99, a stock Kokoro female voice 0.80, a different real speaker 0.71, the same speaker on another minute 0.85; the clone said every word of the script correctly (checked with speech recognition). Speed on an RTX 4050: about 6 s of speech in 37 s the first time (model load included), about 1.2 s of speech per second of work afterwards on short sentences. (3) **Say it again in my voice**: `POST /api/projects/{id}/voice/overdub` speaks new text in the cloned voice, adds it as a sound ("My voice" audio track, never overlapping), and mutes the original range; button on each sentence in the Script tab; everything stays undoable. Tests: `tests/test_voices.py` (consent, refusals, trimming, protocol with a stand-in helper, errors, overdub, API), `tests/test_tts.py` (Kokoro incl. a slow real synthesis), `scripts/qa_voices.py` (real run). **Not done / unverified:** the cloned voice was not judged by ear; English only (Chatterbox's multilingual model was not tried, so no Bangla cloning); Concat's Chatterbox-Turbo ONNX route was not used (the PyTorch route is simpler and fast enough here); no word-level splice into the original recording (the overdub replaces a whole range, and the captions still show the old words until corrected in the Script tab); the voice helper keeps about 4 GB of GPU memory while the Studio runs after first use.

* **Kokoro** (multi-language, int8) and **Chatterbox Turbo** (cloning from a few seconds) run in Python through onnxruntime, models downloaded on first use with sha256 pins (same table approach as Concat's `manifest.toml`).
* Uses: script-to-video with a chosen or cloned voice; **fix a word in the voice** (re-say one phrase in the speaker's cloned voice and splice it, with crossfade and loudness match); fill a removed mistake; dub to another language.
* **Bangla:** Kokoro and Chatterbox Turbo do not cover Bangla well (to verify in the spike). Keep the current Bangla TTS path; use cloning for English/Banglish phrases only until a Bangla-capable model is validated by ear. Consent: cloning only a voice the user uploads as their own, with a checkbox stating so; no cloning from downloaded media.

### P6.5 Cutout, cleanup and effects

**Status 2026-10-23: cutout and voice cleanup built and tested; effects not done.** **Cutout** (`vt/cutout.py`): IS-Net general-use (Apache 2.0, 178 MB, downloaded on first use, size and SHA-256 checked, ONNX Runtime, GPU when available) removes the background of a picture; media bin button "Cut out" adds `<id>-cutout` (a PNG with transparency) next to the original (`POST /api/projects/{id}/media/{mid}/cutout`, a job); refused for videos (no per-frame masks) and for pictures with no clear subject. Real model checked on a synthetic subject (centre opaque, corners transparent); not judged on real portraits. **Voice cleanup** ("Clean up the voice" on the Export page, `clean_voice`): high-pass, spectral noise reduction, a gate, a presence boost, a light compressor on the voice only; measured on real speech with added hiss and hum: +13 dB speech-to-pause ratio (gate-less settings gave only +1 to +5 dB, a pure-tone test signal is useless for this), speech level kept. **Not done:** video cutout (talking head over a graphic), the person-model (RVM is GPL and needs recurrent state), mask brush correction, Concat's effects and transitions (needs the Concat sidecar), speed ramps.

* **Background removal** (cutout-person/object models via onnxruntime, or Concat engine): talking head over a graphic or B-roll (P5 "split"/"pip" layouts), stickers of people, mask correction with a brush in the inspector.
* **Voice cleanup in one switch** (Concat idea): denoise (existing), enhance, loudness level, de-ess; presets for fun voices only on request.
* **Effects and transitions:** use Concat's catalogue through the sidecar where installed; our own small set (cut, dissolve, slide, zoom, blur, colour) through ffmpeg/HTML otherwise. Planners use only cuts and dissolves by default (Phase 5 rule).

### P6.6 Sound-aware visuals (non-speech audio)

**Status 2026-10-23: built and verified on real recordings.** `vt/sounds.py`: the AudioSet Audio Spectrogram Transformer (`MIT/ast-finetuned-audioset-10-10-0.4593`, 527 sound classes, via `transformers`, GPU when present; first load ~60 s, then 22 s for a 5-minute file) listens to overlapping 3 s windows; labels are grouped into ~30 concepts (laughter, baby laughter, applause, cheering, crying, music, rain, thunder, dog, cat, birds, traffic, bell, phone ...) by *adding up* the labels of a concept (AudioSet labels are independent probabilities), with a higher bar while someone speaks and no animal sounds next to a baby's laugh; windows merge into events saved as `sounds_events.json` (output time). New pipeline stage **sounds** after cuts (never fails the video; option `sound_events: auto|off`). The planner puts the sound's emoji (with a label) in the scene showing at that moment, people sounds first, never twice, at most four elements per scene, background sounds (music, traffic, wind, typing ...) get no picture. **A recording with no speech** (the recogniser finds nothing or one stray word) becomes sound captions such as "[Baby laughing]", one sentence and one scene per sound, each scene showing that sound's emoji. Studio: a **Sounds** lane in the timeline (emoji chips, click to jump) with a button to listen to older projects; API `GET/POST /api/projects/{id}/sound-events`. Real check `scripts/qa_sounds.py` (public-domain baby laughter, CC0 applause and rain from Wikimedia Commons mixed with speech): laughter found at 12-18 s and applause at 27-34 s where they were placed, the plan shows the baby and clapping emoji there, the sound-only recording renders as three scenes (laughing, laughing, applauding). Tests: `tests/test_sounds.py`, `e2e/sounds.mjs`. **Known weaknesses:** the baby's babble before a laugh was labelled "farm animals" (shown as a cow); rain was only weakly recognised (about 1 window of 12); the AudioSet model does not know speech content, so "someone laughing while talking" depends on its score; CLAP-style free-text sounds are not supported; sounds are not yet shown as B-roll searches (the `query` field is stored for that); the AI script prompt does not see the events yet.

Problem: a clip of babies laughing, applause, music or rain gets no picture because planning reads only the transcript.

* **Sound event tagging** on every audio and A-roll track: a local audio-tagging model (PANNs CNN14 or YAMNet, AudioSet's 527 classes; CLAP for open-vocabulary "baby laughter", "crowd cheering") over 1 s windows, merged into events `{start, end, label, confidence}` stored in `sounds.json`, shown as a "Sounds" lane in the timeline.
* The narrative map (P5.4) treats non-speech events as beats: *baby laughter* → B-roll search "baby laughing" in the project/catalogue/stock (VLM-verified), else a graphic (emoji 👶😂, clipart, stick figure laughing), plus an on-screen label only if useful; *music only* → title card or visualizer; *applause* → reaction graphic; *silence with no speech* → keep or trim (existing lead-in rule).
* Videos with **no voice at all** (only sounds or music) get a plan from sounds and on-screen content (VLM captions of the A-roll) instead of failing with "no speech".
* Tests: fixtures with laughter, applause and rain (CC0 from the catalogue); the plan must contain a matching visual within 0.5 s of each event.

### P6.7 Readable colours (the green-on-white problem)

**Status 2026-10-23: built and tested** (`e2e/contrast.mjs`, 14 themes x 9 moments, every text node >= 3:1 against what is behind it). Accent colours used as text are darkened or lightened until they reach 4.5:1 against the theme's background and card (`--accent-text`, `--accent2-text` in `renderer/runtime/vt.js`; all `color: var(--accent)` rules use them); text on a filled accent shape uses the better of black or white (`--accent-on`, fixed the white "VS" on yellow). Outline and border colours keep the pure accent. **Not done:** the pixel-level check in Check & fix on rendered frames, and the contrast warning in the theme editor.

The screenshot of 2026-10-23 shows lime-green outlined text on a near-white background (contrast ~1.3:1). Rules:

* The composer computes the **real contrast** of every text element against what is behind it (theme background, card fill, or the sampled frame for video backdrops) using WCAG relative luminance, and enforces **≥ 4.5:1** for body text and **≥ 3:1** for big display text (≥ 48 px). If a theme colour fails, it is replaced by the theme's ink or accent-strong variant, or the element gets a backing plate/outline/shadow; never shipped as is.
* Theme editor shows a contrast warning and the ratio for each pair; the "stamp" / outline styles get a solid fill plate by default on light themes.
* The frame QA (`vt/ai/vision.py` pixel fallback) adds a contrast check on rendered frames: text boxes from `data-el` rectangles, measured in the actual pixels; failures are listed in Check & fix and fixed automatically.
* Tests: unit tests on the contrast function and the fix-up; a golden render of the screenshot's scene must pass ≥ 3:1.

### P6.8 Live transcript side panel

**Status 2026-10-23: built and tested** (`e2e/script.mjs` 11/11, API tests): a **Script** tab next to Scenes/Words/Media with one box per sentence, current sentence highlighted and followed during playback, click the time to seek; paste a correction and press Ctrl+Enter or click away (`PUT /api/projects/{id}/transcript`, aligned with difflib in `vt/transcript_edit.py`: matching words keep their real time, replaced runs are spread over the old words, inserted words ride on the previous word, missing words are dropped without touching the audio); **Paste all text** shows a preview of what changes before applying; one-step Undo/redo (`/transcript/undo`). **Not done:** find/replace, speaker labels, forced re-alignment of changed spans, multi-step text undo.

The old transcript page is gone; the Words tab edits one word at a time.

* A **Transcript** panel docked to the side of the editor (toggle, resizable), showing the whole text as sentences/snippets with timecodes, the current one highlighted and auto-scrolled with playback, click to seek.
* Each snippet is an editable text box: **paste a corrected sentence** and it is aligned back to the words (keep timings for unchanged words; for changed ones, distribute the snippet's time by character length, then refine with forced alignment from faster-whisper word timestamps on that span). Saved as word edits (existing `edits.json`), captions and graphics update live, undoable.
* "Paste whole transcript": align a full correct script to the recording (already supported for script policy; extend to replace all words), with a diff view before applying.
* Find/replace across the transcript, add to glossary from a selection, mark/cut filler words, speaker labels.

### P6.9 Order of work

1. **Spikes (2–3 days, decide go/no-go):** (a) run Concat headless on this Windows machine, drive it over JSON-RPC from Python: create project, import a clip, add a title and an alpha overlay, export; measure speed; (b) Kokoro and Chatterbox via onnxruntime in Python, English and Bangla samples, judged by ear; (c) PANNs/CLAP on the laughter/applause fixtures. Record results in this file.
2. **P5.1 dragging fix** and **P6.7 contrast** (small, user-visible).
3. **P6.8 transcript panel.**
4. **P6.2 track model + editor**, with conversion of old projects; then **P6.3 layered rendering** (ffmpeg compositor first, Concat compositor if the spike passed).
5. **P6.6 sound-aware visuals.**
6. **P6.4 voices**, **P6.5 cutout/cleanup/effects.**
7. **Phase 5** (A-roll/B-roll/motion graphics) on top of the track model.

**Acceptance for Phase 6:** a project with voice, music, two B-roll clips, a laughing-baby sound clip and graphics can be built automatically and then edited by hand with added tracks; every text element passes the contrast rule in the rendered frames; a pasted corrected sentence updates captions within a second; exports pass `qa_analyze` with both compositors (or the ffmpeg one alone if the Concat spike fails); all existing suites still pass. Report what was verified by rendering, and what only by tests.

---

## Phase 5 plan (2026-10-22): A-roll, B-roll and motion graphics, and fixing timeline dragging

Written after reading the code as it is today. Nothing in this section is built yet. Build it in the order of P5.9; each step ends with real renders checked by `scripts/qa_*.py`, not only unit tests.

### P5.0 Where the app stands (facts that shape the plan)

* The app is **voice-first**. A dropped video is reduced to its audio (`input.wav`); the speaker's picture is thrown away. There is no "A-roll picture" anywhere: every frame on screen is generated HTML (scenes, stick figures, emoji) or a media-bin item used as a backdrop / `media_frame` / `device`.
* What already exists and is reused:
  * word-timed transcript, sentences (`beats`), cuts in source time (`cuts.json`, `audio_edits.json`), filler and silence removal, lead-in trim;
  * the scene plan (`scenes.json`) and the AI Video Script contract (`vt/script/`), with validation and repair, rules fallback, local LLM (Ollama) and Claude over MCP;
  * the media bin (`MediaItem`: image / video / gif, caption, tags, faces, focus point, source, licence), VLM captions and tags (`vt/ai/media_tags.py`), the free catalogue (`vt/director/catalog.py`), stock search (`vt/director/stock.py`);
  * ~40 deterministic motion-graphic components (charts, steps, flow, compare, device, code-like cards, clipart), stick figures, emoji, captions, transitions, SFX and music ducking;
  * HyperFrames/Chrome rendering of a composition per aspect, ffmpeg mux, loudness normalisation, QA scripts (`qa_generate`, `qa_analyze`, `qa_media_audio`).
* Therefore the new work is mostly: **keep the speaker's picture as a real track**, add **reframing (crops, punch-ins) driven by face tracking**, turn the scene plan into a **multi-track edit plan** where a "scene" can be *A-roll*, *B-roll clip*, or *motion graphic*, and teach the planners to choose between them. Motion graphics already exist; they become one of three B-roll kinds instead of the only picture.

### P5 status 2026-10-23: first slice built (A-roll for imported videos)

What exists (`vt/aroll.py`): a project made from a **video** keeps the speaker's picture. A pipeline stage *aroll* cuts it with exactly the voice's cuts (silences, fillers, the owner's own cuts; picture time = voice time, proven by a brightness-ramp test and on real footage), stores it as `media/aroll.mp4` without sound (`role: a_roll`; the planners never use it as B-roll: `ProjectMeta.planner_media()`), finds the face (median of eight frames at 960 px) for the crop, and re-cuts when the cuts change. **Planning:** `apply_speaker` shows the speaker on the opening scene and on every scene whose only pictures are a word or small sticker (never a chart, steps or card), at most two speaker scenes in a row, a gentle punch-in on every other one but never two in a row and only when a face was found, text placed away from the face (the band above the captions when the head is high), no wash over the picture (a soft gradient under the captions only). The composer derives the backdrop's media offset from the scene start, so edits and cuts never leave a stale offset. Studio: "The speaker's picture" panel (show the speaker where it fits / graphics only; `POST /api/projects/{id}/aroll/apply?on=`), "A-roll (speaker)" chip in the media bin. Real check `scripts/qa_aroll.py` on a public-domain 32 s 1080p talking-head video (US CBP video blog): the speaker is on 4 of 5 scenes, the face is inside the frame in all rendered speaker frames in 9:16 and 16:9, and in 16:9 the rendered picture matches the right source moment. Tests: `tests/test_aroll.py`. **Nothing is placed on a person (added after the owner's feedback "emojis on top of people is not cool", `vt/people.py`):** the person is found with image processing: a matte of the main subject (IS-Net, face-box body shape as a fallback), morphology (opening, closing, hole filling), only the part touching the face is kept (a big object beside the speaker is not a person), a safety margin, and a coarse 48x27 grid stored per speaker scene. For each output shape the grid is mapped through the crop the picture really gets (object-fit cover around the subject position plus the punch-in), the largest empty rectangle outside the caption zone becomes the scene's `stage` (renderer override), and when there is no room worth using the elements are dropped so the speaker stays clear. Photos with a detected face get the same care from a body shape estimated from the face. The crop also follows the head of each scene (the speaker leans in and turns), not one global face position. Real result on two talking-head videos (a US government video blog and the owner's "Talking Head Video Raw"): in 16:9 the elements sit in the empty corners with 0.0 % overlap with an independent person mask, in 9:16 (the speaker fills the crop) they are dropped. Tests: `tests/test_people.py` (geometry against brute force, decoy object, composer). **Not done from the Phase 5 spec:** B-roll semantic search and the VLM check that a clip shows what is said, narrative map and importance scoring, several A-roll clips, wide/medium/close crops from the source resolution, face *tracking* over time (one median face position is used), zoom limits by source resolution, split-screen and picture-in-picture layouts, generated motion graphics chosen by meaning (the existing component catalogue is still chosen by the old planners), the track view of the speaker on the timeline, validation of the whole edit before export.

### P5.1 Timeline dragging: what is wrong and the fix (do this first, it is independent)

**Status 2026-10-23: built and tested** (`e2e/timeline3.mjs` 13/13): the scene end follows the pointer within 2.5 px on every frame and a green marker shows the sentence it will settle on; scenes have start handles; voice clip edges move live with a size label (− 1.2 s), an outward drag with nothing to restore explains itself, Escape cancels, pointer capture keeps a drag working outside the window, handles are 12 px, snapping is 6 px and ignores words for scene edges. **Not done:** Alt-drag to land on a word (needs `at_word` on the boundary endpoint), first scene start / last scene end (those are voice trims). Also fixed on the way: voice edits returned 500 on a project that has no silence stage (hand-built or imported).

**Symptom (owner):** dragging the start or end of a clip does not move with the mouse.

**Causes found in `studio/src/review/Timeline.tsx`:**
1. *Voice clips:* the clip edge itself never moves. `startTrim` only draws a red/green "ghost" rectangle; the clip keeps its old size until the server re-cuts the audio and returns (1–3 s with recomposition). It reads as "nothing happens" and then a jump.
2. *Dragging a voice clip edge outward* does nothing unless there is an adjacent cut to restore (`shape()` returns `null`), with no feedback.
3. *Scenes* have only an end handle (`.grab` on the right) and it snaps to sentence starts only, so the edge moves in big jumps or not at all within a long sentence. There is no start handle; the first scene's start and the last scene's end cannot be dragged.
4. *Handles are tiny* (8–9 px, partly outside the clip), and the pointer is not captured: when the pointer leaves the window, or moves fast over the iframe, events are lost.
5. *Snapping is applied to the raw pointer* with a 9 px radius to every word start, playhead, scene edge and clip edge; at normal zoom almost every position snaps somewhere, so the edge sticks and then leaps.

**Fix (frontend only, plus one server tweak):**
* A single drag controller for all edges: `setPointerCapture` on the handle, `pointermove` coalesced per animation frame (done), Escape cancels, live state held in a ref and written to the DOM with `transform`/`width` for the two affected elements only (no React re-render per frame).
* **Live edges:** while dragging, the clip's own edge moves under the cursor (voice clip shrinks or grows, scene clip resizes, neighbour follows), the trimmed part is shown greyed with its duration ("−0.84 s"), and a tooltip shows the time. On drop the new geometry stays (optimistic) until the server answers; on error it animates back and shows the reason.
* **Outward drag without a cut** is clamped at the clip's original edge with a visible stop (shake + "nothing cut here to bring back"), instead of silently doing nothing.
* **Scenes get start and end handles**; inner edges move both neighbours. The edge follows the pointer freely and *previews* the sentence it will land on (thin marker + label); it snaps only on drop. Holding Alt lands on the nearest *word* (needs the server to allow splitting a scene inside a sentence: `POST /scenes/{sid}/boundary` with `at_word`, splitting the beat; validation already re-times captions).
* Handles 12 px wide, fully inside the clip, with a visible grip on hover, cursor `ew-resize`; on touch, 24 px.
* Snapping radius scales with zoom (6 px), snaps only to *strong* targets (clip edges, scene edges, playhead) by default, words only with snapping set to "words", and shows the snap line only when it actually snapped.
* Tests: extend `e2e/timeline2.mjs` with frame-by-frame width checks for both edges of a voice clip and a scene, outward drag feedback, Escape cancel, drag outside the window, and Alt-drag to a word. Pass criterion: the edge is within 2 px of the pointer (or the previewed snap) on every sampled frame.

### P5.2 Media roles: A-roll and B-roll

* `MediaItem` gains `role: "a_roll" | "b_roll" | "asset"` (asset = picture, logo, screenshot), `role_source: "user" | "auto"`, and analysis fields (P5.3). A project gets `a_roll: [media ids]` in order (several takes or cameras allowed).
* **Import:** dropping a video on New ("Talking-head video") makes a project whose voice is the video's audio (as today) **and** keeps the video as A-roll. Dropping more videos into the media bin asks or guesses: A-roll if it has continuous speech by the same voice and a face in most frames, otherwise B-roll. The user can change it with one click (Media tab: "A-roll / B-roll / Asset" segmented control); the guess is never final.
* Multiple A-roll clips: the voice track becomes their audio in order (each clip is a source segment in `cuts.json`; the existing source-time machinery is reused, extended from one source file to a list of `(file, in, out)`).
* Audio-only projects keep working exactly as today (no A-roll, every moment is a generated picture).

### P5.3 Analysis (stored per media item, cached by file hash)

* **A-roll:** transcript (existing ASR), speaker turns (existing `stages/speakers.py`), pauses and fillers (existing), **face track** per 0.2 s (box, size, confidence) using the existing `detect_faces` sped up with sampling and interpolation, shot changes (ffmpeg `scdet`), camera motion estimate (frame difference of the background), resolution. Output: `analysis/<media id>.json`.
* **B-roll:** duration, orientation, resolution, shot changes, a VLM caption every shot (existing `media_tags.py`), subjects and actions as tags, a quality score (blur, exposure, shake), dominant colours. Captions and tags are embedded with a small local text-embedding model (Ollama `nomic-embed-text` or similar; fall back to keyword overlap) for **semantic search** (`GET /api/projects/{id}/media/search?q=`), shown in the Media tab search box.
* All analysis runs as background jobs with progress; the editor is usable before it finishes.

### P5.4 The narrative map

From the transcript: for each sentence (beat), its **idea**, **importance** (0–3), **kind** (claim, example, statistic, step, comparison, personal statement, code, question, transition), **keywords**, and **visual need**: `keep_speaker`, `emphasis` (punch-in), `illustrate` (B-roll), `explain` (motion graphic), `data` (chart, only with numbers actually spoken or supplied). Produced by the existing AI provider layer with a schema and validator (facts may only come from the transcript or user-supplied data; anything else is rejected), with a rules fallback built from the existing roles analysis (`vt/director/roles.py`). Stored as `narrative.json`, shown in the Words tab as a thin colour strip per sentence and editable.

### P5.5 The edit plan (extends the Video Script contract)

* `scenes.json` keeps its role as the picture plan but each scene gets a **`shot`**:
  * `{"type": "a_roll", "media": id, "framing": "wide|medium|close|custom", "crop": [x,y,w,h] keyframes, "punch": 1.0–1.25}`
  * `{"type": "b_roll", "media": id, "in": s, "out": s, "fit": "cover|contain", "speed": 1}`
  * `{"type": "graphic"}` (today's behaviour: the elements are the picture)
  * plus `layout: "full" | "overlay" | "split" | "pip"` to combine a shot with graphics (e.g. A-roll with a lower-third label, split A-roll | chart, B-roll with a caption).
* Audio stays the A-roll narration whatever the picture is (the voice track is untouched by B-roll); B-roll's own sound is muted by default, optional "natural sound" at −18 dB.
* Elements, captions, transitions, SFX keep their meaning. Validation adds: every A-roll range exists in the source, B-roll `in/out` inside the clip and long enough, no gaps, crops within the source with headroom, no crop that upscales the source by more than 1.25× for the output size (never fake a close-up from 720p for a 1080p export), graphics only with facts from the narrative map.
* Regeneration is per scene: replacing a B-roll asset or a zoom re-plans and re-composes that scene only (existing per-scene ops and requests).

### P5.6 Deciding the treatment (the "AI editor")

Order per sentence, the same in the rules planner and in the LLM prompt (which only fills choices the rules allow):
1. Personal or emotional statement, or importance 3 with the speaker looking at the camera: **stay on the speaker**, maybe a subtle punch-in.
2. `illustrate`: **existing B-roll** from semantic search above a relevance threshold and quality floor, checked by the VLM ("does this shot show X?" yes/no with a reason); else user assets; else the free catalogue / stock search (licence-checked, existing code); used only if the VLM check passes.
3. `explain` or no acceptable footage: **motion graphic** from the existing component catalogue (flow, steps, compare, chart with spoken numbers, device mock, code card, clipart, stick figure, emoji), or a **generated still** (only if an image model is configured) animated with existing motion (Ken Burns, parallax); text is always real text, never in the image.
4. Nothing reliable: stay on the speaker with captions and keyword emphasis. Never stock footage that does not show what is said.

Rhythm rules: punch-ins only at sentence starts or emphasis words, at most one every ~8 s, alternate wide → medium → wide, never two zooms in a row on the same framing, return to the wide shot after a B-roll; B-roll enters at the first content word and leaves at the end of the sentence (or the idea), minimum 1.5 s, maximum ~8 s per shot; cuts by default, dissolves only between B-roll shots of the same idea. "Energy" setting (Calm / Normal / Social) scales these limits.

### P5.7 Reframing (crops from the face track)

* Framings computed per A-roll segment from the face track: wide = source; medium = face height ~22 % of frame with eyes at 1/3 from the top; close = ~35 %. Smoothed with a critically damped follow (no jitter), held still unless the face moves out of a safe box.
* 9:16 from 16:9 A-roll follows the face horizontally (existing `fx` focus logic extended to a track).
* Rendered by ffmpeg (`crop`+`scale` with expressions from the keyframes) into a per-aspect A-roll intermediate, or as a `<video>` with a CSS transform in the HyperFrames composition — decide by a spike (P5.9 step 2): the composition route keeps one pipeline; the ffmpeg route is faster and frame-exact. Either way the A-roll audio is the existing cut audio, so sync is by construction.

### P5.8 Timeline and editor changes

* Tracks: **V1 A-roll** (clips with framing badges), **V2 B-roll / graphics** (overlapping shots), **Elements**, **Actions**, **Words**, **Voice**, **Music**. Clips on V1/V2 can be trimmed, moved (V2), swapped ("Replace with…" opens semantic search), and their framing changed from the inspector (Wide / Medium / Close / Custom box drawn on the preview).
* "Why this?" on each AI decision (the narrative map entry and the rule or model reason), and "Keep speaker here" / "Find other B-roll" / "Make a graphic instead" one-click alternatives.
* Preview: the A-roll `<video>` in the preview iframe follows the playhead (seeks on scrub, plays with the audio clock).

### P5.9 Order of work, tests and acceptance

1. **P5.1 timeline dragging** (frontend; `timeline2.mjs` extended). Ship on its own.
2. Spike: render a talking-head A-roll through the composition with a moving crop at 30 fps, both aspects, measure speed and sync (A/V offset < 1 frame). Pick the render route.
3. Keep video on import, `role` on media, multi-source cuts (P5.2). Test: a 2-minute talking-head video in, the same video out (A-roll only), lips in sync, cuts and fillers removed, export passes `qa_analyze` (+ new check: frame of the A-roll at time t equals the source frame at the mapped source time).
4. Analysis jobs and semantic search (P5.3).
5. Narrative map with validator and rules fallback (P5.4); eval set of 5 transcripts with hand labels in `tests/script_eval/`.
6. `shot` in the plan, validation, composer and renderer support (P5.5), per-scene regeneration.
7. Treatment decisions (P5.6) and reframing (P5.7).
8. Timeline tracks and inspector (P5.8).
9. End-to-end QA with real media, three cases, each in 9:16 and 16:9, rendered and inspected (contact sheets, ffprobe, A/V sync, loudness, black/freeze, face inside the frame in every crop, no upscale beyond 1.25×):
   * talking head + matching B-roll in the project (B-roll is used where it matches, nowhere else);
   * talking head + partly matching B-roll (gaps filled with graphics);
   * talking head with no B-roll (graphics and reframing only; nothing invented).
   Sources: free CC0/CC BY talking-head and B-roll clips added to the catalogue (`vt catalog`), plus the owner's own recording.

**Done when** the three cases above render end to end, the plan is editable per segment in the Studio, a replaced asset re-renders only its scene, audio-only projects and all existing modes still pass their suites, and the report lists what was verified and what was not.

**Risks:** face tracking speed on long videos (sample and interpolate; cache); VLM relevance false positives (require a positive yes with a reason, and keep the speaker on doubt); render time of video inside HyperFrames (the spike decides); stock licences (existing filter: CC0 / PD / CC BY only).

---

## Phase 4 plan (2026-10-22): stick-figure videos and one "Video Script" contract for every AI

Goal: a new kind of video, **stick-figure animation**, generated fully automatically from a transcript, and at the same time one shared, versioned
data contract (the **Video Script**) that Claude or any other AI (local Ollama models, OpenAI-compatible APIs) fills in from one long, precise
prompt. The tool validates it, repairs what it can, and renders it. The rule engine keeps working without any AI and writes the same contract,
so every path (rules, local model, Claude via MCP, Claude or another API) produces the same kind of file and the same quality checks apply.

### P4.0 What StykAnimate is, and how we use it (decision)

Facts (checked 2026-10-22, repository `filippocalippo/StykAnimate-App`):
* A complete desktop/browser **editor** (Electron + WebGPU) for stick animation: fixed-length joints, IK for arms and legs, stretchy nodes,
  3D figures, motion paths, camera moves, particles, Pivot (`.piv`, `.stk`) and Stick Nodes project import/export, MP4/WebM/GIF export.
* Licence **GPL-3.0**. It is an application, not a library: no npm package or stable API for "pose a figure from data, render frames".
* Its code is organised around an interactive document model (commands, undo, workers, GPU caches); rendering needs WebGPU.

Consequences:
* Copying or bundling its source would make this whole project GPL-3.0 (our repository has no licence file yet). That is a project-level
  choice for the owner, not something to slip in. **Decision for now: no StykAnimate code is copied.** We build a small, clean-room stick-figure
  engine for our renderer (SVG + GSAP, which HyperFrames already renders frame-exactly) and treat StykAnimate as a **companion app**:
  * **Export to StykAnimate**: every stick-figure scene can also be saved as a Pivot-compatible `.stk`/`.piv` project, so a user can open it in
    StykAnimate and hand-polish the animation (Pivot formats are older, publicly documented community formats; the writer is our own code).
  * **Import figures from StykAnimate / Pivot / Stick Nodes**: custom figures made there (a teacher, a robot, a cat) can be imported into our
    figure library: we read the skeleton (joints, lengths, parts, colours) from the file, never their code.
  * Their docs (RIG-CONSTRAINTS, MOTION-PATHS, CAMERA-EDITING, ANIMATION-MODES) are used as a **design reference** for what a good stick rig
    needs: fixed-length bones, IK limbs, easing, onion-skin-style smear, camera follow.
* If the owner later chooses GPL-3.0 for this project, P4.9 describes how StykAnimate's evaluator could be embedded instead. The contract and
  everything else in this plan stay the same either way.

### P4.1 The Video Script contract (all video kinds)

One JSON document per video, `video_script.json`, with a JSON Schema in `vt/script/schema.json` (generated from Pydantic models) and a
`version` field. It describes intent, not pixels:

```json
{
  "version": "1.0",
  "kind": "stick" | "explainer" | "infographic" | "cartoon" | "mixed",
  "meta": {"title": "...", "language": "en", "audience": "students 12-15", "tone": "playful", "aspect": "9:16"},
  "cast": [{"id": "maya", "rig": "stick-basic", "style": {"color": "#1f2937", "head": "round", "accessory": "glasses"}, "role": "teacher"}],
  "sets": [{"id": "lab", "kind": "classroom", "props": ["board", "desk"]}],
  "scenes": [{
    "id": "s1", "beats": ["b1", "b2"], "set": "lab", "camera": {"shot": "medium", "move": "push_in"},
    "actions": [
      {"at_word": "w3", "who": "maya", "do": "walk_in", "from": "left", "to": 0.35},
      {"at_word": "w7", "who": "maya", "do": "point", "target": "board"},
      {"at_word": "w9", "who": "maya", "do": "say", "bubble": "Gravity pulls everything down"},
      {"at_word": "w12", "who": "maya", "do": "react", "emotion": "surprised"}
    ],
    "overlays": [{"at_word": "w7", "type": "definition", "term": "Gravity", "meaning": "a pull between masses"}],
    "sfx": [{"at_word": "w12", "id": "whoosh"}]
  }]
}
```

Rules that make it AI-proof:
* Every time is a **word id** from the transcript (never seconds): the AI cannot drift out of sync, and edits to the transcript re-time everything.
* Every verb, rig, set, prop, emotion, camera move and overlay type is an **enum** from the catalogue the prompt includes; free text is only
  allowed in bubbles, titles and labels, with length limits.
* Overlays reuse the 39 existing elements (definition, steps, chart, ...), so stick videos can teach with the same infographics.
* `validate_script()` returns precise, fixable errors ("s3 action 2: target 'board' is not a prop of set 'lab'; props: desk, door").
  A **repair pass** fixes common mistakes automatically (unknown word id -> nearest word in the scene, verb synonym -> catalogue verb,
  overlapping actions of one character -> queued). Remaining errors go back to the AI once, with the error list (as MCP already does).
* The existing `scenes.json` becomes a **compiled** form: `compile(script) -> scenes.json + stick timeline`. The renderer stays the single
  source of truth for drawing.

### P4.2 The prompt (one big, elaborate, versioned prompt)

`vt/script/prompt.py` builds one prompt from parts, each tested and versioned:
1. **Role and goal**: "You are the director and animator of a short educational stick-figure video ...".
2. **The transcript**, as numbered beats with word ids and times, plus the detected language, kind of video and audience.
3. **The catalogue**, generated from code so it can never go stale: rigs, verbs (with what each looks like and how long it takes),
   emotions, sets and props, camera shots and moves, overlay elements with field limits, SFX ids.
4. **Craft rules** (the "animation pattern"), written as checklists the model must follow:
   * Staging: one main action at a time; the speaker faces the audience; who acts is lit/centred; keep the line of action readable.
   * Timing: anticipation before big moves, action on the stressed word, a hold of 0.5-1 s after it; nothing moves for its own sake;
     never more than ~4 s without a change on screen; the first second already shows the subject (thumbnail).
   * Teaching: introduce a term -> show it (pose/prop) -> name it (overlay) -> recap; numbers become charts; processes become steps
     acted out; comparisons become two figures; questions become a figure thinking with a "?".
   * Continuity: the same character keeps its look and screen side; entrances from the side they will face; props persist inside a set.
   * Social video: 9:16 safe areas, captions zone free, a hook in the first 2 s, a clear end beat (recap or call to action).
5. **Three worked examples** (input beats -> output JSON): an education clip, a story, a product explainer.
6. **The output instruction**: return only JSON that matches the schema (with the schema attached). Local models get it as a JSON-schema
   constrained output (Ollama `format`), Claude via MCP (`get_script_task` / `submit_script`) or via the API with structured output.

Prompt quality is measured, not guessed: `tests/script_eval/` holds 20 transcripts (education, story, product, discussion; Bangla and
English) and scores every model's output automatically (valid on first try, repairs needed, actions per minute, idle gaps, overlays per
key term, continuity violations). A prompt change ships only if the scores do not drop.

### P4.3 The stick-figure engine (renderer)

`renderer/runtime/vt-stick.js`, SVG drawn and animated by GSAP inside the existing HyperFrames timeline (frame-exact, seekable):
* **Rig**: 15 joints (head, neck, chest, hip, 2 x shoulder-elbow-hand, 2 x hip-knee-foot) with fixed bone lengths; poses are joint angles.
  Analytic **2-bone IK** for hands and feet ("put the hand on the board", "feet stay on the floor" while the body leans).
* **Look**: line width, round caps, head shapes, optional face (eyes, mouth shapes for emotions and lip sync from the voice envelope we already
  compute), accessories (glasses, hat, tie, lab coat, hair) as small SVG parts; colour per character; light/dark set backgrounds.
* **Motion library** (verbs), each a function of the rig, start/end time and parameters, built from keyed poses with easing and overlap:
  idle (breathing, weight shift), walk/run (cycle with foot locking), enter/exit, turn, point (IK), wave, nod, shake head, shrug, think
  (hand on chin), explain (open palms), count on fingers (1-5), lift/carry/drop prop, push/pull, sit/stand, jump, fall, celebrate, facepalm,
  write on board, hold sign, look at, handshake/high-five (two figures), react (surprised, happy, sad, angry, confused, scared).
* **Secondary motion**: anticipation, overshoot and settle, follow-through on arms/head, smear frames for fast moves, squash on landing.
* **Camera**: wide/medium/close shots, push-in, pan to follow a walking figure, shake on impacts; same safe-area rules as other videos.
* **Sets and props** reuse the cartoon sets (classroom, office, street, nature, lab, space ...) redrawn in a line-art style that matches
  stick figures, plus our 31 drawn clipart items as props ("a black hole on the board").
* **Crowds**: up to ~8 figures with instanced rigs and cheap idle so classrooms and audiences are possible.
* **Export to StykAnimate**: the same poses are sampled at the project frame rate and written as a Pivot-compatible file (P4.0).

### P4.4 Automatic direction without AI (rules, always available)

The director gains a `stick` profile: roles and facts (already extracted) map to verbs and overlays:
question -> think + "?"; definition -> point at board + definition card; number -> count on fingers or hold a sign with the number;
steps -> act each step in order; contrast -> two figures, one per side; story persons/places -> cast and set; recap -> summarise with a list
held up; call to action -> wave/point at viewer. Emphasis (from the voice) chooses the beat for the main action. The local LLM may then
refine verbs and bubbles inside the same schema, exactly like it refines pictures today.

### P4.5 Studio

* New video: kind **Stick figures** next to Explainer/Product/Story/...; cast picker (look of 1-3 characters) with live preview.
* Review: a scene shows its actions as chips on the word timeline (drag to another word to re-time); "Show as" gets stick variants;
  "Ask AI to redo this scene" sends one scene's part of the prompt.
* Character studio (inside Design Studio): colours, line width, head and accessories; import a figure from StykAnimate/Pivot/Stick Nodes.
* Export: MP4 as today, plus "Open in StykAnimate" (`.stk`) per scene or whole video.

### P4.6 AI providers

`vt/ai/` with one interface `complete_json(prompt, schema) -> dict`: Ollama (local or LAN, as today), Claude via MCP (no key, user's Claude
Code), Claude API and OpenAI-compatible endpoints (optional, user's key, stored like the stock keys, never shown back). Same prompt, same
validation, same repair loop; the Studio shows which provider made the script.

### P4.7 Tests

* Unit: IK (reach, unreachable target clamps, elbow side), bone lengths constant in every frame, every verb keeps feet on the floor unless
  jumping, schema validation and repair cases, prompt builder snapshot.
* Render: golden contact sheets of every verb in 9:16/1:1/16:9; a "no clipping out of the safe area" pixel check.
* End to end: three transcripts -> rules-only stick video, local-model stick video, Claude (MCP) stick video, each rendered and measured
  (no empty screens, actions per minute in range, captions free, loudness and container checks for social upload).
* Interop: write `.stk`, read it back with our reader, compare poses; manual check that StykAnimate opens it.

### P4.8 Delivery order

1. Video Script schema, validator, repair, compiler to scenes.json (with the current non-stick videos expressed in it).
2. Stick rig + IK + 12 core verbs + 3 sets, rendered in HyperFrames; goldens.
3. Rules director `stick` profile; first fully automatic stick video.
4. The big prompt + MCP tools `get_script_task` / `submit_script` + Ollama path; evaluation set and scores.
5. Remaining verbs, two-figure interactions, camera, crowds, lip sync.
6. Studio: kind, cast picker, action chips, character studio.
7. Pivot/StykAnimate export and figure import.
8. Optional API providers (Claude API, OpenAI-compatible).

### P4.9 Risks and open decisions

* **Licence (owner decision)**: keep the project permissive and interoperate through files (planned), or adopt GPL-3.0 and embed
  StykAnimate's evaluator for richer rigs. Needs an explicit choice before any of their code is used.
* Pivot/STK format details must be confirmed against real files; if the format is too irregular, export only figures, not animation.
* Stick animation quality depends on timing craft; the verb library and the evaluation set are the main defence. Budget time for tuning
  by watching real renders, not only tests.
* Local 7-8B models may struggle with a large schema; the repair pass and a "verbs only" reduced schema are the fallback.

---


## Phase 2 plan (2026-10-22): one-two-three, rule-based "motion designer"

Goal: **input → choose a use case (or Auto) → video.** No step needs a human. Everything is HTML/CSS/SVG/GSAP rendered by
HyperFrames; no AI video generation. A local or Claude LLM may *choose* among rules, but every pixel comes from deterministic,
tested templates. Today's weakness: the video is mostly emoji + captions in one stack layout. Phase 2 replaces that with a
**scene grammar**: use-case → narrative beats → scene archetype → layout → infographic/character/media → motion → sound.

### Phase 2 status (implemented 2026-10-22)

| Plan item | Status | What exists |
|---|---|---|
| P2.0 1-2-3 flow | done | New video: input (record, upload, type a script, `Name: text` dialogue) + kind of video (Auto or chosen) + optional pictures, then Generate. Verified end to end with real spoken scripts for product, discussion, story and education (rendered MP4s). |
| P2.1 Use-case profiles | done | `design/profiles/{general,product,story,discussion,education}.json` (pacing, scene-type weights, looks, transitions, SFX level), editable data; Auto detection from sentence roles (`detect_usecase`); profile looks narrow the automatic design. |
| P2.2 Scene grammar | done | `vt/director/`: bilingual role tagger and fact extractor (`roles.py`), 21 scene types with fit functions and builders (`archetypes.py`), grouping by pace and speaker, seeded weighted selection with variety rules, media assignment, transitions (`plan.py`). Deterministic per project id. Layouts added: grid, side, lower. Not done: a dedicated layout solver with a library of ~25 grids (layouts are 6 CSS arrangements plus measured shrink and grow-to-fit). |
| P2.3 Infographics | done | 16 new elements: ring, line_chart, steps, timeline, definition, checklist, pros_cons, stat_row, question, feature_grid, cta, price_tag, device (phone/laptop/browser with callouts), speaker_card, cartoon, media_frame, on top of the 14 existing ones (30 total, all rendered and pixel-checked in both shapes). Also done: flow, cycle, hierarchy, Venn, funnel, pyramid, matrix, pictogram and gauge diagrams (39 elements in all, three shapes). Not done: maps, kinetic-typography presets beyond keyword styles. |
| P2.4 Cartoons | done (own art) | Procedural SVG characters (man, woman, boy, girl, elder, worker, teacher, doctor, robot) with 9 poses and 6 expressions, ten sets (village, market, home, office, classroom, street, nature, studio, shop, plain) with parallax and a slow camera, speech bubbles, props from the emoji library, blinking and breathing, mouths and equaliser bars driven by the real loudness of the voice, casting kept consistent across scenes. Not done: external CC0 art packs (Open Peeps), Lottie props, gesture-to-infographic pointing. |
| P2.5 Media | done | Media bin (images, GIFs converted to looping MP4, clips normalised to 30 fps without audio), subject position estimate, matching by caption/tags/name then even spread, Ken Burns, frames (rounded, polaroid, TV), device mockups, full-screen backdrops. Stock search/download (Pexels, Pixabay) with the user's own keys, licence and credit recorded and a `.credits.txt` written next to exports. Stock search words are suggested from the script (rare content words and the scenes' own keywords, shown as chips in the media bin). Not done: image-embedding matching (CLIP). |
| P2.6 Contrast-aware text | done | `vt/director/contrast.py`: WCAG maths on the worst pixels (3rd percentile, several frames for video), chooses ink then the lightest scrim (gradient from the bottom edge, then full tint) that reaches 4.5:1; the maths mirrors the CSS gradient, and 6 rendered-pixel tests confirm the promised ratio on real frames. Claude's and the user's plans get the same check (`refresh_scrims`). Caption colour follows per scene. Also done: faces (OpenCV Haar) move the text to the 'upper' layout, and a blurred panel treatment. Recordings with two clearly different voices get Speaker 1/2 automatically (`vt/stages/speakers.py`, pitch and spectrum clustering with strict acceptance, switch off in New video > advanced); it is a helper, not a diarisation model, and similar voices are left as one speaker. |
| P2.7 Data and code | done | Schema (Scene.archetype/role/backdrop, Beat.speaker, Word.speaker, MediaItem, ProjectMeta.usecase/media); renderer split into `vt.js` + `vt-info.js` + `vt-cartoon.js` + `vt-media.js` (+css) with an explicit `VTX.start()`; Studio: kind-of-video picker, picture upload, media bin with stock search, per-scene "Show as", Settings for stock keys; MCP tools `list_media`, `add_media`, `list_scene_types`, `show_scene_as`; planning task carries kind of video, scene types and media. |
| P2.8 Delivery P2-A to P2-F | done | see above |
| P2.8 P2-G evaluation | done | `tests/test_evaluation.py`: 7 plans (4 kinds, English and Bangla) rendered in both shapes, checked for empty screens, edge overflow, repetition and contrast; golden contact sheets for every element (`tests/golden/phase2-*`). |

Honest limits: speaker detection comes from `Name: text` scripts only (no diarisation of recordings); the art is simple flat vector drawing generated by code, not illustration; the local AI refines picture scenes only, the other scene types are rule-built; 1:1 aspect is not implemented.

### P2.0 The 1-2-3 flow

1. **Input**: record / upload audio / type or paste a script / paste a URL or product sheet (product mode) / drop media (images, GIFs, video clips, logo).
2. **Use case**: Auto, Product showcase, Storytelling, Discussion (2+ voices), Education. Auto classifies from the transcript (embedding prototypes + LLM brief, already built) and shows the choice with one-click override.
3. **Generate**: one button. Output: MP4 (9:16, 16:9, 1:1), SRT, thumbnail, and a project you may review but never have to.

Acceptance: a 60 s input of each use case renders with **zero edits**, no empty screen > 1.5 s, no text below 4.5:1 contrast, no element outside the safe area, ≥ 3 distinct scene archetypes per minute, and the same input always gives the same video (seeded).

### P2.1 Use-case profiles (`design/profiles/<usecase>.json`)

A profile is data, not code: pacing, archetype weights, allowed looks/palettes, typography scale, caption style, music mood, SFX density, transition set, character usage, and the narrative template.

| Use case | Narrative template (beat roles) | Favoured archetypes | Look | Motion | Sound |
|---|---|---|---|---|---|
| Product showcase | hook → problem → product reveal → 3 features → proof (numbers, reviews) → price/offer → CTA | hero media + callouts, feature grid, spec table, before/after split, device mockup, price card, CTA end card | clean / soft / neon, brand colour from logo | snappy, slide/zoom, parallax on product image | upbeat, whoosh + click SFX |
| Storytelling | setup → character → conflict → turning point → resolution → moral | character scene (cartoon on a set), speech bubble, location card, timeline, emotion close-up, quote card | sticker / calm / brutalist, warm palettes | smooth, camera pans across a scene, idle character motion | ambient, soft pops, gentle risers |
| Discussion (podcast, debate, interview) | topic → speaker A point → speaker B point → contrast → takeaway | speaker cards with live waveform/avatar, quote pull, pros/cons, vs split, poll/bar, key-takeaway list | editorial / clean / graphite | calm cuts on speaker change, word-highlight captions | low music, minimal SFX |
| Education | question/hook → concept → definition → steps → example → recap/quiz | definition card, numbered steps, diagram (flow, cycle, hierarchy), chart, equation, labelled image, quiz card, recap checklist | blueprint / soft / clean, high contrast | build-up (reveal parts one by one), highlighter, arrows drawing | light music, tick/check SFX |

### P2.2 Scene grammar (the rule engine)

Pipeline addition: `beats → roles → archetypes → layouts → elements → motion → audio cues`. Each step is a pure function with tests.

1. **Beat role tagger.** Each sentence gets a role from the profile's template (hook, claim, number, comparison, list item, definition, step, quote, question, emotion, place, character action, CTA...). Rules first: regexes and keyword lexicons per language (Bangla + English: "প্রথমত / first", "কিন্তু / but", "৳ / $", question marks, imperative verbs, "vs/চেয়ে"), numbers and units, list detection across consecutive sentences, speaker change. Then the LLM may relabel within an enum (JSON schema), never invent.
2. **Archetype selector.** A weighted table `role × usecase → archetypes`, with constraints: no archetype twice in a row, every N seconds a "big moment" (hero/number/reveal), variety quota per minute, scene length 2.5–8 s, hard cut on speaker change. Deterministic weighted sampling seeded by project id.
3. **Layout solver.** Archetype → layout from a library of ~25 grid templates per aspect (9:16, 16:9, 1:1): hero-centre, split L/R, top-media/bottom-text, 2×2 grid, 3-column, list-left/visual-right, full-bleed media + lower third, picture-in-picture, timeline band, quote-centre. Safe areas per platform (caption zone, UI overlays of Shorts/Reels/TikTok). Text fits by measured shrink (built), then wrap, then abbreviate; never overflow.
4. **Element filler.** Fills slots from the transcript (exact words, numbers, units, names), the picture dictionary (built), illustrations, characters and user media (P2.5). Every slot has a typed fallback chain: user media → stock media (optional) → illustration → icon/emoji → typography.
5. **Motion director.** Per archetype a choreography (enter order, stagger, emphasis on the stressed word, exit) plus a per-profile motion preset; camera moves (pan, push-in, parallax depth layers), transitions chosen by context (topic change → wipe/whip, same topic → cut/slide, emotional beat → fade/zoom). All on the paused GSAP timeline, so preview = render.
6. **Sound director.** Cues from motion events (built: SFX roles/tiers) + music mood from the profile, ducking (built), risers before reveals, silence on dramatic beats.

### P2.3 Infographics library (HTML/SVG/CSS, data-driven)

Each is a component with a schema, an example, a builder and CSS (same 4-part rule as today) and animated build-ups.

* **Numbers**: big number with count-up, stat trio, percentage ring/donut, progress bar, gauge, money stack, before→after delta with arrow, unit pictogram (icon array "7 of 10 people").
* **Charts** (no chart library needed; SVG paths): bar (vertical/horizontal, race), line with draw-on, area, pie/donut, stacked bar, scatter-lite, sparkline. Data from spoken numbers; when fewer than 2 numbers, never a chart.
* **Structure**: numbered steps, timeline (horizontal/vertical), flowchart (boxes + drawn connectors, auto-layout with a small dagre-like algorithm), cycle, hierarchy/tree, mind map, Venn (2–3), funnel, pyramid, matrix 2×2, pros/cons, comparison table, checklist, myth vs fact, definition card, formula/equation (built), quote card, Q&A/quiz card with reveal.
* **Product**: device mockups (phone, laptop, browser window) holding user media, feature callouts with leader lines pointing at image regions, spec sheet, price tag/offer burst, rating stars, review card, logo reveal, QR/CTA end card.
* **Maps & places** (optional): simple country/world SVG map with pin and route draw (public-domain Natural Earth outlines).
* **Text effects**: kinetic typography (word-by-word slam, highlight sweep, strike-through correction, typewriter, scale-to-emphasis on the stressed word), lower thirds, chapter titles.

### P2.4 Animated cartoons without video AI

* **Assembled characters**: Open Peeps / Humaaans style modular SVG people (CC0) split into layers (head, face, torso, arms, legs, props). A rig file per character (`design/characters/<id>/rig.json`): layer pivots, poses (stand, walk, point, think, wave, celebrate, sit, shrug, sad), mouth shapes (closed, open, wide, round) and eyes (blink, look left/right, happy, sad, angry).
* **Animation by rules**: idle breathing + blinking always; **lip flap driven by the audio envelope** (mouth shape from loudness per frame, so it syncs with the real voice); gestures chosen from the beat role (question → think, number → point at the infographic, emotion word → matching expression, "walk/go/বাজারে গেল" → walk across the set); entrances (walk-in, pop, slide). All tweens on the GSAP timeline.
* **Casting**: characters from the story brief (LLM, built) or rules (pronouns, names, "father/son/বাবা/ছেলে"), consistent look per character for the whole video (seeded skin/hair/clothes from palette).
* **Sets/backgrounds**: layered SVG scenes (village, market, office, classroom, home, street, nature, studio) with parallax depth and time-of-day tint; chosen by place words, fallback to theme background.
* **Props**: emoji and line icons (built) as hand-held props or set dressing, plus Lottie animations where licensed (Lottie Simple License on LottieFiles items, checked per file) via `lottie-web` seeked by the timeline.
* Discussion mode: two-to-four speaker avatars (character or uploaded photo in a circle) with talking animation driven by diarised speech.

### P2.5 User and stock media

* **Inputs**: per project media bin (images, GIFs, MP4/WebM clips, logos, screenshots); per scene/slot assignment in Review; or automatic: the filler matches media to sentences by filename, user captions and CLIP-style image embeddings (local, open model) against the sentence.
* **Stock (optional, opt-in, API keys entered by the user)**: Pexels (free API key; free commercial use, no attribution required, no use implying endorsement) and Pixabay (own licence; no redistribution as standalone files). Downloaded clips are cached per project, licence recorded in `media.json`, credits written to the description file. Openverse for CC images with attribution kept.
* **Treatment**: Ken Burns (pan/zoom chosen by detected subject position), smart crop to each aspect using a saliency/face box, duotone/tint to the palette, rounded media frames, device mockups, split screens; video clips trimmed to scene length, muted under voice, frame-accurate in HyperFrames (video seeked per frame, transcoded to an intra-friendly format first).
* **GIFs**: converted to MP4/WebM once (ffmpeg) for deterministic seeking.

### P2.6 Contrast-aware text on images and video

For every text slot over media, at compose time (Python, before rendering), per scene and per text box:

1. Sample the media region under the box (for video: several frames across the scene; take the worst case).
2. Compute luminance distribution and local variance (busyness) with numpy; optional saliency map to avoid covering faces/subjects (move the box to the least-salient allowed slot first).
3. Choose the lightest-touch treatment that reaches WCAG 4.5:1 (3:1 for large text) against the *worst* pixels under the glyphs, not the average: text colour flip (light/dark) → text shadow/outline → gradient scrim from the nearest edge → blurred/tinted panel (backdrop) → solid card.
4. Record the decision in the composition data so preview and render match; a test renders the box and measures real contrast from the frame.
Reference: the open-source *kontrasto* library does dominant-colour based text adjustment; WCAG F83 explains why average contrast is not enough.

### P2.7 Data and code changes

* `vt/schema.py`: Scene gains `archetype`, `layout`, `role`, `media` slots, `characters`, `camera`; new element models for each infographic, character, media, device mockup, chart; `ProjectMeta.usecase`, `ProjectMeta.media`.
* `vt/director/` (new): `roles.py`, `archetypes.py`, `layouts.py`, `fill.py`, `motion.py`, `media.py`, `contrast.py`, `characters.py`; the rule planner becomes `director.plan(...)`, the LLM planners become optional relabel/choose steps inside it.
* `renderer/runtime/`: split `vt.js` into modules (layout, components, charts, characters, media, camera); keep one composition contract.
* `design/profiles/`, `design/layouts/`, `design/characters/`, `design/sets/`, `design/lottie/` with `LICENSES.md` per folder.
* Studio: New page gets the use-case picker and media drop zone; Review gets a media bin, per-scene archetype switcher ("show as: chart / steps / character / media"), and a "why this scene" explanation.

### P2.8 Delivery order

| Step | Content | Done when |
|---|---|---|
| P2-A | Profiles + role tagger + archetype selector + layout solver for the 5 most common archetypes; use-case picker | each use case renders 60 s with ≥ 3 archetypes/min, zero edits |
| P2-B | Infographics: numbers, charts, steps, timeline, comparison, checklist, quote, definition | golden renders per component, both aspects + 1:1 |
| P2-C | Media bin, Ken Burns, smart crop, GIF/video normalisation, contrast engine | text over 20 test photos/clips all ≥ 4.5:1 measured from frames |
| P2-D | Characters (2 rigs, 8 poses, mouth from audio), 4 sets, story casting | storytelling sample shows characters in ≥ 50% of scenes |
| P2-E | Product mode (mockups, callouts, price, CTA, brand colour from logo), discussion mode (speakers, diarisation) | sample product video and 2-speaker discussion render untouched |
| P2-F | Stock media (opt-in keys), Lottie props, maps | licences recorded, credits exported |
| P2-G | Evaluation set (4 use cases × 3 languages), visual checks automated (empty-screen, overflow, contrast, repetition) in CI | all checks green |

### P2.9 Risks

* Rule engines look repetitive → large layout/choreography pools, variety quotas, seeded randomness, per-profile weights tuned on the evaluation set.
* Character art quality → start with existing CC0 modular sets; keep characters optional per profile.
* Licences of third-party assets vary (Pexels/Pixabay/LottieFiles/unDraw have their own terms) → store licence per asset, prefer CC0, never bundle restricted files.
* Render time grows with media and charts → pre-transcode media, cache static layers, keep NVENC.

Sources consulted (2026-10-22): LottieFiles free animations and the Lottie Simple License; Pexels and Pixabay licence summaries; Open Peeps / Humaaans (CC0) and unDraw licence notes; kontrasto (text-over-image contrast); W3C WCAG technique F83.

---

## Implementation status (2026-10-21): built end to end

Everything below the line is the original design. This section records what was actually built, what was measured, and where the
build deviated from the plan (with the reason). See `README.md` for usage.

### Added after the first build (2026-10-21 and 22)

| Feature | Where | Notes |
|---|---|---|
| Picture dictionary | `vt/visuals/`, `design/icons/` | 145,710 English words mapped to colour emoji (Twemoji, CC-BY) and line icons (Lucide, Tabler) via WordNet + multilingual-e5-small, with seed tables for common words (`seed.json`, `seed_bn.json`) taking priority; offensive emoji blocked; emphasis of each sentence measured from loudness, pitch and length. |
| Other languages | `vt/visuals/translate.py` | Bangla and other non-Latin words are translated to English (Google Translate via `deep-translator`, MyMemory as keyless backup; single words only, cached in `translate_cache.json`, `VT_TRANSLATE=0` disables) and then looked up like English words. |
| Several pictures per sentence | `vt/planner/rules.py`, `vt/planner/llm_plan.py`, `vt/compose/composer.py`, `renderer/runtime/vt.js` | Up to 3 pictures per scene, each anchored on its own word ("lazy and careless" gives sloth + shrug). The first picture is always up within 0.5 s of the scene start. Stages shrink only when their content actually overflows the frame (`shrinkStages`). |
| Local AI planner | `vt/llm.py`, `vt/planner/llm_plan.py` | Ollama at a configurable address (default local; a LAN server works). The model only chooses which words to picture and which candidate picture fits the word in its sentence; candidates come from the dictionary and the word-in-sentence embedding (weak matches, role emoji such as singers, and line icons when a colour picture exists are not offered), the reply is forced into a JSON schema, number scenes keep their rule-built cards, and a scene that fails validation keeps the rule version. `think:false` is sent (thinking models otherwise return empty text). Model choice is automatic (best general text model installed, else sized to GPU memory); if no server runs locally a portable Ollama and the model are downloaded. Unreachable or off: rules plan, with an `ai_notice.json` shown on Review. About 2 minutes for 30 scenes with an 8B model. |
| Automatic design | `vt/designer.py`, `Pipeline._resolve_auto_theme` | Theme `auto` is resolved at the plan stage: the transcript's mood (meaning-based classifier) selects from per-mood looks and palettes, seeded by the project id, and is saved as a theme of its own. |
| Design Studio | `studio/src/pages/DesignStudio.tsx` | 10 looks x 18 palettes with contrast-checked text colours, 11 backgrounds (patterns, waves, rings, mesh, aurora; moving ones are driven by the paused timeline so renders stay frame-exact), soft shadows, Surprise me, Undo, saves with its style and palette recorded. |
| Text to video | `vt/tts.py`, pipeline stage `voice`, CLI `vt script`, `POST /api/projects/from-script` | Edge neural voices (online) or Meta MMS (offline, non-commercial); sentences spoken one by one and joined with natural pauses; word times spread over the real speech and snapped to loudness dips (about 0.1 to 0.15 s from recognition timings); the ASR stage is skipped. |
| Language-aware output | `vt/planner/rules.py` | Digits and the currency symbol follow the speaker's language and the currency actually spoken (taka, rupees, dollars...). |
| Sound effects library | `assets/sfx/`, `vt/sfxlib.py` | User-supplied packs classified into roles, 3 density tiers, seeded non-repeating choice, ducked music. |
| Installable app | `desktop/`, `studio/public/` (PWA), `.github/workflows/release.yml` | Electron shell with first-run bootstrap (portable uv + Node, npm run through node, ffmpeg bundled, no admin rights), user data separated with `VT_DATA` (projects, models, settings, custom themes, own music), NSIS / DMG / AppImage / deb builds. Windows installer built and the first-run setup verified on a clean folder (CPU path); macOS and Linux come from CI and have not been run by hand. |
| Settings | `studio/src/pages/LocalAI.tsx` | Local AI address, model, test, one-click setup job; Claude is now an optional extra. |

Bugs found and fixed in this round (each has a regression test): a corrupt preview audio file when the server and the pipeline built it at the same time (now written atomically); the projects list returning 500 on a server started before a schema change (restart required after updates); tests writing automatic themes into the real theme folder; scroll test depending on a project that no longer existed.

Deviations from the original plan: the app no longer depends on Claude (a local model is the default planner and Claude is optional), "Themes" became "Design Studio", and speech input is no longer the only way in (typed scripts).

Known weak spots: some local-AI picks are odd and abstract words fall back to big typography; the typed-script word timing is estimated; Bangla app text and music were not reviewed by ear or by a native speaker; the macOS and Linux installers are untested.

### Milestones

| | Status | Notes |
|---|---|---|
| M0 Spikes | done | HyperFrames renders Bangla correctly on Windows with NVENC; Bangla ASR benchmarked (below); both aspects; MCP round trip over real stdio. |
| M1 CLI end to end | done | All 7 pipeline stages + render/mux; 12 components, 7 transitions, 3 themes, both shapes, CC0 music/SFX, glossary + script policy. |
| M2 Claude planner via MCP | done | 20 MCP tools, request queue, validation loop with concrete errors, per-scene alternatives, `get_preview_frame`, `/vt-plan` command, skill file, `.mcp.json`. |
| M3 Studio core | done | Projects, New (record/upload/prompter), Progress, Review (preview, transcript editing, schema-driven inspector, undo/redo), Export. |
| M4 Design kit | done | Theme editor with live specimen, import/export, 12 elements, transitions, music ducking, SFX. |
| M5 Polish | done | Filler removal, script prompter, 16:9, `vt doctor`, setup/start scripts, README, golden render tests, browser tests. 1:1 and English UI polish were not done (English video uses a multilingual model but was not benchmarked). |

### Success criteria (section 13) against measurements

| Criterion | Result |
|---|---|
| 90 s Bangla recording → video in ≤ 5 min on this laptop | Processing: 48 s of audio in 21 s. Render: 35 s video in 62 s, so ~2.7 min for 90 s. **Met** (RTX 4050 6 GB; not run on a 90 s real recording). |
| ≥ 90% caption word accuracy before fixes | Synthetic clips: 93% (plain Bangla), 85% (Banglish, 33% error on English words). **Not established for real recordings**; no real recordings were available. |
| 100% correct Bangla glyph shaping | Golden test with conjunct-heavy text (ক্ষ্মী স্ত্রী জ্ঞান দ্বন্দ্ব ঊর্ধ্বে র‍্যাঙ্ক…) verified by eye and pixel-compared in CI. **Met.** |
| New visual element at least every ~6 s | Enforced by the planner brief and rule planner; not measured on real content. |
| Word fix / scene change visible in the preview in < 1 s | Hot-swap of composition data without reload: measured ≈ 0.3–1.5 s including the 500 ms inspector debounce. **Met.** |

### ASR bake-off (synthetic Bangla/Banglish speech, same pipeline code for both models)

| clip | model | word error | Bangla words | English words | speed |
|---|---|---|---|---|---|
| plain Bangla (14 s) | bn-medium | **7%** | 8% | 0% | 1.6× realtime incl. model load |
| plain Bangla | large-v3 | 50% | 44% | 80% | 1.2× |
| Banglish (17 s) | bn-medium | **15%** | 7% | 33% | 1.8× |
| Banglish | large-v3 | 51% | 44% | 67% | 1.1× |

`large-v3` also produced misspellings and a truncated ending, so the planned "merge both models per word" idea was dropped: its only
strength (English in Latin letters) is covered by the term dictionary, and both models mishear the same terms (rent, maintenance, tax).

### Deviations from the plan, and why

1. **Renderer: HyperFrames, not Revideo** (decided in the plan after checking maintenance) — confirmed in practice. Playwright fallback was not needed and is not built.
2. **Bangla model must decode without timestamp tokens.** Verified against the original Hugging Face model: with timestamps it clips the first word and
   hallucinates a tail; without them output is correct. Word times therefore come from attention alignment (faster-whisper), then are **snapped to the real
   speech energy** (`stages/align.py`): stretched word ends are clipped to where speech stops and words "heard" in silence are dropped. This replaces the
   planned WhisperX / MMS forced-alignment stage (its dependency did not build on Windows, and snapping proved sufficient on test material).
3. **Own chunking** (`stages/chunks.py`): the model drops words on merged 30 s windows (a 48 s clip lost 20% of its words). Audio is cut at pauses into ≤ 15 s
   pieces; each is transcribed separately. A neural Silero VAD gate stops it inventing text from noise.
4. **No glossary prompt.** Priming the model with glossary words made it skip sentences and loop. The glossary is applied word by word after recognition.
5. **Banglish via a term dictionary + script policy** (`design/terms.json`, `stages/terms.py`) instead of merging two models (see above). Matching is done in NFC:
   the model emits য় as one code point while typed lists use two, which silently broke matching until a test caught it.
6. **Plans survive re-cuts.** If sentence boundaries move (pace change, filler removal, a cut word), scenes are remapped onto the new sentences by word ownership;
   only if that is impossible is a rules draft made, with a visible notice and the old plan saved as `scenes.invalid.json`.
7. **MCP only**, as decided: the Studio queues requests, Claude Code answers them. Heartbeat (`Claude connected`) lives in the projects folder.
8. **Themes live in `design/themes/`** (not `themes/`), fonts and icons in `design/`; a built-in specimen composition powers the theme editor.
9. **Server-side undo is single-level (`scenes.prev.json`); the Studio keeps a multi-level undo stack** per session.
10. **Export extras** added beyond the plan: 720p downscale, 60 fps, captions on/off, `.srt`.

### Bugs found by testing (kept as regression tests)

First-word clipping and hallucinated tails (model + timestamp tokens) · long-audio truncation · Unicode normalisation of Bengali · uploads silently not
starting (omitted boolean form field is `false` in current FastAPI) · a background thumbnail job redirecting Review to Progress · preview iframe stealing
keyboard focus · job objects not JSON-serialisable · traceback text shown to users · tests polluting the real "Claude connected" status · a syntax error in a
rarely-tested module (now every module is imported by a test) · PowerShell `npm.ps1` argument mangling in the setup script.

### Phase 3 (2026-10-22): links, clipart, subtitles

| Item | Status | What exists |
|---|---|---|
| Video from a link | done | `vt/ingest.py` (yt-dlp): audio + subtitles, public addresses only, 40 min limit, friendly errors; `vt link`, `POST /api/projects/from-link` (job), MCP `import_link`, Studio tab *From a link*. Origin saved in project.json and in `.credits.txt`. Tested with real NASA (YouTube), LibriVox (archive.org mp3) and a Bangla YouTube video. |
| Subtitles as the transcript | done | json3 (word-level for automatic captions) and vtt parsed to the recogniser's format; modes auto / any / off. Auto English captions are skipped (visible errors such as "black doors"); the local model is used instead. |
| Drawn clipart | done | `vt/art/`: 31 coded drawings with English and Bangla words, preferred by the picker (also two-word ideas), the LLM chooser, search and MCP. Bugs found by real videos and fixed: pronoun contractions as keywords, fragments mistaken for questions/definitions/CTAs, education detection, the soft first word after a pause being dropped by word snapping. |
| Image generation | evaluated, not shipped | SD-Turbo (fp16, 0.5 s/picture on the RTX 4050): good for concrete objects, poor for space/abstract ideas, noisy backgrounds. Revisit with a better model or a bigger GPU. |
| Pixabay clipart search | done | Media bin *Clipart* kind (vector images). |

### Not done / open

* Real-recording accuracy and timing are unmeasured. Bring 3–5 clips (30–60 s, your microphone, your accent, your usual English terms) and run
  `python scripts/asr_bakeoff.py bn-medium my-clip.wav` with the true text in `my-clip.txt` next to it.
* Bundled music/SFX are procedurally generated and were never listened to; the Bangla UI strings are machine-drafted.
* No installer beyond `scripts/setup.ps1`; macOS/Linux untested.

---

## 0. Verified facts this plan relies on

| Fact | Status | Impact |
|---|---|---|
| No open-source app does recording → designed scenes → video | Searched; closest are Hypnotype (closed SaaS), anything2explainer, remotion-video-skill, template-prompt-to-video (all start from a topic, not your voice) | We build it |
| **HyperFrames** (HeyGen): HTML + CSS + GSAP → MP4 via headless Chrome + FFmpeg, **Apache 2.0**, ships agent skills for Claude Code | Confirmed by several sources; check LICENSE in repo at M0 | **Chosen renderer** |
| Revideo (MIT) | Repo appears to have moved (redotvideo → midrender); recent activity unclear | Dropped as primary |
| Remotion | Free only for individuals / companies of ≤3 people; licence changes in v5 | Fallback only |
| Best Bangla ASR found: `tugstugi/bengaliai-asr_whisper-medium` (lowest WER in a March 2026 long-form study), word timings via **WhisperX** alignment | Paper-reported; timestamp accuracy not measured, so benchmark in M0 | Chosen ASR, with `large-v3` as comparison |
| Machine: RTX 4050 Laptop 6 GB, Ryzen 5 7535HS, 39 GB RAM, Node 22.20, FFmpeg 9.0.1, Python 3.14.7 | Checked locally | Whisper-medium fp16 fits in 6 GB. **Python 3.14 is too new for torch/CTranslate2 wheels → use a Python 3.11 venv via `uv`** |

---

## 1. Goals and non-goals

**Goals**
- Input: one audio file (recorded in the app or uploaded). Output: finished MP4 + .srt.
- Fully open-source stack. Claude is the only external service, and it's optional (offline fallback).
- Automatic: loudness normalisation, silence/filler cuts, word-timed captions, scene layout, transitions, music ducking.
- Correct Bangla rendering (conjuncts, vowel signs), guaranteed by browser text shaping.
- Design is data: a theme (CSS variables) + a component library the user can edit in the app.
- Fast iteration: edit a word or a scene and see the preview instantly. Only final export takes render time.

**Non-goals (v1):** timeline editor, avatars, AI-generated footage, voice cloning, cloud hosting, multiple users.

---

## 2. System architecture

```
┌──────────────────────── Studio (browser) ─────────────────────────┐
│ React + Vite + Tailwind + shadcn/ui                                │
│ Screens: Projects · New · Progress · Review · Themes · Export · ⚙  │
│ Preview = <iframe> of the SAME HyperFrames HTML composition,       │
│           GSAP timeline scrubbed in sync with the audio            │
└──────────────▲───────────────────────────────▲─────────────────────┘
               │ REST                          │ WebSocket (job events)
┌──────────────┴───────── Local server (Python 3.11, FastAPI) ───────┐
│ Project store (projects/<id>/)    Job queue (1 GPU worker)          │
│ Stages: preprocess → vad/cuts → asr → align → beats → plan → build │
│ Planner: requests queue ⇄ MCP ⇄ Claude Code | rule-based fallback   │
│ Composer: scenes.json + theme → composition HTML (Jinja templates)  │
└──────────────┬─────────────────────────────────────────────────────┘
               │ subprocess
┌──────────────┴──── Renderer (Node 22) ─────────────────────────────┐
│ HyperFrames CLI → headless Chrome frames → FFmpeg encode            │
│ Fallback: own Playwright frame-capture + FFmpeg (same HTML)         │
└────────────────────────────────────────────────────────────────────┘
MCP server (Python) exposes the same operations to Claude Code / Desktop
```

Key design decision: **one HTML composition is both the preview and the render source.** No second rendering model, no drift between what you see and what you export.

---

## 3. Pipeline, stage by stage

Each stage reads/writes files in `projects/<id>/`, is idempotent, and records a hash of its inputs in `project.json` so that re-running only redoes stale stages.

### Stage 1 — Ingest & preprocess
- Accept wav/mp3/m4a/webm (browser recordings are webm/opus).
- FFmpeg: convert to 48 kHz stereo WAV master; loudness normalise to −16 LUFS (two-pass `loudnorm`); optional light denoise (`afftdn`) + high-pass at 80 Hz.
- Also write a 16 kHz mono copy for ASR.
- Output: `audio.master.wav`, `audio.asr.wav`.

### Stage 2 — Voice activity + cut list
- silero-vad on the 16 kHz copy → speech regions.
- Cut silences longer than `pace.silence_max` (Calm 0.6 s / Normal 0.35 s / Fast 0.2 s), keeping 80 ms padding on each side.
- Output `cuts.json`: list of kept `[start, end]` ranges in source time + a monotonic map from source time to output time.

### Stage 3 — Transcribe
- WhisperX with `tugstugi/bengaliai-asr_whisper-medium` (converted to CTranslate2, fp16 on GPU). Language forced to `bn`.
- Runs on the **uncut** ASR audio (better context), with VAD chunking.
- Initial prompt / hotwords: project glossary (e.g. "ইয়েল্ড, গ্রস, ভাড়া") to bias spelling.

### Stage 3a — Banglish (code-mixed) handling
Speech mixes Bangla and English ("খরচ বাদ দিয়া পকেটে যেটা থাকবে, সেটাই net yield").
- **Model risk:** a Bangla-only fine-tune tends to force English words into Bangla script or garble them; `large-v3` handles English better but Bangla worse. M0 bake-off scores both on **code-mixed** clips, and also a third option: run both and merge per word (keep the higher-confidence word, prefer `large-v3` for words detected as English).
- **Script policy (project setting):**
  - `mixed` (default): Bangla in Bangla script, English terms in Latin script ("net yield").
  - `bangla`: transliterate English into Bangla script ("নেট ইয়েল্ড"), as in the reference frame.
  - Normalisation through a per-project + global **glossary** (`glossary.json`: `{"yield": "ইয়েল্ড", "gross": "গ্রস"}`), which is also used as ASR hotwords.
- **Fonts:** every theme pairs a Bangla font with a matching Latin font, so mixed lines look consistent (e.g. Hind Siliguri + Inter, Baloo Da 2 + Baloo 2). The composer wraps Latin runs in a `lang="en"` span.
- **Fillers** include English ones (um, uh, like, you know).
- **Planner** keeps terms in the speaker's script choice; never translates.

### Stage 4 — Word alignment
- WhisperX forced alignment with a Bangla wav2vec2 CTC model for word-level times.
- If no good Bangla aligner is available in M0: use Whisper's own word timestamps + a heuristic re-snap to VAD edges.
- Map every word time through `cuts.json` → output timeline. **This is the only place timings are remapped.**
- Words inside removed regions are dropped. Words with low confidence get `"flag": "review"`.
- Output `transcript.json`.

### Stage 5 — Filler removal (optional)
- Fillers list per language (bn: উম, আ, এ্যা, মানে-repeats; en: um, uh, like-repeats) + immediate repeated words.
- Mark them `cut: true`; extend `cuts.json`; re-map.

### Stage 6 — Beats
- Split into sentences on punctuation from ASR, otherwise on pauses > 0.5 s, max 12 words per beat.
- Output `beats.json`: `[{id, start, end, word_ids}]`.

### Stage 7 — Scene planning
See section 6. Output `scenes.json`, validated.

### Stage 8 — Compose
- Python composer turns `scenes.json` + `themes/<name>/theme.json` into `composition/index.html`:
  - Theme → CSS custom properties.
  - Each element → its component's HTML partial (Jinja) with a `data-*` timing attribute.
  - One master GSAP timeline built by `runtime.js` from the element timings; transitions between scenes.
  - Captions built from transcript words (word spans, karaoke highlight, accent pill on highlight words).
  - Fonts loaded locally with `@font-face`; `document.fonts.ready` awaited before the first frame.
- Output: a self-contained folder the Studio iframe loads and HyperFrames renders.

### Stage 9 — Render
- Preview: none needed (live iframe).
- Final: HyperFrames CLI at 1080×1920, 30 fps (60 optional) → `render.mp4` (silent). Chunked parallel render if supported; otherwise Playwright fallback with N parallel pages, each rendering a frame range.
- Encoder: h264_nvenc on the RTX 4050, libx264 fallback.

### Stage 10 — Audio mix & mux
- FFmpeg: apply `cuts.json` to `audio.master.wav` with 10 ms crossfades at each cut (no clicks).
- Optional music bed: `sidechaincompress` ducking under voice, music −22 dB under speech, fade in/out.
- Optional SFX: soft "pop" on element entrances (from the theme's SFX pack), −18 dB.
- Mux with `render.mp4` → `final.mp4` (AAC 192k, `+faststart`). Also write `final.srt` from the transcript.

---

## 4. Data contracts

All schemas live in `vt/schema.py` (pydantic). JSON Schema is exported for the planner prompt and the Studio forms.

### project.json
```json
{ "id": "2026-10-21-yield", "title": "ইয়েল্ড কী", "language": "bn",
  "aspect": "9:16", "theme": "paper", "pace": "normal",
  "options": { "remove_fillers": true, "music": "lofi-01", "sfx": true },
  "stages": { "asr": { "hash": "…", "done_at": "…" } } }
```

### transcript.json
```json
{ "language": "bn",
  "words": [ { "id": "w17", "text": "থাকবে", "start": 15.82, "end": 16.21,
               "conf": 0.91, "flag": null, "cut": false } ] }
```

### scenes.json
```json
{ "format": { "width": 1080, "height": 1920, "fps": 30 },
  "theme": "paper",
  "scenes": [
    { "id": "s3", "beats": ["b5", "b6"], "start": 12.4, "end": 18.9,
      "layout": "stack",
      "transition_in": "slide_up",
      "elements": [
        { "id": "e1", "type": "title",      "text": "ইয়েল্ড", "at_word": "w9" },
        { "id": "e2", "type": "value_card", "value": "৳১০০", "label": "দোকানের দাম", "at_word": "w11" },
        { "id": "e3", "type": "arrow",      "direction": "down", "at_word": "w13" },
        { "id": "e4", "type": "icon_row",   "icon": "coin", "count": 3, "label": "বছরে ভাড়া", "at_word": "w14" },
        { "id": "e5", "type": "tag",        "text": "৪ = গ্রস", "at_word": "w16" }
      ],
      "caption": { "highlight_words": ["w17"] } } ] }
```
Rules:
- Times are referenced as **word ids** (`at_word`), so timing survives transcript edits and re-cuts. Seconds are derived at compose time.
- Captions are never written by the planner; they come from the transcript.
- Each component declares a max text length; overflow fails validation.
- Max 5 visible elements per scene (layout constraint).

---

## 5. Design system (the video's look)

### 5.1 Theme (`themes/<name>/theme.json` → CSS variables)
- `color`: bg, ink, muted, accent, accent2, card, card_border, caption_bg, caption_ink, highlight_bg, highlight_ink
- `font`: headline, body, numeral (local files in `themes/<name>/fonts/`, OFL)
- `shape`: radius, stroke, shadow, card_tilt_deg
- `background`: kind (paper | flat | gradient | grid), texture strength, decorative arcs on/off
- `motion`: preset (snappy | smooth | bouncy) → GSAP ease, durations, stagger
- `caption`: style (box | pill | underline | none), position (bottom | middle), max lines, words per line
- `sfx`: pack name or none

Starter themes: **Paper** (reference look), **Dark Neon**, **Clean Minimal**.

### 5.2 Component library (`renderer/components/`)
Each component = `component.json` (fields, limits, description for the planner) + `partial.html` (Jinja) + `anim.js` (enter/exit GSAP functions).

| Component | Fields | Use |
|---|---|---|
| `title` | text | topic/keyword heading |
| `value_card` | value, label | a price or number with context |
| `big_number` | value, unit, label | single striking stat |
| `arrow` | direction, label? | cause → effect |
| `icon_row` | icon, count, label | repeated units (coins, people, years) |
| `tag` | text | highlighter formula/label |
| `compare` | left{title,value}, right{title,value}, verdict? | A vs B |
| `list` | items[≤4] | steps or points |
| `equation` | parts[] | "আয় − খরচ = লাভ" |
| `quote` | text, by? | a statement to stress |
| `bar_chart` | bars[≤5]{label,value} | small numeric comparisons |
| `icon` | name, label? | single concept |
| `caption` | (automatic) | always present |

Layouts: `stack` (vertical centre, as in the reference), `split` (two columns), `hero` (one big element). Composer arranges elements, the planner only picks one.

Icons: Lucide + Tabler SVGs (ISC/MIT), plus a small custom set (৳ coin, shop, house). The icon list is given to the planner.

Transitions: `cut`, `fade`, `slide_up`, `slide_left`, `zoom`, `wipe`, `whip` (with motion blur). Within a scene: elements enter staggered at their word; on scene end, all exit together.

### 5.3 Two aspect ratios (9:16 and 16:9)
- One `scenes.json` per project. Aspect is a **compose-time** choice, so the same plan exports both.
- Each layout has two arrangements:
  - `stack`: 9:16 vertical column (reference); 16:9 places the main element left and secondary elements right.
  - `split`: 9:16 top/bottom; 16:9 left/right.
  - `hero`: centred in both, scaled.
- Captions: 9:16 bottom box above the safe area (clear of Reels/Shorts UI); 16:9 lower third, max 2 lines, wider lines.
- Type scale tokens per aspect (`--size-title-916`, `--size-title-169`, …).
- Studio: aspect switch in Review shows the other layout live; Export can render **both** in one job.
- Golden tests run in both aspects.

### 5.4 Music & SFX library
- Ship 8–12 CC0 tracks (moods: calm, upbeat, corporate, lo-fi, tense) + an SFX pack (pop, whoosh, click, ding). Sources: CC0-only libraries (e.g. Pixabay-style CC0 or freepd.com, with each file's source and licence checked and recorded in `assets/LICENSES.md`).
- `assets/music/index.json`: title, mood, BPM, length, loop points, source URL, licence.
- Users can import their own tracks (stored in `assets/music/user/`, not distributed).
- Music loops/crossfades to fit the video length; auto-ducked under voice; ends with a fade on the last scene.

---

## 6. Scene planner

### 6.1 Claude planner (MCP only, no API key)
The app never calls Claude. Claude Code (or Claude Desktop) connects to our MCP server and does the planning. The MCP server is the bridge between Claude and the app.

**Flow:**
1. Pipeline finishes transcription. Project status becomes **"Waiting for Claude"**, and a rule-based plan is composed at once so the preview is never empty.
2. Planning requests are queued in `projects/<id>/requests/` (full plan, or one scene regenerate with a hint from the Studio).
3. In Claude Code the user says "plan my pending videos" (or runs the `/vt-plan` slash command we ship). Claude calls:
   - `list_pending_requests` → `get_planning_task(request_id)`: beats, catalogue, rules, schema (the prompt lives server-side, so it's versioned with the code)
   - `submit_scenes(request_id, scenes)`: server validates; on errors it returns them and Claude fixes and resubmits.
4. Server saves `scenes.json`, recomposes, and pushes a WebSocket event. The Studio preview updates live.

**Studio UX for this:**
- "Plan with Claude" and "Regenerate scene" buttons create a request and show a banner: *"Request queued, ask Claude Code: plan pending videos"* with a copy button for that sentence.
- Request list with status (queued / in progress / done / failed).
- **Optional watch mode:** the shipped `/vt-plan` command can be used with Claude Code's `/loop`, so pending requests get picked up automatically while a Claude Code session is open.
- Everything else (cuts, transcript, render) works without Claude. Rule planner stays the offline default.

**Input given to Claude:** beats with word ids/text, component catalogue (generated from `component.json` files), layouts, icon list, pace, aspect(s), script policy, glossary, previous scene types (for variety).
**Output:** JSON matching `scenes.json`, sent through `submit_scenes`.
- Prompt rules:
  - 1–3 beats per scene, 3–8 s each; never >10 s without a new element.
  - Pull labels from the speaker's own words; translate nothing.
  - Numbers/money/comparisons → visual components; abstract talk → title/icon/quote.
  - One highlight word per caption line: the key noun/verb.
  - No two consecutive scenes with the same layout + main component.
- Validation: pydantic + custom checks (word ids exist, ordered, text lengths, element count, layout fits both aspects). Errors go back to Claude through `submit_scenes`; after 3 failed tries, that scene keeps the rule-planner version.
- **Per-scene regenerate:** the task includes neighbouring scenes + the user's hint ("make it a comparison"); Claude submits up to 3 alternatives, and the Studio shows them as thumbnails to pick from.

### 6.1b Local AI planner (default when Claude is not connected)

Order of planners for a new video: an existing Claude/manual plan is kept; otherwise the local AI plans (see the status table); if it is off or unreachable the rule planner (6.2) plans. Claude can still replace any plan through MCP at any time. The brief and the candidate pictures given to the local model are the same data Claude receives (`visual_suggestions`, `search_icons`).

### 6.2 Rule-based planner (offline / fallback)
- Regex detection: currency/numbers → `value_card`/`big_number`; "vs/বনাম/চেয়ে" → `compare`; enumerations → `list`; otherwise `title` with the beat's keyword (longest non-stopword).
- Always produces a valid video.

### 6.3 MCP server (`vt-mcp`)
Transport: stdio (registered with `claude mcp add vt -- uv run vt-mcp`). It talks to the running local server, or works directly on project folders if the Studio is closed.

Tools:
- Planning: `list_pending_requests`, `get_planning_task`, `submit_scenes`
- Projects: `list_projects`, `create_project(audio_path, options)`, `run(project, from_stage?)`, `project_status`
- Editing: `get_transcript`, `fix_word(word_id, text)`, `add_glossary_term`, `get_scenes`, `update_scene(scene_id, patch)`, `request_regenerate(scene_id, hint)`
- Design: `list_components`, `list_themes`, `get_theme`, `update_theme(patch)`
- Output: `render(project, aspect, quality)`, `get_preview_frame(project, time)` (PNG, so Claude can see what it made and self-correct)

Also shipped: a `/vt-plan` slash command and a skill file (`.claude/skills/video-tool/SKILL.md`) explaining the components and planning rules, so Claude plans consistently.

---

## 7. App (Studio) design

### 7.1 Principles
- Linear flow: **Record → Review → Export.** One primary button per screen.
- Never a timeline; edits happen on words and scenes.
- Instant feedback: every edit re-composes the HTML (~100 ms) and the iframe reloads at the same timestamp.
- Bilingual UI (English / বাংলা).

### 7.2 Screens

**1. Projects (home)**
Grid of cards (thumbnail = first scene, title, duration, status chip Draft/Planned/Exported, edited date). Primary: **New video**. Secondary: Themes, Settings. Search + sort.

**2. New video**
- Tabs **Record** / **Upload**.
  - Record: mic selector, live level meter, too-quiet/clipping warnings, record/pause/stop, retake, playback. Optional **script prompter** panel (paste notes, shown large while recording).
  - Upload: drag-and-drop, file info.
- Options: title, language, aspect (9:16 / 16:9 / 1:1), theme (thumbnail picker), pace (Calm/Normal/Fast), remove fillers, music (preview buttons), SFX on/off, glossary words.
- Primary: **Generate**.

**3. Progress**
Stepper: Cleaning → Cutting → Transcribing → Aligning → Planning → Composing. Live % via WebSocket, transcript streams in, elapsed time + ETA. Cancel. Errors are shown in plain language with **Retry step**. When done, opens Review automatically.

**4. Review (main workspace)**
```
┌──────────────┬───────────────────────────────┬───────────────────────┐
│ SCENES       │          PREVIEW              │ INSPECTOR             │
│ ┌──────────┐ │   ┌───────────────────────┐   │ Scene 3 · 12.4–18.9 s │
│ │1 ▢ title │ │   │                       │   │ Layout  [stack ▾]     │
│ ├──────────┤ │   │     9:16 iframe       │   │ Transition [slide ▾]  │
│ │2 ▢ card  │ │   │                       │   │ ─ Elements ─────────  │
│ ├──────────┤ │   │                       │   │ ▸ title  "ইয়েল্ড"     │
│ │3 ▣ stack │ │   └───────────────────────┘   │ ▸ value_card ৳১০০     │
│ ├──────────┤ │  ◀◀ ▶ ▶▶  00:14 ━━●━━ 01:24   │ ▸ arrow ↓             │
│ │4 ▢ list  │ │  ─────────────────────────    │ ▸ icon_row coin×3     │
│ └──────────┘ │  TRANSCRIPT                   │ + Add element         │
│ + Split here │  …খরচ বাদ দিয়া পকেটে যেটা     │ [↻ Regenerate] [hint] │
│              │  [থাকবে] …  (amber = check)   │                       │
└──────────────┴───────────────────────────────┴───────────────────────┘
 Theme: Paper ▾   Pace: Normal ▾                    [ Export ▸ ]
```
- **Scenes:** thumbnails with time ranges; click to seek; drag a scene boundary onto another word; split/merge/delete/duplicate via menu.
- **Preview:** play/pause, scrub, 0.5–2× speed, safe-area overlay toggle (for Reels/Shorts UI), mute music.
- **Transcript:** karaoke follow; click word = seek; double-click = edit text; right-click = highlight / cut word / restore / add to glossary. Low-confidence words underlined amber; a "Next to check" button cycles through them.
- **Inspector:** forms generated from each component's JSON Schema (text, number, icon picker, count stepper, enum dropdowns). Element timing = pick a word from a dropdown or click "set to playhead". Drag to reorder elements.
- **Regenerate:** optional hint, shows 3 alternative thumbnails, click to apply.
- Undo/redo (command stack), autosave.

**5. Themes (design kit editor)**
- Left: token controls (colour pickers with contrast check, font pickers with Bangla preview, radius/stroke/shadow sliders, background kind, motion preset, caption style/position, SFX pack).
- Right: live **specimen** composition using every component + a sample text box + "preview with project…" to try the theme on a real video.
- Duplicate / rename / export `.vttheme` (zip of theme.json + fonts) / import. Set as default.

**6. Export**
Resolution (720p / 1080p), fps (30/60), encoder (NVENC/CPU), captions burned-in (on by default) + `.srt` sidecar, music volume. Progress with ETA; finish card with player, Open folder, Copy path. Exports go to `projects/<id>/exports/` with a timestamp.

**7. Settings**
Claude Code connection status (MCP server seen recently, pending requests count, a copyable `claude mcp add` command), ASR model manager (download/verify/switch), GPU detection, default theme/aspect/pace/export folder, UI language.

### 7.3 Studio visual design
- Quiet chrome so the video stands out: warm neutral greys, single orange accent (#F26B1D-ish) matching Paper, light + dark mode.
- Inter for UI, Hind Siliguri for Bangla UI. 8-px grid, 12-px radius, 1-px borders, minimal shadows.
- Status: green done, amber review, red error.
- Keyboard: Space play/pause · ←/→ word · J/K scene · E edit word · H highlight · R regenerate · Ctrl+Z / Ctrl+Shift+Z · Ctrl+Enter export.
- Accessibility: AA contrast, visible focus, everything keyboard-reachable, reduced-motion mode for app UI.

---

## 8. Repo layout

```
Video Tool/
  plan.md
  README.md
  pyproject.toml            # uv-managed, Python 3.11
  vt/
    cli.py                  # Typer: new, run, render, studio, doctor
    config.py
    schema.py               # pydantic contracts
    project.py              # store, stage hashing
    stages/
      preprocess.py  vad.py  asr.py  align.py  fillers.py  beats.py
    planner/
      claude.py  rules.py  prompt.py  catalogue.py
    compose/
      composer.py           # scenes + theme → HTML
      templates/            # base.html.j2
    render/
      hyperframes.py  playwright_fallback.py  mux.py
    server/
      app.py  jobs.py  ws.py
    mcp/
      server.py
  renderer/                 # Node side
    package.json            # hyperframes, gsap, playwright
    runtime.js              # builds master GSAP timeline
    components/<name>/{component.json, partial.html, anim.js, style.css}
    transitions/
    icons/
  themes/
    paper/  dark-neon/  minimal/
  assets/
    music/  sfx/            # CC0 only, with a LICENSES.md
  studio/                   # React + Vite app
  samples/                  # test recordings + expected outputs
  tests/
  projects/                 # gitignored
```

---

## 9. Setup & tooling

- `uv` → Python 3.11 venv (system 3.14 stays untouched).
- PyTorch CUDA 12.x build for WhisperX; CTranslate2 with cuDNN 9.
- Node 22 (already installed); `npm i` in `renderer/` and `studio/`; Playwright downloads Chromium.
- FFmpeg 9 (already installed; check `h264_nvenc`).
- `vt doctor`: checks GPU/CUDA, FFmpeg encoders, Node, Chromium, models downloaded, fonts present, API key.
- One-command start: `vt studio` (starts FastAPI + serves the built Studio).

---

## 10. Testing & quality

- **Unit:** cut-map remapping (property tests: monotonic, no word outside kept ranges), schema validation, composer output, rule planner.
- **Golden tests:** fixed `scenes.json` → render 5 frames → compare against reference PNGs (pixel diff threshold). Includes a Bangla stress string with many conjuncts ("ক্ষ্ম, ন্ত্র, স্ত্রী, জ্ঞ, রু, র্ক").
- **ASR benchmark:** `samples/` with 5 hand-transcribed clips (different mics, speeds, code-mixed Bangla-English). Track WER + median word-start error (target < 80 ms).
- **Planner eval:** 10 transcripts → check validity rate (target 100% after retry), variety score, and a manual 1–5 rating sheet.
- **Added suites:** visuals/dictionary, designer (every look x palette is readable), TTS, local-AI planner with a fake model (never invents, survives garbage and outages), pipeline-level AI fallback, preview-audio concurrency; browser checks `flows`, `design`, `scroll`, `export`, `journey`.
- **E2E:** CLI run on a 30 s sample in CI-style script; checks final.mp4 duration ≈ cut audio ± 1 frame and A/V sync.
- **Performance budget (90 s video on this laptop):** preprocess+VAD < 10 s, ASR+align < 40 s, planning < 30 s, final 1080p render < 3 min.

---

## 11. Milestones

**M0 — Spikes (2–3 days)**
1. Install HyperFrames; confirm LICENSE, a headless render works on Windows, and how it splits work across parallel chunks.
2. Hand-build the reference frame as HTML/GSAP; render 5 s; verify Bangla shaping + fonts.
3. ASR bake-off on 3–5 real **Banglish** clips: bengaliai whisper-medium vs large-v3 vs per-word merge of both (+ WhisperX alignment). Record WER separately for Bangla and English words, timing error, speed, VRAM.
4. Render the reference frame in both 9:16 and 16:9.
5. Minimal MCP round trip: Claude Code calls `get_planning_task` → `submit_scenes` on a sample.
6. Decide aligner, and confirm Playwright fallback works if HyperFrames is blocked.

**M1 — CLI end to end**
Stages 1–10 with the rule planner; components: title, value_card, arrow, icon_row, tag, caption; transitions: cut, fade, slide_up; Paper theme in both aspects; glossary + script policy; 3 CC0 tracks with ducking. `vt run` produces a watchable video.

**M2 — Claude planner via MCP**
MCP server, request queue, catalogue generation, `get_planning_task`/`submit_scenes` with validation loop, `/vt-plan` command + skill file, per-scene regenerate with alternatives, `get_preview_frame`.

**M3 — Studio core**
FastAPI + jobs + WebSocket; Projects, New (record/upload), Progress, Review (preview + transcript editing + inspector), Export.

**M4 — Design kit**
Theme editor with specimen; Dark Neon + Minimal themes; remaining components (big_number, compare, list, equation, quote, bar_chart, icon); more transitions; music ducking + SFX.

**M5 — Polish**
Remaining MCP tools (design/theme editing), filler removal, script prompter, full CC0 music/SFX library, 1:1 layout, `vt doctor`, README, packaging (single installer script).

---

## 12. Risks & mitigations

| Risk | Mitigation |
|---|---|
| HyperFrames API changes, or it has Windows problems | Composition is plain HTML + GSAP; own Playwright frame-capture fallback renders the same files |
| Bangla ASR errors (dialect, code-mixing) | Bangla fine-tune + glossary prompt + amber review flow; captions always from the corrected transcript |
| Weak Bangla forced alignment | Fallback to Whisper word timestamps + VAD snapping; measure in M0 |
| Torch/CTranslate2 vs Python 3.14 | Isolated Python 3.11 venv via uv |
| 6 GB VRAM | Medium model fp16; unload ASR before render; large-v3 int8 only if needed |
| Repetitive/boring scenes | Variety rules, previous-scene context, regenerate with alternatives |
| Render time | Parallel chunk rendering, NVENC, 720p drafts |
| Asset licences | Only OFL fonts, ISC/MIT icons, CC0 music/SFX; `LICENSES.md` |
| Remotion licence if ever used | Only as fallback; free tier ≤3 people |
| Banglish ASR mangles English terms | Per-word merge with large-v3, glossary hotwords, script policy normalisation |
| MCP-only planning needs a Claude Code session open | Rule plan always ready; clear "waiting for Claude" state; `/loop` watch mode |
| Layout overflow in one aspect only | Validation checks both aspects; golden tests in both |

---

## 13. Success criteria (v1)

- 90 s Bangla recording → finished 1080p video in ≤ 5 min on this laptop, zero manual steps required.
- ≥ 90% caption word accuracy before fixes; 100% correct Bangla glyph shaping in golden tests.
- A new visual element at least every ~6 s; output recognisably matches the reference style.
- Any word fix or scene change visible in the preview in < 1 s.

---

## 14. Decisions (answered 2026-10-21)

1. **Aspect:** both 9:16 and 16:9 in v1 (1:1 later). See 5.3.
2. **Language:** Banglish (Bangla speech with many English terms). See 3.3a.
3. **Claude:** MCP only, no API key. The app never calls Claude directly. See 6.1.
4. **Music:** ship a small CC0 library; users can also add their own. See 5.4.

---

## Sources checked
- HyperFrames: https://themenonlab.blog/blog/heygen-hyperframes-video-as-code · https://www.noqta.tn/en/blog/heygen-hyperframes-html-to-mp4-ai-agent-video-2026
- Revideo: https://docs.re.video/ · https://cdn.jsdelivr.net/gh/midrender/revideo@main/README.md
- Remotion licence: https://www.remotion.dev/docs/pricing · https://github.com/remotion-dev/remotion/blob/main/LICENSE.md
- Bangla ASR: https://arxiv.org/pdf/2603.03158 · https://arxiv.org/html/2603.04809v1 · https://www.alphaxiv.org/abs/2605.08214v1 · https://huggingface.co/bangla-speech-processing/BanglaASR
- Similar tools: https://futuretools.io/tools/hypnotype · https://github.com/remotion-dev/template-prompt-to-video · https://github.com/codewithdark-git/faceless-short


---

## Phase 12 plan (2026-10-23): take in video-shotcraft (motion library, sound, beat sync, QA rules, exports)

Owner: "we have an open source product on GitHub, https://github.com/Vincentwei1021/video-shotcraft, something we can use here too; incorporate the whole thing into our plan; as it is open source you can directly take its code." Read on 2026-10-23 (commit `43bd349`, Apache-2.0). The library is copied unmodified into `third_party/video-shotcraft/` with its LICENSE and a `NOTICE.md` (Apache-2.0 asks for exactly that: keep the licence, keep notices, say what was changed); `scripts/build_shotcraft_index.py` writes `third_party/video-shotcraft/index.json` (124 cards: name, category, description, duration, energy, reference implementation).

### P12.0 What it is, and what we take (measured by reading it, not guessed)

It is a Claude Code / Codex skill that makes **product promo films** with Remotion (React): a library of **124 recipe cards = 150 shots** in 10 categories (typography 22, ui-entrance 21, transition 15, effects 15, opening 11, interaction 11, camera 10, rhythm 8, outro 6, data 5), each a written recipe (timing in frames, easing curves, parameter table, known pitfalls) plus a Remotion implementation; **149 sound effects in 16 categories and 5 music tracks** (Mixkit licences; a few files have no recorded source); a method for **beat-sync** (fit an exact beat grid, put cuts within 3 frames), **sound design** rules, **aesthetic rules** (R/Q/S, e.g. minimum caption height 5 % of frame, a held wordmark 1 s, full-frame beat hits at most 3 per film), a **final-review** checklist, **sequences** (the energy arc of a whole film), a **JianYing (CapCut CN) draft exporter** (pyJianYingDraft), an **Upload-Post social publisher**, and a browser **Motion Workbench**.

Fit with this product (a voice or script becomes a faceless explainer; our renderer is HyperFrames = HTML + GSAP, our edit surface is the Studio):

| Part | Decision | Why |
|---|---|---|
| Transition cards (15 cards, about 30 techniques) | **Port** | we have 7 transitions (`cut fade slide_up slide_left zoom wipe whip`); a visible change at least every 3 s (hard rule) needs many more, and they are pure CSS/GSAP ideas |
| Typography, effects, rhythm, data, opening/outro, camera, ui-entrance cards | **Port in waves**, by retention value (see P12.2) | they are the "something happens" vocabulary; each becomes a named recipe the planner can pick |
| SFX (149) and BGM (5) | **Take as they are** (P12.3) | our sound library is smaller; the 16 categories give the sound planner a vocabulary |
| Beat-sync method | **Port** the beat-grid fit and the ±3-frame rule (P12.4) | music-driven cuts are a retention tool; the method is measured (cut error ≤ 2.2 frames) |
| Aesthetic rules + final-review | **Turn into automatic checks** (P12.5) | they are the same idea as our retention scorecard; the numbers (min text height, hold times) are testable |
| Sequences (promo energy arc) | **Use as hook / pacing / ending profiles** (P12.6) | this is the remaining part of Phase 9 |
| JianYing draft export | **Port** after the editor is stable (P12.7) | our timeline (`layers.json` + cuts) maps to tracks; "export to an editor" is a real exit door |
| Social publishing (Upload-Post) | **Port, off by default** (P12.8) | removes the last manual step, but posting is an outward action: only when the owner asks, with a dry run first, never with a key in output |
| Remotion and React | **Not used** | one renderer (HyperFrames) keeps the installer small and the render path single; every recipe is re-implemented, not wrapped |
| Motion Workbench (Vite + Remotion Player editor) | **Not adopted**; mine its ideas: a Gallery of all shots with live previews, "swap this shot for that one" | the Studio already has the timeline and inspector |
| Their agent workflow text (questions to the user, manual storyboard approval) | **Skip** | this product is automatic by design |

### P12.1 Architecture of the port (one place, one contract)

1. `renderer/runtime/vt-shots.js` (new): a registry `X.shots[name] = { kind, params, build(ctx, p) }` where `kind` is `transition` | `text` | `element` | `camera` | `fx`. A recipe is **a pure function of time** like the rest of the runtime (GSAP timelines are built paused and `seek` is frame-exact), takes only its parameters and the theme tokens, and uses CSS 3D transforms, SVG and canvas only. No randomness without a seed.
2. `vt/shots.py` (new): the catalogue read by the planner, the validator and the Studio: name, kind, category, English one-liner (translated from the card, **not** machine-guessed at run time), parameters with limits, duration range, energy (low/mid/high), what it needs (a title, a number, two pictures), which aspect ratios it supports, and `min_gap`/`max_len` so the 3 s rule can be checked without rendering.
3. Schema: `Transition` becomes an open enum validated against the catalogue; a new element type `shot` (`recipe`, `params`, `text`, `media`) for typography/effect/data recipes; `camera` recipes become scene `camera.move` values. Old projects keep working (the old values stay valid).
4. Planner: the rules planner and the AI prompt get the catalogue as a short table (name, when to use, energy); rules pick by sentence role from `context.json` (Phase 10): hook, definition, number, comparison, list, turn ("but"), conclusion, call to action. The AI planner may name any recipe; the validator refuses unknown names and parameter values outside limits and says why.
5. Tests per recipe (the same discipline as the phase-2 showcase): (a) it renders (visible, inside the frame, not blank); (b) seeking is exact: the frame at t is identical whether reached by playing or by jumping; (c) the picture changes during its animation (it does what it says); (d) its length and the longest still stretch it leaves are inside its declared limits; (e) a golden contact sheet reviewed by eye before it is accepted. `scripts/qa_shots.py` renders every recipe in 9:16 and 16:9 and writes the sheets; nothing is called done without looking at them.
6. Provenance: each ported recipe's file header names its card (`typography/blur-slide`) and the commit; `third_party/video-shotcraft/NOTICE.md` stays accurate.

### P12.2 The recipes to port, in waves (retention value first)

**Wave A: scene changes and emphasis (the 3-second rule), about 28 recipes, 16-20 h.** Transitions: `wipe-transitions` (blinds-slice, others), `page-turn-transitions` (barn-door-split), `shot-transitions` (push-flow, whip-pan, mask-wipe), `transition-hidden-cut` (occluder cut, collision open, light leak), `tear-streak-transitions` (glitch-displace), `bottom-push-stack-wipe`, `card-flip-reveal`, `circle-match-iris`, `line-carry-transition`, `print-texture-transitions` (ink bleed). Emphasis on the spoken word: `blur-slide`, `marker-underline-title`, `gradient-word-sweep`, `lead-word-zoom-assemble`, `type-assembly-moves` (split-text-stagger), `outline-word-fill`, `paper-title-card`, `countdown-arc-scatter`, `title-demote-to-label`. Hit and punch: `crash-zoom-punch` (also the **A-roll punch-in**, replacing our fixed rules), `impact-feedback`, `slam-entrance-moves`, `jump-cut-punch-in`, `speed-ramp-freeze`.
**Wave B: data and structure, about 18 recipes, 10-14 h.** `chart-live-moves`, `gauge-readout-moves`, `before-after-slider-scrub`, `timeline-travel`, `scroll-brake-moves`, `value-stagger-gradient`, `list-reveal`, `list-stack-press`, `row-embed`, `card-stack`, `radial-wave`, `bezier-source-converge-merge`, `draw-svg-trace`, `integration-hub-map`, `product-card-progressive-assemble`, `pill-slot-cycle`, `type-and-filter`, `typewriter-moves` (error-retype).
**Wave C: openings, outros, light and camera, about 20 recipes, 14-18 h.** `brand-ink-open`, `text-as-mask`, `spotlight-hero-card`, `crane-rise-reveal`, `letterspace-materialize`, `stroke-segment-build`, `icon-field-colorize`, `logo-shrink-wordmark-lockup`, `outro-group-photo-launch`, `ui-strip-away-outro`, `ui-to-brand-morph`, `neon-triple-marquee`, `spotlight-sweep-moves`, `light-play-moves`, `scan-bracket-sweep`, `depth-layer-moves`, `space-camera-moves`, `overhead-camera-moves`, `panel-grid-moves`, `beat-cut-moves`.
**Not ported** (product-promo specific or needs real UI screenshots to make sense): the page-capture and mock-UI cards (`cursor-flyover`, `terminal-3d`, `graze-face-tour`, `page-waterfall-wall`, the collaboration-cursor, voice-waveform, dictation and picker-carousel cards, `integration-hub-map` stays in Wave B only if it can run on our own icons). They stay in `third_party/` for a later "product film" mode.
Each recipe takes about 40-60 minutes with its test and sheet; the wave estimates include that.

### P12.3 Sound library (2-3 h)

1. Merge `third_party/video-shotcraft/audio/sfx/**` (149 files, 16 categories) into `assets/sfx/` next to ours (keep the category folders, never rename, keep `ATTRIBUTION.md` beside them). Re-run `scripts/build_sfx_library.py` so `sounds` and the picker know the new files; loudness-normalise to our SFX target with ffmpeg `loudnorm`, measured per file, never by name.
2. Music: add the 5 BGM tracks to `assets/music/` with their mood tags (the cards say "strong electronic beat"; we tag by measured tempo and energy, see P12.4).
3. Use: the sound planner picks an SFX category per event (transition -> `transition`, number reveal -> `counter`, impact word -> `impact`, list item -> `ui`, text pop -> `text`) with the card's own rules: **double samples alternate, volume steps down on repeats, gaps shorten** (no machine-gun repeats), a riser only before an impact, SFX timed relative to the shot start, not to absolute frames.
4. Licence note: Mixkit licences allow use inside a video; redistributing the sound files as a library is grey. The owner said licensing is not a concern; `ATTRIBUTION.md` ships with the files anyway, and the six files with no recorded source are flagged in the Studio's sound picker as "source not recorded".
**Gate:** `pytest` for the library (every file decodes, loudness inside +-1.5 LU of target, no duplicates by hash), and a real render with SFX on a 9:16 and a 16:9 video, listened to through the loudness and peak report.

### P12.4 Beat sync (4-6 h)

1. `vt/beats.py` (new): from a music file get onset strength (numpy/scipy STFT, no librosa dependency), pick beats, and **fit an exact grid by least squares** `t_i = t0 + i*T` (the card's method; the scalar tempo of a beat tracker is not trusted), report BPM, phase and the maximum residual; a track is "grid-clean" when the residual is within +-15 ms. Result cached next to the track as `<track>.beats.json`.
2. Use only when a track is chosen and is grid-clean: scene cuts, transition starts and keyword entrances may move to the nearest beat **if the move is under 150 ms and no spoken word is crossed**; cuts never move words, only pictures. Rule from the cards: full-frame beat hits at most 3 per film, otherwise only the element layer moves.
3. Report in the retention scorecard: "cuts on the beat: n of m, worst error in frames".
**Gate:** on each of the 5 tracks the grid residual is measured and recorded; a rendered 30 s video with music has every moved cut within 3 frames of a beat when measured again from the rendered file, and no word was cut.

### P12.5 Their rules become our checks (3-4 h)

Add to `vt/retention.py` and to the QA scripts, each as a number with a threshold and a test: caption height at least 5 % of the frame and helper text at least 3 % (measured from the render); a held title or wordmark stays at least 1 s; full-frame impact hits at most 3 per video; no handheld shake by default; an end card is held at least 0.5 s; no text with contrast below the contrast engine's floor; fly-in elements end on real layout slots (already covered by people/avoid and re-flow). The final-review checklist (P product goal, F function, V visual, S shot cards, B storyboard consistency, D data safety, A audio and rhythm, Q technical quality) becomes `scripts/final_review.py`: it runs the automatic parts and prints the few questions that need an eye.

### P12.6 Sequences become hook, pacing and ending profiles (4-6 h)

`references/sequences/promo-energy-arc.md` (acts with energy levels) becomes `vt/director/arc.py`: a profile per video kind (explainer, story, product, stick, talking head) that sets, for each part of the video, the energy and the recipe families allowed: cold open from the strongest sentence (Phase 9 hook), a fast first 3 s, a slower middle with the heartbeat, a peak before the call to action, an ending recipe (`outro-group-photo-launch` style or `ui-to-brand-morph` for products, plain hold for talking heads). This finishes P9 (hook, pacing, endings) using the recipe catalogue.

### P12.7 JianYing / CapCut draft export (6-8 h, after the editor is stable)

Port `jianying-export/` (pyJianYingDraft 0.3.x): our project becomes a draft with the voice as an audio track, clips per scene (rendered plate per scene so each can be retimed in the editor), captions as native text tracks, SFX and music as separate tracks, layers as extra tracks. It was verified by its author on JianYing Pro 11.2 for macOS only. **Windows is untested; the gate says so**: unit-test the draft JSON we write (tracks, timings, no overlaps on one track) and open it in JianYing/CapCut if the owner has it installed; if not, report "draft written, not opened in the app".

### P12.8 Social publishing (3-4 h, off by default)

Port `publish/` (stdlib Python, Upload-Post API, offline tests). Rules: the API key lives in `settings.json` or the OS keyring and is **never printed, logged or put in a URL shown to the user**; `publish` always starts as a **dry run** that shows the file, caption and platforms; the real post needs an explicit confirm per video in the Studio ("Publish to YouTube, TikTok..." with a preview of the caption), never from a batch or a script; nothing is posted while testing (the offline tests use a local fake server, and the real call is never made without the owner's key and request).

### P12.9 Studio: a Shots gallery (4-5 h)

A panel "Motion library" listing every ported recipe with a live preview rendered by our own renderer (not their webp), search by name or kind, and two actions on a selected scene: "Use this transition/effect here" (writes the recipe into the scene, validated) and "Pick for me" (the planner's choice with its reason). Keeps the UI simple: it is a picker, not an editor.

### P12.10 Order, estimates and gates

1. P12.3 sound library and P12.5 checks first (cheap, immediately useful): about 6 h.
2. P12.1 architecture and Wave A (28 recipes) with the 3 s rule tests: 20-24 h. After this wave the rest of Phase 9 (hook, pacing, endings, covers) is built on the recipe catalogue (P12.6).
3. P12.4 beat sync: 4-6 h.
4. Waves B and C: 24-32 h; P12.9 gallery: 4-5 h.
5. P12.7 and P12.8 last, after Phase 11's clean board, because they add outside dependencies.
Total about 95-120 working hours. **Every wave ends with: `scripts/qa_shots.py` sheets looked at in both shapes, all recipe tests green, the full `pytest`, the e2e suites, and a real 60 s video made with the wave's recipes measured by the retention scorecard (longest still stretch under 3 s).** A recipe that cannot reach the card's look in GSAP is dropped from the catalogue and written down here, not shipped looking worse.

### P12.11 Risks

* **Fidelity.** The Remotion demos use per-frame React and sometimes WebGL-free tricks that depend on Remotion's frame model. Our runtime seeks GSAP timelines; anything that needs per-frame state is rebuilt as a function of time or dropped.
* **Catalogue bloat.** 90 recipes make the AI planner's prompt long and its choices random. The prompt shows at most 12 recipes per request, pre-filtered by the sentence role and the energy the arc profile allows; the rules planner is deterministic.
* **Look consistency.** Recipes were tuned for dark product films; ours must follow the theme tokens (colour, font, stroke), or a recipe looks pasted in. Every port reads theme variables and is checked on at least three themes.
* **Audio licences.** See P12.3.
* **Maintenance.** The upstream library moves; we do not track it. `NOTICE.md` pins the commit; re-importing later is a manual, reviewed step.

### P12.12 Status

*2026-10-23:* library read, copied to `third_party/video-shotcraft/` with LICENSE and NOTICE, index of 124 cards generated, this plan written. Nothing is ported yet.


---

## Phase 13 plan (2026-10-23): a real creative director (the stick-figure and every other mode)

Owner: "If I click stick man figure then it just created 2 simple stick men talking... no other artifact or motion in between. There is no creative intelligence in this whole software. You can talk with AI / Gemma and Claude to plan the entire video."

### P13.0 What is wrong, measured on 2026-10-23 (`scripts/qa_director.py`, real local model gemma4 on the owner's server)

| transcript (a story with two named people) | characters | places | different verbs | props | talk share | what happens |
|---|---|---|---|---|---|---|
| `story-wallet`, rule director | 1 ("Maya, teacher") | 1 (a **market** for a story set on a street) | 4 | 0 | 0.40 | walk in, wave, nod, explain |
| `story-wallet`, gemma4 | 1 (an unnamed "narrator") | 1 | 6 | 1 | 0.00 | walk in, point at the wallet, think, run, react; the finder and the owner never appear |
| `edu-money`, rule director | 1 | 1 | 5 | 0 | 0.43 | wave, hold a sign, nod, explain |
| `edu-money`, gemma4 | 1 (unnamed) | 1 (plain) | 8 | 0 | 0.20 | the same teacher in the same empty room |

Causes, read in the code: (1) the rule director (`vt/script/rules_stick.py`) hard-codes one character "maya", one set, and a rotation of `explain / nod / explain / shrug`; it ignores who and what the story is about (the people, places and things the context reading of Phase 10 already finds). (2) The AI path is **one prompt for the whole video** that must produce cast, sets, every action and every overlay at once; a small model answers with the minimum that validates. (3) The engine's vocabulary is small (10 sets, 31 verbs, one rig, no way to show an animal or an object that moves on its own, no interaction beyond hand-shake and high-five), so even a good plan has little to draw. (4) Nothing reviews the result for *interest*: the quality metrics only check that the script is valid, covers every sentence and has no idle gap.

### P13.1 The principle

A video is directed in passes, the way a person would: understand the story, decide the **concept, cast and places**, storyboard section by section with **something happening in every line**, review as an editor, fix what is weak. Each pass is a small, checkable AI job that a local model can do (and that Claude can do through the MCP tools); a deterministic director with the same structure runs when no AI answers, so the result is never "two figures talking". The person can **talk to the director** ("make it funnier", "add a chase", "the owner should be an old man") and the plan changes only where it must.

### P13.2 The vocabulary (what the engine can draw), 12-16 h

Everything the director may name lives in `vt/script/catalogue.py` and is drawn by `renderer/runtime/vt-stick.js`; every addition gets a render test (visible, inside the frame, moves when it should) like `scripts/qa_stick.py`.
1. **Places:** from 10 to about 22 set kinds (kitchen, school yard, bank, hospital, inside a shop, factory, farm, airport, city skyline, mountain, island/desert, courtroom, phone/app screen), each with 4-6 props; **time of day** (day, evening, night) and simple **weather** (rain, snow) per scene as background tints and light particle layers.
2. **Cast:** looks that differ at a glance (height: child / adult / elder; build; colour; accessory; hair; clothes colour), a role table, and **non-human actors**: any emoji or sticker can be an actor (a fox, a coin, a wallet, a bulb) that walks, hops, bobs, spins, grows, shakes, flies and bounces by the same verb names, so a fable can have a fox and a vine.
3. **Verbs:** add about 22 (give, take, chase, follow, sneak, hide behind a prop, peek, throw, catch, lift a heavy thing, climb, dance, clap, bow, laugh, cry, yawn/sleep, phone, type, eat/drink, argue, hug, wave with both hands, pose, trip over a prop) plus **emotion marks** above a head (`!`, `?`, light bulb, heart, anger, sweat drop, zzz), and **object verbs** (appear, slide in, bounce, spin, grow, shake, fly across, fall, light up).
4. **Camera and cuts:** `zoom_to` a prop or a face, `cut_to` an **insert shot** (a big object, a close face, a chart) for 1-2 s, `whip` between places, match cuts on a moving object, shake on an impact; the transition list grows with the Phase 12 recipes.
5. **Two or more characters** are the normal case: entrances and exits are explicit, positions persist between scenes (already supported), and interaction verbs name `target`.

### P13.3 The director in passes (AI and rules share the structure), 12-16 h

0. **Understand** (exists: `context.json` of Phase 10): topic, sentence roles, mood, named people / places / things with their types, numbers.
1. **Treatment** (one small JSON): the concept in one line, the tone, the **cast** (every named person becomes a character with a look and a personality; every named animal or object that acts becomes an emoji actor), the **places** (set kind, props, time of day) and which sections happen where, a **running motif** (a prop or gag that comes back), and the **energy arc** (calm opening, build, peak, resolution). The rule version takes these from the context entities and a topic -> place table.
2. **Storyboard per section** (windows of about 4 sentences, the earlier decisions pinned in the prompt): for each sentence a list of **events with times** (who does what, to whom, where; an insert shot; an overlay; a sound; the camera), the continuity facts (who is on screen, where they stand, what they hold) carried forward, and hard rules checked by the validator: a new visible event at least every 2.5 s (the owner's 3 s rule), every cast member appears in the section they belong to, no verb twice in a row for one actor, at most 30 % of actions are plain talking, a place change has a transition.
3. **Editor's critic** (deterministic, `vt/script/critic.py`): extends `score.py` with *interest* metrics: characters used vs cast, places used vs planned, different verbs per minute, talk share, props touched, camera and transition variety, repeated phrases, longest stretch with only the same figure doing the same thing, overlays that repeat a kind three times in a row, the fit between sentence role and event (a number gets a number overlay or a count, a question gets think/shrug, a turn "but" gets a reaction or cut). It lists **scene by scene issues** in plain words.
4. **Revise**: the issues of the weak scenes go back to the model ("scene s3 has only talking for 6 s; add something that happens"), at most two rounds, only for the scenes that failed; then a **deterministic enricher** fills what is still missing (insert shot, mark, prop bounce, camera move, entrance) so the rules path alone beats today's baseline.
5. **Vision review** (the local vision model, existing `vt/ai/vision.py`): one frame per scene from a real render: is the figure visible and not under the caption, does anything overlap, does the picture match the sentence; findings go to the same revise step.
6. **Provenance**: `director.json` in the project keeps the treatment, every pass's output, the issues found and the version history (undo), so a person or Claude can see why the video looks as it does.
All passes use `ai.complete_json` with the repair and check hooks already in the code, a per-pass token budget small enough for gemma-sized models, and the cache; every pass degrades to its rule version when the model fails.

### P13.4 Talking to the director, 8-10 h

* `POST /api/projects/{pid}/director/chat` `{message}`: the model sees a compact summary of the current plan (treatment, one line per scene) and the request, and answers with **operations** (add or change a character, change a place, rewrite a scene, add a gag, change the tone, make it shorter / faster), applied only after validation; only the affected scenes are re-directed. Every reply says in plain words what changed; undo restores the previous version.
* Studio: a **Director** panel (a chat) in the editor, and in the new-project flow one optional line **"What is the idea?"** (for example "a funny story for kids") that goes into the treatment. No other new control.
* Claude Code: new MCP tools `get_director_task` / `submit_treatment` / `submit_storyboard` so Claude can do the same passes with its own judgement (the existing whole-script tools keep working); the chat endpoint is also callable from Claude.
* Not automatic and not hidden: the director never changes the words, the voice or the timing of speech; it directs pictures and motion.

### P13.5 The gate (what "done" means)

`scripts/qa_director.py` on at least 8 transcripts (the 9 evaluation sets, plus the owner's talking-head project and a Bangla one), for rules and for gemma4 (and qwen3.6:27b when reachable), recorded in this section, with targets: **characters used = people named in the story (at least 2 for a story with 2 named people), places >= 2 for any story of 4+ sentences, different verbs >= 8 per video of 10 sentences, talk share <= 0.30, longest time with nothing new <= 2.8 s, props touched >= 2, camera moves >= 3, no verb twice in a row for one actor**; the storyboards **read by a person** (me, written down here with my verdict: is it a story, is it funny or clear, would I keep watching); rendered contact sheets of every scene of 4 videos looked at in 9:16 and 16:9; the owner's own test video planned and rendered with the scorecard (`retention.json`: risk lower than the baseline). Unit tests for every validator rule and for the critic's metrics; e2e for the chat panel. No pass is declared good because it validates: the numbers above and my reading of the storyboards decide.

### P13.6 Order and estimate

1. P13.2 vocabulary, first the verbs and non-human actors (they give the director things to use), then places and cast looks, then camera and inserts: 12-16 h.
2. P13.3 rules director v2 with the treatment from context entities (so offline is good): 6-8 h; then the AI passes and the critic/revise loop: 8-10 h.
3. P13.4 chat, panel, MCP tools: 8-10 h. 4. Tuning on the eval sets and the real renders: 6-8 h. **Total about 45-55 hours.**
5. After stick mode, the same passes drive the other kinds (explainer, story, product, emoji): their "vocabulary" is the Phase 12 recipe catalogue and the element types; they share the treatment, the critic and the chat.

### P13.7 Status

*2026-10-23:* baseline measured (table above, `scripts/qa_director.py` and `qa_out_director/`), plan written.
**P13.2 vocabulary: built and looked at (20 patterns x 2 shapes, `scripts/qa_stick.py`, `tests/test_stick_vocab.py` 9, `tests/test_stick_render.py` 2 slow).** Catalogue: 58 verbs (was 31: clap, bow, laugh, cry, yawn, dance, phone, type, eat, lift, throw, give, chase, follow, sneak, hide, peek, hug, argue, wave_both, mark, bounce, spin, grow, appear, fly), 23 places (was 10: kitchen, school yard, bank, hospital, inside a shop, factory, farm, airport, city, mountain, island, courtroom, screen world) with 22 new drawn props, 16 accessories (beard, bow, crown, headband, apron, backpack, helmet, mask), heights (child / adult / elder, elders stoop), hair styles, shirt and skin colours, 23 roles, **emoji actors** (any sticker can be a cast member: fox, crow, light bulb), 8 marks above a head (! ? bulb heart anger sweat zzz sparkle), **time of day** (dawn, evening, night: the whole scene recolours and the ink turns light) and **weather** (rain, snow), camera `zoom_to` a prop or person, validation of all of it. Looked at: a fable with a fox and a crow that jumps and gets laughed at, a wallet story where an old man in a beard takes the wallet and hugs the boy, a stormy night with rain and zzz, a cook, two shopkeepers arguing then shaking hands and bowing, an idea (bulb actor + bulb mark), children throwing a ball to a boat, a thief sneaking, hiding and peeking. **Defects found by looking and fixed:** (1) the drawing sat in a 4:3 box on the left of a 16:9 frame (now centred and larger when no overlay shares the frame) and the 9:16 floor was 20 px under the caption's top edge (feet hidden; stage raised); (2) people walked to where the other person *started*; planning now runs **all characters' actions in time order** so a relation uses the other person's real position then (a first attempt with position functions made two people who walk toward each other crash the page by circular calls; it was removed, and the time-ordered plan has no cycles); (3) marks above a head clipped at the picture's top (now beside the head); (4) the picture search put "hyacinth" before the sticker named "grapes" and "tiger" before "fox": an exact-name match (and the last word of a name: "light bulb") now beats a look-alike by meaning, `vt/visuals/search.py`; (5) the QA's own figure detector assumed dark ink on a light page (now measures against the corner colour so night works). **Not done:** places drawn as scenery behind (a bed to lie in, a chair), walking across props, camera `cut_to` insert shots, a real "sit on" for chairs and beds, partial hiding behind a prop (the figure crouches beside it), snow tested only in code.


**P13.3 rules director v2 (the offline version of the passes): built (2026-10-23), `vt/script/story.py`, `tests/test_story.py` 12, `scripts/qa_story_render.py`.** Stick mode now makes the cast from the words (named people by first name or rare capitalised word, "the old man / the owner / the doctor" with a matching look, animals as emoji actors, a host and a curious learner when nobody is named, a fable gets no teacher), one place per scene from the words and the topic (23 kinds) with night/dawn and rain/snow from the words, events from the exact word that causes them (found -> lift the wallet, gave it back -> hand it to the other person, ran, laughed, afraid, "says that ..." -> the opinion in that person's speech bubble, a question -> the learner asks it aloud and the host wonders), pronouns follow the person the story is about, "gave up" is not a hand-over, props are nouns we can draw, gaps over 2.2 s get a different small thing (never the same twice in a row), camera and transitions follow what happens (new place -> whip, important sentence -> zoom to the prop, end -> pull back), sound cues. The same text always gives the same story. Falls back to the old director if it ever fails. **Measured (10 evaluation transcripts):** characters 1 (a fable) to 3, never the old fixed 1 "Maya"; places up to 2; different verbs 4-8; talk share 0.0-0.57 (the discussion video is talk by nature); longest time with nothing new 1.4-2.1 s. **Looked at in real renders:** the wallet story is now a story (finds, carries, runs, hands it over, thanked); the money explainer has a host and a learner who walks in at the question. **Still weak (honest):** the sentences are short in these samples so the plans are still modest (4-8 verbs per video); product videos name the product as a person if it is not recognised as one (guarded for tech/business topics only); camera variety is 2 moves in short videos; Bangla text gets places/roles only from the English word lists (the Bangla path is not yet tuned). The AI passes (treatment, storyboard, critic, revise, chat) with Gemma/Claude are not built yet: that is next.

---

## Phase 14 plan (2026-10-23): a New project screen that is crazy simple

Owner: "with this many features we need a more easy streamlined process for the new project scene. Functionality can be complex but UI should be crazy simple."

### P14.0 Today (counted in `studio/src/pages/New.tsx`)

Four source tabs (record, upload, script, link), two columns and about 15 controls on one page: name, language, shape, kind of video, pictures, a theme grid, pace, filler words, sound effects, music (with preview), and an advanced block (English words policy, speakers, glossary, speech model).

### P14.1 The screen (first view has a drop box, one line of choices, one button)

1. **One drop box** in the middle: "Drop a recording or a video, paste a link, or write a script". It works out what it was given: a file (audio or video) is uploaded, text that looks like a link is a link, other text is a script (the box becomes a text area). Under it three plain buttons: **Choose a file**, **Record**, **Write a script**. The four tabs disappear.
2. After something is given, **one line says what was understood** ("Voice recording, 1:12") and three small choices appear in one row: **Shape** (vertical / wide / square, remembered), **Language** (**Auto**, Bangla, English; auto-detects), **Style** (**Auto** or Stick figures / Emoji / Explainer). Plus the optional **"What is the idea?"** line (Phase 13). The name is made from the content and can be edited in place.
3. **One big button: Make my video.** Everything else (theme, music, pace, effects, fillers, pictures, glossary, speech model, speakers) lives in one folded section **More options**, closed by default, with the same controls as today.
4. Smart defaults decide what the person did not: language by detection, kind and theme by `auto`, music chosen from the mood of the content when "auto", pace and effects from the saved defaults. Nothing asks for a model download before the person has pressed the button.
5. A person who only wants the result sees: box -> (one line, three small choices) -> button. That is at most **6 visible controls** on the first screen (asserted in a test).

### P14.2 Backend (small)

* `language: "auto"`: for scripts decided by the letters (`vt/langdetect.from_text`), for recordings decided in the ASR stage by the speech model's own detection on the first 30 s of speech, restricted to supported languages with a head start for Bangla (Banglish is often called English by a detector); the project's language is updated and the progress line says "Language: Bangla".
* `POST /api/inspect` (upload a file or give a link): kind (audio/video), length, and for video whether a speaker's face is found (then Style defaults to "keep the speaker").
* Auto style from the content type: a talking-head video -> speaker mode; a story -> stick; otherwise explainer; the person's last choice is remembered.

### P14.3 Tests and gate

Unit: language detection (text by script, probabilities with the Bangla head start), auto resolution in the pipeline, inspect. E2E `studio/e2e/new_simple.mjs`: dropping a file, pasting a link, writing a script and recording each reach the button with the right understanding line; More options is closed on load; the first screen has <= 6 controls; a11y clean; keyboard only works. The old e2e suites that drive the tabs are updated, not deleted. Real runs: a Bangla recording, an English recording, a typed Bangla script and a link, each started with only the drop box and the button.

### P14.4 Status

*2026-10-23:* plan written; `vt/langdetect.py` (text and audio detection) is written, not yet wired.

---

## Order after these two plans (replaces the earlier order)

Phase 13 (creative director) and Phase 14 (simple New screen) come **before** the rest of Phase 7 step 6 onward and before Phase 8, because they decide whether the product is worth using; then the unfinished Phase 7 gates (product smoke list, installer), Phase 8, Phase 12 (shotcraft; its transition and kinetic-text recipes feed the director), the rest of Phase 9, Phase 11.


---

## Phase 15 plan (2026-10-23): the app prompts Claude directly, like it prompts local Ollama

Owner: "how do I allow the app to directly prompt Claude, just like local Ollama? Think about that and apply as well. Plan first."

### P15.0 What exists, what was measured today

* Today the app talks to a model through `vt/ai/providers.py`: `OllamaProvider` (local or LAN), `OpenAIProvider` (any OpenAI-compatible URL), `AnthropicProvider` (the Messages API; needs a **paid API key**, billed per token and separate from a Claude plan), and the chosen one is `ai_provider` in `settings.json`. Claude through **Claude Code + the MCP server** is a different, manual route: the Studio only queues a request and a person must be running Claude Code.
* The owner has **Claude Code installed and logged in** on this machine (`claude` 2.1.306, `claude auth status` -> logged in, plan Pro). Claude Code has a **non-interactive mode** (`claude -p "<prompt>" --output-format json --json-schema '<schema>' --no-session-persistence --tools "" --system-prompt "..." --model sonnet`). Measured on 2026-10-23: a structured answer came back in **about 10 s**, the validated object is in the JSON field `structured_output` (also `result` as text), the call reports its cost (about $0.02-0.03 of list price for a tiny prompt, which counts against the plan, not a bill) and `is_error`. No API key was involved: it used the owner's login.

### P15.1 Decision: four ways, one list, the person picks one word

| Provider | Needs | Good for | Costs |
|---|---|---|---|
| **Local (Ollama)** | a server (this PC or the LAN) | everything offline, vision, privacy | free |
| **Claude, my login** (new, `claude-cli`) | Claude Code installed and logged in (`claude auth login`) | the creative director, planning, scripts: the strongest model, **no key** | counts against the Claude plan's usage limits |
| **Claude, API key** (exists) | an Anthropic API key | servers, unattended machines, many parallel calls | per token |
| **OpenAI-compatible** (exists) | URL and key | other providers, LM Studio, vLLM | per provider |

The Settings page shows these four as plain cards with a status line each ("ready", "not logged in: run `claude auth login`", "no server found") and a **Test** button that sends a real one-line request and shows the answer and how long it took. One more choice, **Best available** (the default): Claude (login) for text planning when it is logged in, else the local model; **vision always stays on the local vision model** (the CLI route takes no pictures here).

### P15.2 How the `claude-cli` provider works (and what it must never do)

1. `ClaudeCLIProvider.complete()` runs `claude -p <prompt> --output-format json --json-schema <schema> --no-session-persistence --tools "" --system-prompt <system> --model <alias>` in a **fresh empty temp folder** (so no project `CLAUDE.md`, no project MCP servers, no repo settings are read), with the console window hidden, a timeout, and returns `structured_output` as JSON text (the existing `complete_json` then validates it with the same repair/check hooks as every provider). Tools are switched off: it can only answer, never touch files or run commands.
2. **One call at a time** by default (a lock) and the existing on-disk **answer cache** (`ai_cache`), so a re-plan of the same text costs nothing; a call count and the cost the CLI reports are kept in `usage.json` and shown ("Claude calls today: 14, about the same as $0.40 of list price") so a person sees what the plan is spending. A daily cap setting (default 200 calls) stops a runaway loop.
3. Availability: the `claude` executable is found in `~/.local/bin`, on PATH or at the path in Settings; "logged in" comes from `claude auth status` (JSON), cached for a minute. If it is missing or logged out, the provider says exactly how to fix it and the app falls back to the next provider in the list, never a silent failure.
4. Model: `sonnet` / `opus` / a full id, default `sonnet`; the director passes (Phase 13) can use a stronger model for the treatment and a faster one for per-scene rewrites.
5. Safety: the prompt may contain the person's transcript; it is sent to Anthropic exactly as when using Claude Code by hand. The Settings card says so in one sentence. The key or login is never read or printed by the app (the CLI owns it); no email or account id is logged.
6. Terms: `claude -p` is Claude Code's documented non-interactive mode; the app uses it on the person's own machine with their own login for their own videos. It is not a way to share one login between people, and the card says "your login, your plan".

### P15.3 Where the app uses it

* Everything that already calls `ai.complete_json` (planning, context reading, script, stick/emoji director, transcript fixes) works with any provider, so nothing else changes.
* The Phase 13 director passes (treatment, storyboard, revise, chat) are the main users; the **"Plan with Claude"** button stops needing Claude Code to be running with MCP: it runs the same job through `claude-cli` (the MCP route stays for people who prefer to work in Claude Code).
* Parallelism: a director run makes about 8-12 calls (treatment, sections, a couple of revisions); at about 10 s each that is under 2 minutes; sections are independent so two can run at once with `claude_cli_parallel: 2` (off by default).

### P15.4 Tests and gate

Unit tests with a **stand-in `claude` program** (a tiny script on a temp PATH): the command line is exactly as designed (no tools, temp cwd, schema passed, model), `structured_output` is returned, `is_error`, a non-JSON answer, a timeout, "not logged in" and a missing executable each give a readable `AIUnavailable`, the lock serialises, the cache hits, the daily cap stops. **A real call**, marked slow, through the app's own `complete_json` with a real schema (this machine is logged in): the validated answer, the time, and the reported cost are written here. The Settings page e2e: the four cards, the status lines, Test shows a real answer. Gate: the creative director (Phase 13) runs end to end on a real transcript with this provider and the result is read by a person.

### P15.5 Status

*2026-10-23 (done):* `ClaudeCLIProvider` in `vt/ai/providers.py` (`ai_provider: "claude_cli"` or `"best"`), `find_claude`, `login_status` (cached 60 s; keeps only found / logged in / plan, never the e-mail), usage log `claude_usage.json` with a daily cap (default 200), settings `claude_cli_model` / `claude_cli_path` / `claude_cli_daily_cap`, `/api/ai/status` reports the Claude state, the Settings page has the provider choice (Local, Claude (my login), Best available, Claude API key, OpenAI-compatible, Off) and a Claude panel (ready or what to do, model, daily cap, today's calls and list-price cost). Prompt and system text go in through stdin and a temp file (the Windows command line is limited); a schema over 6000 characters goes into the prompt instead of `--json-schema`. `tests/test_claude_cli.py` 9 tests (command line exactly as designed, empty temp folder, no API key passed on, every failure readable, cache, cap, provider choices, status endpoint) + 1 slow real call. **Measured with the real logged-in Claude Code on this machine:** a validated answer through the app's own `complete_json` in 5.7 s for about $0.0065 of list price; a 17,418-character schema through the stdin path in 5.2 s (answer "Paris"). Default stays "Local (Ollama)" so nothing spends the owner's plan without them choosing it; "Best available" is one click. **Not done:** the Phase 13 director passes that will use it; parallel calls (`claude_cli_parallel`); the "Plan with Claude" button still queues for the MCP route (to be switched to this provider when the director lands).

---

## Phase 16 plan (2026-10-23): a full-screen loading screen for every long operation

Owner: "add full screen loading for every long async operation."

### P16.1 What counts and what the person sees

Today a long operation shows a small spinner in a button, a toast, or its own page (Progress) depending on where it was started, and some show nothing at all. **One rule**: any operation expected to take more than about half a second and that the person is waiting for shows the **same full-screen loading layer**: dimmed page, a clear title ("Making your video"), a spinner or a real progress bar with the percentage, **the step it is on in plain words** ("Listening to the recording", "Reading what the video is about", "Drawing scene 3 of 8"), elapsed time and, when known, a time left, and a **Cancel** button whenever the operation can be cancelled. It is a real modal (focus kept inside, `aria-live` announcements, Esc cancels when cancellable, the page behind is inert), it appears only after 400 ms (no flicker for fast things) and stays at least 600 ms once shown, and it never stacks: a second operation updates the same layer (a short list of the steps running). Background jobs the person is *not* waiting for (a render started and left, thumbnails) stay in the existing job tray; the layer is only for waiting.

### P16.2 Inventory (every place in the Studio that waits for something slow, from a search of `studio/src` on 2026-10-23)

Start a video from a recording, a link or a script (upload, download, voice, pipeline); the Progress page keeps its own view but uses the same component; sample voice download; record-then-process; Export (render, loudness, retention check); Review: re-run from a stage, replan, "Plan with Claude/AI", polish, QA frame check, show-as, transcript fixes and edits, overdub in my voice, apply A-roll, cut out a picture, sound events, context re-read, import media, describe media, voice preview, model downloads; Settings: test an AI provider, download a model, local AI install; Themes/Design Studio: generate; Director chat (Phase 13); language detection and inspect (Phase 14). Each is wrapped by the one helper below; a new long operation must use it (a lint-style test greps the code for bare polling loops).

### P16.3 Implementation

1. `studio/src/busy.tsx` (new): a store of running operations, `runBusy(title, work, opts)` for plain awaits, and `awaitJob(jobId, { title, cancel })` that replaces the eight hand-written polling loops (Export, New, Review, ContextPanel, MediaBin x2, ScriptPanel, Progress): it follows the job through the existing websocket events (falls back to polling), shows its `msg` and `frac`, and offers Cancel through `/api/jobs/{id}/cancel`. `<BusyLayer/>` mounted once in the app shell.
2. Errors: a failed operation closes the layer and shows the error in a toast (plain words, the same as now) and leaves the person where they were; an operation that is cancelled says "Cancelled".
3. Accessibility and keyboard: `role="alertdialog"`, `aria-busy` on the main region, focus moved to Cancel (or to the dialog), restored after; reduced-motion respected (no spinner animation, a static bar).
4. The Progress page and the New page's "Starting..." state use the layer's content component so there is one look.
5. Server side: every endpoint that runs a job returns the job id immediately (already true for jobs); the handful of long synchronous calls that block the request (any found by timing: over 2 s on the QA server) are turned into jobs so there is something to follow.

### P16.4 Tests and gate

Component tests are e2e (Playwright) in `studio/e2e/busy.mjs`: a fast operation shows no layer; a slow one (a test endpoint that sleeps) shows it after 400 ms with the title, a moving bar and the step text, then removes it; Cancel stops a cancellable job and a non-cancellable one has no Cancel; keyboard focus is inside and returns after; two operations at once share one layer; an error closes it with a toast; the a11y scan is clean with the layer open; a grep test finds no new `setInterval`/`for (let i...) await sleep` polling outside `busy.tsx`. Real runs: start a video from the sample audio and watch the layer through to the end; render an export; run "Plan with AI"; each looked at in a screenshot.

### P16.5 Order and estimate

P15 (4-6 h) and P16 (6-8 h) go **before** the rest of the Phase 13 engine tests, because P16 is needed by the director's long runs and P15 is what makes the director strong. Then Phase 13, Phase 14, the remaining Phase 7 gates, and the earlier order.

### P16.6 Status

*2026-10-23 (built, being regressed):* `studio/src/busycore.ts` (the list of things being waited for; every POST/PUT/DELETE/upload goes through `trackRequest` in `api.ts`; a job answer is followed with the job's own label, step text and progress; polls fast then slow), `studio/src/busy.tsx` (the layer: appears after 400 ms, stays 600 ms at least, modal alert dialog, focus moved in and restored, page behind `inert`, Tab trapped, Escape cancels or hides, elapsed and time left, Cancel for jobs, "Keep working while it runs", failure shown inside with Close, other running things listed), styles with reduced-motion. Mounted once in `Shell`. This covers every long operation without editing 30 call sites. `studio/e2e/busy.mjs` 17 checks (fast op shows nothing; slow op after about 0.4 s; modal, focus, inert; job title, step and bar; failure state; Cancel/Escape reach the server; Keep working hides it and a toast says when it finished; Tab trap; **a real export of the scratch project followed to a real Cancel**). The screenshot of the real export layer was looked at. **Not done:** converting the older hand-written polling loops (they still work and now sit behind the layer), the Progress page sharing the layer's content component, a grep test for new bare polling loops, long synchronous endpoints turned into jobs (none measured over 2 s yet).