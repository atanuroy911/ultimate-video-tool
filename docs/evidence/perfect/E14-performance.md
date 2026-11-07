# E14 - Performance (partly done, honest numbers)

Method: `client/studio/e2e/perf_timeline.mjs` against a **production build** of the Studio (`vite build` + `vite preview`), headless Chrome with `--disable-gpu` (no graphics card is used on this PC), the scratch server. Two projects: `reference` (17 s) and a synthetic 10-minute project `long10` (125 sentences, 63 scenes, 1,500 words, a 600 s soundtrack; built by cloning `reference`).

| | 17 s video | 10 min video, before | 10 min video, after |
|---|---|---|---|
| scrub the playhead, median frame | 16.7 ms (jank 0%) | 166.6 ms (jank 65%) | 100 ms (jank 64%) |
| zoom, median | 16.7 ms | 133 ms | 133 ms |
| scroll, median | 16.7 ms | 67 ms | 67 ms |
| play, median | 16.7 ms | 183 ms | 133 ms |
| page nodes | 135 | 4,109 | 2,669 |

Short videos are perfectly smooth. The 10-minute one is **not yet smooth in this GPU-less test**, so the Check ("playback and scrubbing stay smooth", click within 100 ms) is not met and E14 stays open.

What was found by isolating the cost (hiding parts of the page while scrubbing): script, style and layout time are small (under 1 s each over the whole run); the time is painting. Hiding the preview frame alone, or the timeline's chips alone, each brought the median back to 16.7 ms, so the two together pass what a software painter can do. Removing the chips' icons and trim handles plus layout containment gave 16.7 ms in the experiment.

Changes made (all in the Studio): trim handles of chips and words are drawn by CSS instead of two extra elements each; chips narrower than 44 px carry no icon; words are not drawn when they would be narrower than about 12 px (it says "Zoom in to see and edit the words."); scene cards in the left list use `content-visibility: auto`; each lane is `contain: layout paint style`. The editor suite (`editor.mjs`, 23 of 23) still passes.

Left, and why it is parked rather than fixed blind:
- The preview composition keeps every scene's elements laid out at all times (`.scene { opacity: 0 }`, shown by the timeline): 4,667 visible nodes at time 0 for 63 scenes against 84 for the short video. Hiding scenes that are not on screen (`visibility`) belongs in the shared renderer runtime (`vt.js`), so it also changes every export; it needs its own careful change and the golden comparisons, and a measurement on a real graphics card (the owner's browser, H1), which is what people use. The software painter used here exaggerates paint cost.
- Not measured: a click's response time on a real GPU; a 10-minute video with real thumbnails (the synthetic one has none, so its scene list shows 48 loading placeholders).

Also found: `/api/setup` took 9.4 s (see E15-server-page.md); fixed.

Suites that still use old selectors (for A7): `timeline2`, `timeline3` (`Move the end of scene 1`), `layers` (`Fade in` slider).
