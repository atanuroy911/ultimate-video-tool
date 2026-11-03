# Plan: a standalone app made of engines that can be local or remote, and the setup that connects them

Owner's vision (2026-10-28, near verbatim): the software is **standalone**. On first run the **setup downloads every model and program it needs and sets them up locally**. In the same setup it **asks whether the owner's servers are running somewhere else**, takes the address, and connects. The same applies to everything: Ollama, ComfyUI, VoiceStudio, and **other models as necessary**. The models that run on the owner's own PC today can themselves be packaged as a **server element**, installed on another computer, and used through its API. The whole flow should be streamlined. The owner's own GPU machine (VoiceStudio today) is the primary setup; the app must let any other person do the same through the UI. Keep every record in the docs for future agents.

This plan turns that into one design. It extends [PLAN-DIRECTOR-MODULES.MD](PLAN-DIRECTOR-MODULES.MD) (modules are what the director calls; engines are what modules call) and replaces the scattered address fields in Settings (`ollama_url`, `comfy_url`) and the three install helpers (`server/vt/doctor.py`, `server/vt/models.py`, `build/`).

## 1. The idea in one picture
```
 director / Studio / MCP  ->  modules (voice.speak, gen.image, plan.write ...)
                                     |  ask for a capability, never an address
                                     v
                      the ENGINE REGISTRY  (what is connected, where, healthy or not)
              ┌──────────────┬────────────────┬──────────────┬────────────────┬───────────────┐
              | language     | pictures+clips | voice        | recognition    | anything else |
              | Ollama,      | ComfyUI        | VoiceStudio  | Whisper,       | an OpenAI-    |
              | OpenAI-like, |                |              | VoiceStudio    | compatible    |
              | Claude CLI   |                |              |                | endpoint      |
              └──────┬───────┴───────┬────────┴──────┬───────┴────────┬───────┴───────────────┘
                     |  each engine is ONE of three modes
                     |  local   : installed and started by the app on this computer
                     |  remote  : an address (and a key) of a server the person already runs
                     |  off     : not used, the built-in fallback answers
```
**An engine is a service with a contract, not a library.** Every engine answers `health`, says which **capabilities** it offers (`llm.chat`, `image.generate`, `video.generate`, `voice.speak`, `voice.clone`, `asr.transcribe` ...), which models it has, and what it costs (GPU memory, seconds). Modules ask the registry for a capability; the registry picks the engine (the person's choice, else the healthiest, else the fallback) and the call log says which one answered.

## 2. What exists today (read from the code, 2026-10-28)
| Piece | Where | Gap against the vision |
|---|---|---|
| Ollama address in settings, status chip in the top bar, model choice, auto-download of a small model | `server/vt/llm.py`, `server/vt/ai/providers.py`, `server/vt/server/app.py` (`ollama_url`), `client/studio/src/pages/LocalAI.tsx`, `AIAssistants.tsx` | local install of Ollama itself is not done by the app; remote is just a URL |
| ComfyUI address, workflows, status, pre-flight check | `server/vt/comfy/`, `server/vt/server/comfy_routes.py`, `client/studio/src/pages/ComfySettings.tsx` | no local install; no model download; the default address is the owner's machine |
| Speech models download (Whisper, Bangla model), TTS engines (edge, kokoro, clone, mms) | `server/vt/models.py`, `server/vt/stages/asr.py::ensure_model`, `server/vt/tts.py`, `server/vt/doctor.py` | local only; no remote ASR/TTS; no common idea of an engine |
| First-run | the Studio opens on the dashboard; `vt doctor` prints a report | no wizard; nothing asks "do you have a server?" |
| Packaging | `build/make_d...` (desktop shell and installer, partly done) | the installer ships the app, not the engines |
| Modules | `server/vt/modules/` (140 modules) | modules call libraries directly, so a remote engine cannot be substituted |

## 3. The design
### 3.1 The engine registry (`server/vt/engines/`)
```python
class EngineSpec:     id; kind ("llm" | "image" | "voice" | "asr" | "custom"); label; capabilities: list[str]
                      installer: Optional[Installer]          # how to put it on THIS computer
                      client: Callable[[Endpoint], Client]    # how to talk to it
class Endpoint:       mode ("local" | "remote" | "off"); url; key (stored in the app's private settings); gpu: Optional[int]; data_dir: Optional[Path]
class Health:         ok; version; models: list[ModelInfo]; gpu: {name, free_mb}; seconds_to_answer; why_not: str
```
* **Settings** keep one block per engine: `engines: {ollama: {mode, url, key}, comfy: {...}, voicestudio: {...}}`. The old `ollama_url` and `comfy_url` stay readable (migration on first start) so nothing breaks.
* **Endpoints** `GET /api/engines` (all, with health), `POST /api/engines/{id}/test`, `PUT /api/engines/{id}` (mode, url, key), `POST /api/engines/{id}/install` (local mode, a job with progress and the Details log), `GET /api/engines/{id}/models`, `POST /api/engines/{id}/models/install`.
* **Modules** declare `engines=("voice.speak",)`. The executor resolves it **before** running, takes that engine's GPU lock (`gpu.<engine>.<gpu>`) and writes the engine into the call record. A module whose engine is down returns `needs_input` ("the voice server does not answer; use the built-in voice instead?") or runs its fallback, as the contract already says.
* **Capabilities, not brands.** `voice.speak` can be answered by VoiceStudio, Kokoro, Edge or a future engine; `gen.image` by ComfyUI or an OpenAI-compatible image endpoint; `plan.write` by Ollama, Claude, OpenAI or the rules. "Other models as necessary" is then adding an `EngineSpec`, not changing the pipeline.

### 3.2 The setup (first run, and again from Settings -> Engines)
One question per screen, Apple style, like the New flow. It can be left at any step and resumed.
| Step | What the person sees | What happens |
|---|---|---|
| 1 Welcome | "We will make everything run on this computer, and connect anything you already run elsewhere." | detects OS, RAM, disk, GPUs (name, memory, compute capability) with plain words ("Your graphics card can make pictures and clips" / "This computer has no graphics card: pictures and voices will be slower or use a server") |
| 2 Where do the big files go? | a folder picker with the free space shown; default `<data>/models`; a note "you can move this later" | writes `models_dir`; every engine's model cache is pointed there (Hugging Face `HF_HOME`, Ollama `OLLAMA_MODELS`, ComfyUI `extra_model_paths.yaml`, VoiceStudio data volume); the owner's `/mnt/bigdata` case |
| 3 Do you already run any of these on another computer? | for each engine (Language AI, Pictures and clips, Voices, Speech recognition) three cards: **Set it up here**, **Connect to my server**, **Skip** | a recommendation is pre-selected from step 1 |
| 4 Connect | address + key; *Test* shows the version, GPU, models, and what it can do for this app; a tip when the model it needs is missing ("this server has no Z-Image: install it?") | `POST /api/engines/{id}/test`; saved on success |
| 5 Set up here | a plan sheet before anything is downloaded: each item, size, time, disk after; **Start** | the installers run as jobs with progress; resumable; checksums from the model manifest; the Details log shows every step |
| 6 Try it | one sample each: a sentence spoken, a picture drawn, a question answered | proves the whole chain; failures link to the fix |
| 7 Done | "You can change any of this in Settings -> Engines." | |
The wizard writes **`docs/`-style records** the app can show: an *Engines report* (what is connected, where, which versions) that can be copied into a bug report or handed to an agent.

### 3.3 Local installers (`server/vt/engines/installers/`)
One installer per engine with the same shape: `plan() -> Plan` (items, sizes), `install(progress)`, `start()`, `stop()`, `verify()`, `uninstall()`. They must be **idempotent and resumable**, **never need admin rights where the OS allows**, and **put big files in `models_dir`**.
| Engine | Local install on a user's computer | Notes |
|---|---|---|
| Ollama | download the official installer or binary for the OS, start the service, `pull` the chosen small model | already partly done in `server/vt/llm.py` (`ensure_ready`) |
| ComfyUI | a managed copy in `<data>/engines/comfyui` with its own Python environment (the right PyTorch for the GPU's compute capability: the V100 needs `cu126`; the lesson from 2026-10-26), the workflows from `server/assets/comfy/workflows/`, the models from `server/assets/comfy/model-manifest.json` (pinned URLs and SHA-256), `extra_model_paths.yaml` to `models_dir` | `scripts/restore_comfy_models.py` already restores the owner's server from the manifest; the installer reuses it |
| VoiceStudio | the official Docker image where Docker exists, else its client/desktop/AppImage installer or a source setup with `uv`; data in `models_dir/voicestudio` | the owner's server uses the Docker route; see [PLAN-VOICESTUDIO.MD](PLAN-VOICESTUDIO.MD) |
| Whisper and the Bangla model | the existing `server/vt/models.py` | unchanged, now reported through the registry |
| Kokoro, Chatterbox, MMS (small voices that work without a server) | the existing downloads | the built-in fallback voices |
**Rule:** a person without a GPU still gets a working app: the built-in fallbacks (rules planner, Edge or Kokoro voice, typography and stock pictures) answer, and the wizard says plainly what is slower or missing.

### 3.4 "Our own models as a server element": the Engine Server
The owner: *the models running on my PC can be a server element in itself, installed on another computer and connected through an API.* So the app can **host** engines, not only use them.
* **`vt serve-engine`** (new command, and a button in Settings -> Engines -> *Share this computer's models*): starts a small authenticated HTTP service that exposes the engines installed here (the speech models, the recogniser, the saliency and face models, the renderer's headless job runner) with the **same capability contract** the registry speaks. It is the same FastAPI app we already have with a smaller route set, an API key, TLS-friendly headers, and a `/.well-known/vt-engine` document that lists capabilities and models.
* **Discovery and pairing:** the other computer shows an address and a one-time pairing code (QR in the UI); the client enters it in step 4 of the wizard.
* **Packaging:** the installer gets a second target, "Engine only" (no Studio window, no projects), for a GPU box. The owner's `192.168.123.47` could run this instead of three separate programs one day; today it runs Ollama, ComfyUI and VoiceStudio as they are and the registry treats each as an engine.
* **Remote job protocol:** long work (a render, a dub) is a ticket with progress and cancel, the same shape as the module tickets (`server/vt/modules/tickets.py`), so the Details sheet shows remote work like local work.

### 3.5 Storage, models and recovery
* **`models_dir` is one setting** (the owner's `/mnt/bigdata/...`), and every engine's cache is derived from it. A **model manifest per engine** (`server/assets/<engine>/model-manifest.json`: id, source URL, size, SHA-256) is the single list of what must exist.
* **`vt models status | restore | move <new-dir>`** (and the same in Settings -> Engines -> Storage): lists what is present, downloads what is missing (resumable, checksum verified), and moves the whole store to a bigger drive, rewriting each engine's path. This is the owner's "when /mnt/bigdata is unavailable, or when I move to a bigger drive, restore everything" requirement, as a feature instead of a one-off script.
* **Server side** the same scripts exist as plain files (`scripts/restore_comfy_models.py`, `scripts/voicestudio_models.py`) and the runbooks in [ops/](../ops/) so an agent without the app can do it.

### 3.6 In the UI (what a person sees)
* **Top bar chips** (today: "AI: gemma4:latest") become one **Engines** chip with a dot per engine; click opens a quiet popover: each engine, where it runs (This computer / address), health, *Open settings*.
* **Settings -> Engines**: a card per engine with the three modes as a segmented control, address and key fields (key hidden), *Test*, *Install here*, the models list with sizes and *Install* buttons, GPU and disk use, *Move storage*. Advanced options only in a *Step 1-2-3* sheet, never inline.
* **Setup wizard** (3.2) on first run; **"Re-run setup"** in Settings.
* **A "Voices" page, a "Pictures" status in the plan sheet, the editor's "change the voice of this sentence"** are the user-facing faces of the engines; none of them shows an address or a port.
* **Everything is explained in plain words** and in Bangla as well as English (the wizard strings go in `client/studio/src/i18n.ts`).

## 4. Phases
| Phase | What | Done when | Evidence |
|---|---|---|---|
| **E0 Registry and health** | `server/vt/engines/` (spec, endpoint, health, registry), settings migration from `ollama_url` and `comfy_url`, `/api/engines`, Ollama, ComfyUI and VoiceStudio specs with clients | one call lists all three with health; the old settings still work | `tests/test_engines.py`, the live list |
| **E1 Engines page** | Settings -> Engines with modes, address, key, Test, models list; the top-bar chip | the owner connects VoiceStudio from the UI and sees it healthy | `client/studio/e2e/engines.mjs`, screenshots |
| **E2 VoiceStudio as an engine** | client, `voicestudio` TTS engine, `voice.*` modules (see [PLAN-VOICESTUDIO.MD](PLAN-VOICESTUDIO.MD)) | a video is voiced by VoiceStudio; a module call logs which engine answered | tests + a real run |
| **E3 Storage and manifests** | `models_dir`, per-engine manifests, `vt models status/restore/move`, `scripts/voicestudio_models.py` | an empty cache is rebuilt from manifests alone | the script's check |
| **E4 Setup wizard** | the 7 steps, resumable, Bangla and English | a clean profile ends with a working sample of each connected engine | recorded run on a clean data folder **BUILT 2026-10-28 (English only; Bangla strings still to add):** `server/vt/engines/setup.py`, `client/studio/src/components/SetupWizard.tsx`, a banner on the dashboard and *Run setup* in Engines |
| **E5 Local installers** | Ollama, ComfyUI (managed), VoiceStudio (Docker or installer), Whisper | on a PC with a GPU the wizard makes pictures and voices with nothing else installed | a clean-machine test (a VM or a second PC) **PARTLY BUILT 2026-10-28:** Ollama and ComfyUI installers (plan, resumable checked downloads, commands) tested with the shell replaced; VoiceStudio is explained, not installed; **no clean-machine run yet** |
| **E6 Engine Server** | `vt serve-engine`, pairing, the capability document, the "Engine only" package | another computer uses this PC's models through the registry | two-machine test **BUILT 2026-10-28:** `vt serve-engine`, `/.well-known/vt-engine`, one-time pairing, `voice.speak`, `asr.transcribe`; tested over loopback, not between two computers; the "Engine only" package is built since 2026-10-28 ([PLAN-PACKAGING.MD](PLAN-PACKAGING.MD)): `vt engine ...`, gateway, installers, workflows; not yet run on GitHub or between two computers |
| **E7 Modules resolve engines** | the executor resolves capabilities to engines, per-engine locks, fallbacks, the engine named in every log row | switching an engine from remote to local changes nothing else | module tests with a fake engine **PARTLY BUILT 2026-10-28:** `engines=` on a module, resolved and recorded in the call; two clip modules use it; per-engine locks and the rest of the modules are still to do |

## 5. Open questions (kept for the end of the build, as the owner asked)
Recorded in [../OPEN-QUESTIONS.md](../OPEN-QUESTIONS.md), not asked mid-work.

## 6. The two-server principle (owner, 2026-10-28)
*"I would prefer the pipeline to depend only on ComfyUI and Ollama. Multiple models and server setups are painful. Use the best models out there that can run on our GPUs."*
This narrows section 1 without changing it: the registry still knows every engine, but **the defaults, the wizard and the docs lead with two**:
| Server | Carries | How a new model arrives |
|---|---|---|
| **Ollama** | every language and vision model | a model name |
| **ComfyUI** | pictures, clips, **voices** (and, if needed, recognition) | a workflow file (`server/assets/comfy/workflows/*.json`) plus, if it needs one, a custom-node pack |
A graphics card that a model cannot use is not a reason for a third kind of server: it is a **worker**, another ComfyUI on that card. The registry's ComfyUI endpoint therefore has `workers` (urls); a workflow runs on the first server whose `object_info` satisfies it (`Workflow.problems()`), and the Engines page shows what each server can do. On the owner's machine: ComfyUI on the V100 (pictures, clips, OmniVoice in fp16) and a ComfyUI worker on the RTX 3060 (Breeze TTS 2, which needs bf16).
**Voices through ComfyUI** (built 2026-10-28): workflow kind `audio`; `server/vt/comfy/voice.py` speaks one sentence; `server/vt/comfy/voicing.py` picks the model from the language and the direction wanted (Breeze for English and Chinese with direction, OmniVoice for everything else, whichever is installed); the app's `comfyvoice` voice engine lists *described* voices and the person's own consented voices. **Direction and vocal events** are a layer above the engines: [PLAN-VOICE-DIRECTION.MD](PLAN-VOICE-DIRECTION.MD).
**VoiceStudio** remains supported as an optional engine and as the owner's own voice workshop; it is no longer on the default path. **Which models are best for each job and why:** [../research/BEST-MODELS.md](../research/BEST-MODELS.md). **What is installed and what is waiting for permission:** [../ops/comfyui-voice-nodes.md](../ops/comfyui-voice-nodes.md).
