# PLAN-CODE-NATIVE-EDITOR: a video editor that works like VS Code, without becoming VS Code

Owner's request (2026-11-21): "if we can get vscode stuff .. or somehow integrate full codex and claude code extension with our software exactly .. basically like VSCODE being a video editor ... when we ask claude to direct videos normally ... you normally create HTML css and ffmpeg ... here also same thing ... but all can be editable in such a manner where those html parts can be easily manipulated with and without editing codes ... claude or codex will have access to the Comfy UI and Ollama for image generation, broll generation, and kokoro and omni voice (find explicit models that's SOTA and can be run on different tiers of hardware)."

Branch: `workbench`. Follows on from `PLAN-WORKBENCH.MD` (W12 is the Claude Code / Codex pane; this plan widens it). Test on the owner's laptop only (Windows, RTX 4050 6 GB, data on E:), never the GPU server.

## 1. The honest answer: what to take from VS Code, and what not

### 1.1 Embedding VS Code itself: no
| Way | What it costs | Verdict |
|---|---|---|
| Fork VS Code and make it a video editor | A 2M-line codebase to rebase every month; our timeline, viewer and inspector would be extensions fighting the workbench layout; the installer triples. | No. |
| Ship the official Claude Code and Codex extensions inside our app | The Visual Studio Marketplace terms allow its extensions only in Microsoft's own products. Claude Code is also on Open VSX (Anthropic publishes it there), so it could run in a VS Code build of ours; the Codex extension is on the Marketplace only, and people running it in code-server report freezes. A backdoored Claude Code build was reported on Open VSX (2.1.313, fixed in 2.1.314), so we would also be shipping a supply-chain risk we cannot check. | No. |
| Embed code-server / openvscode-server as a pane | Possible (both are open source, both use Open VSX), but a second 300 MB web server inside the app, a second settings world, and still no Codex extension. Our users are mostly not programmers. | Not as the main way. Optional later (step C9). |

### 1.2 What we do take: the three things that make VS Code good
1. **The work is files.** A video is a folder of plain, readable files (HTML, CSS, JSON, audio, pictures). An agent edits them, git can version them, the person can open them anywhere.
2. **Agents work in the same files, in a side panel, asking before they act.** Claude Code and Codex run through the Agent Client Protocol (ACP), the same way Zed and OpenFilm host them: the agent is the real Claude Code / Codex program, signed in with the person's own account, and our app shows its chat, its plan, its file edits as diffs, and a permission card before each action. This is "the full Claude Code and Codex", minus the VS Code window.
3. **Two editors on one document.** VS Code shows a settings file as a form and as JSON; both edit the same file. We do the same for a shot: a visual editor (drag, resize, colour, text, timing) and the code, both writing to the same shot.

And for the people who really want VS Code: **"Open in VS Code"** opens the project folder in their real VS Code, where the official Claude Code and Codex extensions work as Microsoft and the vendors intend, and our small VS Code extension (step C8) shows a live preview of the shot being edited.

### 1.3 Why this is better than what we have now
Today the director chooses from our fixed element types (cards, stick figures, story elements), and the person edits those in the inspector. Anything the types cannot express cannot be made. With code-native shots the agent can write any HTML/CSS/SVG/canvas motion, exactly as Claude does when asked to make a video in a chat, and the person still edits it without code.

The risk is the opposite one: free code is harder to keep consistent, safe and deterministic. Rules 2.3 to 2.5 handle that.

## 2. The shot format (tested, see 2.6)

### 2.1 A shot is a folder
```
projects/<p>/shots/<shot-id>/
  index.html        the shot, written by an agent or by a template; one root with data-composition-id, data-start, data-duration
  overrides.json    every edit made in the visual editor; the code above is never rewritten by the visual editor
  assets/           pictures, clips, sounds the shot uses (generated or uploaded)
  shot.json         id, title, duration, aspect, which agent made it, which prompt, the knobs it exposes (2.2)
```
The project's timeline places shots in time; the existing renderer (HyperFrames, `server/vt/render/hyperframes.py`) renders a shot or the whole timeline.

### 2.2 What the visual editor can change without code
- **Elements:** anything with `data-vt-id="<name>"`. Text, colour, size, weight, position (x, y), scale, rotation, opacity, hidden.
- **Knobs:** CSS custom properties declared on `:root` and listed in `shot.json` (`--accent`, `--bg`, `--title-size` ...), shown as colour pickers, sliders and font pickers.
- **Timing:** the GSAP timeline's labelled steps (`tl.addLabel('title-in', 0.25)`), shown as handles on the timeline; moving one writes `overrides.json.timing`.
- Edits are applied on load, before the timeline is built; transforms use the CSS `translate/scale/rotate` properties, so they **compose** with the shot's own animation instead of fighting it (tested: the orb still scales in while moved and shrunk).

### 2.3 Determinism (a rendered frame must be the same every time)
- Motion only through the paused timeline the renderer seeks (`window.__timelines[id]`), or a pure `frame(t)` function; no `setTimeout`, `requestAnimationFrame`, `Date.now()`, `Math.random()` without a seed. `vt check` already samples frames; add a check that renders the same time twice and compares.

### 2.4 Safety
- A shot has no network: fonts, scripts and pictures come from `assets/` or our `runtime/`. The renderer already runs locally; add a Content-Security-Policy meta (`default-src 'self' data: blob:`) injected at render and in the preview iframe.
- The preview runs in a sandboxed iframe (`sandbox="allow-scripts"`, no same-origin) so a shot cannot reach the studio.

### 2.5 Consistency
- Shots read the project's theme as CSS variables (`--vt-bg`, `--vt-ink`, `--vt-accent`, fonts) from `runtime/vt.css`. The agent is taught (director prompt, not code rules) to use them, so a theme change restyles every shot.
- Our existing element types become **templates**: a shot made from a template is just HTML the agent or the person can open and change further.

### 2.6 Spike (done, 2026-11-21)
`docs/dev/spikes/html-shot/`: a 3 s, 1920x1080 shot (title, subtitle, bar, orb; GSAP), rendered by our renderer in about 20 s on this laptop. The same shot with `overrides.json` (new text, three knob colours, title moved, orb moved and shrunk, subtitle bold) rendered correctly with the animation intact: `sheet.png` (top: as written, bottom: edited without touching the code).

## 3. Agents in the app (Claude Code and Codex via ACP)

This is `PLAN-WORKBENCH.MD` W12, made concrete.
- **Runner (client helper):** `client/desktop/acp-agents.js` starts `@agentclientprotocol/claude-agent-acp` or `codex-acp` (the person's own sign-in; we never hold their keys), talks ACP over stdio (`ClientSideConnection` + `ndJsonStream`), working directory = the project folder (a local copy on the client, synced to the server, see C2).
- **Permissions:** never `bypassPermissions` (OpenFilm forces it; we do not). Each tool call shows a card: Allow once, Allow for this session, Deny. File edits show a diff first.
- **Pane:** the assistant column gets tabs: Director (today's chat), Claude Code, Codex. Tabs only appear for agents that are installed and signed in; otherwise a one-click "Set up Claude Code / Codex" that installs the adapter and opens the sign-in.
- **Tools for agents:** our MCP server (`server/vt/mcp/server.py`) is given to the agent session, so it can render a shot, look at frames, and call the generators (section 4). Results already carry `anthropic/maxResultSizeChars` so Claude receives them whole.
- **Usage:** a Claude-directed video costs about 60 requests; the pane shows the agent's own usage messages and the app falls back to the local AI only when the person allows it.

## 4. Generators the agents can call (ComfyUI, Ollama, voices)

Exposed as MCP tools: `make_picture(prompt, aspect, style)`, `make_clip(prompt or picture, seconds)`, `speak(text, voice, language, reference?)`, `ask_local(prompt, picture?)`. Each picks the best model that fits the card(s) Video Tool may use, from a **measured** table, like `vt/engines/fit.py` does for pictures and the language model today. Each result goes into the shot's `assets/` with its prompt and model recorded.

### 4.1 Models by hardware tier (research 2026-11; numbers to be measured here before they go into the table)
VRAM figures below come from third-party guides that disagree with each other; only what we measure goes into `fit.py`.

| Tier | Language (Ollama) | Pictures (ComfyUI) | Clips / B-roll (ComfyUI) | Voice |
|---|---|---|---|---|
| No graphics card | gemma4:e2b on the processor (slow) or Claude/Codex | none (stock pictures, drawn shots) | none: motion comes from the HTML shots | Kokoro-82M (Apache 2.0, runs on a processor, no cloning, English/Hindi and a few more) |
| 6 GB (this laptop) | **gemma4:e2b** (measured, PLAN-LOCAL-AI-6GB) | FLUX.2 Klein 4B in 4-bit/3-bit GGUF (already in `fit.py`); Z-Image Turbo 8-bit reported at about 6.2 GB | FramePack (picture to clip, reported to run in 6 GB); Wan 2.2 TI2V-5B with offloading | Kokoro; Chatterbox (MIT, cloning from 5–10 s, reported 4–8 GB); Qwen3-TTS (Apache 2.0, 10 languages, about 4 GB reported) |
| 8–12 GB | gemma4:e2b / gemma3:4b | FLUX.2 Klein 4B 8-bit; Z-Image Turbo 8-bit | Wan 2.2 TI2V-5B (720p, reported from 8 GB) | the above; IndexTTS-2 (reported 8 GB minimum) |
| 16–24 GB | gemma3:12b | Z-Image Turbo full; Qwen-Image 2.1 (non-commercial licence) | HunyuanVideo 1.5 (reported 14 GB with offloading, custom licence); Wan 2.2 14B with offloading | Higgs Audio v2, Fish Audio S2 Pro (research licence) |
| 32 GB+ (the V100 server class) | larger Gemma/Qwen | everything above | Wan 2.2 14B; LTX-2 (picture and sound together; FP8 reported at 32 GB, community licence) | everything above |

**Bangla voice** is the hard part: no mainstream open model lists Bangla reliably. Candidates to test, in order: OmniVoice (already wired through ComfyUI; check its model card for licence and Bangla quality), Chatterbox Bangla (a 2026 LoRA of Chatterbox; anonymous review release, provisional), a CosyVoice 3 Bengali fine-tune, Meta MMS (Bangla, non-commercial). Breeze TTS 2 stays as today (research, non-commercial).

**Licences** are shown next to each model in the setup screen, and models marked non-commercial are off by default (the person turns them on knowingly).

## 5. Steps (for Sonnet; each step: build, test on this laptop, commit and push to `workbench`)

| # | Step | Done when |
|---|---|---|
| C1 ✅ | **Shot folder + overrides in the renderer.** Done 2026-11-21: `server/vt/shots.py` (overrides checked value by value and written as CSS + a text script; CSP; build/render/frames), 18 tests in `tests/test_shots.py` incl. a real-frame test. `server/vt/shots/` (new): read/write `shot.json` and `overrides.json`, inject the override applier (the script in the spike, moved to `server/renderer/runtime/vt-overrides.js`) and the CSP at render time; `render_shot(project, shot)` reuses `render_silent`. | `tests/test_shots.py`: a shot with overrides renders; text/knob/transform/hidden edits appear in the frame at a sampled time (pixel check); determinism check (same time twice, same frame). |
| C2 ✅ | **Shots on the timeline.** Done 2026-11-21: `Scene.shot`; the composer renders each shot once (cached by a fingerprint of code, edits and assets) and shows it full-frame behind its scene, with no added move or decoration; endpoints in `server/vt/server/shot_routes.py` (list, read, write code, write edits, the built page, one frame). A real 30 s video with two HTML shots among old scenes: `docs/dev/spikes/html-shot/c2-mixed-video.png`. Client-side sync of agent edits moves to C6. A timeline clip kind `shot` that points to a shot folder; the whole-video render composes shots with the existing scenes. Agent edits on the client are synced to the server through the existing project API. | One video mixing an old scene and two HTML shots renders; e2e check in the installed app. |
| C3 ✅ | **Visual editor for a shot.** Done 2026-11-21: `client/studio/src/review/ShotEditor.tsx` (+ pure logic `shotEdit.ts`, 6 unit tests) and the bridge `server/renderer/runtime/vt-shot-bridge.js`. The shot runs in a sandboxed frame with no origin, so its page is built self-contained (scripts, the fonts it names and its pictures inlined). "Edit shot" on a scene with a shot; click to select, drag, corner to scale, top dot to rotate (shift: 15° steps), arrows nudge; text, colour, size, weight, opacity, hide; knobs from shot.json; undo/redo (its own history); autosave. Browser test `client/studio/e2e/shot-editor.mjs`: 11 of 11 on this laptop (`docs/dev/spikes/html-shot/c3-shot-editor.png`). Timing handles (labels) are left for later. In the viewer: click an element with `data-vt-id` to select it; drag to move, handles to scale/rotate, inspector fields for text/colour/size/weight/opacity; knobs panel from `shot.json`; undo/redo through the existing history. Writes only `overrides.json`. | Browser test: select, move, recolour, undo; the rendered frame matches the preview. |
| C4 ✅ | **Code view of the same shot.** Done 2026-11-21 with CodeMirror 6 instead of Monaco (bundles offline with no worker setup, about a tenth of the size; loaded only when Code is opened: 195 kB gzipped). A Design / Code switch in the shot editor; Ctrl+S saves, the server checks the code first, the preview reloads, the visual edits stay; edits whose element the code no longer has are listed with a remove button. The browser test now has 17 checks, all passing. A Code tab in the inspector (Monaco, already an npm package; no VS Code fork) showing `index.html`, with "Reset this edit" per override. Saving code re-renders the preview within a second. | Edit code and an override together; both survive a reload. |
| C5 | **Teach the director to write shots.** Director prompt section (visible in the UI, per the AI-directs rule): the shot format, `data-vt-id` on everything a person may want to change, knobs for colours and sizes, labelled timeline steps, theme variables, determinism. Templates: our element types as starting shots. | Claude (Sonnet) directs a 20 s explainer made of HTML shots; every text in it is editable in the visual editor; then gemma4:e2b does the same. |
| C6 | **Claude Code and Codex panes (W12).** Runner, permission cards, diffs, tabs, set-up flow; the project folder as working directory; our MCP server attached. | Fake-agent tests; then a real Claude Code session changes a shot's title on request and the preview updates. |
| C7 | **Generators as MCP tools.** `make_picture`, `make_clip`, `speak`, `ask_local`, choosing models by tier from the measured table; install ComfyUI on E: through the app's own engine installer; measure Kokoro, Chatterbox, Qwen3-TTS, OmniVoice, FramePack, Wan 2.2 5B on this card and record them in `fit.py`. | Each tool works from a Claude Code session on this laptop; the table holds measured numbers. |
| C8 | **"Open in VS Code" + a small VS Code extension.** The menu item opens the project folder in the person's VS Code. The extension (published to Open VSX and the Marketplace) adds a live preview of the shot under the cursor, connected to the running app. | The extension previews the spike shot; edits in VS Code show in our app. |
| C9 | **Optional: code-server pane.** Only if C4 + C8 leave a real gap. | Decided after C8. |

## 6. Sources
- Claude Code in VS Code, and its Open VSX listing: https://code.claude.com/docs/en/vs-code
- Codex IDE extension: https://developers.openai.com/codex/ide
- Visual Studio Marketplace terms (Microsoft products only): https://cdn.vsassets.io/v/M190_20210811.1/_content/Microsoft-Visual-Studio-Marketplace-Terms-of-Use.pdf
- Open VSX: https://open-vsx.org
- TTS comparisons: https://localclaw.io/blog/local-tts-guide-2026, https://www.tryspeakeasy.io/blog/open-source-text-to-speech-2026, https://rarebuildsoftware.com/blog/best-open-source-voice-cloning-2026, https://findskill.ai/blog/best-open-source-tts-2026/
- Bangla voice: https://github.com/muhib-karim/bangla-voice-studio, https://huggingface.co/Banglabox/chatterbox-bangla-tts, https://github.com/kawshikbuet17/CosyVoice3-TTS-Bengali-Finetuning
- Picture and clip models by VRAM: https://vdf.ai/blog/best-local-image-generation-models/, https://vdf.ai/blog/best-local-video-generation-models/, https://www.tutorial3d.it/en/ai-artificial-intelligence/comfyui-image-models-guide/, https://builderai.tools/blog/best-open-source-video-generation-stack-2026
- OpenFilm (ACP, dock, shots): https://github.com/openfilm/openfilm (reference copy E:\openfilm-a1b8d75)
