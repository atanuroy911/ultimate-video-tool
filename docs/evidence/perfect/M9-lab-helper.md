# M9: the test bench gets the real path (half done: the `make` run waits)

## What changed
- `scripts/lab/vt_lab.py helper start|status|stop`:
  - `start` runs `client/desktop/helper.js` with plain Node, detached, in its own folder `dist/lab/helper` (git ignores `dist/`), with `VT_HELPER_HOME` set to that folder and the computer name `<this PC> (lab)`. A different folder means a different helper: its own device id (`device.json`), its own saved servers, its own run file and log, so it never meets the app's helper. It adds the server by its address (`POST /servers`, no key: the server is on this network, M5b), waits until the server lists it ready, then prints what it found and the `make` command to use.
  - `status` prints the helper (pid, version, memory, device id), each server and its state, Claude and Codex on this PC, and what the server lists for this device.
  - `stop` asks it to stop and waits for its run file to go.
- `client/desktop/helper.js`: `VT_HELPER_NAME` gives the computer another name on the server (default: the computer's own name). Test: `test-helper.js` starts the real program with the name set and checks the name the fake server hears; with the line removed the test fails (`the name from VT_HELPER_NAME is the name the server hears`).
- `vt_lab.py direct` is gone. It ran Claude the way the app did before M3 (no lockdown: it could run shell commands and read files), so it was out of date and unsafe. The helper replaces it. The plan's tool table and H2 say so.
- Plan wording: the device name is `<this PC> (lab)`, not `Lab helper on <this PC>`, so the director reads "Claude on MSI-LAPTOP (lab)" instead of "Claude on Lab helper on MSI-LAPTOP".

## Checks done (2026-11-06, against the owner's real server, 192.168.123.47:8790)
- `helper start`: the helper started (pid 20904), connected, Claude 2.1.314 signed in, Codex not installed on this PC. **The server listed `claude@bf2272d0: Claude on MSI-LAPTOP (lab) | ready | Ready on this device.`**
- `helper stop`: stopped; the server listed the same id as `not ready`, last seen 07:36, "Not connected. Open Video Tool on that computer; its helper starts with it and reconnects by itself."
- `helper start` again: the same device id (`bf2272d0`) came back from its saved file; a second `start` while it runs reused the running one (same pid 37944) instead of starting another. Stopped again afterwards (the helper does not stay running).
- `helper.log` has the start, connect and stop lines only.

## Not done: the `make` run
The step's second check is `make claude@<id> cartoon lab-helper` running. `make` renders the video by itself at the end (the autopilot, GPU mode), and the server stopped hard twice on 2026-11-05 during render-heavy test runs (`A3-server-restarts.md`). The plan's rule (section 0.5) is no render-heavy run until the owner has answered. So M9 stays open. Everything that does not render goes on; the run happens first thing after the owner's answer (and it is also M10).
- The id for it is `claude@bf2272d0` while the helper in `dist/lab/helper` is the one running; `helper start` prints it.

## Left on the owner's server
The server remembers the lab computer for 60 days ("Not connected" under "Computers using this server"). It is harmless, but the owner will see "MSI-LAPTOP (lab)" there until it ages out.
