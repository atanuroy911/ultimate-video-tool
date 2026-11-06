# M6: the app uses the helper

## What changed
- `client/desktop/helper-control.js` (new): the app starts the helper if none runs (`spawn(process.execPath, [helper.js], {detached, stdio: "ignore", windowsHide}` with `ELECTRON_RUN_AS_NODE=1`), reuses one that answers, and replaces one of an older version (it stops it and starts the new one; the servers it knew are kept in `helper.json`).
- `main.js`: `attach()` now ensures the helper and sends it the selected server (`POST /servers`, address only). The in-process companion is gone. `before-quit` does not stop the helper. `--helper` is handled at the very top: ensure the helper, then quit, before anything else loads (this is what the start-with-the-computer entry will run, M7). New IPC for the page, accepted only from the app window: `helper-status/start/stop/refresh/remove-server/autostart`. Help menu: "Open helper log".
- `main-preload.js`: the page sees `vtDesktop.assistants`, `vtDesktop.helper {status, start, stop, refresh, removeServer, setAutostart}` and `vtDesktop.server.choose()`. The old `director`, `companion`, `director-run` and `onLog` entries are gone (nothing handled them).
- Studio: `store.ts` no longer has a director of its own; `Engines.tsx` and `Reach.tsx` call `vtDesktop.server.choose()`.
- Removed: `client-companion.js`, `test-client-companion.js`, `test-live-companion.js`, `assistant-status-worker.js`, `scripts/lab/check_client_connection.py` (it drove the companion; M9 gives the lab bench the helper path instead).
- `package.json`: `build.files` lists `helper.js`, `helper-control.js`, `device.js`; `npm test` runs `test-director-runner`, `test-helper`, `test-helper-control`, `test-transport`. `.github/workflows/ci.yml` runs the helper tests instead of the companion's.

## Found and fixed on the way
- A race in the helper: when stopping it closed its port first and removed its run file a moment later, so for a few milliseconds nothing answered yet the file was still there. `npm test` failed 3 runs in 6 because of it; the file is now removed first. 12 runs in a row pass.

## Checks
- `npm test` (client/desktop): passes 12 times in a row. `tests/test_packaging.py` and `tests/test_product_split.py`: 11 passed.
- **A built app.** `electron-builder --win --dir -c.win.signAndEditExecutable=false` (the flag `scripts/build_client_windows.sh` uses, because this account cannot create the symlinks the signing tools need) into a scratch folder.
  - The packaged program in Node mode **runs `helper.js` straight out of `resources/app.asar`**: no `asarUnpack` is needed.
  - The packaged app started with the owner's real app folder, connected to the server and started the helper as a separate windowless process. The server listed "Claude on MSI-LAPTOP, ready".
  - **After the window was closed** (`CloseMainWindow`): no window left, the helper kept running (same pid), stayed connected, Claude still ready, and the server still listed Claude on this PC.
  - The first-run default would have registered a start-at-login entry pointing into my scratch folder, so before this test I placed the app's own "already decided" marker file; the test registered nothing. Afterwards I removed the marker and every file the test made (`device.json`, `helper.json`, `helper-run.json`, `helper.log`); the app folder has its original five files again, the registry's Run list was never touched, and no helper process is left. The test computers were also removed from the server's remembered list.

## Memory of the idle helper (the plan said under 80 MB)
| What | Plain Node 26 | Electron Node mode (packaged) |
|---|---|---|
| Windows **private** memory (what Task Manager charges the process) | n/a | **58 MB** |
| Working set (`rss`, counts shared pages of the Electron runtime) | 57 MB | **83 MB** |
| JavaScript heap kept | 6.6 MB | 4 MB, flat |
- Private memory meets the limit; the working set is 3 MB over it because Electron's runtime pages are counted. Over 3.5 minutes connected to the real server the working set moved 82 to 83 MB while the heap stayed flat (a probe of 400 fast-forwarded check cycles grew the heap by 0.2 MB; 40 real Claude and Codex checks grew it by 0.1 MB), so this is not a leak.

## Not done here
- M7: the start-with-the-computer entry (the code is in `main.js`, but registering it needs the real installed build and the owner's agreement; see M7).
- Updating over a running helper: it is the app's own program, so the Windows installer may find the product's exe in use. H1 and H4 must test an update and an uninstall with the helper running, and the installer must stop it.
