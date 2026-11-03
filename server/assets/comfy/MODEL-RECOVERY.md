# ComfyUI model recovery

This directory is also copied to `/home/roy/video-tool-model-recovery` on the GPU server. It covers the **20 large model files that were removed from the old root-drive ComfyUI directory on 2026-10-26**. The working copies are in `/mnt/bigdata/video-tool/comfyui/models`. All 20 working copies matched the SHA-256 values in `model-manifest.json` before cleanup.

Run these from any directory on the GPU server:

```bash
python3 /home/roy/video-tool-model-recovery/restore_comfy_models.py list
python3 /home/roy/video-tool-model-recovery/restore_comfy_models.py verify
python3 /home/roy/video-tool-model-recovery/restore_comfy_models.py download
```

`verify` checks every file by SHA-256 and exits nonzero if one is missing or different. `download` fetches missing files from pinned Hugging Face commit URLs, resumes a `.part` file after an interrupted transfer, verifies size and SHA-256, then moves it into place. It keeps an existing mismatched file for inspection. To fetch just one file, add `--only` with its path from `list`. To restore to another location, add `--root /absolute/path/to/models`. The full set needs about **125 GB** plus space for incomplete downloads. No password is stored in these files.

After restoring files, check ComfyUI at `http://192.168.123.47:8188/system_stats` and in Video Tool Settings → Video generation. The live service must use the V100-capable `/mnt/bigdata/video-tool/comfy-venv/bin/python` and `extra_model_paths.yaml`; the system Python's `cu130` build cannot run on this V100.

The 20 files come from pinned revisions of [Lightricks LTX 2.3](https://huggingface.co/Lightricks/LTX-2.3), [Comfy-Org LTX 2/2.3](https://huggingface.co/Comfy-Org/ltx-2.3), [Comfy-Org Wan 2.2](https://huggingface.co/Comfy-Org/Wan-2.2), [Comfy-Org ACE Step 1.5](https://huggingface.co/Comfy-Org/ACE-Step-1.5), and [Comfy-Org Z-Image Turbo](https://huggingface.co/Comfy-Org/Z-Image-Turbo). Exact per-file URLs and hashes are in the JSON manifest.

The older saved LTX 2 and Wan 2.1 workflows need **additional** models and, for Wan 2.1, custom nodes. Those files were never present in the redundant root copy and are outside this recovery bundle. The current LTX 2.3, Wan 2.2, Z-Image and ACE Step models are included.
