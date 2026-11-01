# Work log

Newest first. Every agent (Claude Code, Codex) adds an entry when it stops: what it did, what it verified, what is left. Read
`CODEX-HANDOFF.md` first.

## 2026-11-01, later (Claude Code) — styles, remote Claude, GPU builds, timeline, lab round 2 + matrix

**Done and verified (committed on `client-server`):**
- **66 film styles from lemo-opuscar** (MIT): `scripts/import_lemo_styles.py` -> `design/styles/<slug>.json` (style bibles) +
  `design/themes/style-<slug>/theme.json` (palette from the bible or its poster, its typeface, WCAG contrast, `picture: line` for drawn looks).
  26 typefaces added (`renderer/scripts/build-fonts.mjs`). `vt/styles.py`, modules `style.list` / `style.get`, `vt styles`, `/api/styles`.
  Planning and script tasks now carry `craft_rules`, the chosen `style` bible and the current `craft_report`.
  Gallery: `scripts/style_gallery.py` -> `C:\Users\Roy\Videos\Video Tool Lab\styles-gallery\index.html` (3 frames per style).
- **Remote Claude**: MCP `prepare_upload` gives a curl / PowerShell line with a one-time ticket (`PUT /api/uploads/<id>/file?ticket=`);
  `create_project` / `add_media` take `upload:<id>`. Test in `tests/test_upload_resume.py`.
- **Every NVIDIA GPU**: `vt/gpu_detect.py` (cu128 RTX 50 / cu124 default / cu118 old drivers / cpu), torch builds are uv extras
  (`--extra cu124` etc., one `uv.lock`); setup.ps1 / setup.sh / desktop bootstrap pick it; `vt doctor` shows "GPU build". Local: cu124.
  **Sync command is now** `.tools\uv.exe sync --extra dev --extra cu124`.
- **Timeline**: `studio/e2e/perf_timeline.mjs` measures frame times + Chrome layout/script costs. Fixed: timeline rebuilt on every clock tick
  during playback (Review.tsx memo) and zoom glide 15 -> 5 renders (Timeline.tsx). Play median 33 -> 16.8 ms, zoom jank 36 -> 16 %
  (machine under load). Conclusion: the slowness was React re-rendering, not Electron/JS; Rust/Tauri would not have fixed it.
- Context AI: tolerant beat-id repair (gemma4 answers no longer discarded). Captions: phrase splitter. Craft check + hook fix.

**Running / next:** round 2 (`round-02\`, same 10 cases as round 1) then the 69-video covering matrix (`matrix\`, `video_lab.py --matrix`)
start automatically. Then: compare rounds (`video_lab.py --compare <r1> <r2>`), judge sheets, fix, re-run. Not yet done: Review page
craft checklist UI; style picker grouping in the New flow (66 styles now appear in the theme list); deploy to the GPU server again.

## 2026-11-01 (Claude Code) — retention lab, craft rules, reference skills

**Done and verified (all committed on `client-server`):**
- Video lab `scripts/video_lab.py`: 10 cases (explainer, Bangla script, two real recordings, cartoon story, product, infographic, stick,
  emoji, 16:9 debate). Round 1 in `C:\Users\Roy\Videos\Video Tool Lab\round-01\` (scores: infographic 48, mixed-wide 54, product 61,
  Bangla 63, stick 80, others 90-100; by eye the high scores were too kind).
- Retention scorecard: new *picture hold* (changes over 8 % of the screen, captions excluded) and *fill*; weights rebalanced.
- Heartbeat: where no safe picture fits, the spoken word in big type (never a wrong-sense picture); key-term filter fixed ("the" was a key term).
- Topic detection from the opening sentence (`terms.topic_terms`); a verb that only starts sentences is not a name ("Skip").
- Spoken compound numbers ("eighty four percent" = 84 %, was shown as 4 %): `vt/planner/rules.py`, `tests/test_spoken_numbers.py`.
- Captions: phrase splitter (2-3 words, max 4; never end on a function word; never split a number; no lone words; appear 0.06 s after the word).
- Craft rules module `vt/craft.py` (24 rules with sources, 10 measured), modules `craft.rules` / `craft.check`, pipeline writes `craft.json`
  and opens the hook on the topic (`fix_hook`). On round-1 plans the check scores infographic 0, product 42, explainer 55 and finds every
  invented figure.
- A note about the video ("The video describes ...") no longer becomes the opening title (`archetypes.b_title_card`, context schema).
- One-click assistants (Claude Code verified with the real CLI, locally and against the GPU server).

**In progress / next:** lemo-opuscar styles; craft module in MCP tools / CLI / API / Review page; remote media upload for remote Claude;
CUDA matrix; lab round 2 and the full combination run; timeline profiling.

## 2026-10-31 (Claude Code) — client/server CS1-CS6

See `docs/plans/PLAN-CLIENT-SERVER.MD` (Progress sections) and the git log from `a64f68a` to `e7ec5b0`.
