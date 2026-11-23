# Plan: OpenMotion-style editing (HyperFrames Studio) in Video Tool

The owner (2026-11-23): "We need EXACTLY THIS kind of editing in our app", and "the UI panel is fantastic, so simple". Reference: https://github.com/nexu-io/openmotion
(Apache-2.0), cloned read-only at `E:\refs\openmotion` (commit a44c714).

## 1. What OpenMotion's editing actually is

- OpenMotion's editor **is the HyperFrames Studio**: the `@hyperframes/studio` 0.9.7 frontend (HeyGen, Apache-2.0), copied into `studio/` with a thin host layer
  (`studio/src/motion/MotionStudioHost.tsx`: brand, project switcher, template library, MCP dialog). The parser, player, SDK, CLI server and renderer are the
  pinned HyperFrames npm packages. They did not write the editor; they adopted it and themed it.
- **We already render with HyperFrames** (0.8.181, `server/renderer`). Version 0.9.81 (published 2026-11-22) ships the same Studio as `hyperframes preview`.
- Tried on this laptop (2026-11-23): `hyperframes preview` opened Claude's battery shot from our own project with no change: Compositions / Assets / Code /
  Catalog on the left, the preview in the middle, Design / Layers / Renders / Variables on the right, a timeline under it, and a header with only Capture,
  Inspector, Share and Export. The Layers panel listed the shot's parts (Body, Fill, Cap, Title). That is the simple panel the owner liked.
- What the Studio edits (from its source): select on the canvas, move, resize, rotate and crop (`DomEditOverlay`, `DomEditCropHandles`, `DomEditRotateHandle`),
  inline text editing with a toolbar, a Design inspector (text, font, size, colour, alignment, fill, opacity, layout), **GSAP animation editing** (add an
  animation, ease curves, **keyframe diamonds**, **motion paths**, "record a gesture"), layers, variables (knobs), source editing, history with checkpoints,
  an NLE timeline (clips, split, snapping, zoom, tracks), a render queue, and WebMCP tools plus "Describe a change to the agent".
- It edits the **HTML and GSAP source directly**: elements are addressed by `id`, `data-hf-id` or a stable selector, and changes are written back into the files.

## 2. What this means for us

Our shots (C1 to C5) are already HyperFrames compositions, so the Studio can edit them today. Our *scenes* are not: our runtime (`vt.js`) builds each scene's
DOM in the browser from `data.json`, so there is no source element for the Studio to address. To get "exactly this kind of editing" for the whole video,
every scene has to become HyperFrames source, the way OpenMotion projects are.

Decision: **adopt the HyperFrames Studio as our editor, the way OpenMotion did**, instead of growing our own canvas editor further. Keep what only we have and
the Studio lacks: the voice and transcript (cuts, words, captions from speech), the director, retention checks, long-talk B-roll, the fast render for
recordings, Claude Code over ACP. Our own editor stays for those until each lives in the Studio as a panel.

## 3. Steps (each: build, test on this laptop, commit and push to `workbench`)

| # | Step | Done when |
|---|---|---|
| O1 ✅ | **HyperFrames 0.8.181 → 0.9.81** for rendering (`server/renderer/package.json`). Render the matrix shot spike, a normal video and the fast render of a long talk; compare frames with the 0.8 renders. | Same frames (or differences explained); every render test passes. |
| O2 ✅ | **"Edit in Studio" for a shot.** The server starts `hyperframes preview` for the shot's folder on a local port (one at a time, stopped when the editor closes), and our Studio opens it in a pane. Edits write the shot's `index.html`; our pipeline renders the edited shot. | Move and retype an element of a Claude-written shot in the Studio; the exported video shows the change. |
| O3 | **Every scene can be a shot ("bake").** A server step that turns a scene the runtime draws into HyperFrames source: one composition per scene, elements as real HTML with `data-hf-id`, their entrances as GSAP tweens on the scene's timeline. Start with the five most used element types. | A baked scene renders the same frames as before and opens in the Studio with its elements selectable. |
| O4 | **The video is a HyperFrames project.** Root `index.html` places each scene composition on the timeline (`data-composition-src`), the speaker's A-roll and the narration as media clips, captions as their own composition, music as audio. Our pipeline writes this project; the Studio edits it; our renderer and the fast render read it. | Open a whole made video in the Studio: scenes on the timeline, any element editable, Export gives the same video. |
| O5 | **The Studio inside our app.** Bring `@hyperframes/studio` into `client/studio` the way OpenMotion did (Apache-2.0; NOTICE and license kept; our host slots for the project switcher, the Director and Claude Code panel). Our theme via its CSS entry, not by editing its components. | The editor page is the Studio's layout with our assistant pane docked; the old canvas editor is behind a "Classic" switch. |
| O6 | **Agents in the Studio.** Its "Describe a change to the agent" and WebMCP tools go to our Claude Code session (ACP, W12) and the Director; our MCP tools read and write the HyperFrames project. | Ask Claude Code to change an element from the Studio; the change appears live and is undoable in the Studio's history. |
| O7 | **What only we have, as Studio panels:** transcript and word edits, voice cuts and restores, the retention scorecard, long-talk outline and B-roll, notices. | Each is reachable without leaving the Studio. |
| O8 | **Retire our own canvas and timeline editor** once O7 covers it (replaces W11.2). | `git grep` shows no imports of the old editor components; all browser suites pass on the Studio. |

## 4. Risks and rules

- Licence: Apache-2.0 for the Studio and OpenMotion; keep their LICENSE and NOTICE files and say what we changed. Our code stays under our licence.
- Do not copy OpenMotion's product layer (templates marketplace, ChatGPT plugin, cloud services); we need the editor, not their product.
- The Studio's Node server (`hyperframes preview`) runs on the processing server, bound to 127.0.0.1, one per open shot, stopped when idle. The desktop app
  reaches it through our server's existing proxy and key rules, never directly from another computer.
- Tests: our Playwright suites drive the Studio through roles and labels; scripted clicks on its canvas need real pointer events (a simple `mouse.click` did
  not select an element on 2026-11-23, selecting from the Layers panel did).

## 5. Progress

- **O1 done (2026-11-23):** renderer on HyperFrames 0.9.81; the shot and fast-render tests pass unchanged.
- **O2 done (2026-11-23):** the shot editor has a **Studio** tab. The server (`vt/shot_studio.py`, routes in `server/shot_routes.py`) makes a working copy of the shot with the video's theme and earlier edits shown between markers, starts `hyperframes preview` on a free 127.0.0.1 port, and copies the edits back (without the markers) on **Save to video**, **Done**, closing the editor or stopping the server. A change made elsewhere while the Studio is open is never overwritten (the Studio's version is set aside as `studio-conflict.html`). The Studio refuses to sit inside another page's frame, so it opens as its own window (an app window in the desktop app). Tested: `tests/test_shot_studio.py` (4, one starts the real Studio) and `client/studio/e2e/shot-studio.mjs` (10: open, layers listed, retype in the Studio's Design panel, Save to video, theme never reaches the code, Done stops it). Also tried by hand: a drag on the canvas of an animated title became a keyframe; our renderer drew both edits.
- **Next: O3** (bake runtime scenes into HyperFrames source so every scene opens in the Studio).
- **O3 first part (2026-11-23):** `vt/bake.py` + `renderer/runtime/vt-bake.js`. The runtime builds the page as for a render while every GSAP call is recorded;
  the result is written as plain HyperFrames source: the built DOM (animated parts get readable ids such as `s4-defn-term`, `s6-bar-val`, plus
  `data-hf-id`) and the timeline as GSAP code addressing them. No vt.js on the baked page. Only the properties GSAP animates go back to their built value
  (the layout guard's fitted sizes stay); shorthand styles the browser cannot write back get their drawn value. Results: the c2-mix sample (value card,
  sticker, shot backdrop video, definition, steps, bar chart, captions) bakes with nothing lost and draws **identical frames** at 7 moments; the baked
  video opens in the HyperFrames Studio with every part as a named layer. Test: `tests/test_bake.py` (same frames at 6 moments; nothing lost; ids unique).
- **O3 (a) done (2026-11-23):** each scene gets its time window from the timeline itself (its first tween to the moment it is hidden, plus one frame); frames stay identical at 15 moments including transition edges, and the Studio's timeline shows every scene as a clip where it plays (docs/dev/spikes/html-shot/o3-baked-video-in-studio.png).
- **O3 left:** (b) captions are baked as per-word parts of the root (they should become their
  own composition in O4); (c) count-up numbers and other callbacks are reported in `lost` (none in the samples so far); (d) bake a stick-figure, cartoon
  and media-heavy video and compare.
- **O4 done (2026-11-23):** the editor's header has a **Studio** button. The server composes the current video, bakes it into `<project>/studio-<shape>/`
  (`vt/video_studio.py`; media hard-linked, not copied) and starts the Studio on it (shared process code in `vt/shot_studio.py`, one Studio at a time).
  The Studio saves into that folder itself. The export draws from it while it holds edits and was baked from the same composition (a fingerprint of
  `index.html` + `data.json`); if the video changed since, the export uses the new video and a notice says the Studio edits are not in it; opening the
  Studio again keeps the old edits aside in `studio-<shape>.old`. With Studio edits the fast long-talk render is skipped (it redraws from the runtime data).
  Tested: `tests/test_video_studio.py`, and `client/studio/e2e/video-studio.mjs` 9/9 (button opens the Studio window, scenes are clips, "S4 Defn Term"
  retyped in the Studio's Design panel, export says it drew the Studio's edits; the final MP4 frame shows the new words).
- **Next: O3 (b) captions as their own composition** (they fill the top of the Studio's Layers panel today), then O5 (the Studio inside our app).
- **O3 (b) done (2026-11-23):** the captions are baked as their own composition (`captions.html`, mounted by a full-frame host inside the root so the
  caption styles and theme still apply; their word tweens on their own timeline). The Studio lists "captions" beside the main composition and its Layers
  panel no longer starts with 35 caption groups. One Studio copy now serves exports with and without captions (the fingerprint ignores
  `captions_enabled`; without captions the host is left out). A scene holding a timed video gets no window of its own (HyperFrames: a video takes no
  timing from its wrapper). The baked sample has no HyperFrames lint errors; snapshots identical at 10 moments, and a real render of the baked page
  matches the original's within encoding noise (same render time, 54 s vs 55 s).
- **O3 left:** ~~each scene as its own sub-composition~~ (done 2026-11-23 as S4 of PLAN-SCENE-TOOLS), callbacks (count-ups), and
  baking stick-figure, cartoon and long-talk videos.
- **O3 (d) long talk and fidelity (2026-11-23):** the owner's 14-minute talk (Claude-directed, 16:9, 2,171 animated parts) bakes in 7 s to a 466 kB page
  with **nothing lost**, matching the original at 16 of 17 sampled moments. What it took:
  - the baked timeline is now written from GSAP's own timeline after the build (tweens the runtime killed or moved are left out or moved), with each
    tween's options from the call that made it;
  - GSAP gets the runtime's own option objects (the runtime reads them back); an ease GSAP turned into a function is written by its name again;
  - count-ups (callbacks on a number) are sampled 30 times a second into plain text steps;
  - free visuals end their window where they hide themselves (`visibility: hidden`), since HyperFrames shows a timed element for its whole window;
  - styles written while the runtime plays its timeline to measure layout are not taken as built styles; a direct `gsap.set` is part of the built page;
  - **runtime fix (all renders):** every font loads before the page builds (`vt.js` `fontsThenBoot`), so text is fitted once with the real fonts;
    before, the fit depended on how fast fonts arrived; the page probe now starts Chrome with the renderer's text settings (`--font-render-hinting=none` ...).
  Left: the mosaic transition scene at 405 s (the original keeps its card hidden for ~4 s after the mosaic; the baked page shows it as designed) and a
  small difference at 640.95 s; stick figures (their limbs are drawn by callbacks: 17 steps lost; the Studio refuses such videos until they bake).
- **O5 done (2026-11-23), by embedding instead of copying the Studio's source:** in the desktop app the editor's **Studio** button shows the HyperFrames
  Studio inside the canvas pane, with the Director and Claude Code docked on the right; the editor's own library, inspector and timeline step aside
  (the Studio has its own) and "Back to Video Tool's editor" returns (docs/dev/spikes/html-shot/o5-studio-in-the-app.png). The desktop app
  (`client/desktop/main.js`) lifts the Studio's no-framing rule only for a 127.0.0.1 frame inside its own page, hides the Studio's Share (HeyGen's
  cloud), Install-the-desktop-app and Export buttons there, and refuses any request the Studio page makes off this computer (none seen). In a plain
  browser the Studio still opens in its own window. Copying `@hyperframes/studio`'s source the way OpenMotion did stays possible later (O5b) if we need
  our panels inside the Studio's own layout; today the Studio runs unchanged, so its updates come with `npm install`.
  Tested: `client/studio/e2e/desktop-studio.mjs` 7/7 in the real desktop app.
- **Next: O6** (the Studio's "Describe a change to the agent" goes to our Claude Code / Director; our MCP tools read and write the baked video).
- **O6 done for Claude Code (2026-11-23):** new MCP tools `studio_parts`, `studio_part`, `studio_edit` (one exact replacement, checked to keep the video
  timed) and `studio_selection` (what the person selected in the open Studio, read from HyperFrames' own `preview --selection --json`), in
  `vt/video_studio.py`. Claude Code's instructions say "this / the selected part" means the Studio selection. Real test with Claude Sonnet in the desktop
  app (`e2e/desktop-studio-agent.mjs` 4/4): the person selects "S4 Defn Term" in the embedded Studio and asks Claude Code to change "the selected part";
  it reads the selection, the part and edits it in 11 s; the Studio reloads by itself with the new words and the part still selected
  (docs/dev/spikes/html-shot/o6-claude-in-the-studio.png).
- **O6 left:** the Studio's own "Ask agent about this element" / "Describe a change to the agent" box still talks to HeyGen's agent flow, not ours
  (route it to the docked Claude Code); the Director chat does not have the studio tools yet; whether an agent's file edit is undoable in the Studio's
  history is not checked yet.
- **O5/O6 follow-up (2026-11-23, owner: "the entire viewport looks shrunk"):** in Studio mode our second toolbar hides and the assistant starts closed
  in windows narrower than 1500 px, so the Studio fills the window below the title bar (1344 x 770 in the app's default 1360 x 880 window); the Studio
  menu has "Show / Hide the assistant". The Studio's own "Ask agent about this element" / "Describe a change to the agent" (and Ctrl+K) now open the
  docked Claude Code with "The part I selected in the Studio: " ready to finish. e2e desktop-studio 10/10.
- **Studio edits survive changes to the video (2026-11-23):** when the plan changes after Studio edits (a Director note, a word edit, an element edited
  in Video Tool's editor), the next Studio open or export bakes the new video and carries each Studio change into it, found by the code around it
  (`video_studio.carry`, token diff of the old bake against the edited copy). Changes whose part is gone are counted and kept in `studio-<shape>.old`,
  and the export says so. Agent edits are recorded in HyperFrames' own history under "Claude Code" with a plain label (the Studio shows it; `studio_undo`
  takes it back). HyperFrames' update check and self-install are switched off (`HYPERFRAMES_NO_UPDATE_CHECK`, `HYPERFRAMES_NO_AUTO_INSTALL`).
  Checked end to end on c2-mix: a Studio edit on scene 4, then scene 5 changed in the editor; the export shows both.
- The Director stays plan-level (it rewrites the plan; the Studio edits are then carried). Claude Code is the agent for Studio-level changes.
- **O7 first part (2026-11-23):** in Studio mode the docked pane has a **Words** tab (the transcript: edit a word, cut or bring back a part). Any change
  to the video while the Studio is open (a word edit, a cut, a Director note) is baked again on the server with the Studio edits carried over and moved
  into the Studio folder file by file, so the open Studio shows it by itself (`POST /studio/refresh`; `video_studio._swap_in`). e2e desktop-studio 12/12.
- **Words on our timeline, readable at any zoom (owner: "the words section is too much overlapping"):** zoomed out, caption lines too narrow to read
  join into one block (a mark along the bottom where each word starts) and a block grows only until it can be read; zoomed in, each word gets its own
  slot once every word has 22 px. Double-clicking a caption word opens it for editing, like the narration. `occ/bridge/captionLod.ts`,
  tests/caption-lod.test.mjs, e2e/timeline-words.mjs (no overlap; double-click opens the word). Screens: docs/dev/spikes/html-shot/timeline-words-*.png.
- **O7 done (2026-11-23):** beside HyperFrames the docked pane has **Words**, **Outline** and **Checks** tabs. Outline: the talk's sections and
  examples, each marked with B-roll or "on the speaker" (with what the outline says could be shown); Checks: the retention check of the newest
  export (score, verdict, the moments where viewers may leave; "Check again") and the skipped extras (notices, "Got it"). Every time is a button
  that moves HyperFrames there (the scene bar follows). Server: `GET /api/projects/{pid}/insights` (`server/insight_routes.py`). Voice cuts and
  restores are in the Words tab. Tests: test_scene_gen (outline view), e2e desktop-studio 19/19. Screen: docs/dev/spikes/html-shot/o7-outline-checks.png.
- **O8 not yet:** our own editor is still needed where HyperFrames cannot go: videos it cannot hold (stick figures, whose limbs are drawn by code
  every frame), a web browser on another computer than the server (the Studio is bound to the server's own computer), and scene-level work the
  Studio has no place for (the Director's plan, shots). Retiring it waits for those three.
- **HyperFrames from another computer (2026-11-23, one of O8's three blockers):** when the server listens beyond this computer it also opens the
  **Studio gateway** (`vt/server/studio_gateway.py`, the server's port + 1). Every request there goes to the open Studio on 127.0.0.1, event streams
  and saves included. Who gets through: this computer; a browser that came with a one-time ticket (two minutes) that our server hands only to a
  caller it already let in, swapped for a cookie of this run (the key never goes into an address); or the desktop app, which sends the key as a
  header for gateway requests (inside the app the Studio is on another site than the app's page, where a cookie would not be sent). Web pages from
  elsewhere are refused (same Host/Origin rule as the server); only Video Tool may frame it. The Studio routes give a caller on another computer the
  gateway's address; with no gateway they say so. Tests: tests/test_studio_gateway.py 4, e2e/studio-gateway.mjs 6/6 (the real Studio through
  the gateway, its event stream too), desktop-studio 19/19. Screen: docs/dev/spikes/html-shot/studio-gateway.png.
  Left of O8: stick-figure videos in HyperFrames, and the plan-level work (Director, shots) that has no place in the Studio.
- **Stick figures in HyperFrames (2026-11-23, the second O8 blocker):** a stick scene's figures are drawn by code every frame (a pure function of
  time), which no list of steps can hold. The bake now notes each call of the stick engine (the scene, its data as given, the props state carried
  from earlier scenes, the steps it added) and makes the scene a composition that carries the engine and calls it on the scene's own timeline
  (times shifted to the scene's start; the voice loudness for lip-sync cut to the scene's stretch). While the engine builds or draws, hidden
  ancestors are shown for that moment, since HyperFrames hides compositions outside their window and the engine measures bubbles and props. The
  engine's own text redraws are not taken for count-ups. Result: the e2e-stick sample bakes with nothing lost in 9:16, 16:9 and 1:1, all 36
  sampled moments identical; the Studio opens stick videos and draws the figures. Tests: test_bake (a stick video's frames), e2e/studio-stick.mjs
  3/3. Screen: docs/dev/spikes/html-shot/studio-stick.png.
  Left of O8: plan-level work (the Director, shots) has no place in the Studio; then the old editor can go.
- **O8, the video's panels beside HyperFrames (2026-11-24):** the docked pane has three tabs: Director, Claude Code and **Video**. Video has the old
  editor's panels as views: Scenes (the plan with its scene menu), Direction (of the scene HyperFrames is on), Words (with the caption look), Script,
  Sound, Media (the bin, pictures for the scene, picture tools), Outline and Checks. e2e desktop-studio 22/22. Screen: o8-video-views.png.
  What the old editor still has that this does not: the Elements panel (adding a text, shape or diagram to a scene through our plan) and our own
  inspector for a plan element; in HyperFrames parts are added and changed directly. Next: decide those two, then make HyperFrames the editor.
- **O8, HyperFrames is where a video opens (2026-11-24):** in the desktop app a video with a plan opens in HyperFrames by itself (once per video
  opened). The HyperFrames menu has "Open videos in Video Tool's editor instead" (remembered on this computer); "Back to the editor" still
  shows our own canvas. The Video tab has every panel of the old editor (Elements added). Not done: deleting the old canvas and timeline code;
  the suites that test Video Tool's own editor (Claude Code in it, shots, media) turn the auto-open off for their run. Tests: desktop-studio 23/23,
  desktop-studio-agent 4/4 and desktop-agent 7/7 with the real Claude Code.
