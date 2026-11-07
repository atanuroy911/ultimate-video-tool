# K6 / F9: a real gemma video, with the cards sampled every 2 s (2026-11-06, after the owner said go ahead)
Server uptime 5:40 before, 5:46 after: no restart. One video (`f9-gemma-1`, director Local AI = gemma4:latest through Video Tool's own Ollama, explainer, English) made and rendered in about 2 minutes (23:43:13 to 23:45:09), 15 AI conversations, status rendered.
Processes seen on the cards (`nvidia-smi --query-compute-apps` every 2 s, `/home/roy/vt-tests/f9-sample.txt`):
- **V100 (GPU-65081c2a): only the owner's `/usr/bin/python3` (training).** Nothing of Video Tool's was ever on it.
- **RTX 3060 (GPU-a1b5ab18), allowed:** Video Tool's own venv python (113 samples), its own Ollama `llama-server` (87), headless Chrome GPU processes and ffmpeg (render); also the owner's ComfyUI and `/opt/conda` python, which are theirs.
- gemma fitted on the 3060 next to the owner's ComfyUI; no out-of-memory.
Not sampled in this run: a ComfyUI picture made by Video Tool, and a separate speech run. The fake two-card tests (tests/test_gpu_*.py) cover following a different allowed set.
