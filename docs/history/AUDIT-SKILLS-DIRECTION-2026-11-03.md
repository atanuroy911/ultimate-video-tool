# Reusable skills and editable direction: implementation checkpoint

This continues [the app audit](AUDIT-2026-11-03.md). Implementation and acceptance are separate: downloaded reference material is not an installed capability.

| Capability | Implementation | Evidence and remaining acceptance |
|---|---|---|
| HyperFrames editing | Shared canonical keyframes, entrances, transitions, camera recipes, text treatments and 16 component templates. Element and free-layer controls use the same renderer. | 18 measured render positions across three aspect ratios, including split continuity. Studio builds and 19 timeline behavior tests pass. Fresh interactive Motion-panel acceptance remains pending. |
| Reusable animated shorts | Three character treatments, ten environments, timed poses/expressions, generated-image props, environmental text, optional original procedural Three.js sets. Existing story planning is adapted to editable canonical cartoon elements. | Nine real frames inspected across three styles and formats. These are stylized reusable templates, not a claim of matching every reference video's production quality. |
| Director discovery | Full component schemas, story and motion capability modules, scene-direction settings available through the shared module registry. | Contract tests cover canonical data and module parity. Long-form autonomous quality still needs measured real-model evaluation. |
| Scene Direction panel | Editable instructions; selected director/model; picture, video and voice choices; original plan and recorded generation history; per-scene regeneration. | API tests pass. Settings use revision conflicts. Switching tools retains unsaved drafts and active jobs in the current app session. Browser reload does not yet persist unsaved drafts. |
| Scene voice replacement | Any supported voice engine; requested range retained; bounded time fitting; captions updated; one undo for mute, track and caption changes. | Regression tests prove cut clock, scene timing and components survive replacement, including shorter narration. Compose failure restores prior files. Caption timing uses original word anchors; this is not fresh speech alignment. |
| Generation conflicts | Picture/video/voice generation checks whether relevant content changed before applying results. Generated media remains available when a conflicting edit is preserved. | Guards implemented; concurrent multi-client stress testing remains outstanding. |
| Share and Shorts | Selection-first sharing, named account forms, explicit export readiness; Shorts source/picks/edit workflow. | Backend checks and Studio build pass. No real social post or OAuth acceptance is claimed. |
| Distribution | Ultimate Video Tool branding; Windows/Linux client/server build matrix, server isolation and bootstrap fixes. | Older local installers were built and installed. They predate these changes. Fresh installers, clean Linux CI and release publication remain pending. |

Reference research snapshots are in [research/video-skills-2026-11-03](research/video-skills-2026-11-03). The awesome-list extraction contains 412 unique GitHub links; it is an inventory, not 412 audited or integrated projects. HyperFrames remains the actual rendering engine. External arbitrary-code agents, hosted services, Remotion-only compositions and Lottie editing have not all been ported. Original procedural geometry and reusable controls were implemented instead of copying third-party agent instructions. Three.js license files are bundled with compositions.

## Current verification

- Broad non-slow checkpoint before the new Direction work: **1,172 passed, 4 skipped**; [XML](evidence/skills-regression.xml).
- Direction, voice, animation, words and pipeline follow-up: **33 passed**; [XML](evidence/direction-final.xml). Includes rollback, stale scene range and one-word replacement cases.
- Studio production build and all **19** Node timeline/save-race tests pass after the Direction draft changes.
- Real story frames: [contact sheet](evidence/story-kit/contact-sheet.png). Real motion checks: [measurements](evidence/visual-motion/measurements.json).
- Scene caption replacement was rendered and inspected in all three formats: [Run every day](evidence/direction-render/contact-sheet.png). The synthetic fixture's original data was restored exactly by undo; this does not claim real TTS alignment quality.
- Documentation links and measured facts pass the checker. Local Studio was restarted on port 8878; the disposable project's Direction endpoint returns seven picture recipes and two video workflows.
- Browser access subsequently became available. Focused visual checks passed on the disposable project: Direction draft retention, picture/voice controls, live RUN → SPRINT preview and Escape restoration, Video settings returning to caption selection, Typewriter preview/insertion, Slide points and two undos restoring the original component count. Desktop 1440×900 and mobile 400×760 inspected. Compacted the tool navigation and Direction tabs after observing excessive header height; production build passes. Share selection/export readiness, Accounts onboarding and Shorts source screens inspected. Full option/drag coverage, real regeneration quality and distribution acceptance remain outstanding.

No remote GPU service changes, real social posts, commits or release publication were performed in this checkpoint.
