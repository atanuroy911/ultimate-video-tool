# Classic and New timeline: what each does (W11.1, 2026-11-22)

Classic: `client/studio/src/review/Timeline.tsx`, `LayerLanes.tsx`, `MotionClip.tsx`. New: `client/studio/src/occ/` (bridge: `fromProject.ts` builds the tracks, `toProject.ts` turns edits into our server calls, `pages/Review.tsx saveTimeline` sends them).

| Feature | Classic | New | Action |
|---|---|---|---|
| Select tool, blade/split tool, split at playhead (Ctrl+B) | yes | yes | same |
| Snapping (Alt turns it off) | yes | yes | same |
| Zoom in/out, slider, fit | yes | yes | same |
| Ruler: click or drag to move the playhead | yes | yes | same |
| Playhead position typed in seconds | yes | timecode display | check typing a time in the New timecode |
| Scenes lane: drag a shared edge (snaps to words), split, remove | yes | yes (scene-edge, scene-split, scene-remove) | same |
| Elements lane: move/trim/split/delete an element | yes | yes (element ops) | same |
| Added layers (pictures, video, sound, text): move, trim, split, volume, fades, hide/mute/lock | yes | yes (layers document) | same |
| Narration: cut a stretch | yes | yes (voice-cut, by words) | same |
| Narration: mute the selection (M), volume of the selection (dB) | yes | **ported 2026-11-22** (voice-mute, voice-gain from a piece's volume; test in tests/occ-bridge.test.mjs) | ported |
| Narration: restore a cut by dragging an edge outward | yes | no (moving the narration is reported as ignored) | to port |
| Words lane: double-click a word to edit its caption | yes | narration has the transcript; editing a word's text is not saved | to port |
| Selected range on the voice (drag across) | yes | pick mode exists for pointing the assistant; not for edits | to port |
| Add a text layer at the playhead; add a picture/video/sound from files; add a track | yes | yes (text; files via the library and the track menu; TrackCreateControl adds a track) | same |
| Sounds lane (laughter, applause found in the voice; "Listen for sounds") | yes | **shown, 2026-11-22** (a locked Sounds track; test) | ported, with a "Listen for sounds" button by the timeline switch |
| Actions lane (stick-figure actions: drag, trim, delete) | yes | **ported 2026-11-22** (an Actions track; moves, trims and deletes saved as the same action edits; test) | ported (selecting one to edit it in the inspector: still Classic) |
| Motion clip from a picture (MotionClip.tsx: ComfyUI image-to-video) | yes (from a layer clip) | no | to port (the clip itself is slow on a 6 GB card, C7) |

Nothing is dropped yet. Classic stays until every "to port" row is done (W11.2).
