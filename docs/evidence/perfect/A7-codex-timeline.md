# A7 timeline and layer suites — Done by codex

2026-11-07. Continued Claude's browser-suite triage on fresh, disposable copies of the reference project. Each suite used its own loopback backend and Vite proxy, synthetic audio, disabled engine and thumbnail work, and Chrome with `--disable-gpu`.

The initial selector repair reached the timeline controls and exposed stale behavior assertions. A free scene edge now saves an exact time. It keeps the narration beat assignments. The updated suite checks the saved next-scene start against the actual POST body and compares every beat assignment before and after the edit. The edge suite turns snapping off to measure raw pointer movement, scrolls the voice trim handle into view, and compares saved cuts before and after Escape. Previously its no-cut assertion compared two reads taken after the action.

The layer suite now opens Timing before setting a fade and Position before choosing a simple motion. It verifies that the chosen motion is persisted. Existing undo, redo, copy, paste, overlap and hidden-track checks remain in place.

| Suite | Final result | What passed |
|---|---:|---|
| `timeline2.mjs` | 8 passed | Gradual shared boundary movement, exact save, preserved narration beats and non-overlapping chips |
| `timeline3.mjs` | 13 passed | Free edge follows pointer, exact time marker, Escape preserves plan and cuts, voice trim and undo |
| `layers.mjs` | 20 passed | Text editing, live preview, dragging, trimming, fades, motion, history and track operations |

All three reported zero page errors. The wider A7 suite sweep remains open.
