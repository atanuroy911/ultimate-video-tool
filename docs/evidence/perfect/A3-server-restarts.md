# The GPU server stopped hard twice on 2026-11-05, both times during my full test runs

Written 2026-11-05 21:40 while doing plan step A3 (the baseline test run). Facts first, then what is not known.

## What was seen
- `vt_lab.py tests` (the whole suite, on the RTX 3060 with `CUDA_VISIBLE_DEVICES=1`) started at about 21:20.
- From 21:25 this PC lost 50-66% of pings to the server and SSH timed out. The test output file stopped changing at 21:25 (43% done, one failure so far).
- The server's `uptime` at 21:33 said "up 0 min": it had restarted at 21:33:11. The previous boot's journal ends at 21:24:48 with no shutdown messages, no kernel panic, no out-of-memory line and no NVIDIA error. A machine that is stuck cannot write such lines, so their absence does not clear anything.
- The boot before that (2026-11-03 00:06 to 2026-11-05 16:59:55) also ended with no shutdown messages. It stopped at 16:59:55 and the next boot began at 17:11:45. My earlier full test run was in progress then.
- In that earlier boot's kernel log, at 09:20:17 on 2026-11-05: `NVRM: Xid (PCI:0000:26:00): 32 ... name=chrome-headless` twice. 26:00 is the RTX 3060. Xid 32 means a corrupted GPU command stream. That machine did not stop then.
- During the 21:20 run, the journal shows one headless Chrome started every few seconds (systemd scopes `app-org.chromium.Chromium-*`), rising from 2 to 24 a minute between 21:20 and 21:24. These are the render tests. They use the renderer's GPU mode (`render/browser_gpu.py` adds `--use-angle=vulkan --use-vulkan=native`).
- After the restart at 21:33 everything came back by itself: ComfyUI (8188), Ollama (11434), Video Tool's server (8790, health ok) and the owner's `train.py` on the V100 (it was 76 seconds old at 21:35, so something starts it at boot). Before the stop, the V100 showed 90% load from that training at 21:18.

## What is not known
- Whether my tests caused either stop. Nothing in the logs says so. Two stops during two of my full runs in one day is too much of a coincidence to ignore.
- Whether a person restarted the machine afterwards (the gaps were 12 and 8 minutes) or a watchdog did.
- Whether the training resumes from a saved checkpoint after such a restart.

## What I did to the server
Only the deploy at 21:18 (code into `/home/roy/ultimate-video-tool-server/app`, restart of `ultimate-video-tool.service`) and the test run in `/home/roy/vt-tests`. Nothing else.

## Decision
No more full-suite or render-heavy runs on the server until the owner has read this and answered (see the trap in PLAN-PERFECT.MD section 0.5). Light work (reading, deploying code, single small test files that do not render) continues.
