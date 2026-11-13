# Our timeline, OpenChatCut's parts

Owner, 2026-11-09: "go through the Timeline UI, I think we can do better… check out OpenChatCut… we chat with the director as well as edit
ourselves… adopt this full open-source work in our timeline." Then, choosing between readings: **"Our timeline, their parts."** Video Tool keeps
its own editor and its own data (scenes, elements, layers, words, pictures, sound). OpenChatCut's code is taken piece by piece and fitted into
OUR timeline so it works on our scenes and pictures. Not a second app, not their editor replacing ours.

Licence: OpenChatCut is AGPL-3.0-or-later; the owner is on its team and approved copying its code. Each ported file keeps a header naming its
source path and commit. Reference copy: `E:\OpenChatCut-9242a95` (github.com/0xsline/OpenChatCut, commit 9242a95, 2026-11-06).

## What is wrong with our timeline today (critique, 2026-11-09)

Seen in the editor (client/studio/src/review, `Timeline.tsx` 709 lines, `LayerLanes.tsx`, `ChatAssistant.tsx` 66 lines):

1. Two lanes only, "Scenes" and "Elements" (packed rows). No track heads, no per-track hide / mute / lock, no audio tracks: the narration, the
   music and the effects are not on the timeline at all, so the person cannot see or move what they hear.
2. No captions track; captions are edited through words in a separate panel.
3. Trimming and moving exist only for scene edges and layers; elements cannot be dragged in time; no ripple, no slip, no roll.
4. No keyframes: an element's motion is a preset name, not something the person can shape on the timeline.
5. The playhead, ruler and zoom are basic: no frame-accurate readout at zoom, no fit-to-window, no markers, no thumbnails strip per clip
   beyond the scene icon, no waveform.
6. The AI is a side panel that answers; it does not show what it changes, step by step, and its changes are not individually undoable.
7. Selection is single; no multi-select, no box select, no copy/paste, few keyboard shortcuts.
8. Undo is per request to the server, not a history the person can step through in the editor.

OpenChatCut has each of these (a multitrack timeline with video, audio and caption tracks, track heads, trim/ripple/slip/roll, keyframes,
markers, waveforms, multi-select, shortcuts, an undo history, and a chat whose every change is a visible, undoable step).

## What we take, and where it goes

| Their part (E:\OpenChatCut-9242a95) | Lines | In our Studio |
|---|---|---|
| `src/components/timeline/*` (Timeline, TrackLane, TrackHead, TimelineRuler, TimelineToolbar, pointer / drag / trim / zoom / shortcut hooks, playhead paint, context menus) | 5.7k | `client/studio/src/occ/components/timeline/` — the new timeline |
| `src/editor/*` engine: clip / track / timeline types, store, reducer (clip, track, timeline, history), keyframes, multi-select, slip, snap, ripple, rate stretch | ~9k | `client/studio/src/occ/editor/` — the editing engine behind it |
| `src/components/chat/*` (chat panel, messages, tool steps, proposal cards, composer, change log) | 4.7k | `client/studio/src/occ/components/chat/` — the director chat, on our director |
| caption types, track geometry, small utilities they need | ~1k | `client/studio/src/occ/…` |
| i18n dictionaries (13 languages), GL effects (56 files), AI model picker, plugin store, uploads | — | not taken: stand-ins (`occ/shims/`): English strings only (memory: UI is English only), no effect registry, our own upload and director |

React stays 18 in the Studio; the ported code is adjusted where it uses React 19 APIs.

## The bridge: our project ⇄ their engine

The new timeline edits an OpenChatCut `TimelineState` in the browser; that state is a **view of our project**, built by
`occ/bridge/fromProject.ts` and written back by `occ/bridge/toProject.ts`:

| Ours | Their track | Notes |
|---|---|---|
| scenes (sentence spans, backdrop picture/clip with its pan/zoom) | V1 clips | moving a scene edge snaps to a word boundary (our rule: scene structure follows sentences); pan/zoom ⇄ zoom keyframes |
| scene elements (title, value card, icons, arrow, compare, …) | V2…Vn clips | per-element timing, position, scale, opacity, keyframes (our E17 per-element editing) |
| free layers (text, media, shapes) | V tracks above | already free in time and space |
| cut narration (words, cuts) | A1 | trimming A1 = cutting words, the same edits our Words panel makes |
| music (with ducking, fades) | A2 | volume keyframes ⇄ our duck / fade settings |
| sound effects (cues) | A3 | |
| captions (word-timed) | C1 | |

Writes go to our server through one new endpoint, `PUT /api/projects/{id}/timeline` (a list of changes in their action vocabulary: move, trim,
split, keyframe, delete, …), which applies them to scenes / elements / layers / words and returns the new view; the server keeps the rules (word
snapping, scene invariants) and the undo history.

## The director in the chat

Their chat UI shows each change as a step ("edit_item", "split_item") with undo, and proposals the person accepts. It is fed by OUR director:
`POST /api/projects/{id}/director/chat` streams the director's turn (Claude / Codex / local AI, as chosen in Settings) with tool calls that
are our editor's operations (the same change list as above, plus ours: redraw a picture, re-voice a line, fix a word, change the look). The
director's rules and prompts stay ours (memory: AI directs, no static rules; prompts visible in the UI).

## Phases (each ends tested in the Studio and in the installed apps on this PC)

| Phase | Done when |
|---|---|
| 1. Engine and timeline in the Studio | Their engine + timeline compile in our Studio (React 18) with the stand-ins; the editor shows our project as V1 scenes, V2+ elements and layers, A1 narration with waveform, A2 music, A3 effects, C1 captions; zoom, ruler, playhead, track heads (hide/mute/lock) work; reading only. |
| 2. Editing writes back | Move / trim / split / delete / multi-select / undo on the new timeline change our project through `PUT …/timeline`; scene edges snap to words; preview and export follow; old timeline removed. |
| 3. Keyframes and audio | Per-element keyframes (position, scale, opacity, rotation) shaped on the timeline; music volume keyframes and ducking; slip/ripple/roll. |
| 4. Director chat | Their chat panel on our director; each change a visible, undoable step; proposals; our tools (redraw, re-voice, fix word). Old AI panel removed. |
| 5. Polish | Markers, shortcuts, context menus, waveforms, thumbnails, light/dark, phone layout; the setup_audit-style measured browser test for the editor. |

## Status

- **2026-11-09 — phase 1 done (behind a switch).** 172 OpenChatCut files ported into `client/studio/src/occ/src` and `src/occ/shared`
  (about 21,000 lines: the timeline UI, its editing engine, captions track, transcript search, shortcuts, English dictionary) with 17
  stand-ins and a typed Remotion `PlayerRef`; they compile in our React 18 Studio. `src/occ/bridge/` shows our project on its tracks
  (`fromProject.ts`: captions from the narration's words, layers, elements packed into rows, scenes with their picture, the narration after
  cuts with words clamped to the kept audio) and drives its playhead from our preview (`playerAdapter.ts`). The editor page has a
  Classic / New timeline switch (remembered per browser); the new one loads only when chosen and says plainly that its changes are not
  saved yet. Tests: `tests/occ-bridge.test.mjs` (OpenChatCut's own engine moves, trims and deletes our converted project),
  `e2e/occ_timeline.mjs` 38/0 on a cartoon and a reel, light and dark.
- **2026-11-09 — phase 2 done.** Every finished edit on the new timeline is saved: `src/occ/bridge/toProject.ts` compares the timeline before
  and after (item ids say what each is in our project) and turns the change into the calls the classic timeline already makes — layers
  document (move, trim, split, duplicate, delete, fades, volume, place, track hide/mute/lock), element timing/split/delete (deletes from the
  last index back), scene edges (our edge move: snapped to words; growing a scene = trimming its neighbour), scene split/remove, and
  narration cuts (OpenChatCut edits a narration with words as word streams: a cut is the run of our words no longer played, up to the next
  word still heard). No new server endpoint was needed. After a save the project reloads and the timeline is rebuilt from it; Ctrl+Z goes to
  our project's undo. The captions track is locked (edited in the Captions panel for now). The save status sits beside the switch and never
  moves the timeline. Tests: unit 44 (each kind of edit through OpenChatCut's own commands → the right call), `e2e/occ_timeline_save.mjs` 6/0
  (delete an element, Ctrl+Z; drag a scene edge, Ctrl+Z; on a copy), `e2e/occ_timeline.mjs` 42/0. Next: phase 4 (director chat) before 3.
- **2026-11-09 — phase 4, first part done.** A **Director** tab (first in the editor's left panel) holds the chat beside the preview and the
  timeline: `src/occ/bridge/DirectorChat.tsx` draws the conversation with OpenChatCut's `ChatMessage` / `ChatRunStatus` (ported, with
  `ToolGroupRow`, `WidgetCard`, message grouping; a small Markdown renderer replaces react-markdown) on OUR director
  (`GET/POST /api/projects/{id}/director[/chat]`, the AI chosen in Settings). While it works its steps show (the current one live, with a
  timer), nothing covers the editor (the request carries `?quiet=1`, so the full-screen job window stays away) and the timeline can be used;
  its reply says what changed and the timeline is rebuilt from the changed video. The first real Claude run on this PC added a title and
  changed a tag and a value card. That first pass left undo, timeline change markers, proposals and timeline operations for later.
- **2026-11-09 — phase 4 undo and change markers — Done by codex.** A Director result now carries the complete state from before its turn
  and exact changed-scene ids. The editor records that result as one shared history step: Ctrl+Z or the reply button atomically swaps the
  scene plan, video script, compiled script plan and Director report, and the button then redoes/undoes the same turn. Changed scene
  buttons select and scroll to the scene; its scene and element clips briefly pulse. Director apply also has an optimistic-concurrency
  guard, so an edit made while the AI is working wins instead of being overwritten. Evidence: `tests/test_director_chat.py` plus the
  script/plan regression suites (25 pytest checks), `e2e/occ_director_chat.mjs` 20/0 with the real AI, `e2e/occ_timeline_save.mjs` 6/0,
  `e2e/occ_timeline.mjs` 42/0, timeline unit tests 44/44, TypeScript and production build. Still to do in phase 4: proposals (optional;
  owner decision), the Director using timeline operations, and the current selection/time range as message context.

## Not taken (decided)

Their project store, Node agent server, Electron shell, export pipeline, media normalization, ONNX/MediaPipe/whisper models, 13-language
dictionaries, plugin marketplace, stock media and generation services. Video Tool already has its own for each, and they are not part of the
timeline the person sees.
