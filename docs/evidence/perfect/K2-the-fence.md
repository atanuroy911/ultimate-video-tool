# K2: the allowed cards are a fence

## What changed
- `gpuassign.apply()`: fences the process to the allowed cards by setting `CUDA_VISIBLE_DEVICES` to their uuids, in nvidia-smi's order (which is CUDA's order with `CUDA_DEVICE_ORDER=PCI_BUS_ID`). Programs the server starts inherit it at once. No allowed card gives `-1` (every card hidden). If nvidia-smi does not answer, the person's saved list is used as it is; with no answer saved and no way to look, nothing changes. `vt server` and `vt studio` call it first (`cli._fence()`, before the engines are placed) and print `Graphics cards Video Tool may use: 1 NVIDIA GeForce RTX 3060` (and, when nobody has chosen, say how to).
- `gpuassign.restart_needed()` (and `describe()["restart_needed"]`): true when the person changed the list after the server fenced itself. False while nobody has answered (the default is not an answer) and for a process that never fenced itself. The Server page's restart offer is K4's.
- `gpuassign.blocked()`: there are NVIDIA cards and Video Tool may use none. Everything below treats it as "the processor does the work". No NVIDIA card at all is not blocked.
- `gpuassign.uuid_for(n)` and `child_env(n)`: a program of ours started "on card n" can only reach a card that is allowed; any other number leaves it the fence it inherits.
- **Servers set up before the question existed:** a card the person already picked (the primary card, or one for a job) counts as their answer until they give one, instead of the one-card default. Found while planning the deploy: the owner's server has `primary = the RTX 3060` saved and no list; without this, an update could have moved Video Tool to whichever card looked emptier, the V100 included.
- `tests/conftest.py`: every test sees a computer with no NVIDIA card unless it gives its own cards, so no test depends on the machine it runs on (and none asks nvidia-smi again and again).

## Every use of a card, read and fixed (the search was `CUDA_VISIBLE`, `device_index`, `device_id`, `torch.cuda`, `-gpu`, `nvenc`, `cuda`, `onnx_providers`, `nvidia-smi`, `setup_gpu`, `use-angle`, `use-vulkan` over `server/vt`, then over the whole repository)
| Where | What it does | Now |
|---|---|---|
| `render/browser_gpu.py` `nvidia_render_device()` | tries each NVIDIA card with a 1-frame NVENC encode, the chosen render card first, the rest as fallbacks | only allowed cards are listed, so no fallback can reach another; if the list cannot be read it uses none and says so in the log |
| `render/browser_gpu.py` `browser_environment()`, `render/chrome_gpu_launcher.py` | pins the render subprocess to the chosen card (`CUDA_VISIBLE_DEVICES`, `ANGLE_PREFERRED_DEVICE`) and makes Chrome use Vulkan | unchanged: the card it is given now comes only from the allowed list |
| `render/hyperframes.py` `render_silent`, `snapshot` | `--gpu --browser-gpu` hardware mode | software mode when no card is allowed; the acceleration report says why |
| `render/mux.py` `mix_and_mux` | `h264_nvenc` when shrinking the video | CPU encoder when no card is allowed; `-gpu N` names the render card among the cards the process sees |
| `aroll.py`, `shorts/splitter.py` | `h264_nvenc` through `gpu.has_nvenc()` | `has_nvenc()` is false when no card is allowed; `-gpu N` added |
| `gpu.py` | `onnx_providers` (cutout, voice models), `has_nvenc`, diagnostics | no CUDA provider when blocked; its `device_id` is the speech card counted among the visible cards; new `usable()`, `nvenc_device()`, `torch_device()` |
| `cutout.py`, `clone_onnx.py` | ONNX sessions through `gpu.onnx_providers()` | follow it |
| `stages/asr.py`, `langdetect.py` | Whisper on CUDA, `device_index` | `cuda_available()` false when blocked; the language detector now names the speech card too (it used device 0) |
| `sounds.py`, `visuals/embed.py` | PyTorch models, `device=0` / `"cuda"` | `gpu.torch_device()`: `cuda:N` on the speech card, or `cpu` |
| `tts.py` | the 8-bit voice runs on the CPU on purpose | no change |
| `sysstats.py` `_visible()` | the System panel's "usable by Video Tool" | the allowed list (it read the environment variable) |
| `engines/setup.py` `recommended_gpu` | the newest card for a new install | the newest allowed card |
| `engines/installers.py` `ComfyInstaller.start`, `llm.py` `start_server` | started a program of ours with `CUDA_VISIBLE_DEVICES=<number>` | `child_env`: only an allowed card; K3 gives these their own jobs |
| `engines/discover.py`, `engines/hardware.py`, `gpu_detect.py`, `llm.py` (memory query), `doctor.py` | read what exists (names, memory, another program's environment) | read-only, no change |
| `comfy/voice.py`, ComfyUI, Ollama, VoiceStudio | separate programs reached over HTTP | not ours to fence: K3 reports where they run and offers Video Tool's own copy |
| `scripts/lab/deploy_server_code.py` | removes the launcher's `export CUDA_VISIBLE_DEVICES=` from `run-server.sh`, so the launcher fence is not in use on the owner's server | no change: the server now fences itself |
| `scripts/lab/vt_lab.py` (tests, scratch server, remote runs) | starts them with `CUDA_VISIBLE_DEVICES=1` | no change: that is the launcher's fence, and it stays first |
| Found in `docs/ops/comfyui-server.md` | said the owner's own ComfyUI service sets `CUDA_VISIBLE_DEVICES=0`, the V100 | **Corrected on 2026-11-06 (K6): the service runs on the RTX 3060 now (`CUDA_VISIBLE_DEVICES=1`); that document was out of date.** Not touched either way. |

## Checks (local, fake cards, fake programs, 2026-11-06)
- `tests/test_gpu_fence.py` (new, 24), `tests/test_gpu_choice.py` (25), `tests/test_gpuassign.py` (9), `tests/test_render_acceleration.py` (5, three of them now give the cards they assume), `test_gpu`, `test_engine_fit`, `test_engine_placement`, `test_gpu_detect`: **100 passed**. `test_imports`, `test_one_director`, `test_server_auth`, `test_client_server_flow`, `test_paths_dist`, `test_cli_modules`: 73 passed. `test_setup`, `test_music_mix`, `test_aroll`, `test_auto_language`, `test_shorts`, `test_hub`, `test_engine_placement`, `test_hyperframes_check`: 64 passed.
- **20 deliberate breakages, each caught by a test:** `apply()` writes nothing; no card gives `""` not `-1`; a restart is never asked for; `blocked()` is never true; `child_env` gives any card; the renderer tries every card; render ignores a closed list; snapshot ignores it; the mix ignores it; the mix does not name the card; `has_nvenc` ignores it; ONNX ignores it; torch ignores it; speech recognition ignores it; the System panel reads the old variable; setup recommends any card; the picture engine and the language model take any number; the start does not fence; and (migration) a picked card is not honoured.
- The renderer test records every card the encoder probe touches: with only the 3060 allowed it probes the 3060 alone (the V100 is never tried as a fallback), with both allowed it tries both, with none it tries nothing.

## Not done here
- No fake run against a real card: tests use fake cards. K6 does the real check on the owner's server (`nvidia-smi` sampled during a real render).
- The Server page's "restart needed" offer and the setup question are K4. There is no restart endpoint (the server manager restarts it from outside); K4 decides the wording.
- Nothing is deployed to the owner's server yet. Deploying before K6 is safe because of the migration rule above.
- I ran `tests/test_gpu.py` on this PC by accident in one of the groups (a tiny CUDA multiplication on the RTX 4050, a few seconds). From now on local runs leave it out.
