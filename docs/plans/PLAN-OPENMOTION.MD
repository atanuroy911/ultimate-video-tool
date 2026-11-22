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
