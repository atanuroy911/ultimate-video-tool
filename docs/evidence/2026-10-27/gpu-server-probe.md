# GPU server probe, 2026-10-27 22:10 (this PC's clock), 192.168.123.47

Read-only probes from this PC. No credentials are stored here.

| Probe | Result |
|---|---|
| ComfyUI `GET /system_stats` | up: 0.42.5, V100 16 GB, 44 GB RAM free; queue empty; `GET /history` empty (the server restarted since the 2026-10-26 runs) |
| ComfyUI `GET /object_info` | 974 nodes, **but the core loaders are missing**: `CLIPLoader`, `LoraLoaderModelOnly`, `LoraLoader`, `CheckpointLoaderSimple` and `VHS_VideoCombine` are absent while `UNETLoader`, `VAELoader`, `KSampler`, `LoadImage`, `SaveVideo` are present |
| Studio, Wan 2.2 clip from `tests/fixtures/face.jpg` through `POST /api/projects/reference/comfy/generate` | **failed before the GPU was used**: "the server has no node 'CLIPLoader' (node 84); ... 'LoraLoaderModelOnly' (node 102) ... (node 101)". The Studio's pre-flight check caught it, as designed. |
| Ollama `GET /api/tags` and `POST /api/generate` (gemma4:latest) | **both fail**: `mkdir /usr/share/ollama: input/output error: ensure path elements are traversable` |
| Ollama `GET /api/ps` | `{"models":[]}` (answers, nothing loaded) |
| Open WebUI `GET :3000` | HTTP 500 |
| SSH (port 22) | the port accepts the connection and then **closes it during key exchange** ("kex_exchange_identification: Connection closed by remote host"); no banner is sent |

**Reading.** Everything that lives on the server's root drive (`/dev/sda2`, 89 % full on 2026-10-26: `/usr/share/ollama`, the SSH daemon's files, Open WebUI's container) returns an input/output error, which points at the root filesystem or disk, not at our code. ComfyUI itself runs from `/mnt/bigdata` but is missing its core loader nodes. That is a change: Wan, LTX, Z-Image and ACE Step all ran after the model cleanup earlier on 2026-10-27 ([evidence](../2026-10-26/comfy-model-cleanup.md)), and the boot audit ([evidence](comfy-boot-persistence.md)) saw `/` at 62 % used and `/mnt/bigdata` at 81 %. Whatever broke happened after those checks. Both the cause and the repair need a person at the machine or a working shell (`dmesg`, `smartctl -a /dev/sda`, a read-only remount check, `fsck`).
**Not tried, on purpose:** restarting services blind, or changing anything on the server.
