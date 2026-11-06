# Client UX: one place for each thing

Status: plan + first execution, 2026-11-03. Method: the `ui-ux-pro-max` skill's guidance (navigation, live status, accessibility) applied to the existing look
(Apple-like tokens in `client/studio/src/styles.css`; no re-skin). Evidence: screenshots of the old pages in `client/studio/e2e/out/settings-audit/`.

## What was wrong (from the owner and from the screenshots)

| Finding | Where |
|---|---|
| Nine Settings sections; the same two engines configured on three pages (Computers & setup, Free AI computer, Make pictures) | Settings |
| Two controls for "who directs" that contradicted each other ("Claude on MSI-LAPTOP: Ready" above "Claude on this computer: Not ready") | Settings / Plan my videos |
| Six words for one idea: planner, director, helper, AI, "Who plans each scene", "AI that directs your videos" | everywhere |
| Two names for one server ("roy-CT500" in the banner, "Ultimate Video Tool Server" on the card) | banner / Engines |
| "Run this in a terminal" cards, against the one-click rule | Settings |
| Clicking a finished video that was exporting opened the export/progress page, not the timeline | Projects / Review |
| No view of how busy the server is, no way to see or choose which GPU does which job | missing |
| A render does use the RTX 3060, but nothing shows it (the owner could not see it) | missing |

## Information architecture

The sidebar answers four questions, in this order; each destination appears once.

| Group | Item | What it is for |
|---|---|---|
| (button) | **New video** | start |
| Make | **Your videos** | the library; opening one opens the **timeline editor** |
| Make | **Styles** | looks |
| Make | **Short clips** | cut shorts from a long video |
| Share | **Share** | post finished videos |
| **Server** | **Server** (live dot) | how busy the computer that does the work is, which GPU does which job, the engines it uses, setup |
| | **Settings** | preferences only: how new videos start, voices & speech, directors & assistants, libraries, help |

Rules:
- **Server and Settings are different things.** Server = the machine and its engines (changes rarely, watched often). Settings = the person's choices.
- The sidebar footer shows one status line: `Server name · GPU 22% · CPU 18% · RAM 9/30 GB` (opens Server). Nothing else competes with it.
- Every page has one `h1`; sections use `h2` in order (heading hierarchy). The current item is marked (`aria-current="page"`).
- Deep links: `/settings?s=directors`, `/server`. The "Director" pill opens `/settings?s=directors`.

## One name for each thing (glossary, used in every string)

| Say | Never |
|---|---|
| **Director**: whoever plans the scenes (Local AI, Claude on this PC, Codex on this PC, Claude on the server) | planner, helper, AI helper, "who plans each scene" |
| **Server**: the processing computer; always its own name (`/api/server` name) | "roy-CT500" in one place and "Ultimate Video Tool Server" in another |
| **Engines**: Language AI (Ollama), Pictures & clips (ComfyUI), Voices | "free AI computer", "make pictures computer" |
| **This PC**: the computer the app window runs on | "this computer" when the server is meant |

## Settings after the redesign (5 sections)

1. **Preferences**: how new videos start, theme, shape, pace, music, language.
2. **Voice & speech**: voices that read scripts; speech-recognition models.
3. **Directors & assistants**: the order and availability of directors; connecting Claude/Codex (one click); the server's own AI services (advanced, closed).
4. **Picture libraries**: free photo/video libraries.
5. **Help & checks**.

## Server page (new): `/server`

1. **Identity**: the server's name, address, version, online state, and "Update needed" when it is older than the app.
2. **System** (live): processor, memory, disk, every GPU (load, memory, temperature, power), and the programs on each GPU by name. Rules from the skill: it says when it was updated ("updated 2 s ago", "stale" after 10 s), has a **Pause** control, stops polling when the window is hidden, and announces changes through one atomic `role="status"` line, not per number. Under reduced motion the meters do not animate.
3. **GPU assignment**: which GPU each job uses (see below).
4. **Engines**: Language AI, Pictures & clips, Voices, Another computer: status, Change, Run setup, "Picture makers found". Their advanced settings (address, model, test) sit inside each card, closed.

## GPU assignment

Jobs and who controls them:

| Job | Runs in | Can the app choose its GPU? |
|---|---|---|
| Video rendering (browser capture + encoder) | Video Tool's server | **Yes** |
| Speech recognition | Video Tool's server | **Yes** |
| Voices made on the server (local engines) | Video Tool's server | **Yes** |
| Language AI (Ollama) | the server's own Ollama | **Shown, not changed** (it is a separate program; the card shows where it runs and how to move it) |
| Pictures & clips (ComfyUI) | the server's ComfyUI | **Shown, not changed** (same) |

Setting: `gpu` in the server's settings: `{"primary": "<uuid>|auto", "render": "<uuid>|primary", "speech": "<uuid>|primary", "voice": "<uuid>|primary"}`.
`auto` = the card with the most free memory and the lowest load, that Video Tool is allowed to use. Applied per job, with no restart: rendering passes the card to the
renderer's GPU selection, speech recognition opens its model on that card's index, local voices likewise. `GET /api/system/gpus`, `PUT /api/system/gpu`,
`vt gpu` / `vt gpu set render <name|index|uuid>`, MCP `gpu_assignment`. The Server page shows it as five rows with a select each.

## Accessibility and responsive checklist (from the skill)

- Contrast 4.5:1 text, visible focus ring on every control, no icon-only button without a label.
- Targets at least 44 x 44 px on touch widths; 8 px between them.
- Works at 400 px: the sidebar becomes the existing tab bar (5 items max: Make, Styles, Short clips, Server, Settings; New video is a button above; Share sits inside Your videos on a phone).
- Live numbers: contextual status text, pause, stale state, reduced motion.
- Light and dark both checked on the Server page and Settings.

## Acceptance

Screenshots at 1440 x 900 and 400 x 760, light and dark, of: Your videos, Server, each Settings section; a keyboard-only pass through the sidebar and the GPU rows; a render with the GPU assignment changed shows load on the chosen card in the System panel.
