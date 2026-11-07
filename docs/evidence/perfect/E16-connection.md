# E16 - First run and connection (partly done)

Done, with browser tests on the scratch server and screenshots viewed (`client/studio/e2e/out/connection/`):
- **First open:** a server not set up yet says so with "Set up server" and "Later" (`e2e/connection.mjs`).
- **A server that does not accept this computer:** the refused screen says what is wrong and what to do, with no raw error.
- **Choosing graphics cards on a multi-card server:** `e2e/gpu_card.mjs` 37 of 37.
- **The helper starting:** `e2e/helper_card.mjs` 25 of 25.
- **Losing the connection and getting it back:** this was a gap, the Studio said nothing while the server was away. New `src/connection.ts` asks `/api/health` every 3 s; after two misses a banner says "Lost the connection to the server ... Nothing you made is lost"; when it answers again the banner says "Connected again" for 4 s, and every list that had failed to load asks again by itself (`hooks.ts`). `e2e/connection.mjs` 11 of 11; mutation checked (stop reloading and the last check fails).

Not done here, needs the real desktop app (H1, H3): typing the server's address in the app's own window, and a new app version meeting an older server (the app has no auto-updater; the older-server notice in the Studio exists and is not covered by a new test here).
