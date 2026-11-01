# VoiceStudio install and first checks (2026-10-28)

What was done on `192.168.123.47`, in order. Runbook: [ops/voicestudio-server.md](../../ops/voicestudio-server.md). Nothing secret is recorded here.

| Step | Result |
|---|---|
| Looked at the machine (read-only) | Docker 29.1.3 present, **no NVIDIA container toolkit**, Python 3.14 (too new for the app), `cloudflared` running as a service with a local config of 7 hostnames, `roy` in the `docker` group, GPUs: V100 16 GB (12.9 GB busy with ComfyUI), RTX 3060 12 GB (idle), root drive 61 % used, big drive 81 % |
| `docker pull ghcr.io/debpalash/voicestudio:stable` | 17.3 GB image, layers on the root drive |
| `run.sh` (versioned in `assets/voicestudio/run.sh`) | container `omnivoice` on the **RTX 3060** by device passthrough; data on `/mnt/bigdata/video-tool/voicestudio/data`; healthy 25 s later; migrations ran; MCP mounted at `/mcp` |
| GPU inside the container | `torch.cuda.is_available() == True`, `NVIDIA GeForce RTX 3060`, `torch 2.8.0+cu128` |
| REST description | 306 paths, saved as [voicestudio-openapi.json](voicestudio-openapi.json); the model catalogue (38 models with licence categories) as [voicestudio-models.json](voicestudio-models.json) |
| First speech request (`POST /v1/audio/speech`) | **HTTP 403 `model_licence_required`**: the default model `k2-fsa/OmniVoice` is non-commercial (`CC-BY-NC`, Higgs Audio 2, Meta Llama 3 terms) and VoiceStudio will not use it until a person accepts its licence. **Not accepted by the agent.** |
| Installed `KittenML/kitten-tts-mini-0.8` (commercial category, 80 MB) | `POST /generate` with `engine=kittentts`: **9.4 s of 24 kHz speech in 13.7 s** (including loading), over the LAN with the key |
| Cloudflare | rule `voice.atanusroy.com -> http://127.0.0.1:3900` added (old config backed up), `cloudflared` restarted (a few seconds), CNAME added with `cloudflared tunnel route dns`; `https://voice.atanusroy.com/health` answers **200**; `chat.atanusroy.com` still answers 200 |
| Our app | the three engines (Ollama, ComfyUI, VoiceStudio) connected on the scratch Studio and **all healthy** in `/api/engines`; a 52 s reel was made end to end with the **voice from VoiceStudio (KittenTTS)**, the plan read by Ollama, 13 pictures drawn by Z-Image on the V100, the sound mixed: [reel-voiced-by-voicestudio-9x16.mp4](reel-voiced-by-voicestudio-9x16.mp4) |

## Found by that run, and fixed
* After the pictures were drawn, **the reel plan saved the project settings it had read earlier and erased the pictures from the media bin**, so the video had captions on a blank page. Fixed in `vt/pipeline.py::stage_plan` (re-read before saving); regression test `tests/test_reel.py::test_the_reel_plan_does_not_erase_the_pictures_it_just_added` (fails without the fix).
