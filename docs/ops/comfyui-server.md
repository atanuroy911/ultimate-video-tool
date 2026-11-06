# The ComfyUI server (192.168.123.47): how it is set up

One Linux machine hosts ComfyUI (video generation), Ollama (text and vision models), Open WebUI (chat), and unrelated containers. This page is how ComfyUI is laid out after the 2026-10-26 rebuild, so it can be repeated, updated and rolled back. No passwords are kept here.

> **Update 2026-11-06:** the service now runs on the RTX 3060. Its drop-in sets `CUDA_VISIBLE_DEVICES=1` with `CUDA_DEVICE_ORDER=PCI_BUS_ID`, and `/system_stats` says "NVIDIA GeForce RTX 3060". The V100 sections below describe how it was set up on 2026-10-26 and are kept for the Volta notes (PyTorch build, no bf16/fp8).

## Hardware that decides everything
| | |
|---|---|
| GPU 0 | Tesla V100 16 GB, compute capability **7.0 (sm_70, Volta)**: ComfyUI uses this one |
| GPU 1 | RTX 3060 12 GB (sm_86): free for Ollama |
| RAM | 47 GB |
| Disks | `/` 452 GB (keep light), `/mnt/bigdata` 818 GB (models, outputs, environments) |

**Why the PyTorch build matters.** PyTorch's CUDA 13 wheels are built for `sm_75` and newer; they have no kernels for a V100. That is the failure seen in video nodes ("no kernel image is available for execution on the device"): plain matrix operations still worked, which hid it. The `cu126` wheels still include `sm_70`. ComfyUI therefore runs from its own virtual environment, not the system Python.

## Layout
```
/mnt/bigdata/video-tool/
  comfy-venv/            Python 3.14 venv: torch 2.12.1+cu126 (sm_50…sm_90 incl. sm_70), torchvision 0.27.1, torchaudio 2.11.0, ComfyUI's requirements
  comfyui/
    models/              all model files (117 GB): checkpoints, diffusion_models, text_encoders, vae, loras …
    input/ output/ temp/ user/   ComfyUI's working folders (user/ has the Manager data and the sqlite db)
    cache/               HF_HOME, TORCH_HOME, XDG_CACHE_HOME for anything ComfyUI downloads
    extra_model_paths.yaml  makes comfyui/models the default place to look and to save
  pip-cache/             wheels, so a rebuild does not download PyTorch again
  backups/               pre-update snapshots (see below)
  logs/                  the setup, cutover and update scripts' logs
/home/roy/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/ComfyUI   the application (a git checkout); only code, custom_nodes
```
The application folder has historically held a redundant `models/` copy on the root drive. The service reads the big-disk directory through `extra_model_paths.yaml`; see the recovery and verification notes below before removing a root copy.

## The service
`/etc/systemd/system/comfyui.service` is unchanged. Three drop-ins override it:
* `override.conf` (existing): `CUDA_VISIBLE_DEVICES=0`
* `10-video-tool.conf` (new): `CUDA_DEVICE_ORDER=PCI_BUS_ID` (so "0" is the V100 in the same order as `nvidia-smi`), cache variables pointing at `/mnt/bigdata`, and an `ExecStart` that runs the venv's python with
  `--extra-model-paths-config …/extra_model_paths.yaml --input-directory … --output-directory … --temp-directory … --user-directory …`
* [`20-bigdata-boot.conf`](../../server/assets/comfy/systemd/20-bigdata-boot.conf): `RequiresMountsFor` makes systemd mount `/mnt/bigdata` before starting ComfyUI; `ConditionPathIsMountPoint` prevents ComfyUI from starting against an unmounted directory. Installed and service-restarted on 2026-10-27; [boot audit](../evidence/2026-10-27/comfy-boot-persistence.md).

To remove only the boot guard, delete `20-bigdata-boot.conf`, then `systemctl daemon-reload` and `systemctl restart comfyui`. Rolling back to the original storage layout also requires removing `10-video-tool.conf`, but would leave the current models on `/mnt/bigdata`; restore the model location before using that older service command.

## Updating (what was done on 2026-10-26, v0.22.0 → v0.42.5)
1. `pip freeze` of the venv saved to `backups/comfy-venv-freeze-before.txt`; note `git rev-parse HEAD` (was `a8d25190`, v0.22.0).
2. Stop the service. `git fetch --tags`, `git checkout -f <newest vX.Y.Z>` (the 799 "modified" files in the old checkout were line endings only).
3. `pip install -c torch-pins.txt -r requirements.txt` and `manager_requirements.txt`. **The pins file is essential**: without it pip may replace the Volta-capable PyTorch with a build that cannot run on this GPU.
   ```
   torch==2.12.1+cu126
   torchvision==0.27.1+cu126
   torchaudio==2.11.0+cu126
   ```
4. Start; wait for `/system_stats`; read `journalctl -u comfyui -b` for `Traceback`/`IMPORT FAILED`. If it does not come up: `git checkout -f a8d25190` and reinstall the freeze file.
5. Check Video Tool's workflows still match the server: Studio → Settings → Video generation shows each engine as Tested / Untested / Not installed.

## Backups kept from 2026-10-26 (`/mnt/bigdata/video-tool/backups/`)
`ollama-systemd-before.tgz` (the Ollama unit and drop-in), `open-webui-data-before.tgz` (1 GB, the chat database), `open-webui.env` (its settings, root-readable), `comfy-venv-freeze-before.txt`, and `ComfyUI-AnimateDiff-Evolved-empty-shell/` (a custom-node folder with no code in it, which made ComfyUI print a traceback on every start). The previous Open WebUI container is kept stopped as `open-webui-old` (`docker rm open-webui-old` once the new one is trusted).

## Known, harmless log lines
* "You need pytorch with cu130 or higher to use optimized CUDA operations": the optimised kernels do not exist for Volta.
* `comfy_kitchen backend ascend` unavailable, `OpenGL_accelerate` not loaded: optional accelerators.

## What a V100 cannot do
No bf16 and no fp8 hardware: fp8 models (Wan, LTX) are stored small and computed in fp16 by ComfyUI, which costs speed, not correctness.

## Also updated on 2026-10-26
* **Ollama** 0.24.0 → 0.40.11 with the official installer (`curl -fsSL https://ollama.com/install.sh | sudo sh`). The installer rewrites `ollama.service` but not `ollama.service.d/override.conf`, where the host, keep-alive, context and GPU settings live. All 14 models kept; `gemma4` answers from the GPU.
* **Open WebUI** (Docker, port 3000) :main image of 2026-05-10 → 2026-10-25 (v0.12.4). The data volume was backed up first; the container was recreated with the same volume, port, `host.docker.internal` mapping and `OLLAMA_BASE_URL`; the old container stays stopped as `open-webui-old` for rollback; the database migrated on first start.
* After the updates every service starts without a traceback: `systemctl --failed` is empty, all containers up.

## Timings on this GPU (3 s vertical clip)
Wan 2.2: ~60 s warm. LTX-2.3: ~126 s warm, ~530 s the first time (29.5 GB to load). The first clip after switching engines pays the load again.

## Model recovery

The 20 large model files (124,563,203,317 bytes) are listed in [`server/assets/comfy/model-manifest.json`](../../server/assets/comfy/model-manifest.json). Each entry records its ComfyUI relative path, exact size, SHA-256 published in the upstream Hugging Face LFS metadata, and a download URL pinned to a repository commit. The matching [`scripts/restore_comfy_models.py`](../../scripts/restore_comfy_models.py) lists, verifies, and downloads files with a resumable `.part` file. It checks the size and hash before replacing a completed download. It will not overwrite an existing mismatched file. The [recovery guide](../../server/assets/comfy/MODEL-RECOVERY.md), manifest, and script are also copied to `/home/roy/video-tool-model-recovery/`, so they remain accessible from the server user's home even if this workspace is unavailable.

```bash
python3 /home/roy/video-tool-model-recovery/restore_comfy_models.py list
python3 /home/roy/video-tool-model-recovery/restore_comfy_models.py verify
python3 /home/roy/video-tool-model-recovery/restore_comfy_models.py download
# for one missing model:
python3 /home/roy/video-tool-model-recovery/restore_comfy_models.py download --only checkpoints/ltx-2.3-22b-distilled-fp8.safetensors
```

The default destination is `/mnt/bigdata/video-tool/comfyui/models`; `--root` selects another models directory. Download needs internet access and enough free space for the selected files. The small `vae_approx` files, placeholder files and config YAMLs are part of the ComfyUI application installation, not this large-weight manifest.

The root-drive copy was approved for deletion by the owner on 2026-10-26. Only files larger than 100 MB under the exact old `ComfyUI/models` path are candidates; the small files and directory tree stay in place. The cleanup result and post-cleanup workflow check are recorded in [model cleanup evidence](../evidence/2026-10-26/comfy-model-cleanup.md).

## Memory after clips
ComfyUI keeps models cached in RAM after a run: after one LTX and one Wan clip it held 39 GB of the 45 GB and the machine ran out of memory (swap nearly full). `POST /free {"unload_models": true, "free_memory": true}` releases it at once (39 GB to 4 GB, V100 11.9 GB to 0.4 GB); nothing needs restarting.
