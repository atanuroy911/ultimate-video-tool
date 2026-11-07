# Retired browser suites

`timeline.mjs`, `flows.mjs` and `phase2.mjs` drove widgets of the old editor (`.tl-aclip`, `Hero`, "Kind of video") that no longer exist. Their checks are covered by `timeline2`, `timeline3`, `editor_simple`, `editor` and `quality`. Kept for reference; they are not run. Retired 2026-10-28.

`link.mjs` and `busy.mjs` (2026-10-28) drove the single-page New form and a "Test the AI" button that no longer exist; `new_flow.mjs` covers the New page as it is now, and the Engines page has its own suite (`engines.mjs`). The New-page parts of `design.mjs` and `edge.mjs` moved to `new_flow.mjs`.

`editor_simple.mjs` (2026-11-07) drove the "everyday editor" with a tool rail and three tracks (`data-testid=simple-editor`), which was replaced by the one editor at `/p/<id>`; `editor.mjs` covers that editor now.
