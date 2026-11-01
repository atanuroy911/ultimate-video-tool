# GPU server re-check after the restart, 2026-10-27 22:11 onward

The owner restarted the machine after [the probe](gpu-server-probe.md) found it unhealthy. The root drive now appears as `/dev/sdd2` (it was `sda2`), 61 % used, so the disks were renumbered; `/usr/share/ollama` is readable and `uptime` read 2 minutes.

| Check | Result |
|---|---|
| Ollama `GET /api/tags` | 14 models listed (gemma4, qwen3.6:27b, qwen2.5vl 3b and 7b, llama3, and others) |
| Open WebUI `:3000` | HTTP 200 |
| SSH | works again |
| ComfyUI nodes | 1,049 (was 974); `CLIPLoader`, `LoraLoaderModelOnly`, `CheckpointLoaderSimple` are back |
| **Wan 2.2 clip through the Studio** (`POST /api/projects/reference/comfy/generate`, `tests/fixtures/face.jpg`, "the person blinks and slowly turns their head, soft light", 9:16, 3 s) | **done**, about 7 minutes on the first run after the restart (models load from disk). The clip is 320x512 H.264, 49 generated frames at 16 fps. Three frames looked at: [shots/wan-face-clip.png](shots/wan-face-clip.png). The person is the same person in all three, the head turns to the right and the expression changes; no artefacts seen. |
| **Real-model script eval**: `VT_EVAL_MODEL=1 pytest tests/script_eval -k real_model`, log [ollama-script-eval.log](ollama-script-eval.log) | **fails its own bar**: the AI beat the rules on 5 of 10 sets, the test demands 6. Nothing failed to run and the AI's `valid`, `coverage` and `number_fidelity` were 1.00 on every set. The 5 non-wins are 4 ties and 1 loss (`product-bike`, `fit` 0.50 against 1.00). It won clearly on `variety` in `edu-gravity` (1.00 against 0.58) and on `fit` in `story-wallet` and `bn-yield` (1.00 against 0.00). Run twice with the same 5 of 10. |
| **LTX 2.3 clip through the Studio** (same photo, "the person smiles and nods slightly, gentle camera push-in, soft light", 9:16, 3 s) | **done**, about 8 minutes. 320x512, 73 frames at 25 fps (2.9 s). Three frames looked at: [shots/ltx-face-clip.png](shots/ltx-face-clip.png). Same person, a smile appears and the camera pushes in as asked; sharper than the Wan clip. |
