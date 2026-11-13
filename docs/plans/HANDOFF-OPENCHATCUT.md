# Hand-off: OpenChatCut's parts in our timeline

Written 2026-11-09 at the end of a session, so the work can be picked up in a new one. Read this first, then
[PLAN-OPENCHATCUT.MD](PLAN-OPENCHATCUT.MD) (the plan, phases and a dated Status section) and the top entries of `WORKLOG.md`.

## The goal, in the owner's words

"Go through the Timeline UI, I think we can do better… check out OpenChatCut (github.com/0xsline/OpenChatCut)… we have a chat window and we
chat with the director as well as edit ourselves… adopt this full open-source work in our timeline."

What that means, as the owner confirmed after two wrong readings: **"Our timeline, their parts."**

- Video Tool keeps its own editor, its own data (scenes, elements, layers, words, pictures, sound) and its own server.
- OpenChatCut's code is taken **piece by piece** and fitted into our editor so it works on our scenes and pictures.
- **Not** a separate OpenChatCut app, **not** their editor replacing ours, **not** Video Tool inside OpenChatCut.

Licence: OpenChatCut is AGPL-3.0-or-later. The owner said: "I am part of the same team. Copy their code." Every ported file keeps a header
naming its source path and commit; `client/studio/src/occ/NOTICE.md` records this.

## Where things are right now

- **Git:** branch `small-cards-and-easy-setup`. The last commit is `eed58b0` (setup audit). **Everything about OpenChatCut is NOT committed
  yet.** The owner was asked whether to commit and has not answered. Do not push to `main`. No `Co-Authored-By` lines.
- **Uncommitted files** (all part of this work):
  - new: `client/studio/src/occ/` (the ported code, the bridge, styles, notice), `client/studio/tests/occ-bridge.test.mjs`,
    `client/studio/e2e/occ_timeline.mjs`, `e2e/occ_timeline_save.mjs`, `e2e/occ_director_chat.mjs`, `docs/plans/PLAN-OPENCHATCUT.MD`,
    this file, `scripts/port_openchatcut.py`, `scripts/openchatcut-timeline-files.txt`
  - changed: `client/studio/src/pages/Review.tsx` (switch, Director tab, saving), `src/styles.css`, `src/busycore.ts` (`?quiet=1`),
    `tsconfig.json` (ES2022 target, ES2024 lib), `package.json` (unit test list), `WORKLOG.md`
- **Installed apps on this PC** (`E:\UVT-Client`, `E:\UVT-Server`) do **not** have this work yet: they were last rebuilt before it.
- **Reference copy of OpenChatCut:** `E:\OpenChatCut-9242a95` (commit `9242a95`, 2026-11-06), the full source. Port from here. A second,
  disposable clone with a half-done `npm install` is in this session's temp folder; ignore it.

## What is done

### Phase 1 — their timeline inside our editor page (done)

- **Ported code:** 181 OpenChatCut files (180 as they are, plus their Markdown component rewritten) and 18 stand-ins, about 25,500 lines in
  all, in `client/studio/src/occ/src/` and `src/occ/shared/`, keeping their folder
  layout so their relative imports work unchanged:
  - the timeline UI (`components/timeline/*`): tracks, track heads (hide/mute/lock), ruler, toolbar, zoom, playhead, context menus, pointer
    gestures (move, trim, slip, snapping), marquee and multi-select;
  - the editing engine (`editor/*`): types, store with undo history (`useEditor`), reducers (clip, track, timeline, project), keyframes,
    ripple, slip, rate stretch, multi-select, draft engine (`makeDraft`, for proposals later);
  - captions track (`captions/*`), transcript editing (`transcript/*`), transcript search, keyboard shortcuts (`shortcuts/*`), the English
    dictionary (their UI text is written in Chinese and translated through it);
  - chat parts (`components/chat/`: ChatMessage, ChatRunStatus, ToolGroupRow, WidgetCard, message grouping, thinking phrases).
- **Stand-ins** (marked `// Video Tool:`) for what we do not take: other languages, GL effects, custom transitions, uploads, media probing,
  scene detection, motion tracking, caption translation and style menu, plugin templates, version store, agent context/session types,
  Google font catalogue, voice isolation, Markdown (a small safe renderer instead of react-markdown). A typed `@remotion/player` PlayerRef is
  declared in `src/occ/remotion-player.d.ts`. React stays 18: 9 small ref-typing fixes, each marked.
- **`initial.ts`** carries no built-in templates (their 1.9 MB of motion-graphic templates are left out until phase 3).
- **The bridge** (`client/studio/src/occ/bridge/`, our own code):
  - `fromProject.ts`: our project → their timeline state. Track layout, top to bottom:
    - `C1` captions, made from the narration's words, **locked** (captions are edited in our Captions panel for now)
    - `L_<id>` our free layer tracks (text, pictures, sounds)
    - `V3…` scene elements, packed into rows so overlapping ones do not share a row
    - `V1` scenes, each with its backdrop picture or clip
    - `A1` the narration after cuts, with its words in edited time (words overlapping a cut pause are clamped to the kept audio;
      "five" + "-minute" are joined into one word)
    - Item ids say what each item is in our project: `scene:<id>`, `el:<scene>:<index>`, `layer:<clip>`, `voice`.
  - `playerAdapter.ts`: our Preview player and `timeStore` wrapped in the PlayerRef shape, so their playhead follows our preview.
  - `OccTimeline.tsx`: their store (`useEditor`) + timeline + keyboard shortcuts on our page; lazy-loaded (about 450 kB, only when chosen).
  - `occ.css`: their `--cc-*` colours mapped to our light/dark tokens and blue accent; their timeline style rules (extracted from their
    2,115-line stylesheet, only the classes the ported files use).
- **On the editor page** (`pages/Review.tsx`): a **Classic / New timeline** switch above the timeline, remembered per browser
  (`localStorage` `vt-timeline`). **Classic is the default.** While the new timeline is on, our page's own keyboard handler steps aside
  (their shortcut dispatcher owns the keys).

### Phase 2 — edits are saved (done)

- `toProject.ts` compares the timeline before and after each finished edit and turns the difference into the calls our classic timeline
  already makes (no new server endpoint):
  - layers document via `layers.saveNow(doc)`: move, trim, split, duplicate, delete, fades, volume, place, track hide/mute/lock;
  - elements via `r.patchElement`: `{start, end}`, `{split: t}`, `{delete: true}` (splits and deletes from the last index back);
  - scenes: `r.moveEdge` (snaps to words; an edge belongs to the scene on its left; growing a scene = trimming its neighbour, because their
    engine refuses overlapping clips), `r.splitAt`, `r.removeScene`;
  - narration: `r.audioEdit("cut", {start, end})`. **Important:** OpenChatCut edits a narration that has words as *word streams* (a split
    gives each piece its own words; deleting words marks them deleted). So a cut is worked out as the run of our words no longer played by
    any piece, from its first word to the next word still played. Without words, a piece plays `[srcIn, srcIn + duration)`.
- After a save the page reloads the project and the timeline is rebuilt from it, so what is shown is what was saved.
- Ctrl+Z: an unsaved local change is undone locally; otherwise it goes to our project's undo (`r.undo`).
- The save status ("Saving…", "Saved.", "Not saved…") sits beside the Classic / New switch and never moves the timeline.

### Phase 4 — the director chat, undo and change markers (done so far)

- A **Director** tab, first in the editor's left panel (`src/occ/bridge/DirectorChat.tsx`), beside the preview and the timeline.
- Drawn with OpenChatCut's chat components; the conversation is **our** director's (`GET /api/projects/{id}/director`,
  `POST /api/projects/{id}/director/chat`), run by the AI chosen in Settings (on this PC: Claude, "Claude on the server").
- While it works: its current step shows live with a timer; earlier steps stay as lines; the input waits. The full-screen job window is kept
  away (the chat's request carries `?quiet=1`, matched in `busycore.ts`), so the person can keep editing the timeline.
- When done: its reply says what changed ("Changed 1 of 3 scenes.") and the timeline is rebuilt from the changed video.
- A completed Director turn is one editor-history step. Ctrl+Z or the reply's **Undo the Director's change** button restores the complete
  state from before that turn (scene plan, video script, compiled script plan and Director report); the same button becomes Redo and swaps
  the complete state back. A new server route performs that state swap atomically.
- Changed scene numbers in the reply are buttons: they select and scroll to that scene. Its scene clip and element clips briefly pulse on
  the timeline, so the result is visible rather than only described in prose.
- Director work is optimistic: the job remembers the plan it read and compares again immediately before applying. If the timeline changed
  meanwhile, it leaves that newer edit alone and returns a clear conflict instead of overwriting it.

### Tests (all passing at the end of the session)

| Test | What it covers | Result |
|---|---|---|
| `client/studio/tests/occ-bridge.test.mjs` (in `npm run test:timeline`) | the bridge, and every kind of edit made through OpenChatCut's own commands → the right call of ours | 44/44 unit tests overall |
| `e2e/occ_timeline.mjs` | read-only: switch, tracks, playhead follows our preview, select, Delete shows a save status that does not move the timeline, back to Classic, light + dark, a cartoon and a reel | 42/0 |
| `e2e/occ_timeline_save.mjs` | **mutating, copy only**: delete an element → saved → Ctrl+Z restores; drag scene 2's start → shared edge saved → Ctrl+Z puts it back | 6/0 |
| `e2e/occ_director_chat.mjs` | **mutating, uses the real AI (1–2 min)**: a note → steps shown, nothing covers the editor, timeline usable meanwhile → reply → changed-scene buttons/highlights/jump → Ctrl+Z and reply-button redo/undo restore the exact plan and script version | 20/0 |
| classic editor suites (`editor`, `layers`, `layers_media`, `timeline2`, `timeline3`, `editor_cleanup`) | the classic editor still works | pass, except failures that happen the same way without this work (a Settings "directors" check; earlier "a hidden track is not drawn 4" in `layers`) |

Also: `npx tsc --noEmit -p .` clean, `npm run build` OK.

## How to run it (this PC)

1. Test server with test data (projects with pictures and with scene elements):
   ```
   cd server
   VT_DATA='E:\VT-test-lowvram' ../.venv/Scripts/python.exe -m vt.cli server --host 127.0.0.1 --port 18796 --name TEST-PC --comfy off --ollama off
   ```
   Drop `--comfy off --ollama off` when pictures or the local writing AI are needed (it starts its own ComfyUI on 8288 and Ollama on 11444).
2. Studio against it: `cd client/studio && VT_SERVER_URL=http://127.0.0.1:18796 npx vite --port 5291 --strictPort`, open
   `http://localhost:5291/p/<project id>` (use `localhost`, not 127.0.0.1).
3. Projects on that server:
   - `2026-11-09-small-habits-low-vram-test-copy` — a cartoon with scene elements; **the one to mutate** (the tests change it and undo).
     It has been edited by the tests and the director (it lost the "Question" element in an early failed run; the director added a title and
     changed a tag and a value card). Make a fresh copy with `POST /api/projects/2026-11-09-small-habits-low-vram-test-copy/duplicate` or from
     `2026-11-09-small-habits-low-vram-test` if a clean one is needed.
   - `2026-11-09-small-habits-same-person` — a reel with three pictures (read-only tests).
4. Tests:
   ```
   cd client/studio
   npm run test:timeline
   VT_PROJECT=2026-11-09-small-habits-low-vram-test-copy VT_PICTURES=2026-11-09-small-habits-same-person VT_URL=http://localhost:5291 node e2e/occ_timeline.mjs
   VT_PROJECT=2026-11-09-small-habits-low-vram-test-copy VT_URL=http://localhost:5291 node e2e/occ_timeline_save.mjs
   VT_NOTE="..." VT_PROJECT=2026-11-09-small-habits-low-vram-test-copy VT_URL=http://localhost:5291 node e2e/occ_director_chat.mjs
   ```
5. Port more OpenChatCut files: add their paths (`src/...`, `shared/...`) to `scripts/openchatcut-timeline-files.txt`, then
   `python scripts/port_openchatcut.py E:/OpenChatCut-9242a95 scripts/openchatcut-timeline-files.txt`. It never overwrites a file marked
   `// Video Tool:`. To see what a file pulls in, follow its imports (a helper script was used: list relative imports recursively, stop at
   modules you will stand in).

## What to do next, in order

### 1. Finish phase 4 (the chat is the owner's main wish)

- [x] **Undo a director change from the editor — Done by codex.** Ctrl+Z and the reply button now undo/redo the Director turn as one
  complete-state history step. Evidence: `tests/test_director_chat.py`; `e2e/occ_director_chat.mjs` 20/0.
- [x] **Show what changed — Done by codex.** Changed scene buttons jump to the scene; its scene and element clips briefly highlight.
  Evidence: `e2e/occ_director_chat.mjs` 20/0.
- [ ] **Proposals before applying** (optional, ask the owner): OpenChatCut's `ProposalCard` + `makeDraft` let the person accept a change before
  it applies. Our director applies at once today.
- [ ] **Give the director the timeline's own operations** (trim, split, move, delete, volume) besides rewriting the script, so "cut the pause
  after the first sentence" or "make scene 2 shorter" work directly. These map to the same calls as `toProject.ts`.
- [ ] **Selection as context:** OpenChatCut can send the selected clip/time range with a message (`agent/selection-refs.ts`, already ported):
  "make *this* shorter".

### 2. Phase 3 — keyframes and audio

- Per-element keyframes (position, scale, opacity, rotation) shaped on the timeline; map OpenChatCut `keyframes` ⇄ our element/layer
  motion (`LClip.keyframes` = `MotionPoint[]`; elements' Motion tab).
- Music on A2 (from the project's music option) with volume keyframes ⇄ our duck / fade settings; sound effect cues on A3.
- Slip / roll edits.

### 3. Phase 5 — polish

- Captions track unlocked and edits mapped to our word/caption edits.
- Markers, context menus checked, waveforms, thumbnails, phone layout, a measured browser test like `e2e/setup_audit.mjs` for the editor
  (contrast, tap sizes, focus).
- Make the new timeline the default, then remove the classic timeline (`review/Timeline.tsx`, its tests) once it covers everything.
- Rebuild and reinstall the apps on this PC (`scripts/build_client_windows.sh`, `scripts/build_server_windows.sh`; reinstall with
  `<installer>.exe /S /currentuser` over the existing install, **no `/D=`**, no uninstall first).

## Things learned (avoid re-discovering them)

- OpenChatCut's UI copy is keyed by the Chinese original; `t('中文')` looks it up in the English dictionary (`src/occ/src/i18n/locale.ts`).
- Their colours are all `var(--cc-*)` (`theme.ts`); map those, do not edit their components' styles.
- Their narration editing is word-based (see phase 2 above); `splitItem` keeps the original id on the left piece.
- Their engine refuses overlapping clips on one track; a scene grows by trimming its neighbour.
- Their trim handle is about 1–8 px inside a clip's edge; the outer 1–2 px move the clip.
- After a save the project reloads and the board is rebuilt; anything that must survive (the save status) lives above the board.
- More element rows push the scenes below the fold of the timeline panel: tests must scroll clips into view.
- Our plan undo (`r.undo` → `planUndo`) lives in the browser page; reloading the page loses it. Restore a test copy through the API
  (`POST /api/projects/{id}/scenes/{scene}/edge {t}`) if a run leaves it changed.
- Old leftover Vite processes keep port 5291 and point at the wrong server; check with `Get-NetTCPConnection -LocalPort 5291` and stop only
  this session's own processes. Other sessions run Vite on 5173–5191; leave those alone.
- `npm install` in a full OpenChatCut checkout was refused by the auto-mode safety check; it is not needed for this porting approach.
