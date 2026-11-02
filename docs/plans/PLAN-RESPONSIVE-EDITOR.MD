# Responsive editor and component-library implementation

Requested 2026-11-02. Keep one editor; preserve existing projects and all supported tools.

## Reference inspection

Cloned for inspection only under `%TEMP%/vt-editor-reference-20261102`:
- [Concat](https://github.com/jub0t/Concat), commit `9e69bbcf40d0f9b74e7d5accfc22a13047c87a00`: inspected editor-dark.png, dock.rs (default/compact layout), inspector and title panel locations. Adopt the compact library/preview/selection arrangement and a narrow-screen layout that gives the preview and timeline their own space. Source is AGPL-3.0; no source/assets will be copied into this implementation.
- [Filmcraft](https://github.com/storytold/filmcraft), commit `68919ed87aa6a097a4d21414ec7c438883f5fe22`: inspected effects screenshot, workspace routing, timeline/trim/transform panel structure. Adopt searchable component groups and explicit selection/timing controls. Source has MIT/Apache licensing. No foreign runtime or project format is needed for this pass.

## Cross-check of existing implementation

| Capability | Actual state | Work needed |
|---|---|---|
| 39 scene element types | Pydantic schema, generated catalogue, director/MCP exposure, renderer implementations already exist | Replace the long Add menu with a searchable, categorized visual library; preserve the same schema |
| Extra text, picture, video and sound tracks | layers.json + API + timeline + live renderer + export mixer exist | Keep these; expose insertion alongside scene components |
| Animated text, stickers, icons, diagrams, charts, characters | Already implemented as scene components | Make them discoverable and editable without knowing component names |
| Motion presets, transitions, picture framing, caption styles | Existing controls and renderer support | Retain; do not introduce duplicate editor pages |
| Concat integration | Optional experimental stdio client and spike script; not a complete Studio feature | Do not present this as production integration or replace the existing renderer |
| Filmcraft integration | No implementation found | Use workflow ideas; do not claim native Filmcraft support |
| Mobile editor | CSS stacks full panels; toolbar/grid wastes height, canvas shrinks, controls overflow | Compact navigation and overlay panels; preserve visible preview + timeline; large touch targets |
| Shared scene edge | Frontend uses beat.start; renderer uses beat.start minus 0.10s and minimum spacing. Save reload is not awaited. Two single-sentence scenes have no alternate boundary. | Use exact video seconds, preserve pointer offset and await saved timing; narration ownership does not constrain scene edges |
| Scene redistribution | Silently slices visuals to 5 | Remove the five-visual cap and never silently discard elements or sound cues |

## Implementation order

1. Scene edges and splits use exact video seconds, independent of sentence ownership. Visuals and actions retain their own ranges across scene changes. Use the same timing functions from the UI API and Director/CLI/MCP modules. Keep every visual and sound cue on merge; save and undo must preserve precise times.
2. Add a shared searchable element library. Category chips, representative illustrations, plain names, timing/target guidance and click-to-add. Reuse it in the left panel and Inspector Add. Existing components stay available; empty/loading states explain the next step. English default insertion examples; do not inject unrelated sample facts into finished content silently.
3. Add a small geometric Shape component (rectangle, circle, triangle, line) through the canonical schema, catalogue and renderer. Forms, director, MCP, composition and export must all use this same representation. No UI-only widgets.
4. Rework responsive space allocation: compact editor header, compact labeled tool tabs, panel close controls, one side panel at a time on smaller windows, overlay panels on phones, preview and timeline retained. Keep all commands reachable, with explicit labels and keyboard access.
5. Validate: build/typecheck; timeline and save-race regressions; component catalogue/schema/API/compose tests; boundary precision/loss tests; live project-copy API checks. Visually inspect desktop, tablet and phone layouts and insert/edit/undo new and existing components when Cua is available. Update handoff with actual outcomes and blockers.

## Scope boundary

This implements discoverable components and an editor workflow on our existing engine. Native Rust codecs, a node compositor, full keyframe curves, grading scopes and importing Concat/Filmcraft project files are separate engine projects, not implied by a UI reference. Existing motion/transition tools remain available. Scene boundaries, visual ranges, captions and actions can be timed independently. Voice cuts ripple explicit visual timings through the source clock.

## Acceptance

- No duplicate editor routes, hidden desktop-only timeline, silently dropped visuals, or component that only renders in the browser preview.
- At 390, 768, 1024 and 1440+ widths, navigation and selection controls remain reachable; opening a panel does not collapse the preview to zero.
- Drag guide and saved scene edge agree to 1 ms; no unexpected jump from the 0.10s scene lead.
- Every selectable library item has a validated default and a renderer path; Shape is visible in director/MCP catalogue and all output formats.
- Report remaining failures and visual restrictions explicitly.
