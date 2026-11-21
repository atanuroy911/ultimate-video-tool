# UI review, 2026-10-28

Method: `client/studio/e2e/shots_all.mjs` takes a screenshot of ten pages at 1440 px and 390 px, light and dark (`client/studio/e2e/out/ui/`). Each was looked at; this is what was found and changed.

## Changed
| Found | Change |
|---|---|
| Phone: the top menu was cut off ("Socia") | A bottom tab bar on phones (Projects, Look, Shorts, Social, Settings), as on iOS |
| Shorts page was a dark panel with unreadable text in light mode | Three colour names used by older pages did not exist; they now point to the real palette (`--card-bg`, `--input-bg`, `--fg`) |
| Shorts header carried a "Powered by..." badge | Removed |
| Projects with one video showed filters, Select and search | Select appears from 3 videos, search from 9, filters from 6 (the dashboard test already required the 9) |
| Setup wizard had English text typed into the code | All of it is in `i18n.ts`, English and Bangla |
| Phone editor: the Export button dropped to a second line | One line; Details shows its icon only |

## Still open (not done)
- Result page: the preview is black until a video is rendered; no first-frame cover.
- Export page: "Advanced options" is a disclosure triangle, not a step sheet.
- The older pages (Local AI, AI assistants, Social accounts) were not opened one by one.
- Not done: the accessibility pass (U12), the full Bangla editor (U10), a test with a person who has never seen the app.

Checks after the change: `dashboard` 10/10, `engines` 9/9, `quality` 10/10, `contrast` 14/14, `editor_simple` 22/22, `menus` all passed; `a11y` is skipped without axe-core.

## Second pass (same day)
| Found | Change |
|---|---|
| Export: "Advanced options" was a disclosure triangle | A three-step sheet (Size and quality, Words, Sound), opened by "More options…" or by choosing Custom; `e2e/export.mjs` updated and passes with a real render (8/8) |
| Result: a black box before the first render | The first frame, dimmed, with the message over it |
| Result: two loud gradient buttons | Only "Redo with AI model" keeps the gradient; the other reads "Fix the risky moments" |
| Settings: opened with the Codex connection | Order is now General, Speech, Engines, AI, Stock keys, Claude, Codex, System check |

`flows.mjs` fails on `.scene-card`, which the editor no longer has; it was not touched by these changes and is one of the stale suites in the audit.

## Third pass (same day)
| Done | Evidence |
|---|---|
| **Accessibility sweep with axe-core** over nine pages (Projects, New, Editor, Export, Themes, Settings, Shorts, Social, Result), light and dark, 1440 and 390 px: zero serious or critical findings | `AXE=<path>/axe.min.js node client/studio/e2e/a11y.mjs`; fixed low-contrast blue text (new `--accent-text`), green status text, the dark-mode Delete button, a radio card that held other controls, three selects and two progress bars without names |
| **Everyday editor in Bangla**: about 120 strings moved to `i18n.ts` (editor, timeline, sound panel, picture tools, hook card) | screenshot `client/studio/e2e/out/ui/editor-bn.png`; the English text is unchanged so the suites still pass |
| New flow step label "3 → 7" now reads "Step 3 of 7" (ধাপ ৩ / ৭ in Bangla) | `e2e/walk_new.mjs` |
| Settings: the JSON blocks for Cursor, Windsurf, VS Code and Gemini sit behind one "Other assistants" fold | |
| Retired the three browser suites that drove the old editor (`timeline`, `flows`, `phase2`); `editor.mjs` and `stick.mjs` now open `/p/:id/pro` | `client/studio/e2e/retired/README.md`; `editor` 23/23 |

Not done: the Bangla text is mine and has not been read by a Bangla speaker; the full editor at `/p/:id/pro` is still English; nobody who has never seen the app has tried it (the screenshots in `client/studio/e2e/out/ui/` are the review, not a user test).

## Fourth pass (same day): the plan sheet and what came with it
| Done | Evidence |
|---|---|
| The plan review sheet (four steps, moment cards, the strip of changes, cost and Start, the live board): looked at at 1280 and 390 px, light and dark; no sideways scroll; axe finds nothing serious or critical on step 1, the cards and the last step | `client/studio/e2e/plan.mjs` (36 checks), screenshots in `client/studio/e2e/out/plan/` |
| Dark mode: the lighter blue on a hovered primary button failed contrast against white text; it keeps its blue and brightens instead | `styles.css`, found by that axe check |
| The New page again has what the one-question flow had dropped: *Kind of video* (Fine tuning), the rights note on a link, the script shown large while recording, and a *Delivery* switch on the voice screen | `client/studio/e2e/new_flow.mjs` (22 checks) |
| The editor can open a plan again for a reel (*Change the look or the pictures…* on the AI tab) | `client/studio/e2e/plan.mjs` |

The plan sheet and the shared step sheet (Step n of m, Back, Continue, Done) are in English and Bangla (about 90 strings, mine, not read by a Bangla speaker). Still English: the sentences the director writes ("Why: ...", the notes and checks) because they come from the server; the cost lines; the Share card. A person has not used the plan sheet on a real video.
