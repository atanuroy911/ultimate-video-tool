# The best models we can use, for each job, on the GPUs we have

The owner's rule (2026-10-28): use the best models for every case, but **the pipeline should depend only on ComfyUI and Ollama**: many servers and setups are painful. This page is the choice, with the reasons and the limits. Sources are named where a fact is not from our own measurements. Facts about licences are as published by the model authors on the date shown; nothing here is legal advice. The owner has said licensing is not a concern; the non-commercial marks below are kept so the choice is visible if a version is ever sold or monetised.

## The machines
| GPU | Memory | Compute capability | What it means |
|---|---|---|---|
| Tesla V100 PCIe (the GPU machine, device 0) | 16 GB | sm_70 (Volta) | fp16 only, **no bf16**, no FlashAttention 2, needs PyTorch built with cu126 (the lesson of 2026-10-26) |
| GeForce RTX 3060 (the GPU machine, device 1) | 12 GB | sm_86 (Ampere) | bf16, FlashAttention 2, int8 kernels |
| the owner's PC | (CUDA 13 toolkit installed) | | the Studio, rendering, small local models |

## The decision: two servers
```
 Ollama   -> every language and vision model (planning, reading, rewriting, picture description)
 ComfyUI  -> everything that makes media: pictures, clips, voices, (and, when needed, recognition and alignment)
              one ComfyUI per GPU where a model needs a particular card (a worker), all speaking the same protocol
```
VoiceStudio, which the owner also runs, stays an optional engine (its own UI, dubbing, audiobooks). Speech recognition and word alignment already run inside the app (faster-whisper) and need no server; ComfyUI also has Whisper nodes for the day the app is only a thin client.

## By job
| Job | Best choice for us | Why | Runs on | Licence note | Status |
|---|---|---|---|---|---|
| **Voice, English or Chinese, with direction and vocal events** | **Breeze TTS 2** (BreezeBlue, 3B) through ComfyUI-Breeze-TTS-2 | the authors report #1 among open-weight models on the Artificial Analysis TTS leaderboard; clone, **design from a description**, **direction** (free-text tone, emotion, pace), `(laugh) (sigh) (cough) (clears throat)`, multi-speaker (8); 24 kHz | **RTX 3060** (bf16, about 5.3 to 7.5 GiB). The V100 has no bf16, so it would fall back to fp32 and 13 GB | research and **non-commercial**; commercial use needs written authorisation from RESONIA, INC. | **installed and verified 2026-10-28** on the RTX 3060 through a second ComfyUI ([evidence](../evidence/2026-10-28/voices-comfyui.md)) |
| **Voice, Bangla and 600+ other languages**, cloning, design, tags | **OmniVoice** (k2-fsa) through ComfyUI-OmniVoice-TTS (364 stars), also in VoiceStudio | the only open model here that covers Bangla at this quality; zero-shot clone from 3 to 10 s; `[laughter] [sigh]` and question and surprise tags; fp16 works, so the **V100 can run it** (4 to 6 GB) | V100 or RTX 3060 | code Apache-2.0; the weights carry CC-BY-NC plus Higgs Audio 2 and Meta Llama 3 tokenizer terms per VoiceStudio's catalogue | **installed and verified 2026-10-28** on the V100 (fp16), design and a Bangla clone |
| Voice without any server (fallback) | Edge online voices (best Bangla), Kokoro (Apache-2.0, English and Hindi), KittenTTS (CPU) | always available | the owner's PC | Kokoro and Kitten permissive; Edge is a free online service | in the app today |
| Other voice models worth knowing | CosyVoice 3 (free-text instruct, `[breath]`), VoxCPM2, IndexTTS-2 (emotion vector), Qwen3-TTS, Chatterbox (MIT), F5-TTS: all have ComfyUI node packs ("TTS Audio Suite" bundles most) | each wins on one axis | | VoiceStudio's catalogue marks CosyVoice 3, VoxCPM2, GPT-SoVITS, MOSS-TTS-Nano as commercial-category | candidates for later; the workflow layer takes any |
| **Pictures** (one per sentence) | **Z-Image Turbo** (8 steps, bf16 file, Qwen3-4B text encoder) | verified here: 13 s warm at 576x1024 on the V100, sharp clean illustrations, follows a style prompt; small text inside pictures is garbled, so prompts ask for none | V100 | check the model card for commercial terms before selling output | **in use** (`assets/comfy/workflows/zimage_t2i.json`) |
| **Short silent clips** | **LTX-2.3** (22B distilled, fp8) first, **Wan 2.2** (14B, 4-step) as the alternative | measured here: LTX 2.9 s clip in about 8 minutes the first time, sharper; Wan about 7 minutes first time, 67 s warm | V100 | | **in use** |
| **Language, reading, planning, rewriting** | Ollama: `qwen3.6:27b` for quality, `gemma4:latest` for speed (both installed) | the script eval passes validity on all 10 sets with gemma4; larger models for harder reading | the GPU machine | | in use; the eval shortfall is tracked as P10-16 |
| **Vision (describing a picture)** | Ollama `qwen2.5vl:7b` (installed) | the app already prefers it | | | in use |
| **Speech recognition and word times** | faster-whisper `large-v3` inside the app; Bangla fine-tune for Bangla | local, accurate word times | the owner's PC or the GPU | | in use |
| Music and sound effects | the bundled library; ACE-Step 1.5 (installed in ComfyUI) for generated music | | V100 | | library in use; generation not wired |

## What we will not do
* Install a model server per model. A new model becomes **a workflow file** (ComfyUI) or **a model name** (Ollama).
* Accept a model's licence for the owner. The click-through for `k2-fsa/OmniVoice` in VoiceStudio is waiting for the owner ([OPEN-QUESTIONS.md](../OPEN-QUESTIONS.md) Q10).

## Sources
* Breeze TTS 2 model card, [huggingface.co/BreezeBlue/Breeze-TTS-2](https://huggingface.co/BreezeBlue/Breeze-TTS-2), and the ComfyUI pack [saganaki22/ComfyUI-Breeze-TTS-2](https://github.com/saganaki22/ComfyUI-Breeze-TTS-2) (nodes, loader options, vocal events, licence).
* OmniVoice, [github.com/k2-fsa/OmniVoice](https://github.com/k2-fsa/OmniVoice), and the ComfyUI pack [Saganaki22/ComfyUI-OmniVoice-TTS](https://github.com/Saganaki22/ComfyUI-OmniVoice-TTS) (fp16 supported, tags, model folders).
* VoiceStudio documentation, [github.com/debpalash/VoiceStudio](https://github.com/debpalash/VoiceStudio), and the catalogue saved from our own server: [../evidence/2026-10-28/voicestudio-models.json](../evidence/2026-10-28/voicestudio-models.json).
* Our measurements: [../evidence/2026-10-27/gpu-server-recheck.md](../evidence/2026-10-27/gpu-server-recheck.md), [../evidence/2026-10-27/reel-pipeline.md](../evidence/2026-10-27/reel-pipeline.md).
* Consistent figure across pictures (2026-10-28 search): the Z-Image pack in our ComfyUI has `TextEncodeZImageOmni` (reference images), but no Z-Image Omni weights are installed and a ComfyUI-format file with a reference workflow was not found; searches pointed to [Z-Image Base in ComfyUI](https://docs.comfy.org/tutorials/image/z-image/z-image.md), [a LoRA route](https://www.runcomfy.com/comfyui-workflows/z-image-turbo-ai-toolkit-lora-inference-in-comfyui-training-matched-results) and [reference-latent workflows for Flux.2 Klein and Qwen](https://huggingface.co/wizdroid/comfyui-workflows). Not installed or tested.
