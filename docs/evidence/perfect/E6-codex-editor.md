# E6 editor cleanup — Done by codex

2026-11-06. Implementation and isolated software-browser checks completed. The full scratch-server acceptance gate remains open.

Completed:

- Reproduced the selected Video settings caption disappearing on hover. Computed light-theme foreground was `rgb(0, 91, 184)` on `rgb(0, 98, 196)`: the shared pressed rule supplied blue text, while the primary hover rule supplied a blue background. Scoped editor styles now keep the primary action's white text through selection and hover. Verified light and dark, 1280 and 400 pixels.
- Replaced raw schema field/value presentation with plain labels: Character, Character look, Classic colour, Girl, Speaking character, scene size, camera movement, and readable enum words. Schema values sent to the server retain their original IDs.
- Moved element JSON out of the everyday tabs into an Advanced disclosure. The complete scene JSON is also labelled Advanced; existing JSON validation and all transform/gesture editing remain available.
- Cartoon characters now have horizontal-position and feet-height sliders, nullable automatic floor placement, nullable arrival seconds with its automatic meaning explained, a facing checkbox, and every pose shown through the existing keyboard-accessible PictureChoices component. The SVG pictures are small pose guides, not rendered video frames. A save test verifies the precise x/y/arrival/pose/flip values and the return to `null` automatic settings. Coordinated with C3: all 15 poses have guides, Elder woman has a plain label, and hair/clothes colour pickers preserve empty automatic colours until changed and reset them to empty on request.
- Shared scene thumbnails show a skeleton before a URL exists and while an image loads. A failed image has a named, static fallback. Scene cards and timeline scene clips use the same component.
- Timeline element chips have recognisable icons and readable names. Short chips keep their icon instead of cutting a word to a few letters; the complete visual name remains in the accessible label and tooltip. Keyboard selection and the trim handles remain available.

Validation after the final implementation edit:

- `cd client/studio; npm run build` — passed (TypeScript and Vite).
- `cd client/studio; npm run test:timeline` — 34 passed, 0 failed, 0 skipped.
- `cd client/studio; node e2e/editor_cleanup.mjs` — four viewport/theme combinations passed: 1280/light, 1280/dark, 400/light, 400/dark. The first run failed on the blue-on-blue regression before the fix. This fixture mounts the actual Inspector, ScenesPanel and Timeline, uses an in-memory review, blocks every `/api` request, and launches headless Chrome with `--disable-gpu`.
- Screenshots inspected: `client/studio/e2e/out/editor-cleanup/400-light.png`, `400-dark.png`, `1280-dark.png`; loading screenshots are saved beside them. No page overflow at 400 pixels, all pose titles and controls readable, selected caption visible, narrow number clip icon visible. Screenshots in `e2e/out` are local test output.

Still open: E6 explicitly requires `e2e/editor.mjs` and `e2e/editor_simple.mjs` to pass against the scratch server. They were not run: the former expects a real composition, and the latter edits the scratch reference project. An isolated fixture does not prove server saves or composition rendering. No real render, GPU/model/ASR job, owner-server change or protected service action was performed. Keep E6 unticked until that acceptance gate is run safely.
