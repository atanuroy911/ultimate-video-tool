# M2: the helper (client/desktop/helper.js)

`node test-helper.js` (in `npm test`), with fake servers and fake assistants. It passes four times in a row. Checked: the local API refuses a missing or wrong key; two servers each connect with their own key and hear about Claude and Codex; no key appears in `/status`; `helper.json` is private (mode 600 on Linux and macOS); a second copy exits and leaves the first running; a closed server is reconnected by itself (backoff 2, 4, 8, 16, 30 s; shortened in the test); planning sessions run one at a time across servers while the others wait (nobody is refused); questions run two at a time with their pictures and each answer goes back to the server that asked; an assistant that is not signed in is told so at once; a cancelled task is stopped and nothing is sent for it; an answer finished while the link was down is sent when it returns; a connection that went quiet is replaced; a server can be removed; the log keeps no key, prompt or picture and is cut at its limit; a restarted helper reconnects to its saved servers; `POST /stop` lets go of the run file.

Two deliberate breakages make it fail: two planning slots instead of one ("Timed out waiting for two sessions to wait"), and no key check ("200 == 401").

## Idle memory
Measured by the last part of the test, which starts the helper as a real process (`ELECTRON_RUN_AS_NODE=1` set, run by plain Node 26.13 on Windows), connects one server, waits for the first Claude/Codex check, and reads `rss_mb` from `/status` 1.5 s later: **59.4 to 60.7 MB** over five runs (limit 80). Electron's own Node mode has not been measured yet: M6 does it with the built app.

## Still to do for this step's wording
"Replacing `test-client-companion.js`": the old companion and its test stay until M6 switches the app over.
