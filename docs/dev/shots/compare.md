# The editor, looked at critically (W15.1, 2026-11-22)

New screenshots: `docs/assets/screens/editor.png` (1440x900 light, a scene selected), `editor-dark.png`, `assistant.png` (Claude Code mid-conversation). All twelve (two sizes, two themes, three states) are in `E:\UltimateVideoTool\scratch\screens\` (made by `client/studio/e2e/screens.mjs`). Earlier: `docs/dev/shots/before-*.png`.

What still looks heavier than the reference (OpenFilm's quiet panes), to fix before W15.1 is ticked:
1. **The pane pills under the title bar** (Tools, Details, Assistant, Timeline) are orange outlined pills: loud for switches that are used rarely. Make them quiet icon buttons in the title bar.
2. **At 1280x720 the timeline toolbar wraps onto two lines**, and the zoom slider lands alone at the start of the second line. Collapse the rarer tools (Split tool, Mute, Remove) into a menu below 1400 px.
3. **The preview is small at 1280x720** (about 136 px wide for a 9:16 video) because the library, inspector and assistant all stay open. Close the library by default below 1400 px.
4. **The Classic / New timeline switch** takes a whole row; it goes away with W11 (one timeline).
5. **The scene list is scrolled so the selected card is cut off at the top** (1440x900, scene 2 selected): scroll the selected card fully into view.
6. **A shot with the scene's old elements on top** (the battery shot under "First" and "Always-on display"): not a layout problem but a content one; fixed in the tool (`set_scene_shot` now says which elements remain on top and can clear them).
