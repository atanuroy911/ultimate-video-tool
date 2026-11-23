# Plan: scene-level HyperFrames editing and a scene generation panel

Owner, 2026-11-23: "for image/video generation using some models, we should have a panel where we can generate multiple images for a scene (not
initially done by the director, but we can through prompts and manual edits). Think of Higgsfield." And: "the Studio button is vague; we have
HyperFrames inside our own Studio, so if we are editing via HyperFrames for a particular scene there should be more granular and intuitive controls."
Reference picture: a three-column generation page (result player with versions; a grid of generated frames, each with "Redraw"; a setup column with
reference images, style and quality presets Low / Normal / High / Ultra / Ultra Max, a progress list and one "Send" button).

## Part S: HyperFrames per scene (granular, named for what it does)

| # | Step | Done when |
|---|---|---|
| S1 | **Name it.** The header button says "Edit in HyperFrames"; inside the Studio a **scene bar** sits above it: ◀ Scene 3 of 7 ▶, the scene's words, and buttons *Pictures for this scene*, *Redo with the Director*, *Back to the editor*. ◀ ▶ move the Studio's playhead to that scene. | Moving scene by scene in the bar moves the Studio; each button does its one thing. |
| S2 | **Open a scene, not the video.** Every scene card's menu and the scene inspector get *Edit this scene in HyperFrames*: the Studio opens at that scene's start with the scene's clip selected. | From scene 4's menu the Studio opens on scene 4. |
| S3 | **The scene's parts in our words.** The scene bar lists the scene's parts (title, card, picture...) by their readable ids; clicking one selects it in the Studio (through its Layers panel). | Clicking "Term" in the bar selects S4 Defn Term in the Studio. |
| S4 | **One scene as its own composition** (HyperFrames' own advice, `nested_structure_needs_subcomposition`): bake each scene to `scenes/<id>.html` mounted by the root, so the Studio can open one scene alone. | The Studio's Compositions panel lists one entry per scene; frames stay identical. |

## Part G: a generation panel for a scene (Higgsfield-like)

| # | Step | Done when |
|---|---|---|
| G1 | **Generate pictures for a scene.** A panel with three columns: the scene playing (left), the candidates grid (middle: each picture with *Use*, *Redraw*, *Variations*), the setup (right: prompt prefilled from the scene's words and the Director's note, reference pictures from the media bin, quality Draft / Normal / High / Ultra, how many 1-8, the picture model). *Generate* makes the pictures one after another (a job with progress per picture); each lands in the scene's candidates and in the media bin. *Use* puts the picture behind the scene (the same as the Director's picture backdrop). | Four pictures for scene 3 from a prompt; one used; the scene shows it; the others stay as candidates. |
| G2 | **Clip from a picture.** A candidate's *Make it move* turns it into a short clip (the Wan 2.2 / LTX image-to-video workflows already there), shown in the grid as a clip; *Use* works the same. | A 3 s clip from a candidate plays behind the scene. |
| G3 | **Prompt help.** *Write prompts for me*: the Director (or Claude Code) proposes N different prompts for the scene from its words and the video's look; the person edits them before generating. | Four distinct prompts appear and can be edited. |
| G4 | **History per scene.** Every run is kept (prompt, seed, model, quality, time taken); *Redraw* reuses all of it with a new seed; candidates can be deleted. | Reopening the panel shows earlier runs; Redraw keeps the prompt. |

Rules: the pictures come from the picture engine the person chose (ComfyUI on this computer or their own server address); nothing goes to a cloud
service unless the person adds one in Settings. When no engine answers, the panel says so in one sentence and links to Settings. English UI.
Order: S1, S2, G1, G4, S3, G2, G3, S4.

## Progress

- **S1 done (2026-11-23):** the header button says **Edit in HyperFrames** ("HyperFrames open" while it is). Above the Studio a scene bar: ◀ Scene n of N ▶
  (the Studio's playhead moves to the scene: its address hash `t=` is set without reloading it), the scene's words, *Pictures for this scene*, *Redo with
  the Director* (opens the Director on that scene), *Back to the editor*. Screen: docs/dev/spikes/html-shot/s1-scene-bar.png.
- **S2 done:** every scene card's menu has *Edit this scene in HyperFrames* (the Studio opens on that scene) and *Pictures for this scene*.
- **G1 done (and G4's history):** `vt/scene_gen.py`, routes in `server/gen_routes.py` (list, generate as a job, use, forget), panel
  `review/ScenePictures.tsx` (three columns: chosen picture with *Use for this scene*; every picture made for the scene with *Use*, *Redraw*, *Forget*;
  the setup: prompt from the scene's words or the last run, model from the picture sets, how many 1-8, *Generate n*, progress). Runs are kept in
  `gen/<scene>.json`. With no picture engine the panel says so in one sentence. Tests: tests/test_scene_gen.py (3, stand-in engine),
  e2e/scene-pictures.mjs 7/7. Screen: docs/dev/spikes/html-shot/g1-scene-pictures.png. Not tried with real pictures: no ComfyUI on this PC (ISSUES).
- **S3 done:** the scene bar has a second row, *Select:* and the scene's parts by name ("Term", "Eq", "Meaning" for `s4-defn-term`...; layout boxes left out),
  from `GET /api/projects/{pid}/studio/parts?scene=`. Picking one adds `selFile`/`selId` to the Studio's address hash, which the Studio reads as its
  selection (found in its source: the hash keeps `t`, `tab`, `selFile`, `selId`), without reloading; picking it again clears it. Tests:
  e2e/studio-parts.mjs 5/5 (the Studio's own `--selection` answers the part), desktop-studio.mjs (the chips and the address).
- **G2 done:** each picture has *Make it move* (a 3 or 5 s clip that starts on it; the clip model from the list or "Any that runs"); clips show in the grid
  next to their picture and play large on the left; *Use* shows a clip behind the scene. `scene_gen.animate`, `POST .../pictures/{media}/move` (a job).
  Tests: test_scene_gen 4/4, scene-pictures 9/9. Screens: s3-scene-parts.png, g2-make-it-move.png. Real clips not tried (no ComfyUI here).
- **G3 done:** *Write N prompts for me* under the prompt: the AI chosen in Settings writes N different prompts from what is said in the scene and
  around it, with the drawable-prompt rules (self-contained place, people and scale; only visible things; close-up for rare poses; no writing).
  Each is an editable card (*Use*, *Draw one*, remove); *Draw all N* makes one picture from each in one run, and each picture keeps its own prompt
  for *Redraw*. `scene_gen.write_prompts`, `POST .../pictures/prompts`. Real test: Sonnet wrote 4 distinct prompts for c2-mix s4 in 7 s. Tests:
  test_scene_gen 6/6, scene-pictures 12/12. Screen: g3-written-prompts.png.
- Left: reference pictures in the setup (not built), S4, and real pictures/clips once a picture engine runs here.
- Next: S4.
