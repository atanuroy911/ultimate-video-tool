# Voices inside ComfyUI: Breeze TTS 2 and OmniVoice (runbook, and the one step still waiting)

Why: the owner wants the pipeline to depend on **ComfyUI and Ollama only** ([plans/PLAN-ENGINES-AND-SETUP.MD](../plans/PLAN-ENGINES-AND-SETUP.MD) section 6, [research/BEST-MODELS.md](../research/BEST-MODELS.md)). Voices become ComfyUI workflows like the pictures and the clips.

**Update 2026-10-28 (evening): the packs are installed and verified; see [evidence/2026-10-28/voices-comfyui.md](../evidence/2026-10-28/voices-comfyui.md).** The section below describes the state before that and the reasons.

## State on 2026-10-28 (before the install)
| Piece | State |
|---|---|
| App side: workflow kind `audio`, `server/vt/comfy/voice.py`, model choice `server/vt/comfy/voicing.py`, the `comfyvoice` voice engine, direction and vocal events (`server/vt/voice_direction.py`), workers (more ComfyUI servers of the same engine) | **done and tested** against a fake ComfyUI ([tests/test_comfy_voice.py](../../tests/test_comfy_voice.py), 6 tests) |
| Workflows `server/assets/comfy/workflows/breeze_design.json`, `breeze_clone.json`, `breeze_direction.json` | written from the node pack's published source (node ids and inputs), **never run on a real server** (`status: unverified`) |
| OmniVoice workflows | **not written**: the pack's node ids are not published in its README; they must be read from `object_info` after install |
| **The node packs on the GPU server** | **not installed. The permission system of the agent session refused to let it clone third-party code into the ComfyUI folder** (class: "untrusted code integration"; the same refusal as for ComfyUI-GGUF on 2026-10-26). It was **not worked around**. A person runs the script below, or allows the agent to |

## The step: run [scripts/install_comfy_voice_nodes.sh](../../scripts/install_comfy_voice_nodes.sh) on the GPU machine as `roy`
It: (1) saves `pip freeze` to `/mnt/bigdata/video-tool/backups/`, (2) clones `saganaki22/ComfyUI-Breeze-TTS-2` and `Saganaki22/ComfyUI-OmniVoice-TTS` into `custom_nodes/`, (3) installs their small requirements **with PyTorch, torchaudio, torchvision, transformers and numpy pinned to the installed versions** (so the V100's `cu126` build is never touched), (4) creates `comfyui-audio.service`, a second ComfyUI on the **RTX 3060** (`CUDA_VISIBLE_DEVICES=1`, port 8189, same models, nodes and folders), (5) restarts the main ComfyUI so it lists the nodes too, (6) waits until both list `BreezeTTS2VoiceDesign`.

Why two ComfyUIs: Breeze loads only in bf16 or fp32; the **V100 (sm_70) has no bf16**, so it would use fp32 (about 13 GB, the whole card). The RTX 3060 (sm_86) runs bf16 in about 7.5 GiB. OmniVoice runs in fp16, so either card works. Both are ComfyUI, so the app sees one engine with **workers**.

Then, in the app: **Settings, Engines, ComfyUI, add the worker** `http://192.168.123.47:8189` (API: `PUT /api/engines/comfy` with `"workers": ["http://192.168.123.47:8189"]`), *Test* (it should list `voice.speak`), and pick the voice engine **Voices on my ComfyUI server**.

## Weights (where they really are)
* The node packs write new downloads into the **app folder** (`ComfyUI/models/breezetts2`, `omnivoice`, on the root drive). They were moved to `/mnt/bigdata/video-tool/comfyui/models/` and left as **symlinks**. After any fresh download run the same move (`scripts/` has none yet; the commands are `rsync -a`, `mv`, `ln -s`).
* Breeze: `drbaph/Breeze-TTS-2-comfyui` (the node downloads the chosen file on first use into `ComfyUI/models/breezetts2/`; the workflows ask for **`bf16 (best quality)`**, 6.49 GiB). Other builds: `int8 hybrid` 4.53 GiB, `int8 (smallest, slower)` 4.22 GiB, `int8 text encoder only` 5.84 GiB; all share the 0.64 GiB audio codec.
* OmniVoice: `k2-fsa/OmniVoice` into `ComfyUI/models/omnivoice/` (about 4 GB fp32, about 2 GB bf16 build).
* Both land under the models folder that `extra_model_paths.yaml` points at (`/mnt/bigdata/video-tool/comfyui/models`). **If `/mnt/bigdata` is gone**, run the workflow once and the nodes download them again (`download_if_missing` is on in the workflows); or pre-fetch with `huggingface-cli download drbaph/Breeze-TTS-2-comfyui Breeze-TTS-2-bf16.safetensors --local-dir <models>/breezetts2`.

## Licences
* Breeze TTS 2 **weights, derivatives and self-hosted outputs are under the BreezeBlue Research and Non-Commercial License; commercial use needs written authorisation from RESONIA, INC.** The node pack's code is Apache-2.0.
* OmniVoice code is Apache-2.0; its weights and tokenizer carry further terms (see [ops/voicestudio-server.md](voicestudio-server.md)).

## Rollback
`sudo systemctl disable --now comfyui-audio`; delete the two folders in `custom_nodes/`; `pip install -r /mnt/bigdata/video-tool/backups/comfy-venv-freeze-before-voice-*.txt --no-deps` if anything in the environment must be put back; `sudo systemctl restart comfyui`.
