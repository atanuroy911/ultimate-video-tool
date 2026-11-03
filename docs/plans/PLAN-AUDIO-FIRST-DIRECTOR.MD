# Audio-first direction: cut on impact, let the director choose what fills each cut

Written 2026-10-26 from the owner's decisions and the research listed in §8. This plan replaces the earlier idea of "generate scenes, then fit audio". Read §1 and §2 first; the rest is detail for whoever builds it.

> **Delivery (decided 2026-10-26): every step below is a module the director can call**, with declared inputs and outputs: see [PLAN-DIRECTOR-MODULES.MD](PLAN-DIRECTOR-MODULES.MD), which defines the module contract, the full catalogue (about 145 modules, every existing file mapped), the three director levels and the build phases. This plan says *what the director decides*; that plan says *what it can call and how*. The phases in §7 here are the **new-module** phases (4 to 6) of the modules plan; phases 0 to 3 there (the contract, the pipeline as modules, wrapping every existing component, the surfaces) come first.
>
> **Correction.** An earlier draft called stress measurement new. It is not: `server/vt/visuals/emphasis.py` already measures, per word, peak loudness, pitch (F0) and duration per letter, each as a robust z-score against the speaker's own recording, combined 0.40 / 0.35 / 0.25, and `server/vt/visuals/picker.py` already scores the word to illustrate as 0.45 stress + 0.20 rarity + 0.35 picturability. What is new is the *goal*: the same stress score is weighed by relevance to the director's goal, and the wavelet prominence method is an upgrade behind a `method` input, to be kept only if it beats the existing one on the direction set.

## 1. The idea in one paragraph

**The audio is the master and it is decided first.** We listen to the recording (or to speech made from a script, one sentence at a time, so its real length is known), clean it and cut it. Then a **director** (Claude, Codex or Gemini, any of them) listens in the only way software can: through facts measured from the audio. It decides the video's *goal* and *style*, then marks the **impact points**: the exact word or sound where the picture must change. Every cut lands on one. What fills the time between two cuts is chosen by the director from a short menu (the speaker's own picture, a graphic, a stock clip, a still with a slow zoom, an illustration, a stick-figure or cartoon scene, or a 2–4 second generated clip), cheapest sufficient medium first. Generated clips are small, silent inserts; their audio is never used.

```
 recording ─┐
            ├─► clean + cut audio ─► IMPACT MAP ─► DIRECTOR ─► CUT PLAN ─► FILL EACH CUT ─► assemble ─► judge
 script ────┘   (per-sentence       (where could   (goal, style, (cuts on    (cheapest medium   (captions,   (does the picture
   speech per     speech: exact       a cut hurt?)   budget,       impact      that carries the   music, SFX)  change on the
   sentence)      lengths)                           pacing)       points)     impact)                         impact?)
```

**The person sees the plan before it runs, and can open a live log while it works** (decided 2026-10-26): after the listening phase the director's plan is shown in plain words, editable, and nothing expensive starts until *Start*; a **Details** button opens the full director log at any time. Specified in [PLAN-DIRECTOR-MODULES.MD](PLAN-DIRECTOR-MODULES.MD) §8.

## 2. Decisions already made (the owner, 2026-10-26)

1. **Audio first, never scenes first.** Generated speech has unpredictable length and our models cannot hold earlier, current and later context while reconciling two moving things. So visuals are derived from measured audio, and a script is spoken one sentence at a time before anything is planned. *(The app already speaks a script one sentence at a time and measures each sentence's real length (`tts.synthesize`), so sentence boundaries are exact. **Word times inside a sentence are not measured, only estimated**: `tts.word_times` splits the sentence in proportion to letter count and snaps to the quietest frame within 70 ms. That is fine for captions and wrong for a cut that must land on one word's onset; see step 0 and phase 2.)*
2. **Slots are variable, set by impact, not by a fixed 3 s.** "Everything we ever thought to be powerful is *fake*": if the goal is *waking up to reality* the cut lands on **fake**; if the goal is *power* it lands on **powerful**. The goal decides which word carries the impact, so the **goal is decided before the cuts**.
3. **The opening is special.** The first visual impact must come within about 3 s or attention is lost. Later pacing changes (§4).
4. **The director decides what keeps attention**, per video style, including how much generated footage is worth its cost. No fixed "20 clips for a minute".
5. **The generator's whole job:** short (2–4 s, any length the slot needs) silent clips of content relevant to the audio at that point, in the style the director set. Audio is fitted afterwards.
6. **A still-image style exists and is first-class:** images changing on the sentences, slow zooms, SVG illustrations, text, and the voice. No animation. (Think a recurring cartoon character in different situations.)
7. **The edit listens to the whole audio, not only the words:** background sounds (laughter, applause, a music hit, a silence, an effect) can be the cut, exactly as an editor cuts on them.
8. **The director's prompt must be excellent and *measured* to be so** (§6). Claude, Codex and Gemini all run the same contract through the one provider interface.
9. MiniMax H3 is dropped. Not in scope.

## 3. Step by step, and where the code stands

| # | Step | What it produces | Status |
|---|---|---|---|
| 0 | **Clean and cut the audio.** Silences, "um"s, retakes, false starts, tightening, loudness; a script is spoken per sentence. **Plus, new: measured word onsets for script speech** (align each spoken sentence's audio with the speech recogniser, using the known text; recordings already have measured times from recognition). | `audio.cut.wav`, `cuts.json`, word times, sentence times | ◐ cleaning, cutting and per-sentence speech ✅ (`server/vt/pipeline.py`, `retakes.py`, `tighten.py`, `tts.py`); measured word times for scripts ✗ (today estimated by letter count) |
| 1 | **Impact map.** Everything about the audio that could justify a cut, with a strength and a reason. | `impact.json` | ✗ new module `understand.impact_map` (`server/vt/impact.py`); its inputs exist: stress (`visuals/emphasis.py`), picturability (`visuals/picker.py`), arousal (`prosody.py`), centrality (`saliency.py`), sound events (`sounds.py`), beats (`beatsync.py`) |
| 2 | **Direction.** Goal, audience, tone, style bible, pacing curve, medium budget, one pass over the whole audio facts. | `direction.json` | ✗ new (`server/vt/direction/`); today's `context.py` + `director/profiles.py` are the seed |
| 3 | **Cut plan.** Choose the cuts from the impact map under the pacing curve and the rules in §4. Each cut: time, the word or sound it lands on, why. | `cutplan.json` (slots) | ✗ new (`server/vt/cutplan.py`); today scenes come from sentence beats (`planner/`) |
| 4 | **Fill each slot** with the cheapest medium that carries the impact (§5). | `scenes.json` as today, plus `generate` jobs | ◐ every medium exists except the director's choosing among them by impact; generated clips: tool built, not wired (`server/vt/comfy/`) |
| 5 | **Assemble.** Captions on top, music with ducking, SFX, beat sync, motion recipes, layout guard. | MP4 + timeline | ✅ built |
| 6 | **Judge and revise.** Retention scorecard, vision QA, director revise. New: *impact alignment* (§6). | `retention.json`, `revise.json` | ◐ built; impact metric new |

The editable timeline stays the product: every step above lands as ordinary, undoable timeline items with *who decided* and *why* attached, so the person can see "cut at **fake**: highest prominence in the sentence and matches the goal *waking up*".

## 4. The impact map and the cut rules (the heart of it)

**What counts as an impact candidate** (each gets a 0–1 strength and a one-line reason):

| Kind | How it is measured | Basis |
|---|---|---|
| **Spoken stress** | **Exists:** `visuals/emphasis.py` (loudness, pitch, duration per letter, each against the speaker's own norm; weights 0.40 / 0.35 / 0.25) as module `audio.emphasis`. **Upgrade to test:** word prominence from pitch, energy and word duration combined and read off a continuous wavelet transform (weights about 1.0 / 0.5 / 1.0); kept only if it agrees better with the editors' cuts on the direction set. | Suni et al. 2017, Tamburini 2005 (no training needed) |
| **Meaning** | The director (an LLM) names the word or phrase that carries the sentence's meaning *for this goal*. Needed because stress alone cannot know the goal (stress may fall on *thought*). Text-only prominence prediction is itself workable (BERT-based, arXiv 1908.02262), so the LLM can be cross-checked against it. | the owner's `fake` / `powerful` example |
| **Sound events** | Peaks in a time-only auditory saliency curve (deviation from the background in pitch, intensity, timbre), plus the labelled events we already find: laughter, applause, a music hit, a bark, a silence that follows a loud moment. | Kaya & Elhilali 2012/2014; `server/vt/sounds.py` |
| **Emotion** | Speaker-relative arousal peaks (pitch level and range, loudness, rate, pause share). | `server/vt/prosody.py`; Rhapsody (arXiv 2505.19429) |
| **Structure** | Turns in the argument: a question then its answer, a "but", the payoff after an open loop. | `context.py` roles; Loewenstein 1994 (curiosity gap) |
| **Quiet and still** | Where a cut is *safe*: the speaker is relatively quiet and still. Used to move a cut slightly, never to invent one. | Berthouzoz, Li & Agrawala 2012 |

**The director's goal selects among them.** Impact = *acoustic strength* × *relevance to the goal*. That is how the same sentence gets cut at **fake** or at **powerful**.

**Rules the cut plan must obey** (each one testable; defaults are starting points to tune, not truths):
1. **The first change lands on an impact within 3 s** of the start (target 1–2 s). Evidence that the first watch-time peak falls before 5 s: ECCV 2024 (Snap/CUHK); the app's scorecard already targets hook ≤ 1 s.
2. **Cuts land on the impact word's onset, never after it.** The picture may arrive up to about 0.1 s early (a split edit, "J-cut": the picture leads, or the sound leads), never late. Audio–video offsets become noticeable at roughly 45 ms (audio early) to 125 ms (audio late) in the broadcast studies behind ITU-R BT.1359 (figures from secondary sources; check the recommendation before relying on them).
3. **Cut at the end of a thought, not in the middle**: Murch's *Rule of Six* orders what makes a cut good: emotion first (about half the weight), then story, rhythm, eye-trace, then the two screen-space rules. When they conflict, serve the higher one.
4. **Shot lengths vary on purpose.** Hollywood shot lengths drift toward a 1/f pattern (long and short runs correlated), which tracks how human attention fluctuates (Cutting, DeLong & Nothelfer 2010). So: no fixed slot length, no run of equal lengths, short bursts at peaks, longer holds where the idea needs room. The pacing curve is the director's, per style: fastest in the opening, relaxing, then rising to the payoff.
5. **Each cut gives the eye a fresh centre of interest.** Viewers' gaze converges on the screen centre for about 1.2 s after a cut and follows a moving person (Smith & Henderson 2010; Mital et al. 2011), so the subject of every new shot sits near the centre, and captions never cover it.
6. **The ending matters most after the peak** (peak-end rule, Fredrickson & Kahneman 1993; evidence is mixed, so treat as a default): save the strongest picture for the payoff and end clean, loopable for Shorts.
7. **Cuts are reasons, not noise.** Every cut stores its impact kind and strength; a cut with strength under the floor is removed. An orienting response follows every edit (Lang's LC4MP) and costs attention, so a cut with no purpose is a tax, not a gift.

## 5. What fills a slot: the menu, the budget, the styles

The director picks per slot, cheapest sufficient first. **Generated footage is the most expensive medium** (about 1–2 min of GPU per clip on this server) so it is used only where nothing cheaper carries the impact, or where the style demands it.

| Medium | Best for | Cost | Status |
|---|---|---|---|
| The speaker (A-roll), punch-ins, split screen | talking head, podcast, interviews | free | ✅ (split screen ✗) |
| Graphic: number, chart, list, comparison, icon, text | explainers, infographics, facts | free | ✅ 39 element types |
| Stock clip or photo (catalogue, user's bin, keyed stock) | the moment a real thing is named, where we have one | low | ✅ |
| **Still + slow zoom/pan** (with SVG illustration, text) | image-story style; any slot needing a picture | low | ◐ media + motion exist; the "still-series" style and a consistent character set are new |
| Stick figure, emoji, cartoon scene | stories, dialogue, humour | low | ✅ |
| **Generated clip**, 2–4 s, silent | B-roll inserts in a-roll videos; atmosphere; abstract ideas made concrete; the whole video only when a character style needs it | high | ◐ tool built (`server/vt/comfy/`); the choosing and the prompt-from-words are new |

**Styles set the mix** (the director decides within them, and the person can override):

| Style | Typical mix |
|---|---|
| Talking head / podcast | A-roll as the base; **generated or stock B-roll in between**; graphics for numbers; captions |
| Infographic / explainer | graphics as the base; stock footage (or a generated clip) only where a concept has no graphic and no stock |
| Cartoon / stick story | characters throughout; generated stills or clips for the opening and the ending, or throughout if the owner wants real characters |
| **Image story** (a recurring character in scenarios) | stills changing on each sentence's impact, slow zoom, SVG illustrations, text, voice: no animation |

**Fitting a clip to its slot.** Slots are whatever the impact says; the generator makes what the slot needs: the model's frame rule gives 2–3.5 s (Wan: 4k+1 frames at 16 fps; LTX: 8k+1 at 25 fps). If the clip is a little long: trim the tail. A little short: slow it up to 20 %. A slot over about 4 s: split it into two cuts at the next-strongest impact, or hold a still with a slow zoom. Never loop a clip on screen.

**Making the clip: direct from text, or a still first?** Not decided: this is an experiment (§7, phase 5). Still-first gives a picture to check and fix before spending two minutes on motion, and is the only way to keep a character recognisable between shots (reference-conditioned stills). Direct text-to-video is simpler and probably faster. Run both on the same ten prompts and keep the data. **Continuity:** clips are independent shots, like cutaway B-roll; the style bible (look, palette, lens, the character's description repeated word for word) is what keeps them related.

**Honest cost.** A 3 s clip is about 55–126 s on the V100 once loaded and about 500 s the first time. So: the whole video is assembled immediately from the cheaper media with generated slots showing a placeholder frame; clips arrive one by one and replace their placeholder; the person can export at any moment.

## 6. The director's prompt: how it is made perfect, and how we know

"Perfect" is a claim; make it a number.

**What the director sees, and only this:** the cleaned transcript with word ids and times (measured, never estimated from text length), the impact map with strengths and reasons, sentence roles and sound events, the style options, the media menu with costs and the budget, the pacing targets. It never sees the original request for "a video about X" in a form that lets it invent; every name, number and claim in a prompt for a picture must exist in the transcript (validator).

**What it returns:** strict JSON: `goal`, `audience`, `tone`, `style_bible`, `pacing_curve`, and for each cut `{time or word id, lands_on, kind, medium, prompt_if_generated, why}`. Pydantic-validated; word ids must exist; times inside the audio; cuts ordered and at least the minimum apart; budget respected; the first cut within 3 s; one repair retry with the errors, then the rule director. Same contract and validator for Claude, Codex, Gemini and local models; the provider is a setting.

**How we measure it** (build this *before* the prompt work, it is the point):
1. **A direction set.** 20 short recordings (English and Bangla; podcast, story, explainer, product) where a human editor marked the cuts, what each cut lands on, and the medium. Start with the owner's own samples (the parable, the wolf and the crane, the podcast) and their edits.
2. **Metrics per director:** share of the editor's cuts matched within ±250 ms; share where the *lands-on word* agrees; medium agreement; hook within 3 s; zero invented facts; schema-valid first try; cost per video. Each directed run is cached and diffable.
3. **Prompts are versioned files with tests**; a change must not lower the scores. Few-shot examples are real editor decisions with their reasons (including the `fake`/`powerful` pair).
4. **Cross-check the model with the signal.** If the director's chosen word has the lowest prominence in the sentence *and* the goal does not explain it, the cut is flagged for the second look rather than trusted.
5. **A viewer-side check:** the local vision model looks at the frame before and after each cut and answers "did the picture change meaningfully at the impact?"; and the scorecard gains *impact alignment* = share of impact points where something changed on screen within ±100 ms.

## 7. Phases (hand-off order; each has a gate)

| Phase | Work | Gate |
|---|---|---|
| **1. Direction set and metrics** | Build the 20-clip set and `scripts/eval_direction.py` with the metrics above; baseline = today's sentence-based scenes and the rule director | numbers exist; baseline recorded |
| **2. Impact map** | first, **measured word onsets for script speech** (forced alignment of each sentence; test: onsets within 60 ms of a hand-marked set of 50 words); then `server/vt/impact.py`: stress by wavelet prominence, saliency curve, events, arousal, structure; `impact.json`; tests on synthetic audio (a louder, longer, higher word is found; a laugh is found) and on the owner's samples | word onsets ≤ 60 ms median error; on the direction set, the editor's cut word is in the top 2 candidates for ≥ 80 % of sentences |
| **3. Direction and cut plan** | `server/vt/direction/` (schema, prompts, validator, providers) and `server/vt/cutplan.py` with the §4 rules; option `edit_mode: "impact"`, off by default; the editor shows every cut's reason | director + cut plan beat the baseline on cut match and hook; zero invented facts; a video with the option off is bit-identical to today |
| **4. Mediums and budget** | the director assigns a medium per slot under a budget; the still-series style (stills, slow zoom, SVG, text); consistent character stills | three styles produce watchable videos with no generation at all |
| **5. Generated clips, wired** | prompt from the speaker's words; **experiment: direct vs still-first** (ten prompts, time, vision-model relevance, human judgement); Z-Image Turbo still workflow asset; variable-length fit; placeholder-then-replace; vision check, one retry | generated clips judged relevant on three real videos; export never waits for them |
| **6. Judge** | impact alignment in the scorecard; revise loop uses it | alignment ≥ 90 % on the direction set |

## 8. Research behind this, with the honest caveats

| Source | What we take from it | Caveat |
|---|---|---|
| Lang, LC4MP (2000, 2009) | an edit triggers an orienting response; attention is limited, so each cut should earn its cost | read from secondary descriptions; the primary papers were not opened |
| Murch, *In the Blink of an Eye* (Rule of Six; emotion ≈ 51 %, story 23 %) | the order of what a cut must serve | the percentages are from editing blogs and a thesis, not an experiment |
| Cutting, DeLong & Nothelfer 2010, *Psychological Science* | shot lengths in 150 films (1935–2005) drift toward 1/f, like attention | no link to film ratings was found by one reader (secondary source) |
| Suni et al. 2017 (CWT prominence), Tamburini 2005, arXiv 1908.02262 | word stress from pitch, energy and duration without training; text-only stress prediction as a cross-check | accuracy figures (85 % at word level) are on one news corpus |
| Kayser et al. 2005; Kaya & Elhilali 2012, 2014 | a time-only saliency curve; peaks mark salient sounds | the model is a model, not proof the brain has a saliency map |
| Berthouzoz, Li & Agrawala 2012 | cuts are safest where the speaker is quiet and still; transcript-linked editing | the exact thresholds are in the full paper, not read |
| Truong et al. 2016 (QuickCut) | narration beats aligned to clips, dynamic programming for cut points under film-editing rules | an interactive tool; useful as the model for our slot-filling search |
| Lin et al. 2023 (VideoDirectorGPT) | an LLM plans scenes, entities and consistency groups *before* generation | text-to-video; we adapt only the plan structure |
| Smith & Henderson 2010; Mital et al. 2011 | attentional synchrony: gaze clusters (centre for about 1.2 s after onset; follows a moving person) | tested on static-camera scenes; edited-film extension is our inference |
| Loewenstein 1994 (information gap); Fredrickson & Kahneman 1993 (peak-end) | curiosity gap for the hook; peak and end for the payoff | evidence for peak-end is mixed (2024 study); retention claims in creator blogs are not evidence |
| ITU-R BT.1359 | audio–video offset tolerance (about +45 / −125 ms to detect) | figures from secondary sources and disputed by ATSC (stricter); verify before fixing a number |
| ECCV 2024 (Snap/CUHK); Rhapsody arXiv 2505.19429; VEBench arXiv 2605.03276 | first watch-time peak before 5 s; audio features add to every highlight model; LMMs are far from human editing cognition (so the signal must carry the weight, not the model alone) | VEBench has no cut-from-narration metric; ours is new |

## 9. Out of scope, on purpose

MiniMax H3; the generators' own sound; continuity of one character across generated *videos* without reference stills; real-time editing; replacing the person's choices (every cut and medium stays an editable item).

## 10. Questions that only the owner can answer

1. **The direction set** needs human edits: can the owner mark cuts on five of their own recordings (a few minutes each), so the numbers mean something?
2. **Budget defaults** per style: how many generated clips are acceptable for a one-minute talking-head video before it feels slow to make (the proposal: 3 to 5, placeholders first)?
3. **Image-story style:** which look and which recurring characters first (the plan assumes illustrated, consistent, generated stills with a text description repeated verbatim)?
