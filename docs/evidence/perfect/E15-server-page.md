# E15 - Server page wording

New `client/studio/e2e/server_page.mjs` (16 of 16): at 1280 and 400 wide, light and dark, the first line says "Video Tool is the computer that does the work" (no "server 1"), no raw words (undefined, NaN, null), nothing scrolls sideways. Screenshots in `client/studio/e2e/out/server-page/` were viewed. `tests/test_server_restart.py` (6) covers the Restart button's rules: only where the server can tell how it is supervised, refused while a job runs, honest wording where there is no supervisor.

Changed here: job rows named their kind with the internal word ("thumbs", "qa", "plan"...). `JobsPanel.tsx` now names every kind a job can have in plain words ("Scene pictures for the editor", "Looking at every scene", "Planning the scenes"...).

Found while doing it: `/api/setup` took 9.4 s on a computer with no engines, because 9 usual engine addresses were asked one after another at one second each. They are now asked at the same time (`placement.find_existing`, `setup.overview`): 10.4 s to 2.3 s. This was also what made pages wait for "network idle" in the browser suites.
