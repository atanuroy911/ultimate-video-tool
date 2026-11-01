# ComfyUI video generation integration plan

## Status, 2026-10-26 (read this first)

**Built and tested without a GPU (fake ComfyUI server, `tests/test_comfy.py`, 8 tests):** `vt/comfy/` (client, versioned workflows with a manifest, validation against the live server, the whole job: upload, queue, wait, cancel, download, normalise to silent H.264, verify the decode, add to the bin as `source="comfyui"`, `role="b_roll"`, provenance in `comfy_clips.json`, identical requests not rendered twice), `vt/server/comfy_routes.py` (`GET /api/comfy/status`, `POST /api/projects/{pid}/comfy/generate`, `GET /api/projects/{pid}/comfy/clips`; progress and cancel through the ordinary job API), the `comfy_url` setting, Studio: Settings → Video generation (live status, GPU, engines) and a "Generate motion clip" section in the media bin (`e2e/comfy.mjs`, 6 checks against the real server).

**Why LTX failed earlier, and the fix.** The server's PyTorch (`2.12.0+cu130`) has kernels for `sm_75` and newer only; the V100 is `sm_70`. Text encoding worked, then a video node died with "no kernel image". ComfyUI now runs from a venv on `/mnt/bigdata` with `torch 2.12.1+cu126`, which includes `sm_70`. Layout, update procedure, rollback: [../ops/comfyui-server.md](../ops/comfyui-server.md).

**Measured on the V100 (ComfyUI v0.42.5, PyTorch 2.12.1+cu126), through the Studio API, same still and prompt, 3 s vertical (320×512):**
| Engine | First run (loads the weights) | Warm run | Looked at |
|---|---|---|---|
| Wan 2.2 14B, 4-step LoRAs | 422 s (2 s wide, 512×320) | 55–67 s | coherent, soft; subject drifts slightly; smooth camera (`qa_remote_comfy/app_wan22_i2v_final.mp4`) |
| **LTX-2.3 22B distilled fp8** | 527 s | **126 s** | **sharper, more natural light and fabric, subject stable** (`qa_remote_comfy/app_ltx23_i2v.mp4`, `…i2v8.mp4`) |

LTX is the better engine, as expected; Wan is 2× faster and stays as the quick option. Both are marked **verified** and the picker lists tested engines first. Switching engine reloads the other's weights, so the first clip after a switch costs the "first run" time.

**Found while testing, fixed:** (1) the workflow's centre crop cut off a subject standing at the edge of a landscape still: the app now crops the still itself, around the subject, before sending it, and the Studio shows the crop window on the picture so the person can click the subject (the automatic subject finder chose the centre for a small figure next to a big car); (2) Ollama's idle chat model sits on the same V100 (`KEEP_ALIVE` 5 min) and left only 4 GB free: before a clip the app asks that Ollama to unload (`vt/comfy/gpu_share.py`), it reloads on its next question; (3) a run stopped on the server used to read "see the server log": it now says it was stopped.

**Known limits:** clips are 16 fps (Wan) or 25 fps (LTX) and the media bin re-encodes everything to 30 fps, which repeats frames (Wan looks slightly steppy at 3 s); frame interpolation would fix it. Resolution is small (320×512 / 512×320) because the V100 has 16 GB: larger sizes are untested.

## What this feature is for (and what the first test was not)

The first clips (2026-10-26) used a stock QA picture and were placed into an unrelated video: that proved the plumbing (upload, queue, wait, normalise, bin, timeline, render with captions) and nothing editorial.

**The role is now defined in [PLAN-AUDIO-FIRST-DIRECTOR.MD](PLAN-AUDIO-FIRST-DIRECTOR.MD):** the audio is cut first; a director marks impact points and chooses, per slot, the cheapest medium that carries the impact; a generated clip is the most expensive option, a short (2-4 s, variable) **silent** insert in the style the director set, for B-roll between a-roll, atmosphere, or abstract ideas with nothing cheaper to show them. Its audio is never used. Its callable form is the `gen.*` modules of [PLAN-DIRECTOR-MODULES.MD](PLAN-DIRECTOR-MODULES.MD) §4.8. This page keeps only the ComfyUI facts: the server, the workflows, the measured timings, the job and the Studio controls.

**Built:** the tool (a picture becomes silent B-roll: framing, job, bin, timeline, render with captions).
**Not built:** everything that decides *whether, where and what*: see phase 5 of the audio-first plan (prompt from the speaker's words, direct text-to-video versus still-first as a measured experiment, variable-length fit, placeholder-then-replace, the vision check).

## Verified environment, 2026-10-26

- `http://192.168.123.47:8188` responds to `/system_stats`, `/models`, `/object_info`, and `/prompt`; queue was empty when checked. ComfyUI reports version 0.22.0 and one Tesla V100 with 16 GB VRAM. This GPU is on the same host as Ollama, so video generation and model inference can contend for memory.
- Installed local video assets include Wan 2.2 image-to-video high/low-noise 14B FP8 diffusion models, `wan2.2_vae.safetensors`, `umt5_xxl_fp8_e4m3fn_scaled.safetensors`, and an `ltx-2.3-22b-distilled-fp8.safetensors` checkpoint. `Wan22ImageToVideoLatent`, `CreateVideo`, and `SaveVideo` are available nodes. Presence of files and nodes is **not** evidence that a full workflow fits or runs on this GPU. No generation job was submitted in this audit.
- Video Tool already stores and composes video `MediaItem`s and exposes them in the Studio media bin. Generated footage can enter through that path with `source="comfyui"` and `role="b_roll"`; the existing renderer and narration track remain the final assembly path.

## Product behavior

The first feature is **Generate motion clip** for a selected scene or uploaded still. **LTX-2.3 is the preferred engine; Wan 2.2 remains an optional fallback.** The user chooses a source image, enters or edits a visual prompt, sets 9:16 or 16:9, duration preset, engine, and seed, then sees queue/progress, the generated clip, and **Use in scene / Keep in media bin / Regenerate** actions. The clip is silent B-roll; Video Tool keeps the original spoken audio and captions. Generation is an explicit action. In Shorts, original A-roll stays the default, and generated footage is an optional insert reviewed before use.

The director may suggest a prompt from the current beat and media but must keep it grounded in the source. A generated scene should be labeled as generated media in the bin and in project metadata. Regenerating creates a new item and preserves the prior clip until the user deletes it.

## Implementation sequence

1. **Connection and capability discovery.** Add `comfy_url` (default to the verified LAN endpoint only for this installation), connection status, GPU/VRAM, available video nodes, and installed model names to Settings. Implement `vt/comfy/client.py` for `/system_stats`, `/object_info`, `/models`, `/prompt`, `/history/{prompt_id}`, and `/view`. The browser calls only Video Tool's backend; the backend calls ComfyUI.
2. **A versioned workflow contract.** Export one known-good LTX-2.3 workflow in ComfyUI API JSON format and store it under `assets/comfy/workflows/`; start with the installed distilled checkpoint and its matching Gemma encoder. Add Wan 2.2 I2V as a second workflow after a comparison run. Use stable node IDs or a manifest for prompt, image, width, height, frame count, seed, and `SaveVideo` output. At startup/job submission, validate node classes and model filenames against the live server. Start with a short modest-resolution preset; determine the actual frame rate and maximum size by benchmark. Avoid building an unverified graph from guessed node wiring.
3. **Backend job lifecycle.** Add `POST /api/projects/{pid}/comfy/generate`, `GET /api/projects/{pid}/comfy/jobs/{id}`, and cancel. Upload a project image to ComfyUI, patch only approved workflow inputs, submit `/prompt`, track its `prompt_id`, read WebSocket progress when possible and poll `/history/{prompt_id}` for completion. Surface `execution_error`, validation errors, timeout, interruption, and out-of-memory as job failures. Use one concurrent generation per server and deduplicate identical project/scene/prompt/seed/workflow requests.
4. **Import and validation.** Fetch the exact output via `/view`, cap download size, then probe and normalize with FFmpeg to silent H.264 MP4. Validate duration, dimensions, frame count, and full decode before calling `vt.director.media.add_media(...)`. Store prompt, seed, workflow version, ComfyUI prompt ID, source still, model, and timing in a project-side provenance record. Add the resulting `MediaItem` to the normal bin, so existing scene selection, timeline placement, and final render use it without a second video compositor.
5. **Studio controls.** Add Generate motion clip to `studio/src/review/MediaBin.tsx` and a selected-scene action in Review. Show model/preset availability, estimated queue status, prompt, seed, source frame, progress, result preview, and errors. Let the user place the clip into a scene and rerender the project. Add the same optional action to a Short child project after slicing.
6. **Resource scheduling.** Benchmark LTX-2.3 first on the V100, then compare Wan I2V on the same source still, resolution, and clip length. Queue generation behind existing ComfyUI work and account for Ollama's loaded models on the shared GPU. If a workflow cannot reliably fit, expose it as unavailable for that preset or add a smaller verified workflow. The installed 22B LTX checkpoint is larger than the 16 GB VRAM, so offloading and runtime are acceptance criteria, not assumptions.
7. **Storage.** Store ComfyUI models, input, output, temp, user data, and future model caches under `/mnt/bigdata/video-tool/comfyui/`. Keep only the ComfyUI application code and service definition on `/`. Migrate by copying and verifying first, switching paths during a short service stop, testing the API, and only then removing root-drive backups. Ollama's separate model storage is outside this ComfyUI change.

## Acceptance checks

- A project still generates a 3–5 second clip through ComfyUI, returns a nonempty MP4, and shows it in the media bin with correct source and provenance.
- The same clip can be placed in one scene, survives save/reopen, and appears in the final 9:16 render without replacing the narration or captions.
- UI shows queue, progress, retryable failures, and cancel; disconnected ComfyUI and out-of-memory leave the project and existing media intact.
- A real Short with A-roll remains A-roll by default. An optional generated insert appears only where the user places or accepts it, and the finished MP4 passes stream, decode, and representative-frame review.
- Measure render time, peak VRAM, and output quality on this exact V100 before declaring any preset ready; retain LTX and Wan results side by side.

## API references

ComfyUI documents the self-hosted [server routes](https://docs.comfy.org/development/comfyui-server/comms_routes), [workflow API examples](https://docs.comfy.org/development/comfyui-server/api-examples), [LTX-2.3 workflows](https://docs.comfy.org/tutorials/video/ltx/ltx-2-3) and [Wan 2.2 workflows](https://docs.comfy.org/tutorials/video/wan/wan2_2). The API examples submit an API-format workflow to `/prompt`, follow progress via WebSocket, and retrieve results through `/history` and `/view`.

## Next
See phase 5 of [PLAN-AUDIO-FIRST-DIRECTOR.MD](PLAN-AUDIO-FIRST-DIRECTOR.MD). Also open here: frame interpolation for the 30 fps bin, free ComfyUI's model cache after idle time (it held 39 GB of RAM after two clips), larger sizes than 320×512 (untested on 16 GB).
