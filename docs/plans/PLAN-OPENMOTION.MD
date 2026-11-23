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
- **O3 left:** each scene as its own sub-composition (HyperFrames suggests it: `nested_structure_needs_subcomposition`), callbacks (count-ups), and
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
