# Frame measurements and Details — Done by codex

## C6 — Done by codex

The production frame probe now shares its self-contained DOM measurement function with `client/studio/e2e/frame_measurements.mjs`. Existing Cartoon measurements remain; stick rigs expose the actual head and character name, Story cartoon figures expose their face and name, and the rebuilt Story bundle carries those markers. Story items are measured individually. Items painted before a Story character are excluded from its coverage findings; a person's own container never counts as covering its face.

Media nodes carry existing detector face rectangles and source dimensions. The probe maps them through the current image's object-fit crop and focal position; it clips them to the visible picture. This uses stored detector metadata and does not run a detector or download a model. Pictures without detected faces produce no invented face findings. Bounds remain geometric, not a pixel segmentation or a full visibility/depth test; rotated/skewed photo bounds are approximate.

Software-browser checks cover covered and clear stick/story faces, photo crop mapping, and own-container exclusion. They also load the actual stick runtime, rebuilt Story runtime and media factory and put a sticker over the resulting named face. All pass. No composition/video export or GPU processing is used.

## C7 — Done by codex

The probe reports text below the phone reading target (34px at 1080 frame width), low contrast against known solid backgrounds (4.5:1 target), text in portrait platform-control zones, and partial opacity. Gradients/images with unknown backgrounds are not assigned invented contrast ratios. Hidden elements are excluded. Sizes and platform zones are explicit heuristics, not universal readability/platform guarantees.

The browser test checks each finding and verifies the DOM is unchanged by measuring. Both new measurements and the existing coverage data feed the director's prompt and the stored final `left` report shown by Quality check. Codex-path tests verify exact measurement text and frame bytes reach a helper director.

## E5 — Done by codex

Details now opens at its tabs rather than auto-scrolling to the end when its first log request arrives. Later new entries can still be followed. Conversations group by step and show a compact preview of the question; opening a row gives the full system instructions, question, answer and retained image attachments. A failed row load offers Try again instead of staying Loading forever.

Provider calls retain exact PNG/JPEG/WebP bytes in the video's `ai-talk-images` folder under content hashes (duplicate images take one file). A project-scoped, name-validated endpoint serves them and rejects path traversal/symlinks. Older records explicitly say only the picture count was kept. An image-storage failure retains the question/answer and records a plain storage warning. Retention limits for these attachments remain part of F11, still open.

The craft module's user-facing summary says `Quality check: N/100; N things to look at.` The existing log browser suite now uses the current What happened / AI conversations / Problems tabs. That live-server suite was updated but not run; the new isolated `details_readability.mjs` exercises actual Details/AiTalk components with fake responses in wide/phone, light/dark. All four cases pass, with full text, grouping, images, visible opening tabs and no overflow/errors. Screenshots in `e2e/out/details-readability` were viewed.

## C8 partial implementation — Done by codex

Measured facts lead the single-revision prompt, with one requested change per problem and correct content left alone. Refused edits now report the field and validation reason; before, only `1 validation error for Scene` was retained. A regression test failed before this fix. The one-revision limit is unchanged. Real gemma runs and verified visual-choice suggestions remain open, so C8 is not ticked.

Later continuation — Done by codex: planning and frame-review prompts now include a bounded menu of real library search results for the spoken content words, with exact sticker/icon fields, values and labels. The menu uses the same dictionary/keyword search as the Studio, with embedding and translation explicitly disabled during prompt construction. Missing libraries leave the prompt usable. It changes no scene and leaves facts first. Four new tests cover real search fixtures for coin/shop and Bangla, exact IDs, unavailable libraries, prompt limits and both prompt paths; the revision/choice group passes six tests. The broader provider/engine/module/conversation/choice/revision selection passes 59 tests. Real gemma acceptance remains paused and C8 stays open.

## Checks and boundaries

- Focused revision/conversation/Codex tests passed (9); the broader selection including one-director tests passed 43, with overlapping coverage. Additional provider/image-failure regressions passed in the final conversation selection.
- Frame software-browser checks pass for DOM fixtures and actual runtime factories. Story bundle rebuilt with `node server/renderer/story/build.mjs`.
- Studio TypeScript/Vite build and 34 timeline tests pass; Details browser fixture passes in four modes.
- Real rendering remains paused by the owner. No GPU, speech recognition, real model calls, deployment, server restart, commits or pushes were performed.
