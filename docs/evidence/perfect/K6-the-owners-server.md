# K6: the owner's server (set up; the last check waits)

Done on 2026-11-06, 12:47 to 13:10 (+06), with `scripts/lab/server_cards.py` and `scripts/lab/deploy_server_code.py`. No job was running at any point. The server's uptime was read before and after: **up since 2026-11-05 21:33:11 the whole time, no restart of the machine.**

## Before
- Disk: 117 GB free. Port 11444 free. The owner's Ollama service (`ollama`, user `ollama`, port 11434): active since Thu 2026-11-05 21:33:24 +06.
- Cards: the V100 held 9 MiB (nothing; the owner's training was not running), the RTX 3060 held 289 MiB (the owner's ComfyUI python, 104 MiB, and VoiceStudio's python3, 104 MiB).
- **The owner's ComfyUI runs on the RTX 3060**, not the V100 as `docs/ops/comfyui-server.md` and my earlier notes said: its drop-in sets `CUDA_VISIBLE_DEVICES=1` with `CUDA_DEVICE_ORDER=PCI_BUS_ID`, `/system_stats` says RTX 3060, the process environment says the same. The document and the notes are corrected (see WORKLOG).
- Video Tool's settings had `gpu.primary` = the RTX 3060 and no list of allowed cards; it used `--ollama existing --ollama-url http://127.0.0.1:11434`.

## What was done (only Video Tool's own folder and own user service)
1. **Deployed the code** (`deploy_server_code.py`; it restarts only `ultimate-video-tool.service`). The server answered the new way at once: the V100 not allowed, the RTX 3060 allowed. That was the rule for servers set up before the question existed (a card already picked counts as the answer): without it this update could have moved Video Tool to whichever card looked emptier.
2. **Saved the answer** through the API (`PUT /api/system/gpu`, the Server page's switches): only the RTX 3060. All four jobs (render, speech, ai, pictures) resolve to it. `needs_choice` false, `restart_needed` false.
3. **Video Tool's own Ollama.** `run-server.sh` (a copy is kept next to it as `run-server.sh.before-own-ollama`) now has `/usr/local/bin` on its PATH (so the system's `ollama` program can be found; it is only run, with our own settings) and `--ollama own`. After the restart the server started its own Ollama:
   - port **11444**, `OLLAMA_MODELS=/home/roy/ultimate-video-tool-server/data/models/ollama`, its key and history in `HOME=/home/roy/ultimate-video-tool-server/data/engines/ollama-home` (so nothing is written to `/home/roy/.ollama`; found and added while doing this: `llm.start_server` now gives an own copy its own home folder on Linux and macOS),
   - **`CUDA_VISIBLE_DEVICES=GPU-a1b5ab18-…` = the RTX 3060** (read from the running process).
4. **Pulled `gemma4:latest`** (9.6 GB) into that folder: about 2 minutes. Disk free 117 to 111 GB.

## Checks done
- `/api/system/gpus`: V100 "not used", RTX 3060 "MAY be used"; jobs all on the RTX 3060; engines: "Video Tool's own Ollama is not holding a card right now. It starts on the card chosen for it." and "ComfyUI was already running on this computer, on NVIDIA GeForce RTX 3060 (0.1 GB). Video Tool leaves it as it is."
- **The owner's Ollama service is unchanged**: still `ActiveEnterTimestamp=Thu 2026-11-05 21:33:24 +06`, still on 11434. Nothing under `/mnt/bigdata`, nothing in `/home/roy/.ollama`, the owner's ComfyUI untouched.
- Machine uptime unchanged (no restart); the V100 stayed at 5 to 9 MiB throughout.

## Not done (parked in `BREAKING.md`)
- **The last check of the step:** "a gemma video, with nvidia-smi sampled every 2 s, shows Video Tool's work only on the RTX 3060", how long it took, and whether gemma (9.6 GB) fits fully on the 12 GB card next to the owner's ComfyUI and VoiceStudio, or falls back partly to the processor. It needs a real video, which is behind the owner's answer about renders (`A3-server-restarts.md`).
- Until that is checked, Video Tool's local AI is set up but has not answered a question since the switch. `vt_lab.py make local ...` is the first test, one video, with `uptime` before and after.
