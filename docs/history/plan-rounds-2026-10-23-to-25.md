# Video Tool — the plan

> **Vision.** Speak (Bangla, English or Banglish) and get a finished, scroll-stopping video *and* a fully editable timeline,
> with no human step in between. An AI makes every editorial decision a good human editor would make, explains each one,
> and the person only steps in if they want to. The goal is the tool that makes a video editor's job unnecessary.

The full history of how the app was built (Phases 2–16, every measurement, every bug, every decision) is kept word for word in
[docs/history/plan-until-2026-10-23.md](docs/history/plan-until-2026-10-23.md). This file replaces it as the working plan: what
we are building, what exists, what is missing, and in which order. Section references like "old P13.3" point into that file.

**Hard rules (owner):**
1. Something must change on screen at least every 3 seconds, in every shape (heartbeat targets 2.5 s tall / 2.6 s wide; tests enforce it).
2. AI first, rules as the safety net. Every AI step has a rule fallback, a validator, a cache and provenance. The pipeline never breaks because a model failed.
3. Never invent facts. Pictures, hooks, titles and on-screen text come from the speaker's own words.
4. Licensing is not a concern for this project (owner's decision).

---

## 1. How a human editor makes a viral short, and what the app does at each step

This is the yardstick. A good editor receiving a voice note works through roughly these decisions. Each row is something the AI
must do on its own. Status: **✅ done**, **◐ partial or unmeasured**, **✗ missing**.

### 1.1 Listen and understand
| The editor… | App today | Owner |
|---|---|---|
| hears what language it is | ✅ **new:** `language: "auto"` (speech detection between Bangla and English, Banglish → Bangla; scripts by their letters) | `vt/langdetect.py`, `Pipeline._detect_language` |
| writes down every word accurately, Banglish included | ✅ Bangla fine-tune + Whisper large-v3, glossary, LLM polish as suggestions | `vt/stages/asr.py`, `vt/ai/polish.py` |
| understands the topic, the mood, who and what is named, the sections | ✅ `context.json` (rules + AI pass) | `vt/context.py` |
| decides **what the video is for** (teach, sell, tell a story, give an opinion) and who it is for | ◐ use-case profiles auto-detected; no audience, no single "promise of the video" | `vt/director/profiles.py` |

### 1.2 Cut the talk (the editor's first and most important pass)
| The editor… | App today |
|---|---|
| removes silences and "um"s | ✅ pace-based silence cuts, filler removal |
| **removes retakes and false starts** (speaker says a sentence, stops, says it again) and keeps the last take | ✅ **built 2026-10-23** `vt/retakes.py` (false starts, repeated takes, stumbles; conservative; never on scripts), shown on Result with “Put back” |
| **tightens the content**: drops a rambling sentence, a repeated point, a weak tangent, so a 2-minute ramble becomes a 55-second short | ◐ **built 2026-10-23** `vt/tighten.py` + `tighten` stage: ranks by the context reading, protects hook / main point / CTA / sentences others depend on, ≤40 % dropped; “Put back” on Result. Not yet judged on real recordings. |
| removes breaths, mouth clicks, background hum; evens the voice level | ◐ denoise + loudness to −14 LUFS; breaths/clicks not handled |
| decides the target length for the platform (≤60 s Shorts, ≤90 s Reels) | ✅ `target_length` auto / 1 min / 1.5 min / keep all (auto: vertical over 90 s → about 60 s) |

### 1.3 The hook (first 1–3 seconds decide everything)
| The editor… | App today |
|---|---|
| puts the strongest moment first (cold open: the most surprising line, then the start) | ◐ designed (old P9.3 step 1), measured by the scorecard (`hook_s`), not built |
| shows something big and meaningful on frame 1, never a blank or a fade from black | ✅ first frame shows content |
| writes a 3–6 word hook title on screen in the speaker's words | ◐ AI writes a hook line for the publish kit; not placed in the video's opening as a rule |

### 1.4 Structure and story
| The editor… | App today |
|---|---|
| sees the arc: hook → problem → turn → payoff → call to action | ◐ sections and sentence roles in `context.json`; no arc check |
| puts a "reason to keep watching" in the middle (open loop, "3 of 3" counter) | ✗ designed (old P9.3 step 4) |
| ends cleanly, ideally loopable for Shorts | ✗ designed |

### 1.5 The picture layer
| The editor… | App today |
|---|---|
| shows what is said: a picture, icon, chart, number, diagram for each idea | ✅ 39 element types, icon library with meaning search, drawn clipart, charts/steps/timeline/diagrams |
| uses real logos, flags, faces for named things | ◐ old Phase 8 planned |
| B-roll from the speaker's media or stock | ◐ user media bin + catalogue + stock with the user's keys |
| keeps the speaker in shot when there is video (A-roll), cut like the voice, with punch-ins | ✅ A-roll cut with the voice; ◐ punch-ins |
| changes something on screen every ≤3 s | ✅ heartbeat + retention scorecard |
| stick-figure / emoji stories with a cast, places, props and action | ✅ vocabulary (58 verbs, 23 places); ✅ rules director v2; ✗ AI director passes, critic, revise (old P13.3) |
| keeps a consistent look matched to the topic | ✅ auto theme, Design Studio |

### 1.6 Captions (most short-form viewers watch muted)
| The editor… | App today |
|---|---|
| big, readable, word-by-word captions with the key word highlighted | ✅ word-timed captions with highlights; ✅ safe areas |
| emoji and emphasis styling in captions, one keyword pop per sentence | ◐ |
| caption styles per platform/trend (bold pop, box, karaoke fill) | ◐ one style per theme |

### 1.7 Sound
| The editor… | App today |
|---|---|
| picks music that fits the mood and ducks it under the voice | ◐ music from mood possible, ducking ✅; library is synthesised loops, never auditioned |
| hits cuts and pops on the beat | ✗ beat sync (old P12.4) |
| adds whooshes, pops, risers on transitions and reveals | ✅ sound cues; ◐ library quality (old P12.3) |
| delivers platform loudness | ✅ −14 LUFS, −1.5 dBTP |

### 1.8 Watch it back, like a viewer
| The editor… | App today |
|---|---|
| watches the whole thing and fixes boring or confusing moments | ◐ retention scorecard measures; per-frame vision QA checks; **no automatic revise loop driven by them** |
| makes 2–3 variants of the hook and picks the best | ✗ |

### 1.9 Package and publish
| The editor… | App today |
|---|---|
| exports the right shape(s) with good encoding | ✅ 9:16 / 1:1 / 16:9, H.264 High, AAC 48 k, faststart |
| makes a cover, title, description, hashtags | ✅ publish kit (AI with rule fallback) |
| hands over an editable project | ✅ the Studio editor; ✗ export to CapCut/JianYing draft (old P12.7) |

### 1.10 Learns the creator's taste
| The editor… | App today |
|---|---|
| remembers what this creator likes (look, music, pace, words they always misspell, what they always change) | ◐ glossary, saved defaults; ✗ learning from the creator's edits |

**Summary.** The app is strong at *transcribing, illustrating and rendering*. It is weak at the editor's *judgement*: cutting
content (retakes, rambling, length), the hook, the arc, and watching its own result and fixing it. That judgement is where the
"human touch" lives, so it is where the next work goes.

---

## 2. The architecture that delivers this

### 2.1 One pipeline, the AI as the editor
```
voice ─► listen ─► understand ─► EDIT THE TALK ─► DIRECT ─► build timeline ─► WATCH & REVISE ─► render + publish kit
          asr       context.json   (new: retakes,    treatment,   scenes.json      scorecard + vision
          + lang    roles, cast     tighten, hook,    storyboard,   + layers         critic → fix weak
          auto      sections        target length)    pictures      (editable)       scenes, ≤2 rounds
```
* Each box is a small, checkable AI job (`ai.complete_json` with a JSON schema, validator, one repair retry, cache, then the rule
  version). Small local models (gemma-class on Ollama) must be able to do each job; Claude (the owner's login via `claude -p`,
  old P15) does them better when available. **"Best available"** is the default provider.
* **Provenance and "why"**: every decision on the timeline carries who made it (rules / local model / Claude / person) and a
  one-line reason ("cut: repeated take of sentence 4", "hook: the most surprising claim, moved to 0 s"). The editor shows it.
  This is what lets a person trust an editor they never talk to.
* The person never has to touch anything. Every AI decision is an ordinary, undoable edit on the timeline.

### 2.2 The output contract: the editable timeline
The product is not the MP4; it is the **timeline** (`scenes.json` + layers + cut list), from which the MP4 is rendered.
Everything the AI does must land there as normal timeline items, so the editor, undo, MCP tools and future exports (CapCut)
all see the same thing. No AI step may produce something only the renderer knows about.

### 2.3 Where each part lives (unchanged, see old §2 and §8)
Python (`vt/`): pipeline, AI, audio. Node + HyperFrames (`renderer/`): motion graphics and Bangla shaping. React (`studio/`):
the UI. MCP server (`vt/mcp/`): any AI assistant can drive the app with the same contract.

---

## 3. The UI: three screens, the editor one click away

The vision says no human interaction, so the default path must need **zero decisions**. The full editor stays, but nobody has
to open it.

| Screen | What the person sees | Status |
|---|---|---|
| **1. Make** (`/new`) | A big microphone. Under it one box: paste a link or write a script; or drop/choose a file. When something is given: one line saying what was understood, Shape (Vertical/Wide/Square), Style (Auto/Stick figures/Emoji), one button **Make my video**. Everything else (name, language, kind, look, pace, music, effects, pictures, voice for scripts, Banglish, glossary, speech model, mic, prompter, sample voices) is under one closed **More options**. | ✅ **built 2026-10-23** (was 4 tabs + ~20 visible controls). Dashboard tiles still work through `?tab=`. |
| **2. Making** (`/p/:id/progress`) | One progress line in plain words, live preview filling in, time left. | ✅ **built 2026-10-23**: one plain-words headline, one bar, step n of N, time left, details folded. Live preview not yet. |
| **3. Result** (`/p/:id/result`) | The finished video playing (rendered automatically), one sentence from the retention check, and four buttons: **Download** (all shapes), **Change the look**, **Fix a word**, **Edit everything**. | ✅ **built 2026-10-23**, plus “What the editor cut” with Put back, and the AI title/description/hashtags with copy buttons. |

Rules for every screen: one primary button; works at 390 px; keyboard reachable; axe clean; no screen needs a scroll at 1280×720
to reach its primary action.

**Options pattern (owner, 2026-10-23): Apple setup-assistant steps.** Every "more options" is a sheet with Cancel · *Step n of N*
· Done, a large title and one-line subtitle per step, iOS grouped inset rows (label left, control right, note below), iOS
switches, page dots and Back / Continue. Built as `Steps`, `Group`, `Row` in `studio/src/ds/`; the Make screen uses it in four
steps (1 Basics, 2 Look, 3 Sound and editing, 4 Voice and speech). New option screens must use the same components.

**UI issues found in this review:**
* ✅ fixed: at phone width the top bar hid "Settings" (nav now takes the free width; language switch hidden on phones).
* ✅ fixed: the top bar said "Claude not connected" to everyone; it now shows which brain decides ("AI: Claude" / model name /
  "rules only") and links to Settings.
* ✅ fixed: a plain rename recomposed the whole video (0.45 s), which flashed the full-screen loader; renames no longer recompose.
* Open: the pill reads `vt/ai/providers.py`, but context reading still goes through the older `vt/llm.py` (it auto-downloaded a
  local model on a fresh data folder while the pill said "rules only"). One AI path is needed (M3 prerequisite).
* Open: Settings has six AI providers in one list; it should be the four cards of old P15.1 with "Best available" preselected.

---

## 4. Roadmap (replaces every earlier "order of work")

Each milestone has a gate that is measured, not assumed. Estimates are working hours for an agent.

### M1 — Zero-click path (UI) · ✅ done 2026-10-23
`e2e/simple.mjs` 13/13 on an isolated server with a real voice, real render, real retention check and publish kit:
typed script → **1 click** → finished video playing on Result (also at 390 px). Autopilot is a setting (default on).
1. ✅ Make screen (done, see §3).
2. Result screen: after the pipeline, render 9:16 draft automatically, land on Result instead of the editor.
   "Download" renders the delivery quality in every shape the person asks for.
3. Making screen: plain-words steps only ("Listening", "Cutting the pauses", "Choosing pictures", "Drawing", "Rendering").
4. Top bar: responsive nav; AI status pill shows the active provider.
5. **Autopilot setting** (default on): Make → Result with no stop. Off: stop at the editor as today.
**Gate:** new `e2e/simple.mjs`: from an empty data folder, record or drop the sample, reach a playing finished video and a
downloaded MP4 with ≤ 2 clicks after the source is given; existing editor suites still pass via "Edit everything".

### M2 — Edit the talk (the editor's first pass) · 14–18 h — steps 1 and 2 built 2026-10-23, gate not yet run
1. ✅ **Retake detection**: find sentences repeated within ~20 s (word overlap + embeddings over the transcript), keep the last
   complete take, cut the others. Rule version first, AI to judge unclear cases. Cuts are normal cut-list items with a reason.
2. ✅ (rules version) **Tighten**: AI ranks sentences by importance (context roles already give this), proposes cuts to reach the target length
   (Shorts 60 s / Reels 90 s / "keep everything"), never cuts a sentence that a later one depends on. Shown as removable cuts.
3. **Hook**: pick the strongest line (surprise, number, question; from the speaker's words) and make a 2–3 s cold open; put a
   ≤6-word hook title on the first scene. *Status 2026-10-23:* the hook title exists (director archetypes: topic or the tidied
   first sentence, ≤40 chars, on screen from frame 1; scorecard `hook_s`). **Cold open deferred**: it plays a piece of audio out
   of order, and ~10 places assume the cut list is in time order (`Cuts.map_time`, `audio_edit` out_to_src/src_ranges/view/
   apply_to_cut_audio, `apply_cuts`, A-roll filter, `words.py`). Design: an optional `Cuts.lead` (source range) played before
   `keep`; `map_time` offsets the body by its length; words inside it are duplicated with ids `t<n>` for the teaser's captions;
   every `keep` iterator gets the lead first; no cold open when there is an A-roll. Its own milestone with editor tests.
4. Breath and click removal on the voice track. *(not built; breaths in pauses already go with the silence cuts)*
**Gate:** on 5 real phone recordings (the owner's, Bangla and English) a person rates the cut version better than uncut in all
5; no cut lands mid-word (alignment test); hook ≤ 1.0 s on all.

### M3 — The director in passes (old P13.3–P13.4) · core built 2026-10-23
*Built:* `vt/script/critic.py` (`review`: score, metrics, scene-by-scene notes in plain words with a fix; `enrich`: fills every
still stretch > 2.8 s with a gesture that answers the words: a question → think, a small number → count on fingers, a big
number or "!" → react, never the same verb twice running), `planner.revise` (the critic's notes go back to the AI, ≤2 rounds,
kept only when the critic scores it higher), enricher on both AI and rules paths, `director.json` report, **talk to the director**
(`vt/script/chat.py`, `GET /api/projects/{pid}/director`, `POST …/director/chat` as a job that re-renders; Result screen card
with suggestions; reply says what now happens per scene; undo keeps the previous plan), MCP `get_director_notes` + notes returned
by every `submit_script`. **One AI path**: `providers.ai_enabled / ensure_ai / fingerprint`; the pipeline no longer prepares the
local model when Claude is chosen; scripts made through the Claude login are labelled "claude".
*Real run (owner's gemma4):* first plan 51 s with one revise round (score 88); "trip over a coin and laugh" → s3 jump, fall,
look at (score 94; the model ignored the coin and the laugh); "drop a coin and chase it" → drop, chase, run (score 100).
*Not yet:* the separate treatment and per-section storyboard passes (the AI still writes the whole script in one call, then
revises), the P13.5 gate on 8 transcripts.
Treatment → storyboard per section → **critic** (`vt/script/critic.py`: interest metrics, scene-by-scene issues) → revise (≤2
rounds) → deterministic enricher. For every style, not just stick figures. Then **talk to the director** (`/director/chat`):
"make it funnier", "shorter", "the owner is an old man" → validated operations on the timeline.
**Gate:** old P13.5 targets (characters = named people, ≥2 places, ≥8 verbs per 10 sentences, talk share ≤0.30, nothing new
for ≤2.8 s) on 8 transcripts, rules and AI; contact sheets looked at.

### M4 — Watch and revise · built 2026-10-23 (one round; unmeasured on real risky videos)
*Built:* `watch_and_revise` in the autopilot: risk > 35 → the scorecard's worst moments go to the director as a "viewer test"
note → render → score; the new cut is kept only if its risk is lower, otherwise the first plan and video come back; `revise.json`;
the Result screen says what happened. Needs an AI and a Video Script. Tests: kept / rolled back / skipped.
After compose: scorecard + vision check → the worst three moments go back to the director as issues → re-plan only those
scenes → re-score. Stop when the risk score no longer improves. Show "what I fixed" on the Result screen.
**Gate:** risk score lower than the single-pass baseline on all QA videos; never worse.

### M5 — Sound that feels edited · built 2026-10-23
*Built:* `vt/beatsync.py`: tempo + phase (spectral-flux onsets, autocorrelation, joint fine search; within 0.05 BPM and < 25 ms on
click tracks; agrees with librosa within 1–2 BPM on real tracks), pictures and sound cues moved onto the nearest beat when ≤ 0.12 s
away (never the opening picture, never out of the scene; 5 of 8 on the reference), cache in the data folder; option `beat_sync`.
Five real tracks from video-shotcraft (Mixkit licence) added (10 in all). **Auto music** (`vt/musicpick.py`: from the context's mood,
stable per project) is the default for new videos. Real render: −14.6 LUFS, −1.3 dBTP. *Not yet:* music swells at the payoff.
Old P12.3 (a real SFX/music library from video-shotcraft), P12.4 (beat sync: scene cuts and pops on beats when music is on),
music chosen by mood and section energy, music swells at the payoff.
**Gate:** cuts within 1 frame of a beat when beat sync is on; a person listens to 3 videos.

### M6 — Captions and emphasis · pop style built 2026-10-23
*Built:* caption style **pop** (big white words, thick outline under the fill, 3 words at a time, the spoken word lights up in the
theme's highlight colour and bounces); option `caption_style` (theme / auto / pop / box / pill / underline); new videos from the
Make screen use auto (pop for vertical). Looked at on the Banglish reference: Bangla shaping correct. Goldens unchanged and green.
*Not yet:* emoji in captions, punch-in on emphasised words.
Caption style presets (bold pop, box, karaoke fill) chosen per platform and mood; one keyword pop per sentence with an emoji
when it fits; punch-in on emphasised words for A-roll.
**Gate:** contrast and safe-area tests in all shapes; Bangla shaping golden test.

### M7 — Variants and learning · learning built 2026-10-23, variants not
*Built:* `vt/taste.py`: a spelling corrected the same way in two videos joins the global glossary; the same look chosen twice in a
row becomes the default; notes to the director become a hint for the next video's director. Tests isolate the owner's files.
*Not yet:* hook variants.
Three hook variants rendered as short previews, the AI (or the person) picks; the creator's edits are recorded and become
preferences for the next video (look, music, pace, glossary, what they always undo). Old P9.3 step 6 (import platform retention
CSVs) when the owner has data.

### M8 — Product (old Phases 7, 8, 11, 12.7) · 30–40 h
Named things get real logos and flags (old P8); clean the repo, one launch script, one installer per platform (old P11);
CapCut/JianYing draft export (old P12.7).

**Not doing / closed:** StykAnimate/Pivot interop (needs sample files; old H.10), image generation (rejected on quality; old
H.2-8), a Rust rewrite (old P6.1).

---

## 5. What is true today (verified, with dates)

* Pipeline end to end on real material (Bangla and English recordings, YouTube links, scripts), all shapes, upload-ready
  encoding (old H.4, H.11). ~600 fast tests pass (old P7.4, 2026-10-23).
* AI providers: Ollama (owner's LAN server), Claude via the owner's login (`claude -p`), Claude API, OpenAI-compatible, MCP
  for any assistant (old H.10, P15.5).
* Context reading, retention scorecard, heartbeat, A-roll, stick-figure vocabulary and rules director v2, ONNX voice cloning on
  one Python environment (old P10, P9, P5, P13.7, P7.4).
* **2026-10-23 (this revision):** `language: "auto"` wired for recordings (speech detection, Bangla/English only, falls back to
  Bangla), scripts (by letters; the voice follows the language) and links (listen instead of fetching subtitles).
  `tests/test_auto_language.py` (4) pass. New Make screen built, type-checked, built and looked at in screenshots at 1280 and
  390 px on an isolated server.

* **2026-10-23, second round (M1 + M2.1–2):** autopilot (`autopilot_finish`: render, retention scorecard, publish kit,
  AI title for unnamed videos), Making and Result screens, Steps sheet, top-bar fixes, retakes, tighten, decisions API with
  Put back. Tests: `test_autopilot.py` (5), `test_retakes.py` (7), `test_tighten.py` (3), `test_auto_language.py` (4); full fast
  suite passes. Browser suites on an isolated server: simple 13/13, flows 26/26, editor 24/24, dashboard 11/11 (×2),
  link 11/11, edge 21/21, design 16/16. Suites updated for the new screen: link, edge, design, journey, dashboard, editor.
  `journey` (needs the speech model) was updated but not run.

* **2026-10-23, third round (M3–M7):** tests `test_ai_gate` 3, `test_critic` 3, `test_director_chat` 2, `test_autopilot` 9,
  `test_beatsync` 5, `test_music_auto` 2, `test_caption_style` 4, `test_taste` 4; fast suite and slow render goldens pass; browser
  suites on an isolated server: flows 26, editor 24, dashboard 11 (×2), link 11, edge 21, design 16, simple 13, **director 3**
  (real gemma4: note sent from the Result screen, answer shown, video re-rendered).
* Seen in a frame of the demo video (pre-existing, not fixed): the first scene draws the title word twice behind the "?" bubble.

* **2026-10-23, fourth round: the owner's two samples, end to end in the real Studio, zero clicks.**
  `english sample.mp3` (3:47, a parable) and `bengali sample.mp3` (4:50, the wolf and the crane), with the Make-screen defaults and
  the Claude login as the brain. Found and fixed, each with a test:
  * **Server crash** on every recording with sound detection: the new language detection loaded faster-whisper before torch's
    CUDA libraries, so the sound classifier died with "Could not load symbol cudnnGetLibConfig" and took the server down.
    `gpu.prepare()` now runs first (in `langdetect` and at the start of every pipeline run); ONNX "is it installed" checks no
    longer load the library.
  * **Empty screens** (the old P9.1 root cause): a scene laid out every element at once, including ones not yet shown, so five
    pictures sat at 40 % size. `composer.paginate`: a scene of separate pictures becomes one shot per new picture (pictures arriving
    within 0.35 s stay together; no shot under 1.2 s), each laid out alone; build-ups (cards, arrows, rows, charts, lists, the
    reference look) stay on one screen. Stickers, keywords, tags and titles may grow to fill the stage. Editor picking keeps working
    (pages carry `src` scene id and `_i` element index). English sample: risk 76 → 49, hook 4.0 → 0 s.
  * **Shortening cut the plot** of a story (31 sentences). Stories (context mood, story roles, or openers/dialogue in the words,
    Bangla included) now only lose filler. English: 3 sentences dropped.
  * **Retake false positive**: "Some said 500, some said 800" (a list) was cut. A false start must repeat the whole phrase, a cut-off
    word, or a long shared opening.
  * **Invented words** in Bangla recognition ("ট্রেনের" at the end of the story): segments that loop a word are rejected, and a
    low-confidence word the model invented elsewhere on the same recording is dropped (`asr.looped`, `JUNK_CONF`).
  * Unnamed uploads were titled "Untitled" and never got the AI title; a rejected revise left two videos (WinError 32 on delete).
  Results: English "The Price of Time: A Father's Lesson to His Lazy Son", Bangla "নেকড়ে আর বকের গল্প: গলায় হাড় আটকালে কী হলো" (risk 30, Good).
  Still weak: fast speech makes captions hard to read (6–7 words/s), a 16 s still stretch in the Bangla video (its plan was kept
  from the earlier run), sentence fragments from Bangla recognition (no punctuation) are split into separate "sentences".

* **2026-10-24, fifth round: podcast footage, stick figures, cartoons.**
  * Podcast clip (`P_snippet_AMS_2.mp4`, 2 people, multi-camera, burned-in subtitles), vertical: **shot-by-shot face tracking**
    (`aroll.shot_track`: camera cuts from frame differences, the face per shot, the people mask when no face is seen, one person in a
    two-shot; the renderer re-aims the crop at each cut), each scene's own framing is now actually used (it was computed but ignored),
    per-frame faces instead of the clip's average face, **burned-in subtitles detected and zoomed out of frame** (`aroll.text_band`).
    16 of 16 checked frames have a person centred; risk 32.
  * Bangla sample: pictures showed at the wrong words after recognition ran again (positional word ids shifted under a kept plan):
    `plan_basis.json` records what each id meant; a stale plan is redone. Sound stickers speak the video's language ("কাশি", not
    "Person coughing").
  * Dashboard card menus were clipped by the card: the design-system Popover now draws in a portal and flips at the edges
    (`e2e/menus.mjs`, 4/4).
  * Stick figures (the English parable as a stick video): critic 94, 3 characters, 5 places, 26 verbs, talk 23 %, risk 17. Vertical
    stage made a closer shot (figures ~2× bigger) with labels in a band above the figures.
  * **Cartoon style** (art and mouth rig from Cartoon Studio, Apache-2.0, `third_party/cartoon-studio/NOTICE.md`): illustrated characters
    as a cast kind `toon`, painted places as `set.art`, mouths follow the voice (any language); `toonify` turns any stick script into a
    cartoon; the director chat keeps a cartoon a cartoon. Rendered the parable: full-bleed painted backyard / living room / street.
    **Limits:** 4 characters (2 boys, a girl, a dog: no adults, so a father is played by a boy) and 4 places; growing the cast needs art
    (Cartoon Studio uses Recraft text-to-SVG with a paid key). Line-drawn props on painted sets, a tiny "First Second Third" element,
    a title over a busy painting without a backing.

### Referenced repositories: what is in, what is not (audit 2026-10-24)
| Repo | In the app | Not in the app |
|---|---|---|
| video-shotcraft (124 motion recipe cards for Remotion, Ink Press template, SFX/BGM, beat sync, QA rules, JianYing export, publishing) | 5 BGM tracks, beat sync (own implementation), sound effects library (from the owner's SFX folder, roles like theirs) | **the 124 motion recipes** (22 typography, 21 UI entrances, 15 transitions, 15 effects, 11 openings, 10 camera, 8 rhythm, 6 outros, 5 data; Remotion/React, must be re-made in GSAP), JianYing/CapCut draft export, auto-publishing |
| Cartoon Studio | characters, scenes, mouth rig (this round) | text-to-SVG character generation (Recraft, paid), its Stage/Dialogue screens |
| Concat (Rust editor) | Chatterbox Turbo ONNX voice cloning (port), cutout, ideas for the multi-track timeline and transcript panel | the native engine, ~100 effects, 4K/10-bit export, upscaling |
| StykAnimate | none (clean-room stick engine; interop closed for lack of sample files) | `.stk/.piv` import/export |
| faceless-short, Remotion prompt-to-video | the idea (script to faceless short) | no code |
| AI-Youtube-Shorts-Generator (Anil Matcha) | Virality framework, hook scores, NMS dedupe, 20m overlap chunks, multi-short extraction | Cloned to `third_party/ai-youtube-shorts-generator`; full architectural plan in [PLAN-SHORTS.MD](../plans/PLAN-SHORTS.MD) |


**Motion graphics automatically:** today the app animates 39 infographic elements, stickers, captions and camera moves by itself; the
big missing piece is shotcraft's recipe library (kinetic typography, openings, transitions). Porting it is the next big M5/M6 job.

* **2026-10-24, sixth round: motion graphics, layout guard, animals, local vision.**
  * **Motion graphics, automatically** (`renderer/runtime/vt-motion.js`, `vt/compose/motion.py`): the shotcraft cards realised as 50 GSAP
    recipes (25 element entrances, 16 scene transitions, openings, outros, camera and rhythm moves), all **124 cards mapped** (a test
    fails if one is missing), chosen per element by role (numbers count up, questions glitch, quotes type out), no repeats in a row,
    an opening and an outro, deterministic per project, option `motion` auto / subtle / off. Real videos use ~45 recipes each with no
    script errors (`e2e/motion.mjs` also fails on any element visible before its entrance). The marquee outro is realised but not
    chosen (its text band collided with labels).
  * **Layout guard** (renderer, after layout): cut off > 12 % → shrink, or drop if optional; overlap > 18 % of the smaller box → the
    lower-ranked element goes; optional labels under 26 px are dropped; stick/cartoon props cut by more than a quarter are not drawn;
    figures under 3:1 WCAG contrast with the background are drawn in the theme ink; speech bubbles clamped to the frame by their real
    size. Decisions in `window.__guard`. Stick and cartoon scenes now page their labels too (hard cuts, the figures continue).
  * **Animals are never people** (`vt/script/animals.py`, ~35 animals in English and Bangla → animal actors).
  * **Local vision QA** in autopilot on the rendered frames (up to 20 scenes) feeding the director's revise step. Measured
    (`scripts/eval_vision.py`, 6 labelled frames): llama3.2-vision with one focused yes/no question per problem 0.83 precision /
    0.83 recall; qwen2.5vl:7b checklist 0.67 / 0.17; gemma4 checklist 0.50 / 1.00. Now the default. The sample is small and has no
    clean frames yet: false alarms on good frames are not measured.
  * Six typed stories through the zero-click path (before the guard): risk 0-24, critic 94-100, AI titles in both languages.
  * Fixed on the way: bar-chart labels visible before the chart, a renderer syntax error that blanked stick videos (now a test
    syntax-checks every runtime file), count-ups showing the wrong number on a still.

* **2026-10-24, seventh round: six typed stories, iterated until every scene holds** (`scripts/qa_stories.py`, frame grids looked at
  after every round). Final viewer-retention risk (lower is better): lion and mouse (bn, stick) 0, exam dialogue (bn, stick) 0,
  rain (bn, explainer) 2, kids and dog (en, cartoon) 8, sleep habits (en, emoji) 8, compound interest (en, explainer) 21; director's
  critic 94-100 on all. What the rounds found and fixed: animals drawn sticker-size (now cast-size when no people, a mouse smaller than
  a lion); the guard dropping re-flowed elements (now measured on the scene's last frame) and stickers by their caption (the small-text
  rule is for tags only); a transition leaving the old scene at 40 % for the rest of a render (only when frames are played forward:
  `e2e/motion.mjs` now steps through every frame); the vision model's false "cut off" (confirmed by an edge-pixel test,
  `vision.edge_content`); build-ups of four or more items kept small (now cut at their biggest pause, pictures before a build-up get
  their own shot; the titled reference look is unchanged); a lone element only allowed to grow 1.7× (now 2.6×).
  What remains: fast narrators (5-7 words a second) make captions hard to read; the scorecard counts it against every video.

**Round 8 (2026-10-24): think like an editor: modes, one question per screen, a calmer dashboard, easier editing.**

What an editor expects from an AI editing tool, and where the app stood:

| Editor expects | Done this round |
| --- | --- |
| It knows what it was given (a talking head is not a voice memo) | `vt/source_inspect.py`: six frames, face detection → `talking_head` / `video` / `audio`; `POST /api/inspect`; stored per project as `source.json`, shown as `source_mode` |
| A different edit for a talking head | The New flow asks "Keep the speaker on screen / Graphics only" only for videos (sets `options.aroll`); the editor's title bar switches Talking head ⇄ Graphics only in one undo step (`/aroll/apply`) |
| Start with questions, not a form | `studio/src/pages/New.tsx`: Typeform-style screens (source → mode → style → shape → look → sound → voice → ready), a best answer pre-picked, Enter moves on, letters pick, Escape goes back; the last screen shows the detected language and starts the process; everything else under Fine tuning |
| A dashboard that shows videos, not controls | `pages/Projects.tsx`: New video card + covers with one status line and one menu; search only from 9 videos; covers fall back to a frame of the latest export |
| Click a thing, edit that thing | Inspector tabs Elements / Characters / Scene; picking on the canvas or timeline opens Elements on that element |
| Recast and restyle characters | `review/CastEditor.tsx`: played by stick figure / cartoon (bill, ted, jane, max) / any of 34 animals; age, line, clothes and skin colour, head, hair, accessory; `GET /api/cast-options`; `scene_ops.edit_cast` accepts kind, art, emoji |
| A fast app | Every screen except the dashboard loads on demand: first load 184 KB (was ~450 KB); the editor (143 KB) loads when opened |

Verified: fast pytest suite green; new tests `test_source_inspect.py` (audio, faceless video, the podcast sample is a talking head, endpoint) and the recast test in `test_stick_edit.py`; e2e `flow.mjs` (keyboard walk of every screen, podcast detected as a talking head, no sideways scroll on a phone), `dashboard.mjs` (rewritten, 10 checks), `menus.mjs` (menus fully visible at 1280 and 390 px). Recasting the host as cartoon Bill redrew the preview live.

Next for this direction: show the speaker split-screen for a wide two-person podcast; per-character voice for scripts; a mode chip on Progress/Result; Bangla labels for the New flow questions (the app's other strings already have them).

**Not verified / be honest:** recognition quality on real noisy phone recordings; picture judge and vision QA quality on real
videos with a real vision model; Bangla UI strings are machine-drafted; music library never auditioned; installer unsigned,
Windows only; retakes and tighten have only been tested on constructed transcripts, never judged on the owner's real phone
recordings (the M2 gate).

---

## 6. Engineering rules (condensed from old H.2, H.7)

* AI: one interface `ai.complete_json(prompt, schema, images=None)`; schema-constrained, Pydantic-validated, one retry with the
  errors, then the rule fallback. Timeouts, cancel, cache keyed by model+prompt+inputs. AI output is untrusted data.
* Every change: `.venv\Scripts\python.exe -m pytest -q -m "not slow"`; render changes also `-m slow`; UI changes: the e2e suite
  for that screen against an isolated server (`VT_DATA=<temp>`; never the owner's settings) and screenshots looked at.
* A bug found by testing gets a regression test first. Never weaken an assertion without writing down why.
* For anything visual, the acceptance artefact is a picture a person has looked at.
* How to run: `.venv\Scripts\vt.exe studio --no-open` (UI rebuild: `cd studio && npm.cmd run build`). Windows: use `npm.cmd`;
  write patch scripts to files rather than heredocs with escapes.
