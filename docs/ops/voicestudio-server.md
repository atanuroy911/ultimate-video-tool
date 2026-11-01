# VoiceStudio on the GPU machine: runbook

Installed 2026-10-28 on `192.168.123.47` at the owner's request. Plan and reasons: [plans/PLAN-VOICESTUDIO.MD](../plans/PLAN-VOICESTUDIO.MD). **Since the same day the preferred voice path is ComfyUI** ([plans/PLAN-ENGINES-AND-SETUP.MD](../plans/PLAN-ENGINES-AND-SETUP.MD) section 6): VoiceStudio stays installed as the owner's own voice workshop (its UI, cloning, dubbing, audiobooks) and as an optional engine for the app.

## What runs where
| Item | Where |
|---|---|
| Container `omnivoice` (image `ghcr.io/debpalash/voicestudio:stable`, 17.3 GB, layers in `/var/lib/docker` on the root drive) | the GPU machine, restart policy `unless-stopped` |
| GPU | the **RTX 3060** (device `/dev/nvidia1`), passed in as a device; the NVIDIA container toolkit is **not** installed (installing it restarts Docker and every other container) |
| Data volume (database, voices, settings, **models**) | `/mnt/bigdata/video-tool/voicestudio/data` mounted at `/app/omnivoice_data`; `HF_HOME` is inside it |
| API key | `/mnt/bigdata/video-tool/voicestudio/voicestudio.env` (mode 600, one line `OMNIVOICE_API_KEY=...`). **Not in the repository, not in any log.** The app keeps its copy in its private `settings.json` |
| Start script | `/mnt/bigdata/video-tool/voicestudio/run.sh`, versioned copy [assets/voicestudio/run.sh](../../assets/voicestudio/run.sh) |
| LAN address | `http://192.168.123.47:3900` (UI and API; every request except `/health` needs the key) |
| Public address | `https://voice.atanusroy.com` through the existing Cloudflare tunnel (`/etc/cloudflared/config.yml` got one rule: `voice.atanusroy.com -> http://127.0.0.1:3900`; the DNS record was added with `cloudflared tunnel route dns`; a backup of the old config is in `/mnt/bigdata/video-tool/backups/`) |
| Environment | `OMNIVOICE_SERVER_MODE=1`, `OMNIVOICE_ANALYTICS_DISABLED=1`, `OMNIVOICE_GENERATE_TIMEOUT_S=900`, `OMNIVOICE_ALLOWED_HOSTS/PUBLIC_API_BASE/ALLOWED_ORIGINS` set to the public name |

## Everyday commands (on the GPU machine)
```bash
docker logs -f omnivoice                      # logs
docker restart omnivoice                      # restart
bash /mnt/bigdata/video-tool/voicestudio/run.sh   # recreate the container (after an image update or a changed setting)
docker pull ghcr.io/debpalash/voicestudio:stable && bash /mnt/bigdata/video-tool/voicestudio/run.sh   # update
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3900/health   # 200 when ready (503 while starting)
```
From the PC, with the key in the environment: `curl -H "Authorization: Bearer $KEY" http://192.168.123.47:3900/engines/tts`. The full REST description is saved in [evidence/2026-10-28/voicestudio-openapi.json](../evidence/2026-10-28/voicestudio-openapi.json) (306 paths); the model catalogue with licence categories is [evidence/2026-10-28/voicestudio-models.json](../evidence/2026-10-28/voicestudio-models.json).

## Models and licences (what is installed, and what is blocked on a decision)
* The default voice model `k2-fsa/OmniVoice` (2.4 GB) carries a **non-commercial** licence category in VoiceStudio's catalogue (`CC-BY-NC`, plus the Higgs Audio 2 and Meta Llama 3 terms of its audio tokenizer). VoiceStudio **refuses to speak with it until the licence is accepted** (`/models/licenses/accept`, or one click in the Model Catalogue of its UI). **The agent did not accept it for the owner** ([OPEN-QUESTIONS.md](../OPEN-QUESTIONS.md) Q10).
* `KittenML/kitten-tts-mini-0.8` (80 MB, English, 8 preset voices, CPU) is in the **commercial** category and was installed to prove the chain: `POST /generate` with `engine=kittentts` returned a 9.4 s, 24 kHz WAV in 13 s ([evidence](../evidence/2026-10-28/voicestudio-install.md)).
* Other engines in the catalogue (CosyVoice 3, VoxCPM2, GPT-SoVITS, MOSS-TTS-Nano ...) are listed as commercial-category but are not installed.

## If `/mnt/bigdata` is unavailable, or the drive is replaced
Everything VoiceStudio owns is in one folder, so recovery is a copy plus a re-download:
1. **Models are re-downloadable.** `python3 scripts/voicestudio_models.py --url http://192.168.123.47:3900 --key-env OMNIVOICE_API_KEY status` lists what is installed; `... restore` installs what [assets/voicestudio/model-manifest.json](../../assets/voicestudio/model-manifest.json) names (it reads the same list from the server's own `/models` catalogue and installs the entries marked wanted). Licence-gated models are listed and skipped unless `--accept-licences` is given *by a person*.
2. **User data is not re-downloadable** (cloned voices, projects, settings): back up `/mnt/bigdata/video-tool/voicestudio/data` (it is small, apart from `huggingface/`).
3. **Move to the root drive later** (when the bigger drive arrives): stop the container, `rsync -a /mnt/bigdata/video-tool/voicestudio/ /home/roy/video-tool/voicestudio/`, change `VOICESTUDIO_BASE` in `run.sh` (or export it), run `run.sh`. Nothing else changes: the address, the key and the tunnel stay.
4. **Rollback** of the public name: delete the `voice.atanusroy.com` block from `/etc/cloudflared/config.yml` (restore the backup), `sudo systemctl restart cloudflared`, remove the CNAME in Cloudflare.

## Known facts and traps
* A request to a licence-gated model returns HTTP 403 with `{"error": {"code": "model_licence_required", ...}}`; the app turns it into a sentence.
* From inside Docker, even the machine's own `curl http://127.0.0.1:3900/openapi.json` needs the key (the request does not come from the container's loopback).
* The first request after a restart loads the model (about 30 to 60 s); `OMNIVOICE_GENERATE_TIMEOUT_S=900` keeps that from timing out.
* The container sees one GPU (the 3060) as `cuda:0`; PyTorch 2.8.0+cu128 inside it; confirmed `torch.cuda.is_available() == True`.
