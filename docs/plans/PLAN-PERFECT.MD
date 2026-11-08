# Plan: take Ultimate Video Tool to "nothing left to fix"

For an AI agent (Claude Sonnet) working in this repository with no memory of earlier sessions. Written 2026-11-05 from a reading of the code and real test videos. Updated the same day with the owner's decisions (Phases M and K, section 3). Your progress lives in this file: each session continues at the first unticked step.

## How to use this plan

1. At the start of every session, read sections 0 to 3 in full.
2. Find your place: `grep -n -m1 "^- \[ \]" docs/plans/PLAN-PERFECT.MD`.
3. Do that one step, in the way section 0.3 describes.
4. Tick it (`- [x]`) only when its **Check** passed after your last edit. Add one line under it: `Evidence: <file, command result or what you saw>`. Add one line to `WORKLOG.md`.
5. If the check still fails after three real attempts at the cause, mark it `- [!]`, write what you tried and what you found, and go on to the next step that does not depend on it. **Owner, 2026-11-06: "list all the breaking stuff and finish rest of the implementation and then come back to it later."** Everything that is broken, blocked or risky is in `docs/evidence/perfect/BREAKING.md`. Add to it whenever you park something, keep working on what is not blocked, and come back to that list when the rest is done.
6. Do the phases in the order they appear: A, M, K, B, C, D, E, F, G, H, I. Phase A makes every later check trustworthy. Phases M and K change how directors and graphics cards work, and everything after them tests on top of that.
7. At the end of each phase, update `CLAUDE-HANDOFF.md` and `CODEX-HANDOFF.md`, and tell the owner in a few plain sentences what now works and what does not.

Short paths such as `vt/...`, `ai/...`, `script/...` and `compose/...` are under `server/vt/`. Line numbers in this plan drift, so steps name functions and search terms. Read the code before you change it. If the code disagrees with this plan, the code is the truth: note the difference and do what the step is for.

---

## 0. Rules

### 0.1 The owner's standing rules. Never break these.

- **No commits and no pushes** until the owner asks in the current session. Never add `Co-Authored-By` or any attribution line.
- **All heavy processing runs on the GPU server** `roy@192.168.123.47`, under `/home/roy`. Ask the owner once per session for the password and pass it only as the environment variable `GPU_PASS` on the command that needs it. Never write it to a file, a log or this plan.
- **The Tesla V100 (GPU 0) is for the owner's training.** Nothing Video Tool starts or asks may run on it, AI models included. The RTX 3060 (GPU 1) is Video Tool's card. Phase K makes this a real setting.
- **Never change** the owner's ComfyUI install or service on 8188, the Ollama service, anything under `/mnt/bigdata/`, or ports 8765, 8766 and 8777. Your own test folder on the server is `/home/roy/vt-tests`, and Video Tool's own files are under `/home/roy/ultimate-video-tool-server`. Step K3 runs Video Tool's own Ollama copy there, beside the owner's service, which stays untouched. Do not touch other folders. If a step seems to need it, stop and ask.
- **No GPU tests, renders or speech recognition on the Windows PC.** Browser tests may run on this PC in headless Chrome with `--disable-gpu`, because they only drive the UI.
- **No global Python.** Use `.venv/Scripts/python.exe` and `.tools/uv`. Do not bypass Windows UAC.
- **The AI directs.** One director per video. See 0.2.
- **Every prompt and answer stays visible** in the UI (Details, AI conversations; `vt/ai/talk.py`).
- **The UI wraps everything.** A user never runs a command after install. Each capability is one function in `server/vt/`, with an `/api` route the Studio uses, a `vt` command and, where useful, an MCP tool.
- **One name per thing.** See step E1.
- **Retention is the metric for videos.** Apple's clarity, deference and depth are the standard for the app.
- **Test with Claude on the Sonnet model first, then gemma.** Do not ask about Claude usage. ElevenLabs waits until the owner gives a key.
- Write plainly in the UI and in reports. Say "Claude on this PC", not "claude@device".

### 0.2 The test for any code that touches a plan

Before you add or keep code that handles a director's plan, ask: **does this change, hide or remove what the director decided, without the director hearing about it?**

If yes, do not do it. In this order, prefer to:
1. **Teach:** say it in the director's brief (`server/vt/house_rules.py`, `script/prompt.py`, `planner/prompt.py`, `director_review.py`, `directors.py`).
2. **Give ability:** add the field, pose, tool or picture the director lacked.
3. **Give facts:** measure the frame and tell the director (`frame_facts`). The director decides.
4. **Refuse with the reason:** for something invalid, return the exact error so the director can fix it.

Allowed: rule-based plans made when no AI is available may be finished by rule passes (the `ai_directed` flag in `Pipeline.stage_plan`), and a person's own edits always win.

### 0.3 How to do every step

1. Read the code involved, all of it, before deciding anything.
2. Reproduce the problem and see it yourself.
3. Find the root cause. Do not patch the symptom.
4. For a bug, write a test that fails first, and confirm it fails.
5. Make the smallest change, in the style of the surrounding code.
6. Run the test and the related tests.
7. **Look at the result.** For video work, deploy and read the real frames with the Read tool. For UI work, take a screenshot and read it. A passing test does not prove a picture looks right.
8. Run the step's Check again after your last edit. "I did not re-check after the last edit" means the step is not done.

### 0.4 Honesty

- Say only what you saw. Passing with a fake server proves nothing about the real one, so say which you ran.
- Report failures with the output. Do not retire, skip or loosen a test to make it pass unless the feature it tests is really gone, and record why.
- Changing a golden image or an expected value requires looking at the new result first.
- An estimate is not a measurement. Label it.

### 0.5 Traps that already cost time here

- The Bash tool breaks on large heredocs with mixed quotes, and `sed` can turn `\b` or `\n` into control characters. For anything long, write a script file and run it, or use the Edit tool.
- `cat > file` without input hangs the shell. So does `python3 -` before a heredoc on some setups.
- Windows consoles are cp1252: set `PYTHONIOENCODING=utf-8` or a print can crash after the work finished.
- Do not run `pytest tests` from the repo root on this PC. Many tests need `ffmpeg` and `node` on PATH and a different working folder, and some would use local hardware. Use `vt_lab.py tests`.
- A render test that fails on its first line may be a leak from an earlier test (see A4), not a render bug. Run the file alone before you believe it. `vt_lab.py tests <files> -rs` also lists what was skipped: samples kept out of git make tests skip themselves quietly.
- Vite can serve a stale file. Restart it before judging a screenshot.
- A contact sheet can catch a frame mid-transition, so something looks faded. Check the exact moment with `vt_lab.py frames` before calling it a bug.
- A server restart empties the list of connected directors. Once Phase M is done the helper reconnects within seconds. Until then, "Claude on this PC" returns only when the desktop app reconnects.
- Starting Electron from a VS Code terminal needs `ELECTRON_RUN_AS_NODE` removed from the environment, or it exits at once.
- `scripts/run_all_checks.py --e2e` uses port 8777 and `scripts/run_acceptance.py` starts a local server. Do not run either as they stand (see A6 and I1).
- After creating a new folder, run `git check-ignore -v <path>`. Ignore rules have swallowed source before.
- **The server stopped hard twice on 2026-11-05 during full test runs** (16:59 and 21:25), and the owner's V100 training was running. Cause unknown: read `docs/evidence/perfect/A3-server-restarts.md`. Before and after any heavy run, read `uptime` on the server (`ssh ... uptime -p`). If it says the server restarted, stop, do not start another run, and tell the owner. Do not run the whole suite or the render tests again until the owner has answered the question in that file. Run small groups of files instead.

---

## 1. Tools

| Need | Command |
|---|---|
| Put the working tree on the server | `GPU_PASS=... .venv/Scripts/python.exe scripts/lab/deploy_server_code.py` (refuses while a job runs). It sends `server/vt`, `renderer/runtime`, `renderer/scripts`, and the coin picture. Extend it if you change other server files. |
| Make a real video | `GPU_PASS=... .venv/Scripts/python.exe scripts/lab/vt_lab.py make <director> <style> <name> [--aspect 9:16] [--lang en]`. `<director>` is `local` (not before K6), `best`, or a Claude or Codex id from `/api/directors` once the helper runs. |
| Keep Claude on this PC ready for the server | `... vt_lab.py helper start`, `status`, `stop` (M9). `start` prints the id to give `make`. It runs the same `helper.js` as the app, with plain Node, in `dist/lab/helper`. |
| Render it | `... vt_lab.py export <project> [--aspect 9:16]` |
| Contact sheet of the render | `... vt_lab.py sheet <project> <name>`, then read `dist/lab/<name>.png` |
| Exact frames from the deployed code | `... vt_lab.py frames <project> <name> 0.0,2.0,8.0` |
| What covers what, measured | `... vt_lab.py facts <project> 1.0,8.0` |
| Who directed, AI conversations, errors | `... vt_lab.py report <project>` |
| Full test suite on the server | `... vt_lab.py tests` (about 10 minutes; run it in the background; results stay in `/home/roy/vt-tests/last.txt`) |
| One test file on the server | `... vt_lab.py tests ../tests/test_stick.py` |
| Studio on this PC, against the server | `cd client/studio && VT_SERVER_URL=http://192.168.123.47:8790 npx vite --port 5174 --strictPort --host 127.0.0.1` |
| Screenshot every page | `cd client/studio && VT_URL=http://127.0.0.1:5174 node e2e/_audit.mjs <out dir> light` (needs the API key in `dist/recording-run/key.txt`) |
| Types and build | `cd client/studio && npm run build` |
| Windows app installer | `bash scripts/build_client_windows.sh client/desktop/dist` |

`<style>` is one of `cartoon story stick emoji explainer infographic mixed reel auto`. The API key is at `dist/recording-run/key.txt`: never print it.

Test scripts live in `scripts/video_lab.py`: `EN_SLEEP`, `EN_STORY`, `EN_PRODUCT`, `EN_DATA`, `EN_DEBATE`, `BN_SCRIPT`. `vt_lab.py make` uses the Maya story by default and takes `--script-file`. Name test videos `lab-...`, and use the scratch server from A6 as soon as it exists.

Skills worth loading for UI work: `ui-ux-pro-max:ui-ux-pro-max`, and the design auditor at `C:\Users\Roy\design-auditor\SKILL.md` with its `references/`.

---

## 2. What "perfect" means here

The work is finished when all of these are true. Every gate is checked in Phase I.

| Gate | Passes when |
|---|---|
| G1 Tests | `vt_lab.py tests`: 0 failed, 0 errors. Each skip has a stated reason. `npm run test:timeline`, `npm run build`, `client/desktop` and `server/desktop` `npm test`, and `scripts/check_docs.py` all pass. |
| G2 Browser | Every kept suite in `client/studio/e2e/` passes against the scratch server. Axe reports 0 serious or critical problems on every page, light and dark, wide and phone. |
| G3 Director | A test proves code never hides, shrinks or drops what any AI placed: it measures and tells the director. Details names one director per video, and every AI step of that video went to it. |
| G4 Claude videos | Every style passes the video checklist (D1) three fresh times in a row with Sonnet, in 9:16, and once each in 16:9, 1:1 and Bangla. |
| G5 Local AI videos | Every style finishes with gemma: no fallback to rules, one model in Details, no crash, no measured face coverage above 10%. Its pictures may be simpler than Claude's. |
| G6 Inputs | Audio with SRT, a real recording, a talking-head video, a screen recording in both modes, and a link each produce a passing video. |
| G7 App | Every page scores at least 90 with the design auditor, has no horizontal scroll at 400 px, has loading, empty and error states. |
| G8 Reliability | Every failure in Phase F produces a plain message and recoverable state, and has a test. |
| G9 Install | Windows client and Linux server install and uninstall cleanly, and typing the server's address is all a new computer needs. |
| G10 Helper | With the app closed and no Claude on the server, a whole video runs through the helper: every AI step goes to Claude on the person's computer, nothing goes to the local AI, and the director comes back by itself after a restart of the helper or the server. |
| G11 Graphics cards | Setup on a multi-card computer asks which cards Video Tool may use, in the app, in the server manager and in the terminal. Sampling `nvidia-smi` during real work shows nothing Video Tool started or asked on a card that is not allowed. |
| G12 The owner | The owner has watched the final pack and says it is good. Only the owner can close this gate. |

**Limits. Say these plainly; do not hide them.** Tests can prove the app is correct, not that strangers will watch to the end: that needs real viewers. Gemma's taste may stay below Claude's. Some items need the owner's accounts (section 3).

---

## 3. Decisions

### Decided. Follow these.

| # | Decision |
|---|---|
| 1 | **Code never hides, shrinks or drops what any AI put on screen, for every director including gemma.** The owner asked for this to be thought through rather than asked. When things do not fit, automatic layout makes them fit by scaling them together, because that is layout's job. What still overlaps is measured and told to the director, who fixes it. If it is still there after the director's rounds, the video keeps it and the Quality check lists it for the person. Only plans made by the built-in rules, with no AI in charge, keep the old guard. Steps B2 and B3. |
| 2 | "Style" means how a video is drawn. "Look" means its colours and type. "Cartoon 1" becomes "Cartoon" and "Cartoon 2" becomes "Story cartoon". Owner agreed 2026-11-05. |
| 3 | Sonnet is the default Claude model for directing, changeable in Settings. Owner agreed 2026-11-05. |
| 4 | The V100 is for training, so Video Tool's AI stays off it too. Done by running Video Tool's own Ollama copy pinned to an allowed card (K3, K6). The owner's Ollama service is not changed. |
| 5 | A small helper is always bundled with the client, because Claude and Codex are usually not on the server. It starts with the computer by default, with a visible switch to turn that off. Phase M. |
| 6 | Setup asks which graphics cards Video Tool may use on any multi-card computer or server. Phase K. |
| 7 | **No pairing.** Owner, 2026-11-05: "remove the key pairing altogether... Just let user put the ip address." A computer on the server's own network (this computer, home or office addresses, Tailscale) connects with the address alone: no code, no approval, no key. Two things stay, because without them the change would be unsafe: (a) a connection from outside that network, or one a tunnel or proxy forwarded, still needs the server's own key, so publishing a port can never open the machine to the internet; (b) a request from a web page is refused (a different site, or a name that is not an address or a local name), so a site the person visits cannot use their server. The separate feature that shares one computer's engines with another (Engines page, "Share this computer's engines", `vt engine pair`) keeps its own code: this decision was about connecting the app to a server. Step M5b. |
| 8 | **The interface is English only.** Owner, 2026-11-06: "remove bengali i18n in ui. It sucks.. No need. Just language in video is fine." The Studio, the server pages and the desktop windows show English only: no Bangla dictionary, no language switch, no Bangla screenshots or checks for any screen. **Bangla stays a language for videos**: the script, the voice, the captions, the transcription (D5, D8, G4). Step E10 is withdrawn. |
| 9 | **The director makes the first cut and one revision; the person finishes it in the editor (human in the loop).** Owner, 2026-11-06: "see even if something cuts text and overlaps.. the later edits on the timeline we should be able to fix them ourselves... I think one revision is fine" and "having comprehensive edit option in the timeline per element like all kinds of transform warp etc.. i can fix them.... human in the loop". So: (a) the director's last look is one look and one revision (`ROUNDS = 1` in `director_review.py`); no more AI rounds to chase perfection. What is still wrong afterwards is listed for the person in the Quality check (B2). (b) Every element can be fixed by hand, on the canvas and on the timeline, with a full set of transform controls: step E17, done right after B7. (c) A hand edit is never undone by the pipeline: an edited scene or a free-placed element is left alone by every rule. |

### Waiting for the owner. Do not act on these.

| # | Question | Until answered |
|---|---|---|
| W1 | Try a better local vision model? Video Tool's own Ollama copy (K3) means this no longer touches the owner's service, but it costs disk and memory on the RTX 3060. | Stay on gemma. |
| W2 | Claude on the server needs the owner to log in there. The helper makes this unnecessary. | Keep that path working, and test it with a fake only. |
| W3 | ElevenLabs key, social accounts, code-signing certificate, a Mac to test on. | Those steps stay unticked, marked "needs the owner". |
| W4 | Delete the many test videos on the real server (`look-local`, `final*`, `One director test`, `SRT test`, `Cartoon * test`)? | Show the list and ask. Never delete a video you did not make. |

---

## Phase A: Make the bench trustworthy

- [x] **A1. Confirm the starting point.** Run `git status --short | wc -l` and `git log --oneline -3`. Run `vt_lab.py report 2026-11-05-final4`. **Check:** the report prints a status. If `dist/recording-run/key.txt` is missing, ask the owner.
  Evidence: 184 changed files on main (last commit 4d544a6); vt_lab.py report 2026-11-05-final4 printed status rendered, director local, 59 AI conversations; key file present.

- [x] **A2. Deploy the working tree.** Run the deploy command. **Check:** it prints `health: {'ok': True...` and the RTX 3060 is the saved primary card.
  Evidence: deploy printed health: {'ok': True, ...}; the saved primary card GPU-a1b5ab18 is the RTX 3060 (index 1). The V100 showed 90% load from the owner's own python3 training.

- [x] **A3. Take a baseline.** Run `vt_lab.py tests` in the background. Save its output as `docs/evidence/perfect/A3-baseline.txt`. **Check:** the last line gives counts of passed, failed and errors. On 2026-11-05 it was 13 failed, 1303 passed, 12 skipped, 9 errors.
  Evidence: whole suite on the server: 1882 passed, 0 failed (docs/evidence/perfect/A3-A5-tests.md)

- [x] **A4. Fix every failure in the baseline, one test at a time.** Read each failure first. Decide: code bug, out-of-date test, or something about the test bench. Fix the right one. **Check:** `vt_lab.py tests` has 0 failed and 0 errors, except any you marked `[!]`.

  Known failures and causes, as found on 2026-11-05. Confirm each before you act on it.
  1. **A leak between tests causes most of them.** `tests/test_paths_dist.py::test_the_renderer_is_pointed_at_the_products_own_ffmpeg_ffprobe_and_chrome` leaves `HYPERFRAMES_BROWSER_PATH` pointing at a fake Chrome. `monkeypatch.delenv` records nothing for a variable that is absent, `use_product_binaries` then sets `os.environ` directly, and the test's final `delenv` records the fake value, which teardown restores. Every later render test then fails with `spawn .../chrome-headless-shell EACCES` (`test_render_golden`, `test_phase2_render`, `test_stick`, `test_stick_render`, `test_vision`). Run alone, those files pass. Fix the test so the environment is exactly as it was afterwards. Then check the whole suite.
  2. **`test_gpu.py::test_onnx_runtime_has_cuda_and_never_tensorrt`:** `gpu.onnx_providers()` returns `("CUDAExecutionProvider", {"device_id": n})` when a card is pinned, and the test compares it with a plain string. The test is out of date. Compare the provider's name.
  3. **`test_engine_fit.py::test_tunnel_config_marks_published_ports`:** `discover.tunnels()` also reads `/etc/cloudflared`, so on the server the test reads the owner's real config. Make the test isolate it. Do not print the owner's hostnames in reports.
  4. **`test_phase2_render.py::test_contact_sheet_matches_the_golden`, all three shapes (mean difference 10 to 14):** the golden images date from the first commit, and shorter caption chunks came later (`_tidy_chunks` in `composer.py`). On 9:16 the graphics match by eye and only the captions differ. Look at every sheet, in all shapes, a and b. Then regenerate with `VT_UPDATE_GOLDEN=1` on the server and copy the new images back into `tests/golden/`.
  5. **`test_modules_equivalence.py::test_recordings_are_byte_identical[bn_plain]`** fails on `project.json`. That is step A5.
  6. **`english sample.mp3` is not on this PC,** so the English recording test skips. Ask the owner for the file. Until then, state this as the reason for the skip.
  Evidence: whole suite on the server: 1882 passed, 0 failed (docs/evidence/perfect/A3-A5-tests.md)

- [x] **A5. Solve `test_recordings_are_byte_identical`.** It fails on `project.json` when run on the server with the samples present, and the cause was never found. In `tests/test_modules_equivalence.py::_compare`, when hashes differ, make the assertion print which files differ, and for JSON files the first differing key and both values. Run it on the server only (`vt_lab.py tests ../tests/test_modules_equivalence.py`). Find what is not repeatable (a time, a floating-point value from speech recognition, an order of keys, a cached model answer) and fix the code. **Check:** it passes twice in a row.
  Evidence: whole suite on the server: 1882 passed, 0 failed (docs/evidence/perfect/A3-A5-tests.md)

- [x] **A6. Make the browser tests able to run again.** They have not worked since the client and server split, because the server requires a key.
  1. In `client/studio/vite.config.ts`, when the environment variable `VT_SERVER_KEY` is set, add an `Authorization: Bearer` header to every proxy entry. Do not change production behaviour.
  2. Add `scratch start` and `scratch stop` to `scripts/lab/vt_lab.py`: copy the repo as `tests` does, into `/home/roy/vt-tests/scratch-repo`. Start `venv/bin/python -m vt.cli server --host 0.0.0.0 --port 8792 --name Scratch --comfy existing --comfy-url http://127.0.0.1:8188 --ollama off --voicestudio off`, with `VT_DATA=/home/roy/vt-tests/scratch` and `CUDA_VISIBLE_DEVICES=1`. Check with `ss -ltn` first that 8792 is free. Read the scratch key from `$VT_DATA/engine-hub.json`. Never point these flags at anything else: other values can start or change the owner's engines. After K3, a suite that needs the local AI may use `--ollama existing --ollama-url http://127.0.0.1:11444`, Video Tool's own copy.
  3. Build the `reference` test project there with `samples/build_reference.py` (read it first, and confirm it writes under `VT_DATA`).
  4. In every suite in `client/studio/e2e/`, add `--disable-gpu` to the `chromium.launch` args.
  5. Run: `VT_SERVER_URL=http://192.168.123.47:8792 VT_SERVER_KEY=<key> npx vite --port 5175 --strictPort --host 127.0.0.1`, then `VT_URL=http://127.0.0.1:5175 VT_PROJECT=reference node e2e/dashboard.mjs`.

  **Check:** `dashboard.mjs` reaches the real app, not the "Approve this PC" screen. Confirm by reading a screenshot.
  Evidence: scratch server on the GPU server (8792), reference built, dashboard.mjs reaches the real app, screenshot read (client/studio/e2e/out/a6-dashboard.png)

- [ ] **A7. Run every browser suite and sort the results.** Write `docs/evidence/perfect/A7-e2e.md` with one row per suite: passes, fails and why, or out of date. Delete helper scripts beginning with `_` that are no longer useful (keep `_audit.mjs`). Fix real bugs now. Update out-of-date suites. Retire a suite to `e2e/retired/` with a reason in its README only if the feature is gone. Find out why `crawl.mjs` takes over 10 minutes (ROADMAP P10-12). **Check:** every kept suite passes.
  Partial verification — Done by codex (2026-11-07). The updated timeline and layer suites passed 41 checks on isolated scratch projects, including exact boundary saves with unchanged narration beats. Evidence: docs/evidence/perfect/A7-codex-timeline.md. The full sweep stays open.
  Progress (2026-11-08, Claude): full sweep on this PC behind a guard that refuses heavy work (`scripts/lab/e2e_guard.mjs`; the runner now resets `reference` per suite): 56 of 71 pass. 5 real bugs fixed (empty narrow chips, size jump when typing a transform, the caption look and a picture video's plan unreachable after the old editor, a Settings crash) and 17 out-of-date suites updated; crawl takes 62 s. The other 15 need the GPU server's scratch (they make videos or need ComfyUI). Evidence: docs/evidence/perfect/A7-e2e.md.

- [x] **A8. Run the other test sets.** `cd client/studio && npm run test:timeline && npm run build`. `cd client/desktop && npm test`. `cd server/desktop && npm test`. `.venv/Scripts/python.exe scripts/check_docs.py` (on 2026-11-05 it reported that the facts table in `docs/STATUS.md` differs from the code: run it with `--fix-facts`, then read what changed). **Check:** all pass.
  Evidence: npm run test:timeline 23/23 pass; npm run build (tsc + vite) ok; client/desktop npm test (companion, director runner, transport) ok; server/desktop npm test (3 files) ok; check_docs.py --fix-facts rewrote only the counts in the STATUS.md facts table (40->41 element types, 37->43 MCP tools, 247->264 API routes, new pages NewOptions/ScriptReview/Server...), then check_docs.py reports no PROBLEM.

- [ ] **A9. Lock in the renderer fixes with real-browser tests.** These were checked only by eye on 2026-11-05. Add `server/renderer/scripts/dom-probe.mjs`, modelled on `frame-facts.mjs`, which opens a composition, seeks to a time and returns the result of a JavaScript expression. Add `tests/test_render_direction.py` (mark it slow) that proves:
  - a first-scene cartoon has its character at opacity 1 at `t = 0`, with `entrance: "auto"` and with `"none"`;
  - lip and pose cues are not shifted ahead of the voice;
  - a quote with the `blur-slide` recipe in a later scene reads `bought sweets anymore` with its spaces;
  - `arrive: 0` and `arrive: 2` show the character at the right times;
  - `caption.y` moves the caption;
  - a word-reveal caption box grows with the words said;
  - `frame_facts` reports a sticker placed on a face.

  **Check:** the tests pass on the server, and each one fails if you revert its fix (try this for at least three of them).

---

## Phase M: The helper on the person's computer

Owner, 2026-11-05: Claude and Codex are usually on the person's computer, not on the server, so a small micro server is always bundled with the client.

**What exists.** `client/desktop/client-companion.js` runs inside the app's main process. It dies when the window closes, serves one server, and does one kind of task: a whole planning session over MCP (`direct`). So on a video directed by Claude on the person's computer, every other AI step (understanding the video, the last look, the title) gets no AI at all (`NoProvider` in `server/vt/ai/providers.py`).

**What to build.** In the UI it is called **the helper**.
- It runs by itself: the app's own program in plain Node mode (`ELECTRON_RUN_AS_NODE=1`, the way `mcp-bridge.js` already runs). No window, no Chromium, no Python, no models, no project files.
- It starts with the computer and with the app, and stays when the app closes. One per user.
- It calls the server. The server never connects to the person's computer, so firewalls and home routers do not matter. It reuses `/ws`.
- It does two jobs: `direct` (a whole planning session, as today) and `ask` (one question, with pictures if any, answered as JSON).
- On the server, every AI step of such a video goes to it through one new provider. `NoProvider` goes away. One director, for everything.

- [x] **M1. Record how it behaves today.** With the app open, read `/api/directors`, then close the app and read it again. Read the AI conversations of a video directed from this PC. Write what you saw in `docs/evidence/perfect/M1-before.md`. **Check:** the file shows Claude disappearing with the window, and the AI steps that got no AI.
  Evidence: docs/evidence/perfect/M1-before.md: Claude and Codex on MSI-LAPTOP listed with the app open and gone after the window closed (also not back after the server restart); NoProvider shown to give every other AI step no AI.

- [x] **M2. Make `client/desktop/helper.js`, grown out of `client-companion.js`.** It must start with plain Node as well as in Electron's Node mode.
  1. Home folder: the app's own (`%APPDATA%\Video Tool`, `~/Library/Application Support/Video Tool`, `~/.config/Video Tool`; `UVT_DEV_HOME/client` in development, as in `main.js`).
  2. `helper.json` keeps each saved server and its token, readable by this user only (`chmod 600` on Linux and macOS). This is the same protection Claude's own login file has, and the token can be withdrawn from the Server page. `helper-run.json` keeps its port, key and process id.
  3. One per user: if `helper-run.json` names a live helper that answers, exit.
  4. Local HTTP on `127.0.0.1` with the existing key check: `GET /status` (version, each server and whether it is connected, last error, Claude and Codex found and logged in, busy, queue), `POST /servers` and `DELETE /servers` (`{server, token}`), `POST /refresh`, `POST /stop`.
  5. One `/ws` link per saved server, each reconnecting on its own (2, 4, 8 up to 30 s), each announcing Claude and Codex as `refresh` does today.
  6. A queue: `direct` runs one at a time across all servers, and further ones wait instead of being refused with "already directing". `ask` runs up to two at once.
  7. `helper.log`, cut at 1 MB. Never log a token, a prompt or an image.

  **Check:** `test-helper.js`, replacing `test-client-companion.js` and added to `npm test`, with a fake server: the key is required, two servers connect, a server restart reconnects, tasks queue, a second copy exits. Idle memory is measured and written down, and under 80 MB.
  Evidence: client/desktop/helper.js + test-helper.js (in npm test, passes 5 runs, two deliberate breakages fail it); idle memory 59.4-60.7 MB under plain Node (limit 80). The old companion and its test stay until M6. See docs/evidence/perfect/M2-helper.md.

- [x] **M3. Add the `ask` job, and lock the helper down.**
  1. In `director-runner.js`, add `ask({system, prompt, schema, images, model, timeout, signal})`: the twin of `ClaudeCLIProvider.complete` in `ai/providers.py`, which you must read first. It uses a temp folder, a system-prompt file, the same flags, image files opened with the Read tool, `--json-schema` or the schema in the prompt, and it reads `is_error`, `structured_output` and `result`.
  2. In `codex-runner.js`, add the same with `codex exec` and the same isolation flags, with no MCP. Read `codex exec --help` for the current image and output-schema options.
  3. Messages: server to helper `{type: "ask", request, assistant, model, system, prompt, schema, images: [base64 png], timeout}`; helper to server `{type: "ask_done", request, ok, text, error, error_kind}` with `error_kind` one of `limit`, `login`, `other`. Add `model` to the `direct` message and to `args()`, accepting only `[a-z0-9.-]+`.
  4. **Limit what Claude can touch.** This runs on the person's own computer on text from a transcript or a web page, which must be treated as untrusted. `ask` reaches only its temp folder: use a path-limited rule such as `Read(./**)`, not plain `Read`. `direct` gets the Video Tool MCP tools and no shell. In the 2026-11-05 runs the tool lists show Claude calling `PowerShell`, `Read` and `Grep` during `direct`: find out what those calls did and were allowed to do, then pass the narrowest `--tools` and `--allowedTools` that still let it work, and test that against the real CLI.

  **Check:** `test-director-runner.js` covers both with a fake CLI. A real `ask` on this PC with one image returns valid JSON. A real attempt with a prompt asking it to read a file outside its folder, and to run a command, is refused, and you read the output to confirm it.
  Evidence: ask for Claude and Codex in director-runner.js/codex-runner.js, tested with stand-in programs (and mutations); real Claude: picture read as BANANA, outside-file read and shell command refused, run offers 0 built-in tools and still calls list_projects. Found that the old direct flags let a shell run. Codex only against a stand-in. See docs/evidence/perfect/M3-lockdown.md.

- [x] **M4. Send every AI step to the person's director.**
  1. In `server/vt/directors.py`, add `DirectorBroker.ask(...)`, blocking like `request`, using the same `_runs` and `finish`. Handle `ask_done` in the `/ws` loop in `server/vt/server/app.py`. Add `director_model`, default `sonnet`, to `settings()`, and send it with both tasks.
  2. In `ai/providers.py`, add `ClientProvider(chosen)`: `supports_images = True`, and `available()` true when the device is connected and logged in. `complete()` calls `broker.ask` and turns `limit`, `login` and timeouts into `AIUnavailable` with a plain reason.
  3. `Pipeline._director_provider` returns it for `claude@` and `codex@`. Delete `NoProvider`, and its `isinstance` checks in `ai_enabled` and `stage_compose`.
  4. The planning stage keeps its MCP session, which is where Claude directs best. The last look in `stage_compose` now also runs for these videos, because Sonnet often skips re-checking its last edit and this gives it one more look with measured facts.
  5. Find everything that reaches Ollama without the provider (`planner/llm_plan.py`, `reel/plan.py`, `ai/vision.py`, `server/vt/server/app.py`, and search for more) and make sure none of it runs for these videos.

  **Check:** a test with a fake device: a video directed by `claude@fake` sends understanding, planning, last look and title to the fake, and fails if `OllamaProvider.complete` or `llm.chat_json` is ever called. Update `tests/test_one_director.py`.
  Evidence: ClientProvider + DirectorBroker.ask + director_model + the video's director scope for jobs; NoProvider removed; fake-device test shows understanding, planning, last look (with pictures) and title all go to the laptop and no other mind is asked; 6 mutations caught; 110 passed on the server (uptime unchanged). See docs/evidence/perfect/M4-every-ai-step.md.

- [x] **M5. Survive interruptions.** Today `broker.disconnect` fails a running task at once. Keep a task alive for 90 s after a disconnect, and accept its result from the same device on a new socket. The helper resends a finished result it could not deliver. Retry a lost `ask` once. `listing()` remembers devices it has seen (saved in the data folder) and shows them as "Not connected" with what to do, instead of removing them. **Check:** tests for a short network drop, a long one (fallback with a plain notice), and a server restart.
  Evidence: 90 s grace with re-send on reconnect (helper ignores duplicates), plain failure after the grace and a cancel when the computer returns, boot id in hello so a helper drops a restarted server's work, computers remembered as 'Not connected'; failed client director now recorded as rules with a notice. 7 new Python tests + helper tests; 8 breakages caught; 136 passed. See docs/evidence/perfect/M5-interruptions.md.

- [x] **M5b. Remove key pairing (decision 7).**
  1. `server/vt/server/serve.py`: a request is trusted when its sender is this computer or on a private, link-local or Tailscale (100.64.0.0/10) address, nothing forwarded it, its `Host` is an address or a local name, and any `Origin` matches that `Host`. Trusted requests need no key on `/api`, `/ws`, `/media` and `/mcp`. Everything else needs the server's own key as before. Remove the pairing code, `/api/pair`, `/api/server/code`, the device list and revoke, the assistant key, and `server/vt/server/clients.py`. `/.well-known/video-tool` says `needs_key` for the asker. The 401 text no longer mentions pairing.
  2. `/ws`: a device is named by the `X-VT-Device` header (letters, digits, `_`, `-`, 4 to 40) that the helper sends; this computer without one is `local-app`; a browser tab is a viewer and cannot register as a director.
  3. `vt server`, `vt servers`, discovery and the install scripts stop printing or advertising a code.
  4. Studio: the "Approve this PC" screen becomes a plain message for the one case left ("this server only accepts computers on its own network"); the Engines page "This server" card loses the code, the new-code button and the paired-devices list and keeps the addresses. `vite.config.ts` removes `Origin` on its proxies, as the app's own proxy does.
  5. App and helper: no key is read, stored or sent for a server on the person's network (the helper still accepts one for a server outside it). The `--code` option and `pairFromCommandLine` go. The connect window says "type the server's address".
  6. Server manager (Windows, GTK) and the server's own page: show the address, no code.
  7. Docs and handoffs say it. M9 and the lab scripts need no pairing.

  **Check:** `tests/test_server_auth.py` rewritten: from a private address no key is needed on every guarded path; from a public address, a forwarded request, or with a foreign `Origin` or a non-local `Host`, the key is needed (Bearer, cookie and query still work); `/mcp` follows the same rule; a `/ws` from a web page is refused; a helper named by header can register as a director and a browser tab cannot. A real test: the built app, a fresh data folder, one address typed, a working Studio and "Claude on this PC" listed with no code anywhere.
  Evidence: Pairing removed. A computer on the server's own network connects with the address alone; outside it, forwarded, or via a web page still needs the key/is refused. test_server_auth.py rewritten (25 tests, 8 breakages caught); real server checked with no key from this PC; real helper and the real app (from source, fresh data folder, address only) both registered Claude on this PC with no code. The packaged installer is H1/M6. See docs/evidence/perfect/M5b-no-pairing.md.

- [x] **M6. Make the app use the helper.** In `main.js`: on start, read `helper-run.json` and start the helper if it does not answer: `spawn(process.execPath, [helperPath], {detached: true, stdio: "ignore", windowsHide: true, env: {...process.env, ELECTRON_RUN_AS_NODE: "1"}}).unref()`. In `attach()`, replace `companion.select` with `POST /servers`. Do not stop it in `before-quit`. Add `--helper` at the very top of `main.js`: start the helper and exit before anything else loads. Expose `helper: {status, start, stop, setAutostart}` in `main-preload.js`, and point `vtDesktop.companion` in `Engines.tsx` and `vtDesktop.director` in `store.ts` at it. Remove the old `director.run` and `onLog` preload entries if nothing handles them. Add the new files to `build.files` and, if Node mode cannot read them from the asar archive, to `asarUnpack`. **Check:** `npm test`, `tests/test_product_split.py`, and a built app where closing the window leaves the helper running and "Claude on this PC" still listed.
  Evidence: The app starts/reuses/replaces the helper and only tells it the server's address; --helper entry, helper IPC and preload, companion removed, package and CI updated. A built app (electron-builder --dir): Node mode runs helper.js from app.asar (no asarUnpack), and after the window closes the helper keeps running and the server still lists Claude on this PC. Also fixed a stop-order race (3 of 6 runs failed before). Idle memory: private 58 MB, working set 83 MB (3 MB over the plan's 80). See docs/evidence/perfect/M6-app-uses-the-helper.md.

- [x] **M7. Start with the computer.** Windows and macOS: `app.setLoginItemSettings({openAtLogin, args: ["--helper"]})`. Linux: a file in `~/.config/autostart/`. On by default at first run. **Check:** a real sign-out and sign-in on this PC if the owner agrees, otherwise the registry entry read back and its command run by hand.
  - 2026-11-08 (Claude): the registry read back showed the helper entry still pointing at an uninstalled copy and the server entry named "electron.app.Electron". Fixed (the client rewrites an on entry that points elsewhere; the server uses its own name and moves the old entry). After reinstalling on E: the registry reads `Ultimate Video Tool Helper: E:/UltimateVideoTool/Client/Ultimate Video Tool.exe --helper` and `Ultimate Video Tool Server: E:/UltimateVideoTool/Server/Ultimate Video Tool Server.exe --background`. The owner declined a sign-out test (2026-11-08); the registry read-back is the check.
  Code: written in `main.js` (M6). Checked so far (2026-11-06): the command the entry runs, `"Ultimate Video Tool.exe" --helper`, on a packaged build: it starts one helper and exits with no window (11.5 s cold, 0.26 s when the helper already runs, same helper kept), and registers nothing. **Waiting for the owner and H1:** the entry itself is written only by an installed build (a scratch build would leave an entry pointing at a temporary folder, and the command checker refused that, rightly). Read the entry back once the real installer has put the new app on this PC, with the owner's agreement. Linux's `.desktop` file is untested (no Linux desktop here).

- [x] **M8. Show it in the app.** In Settings, Directors: "Helper on this PC", running or not, which servers it reaches, Claude and Codex each ready or "Sign in", and a switch "Keep Claude and Codex ready when the app is closed". On the Server page: which computers are connected and which directors each offers. `listing()` notes tell people about the helper, not about opening the app. Where the page runs without the desktop app, say the desktop app is needed. **Check:** screenshots wide and phone, light and dark. (Bangla was part of this check until decision 8, 2026-11-06.)
  Evidence: docs/evidence/perfect/M8-show-the-helper.md: Settings, Directors has the Helper card (running/not, servers with Remove, Claude and Codex ready or Sign in, a keep-ready switch, Check again/Stop; says the app is needed in a plain browser); the Server page lists the computers and what each offers, remembered ones as Not connected. client/studio/e2e/helper_card.mjs 27 passed (all states x wide/phone x light/dark x English/Bangla, none scrolls sideways, phone buttons 44 px; a deliberate break fails exactly one check); tsc and build clean; screenshots in client/studio/e2e/out/helper/ looked at.

- [ ] **M9. Give the test bench the real path.** Add `vt_lab.py helper start|status|stop`. `start` runs `helper.js` with plain Node under `dist/lab/helper`, with its own device name "<this PC> (lab)" (so a director reads "Claude on MSI-LAPTOP (lab)"), and adds the server by its address (no code: M5b). It prints the director id. Tell the owner the Server page now lists this device. **Check:** `/api/directors` lists it, and `make <that id> cartoon lab-helper` runs.
  Progress: `vt_lab.py helper start|status|stop` works and the real server lists `Claude on MSI-LAPTOP (lab)` as ready (docs/evidence/perfect/M9-lab-helper.md); the `make` run is the render-heavy part and waits for the owner's answer about renders (section 0.5). `vt_lab.py direct` is removed.

- [ ] **M10. Prove the whole thing.** With no Claude on the server, the app closed and only the helper running, make a video with Sonnet. **Check:**
  - AI conversations show only Claude on this PC, for understanding, planning, the last look and the title, with no local AI row;
  - the model used is Sonnet, read from the `init` line of the run's log;
  - stopping the helper mid-run gives a fallback with a plain notice;
  - restarting the helper or the server brings the director back by itself.

  Do the same with Codex if it is installed. If not, use a fake and say so.

  Follow-up implementation — Done by codex (2026-11-07). The existing Sonnet run reached the 120-second timeout and fell back to Ollama. The scoped brief is shorter and asks for a submission first. Module calls now appear in conversations and modules that would delegate directing work return guidance before execution. 43 local tests passed. A fresh real Sonnet run is still required. Evidence: docs/evidence/perfect/M10-codex-handoff-check.md.

---

## Phase K: Choosing graphics cards

Owner, 2026-11-05: "v100 is for training. i should be able to select gpu while setup for multi gpu installations or servers."

**What exists.** `vt/gpuassign.py` lets the Server page choose a card per job, but nothing can say "never use this card". "Automatic" picks the freest card among all of them, `render/browser_gpu.py` keeps every other card as a fallback, and setup only asks which card a new engine install should use (`setup_gpu`). Ollama and ComfyUI are only reported. On 2026-11-05 the Server page showed Ollama holding 1.17 GB on the V100 while the local AI was in use.

**Until K3 and K6 are done, make no videos with the local AI,** because they can land on the V100.

- [x] **K1. Add "cards Video Tool may use".** In `gpuassign.py`, add `allowed` to the saved `gpu` settings, a list of card UUIDs. `allowed()` becomes the launcher's pin, if any, combined with that list. Capture the launcher's pin once at import, before K2 sets the variable itself. Add `needs_choice()`: two or more cards and nothing saved. Until it is answered, use only cards with no other program's compute work on them right now, or the single freest card if none is free. Never use all of them by default. `_auto` and every fallback choose only among allowed cards. No allowed card means the processor. `save({"allowed": [...]})` validates, and resets job choices that point at a removed card. `describe()` gives each card `allowed` and what is using it now. **Check:** `tests/test_gpu_choice.py` with fake cards, including a busy card, a removed card and an empty list.
  Evidence: docs/evidence/perfect/K1-allowed-cards.md: gpuassign has an allowed list (never asked / answered / none), a safe default of one card before the answer, needs_choice, validation that resets choices pointing at a removed card, describe() with what uses each card; Server route, vt gpu allow and the MCP tool take it. tests/test_gpu_choice.py 24 pass (69 with the other GPU test files); nine deliberate breakages are each caught.

- [x] **K2. Enforce it everywhere.** At the start of `vt server` and `vt studio`, before any GPU library loads, set `CUDA_VISIBLE_DEVICES` to the allowed UUIDs, so a library someone forgets about still cannot reach another card. Child processes get the new value at once. Anything already loaded needs a restart: the API returns `restart_needed`, and the UI offers a restart. Then read every use and fix what does not follow the choice: `render/browser_gpu.py` (its fallback loop), the NVENC encoder, `stages/asr.py`, `gpu.py::onnx_providers`, `clone_onnx.py`, `comfy/voice.py`, `tts.py`, `sysstats.py` (`usable_by_video_tool`), `engines/setup.py` (`recommended_gpu`), `engines/installers.py`. Search for more: `CUDA_VISIBLE`, `device_index`, `device_id`, `torch.cuda`, `-gpu`. **Check:** tests, and the search results written down with what each one does.
  Evidence: docs/evidence/perfect/K2-the-fence.md: gpuassign.apply() fences the server to the allowed cards at vt server/studio start; restart_needed in the API; blocked() sends render, encode, speech, ONNX and torch models to the processor; the renderer's fallback loop, mux/aroll/shorts encoders, language detector, sound and embedding models, System panel, setup recommendation and the engine starts follow the list; every use is tabled in the evidence. Servers set up before the question keep the card they picked. 100 + 73 + 64 tests pass; 20 deliberate breakages are each caught.

- [x] **K3. Pin the engines Video Tool runs itself.** Placement already has `own`: its own folder, models and port, beside any existing install (`engines/placement.py`). `llm.start_server` already takes `gpu`, `program_dir` and `model_dir`, but `placement.start` passes none of them, so pass them. Add jobs `ai` and `pictures` to `JOBS`, applying to own copies only, and have `ComfyInstaller.start` take its card from them too instead of `setup_gpu`. Changing the job restarts that engine. An existing engine stays untouched and is reported: if it sits on a card that is not allowed, the Server page says so in plain words and offers "Use Video Tool's own copy". **Check:** tests, and the plain wording seen in a screenshot.
  Evidence: docs/evidence/perfect/K3-own-engines.md: jobs ai and pictures; own Ollama/ComfyUI start on their job's card with their own folders; gpuassign.change() is the one save behind the Server page, vt gpu and MCP and restarts only a running copy we started (engines/pids.py checks the command line); engines/where.py + the Server page say in plain words when an existing engine sits on a card that is not allowed and offer Video Tool's own copy. 183 tests pass, 20 deliberate breakages caught, 11 browser checks, screenshots looked at.

- [x] **K4. Ask in setup, in the app.** Build `client/studio/src/components/GpuChoice.tsx` from `GpuAssignment.tsx`. One row per card: name, memory, what is using it now ("python3 is using 9.7 GB"), a switch "Video Tool may use this card". Below that, the job rows. Use it on the Server page, and as a step in `SetupWizard.tsx` shown whenever there are two or more cards. It replaces "Graphics card for a new install" and `setup_gpu`. "Not now" keeps the safe default from K1. While `needs_choice()` is true, the sidebar's Server item shows a small dot, not a banner. **Check:** screenshots with two fake cards, phone included (Bangla was in this check until decision 8); `e2e/_gpu_card.mjs` turned into a real suite.
  Evidence: docs/evidence/perfect/K4-ask-in-the-app.md: GpuChoice.tsx (replaces GpuAssignment): a switch per card with what uses it, the one-card default note with Keep this, jobs only among cards that are on, engines (K3) in English and Bangla; the wizard asks as step 2 with two or more cards (Use these cards / Not now) and has no install-card choice any more; a small dot on the Server item (sidebar and phone tab) while a choice waits. e2e/gpu_card.mjs 39 checks (run 3x), 6 breakages caught, 164 backend tests pass, screenshots looked at (phone, Bangla included).

- [x] **K5. Ask in every other setup.** All of these call `gpuassign.save`:
  - the server manager window (`server/desktop/server-manager.html`, `server-manager-ui.js`, first run in `bootstrap.js`);
  - the Linux one (`server/packaging/engine/server-manager-gtk.py`);
  - the server's own page (`server/vt/server/management.html`);
  - `install-engine.sh --gpus 1,2|all` and the same in `install-engine.ps1`, which ask in a terminal when there are two or more cards and no flag, and otherwise use the safe default and print what they chose and how to change it;
  - Docker (`VT_GPUS` in `docker-compose.yml`, documented in `README-ENGINE.txt`);
  - `vt gpu allow <cards|all>` and `vt server --gpus` in `vt/cli.py`;
  - `gpu_assignment` in `mcp/server.py`.

  **Check:** each one tried, with a fake `nvidia-smi` where the machine has one card, and the docs updated.
  Evidence: docs/evidence/perfect/K5-every-other-setup.md: vt gpu setup (the terminal question) and vt server --gpus; install-engine.sh/.ps1 --gpus/-Gpus and Docker VT_GPUS call it before anything is installed; the server's own pages, the Electron and Linux server windows ask (first run, once). Fake-nvidia-smi tests (found and fixed a 534-call loop in my K2 code), bash and PowerShell really run, 21 + 12 browser checks, 19 breakages caught, 168 Python tests pass. Linux window compiles only (H5 does the real run).

- [x] **K6. Set up the owner's server.** When no job runs:
  1. Check the disk (116 GB was free) and that port 11444 is free. Record the owner's Ollama service state: `systemctl show ollama -p ActiveEnterTimestamp`.
  2. Allow only the RTX 3060: `PUT /api/system/gpu`.
  3. Read `OllamaInstaller` and `llm.ensure_ready` first. As read on 2026-11-05 they never run Ollama's system installer and only write under Video Tool's folder: confirm that before running them. `llm.binary()` may find the system's `ollama` program, which is fine to run with our own settings because that changes nothing of the owner's. Pull `gemma4:latest` into Video Tool's own models folder under `/home/roy/ultimate-video-tool-server`.
  4. In Video Tool's own `run-server.sh`, use `--ollama own`. Update `scripts/lab/deploy_server_code.py` if it needs to know this. Restart only `ultimate-video-tool.service`.

  **Check:** `/api/system/gpus` shows the V100 not allowed and Ollama on the RTX 3060. A gemma video, with `nvidia-smi` sampled every 2 s, shows Video Tool's work only on the RTX 3060. The owner's Ollama service timestamp is unchanged. Write down how long the video took, and tell the owner if gemma no longer fits fully on the card and falls back partly to the processor.
  Progress (2026-11-06): steps 1 to 4 are done and checked on the server (code deployed, only the RTX 3060 allowed, Video Tool's own Ollama on port 11444 pinned to it with its own folders and home, gemma4:latest pulled, the owner's Ollama service unchanged, no restart of the machine): docs/evidence/perfect/K6-the-owners-server.md. Open: the last check, a gemma video with nvidia-smi sampled every 2 s (needs a real video: behind the owner's answer about renders).
  Evidence: docs/evidence/perfect/K6-F9-real-gemma-video.md: a real gemma video through Video Tool's own Ollama in about 2 minutes; only the RTX 3060 used by Video Tool; the V100 had only the owner's training; no server restart.

---

## Phase B: The director's word is final

- [x] **B1. List every place code still overrides a director.** Write `docs/evidence/perfect/B1-overrides.md`, one row each: where, what it does, whether the director hears about it, and what to do. Start with these known ones, then search for more: `guardLayout` in `vt.js` (shrinks, drops `cut-off`, `too-small`, `overlap`); `frameProps` in `vt-stick.js` (hides cut-off props); `_keep_clear_of_people` in `compose/composer.py` (clears all elements); the automatic element exit and `_hand_cards_back` in `composer.py`; `paginate`; `_truncate_overlay`, `_nearest`, camera removal and the "interleaved scenes" fallback in `script/validate.py`; dropped elements in `story/engine_validate.py`. **Check:** you read each one, and the file is complete.
  Evidence: docs/evidence/perfect/B1-overrides.md: 12 rows, each function read: guardLayout, frameProps, _keep_clear_of_people, the element timing and exit, _hand_cards_back, paginate, repair_script (the silent repairs, incl. interleaved scenes becoming one scene per beat), engine_validate and submit_story, fix_scenes (the person's own button), the pipeline fallbacks, the reel path (reports only). Each row says whether the director hears and what step deals with it.

- [x] **B2. Stop hiding what any AI placed (decision 1).** The guard in `vt.js` only touches `.stage .el`, the elements automatic layout arranged. Anything the director positioned itself is already outside it. So first make automatic layout do its job: confirm `shrinkStages` really fits everything by scaling it together, and fix it if its limits leave things overflowing. Then, in `composer.py`, set a flag on each scene dict when `sf.planner` shows an AI directed it. In `guardLayout`, for flagged scenes, change nothing and record in `window.__guard` what it would have done. Make `frame-facts.mjs` read `window.__guard` and report it as a fact, for example "element 2 runs off the frame". Store the last facts after the director's rounds, and list what is left in the Quality check as things to look at. Rule-made plans keep the guard, and its entries appear in Details, Problems. **Check:** tests for all three directors with crowded and overlapping elements: everything stays, the facts report it, and a rule plan behaves as before.
  Evidence: docs/evidence/perfect/B2-guard-and-layout.md: code no longer hides, shrinks or drops what an AI placed (composer marks directed scenes; the page only records what the guard would do; the facts tell the director; what the director leaves is stored and listed in the Quality check; a rule plan keeps the guard and its changes are in Details, Problems). Found and fixed three bugs in the old guard (a dropped element came back when its turn came, a shrink was rewritten by the timeline, stacked groups overflowed together) and added a fit across. tests/test_director_authority.py 50 checks, 17 breakages caught, look_at.mjs 21 checks, reference video unchanged in 3 shapes.

- [x] **B3. Apply the same to `frameProps` and `_keep_clear_of_people`.** A scene any AI directed keeps its elements, and the facts report the problem. **Check:** tests for both, and rule plans behave as before.
  Evidence: docs/evidence/perfect/B3-props-and-people.md: a scene an AI directed keeps its cut prop and the elements over a person, the facts say so; rules plans clear and hide as before. Found and fixed: the guard wiped the stick scenes' own log, so a hidden prop was never recorded. 11 checks (61 in tests/test_director_authority.py), 5 breakages caught.

- [x] **B4. Report repairs.** `repair_script` already reports dropped overlays through `dropped`. Extend this to a `notes` list covering every change: a text cut short, a word id moved, a set or camera value removed, scenes restructured. In `apply_script(strict=True)` (the MCP path), changes of meaning return as errors. Cosmetic ones come back as `repairs`. For the local AI, show them in Details, Problems. **Check:** one test per kind of repair.
  Evidence: docs/evidence/perfect/B4-script-repairs.md: repair_script describes every change it makes (35 kinds, with whether it changed what the director wrote); Claude and Codex over MCP get those as errors and the small ones as repairs, the local AI's script is used as repaired and shows them in Details, Problems. 44 tests, 11 breakages caught.

- [x] **B5. Do the same for Cartoon 2.** `story/service.py::submit_story` returns `warnings[:8]`. On the MCP path, make anything dropped an error with its reason, and make sure `client_story_prompt` tells the director to fix it. Remove the 8-item limit if it can hide problems. **Check:** a test submits an unknown element type and receives the error.
  Evidence: docs/evidence/perfect/B5-story-repairs.md: the story validator describes what it drops or replaces (element type, background, speaker, sound) and what it only moves; Claude and Codex over MCP get the first as errors, every warning comes back (no 8-item cut), the person's own edit and the local AI's story show them in Details, Problems; the prompts say so. 15 tests, 10 breakages caught.

- [x] **B6. Check the reel path.** Read `client_prompt`, `check_reel_plan` and the reel submit path. Apply the same standard. **Check:** a test.
  Evidence: docs/evidence/perfect/B6-reel-path.md: the reel plan is the director's own document and no code changes it; the one silent thing (a director approving with picture checks still open) is now written to Details, Problems and returned; checks only report. 7 tests, 6 breakages caught.

- [x] **B7. Prove it.** Add `tests/test_director_authority.py`: for each style a director can write, a plan with crowded and overlapping elements is composed, and every element it placed is present and visible in `data.json` and in the page, or the director received a message saying why not. **Check:** it passes, and it fails if you restore the old guard behaviour.
  Evidence: docs/evidence/perfect/B7-prove-it.md: tests/test_director_authority.py covers explainer, stick, emoji and cartoon scripts with a crowded scene for each AI director (in data.json and on the real page, nothing changed by the guard); story and reel covered by B5 and B6; 4 of 4 breakages that restore the old behaviour are caught. Found and fixed: set decoration the shot cuts is scenery, left out for every plan.

- [x] **B8. Let the person choose the Claude model (decision 3).** M3 and M4 already carry the model with a default of Sonnet. Add a labelled choice to Settings, Directors ("Sonnet: faster", "Opus: slower, most careful"), save it through `save_settings`, and add the same to the `vt` CLI. Earlier "Sonnet" results came only from a test script passing the flag, so this must be read from the real run. **Check:** with each choice, the `init` line of the run's log shows that model.
  Evidence: Claude implementation; verified by codex: docs/evidence/perfect/B8-claude-model.md and the passing director-model tests (part of the 175-test audit).
  Evidence: docs/evidence/perfect/B8-claude-model.md: Settings and vt directors --model choose Sonnet or Opus; real runs show claude-sonnet-5-5 and claude-opus-5-5 in the init line.

- [ ] **B9. Confirm the last look and the title belong to the director.** After M4, `_autopilot_finish` and `director_review` run through `ClientProvider`. Read both, and add any MCP tool or prompt text they still lack. **Check:** on a real Sonnet video through the helper, Details shows the frame check and the title coming from Claude on this PC, and the title fits the video.

- [x] **B10. Handle "Claude ran out of usage" honestly.** `run()` in `director-runner.js` returns `ok` from the exit code, but a run can exit 0 with `is_error: true` in its final `result` message. This happened on 2026-11-05: a run stopped after 20 s on the 5-hour limit. Parse the final `result` line in `run()` as `ask` already does, and report `error_kind: "limit"`. Then the broker falls back and the person sees a plain line: "Claude's usage limit was reached, so the Local AI directed this video." Make sure no half-made plan is left. **Check:** `test-director-runner.js` feeds both jobs a recorded limit message, and a pipeline test sees the fallback and the notice.
  Evidence: Claude implementation; verified by codex: docs/evidence/perfect/B10-usage-limit.md and the passing usage-limit tests (part of the 175-test audit).
  Evidence: docs/evidence/perfect/B10-usage-limit.md: a failed director hands the video on with one plain line; no half-made plan; 8 tests, mutations caught.

- [x] **B11. Check the same path for Codex.** Confirm Codex receives `frame_facts`, images and the same brief, in both `direct` and `ask`. If Codex is not installed, test with a fake and say so. **Check:** a test.
  Evidence: Claude implementation; verified by codex: docs/evidence/perfect/B11-codex-path.md and passing Codex path tests (part of the 175-test audit); real Codex remains untested.
  Evidence: docs/evidence/perfect/B11-codex-path.md: Codex gets the same brief, frames and facts; found and fixed Claude model sent to Codex. Codex itself not installed: stand-in used.

---

## Phase C: Drawing and rendering

- [x] **C1. Feet, floor and captions in every shape.** The floor fix (`viewBox` in `vt-cartoon.js`; `.cn-scene .cn-actor` in `vt-media.css`) was only checked in 9:16. Make `lab-wide` (16:9) and `lab-square` (1:1) cartoons. Read frames. **Check:** in all three shapes feet stand on the floor, no caption touches a character (`frame_facts`), and the first frame is composed.
  Evidence: feet, floor and captions checked in 16:9 and 1:1 on the server (docs/evidence/perfect/C1-three-shapes.md)

- [x] **C2. Check every set in every shape.** Write `scripts/qa_sets.py`: one composition per set (10 sets) with one character, in each of the 3 shapes, using each camera (`still push pull pan`) and lighting. Produce contact sheets in `dist/lab/`. Look at all of them. Fix gaps at the edges: the set layers are 1000 wide and shift, so widen them (for example `x: -100, width: 1200`). **Check:** no edge, gap or floating floor in any sheet.
  Evidence: scripts/qa_sets.py sheets for 10 sets x 3 shapes x cameras x lights; layers widened; no edge gaps (docs/evidence/perfect/C2-every-set.md)

- [x] **C3. Add the poses and expressions directors keep asking for.** Sonnet asked for `idle`, `run`, `laugh`, `count`, `confused`, and needed a riding pose. Draw real ones in `vt-cartoon.js` (`character`, `animateCharacter`). Add them to `Pose` and `Expression` in `schema.py`. Read `POSES` in `story_kit.py` and map to the new ones. Add a `ride` pose with a bicycle drawn with the character. `cartoon_choices()` in `script/prompt.py` picks them up by itself. **Check:** a contact sheet of every `who` in every pose, viewed; `test_story_kit.py` passes. — Done by codex
  Evidence: docs/evidence/perfect/C3-C4-cartoon-vocabulary.md; 150 production-runtime who/pose combinations, contact sheets viewed, StoryKit/schema tests passed. Count actions preserve the requested 1–5 fingers. Software-only visual fixtures; no real video render.

- [x] **C4. Add more people.** `elder` is an old man, and directors want old women and clearly different adults. Add `old_woman`. Add optional `hair` and `clothes` colour fields to `CastMember`, so two women can look different and one person can stay the same. Keep the current automatic look (from the name) when they are empty. **Check:** a contact sheet, and a test that one named person looks identical across scenes. — Done by codex
  Evidence: docs/evidence/perfect/C3-C4-cartoon-vocabulary.md; old_woman, explicit/automatic colors and cross-scene identity checked in the actual runtime; color controls include Auto reset. Contact sheets viewed; software-only fixture.

- [x] **C5. Make word-by-word motion really move.** `split` in `vt-motion.js` says it wraps words in inline-block spans, but `.mw` has no CSS, so transforms on inline spans do nothing. Confirm with computed styles. Add `.mw { display: inline-block; white-space: pre; }` (and `.mc`), keeping the space inside each word. **Check:** frames in the middle of `blur-slide` and `word-relay-geometry` show the words moving, and quotes still wrap at spaces, in English and Bangla. — Done by codex
  Evidence: docs/evidence/perfect/CODEX-IMPLEMENTATION-2026-11-06.md (C5); targeted regression and software-browser checks passed where applicable. Real processing remains paused.

- [x] **C6. Extend `frame_facts` to every style.** Today it measures `.cn-actor` only. Add stick figures (`g.stk-ch` in `vt-stick.js`; add a `data-name`), Cartoon 2 (read `server/renderer/story/src/StoryScene.tsx` and `figures.tsx`, add `data-name`, rebuild with `build.mjs`), and pictures with faces (use `vt/people.py` and the media `faces` data). **Check:** a test per style, with a sticker placed on a face reported. — Done by codex
  Evidence: docs/evidence/perfect/CODEX-FRAME-DETAILS-2026-11-06.md (C6); focused tests and software-browser checks passed. No real video render.

- [x] **C7. Add more facts.** Report: text smaller than a phone can read (under about 34 px at 1080 wide), low contrast text, text in the platform button zones, and an element still fading at that moment. These are facts for the director only. **Check:** tests, and the director's prompt shows them in Details. — Done by codex
  Evidence: docs/evidence/perfect/CODEX-FRAME-DETAILS-2026-11-06.md (C7); focused tests and software-browser checks passed. No real video render.

- [x] **C8. Make the director's one revision count (gemma).** It was told "element 2 covers 100% of Maya's face" and often did not act. Decision 9 gives it one look and one revision, then the person finishes in the editor (E17), so make that one revision as good as it can be:
  Partial implementation — Done by codex: measured facts lead the one-revision prompt; refused changes name the field and reason; planning and review include bounded real library choices with exact IDs/labels, without starting an embedding model or translation request. Real gemma/video acceptance remains open. Evidence: docs/evidence/perfect/CODEX-FRAME-DETAILS-2026-11-06.md.
  1. Put the facts first in the revision prompt, followed by "for each fact, give one change", and ask only for what the facts name.
  2. Say in the same answer what a refused change was refused for (the reason comes back in the notes of that one revision).
  3. Gemma picks odd pictures (a car for "coin", a rocket for "shop") because it guesses emoji codes. Give it the real choices: in its planning and review prompts, list the top results from `visuals/search.py` for the words in that scene.
  4. After the revision the cut is measured again and what is left is listed for the person (B2: `report["left"]`, the Quality check).

  **Check:** on 3 fresh gemma videos, the facts before and after the revision are on record (Details) and what is left is in the Quality check, and pictures match their words. If face coverage stays high, record the best result and what the limit appears to be: the person fixes the rest. W1 is the owner's choice.
  Evidence: 3 fresh gemma videos: facts before/after on record, left listed, pictures match; remeasure fix after the viewer-test revision (docs/evidence/perfect/C8-one-revision.md)

- [x] **C9. Make preview and export match.** For 3 styles, compare the snapshot and the MP4 at 5 moments each. **Check:** they look the same, and any difference is explained or fixed.
  Evidence: 5 moments x 3 styles compared, mean diff <=1.57/255, compression only (docs/evidence/perfect/C9-preview-vs-export.md)

- [x] **C10. Update the golden images.** Floor, caption and coin changes moved them. For each changed golden, put old and new side by side in `docs/evidence/perfect/goldens/` and look. Update only when the new one is right. **Check:** `test_render_golden.py` and `test_phase2_render.py` pass.
  Evidence: Looked at old beside new (docs/evidence/perfect/goldens/phase2-9x16-a-old-new.png): every picture is identical, only the caption lines are shorter (the intended change). The three phase2 '-a' goldens were refreshed. Server suite 2026-11-07: 1869 passed, 11 failed, of which 9 fixed since (see WORKLOG); the rest are A5.

---

## Phase D: Every kind of video, judged

- [x] **D1. Write the judge.** Add `vt_lab.py judge <project>`. It prints PASS or FAIL per line and exits non-zero on any FAIL:
  - one director in the AI conversations, and no fallback notice;
  - `frame_facts` at frame 0 and the middle of every scene: no face covered above 10%, nothing outside the frame;
  - frame 0 shows a subject, not an empty set;
  - `craft.check`: no critical or major violations;
  - `vt/retention.py` risk at or below 15 ("Strong");
  - `vt/judges.py` passes;
  - `ffmpeg blackdetect=d=0.1:pix_th=0.12` finds no flash;
  - loudness from -16 to -12 LUFS;
  - in a cartoon, one picture at a time: two separate pictures share the frame for no more than 0.4 s (owner, 2026-11-08).

  You must also look at the contact sheet and the first three seconds yourself, and check: the picture matches the words, every number is what was said, one person stays one look, text is readable, and it is worth watching. **Check:** it runs on an existing video and catches a bad one.

  Implementation — Done by codex (2026-11-07). Judge checks and fail exit codes passed local tests. An existing MP4 was decoded against an isolated fixture and its low loudness was correctly flagged. A matching real project, export and composition plus visual review remain open. Evidence: docs/evidence/perfect/D1-codex-lab-judge.md.

  Checked by Claude (2026-11-08) on two real cartoons made by the installed server on the owner's PC (Claude on the server, Sonnet): it runs on a real project, export and composition, and it fails the bad one (pictures piled up, a 0.2 s covered opening). Its false alarms were fixed at the cause (WORKLOG 2026-11-08, later): a figure walking in may cross the edge; captions are read over 2 s, not per chunk; a cartoon's figures count as shown.

- [ ] **D2. For each style, with Sonnet, in 9:16.** For each, with the helper running (M9): `make <Claude director id> <style> <name>`, `export` if it did not render by itself, `judge`, and look. When something is wrong, find the cause and fix it with teaching, ability or facts (0.2), not a rule. Deploy and try again until **3 fresh videos in a row pass**, using different scripts (the Maya story, `EN_SLEEP`, `EN_DATA`). Add one row per run to `docs/evidence/perfect/D-matrix.md`.
  - [ ] cartoon
  - [ ] story (Cartoon 2)
  - [ ] stick
  - [ ] emoji
  - [ ] explainer
  - [ ] infographic
  - [ ] mixed
  - [ ] reel
  - [ ] auto

- [ ] **D3. Each style with gemma** (`make local <style>`), using the G5 bar. Fix crashes, "not valid JSON" answers, fallbacks and covered faces.
  - [ ] cartoon
  - [ ] story
  - [ ] stick
  - [ ] emoji
  - [ ] explainer
  - [ ] infographic
  - [ ] mixed
  - [ ] reel
  - [ ] auto

- [ ] **D4. Each style in 16:9 and 1:1 with Sonnet.** One passing video each. **Check:** rows in the matrix.

- [ ] **D5. Bangla.** Use `BN_SCRIPT` with voice `edge`, `bn-BD-NabanitaNeural` (`--lang bn --engine edge --voice bn-BD-NabanitaNeural`), for each style with Sonnet and with gemma. Look for broken conjuncts, wrong fonts and wrong digits. Also run one Banglish recording. **Check:** rows in the matrix, each viewed.

- [ ] **D6. Every kind of input.** One passing video each:
  - audio with SRT, in each style (words come from the SRT with no speech recognition; Details shows it);
  - `samples/audio/bn_plain.mp3`, `samples/audio/banglish.mp3`, `english sample.mp3`;
  - a talking-head video;
  - a screen recording in "Keep my video" and in "screen + graphics" (no black flashes, no full-screen card over a text-heavy screen);
  - a YouTube link;
  - a typed script with each voice engine that is ready.

  **Check:** rows in the matrix.

- [ ] **D7. Sound.** Check on 5 videos that the music fits, the voice is clear above it, sound effects land on their words, and nothing clips. Bensound's free licence requires a credit: confirm `music_credit` reaches the Export and Share text, and fix it if not. **Check:** measured loudness and the credit text seen in the UI.

  Progress (2026-11-07, Claude): the credit half is done. One credits text (`server/vt/credits.py`) reaches the export file, the publishing description, the agents' `publish.credits` and the Export page (Copy credits); Share pre-fills it. Tests: `tests/test_credits.py`, `e2e/credits.mjs`. Still open: listening on 5 real videos and measured loudness (server). Evidence: docs/evidence/perfect/UI-WIRING-2026-11-07.md.

- [ ] **D8. Fast speech.** Reading-speed warnings appear on normal videos ("captions go by at 4.8 words a second"; ROADMAP P10-05). Find out whether the captions or the warning are wrong, on real fast speech, and fix it. **Check:** a fast Bangla recording and a fast English one read comfortably, with no false warning.
  - 2026-11-08 (Claude): the warning was wrong on normal English narration. It measured each 3-word chunk alone; now it measures 2 s of consecutive captions, with a 20 characters-a-second ceiling. Both real cartoons pass. Left: a fast Bangla recording and a fast English one.

- [ ] **D9. Title, description, cover.** On 5 videos, for each director, check they describe the actual video and that the cover is a good frame. **Check:** viewed.

- [ ] **D10. Everything together.** Rerun all 9 styles once at the end, in one go, with Sonnet. **Check:** all pass, and any drop from the earlier scores is explained.

---

## Phase E: The app

Screens were last audited on 2026-11-05. Use `_audit.mjs` at every step, wide and phone, light and dark. Before finishing any step, read the screenshot, and read `references/pro-rules.md` in the `ui-ux-pro-max` skill.

- [x] **E1. One name per thing (decision 2).** Write the glossary into `docs/GLOSSARY.md`, then rename everywhere: UI text, `i18n.ts`, server messages, `STAGE_DONE`, log lines (`modules/defs/craft.py`), and docs.

  | Use this | For | Replaces |
  |---|---|---|
  | Director | Who plans a video | AI model, AI Provider, Ollama Model, planner, "the editor" when it means the AI |
  | Editor | The timeline page only | |
  | Quality check | The score and the things to look at | Viewer test, Retention check, Craft score, Judges, Editor notes |
  | Things to look at | What a check found | violations, risky moments, problems in UI text |
  | Style | How a video is drawn | Kind of video, Visual style, Drawing style |
  | Look | Colours and type | Theme, Design Studio, the nav item "Styles" |
  | Direct again | Redoing the plan | Redo with AI model |
  | Export / Download | Make the file / save it | Render, Render video |
  | Server | The computer doing the work | "Video Tool server 1", engine server |
  | Helper | The small program on the person's computer that keeps Claude and Codex ready for the server | companion, micro server |
  | Your videos | The list | Projects |

  **Check:** a search for each replaced word finds only the allowed meanings. `client/studio/e2e` suites are updated.
  Evidence: glossary + renames; search clean; settings_clarity 4 modes pass (docs/evidence/perfect/E1-one-name.md)

- [x] **E2. Rebuild the redo dialog.** `components/RedoModal.tsx` asks for "AI Provider" and "Ollama Model", and its style list leaves out Cartoon 2, reel and auto. Replace these with the same Director choice and the same Style choice as the New page (share one component). Models are chosen in Settings. **Check:** a screenshot; `e2e` covers redoing with each director. — Done by codex
  Evidence: docs/evidence/perfect/CODEX-IMPLEMENTATION-2026-11-06.md (E2); targeted regression and software-browser checks passed where applicable. Real processing remains paused.

- [x] **E3. Make Settings, Directors one clear page.** It shows "Who directs your videos" and then a second, overlapping set ("AI services the server can call"), with "Automatic: Not ready" beside a ready Local AI. Keep one list: each director with its plain state and what to do next. Add the model choice (B8) and the helper's state (M8). Hide addresses like `http://localhost:11434` behind a "Server details" disclosure. Align the Preferences row (Theme, Shape, Pace). Reword Help & checks so a non-technical person understands each line. **Check:** a person who has never seen it can answer "who will direct my next video?" from the page; a screenshot. — Done by codex
  Evidence: docs/evidence/perfect/E3-codex-settings.md; actual-page software-browser checks passed in four modes, screenshots viewed. Next ready director is stated above the fallback list; no live assistant/model run or new-person usability study.

- [x] **E4. Calm the result page.** `pages/Result.tsx` stacks many actions and two similar buttons ("Auto-fix suggestions", "Auto-fix and render improved cut"). Order it: the video; Download; a one-line quality summary with a score out of 100 and the things to look at; Direct again, Change the look, Fix a word, Edit everything. One auto-fix button. Remove "risk 47 → 11" and similar internal numbers. Use only one coloured gradient button on a page. **Check:** a screenshot, wide and phone. — Done by codex
  Evidence: docs/evidence/perfect/E4-codex-result.md; actual-page software-browser checks passed in four modes with a synthetic poster and fake APIs, screenshots viewed. No video playback or export claim.

- [x] **E5. Make Details readable.** Replace "Craft score 49 with 12 violation(s)" with plain words (E1). Fix the sheet opening scrolled so its tabs are cut off. In AI conversations, each row says which step and shows the first words of what was asked, and opening it shows the full prompt, answer and images sent. Group a video's rows by step. **Check:** a screenshot; `e2e/log.mjs` is updated. — Done by codex
  Evidence: docs/evidence/perfect/CODEX-FRAME-DETAILS-2026-11-06.md (E5); focused tests and software-browser checks passed. No real video render.

- [x] **E6. Clean up the editor.**
  Implementation — Done by codex: selected button contrast, friendly labels, Advanced JSON, character/pose controls, thumbnail loading/error states and narrow timeline icons. Four-mode software-browser checks, build and 34 timeline tests pass. Full named scratch-server browser suites remain open. Evidence: docs/evidence/perfect/E6-codex-editor.md.
  1. Fix the "Video settings" button, which becomes a blank blue pill when selected: inspect its computed colour.
  2. Show values as words, not raw schema values (`classic`, `girl`, `Who`).
  3. Move the JSON tab behind "Advanced".
  4. Give the character form real controls: position, height of the feet, "Arrives after", and a picture of each pose (`PictureChoices`).
  5. Show scene cards a skeleton while thumbnails load, never a blank box.
  6. On phones, make the timeline's element chips readable, or use icons.

  **Check:** screenshots; `e2e/editor.mjs` and `editor_simple.mjs` pass.
  Evidence: editor.mjs 23/23, simple editor retired (docs/evidence/perfect/E6-E8-suites.md)

- [x] **E7. Tidy the video list.** Three "New video" buttons is too many: remove the toolbar one. Collapse filters on phones. **Check:** a screenshot. — Done by codex
  Evidence: docs/evidence/perfect/CODEX-IMPLEMENTATION-2026-11-06.md (E7); targeted regression and software-browser checks passed where applicable. Real processing remains paused.

- [x] **E8. Polish the New flow.** Show full values on its tiles ("Best available vo…" and "Straight to the e…" are cut off). All 14 choices stay visible, as the owner asked. Use illustrated previews for every choice that has a look. **Check:** a screenshot at 1440 and 400; `e2e/new_flow.mjs` passes.
  Implementation — Done by codex: option values now wrap; full New-flow acceptance stays open. Evidence: docs/evidence/perfect/CODEX-IMPLEMENTATION-2026-11-06.md.
  Evidence: new_flow 21/21, new_tiles 12/12 at 1440 and 400, screenshots viewed (docs/evidence/perfect/E6-E8-suites.md)
  Note (2026-11-07, Claude): Purpose and Listening moved here from a Fine tuning panel nothing opened, so the choices screen has 15 tiles for a typed script and 16 for a recording or link; all stay visible (`e2e/new_tiles.mjs`, `e2e/new_moved_choices.mjs`).

- [x] **E9. Make every page reachable on a phone.** The bottom bar has no way to reach Styles. Add a way, keeping 5 tabs or fewer. Use 44 px touch targets. **Check:** a test at 400 px that opens every page by tapping. — Done by codex
  Evidence: docs/evidence/perfect/CODEX-IMPLEMENTATION-2026-11-06.md (E9); targeted regression and software-browser checks passed where applicable. Real processing remains paused.

- [x] **E10. Remove the Bangla interface (decision 8).** The owner withdrew the plan to finish translating the interface: "remove bengali i18n in ui. It sucks.. No need. Just language in video is fine." Remove the Bangla dictionary, the language switch (sidebar and Settings) and the `ui_language` setting, the Bangla checks of the browser suites and the Bangla screenshots. Keep Bangla as a language for videos, and the fonts that show Bangla text from a video. **Check:** `tests/test_no_bangla_ui.py` passes (no Bangla dictionary, no switch, no interface language, Bangla still offered as a video language), the browser suites pass in English, and the Studio builds.
  Evidence: docs/evidence/perfect/E10-no-bangla-interface.md: withdrawn and done the other way, by the owner's decision 8: the Bangla dictionary, the language switch, the Settings row and the ui_language setting are removed; Bangla stays a language for videos. tests/test_no_bangla_ui.py 4 pass (5 breakages caught), helper_card.mjs 25 and gpu_card.mjs 37 pass, tsc, build and timeline tests ok.

- [x] **E11. Every page has every state.** For each page: loading, empty, error, server unreachable, busy. Force them with Playwright route interception. **Check:** a screenshot of each state; no blank page, raw error or stuck spinner.
  Partial implementation — Done by codex: Result loading/project-error retry and quality-check failure/recovery are tested with intercepted responses. Whole-app state audit stays open. Evidence: docs/evidence/perfect/E4-codex-result.md.
  Evidence: states.mjs 180/180 over 12 pages x 4 states, screenshots viewed (docs/evidence/perfect/E11-E12-states-and-access.md)

- [x] **E12. Accessibility.** Install axe-core in a temp folder and run `AXE=<path>/axe.min.js VT_URL=... node e2e/a11y.mjs`. Add any missing pages to its list. Do a full journey by keyboard only, with visible focus. Honour reduced motion. **Check:** 0 serious or critical problems in all four modes; the keyboard journey is a test.
  Evidence: axe: no serious/critical in 4 modes over 13 screens; keyboard journey 16 checks (docs/evidence/perfect/E11-E12-states-and-access.md)

- [ ] **E13. One visual system.** There are 556 inline `style={{...}}` objects and 123 raw colour values in `styles.css`. Move fixed values to classes and tokens, leaving only truly dynamic ones. Set one type scale, one spacing scale, one radius scale. Replace emoji in UI text with icons. Run the design auditor on each page and fix what it finds. **Check:** counts reported before and after; every page at 90 or above; screenshots unchanged except where they got better.

- [ ] **E14. Performance.** Run `e2e/perf_timeline.mjs` and `quality.mjs`. A heavy timeline was noted as slow: hide elements away from the playhead, and scrub at low resolution. Measure a long video (10 minutes). **Check:** measured numbers; playback and scrubbing stay smooth; a click responds within 100 ms.
  Partial (2026-11-07): short videos are perfectly smooth; a 10-minute video is not yet in a GPU-less production build (scrub median 166 to 100 ms after cutting 35% of the page nodes). The preview composition keeps all scenes laid out: a renderer change plus a measurement on a real graphics card are still needed. Evidence: docs/evidence/perfect/E14-performance.md.

- [x] **E15. Server page wording.** Fix the first line ("(Video Tool server 1)"). Explain plainly what each card is doing and for whom. A card the person chose not to use says so plainly. **Check:** a screenshot. Also offer a **Restart** button for `restart_needed` (K4 only says, in words, that a restart is needed): only where the server can tell how it is supervised (a systemd user unit: `systemctl --user restart <unit named in /proc/self/cgroup>`; the Windows server manager already has its own button; with no supervisor, say so and offer nothing), and refuse while a job runs.
  Implementation — Done by codex: verified supervisor restart with a job fence, unsupported-manager wording, internal server number removed; real/full-page acceptance stays open. Evidence: docs/evidence/perfect/CODEX-IMPLEMENTATION-2026-11-06.md.
  Evidence: server_page 16/16, restart tests 6, job kinds in plain words, setup 10.4s to 2.3s (docs/evidence/perfect/E15-server-page.md)

- [ ] **E16. First run and connection.** Walk through: first open, finding the server or typing its address, choosing graphics cards on a multi-card server, the helper starting, losing the connection, getting it back, an app update. **Check:** a test for each, screenshots viewed.
  Partial implementation (2026-11-07): first open, refused screen, graphics-card choice, helper card, and losing and regaining the connection (new banner, lists reload by themselves) are tested with screenshots viewed. Typing the address in the desktop window and an app update meeting an older server need the real app (H1, H3). Evidence: docs/evidence/perfect/E16-connection.md.

- [x] **E17. Full per-element editing on the canvas and the timeline (decision 9, human in the loop). Do this right after B7.** The person must be able to fix any element by hand, so every element gets the transforms an editor expects, animatable on the timeline. Today an element has position, size, rotation and opacity only (`review/VisualControls.tsx`, `MotionPoint` in `visual_motion.py`).
  Implementation — Done by codex: keyframe diamonds, static media transforms, projective corner-pin inversion and rounded-corner fix; remaining full editor/export acceptance stays open. Evidence: docs/evidence/perfect/CODEX-IMPLEMENTATION-2026-11-06.md.
  1. **Data** (`schema.py` `_El`, `visual_motion.py` `MotionPoint`). Add, all neutral by default so no old plan changes: stretch across and up (`scale_x`, `scale_y`), slant (`skew_x`, `skew_y`), flip (`flip_x`, `flip_y`), pivot (`pivot_x`, `pivot_y`), 3D tilt (`tilt_x`, `tilt_y`), a corner-pin warp (`warp`: four corner offsets), crop (`crop`: top, right, bottom, left, and a corner `radius`), `blur`, `blend`. An element with any of them set is a free element (as with x and y today), so no rule moves it. The numeric ones are also keyframe values.
  2. **Renderer** (`vt.js` free visuals, `vt-keyframes.js`). One function builds the element's look from its fields: `translate`, `rotate`, `scale`, `skew`, perspective `rotateX` and `rotateY`, or `matrix3d` for the warp; the pivot as `transform-origin`; `clip-path` for the crop; `filter: blur()`; `mix-blend-mode`. Keyframes tween them with GSAP. Preview, export and the Studio use this same code.
  3. **Studio.** The inspector's Position section becomes **Transform**, with plain labels (Size, Stretch across, Stretch up, Rotate, Slant, Flip, Tilt, Pivot, Crop, Rounded corners, Blur, Blend) and a number field beside every slider so a value can be typed. A diamond beside each animatable value adds a keyframe at the playhead. On the canvas the selected element has handles: drag to move, corners to resize, a rotate handle, and a **Warp** mode with four corner pins. Double-click resets one value; a button resets all. Undo and redo cover every change. Arrow keys nudge, shift+arrows by ten. 44 px targets on phones.
  4. **Nothing is undone.** Recomposing a plan keeps every new field of an edited element, and a rule never moves, hides or fits an element the person has transformed (test it).

  **Check:** tests for the data (defaults change nothing; each field validates and round-trips), for the page (each field changes the element's box or look as measured on the real page; keyframes move it; a snapshot of preview and export match), and a browser suite that drags, types, animates, undoes and resets on the canvas at wide and phone width, light and dark. Screenshots viewed.
  Evidence: docs/evidence/perfect/E17-fix-it-by-hand.md: every element has stretch, slant, flip, pivot, 3D tilt, corner pin, crop, blur, blend, keyframable, with handles on the picture; 43 python + 9 node + 42 browser checks, 25 breakages caught. Left in BREAKING.md item 24.

---

## Phase F: Reliability

Each step: force the failure, see the message, confirm the person can recover, add a test.

- [x] **F1. The server restarts during a job.** No recovery code exists in `jobs.py` or `app.py`, and jobs live in memory. After a restart, a project must not stay "Processing" forever. Mark it interrupted, with one button to continue from the last finished stage. **Check:** a test, and a real restart on the scratch server.
  Implementation — Done by codex (2026-11-06): durable job state, startup interruption recovery including legacy Processing projects, reconnect reconciliation and Continue using valid stage caches. Evidence: docs/evidence/perfect/F1-restart-recovery.md. Step remains open: real restart on the scratch server is still required; renders stay paused by the owner's answer in this chat.
  Evidence: Real restart on the scratch server (2026-11-06): a job was killed mid-run; on restart the project showed interrupted and the job error 'The server stopped before this job finished. You can continue'; Continue ran the normal pipeline. tests/test_job_recovery.py plus Codex's implementation.
- [x] **F2. Cancel at every stage.** Files stay consistent and the video can run again. **Check:** a test per stage. — Done by codex
  Evidence: docs/evidence/perfect/CODEX-IMPLEMENTATION-2026-11-06.md (F2); targeted regression and software-browser checks passed where applicable. Real processing remains paused.
- [x] **F3. Engines fail.** Ollama down, ComfyUI down, a wrong key, a missing model, and a slow answer (use the fakes in `tests/`, never by stopping the owner's services). **Check:** plain messages, and the video still finishes where it can. — Done by codex
  Evidence: docs/evidence/perfect/F3-codex-engines.md; 48 fake-provider/module tests passed, including saved rule-plan completion, failed clip preservation and timeout/retry. No owner service stopped or exported-video claim.
- [x] **F4. A full disk,** and an upload that stops halfway and resumes. **Check:** tests. — Done by codex
  Evidence: docs/evidence/perfect/CODEX-IMPLEMENTATION-2026-11-06.md (F4); targeted regression and software-browser checks passed where applicable. Real processing remains paused.
- [ ] **F5. Director failures.** The helper is stopped or killed during a run, Claude crashes, the network drops, the computer sleeps and wakes, the wait runs out, the server restarts. **Check:** the director comes back by itself where it can, otherwise a fallback with a plain notice, and no half-plan. Tests use a fake device, plus one real kill of the helper.
- [x] **F6. Many jobs.** Two videos queued, export during thumbnails, a double click. **Check:** nothing is lost or started twice. — Done by codex
  Evidence: docs/evidence/perfect/F6-many-jobs.md; simultaneous reuse/refuse requests reproduced 12 duplicate jobs before the fix and one after it; queued videos, thumbnails, export and cancellation preserve order/results.
- [x] **F7. Bad input.** A corrupt file, silence, 2 hours of audio, a wrong SRT, a script of one word, unusual characters in names. **Check:** tests. — Done by codex
  Evidence: docs/evidence/perfect/F7-codex-input.md; 30 new fake-processor/API cases and existing ingest/cancellation regressions passed (51 selected tests). Real decode/ASR/long-audio performance and video acceptance remain separate paused gates.
- [x] **F8. Security.** Instructions hidden in a transcript or a web page are never followed (ROADMAP Phase 8). Keys never appear in logs, in the AI conversations or in Details. The director's MCP token only reaches its own project's tools. No path escapes the data folder. **Check:** tests.
  Evidence: Security tests pass (62): keys never in logs/conversations/Details; a director token reaches only its own project, and the director endpoint is refused without the token under any path spelling (new); log and picture paths that are links or leave the project are never read or written (new vt/secure_paths.py). Transcript text is data: an AI answer is validated against the schema and never executed.
- [ ] **F9. Prove which card is used.** With the V100 not allowed, sample `nvidia-smi` every 2 s during a real render, a real speech run, a gemma video and a ComfyUI picture. Record each process and its card. The owner's own programs on the V100 are not Video Tool's: tell them apart by process. **Check:** everything Video Tool started or asked ran on an allowed card. Then allow a different set on a fake two-card test and confirm the choice is followed.
- [ ] **F10. Progress is honest.** Each stage moves smoothly and never backward, on a real run and a failed one. **Check:** a test, and a sample of real values.
  Implementation — Done by codex: bounded monotonic progress and stale heartbeat suppression; a real-run sample stays open. Evidence: docs/evidence/perfect/CODEX-IMPLEMENTATION-2026-11-06.md.
- [ ] **F11. Files do not grow without limit:** `ai_talk.jsonl`, snapshots, `exports`, caches. **Check:** a measured long run, with limits added where needed.

---

## Phase G: Features that were built but never proven

Each has an entry in `docs/ROADMAP.md`. Update it when done.

- [ ] **G1. Shorts** (P10-01). A podcast and three long videos through the Shorts page. Add a browser suite. **Check:** clips viewed; ask the owner to agree with 3 of the top 5.
- [ ] **G2. Retakes and tightening on real recordings** (P10-02). **Check:** no cut mid-word; viewed.
- [ ] **G3. Talking head** (P10-04): the speaker is centred in all shapes, and the cold open works. **Check:** frames.
- [ ] **G4. Picture videos.** Run reel on the server's ComfyUI, using only what is installed, with one figure consistent throughout (Q16 stays the owner's). **Check:** viewed.
- [ ] **G5. Moving clips, voices, own voice.** The Comfy paths, each voice engine, and voice cloning with consent. Follow `docs/TEST-PLAN.md`. **Check:** one real result each, listened to or viewed as far as a machine can (speech recognition on the result matches the script).
- [ ] **G6. Editing.** Undo, scene split and merge, fix a word, change the look, layers, media bin, the assistant in the editor. **Check:** browser suites, then one video edited by hand end to end, with export matching the editor.
- [ ] **G7. Plan review and director's script.** Each path from New to the finished video. **Check:** browser suite.
- [ ] **G8. Social.** Everything up to the real post, with mocks. **Needs the owner** for real accounts (W3).
- [ ] **G9. ElevenLabs.** **Needs the owner's key** (W3). Then one real voice per language.

---

## Phase H: Installing

- [x] **H1. Build and open the real app.** Build with `scripts/build_client_windows.sh`. Install with `/S`, only when the app is closed. Open it with `ELECTRON_RUN_AS_NODE` removed from the environment. **Check:** it stays open; a screenshot of the running app.
  Evidence: installed client opens and stays open, screenshot read (docs/evidence/perfect/H1-H3-real-app.md)
- [ ] **H2. A real video through the real app.** Inside the app, choose "Claude on this PC" with Sonnet and make a video. Then close the app and make another one with only the helper running, started from `vt_lab.py`. `vt_lab.py helper` runs the same `helper.js` as the app, so the second video proves the helper alone; the first proves that the app starts it and uses it. **Check:** Details names Claude for every AI step of both, and both pass `judge`.
- [x] **H3. Connecting from nothing.** `--server <url>` on the command line, with a new data folder. **Check:** it connects with no code, and the result is logged.
  Evidence: --server from an empty settings folder connects with no code, logged (docs/evidence/perfect/H1-H3-real-app.md)
- [ ] **H4. Uninstall.** The silent uninstaller leaves program files behind. Test the normal one too. The helper must stop, and its start-with-computer entry must go. **Check:** nothing is left except the person's own data, and it says so.
- [ ] **H5. Server install on Linux from nothing,** in a new folder under `/home/roy/vt-tests` on a port you checked is free, without touching the running server. Use `--no-setup` so nothing large downloads, point its engines only at ComfyUI on 8188 and Video Tool's own Ollama copy on 11444, and set `--gpus` to the RTX 3060. Also try it without `--gpus` in a terminal and confirm it asks. Test the server manager's Applications entry. **Check:** it reaches a working video.
  Partial (2026-11-07): a fresh install reached a working video; the V100 is not allowed (fixed by --gpus 1 in the launcher). Still open: the without --gpus prompt and the Applications entry. Evidence: docs/evidence/perfect/H5-fresh-install.md.
- [x] **H6. Windows server installer:** the icon was not rebuilt. **Check:** the right icon appears.
  Evidence: rebuilt with the icon embedded; icon extracted from program and installer is the current blue one (docs/evidence/perfect/H6-server-icon.md)
- [x] **H7. Versions and packaging.** `test_packaging.py` passes; `scripts/set_version.py` keeps versions consistent. **Check:** the tests.
  Evidence: test_packaging 8 pass; set_version moves four files together and back (docs/evidence/perfect/H7-versions.md)
- [ ] **H8. A clean Windows machine** (ROADMAP P10-08, TEST-PLAN L10). **Needs a VM or second PC:** ask the owner. Also the Mac and code signing (W3).

---

## Phase I: Final acceptance

- [ ] **I1. Ten real videos** (ROADMAP P10-17, `tests/acceptance/corpus.json`). `scripts/run_acceptance.py` starts a local server: first add `--url` and the key, and point it at the GPU server. Use the app's defaults, with the director in charge. **Check:** all pass `judge`; `docs/evidence/perfect/acceptance.md` is written.
- [ ] **I2. Run every gate in section 2,** fresh, in one sitting. **Check:** a table with the result of each, in `docs/evidence/perfect/gates.md`.
- [ ] **I3. Clean up the docs.** `docs/ACTIVE-WORK.md` still says stopped. Bring `docs/ROADMAP.md`, `docs/STATUS.md`, `docs/OPEN-QUESTIONS.md`, `docs/TEST-PLAN.md` and `docs/UI-REVIEW.md` up to date. Put the current state in one short section at the top of each handoff. Stop the scratch server. **Check:** `scripts/check_docs.py`. `docs/UI-REVIEW.md` still describes a Bangla interface (decision 8 removed it): mark those lines as history.
- [ ] **I4. Make the owner's pack.** In `C:\Users\Roy\Videos\Video Tool Lab\final\`: the ten videos, one per style in each shape, their contact sheets, screenshots of every page in light, dark and phone, and a one-page report saying what works, what does not, and what you could not test. **Check:** files open.
- [ ] **I5. Hand over.** Tell the owner where the pack is, list every `[!]` step and every "needs the owner" step, and ask them to watch it. Ask whether to commit. Do not commit before they answer.
