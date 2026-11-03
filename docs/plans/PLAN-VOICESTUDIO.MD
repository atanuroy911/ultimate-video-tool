# Plan: VoiceStudio as our voice engine, on the GPU machine, inside our app and callable by the director

Owner's request (2026-10-28): use [VoiceStudio](https://github.com/debpalash/VoiceStudio) for voice; install it on the GPU machine and expose its API locally; expose its UI through cloudflared at `voice.atanusroy.com`; keep large models on `/mnt/bigdata` and leave a script or doc so a future agent can download them again when that drive is missing (the owner will move to a bigger drive soon and then restore everything to the root drive); then **incorporate the whole of VoiceStudio into our app**, fitting our UI, with the director able to use it as modules. Status and measurements are in [STATUS.md](../STATUS.md) (row E11) and `docs/evidence/2026-10-28/`.

## 1. What VoiceStudio is (read from its docs, 2026-10-28)
| Fact | Source |
|---|---|
| Open-source app for **voice cloning, voice design, dubbing, dictation, transcription, audiobooks and stories**, 646 languages, local, alternative to ElevenLabs. AGPL-3.0; model weights have their own terms | repo README |
| Default engine is **OmniVoice** (k2-fsa), with OmniVoice GGUF, CosyVoice GGUF and whisper.cpp for speech recognition; Sherpa streaming for live text | README, `docs/speech-platform.md` |
| A **Python backend** (`backend.main:app`, FastAPI under uvicorn, port **3900**) serves the **web UI and the API**; Electron is only a desktop shell around it | `docs/install/docker.md`, `docs/remote-gpu.md` |
| API: OpenAI-compatible `POST /v1/audio/transcriptions`, streaming `WS /v1/audio/transcriptions/stream`, capabilities at `/.well-known/voicestudio-speech`, **MCP** at `/mcp/` (tools `generate_speech`, `clone_voice`, `describe_voice`, `design_voice`, `transcribe`, `list_voices`, `list_personalities`, `list_languages`, `check_health`), an OpenAPI page (the full REST for generation, profiles, projects and jobs is read from `/openapi.json` of the running server) | `docs/speech-platform.md`, `docs/mcp.md` |
| Auth: loopback is open; anything else needs `OMNIVOICE_API_KEY` as a bearer key; a browser exchanges the key for a short session; a reverse proxy's host name must be in `OMNIVOICE_ALLOWED_HOSTS`, its UI origin in `OMNIVOICE_ALLOWED_ORIGINS`, its public URL in `OMNIVOICE_PUBLIC_API_BASE` | `docs/remote-gpu.md`, `docs/install/docker.md` |
| Docker image `ghcr.io/debpalash/voicestudio:stable`; one data volume `/app/omnivoice_data` holds the project database, user voices, settings and the Hugging Face model cache (`HF_HOME=/app/omnivoice_data/huggingface`); first run downloads about 2.4 GB of weights; `/health` is 503 while starting and 200 when ready | `docs/install/docker.md` |
| GPU notes: float16 on pre-Ampere cards, `TORCH_COMPILE_DISABLE=1` if compile misbehaves, about 2.5 GB of VRAM, a warm request in about 1 s, `POST /models/install` pre-fetches a model, `OMNIVOICE_GENERATE_TIMEOUT_S` lengthens the first-request limit | `docs/hardware-notes-tesla-t4.md` |

**Licence.** AGPL-3.0 applies to VoiceStudio's own code. We use it as a **separate service over HTTP and MCP** and do not copy its code into this repository. (The owner has said licensing is not a concern; this is recorded so the choice is visible.)

## 2. Deployment on the GPU machine (192.168.123.47)
| Decision | Why |
|---|---|
| **Run the official Docker image**, not a source build | the image already contains the backend, the built UI and the right Python; a source build needs Python 3.11 (the machine has 3.14), `uv` and `bun` and a frontend build |
| **Pin it to the RTX 3060 (GPU 1, 12 GB, Ampere), not the V100** | ComfyUI keeps the V100 busy (it held 13 GB on 2026-10-28); the 3060 is idle, has bf16, and VoiceStudio needs about 2.5 GB. Voice and pictures can then run at the same time |
| **GPU through device passthrough, not the NVIDIA container toolkit** | the toolkit is not installed, and installing it means reconfiguring Docker and restarting it, which would restart the owner's other containers (Open WebUI, n8n, Dokploy, the LinkedIn worker). Passing `/dev/nvidia1`, `/dev/nvidiactl`, `/dev/nvidia-uvm` and the host's `libcuda.so.1` is enough for PyTorch |
| **Data volume on `/mnt/bigdata/video-tool/voicestudio/data`** (bind mount to `/app/omnivoice_data`) | models, voices, settings and projects all live there; the image layers (about 10 GB) stay in `/var/lib/docker` on the root drive |
| **Port**: container 3900 published on `0.0.0.0:3900` for the LAN so the app on the owner's PC can reach it, protected by `OMNIVOICE_API_KEY` | the Studio runs on another computer; loopback-only would defeat "expose the API locally" |
| **API key** in `/mnt/bigdata/video-tool/voicestudio/voicestudio.env` (mode 600), never in this repository or in a log; the app reads it from Settings (stored in the app's `settings.json`, which is already private) | the same rule as the SSH password |
| **Cloudflare**: add `voice.atanusroy.com -> http://127.0.0.1:3900` to the existing tunnel's `/etc/cloudflared/config.yml`, restart `cloudflared`, add the DNS record (CNAME to the tunnel) | the tunnel already serves comfy, chat, notebook and others; `OMNIVOICE_ALLOWED_HOSTS=voice.atanusroy.com`, `OMNIVOICE_PUBLIC_API_BASE=https://voice.atanusroy.com`, `OMNIVOICE_ALLOWED_ORIGINS=https://voice.atanusroy.com` |
| **A Cloudflare Access policy is recommended in front of the public name** | a public voice-cloning service is an abuse risk; the API key protects the API but the owner decides about an Access login for the UI |
| **Restart policy** `unless-stopped`; `docker logs` for logs | survives reboots |
| **Model recovery**: `scripts/voicestudio_models.py` (what is installed, pre-fetch, verify) and [ops/voicestudio-server.md](../ops/voicestudio-server.md) | the owner's rule: any agent can rebuild the models if `/mnt/bigdata` is gone |

The runbook (exact commands, paths, update, rollback, what is on which disk, how to move everything back to the root drive) is [ops/voicestudio-server.md](../ops/voicestudio-server.md).

## 3. How it fits our app
```
 Studio (React)  ->  our server (FastAPI)  ->  server/vt/voicestudio/client.py  ->  VoiceStudio on the GPU machine (REST + MCP)
                             ^                                                   ^
 the director (modules, MCP) ┘                                                   └ also reachable by the person at voice.atanusroy.com
```
* **`server/vt/voicestudio/`** (new): `client.py` (health, voices, speak, clone, design, transcribe, models, jobs; a bearer key; clear errors in words), `settings.py` (`voicestudio_url`, `voicestudio_key`), `cache.py` (a spoken sentence is cached by text, voice, language, speed and engine version, so asking twice never renders twice).
* **A TTS engine in `server/vt/tts.py`**: id `voicestudio` next to `edge`, `kokoro`, `clone`, `mms`. The existing script-to-voice path (one sentence at a time, real length known, which the audio-first plan needs) then works with every VoiceStudio voice with no other change.
* **Modules** (group `voice.*`, registered in `server/vt/modules/defs/voice.py`, toolbox `autonomous`, `studio`, `full`):
  | Module | Does | Cost | Notes |
  |---|---|---|---|
  | `voice.health` | server up, GPU, engine, queue | instant | the state card the director reads first |
  | `voice.list` | voices (cloned, designed, built-in), languages, personalities | instant | |
  | `voice.speak` | one sentence in a chosen voice, language and speed; optional target duration | fast (GPU) | wraps `generate_speech`; the **`duration` control lets the director fit a sentence to its slot** |
  | `voice.speak_script` | a whole script, sentence by sentence, with a voice per speaker; writes `audio.master` and the real word times | slow | the audio-first voice step |
  | `voice.clone` | a profile from a short recording | fast | reference audio from the project's own recording or an upload |
  | `voice.design` / `voice.describe` | a profile from a description ("warm older man, slow") / what a description maps to | fast | |
  | `voice.transcribe` | text and word times of an audio file | fast | an additional recogniser; the existing one stays the default |
  | `voice.dub` | a video in another language, voice kept | heavy | phase V5 |
  | `voice.models` | installed models, install one | instant / heavy | |
  Each module has the usual contract (summary, when to use, inputs, outputs, cost, effects, fallback `meta`: "the old engine speaks it instead", a measured example, a plain-words `log_line`) and takes the GPU lock `gpu.voicestudio`, separate from `gpu.comfy`, so a voice and a picture can run together.
* **UI inside our Studio** (Apple-style, our design system, one step at a time, no clutter):
  1. **Settings -> Voice** (a Step 1-2-3 sheet): the server address, the key, *Test the connection*, what GPU it uses, which models are installed.
  2. **A Voices page** (`/voices`, in the top bar): your voices as cards with a play button; *Clone a voice* (record or drop 10 to 30 s, a consent line); *Design a voice* (describe it, hear three candidates); delete, rename, a default voice.
  3. **The New flow's voice step** gets the VoiceStudio voices and a *Hear it* button (a short sample from the real engine).
  4. **The editor**: *Change the voice of this sentence* in the scene's panel, and *Say it again* with a different speed or feeling; one undo step.
  5. **Dubbing and long-form (audiobook) screens** (phase V5): pick a video, pick a language, see the plan (the sentences, the voice), approve, run; progress and the Details log as everywhere else.
  6. **"Open the full VoiceStudio"** inside our app: an embedded frame of `voice.atanusroy.com` (or the LAN address) for everything we have not rebuilt natively yet, with the key passed in the URL fragment as its docs describe. This is how "the whole VoiceStudio" is available from day one, while the native screens replace the frame piece by piece.
* **The director.** The audio-first plan decides audio first. With `voice.speak` the director can choose the voice from the content (a calm woman for a health explainer, a brisk man for steps), set a speed that lands a sentence on its slot, re-speak a single sentence without redoing the video, give a second speaker another voice, and look at `voice.health` before it starts. The reading step (`server/vt/reel/reading.py`) gains a `voice` suggestion beside `style` and `character`.

## 4. Phases
| Phase | What | Done when | Verify |
|---|---|---|---|
| **V0 Install and expose** (today) | the container on the 3060, data on `/mnt/bigdata`, key set, `/health` 200, the OpenAPI saved, the tunnel route and DNS, a first sentence spoken | `curl http://192.168.123.47:3900/health` is 200 from the PC; a WAV comes back; the UI opens at `https://voice.atanusroy.com/` with the key | `docs/evidence/2026-10-28/voicestudio-install.md` |
| **V0b Model recovery** | `scripts/voicestudio_models.py` and the ops runbook, tested by listing and pre-fetching | a fresh container with an empty data folder is brought back to the same models by the script alone | the script's own check |
| **V1 Client and engine** | `server/vt/voicestudio/client.py`, the `voicestudio` engine in `server/vt/tts.py`, settings keys | the New flow makes a video voiced by VoiceStudio; the cache hit is instant | `tests/test_voicestudio.py` (a fake server), one real run logged |
| **V2 Modules** (**BUILT 2026-10-28**: `voice.list`, `speak`, `speak_script`, `describe`, `design`, `clone` in `server/vt/modules/defs/voice.py`, `tests/test_modules_voice.py`; fakes for the engines; a real spoken run through each is not done; no per-engine GPU lock yet) | `voice.*` registered, lint clean, equivalence with the engine, GPU lock | `vt call voice.speak` and MCP `module_call` work; a failure falls back to the old engine and says so | `tests/test_modules_voice.py` |
| **V3 Native screens** | Settings -> Voice, the Voices page, the voice step with samples, per-sentence re-voice | a person with no help clones a voice from a recording and uses it in a new video | `client/studio/e2e/voices.mjs`, screenshots looked at |
| **V4 Director use** | `voice` suggestion in the reading; speed fitted to slots; a voice per speaker; `voice.speak_script` for the audio-first voice step | the reel pipeline speaks its script with a voice chosen from the content | evidence video |
| **V5 Dubbing and long form** | `voice.dub`, audiobook screen, chapters | a short video dubbed into a second language keeps timing and voice | evidence video |
| **V6 Move to the bigger drive** | when the owner's new drive is in, run the runbook's "move back" section | models and data on the root drive, nothing else changed | the runbook's checks |

## 5. Risks
| Risk | Mitigation |
|---|---|
| The image's PyTorch may not run on the V100 (sm_70) | we use the 3060; the V100 is only tried later, and the hardware note says float16 is used below Ampere |
| Device passthrough without the toolkit fails to find the driver | mount `libcuda.so.1` and `libnvidia-ml.so.1` read-only; if still failing, install the toolkit with the owner's go-ahead, accepting a Docker restart in a quiet moment |
| The first request times out while 2.4 GB downloads | pre-fetch with `POST /models/install` (the script does it) and raise `OMNIVOICE_GENERATE_TIMEOUT_S` |
| Public exposure of a cloning service | API key; Access policy recommended; `OMNIVOICE_ALLOWED_HOSTS` set to the one host; no analytics (`OMNIVOICE_ANALYTICS_DISABLED=1`) |
| Cloned voices of real people | the Clone screen asks for consent in words and keeps it with the profile; the director never clones from material the person did not supply |
| The embedded frame is blocked by the site's headers | a link that opens it in a new tab instead, and the native screens replace it |
| It is a second GPU service that can be down | `voice.health` first; automatic fallback to the old engines, with the reason in the Details log |
