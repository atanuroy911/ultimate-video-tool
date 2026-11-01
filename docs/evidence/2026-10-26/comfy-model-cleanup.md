# ComfyUI model cleanup and recovery

Owner approved removal of the redundant root-drive model weights on 2026-10-26, after requesting a reusable download list/script and a check of other saved workflows.

## Before cleanup

- Active service: ComfyUI 0.42.5, PyTorch 2.12.1+cu126, V100 `sm_70` through `/mnt/bigdata/video-tool/comfy-venv/bin/python`.
- Service arguments route models, input, output, temp and user storage to `/mnt/bigdata/video-tool/comfyui`; cache variables point there too.
- Big-disk inventory: 20 model weights over 100 MB, totaling 124,563,203,317 bytes. The old application `models/` directory was about 117 GiB. The earlier read-only rsync comparison found the weight files matched by name, size and timestamp; differences were small configs and changing logs/cache.
- [`assets/comfy/model-manifest.json`](../../../assets/comfy/model-manifest.json) maps all 20 weights to pinned upstream URLs and published SHA-256 values. [`scripts/restore_comfy_models.py`](../../../scripts/restore_comfy_models.py) was tested and copied with the manifest to `/home/roy/video-tool-model-recovery/`.
- Fresh LTX 2.3 and Wan 2.2 jobs succeeded before cleanup ([earlier evidence](module-and-comfy-followup.md)).

## Saved workflows found on the server

Eleven workflow JSONs were found in the active big-disk `user/default/workflows` directory. The Video Tool LTX/Wan API workflows also pass live node/model validation. The [per-workflow audit](saved-workflow-audit.json) records each node and model gap. A summary:

| Saved workflow family | Files | Dependency check |
|---|---:|---|
| Z-Image starter and GSL starter | 2 | required models and execution nodes installed |
| Wan 2.2 image-to-video | 1 | required models and execution nodes installed |
| ACE Step 1.5 text-to-audio | 1 | required models and execution nodes installed |
| LTX 2.3 first/last, image+audio, ID LoRA, text-to-video | 4 | required models and execution nodes installed; `Reroute` is a UI helper node |
| LTX 2 image-to-video | 1 | missing LTX 2 checkpoint and two LoRAs; this predates the storage cleanup |
| Wan 2.1 base and GGUF | 2 | missing several models and custom-node packages; this predates the storage cleanup |

Dependency presence is not a full render test. The last three legacy graphs were already incomplete while the root copy was present; deleting duplicate weights cannot supply their missing dependencies.

## Verification and cleanup result

- The server-side restore script verified all 20 big-disk files against the manifest's upstream SHA-256 values; exit code 0.
- A dry run of the exact-path cleanup passed. The active ComfyUI command and version were checked, and its old root directory contained precisely the 20 manifest-listed files over 100 MB.
- The approved cleanup removed those 20 files from `/home/roy/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/ComfyUI/models`, leaving small files and directories. Root free space grew from 53,085,773,824 to 177,649,098,752 bytes, a gain of 124,563,324,928 bytes. The [machine-readable cleanup report](root-model-cleanup.json) is copied from `/mnt/bigdata/video-tool/logs/root-model-cleanup-2026-10-26.json`.
- ComfyUI remained active at v0.42.5 with PyTorch 2.12.1+cu126. Its live `object_info` still offered the LTX, Z-Image and ACE Step model filenames, and Video Tool's LTX 2.3 and Wan 2.2 workflow validation found no missing node or model.
- Post-cleanup Z-Image starter test: a reduced 512×512 form of the saved graph generated `smoke_zimage_e0cd496e.png` (prompt `e0cd496e-8701-4247-831a-1ef8a7287c4c`). The downloaded image was inspected and shows the requested blue cup on a wooden table. The model, Qwen encoder and VAE all loaded from the big-disk model path after deletion.
- Post-cleanup ACE Step 1.5 test: an 8-second form of the saved text-to-audio graph completed successfully (prompt `4bb0a4b5-f1f4-4253-a9de-f265b24a78e3`). Its MP3 downloaded, decodes as 48 kHz stereo audio, and measures -32.1 dB mean and -9.7 dB peak rather than silence. This is a technical playback check, not a listening-quality review.
- Post-cleanup Wan 2.2 test: prompt `c2cf064b-294a-4805-bf8c-62d86568fb77` completed using the big-disk weights. Downloaded H.264 MP4, 512×320, 33 frames at 16 fps, 2.0625 s. A middle frame was inspected: the astronaut and car remain intact.
- Post-cleanup exact Video Tool LTX 2.3 workflow asset: prompt `7e15d8b0-5984-42af-ad69-040c2893911b` completed with no graph validation errors. Downloaded H.264 MP4, 512×320, 49 frames at 25 fps, 1.96 s. Five frames were inspected: astronaut and car stay recognizable throughout. The raw ComfyUI file carries an AAC audio stream; Video Tool's normalisation removes that stream before generated B-roll is placed under source speech.

**Result:** the active big-disk setup survived removal of the redundant root weights. Video Tool's LTX and Wan engines ran, and saved Z-Image and ACE Step workflows also produced outputs. Three older saved workflows remain incomplete because of dependencies that were never present in either model directory; see the per-workflow audit.
