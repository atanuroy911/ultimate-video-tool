# Video Tool — the plan

> **Vision.** Give it a voice (Bangla, English, Banglish), a talking-head video, a long podcast or a link. Get back finished,
> scroll-stopping videos *and* an editable timeline, with no human step in between. An AI makes every decision a good human
> editor would, says why, and the person only steps in if they want to. The tool that makes a video editor unnecessary.

History lives in `docs/history/` (every round, measurement and bug: `plan-until-2026-10-23.md`, `plan-rounds-2026-10-23-to-25.md`).
Detailed designs and verification status: [Shorts](docs/plans/PLAN-SHORTS.MD), [Social](docs/plans/PLAN-SOCIAL.MD), and the phased plan and proof in [docs/ROADMAP.md](docs/ROADMAP.md) and [docs/STATUS.md](docs/STATUS.md) (start at [docs/README.md](docs/README.md)). This file is the vision and the product description; where it disagrees with STATUS.md, STATUS.md is right.

**Hard rules (owner).** Something changes on screen every ≤3 s, every shape. AI first, rules as the safety net: every AI step has a
schema, a validator, a cache, a rule fallback and provenance; a failed model never breaks the pipeline. Never invent facts: every
word on screen comes from the speaker. Licensing is not a concern. Don't ask; finish the job.

---

## 1. The product: three paths, one timeline

```
 voice / script / link ──► make one video        (/new → /progress → /result)        ✅ zero clicks
 long video / podcast ──► find the viral moments ──► N shorts (child projects)  (/shorts)   ✅ built, unmeasured
 finished video ──► post to every channel        (/social)                             ◐ built; live posting unverified
```

Everything lands on the **same editable timeline** (`scenes.json` + layers + cut list). The MP4 is rendered from it. No AI step may
produce something only the renderer knows about; every AI decision is an ordinary, undoable edit that carries *who* made it and *why*.

**The one principle (owner, 2026-10-26): the audio is the master and is decided first.** Clean and cut the audio; a script is spoken one
sentence at a time so its real length is known. Then a director, working only from facts measured in the audio, decides the video's goal
and style and marks **impact points** (the word or sound where the picture must change; the same sentence is cut at *fake* or at
*powerful* depending on the goal). Every cut lands on one; slots are variable. What fills a slot is the cheapest medium that carries
the impact: the speaker, a graphic, stock, a still with a slow zoom, an illustration, a character scene, or (the most expensive) a 2-4 s
silent generated clip. Never scenes first. Full plan: [PLAN-AUDIO-FIRST-DIRECTOR.MD](docs/plans/PLAN-AUDIO-FIRST-DIRECTOR.MD).

**Modes.** The app looks at what it was given (`vt/source_inspect.py`): `talking_head` (a face on camera: keep the speaker, frame
the face, graphics around it), `video` (keep the picture, graphics on top), `audio` / script (every picture is made). The mode drives
the pipeline (`options.aroll`) and can be flipped in the editor in one undo step.

**The pipeline, the AI as the editor**
```
listen ─► understand ─► EDIT THE TALK ─► DIRECT ─► build timeline ─► WATCH & REVISE ─► render + publish kit
asr+lang  context.json   retakes, tighten,  script,    scenes.json      scorecard + local vision QA
auto      roles, cast    target length      critic,    + motion +        → director fixes weak scenes
                                            enrich     layout guard      (≤2 rounds, kept only if better)
```

---

## 2. The editor's yardstick: what an AI editor must do, and where we are

✅ done · ◐ built but not judged on real material · ✗ missing

| The editor… | Status |
|---|---|
| hears the language, writes every word (Banglish too) | ✅ auto language; Bangla fine-tune + Whisper; junk-word rejection |
| knows what it was given (talking head / video / voice) | ✅ face detection on six frames; the podcast sample detects as a talking head |
| cuts silences, "um"s, retakes, false starts; keeps the last take | ✅ shown on Result with "Put back" |
| tightens a ramble to the platform length (60 s / 90 s) without cutting the plot | ◐ rules + context roles; stories only lose filler; **never judged on the owner's phone recordings (M2 gate)** |
| opens on the strongest line (cold open) and a ≤6-word hook title | ◐ hook title from frame 1; **cold open not built** (cut list assumed in time order) |
| finds the 3–5 viral moments in an hour of podcast | ◐ `vt/shorts/detector.py`: virality prompt (hook, emotion, opinion, revelation, tension, quote, story peak, value), 20-min chunks, NMS dedupe, sentence snapping, rule fallback; **never measured against a human's picks** |
| shows what is said: pictures, icons, charts, numbers | ✅ 39 element types, icon meaning search, one shot per new picture |
| fills a gap with a few seconds of footage that does not exist (a story beat, an abstract idea) | ◐ the **tool** exists and works: a still becomes silent B-roll on the ComfyUI server (LTX-2.3 or Wan 2.2), framed on its subject, placed on the timeline, captions on top, verified on the V100 ([plan](docs/plans/PLAN-COMFYUI-VIDEO.MD), [server](docs/ops/comfyui-server.md)). **The editor's judgement does not**: nothing yet chooses which sentences need footage, writes the picture from the speaker's words, or checks it matches. First tests used an unrelated stock picture. |
| keeps the speaker in shot, on the face, through camera cuts | ✅ shot-by-shot face tracking, burned-in subtitles zoomed out; ◐ punch-ins; ✗ split screen for a wide two-shot |
| tells stories with characters | ✅ stick figures (58 verbs, 23 places), cartoon (4 characters, 4 places), animals are animals; director critic 94–100 on 6 stories |
| motion graphics that feel edited | ✅ all 124 shotcraft cards as 50 GSAP recipes, chosen by role, deterministic; layout guard (cut-off, overlap, contrast, bubbles) |
| captions most people read muted | ✅ pop style, word lit as spoken; ◐ fast narrators (5–7 words/s) stay hard to read |
| music that fits, ducked, cuts on the beat | ✅ auto pick by mood, beat sync, −14 LUFS; ✗ swell at the payoff; library never auditioned |
| watches it back and fixes the weak moments | ✅ scorecard + local vision QA → director revise, kept only if risk drops; ◐ vision eval on 6 frames only |
| packages it: cover, title, description, hashtags | ✅ publish kit, AI title |
| posts it everywhere | ◐ Social queue and four platform upload flows built; real posts on owner accounts not verified |
| learns the creator's taste | ◐ repeated spelling fixes → glossary, repeated look → default, director notes → next hint |

**Where the app is weak:** judgement on *real* recordings (tighten, hook, highlight picks) is built but unmeasured; the cold open
and split screen are missing; publishing does not exist.

---

## 3. The UI

Three screens for the zero-click path, the editor one click away; everything at 390 px; one primary button per screen; keyboard reachable.

| Screen | What it is | Status |
|---|---|---|
| **Dashboard** `/` | A "New video" card, then covers with one status line and one menu. Search from 9 videos. | ✅ |
| **New** `/new` | One question per screen (Typeform): source → *(video)* keep the speaker? → style → shape → look → sound → *(script)* voice → Ready. Best answer pre-picked; Enter moves on, A–E picks, Esc back. Last screen shows the detected language and starts. Fine tuning behind one row. English and বাংলা. | ✅ |
| **Progress** / **Result** | Plain-words steps; the finished video, one sentence from the viewer check, Download / Change look / Fix a word / Edit everything, what the editor cut (Put back), talk to the director, publish kit. | ✅; ✗ mode chip, live preview |
| **Shorts** `/shorts`, `/p/:id/shorts` | Candidates with virality score, hook quote, reason; create child projects / batch slice; open in the editor. | ◐ built and unit tested; real long-video gate unverified |
| **Editor** `/p/:id` | Inspector tabs Elements / Characters / Scene; click a thing on canvas or timeline → its fields. Character editor: stick figure / cartoon / animal, age, colours, head, hair, wear. Mode switch in the title bar. | ✅ |
| **Social** `/social` | Groups of accounts, dispatch from Result, task-flow table with logs. | ◐ built and mock tested; live account gate unverified |

Pattern rules: option sheets are Apple-style steps (`Steps`, `Group`, `Row` in `studio/src/ds/`); screens load on demand (first
load 184 KB); descriptive names, small modules.

---

## 4. What is left, in order

Each milestone has a measured gate. Nothing moves to ✅ without it.

**0. Everything is a module, and the audio decides ([modules plan](docs/plans/PLAN-DIRECTOR-MODULES.MD), [audio-first plan](docs/plans/PLAN-AUDIO-FIRST-DIRECTOR.MD)) · next; everything below waits on its first phases.**
Owner's decision, 2026-10-26: every capability becomes a module with declared inputs and outputs (about 145, every existing file mapped), and the
director, whether rules, a plan from one LLM call, a tool-calling agent, or Claude Code / Codex / Gemini CLI over MCP, calls any module at any point;
prerequisites run automatically; every call is logged with its reason and can be replayed without an LLM. Build order: (0) the contract spike (registry,
workspace of typed artifacts, executor, call log, budgets, locks; three real modules); (1) the 12 pipeline stages as modules with **byte-identical** output
and `Pipeline.run` going through them; (2) every other existing component wrapped, in six slices; (3) the surfaces (MCP tools generated from the registry, the old
31 names kept as aliases, `/api/modules`, `vt call`, a Director log in the Studio); (4) the new modules (measured word onsets for scripts, `understand.impact_map`,
`direct.set_direction`, `cut.*`, `judge.facts`, `judge.impact_alignment`, the still-series fill); (5) the directors and the evaluation set; (6) generated clips
wired in; (7) hardening; (5b) **the plan review**: after the quick listening phase the plan is shown in plain words (idea, where the picture changes, what is in each moment, time and cost), editable, and nothing expensive starts until *Start*; (8) the Studio as the director's seat. A **Details** button opens the full live director log at any time. Gates are in the plans. The ComfyUI tool the generated-clip modules call is built and verified
([server](docs/ops/comfyui-server.md)); nothing decides *whether, where or what* to generate yet.

**A. Shorts, end to end.** Run the podcast sample and one ≥30-min video through `/shorts`: detect → slice → the child projects
go through the normal pipeline → 9:16 renders. Add `e2e/shorts.mjs` and screenshots. *Gate:* on 3 long videos a person agrees with
≥3 of the top 5 picks; no clip starts or ends mid-sentence; each child renders with the speaker on the face.

**B. The M2 gate on real recordings.** Five of the owner's phone recordings, Bangla and English: cut vs uncut rated by a person;
no cut mid-word; hook ≤1 s. Fix what it finds in `retakes.py` / `tighten.py`.

**C. Cold open.** `Cuts.lead` (a source range played first), `map_time` offsets the body, teaser words get ids `t<n>`, every `keep`
iterator takes the lead first, never with an A-roll. Editor tests. *Gate:* `hook_s` = 0 on the QA set, no caption drift.

**D. Talking-head polish.** Split screen for a wide two-shot; punch-ins on emphasised words; mode chip on Progress/Result.
*Gate:* 16/16 frames with a person centred on the podcast sample in all three shapes.

**E. Social publishing** ([detailed plan](docs/plans/PLAN-SOCIAL.MD)): queue, upload flows, dispatch from Result and
task-flow screen are built. Direct dispatch from Shorts is still via each child's Result screen. *Gate:* one real post per platform on the owner's accounts, permalink stored.

**F. Taste and variants.** Three hook variants rendered as previews, best picked by the scorecard; the creator's undos become
preferences. *Gate:* the second video of a creator needs fewer edits than the first.

**G. Product.** Real logos/flags for named things, one installer per platform, CapCut/JianYing draft export, more cartoon cast
(adults; needs art).

**Closed:** StykAnimate interop, image generation, Rust rewrite.

---

## 5. The algorithms behind the judgement (from the literature, all local, all rule-checked)

The AI is one voice among measured signals. Each gap in §2 now has a published method behind it; a model may add to it, never replace it.

| Judgement | Method | Paper | Where |
|---|---|---|---|
| Which sentences carry the talk | LexRank: TF-IDF cosine graph, eigenvector centrality (continuous weights, Bangla suffix stemming) | Erkan & Radev, JAIR 2004 (arXiv 1109.2128); TextRank, Mihalcea & Tarau 2004 | `vt/saliency.py` → `tighten.choose` (among equals the least central goes first; alone when no AI reading), shorts windows |
| Several shorts that are not the same moment | Maximal Marginal Relevance, λ=0.7 over time overlap ∨ text similarity | Carbonell & Goldstein, SIGIR 1998 | `saliency.mmr_select` → `shorts.detector.pick_diverse` |
| A podcast's highlights | AI virality score fused 0.5/0.2/0.2/0.1 with centrality, prosodic arousal, laughter/applause share; zero-shot LLMs alone ≈ a frequency baseline, speech features add to every model | Rhapsody, arXiv 2505.19429; transcript-saliency reward of arXiv 2505.23268 | `detector.measured_signals`, `fuse_scores`; the rule fallback uses the same signals |
| How animated the speaker is | Normalised-autocorrelation pitch (YIN/RAPT core), RMS dB, speech rate, pause share; speaker-relative z-scores averaged | Shriberg, Bates & Stolcke 1997; IBM call-centre prosody; arXiv 2307.02132 (rate↔arousal) | `vt/prosody.py` |
| Sentence ends without punctuation (Bangla ASR) | Pause at the word boundary above the speaker's own distribution: median + 2.5·MAD, floor 0.35 s, ceiling 0.9 s; fragments < 3 words join a neighbour | Shriberg, Stolcke, Hakkani-Tür & Tür, Speech Comm. 2000; Kolář, Shriberg & Liu 2006 | `vt/pausesplit.py` → shorts sentence grouping |
| Following the face without jitter | L1-optimal camera path: LP minimising |D¹p|+|D²p|+|D³p| (weights 10/1/100) with the face within 8 % of the crop centre; the path is still, a pan or an ease; renderer glides between its ends | Grundmann, Kwatra & Essa, CVPR 2011 | `vt/camerapath.py` → `aroll.smooth_pan`, `shots[4]`, `vt-media.js` |
| Camera cuts | Mean-grey jump ∨ colour-histogram χ² above mean + 3σ (adaptive) | Google AutoFlip (2020) shot boundary | `aroll.camera_cuts` |
| Captions people can read | Characters a second: 12 cps comfortable (six-second rule), 17 cps ceiling; fast chunks split, scorecard flags > 17 cps; breaks at punctuation first | Díaz-Cintas & Remael 2007; Szarkowska et al. eye tracking (JEMR); Perego on syntactic breaks | `composer.build_caption_chunks` (READ_CPS), `retention.reading_speed` |
| Cuts on the beat | Spectral-flux onsets, autocorrelation tempo, phase search (an Ellis-style tracker without the DP pass) | Ellis, J. New Music Res. 2007 | `vt/beatsync.py` |
| The hook window | First peak of watch time falls before 5 s; the scorecard's hook target is 1 s and it penalises up to 4 s | Snap/CUHK, ECCV 2024 engagement study | `retention.TARGETS` |

| Which word carries the impact | Word stress from pitch, energy and duration through a continuous wavelet transform, no training; text-only stress prediction as a cross-check; the goal picks among candidates | Suni et al. 2017; Tamburini 2005; arXiv 1908.02262 | planned `vt/impact.py` |
| A sound that deserves a cut | A time-only auditory saliency curve: peaks where pitch, intensity or timbre deviate from the background | Kayser et al. 2005; Kaya & Elhilali 2012, 2014 | planned `vt/impact.py` (with `sounds.py`) |
| Where a cut is safe, and how it should feel | Cut where the speaker is quiet and still; serve emotion before story before rhythm; every edit costs an orienting response; shot lengths should vary like attention (1/f); gaze goes to the centre after a cut | Berthouzoz, Li & Agrawala 2012; Murch; Lang (LC4MP); Cutting et al. 2010; Smith & Henderson 2010 | planned `vt/cutplan.py` rules (see §4 of the plan; the research caveats are listed there) |
| A plan before the pictures | An LLM writes scenes, entities and consistency groups first; narration beats aligned to clips by dynamic programming | VideoDirectorGPT 2023; QuickCut 2016 | planned `vt/direction/` |
| Hook and ending | A curiosity gap in the opening; the strongest moment last (peak-end, evidence mixed) | Loewenstein 1994; Fredrickson & Kahneman 1993 | planned director rules |

Still to take from the literature: a disfluency model with prosodic cues for retakes (Shriberg 1997, the ICSI 2003 rules; today word repetition only), a trained
laughter detector (the ICSI/Gillick ResNet; today AudioSet labels), TransNet V2 for cuts if the histogram test misses dissolves, Rhapsody-style fine-tuning once
we have "most replayed" labels of our own.

---

## 6. What is true today (verified)

* Pipeline end to end on real material in all shapes; ~650 fast tests and the slow render goldens pass; browser suites on an isolated
  server: simple 10, flow, dashboard 10, menus 4, editor 24, stick 9, motion, director 3 (real gemma4).
* Owner's samples, zero clicks: English parable (risk 49 → stick 17), Bangla wolf-and-crane (risk 30), podcast clip (risk 32, 16/16
  frames on a face), six typed stories risk 0–21 with critic 94–100.
* Brains: Ollama on the owner's LAN (gemma4, llama3.2-vision for frames: 0.83 precision/recall on 6 labelled frames), Claude via the
  owner's login, Claude API, OpenAI-compatible, MCP for any assistant.
* Shorts: detector (AI + measured signals, MMR pick), pause-based sentences, splitter into 9:16 child projects, routes and Studio page; automated detector/slicer tests pass. Social: SQLite queue, four upload flows, task UI and mock dispatch tests pass.

**Not verified, honestly:** recognition on noisy phone audio; tighten/retakes/highlights on real recordings; vision QA false alarms on
clean frames; the Shorts page in a browser and picks on three long videos; one live post on each platform; Bangla UI strings are machine-drafted; music never auditioned; installer unsigned, Windows only.

---

## 7. Engineering rules

* AI: one interface `ai.complete_json(prompt, schema, images=None)`; schema-constrained, validated, one repair retry, then rules;
  cache by model+prompt+inputs; AI output is untrusted data.
* Every change: `.venv\Scripts\python.exe -m pytest -q -m "not slow"` (render changes also `-m slow`); UI changes: the e2e suite for
  that screen on an isolated server (`VT_DATA=<temp>`, port 8777, never the owner's settings) and screenshots a person has looked at.
* A bug found by testing gets its regression test first. Never weaken an assertion without writing why.
* Code reads like prose: descriptive names, one job per module, the editor's reasoning in the docstring.
* Run: `.venv\Scripts\vt.exe studio --no-open`; UI rebuild `cd studio && npm.cmd run build`. Windows: `npm.cmd`, patch scripts as files.
