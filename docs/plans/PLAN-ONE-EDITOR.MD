# Plan: one editor, ours, with HyperFrames' parts inside it

The owner, 2026-11-24: "using 2 different studio panels like this is not good ... why would a user need to know 2 studios to work ... you can reuse
individual components from HyperFrames with our own UI. Think better." Before that, the same morning: HyperFrames is for scenes made of HTML, not a
replacement for the whole editor (PLAN-OPENMOTION.MD section 6).

## 1. The idea

There is one editor: Video Tool's own (the workbench: scenes, canvas, inspector, timeline, assistant). What makes HyperFrames' editing good is moved
**into** it as parts, so a person never sees a second studio, a second window or a second set of buttons:

| HyperFrames part (`@hyperframes/studio`, Apache-2.0, published as source) | Where it goes in our editor |
|---|---|
| Canvas editing layer (`ConnectedDomEditOverlay`, `DomEditProvider`, `useDomEditSession`): select, move, resize, rotate, crop handles, snapping, guides (`GridOverlay`) | On our canvas, over the preview |
| Design panel (`PropertyPanel`, `ColorField`, `GradientField`): text, font, size, colour, fill, gradient, opacity, layout | In our inspector, for the selected part |
| Layers panel (`LayersPanel`) | In our inspector or the scene list: the selected scene's parts |
| Edit history (`useEditHistoryActions`, `usePersistentEditHistory`) | Only if it fits our undo; ours stays otherwise |
| Timeline, player | Not taken: our timeline (OpenChatCut-based, the owner's choice) and our preview stay |

## 2. What each kind of scene needs

- **A scene made of HTML (a code-native shot):** it is already HyperFrames source, so its parts plug in almost directly: the handles and the Design panel
  change the shot's elements; our shot format keeps edits in `overrides.json` (the code is not rewritten), so a small adapter turns their edits into
  our overrides. This replaces the separate HyperFrames window for shots.
- **Our other scenes (cards, numbers, pictures, stick, cartoon, story):** they are drawn by our runtime from the plan, not from HTML source. The same
  handles and Design panel work through an adapter that turns a move, resize, rotation, font or colour into our element's fields (position, scale,
  rotation, text style), saved with the plan as today. The person sees the same handles and the same panel on every kind of scene.

## 3. Steps (each built, checked on this laptop, committed to `workbench`)

| # | Step | Done when |
|---|---|---|
| E1 | **Prove it on one shot (spike).** Upgrade our editor to React 19 (the parts need it); add `@hyperframes/studio` at our HyperFrames version (0.9.81); put the canvas handles and the Design panel on a shot in our own shot editor. Measure what it adds to the app's size. | A shot part is moved, resized, rotated and recoloured with HyperFrames' handles and panel inside our editor, saved to the shot; every existing editor test still passes. If the parts cannot work without HyperFrames' own server and project files, stop and report before E2. |
| E2 | **Shots fully in our editor.** Their Layers list for the shot; their handles and Design panel; the separate HyperFrames window and tab removed. | No second window anywhere; a shot is edited start to finish in our editor. |
| E3 | **The same handles on every scene.** The adapter for our runtime scenes. | A card in an explainer, a number, a picture and a stick figure's label are moved, resized and restyled with the same handles and panel; exported videos show it. |
| E4 | **Animation.** If their keyframe, ease and motion-path editing is exported as parts, the same for element animation; otherwise ours stays. | Decided after E3 with what the package actually offers. |
| E5 | **Clean up.** Remove what only served the separate studio (the whole-video bake path for editing, the scene bar, the Video tab, the gateway) once nothing uses it. | No code path opens a second studio. |

## 4. Rules and risks

- One editor, our look: their parts styled with our design tokens, not their theme. English UI.
- Apache-2.0: keep their licence and notice, say what we changed.
- Risks: the React 19 upgrade touches the whole editor (our tests must pass first); their parts may assume HyperFrames' own project server and files
  (E1 finds out before anything else is built on it); the package is large (E1 measures it).
- Testing: the editor's own browser tests on the editor's real pages; no batch video runs (the owner, 2026-11-24). Quality is judged on the owner's own
  recordings when the owner asks.
