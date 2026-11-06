# E10: the Bangla interface is removed (decision 8)

Owner, 2026-11-06, in the middle of K5: "I think remove bengali i18n in ui. It sucks.. No need. Just language in video is fine."

## What was removed
- `client/studio/src/i18n.ts`: the whole Bangla dictionary (about 500 lines), `dicts`, `setLanguage`; `useT()` now simply looks the English text up. The words that existed only so they could be translated (`helper.msg.*`, `gpu.engine.say.*`) are gone, and the cards show the sentence the helper or the server sends.
- The language switch in the sidebar (EN / বাং) and the "App language" row in Settings; the `ui_language` setting in the store and the type; the `vt-lang` browser key; `document.documentElement.lang` is no longer set from a setting. The server no longer keeps `ui_language` (default settings and the list of keys the API accepts); `scripts/lab/configure_fresh_server.py` does not write it.
- Relative times ("3 hours ago") are English.
- Browser suites: the Bangla pages, checks and screenshots are gone from `helper_card.mjs` and `gpu_card.mjs`; `flow.mjs` no longer switches to Bangla and no longer needs Bangla letters in its pass condition; the two scratch scripts `shot_bn.mjs` and `shot_plan_bn.mjs` are deleted; the old `*-bn.png` screenshots are deleted.
- The plan: decision 8; E10 rewritten (this step); G7, M8, K4 and I4 no longer ask for Bangla. The earlier evidence notes (M8, K4) still describe the Bangla screens they once had, and say so.

## What stays (Bangla for videos)
The video language choice "বাংলা" (New video, options), recognising a script written in Bangla (`hasBangla`), Bangla voices, transcription and captions, the Bangla example words in placeholders, the Bangla currency sign, and the fonts that show Bangla text from a video (`--font`, `.bn`, the prompter, the word list). D5 and D8 and G4 still test Bangla videos.

## Checks (2026-11-06)
- `tests/test_no_bangla_ui.py` (new, 4): the dictionary has no Bangla text except the two lines that name the video language, no `bn` map, no `setLanguage`, nothing keeps `ui_language` or `vt-lang`, the shell and Settings offer no language for the app, and Bangla is still offered as a video language. **Five deliberate breakages, each caught:** a Bangla line in the dictionary; a language switch function; the interface language setting; the shell's switch; Bangla removed as a video language.
- Browser (headless Chrome, `--disable-gpu`, against the dev server): `helper_card.mjs` 25 passed, `gpu_card.mjs` 37 passed.
- `tsc` clean, `npm run build` ok, `npm run test:timeline` ok.
- **Found on the way:** the new graphics card section crashed the whole Server page when the server was older than the app, because an older server answers without the new fields. The card now says "this server is older than this app" and the page stays up; `gpu_card.mjs` has a check for it (the owner's real server is in that state until it is updated).
