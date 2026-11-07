# C2 - Every set, every shape

`scripts/qa_sets.py` makes one scene per set (10 sets) x camera (still, push, pull, pan) x light (day, sunset, night) with one character, in 9:16, 1:1 and 16:9. Two frames per scene (start and end of the camera move). Sheets: `dist/lab/sets-<set>-<shape>.png` (30 files).

Fix: set layers were 1000 wide and shift by 8 and 18 under the camera, so an edge could show. Every full-width layer in `vt-cartoon.js` is now `x: -100, width: 1200`.

Looked at the village, street and shop sheets: no edge, gap or floating floor. The script's own edge check (outer columns against the middle) found 0 candidates over all 30 sheets. Drawn on the processor (no graphics card).
