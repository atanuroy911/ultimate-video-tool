# Voices inside ComfyUI, run for real (2026-10-28)

The owner answered the open questions with "Accept all, go ahead, don't wait on me": the model licences were accepted by the agent **on that instruction** (VoiceStudio's `k2-fsa/OmniVoice` and its audio tokenizer; the Breeze TTS 2 non-commercial terms are accepted by using the model) and the node packs were installed. Questions Q10 and Q11 in [OPEN-QUESTIONS.md](../../OPEN-QUESTIONS.md) are decided.

| Step | Result |
|---|---|
| `scripts/install_comfy_voice_nodes.sh` on the GPU machine | cloned `ComfyUI-Breeze-TTS-2` and `ComfyUI-OmniVoice-TTS`; pinned-constraints install (PyTorch 2.12.1+cu126 untouched); `audioop-lts` added because the environment runs Python 3.14; `comfyui-audio.service` created (ComfyUI on the RTX 3060, port 8189); both ComfyUIs list the nodes. Two script bugs found and fixed on the way (the unit written through `tee` while stdin carried the password; Windows line endings) |
| Workflows against the real servers | `Workflow.problems()` returns nothing for all five (`breeze_design`, `breeze_clone`, `breeze_direction`, `omnivoice_design`, `omnivoice_clone`) |
| **Breeze TTS 2, design** (RTX 3060, bf16) | `(sigh) It was the last normal night of your life. But you did not know that yet.`: 4.3 s, 24 kHz, **every word recognised by Whisper large-v3**; 1,693 s the first time (6.5 GB download), seconds warm. Sample: [breeze-design-sample.wav](breeze-design-sample.wav) |
| **Breeze TTS 2, clone + direction** | the design sample used as the reference voice, instruction "Speak slowly with a restrained, serious tone.", text with `(clears throat)`: 4.6 s, **2.6 words a second** (slower than the 3 of a plain voice), the throat clear was a sound and not a word; 15.9 s warm. Sample: [breeze-direction-sample.wav](breeze-direction-sample.wav). Plain clone: 8.3 s warm |
| **OmniVoice, design** (V100, fp16) | a described male voice speaking two sentences: 428 s the first time (3.1 GB download). Sample: [omnivoice-design-sample.wav](omnivoice-design-sample.wav) |
| **OmniVoice, Bangla clone** (V100) | a 3.6 s Edge Bangla recording as the reference; a new Bangla sentence spoken in 5.6 s; the Bangla recogniser read "আজ আমরা শিক্ষক কিভাবে টাকা জমিয়ে রাখতে হয় প্রথমে একটি সঞ্চয় হিসাব খুলুন" for "আজ আমরা শিখব কীভাবে টাকা জমিয়ে রাখতে হয়। প্রথমে একটি সঞ্চয়ী হিসাব খুলুন।" (one word differs). Sample: [omnivoice-bangla-sample.wav](omnivoice-bangla-sample.wav) |
| Models moved to the big drive | `ComfyUI/models/breezetts2` (7.2 GB) and `omnivoice` (3.1 GB) were written by the node packs into the app folder on the root drive; they were moved to `/mnt/bigdata/video-tool/comfyui/models/` and left as symlinks; both ComfyUIs restarted and answer |
| VoiceStudio | the default model accepted and installed (2.4 GB); `scripts/voicestudio_models.py` was fixed to accept licences correctly (it needs the licence fingerprint) |
| **A reel voiced by Breeze through the app** | script with `{Calm and confident}`, `(sigh)` and `{Slowly, with weight}`; 15 sentences spoken on the RTX 3060; the director added a note and a sound; plan read by Ollama; 11 pictures drawn on the V100; 37.6 s video with sound: [reel-voiced-by-breeze-9x16.mp4](reel-voiced-by-breeze-9x16.mp4), [contact sheet](reel-breeze-sheet.png) |

## Found by that run, and fixed
* The director offered `(breath)`, which Breeze cannot make; it was dropped and said so, but the model should never be asked. `suggest()` now tells the model which sounds this voice can make and drops the others; test `test_the_director_only_offers_sounds_the_voice_can_make`.
* The voice stage keeps the old cache key for voices that cannot follow direction, so projects made before today are not re-spoken (tested).

* The first run of the automatic battery's live step (`scripts/run_all_checks.py --live`) found that **OmniVoice rejects a free-text voice description** (`Valid English items: american accent, ... young adult`). Descriptions are now mapped onto that vocabulary (`vt/comfy/voicing.py::omnivoice_instruct`, test `test_a_described_voice_is_mapped_onto_omnivoices_vocabulary`). All ten live voice checks (five workflows on each ComfyUI) then passed: [checks.md](checks.md).
* Breeze ran on the V100 as well (it fell back to fp32), so voice routing now **prefers the RTX 3060 worker for Breeze** and keeps the V100 for pictures and clips (test `test_breeze_prefers_the_worker_when_both_servers_can_run_it`).

## Not yet
Timing of captions around a sound event (VD-1), the editor and New-flow controls (VD-2, VD-3), a listening test by a person (VD-5), a Chinese sentence (VD-6), Bangla through the full reel path with OmniVoice (the voice works; the reel path for Bangla is task R11).
