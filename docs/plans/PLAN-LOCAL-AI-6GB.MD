# PLAN-LOCAL-AI-6GB: the local AI that fits a 6 GB card, measured

Owner's request (2026-11-21): "we need models to be able to fit this 6GB VRAM card flawlessly for ollama.. research about that and then plan and implement."
Measured on the owner's laptop: RTX 4050 Laptop GPU, 6 GB (6141 MiB), Windows 11, Ollama 0.40.16, the installed Video Tool server 0.5.0.
Bench: `scripts/lab/llm_bench.py` (fit and replay of real recorded calls) and `scripts/lab/compare_local_models.sh` (the same videos with each model).
Raw numbers: `E:\UltimateVideoTool\llm-bench\2026-11-21\` and `E:\UltimateVideoTool\matrix\2026-11-21-local-*\`.

## 1. What "fits flawlessly" has to mean here

1. **The whole model and its context stay on the card.** If Ollama cannot fit them, it silently runs part of the model on the processor (`ollama ps` shows e.g. "22%/78% CPU/GPU") and every call becomes several times slower.
2. **At the context our calls really use.** Measured from the 20 videos the local AI directed on 2026-11-21: the frame reviews are about 2,000 tokens, but the planning calls reach 51,000 characters, about 16,000 to 20,000 tokens with the answer. `vt/ai/providers.py` sizes the context to the prompt (16k to 64k). So the model must fit at **32k**, not at the 8k the old table assumed.
3. **It reads pictures.** The director's frame review sends the rendered frame. A text-only model (phi4-mini, granite) cannot do that step.
4. **It writes valid JSON in our schema**, and **it reads Bangla.**
5. **About 1.5 GB of the card is already used** by Windows and other programs on this laptop (measured before each load), so the model gets about 4.5 GB, not 6.

## 2. Research (what others report, 2026)

- Small 4B-class models are the realistic choice for 6 GB: Qwen3.5 4B (3.4 GB download, 256K context, reads images) is the most common recommendation; Gemma 3 4B and Phi-4-mini are the usual alternatives; Gemma 4 E2B and E4B are new multimodal edge models (140 languages; downloads 7.2 and 9.6 GB because they carry audio and vision parts, and they keep their per-layer embeddings in system memory).
- Raising the context is what makes a model that "fit yesterday" spill to the processor; check with `ollama ps`.
- Ollama's 8-bit context cache (`OLLAMA_KV_CACHE_TYPE=q8_0`, needs `OLLAMA_FLASH_ATTENTION=1`) halves the context's memory with negligible quality loss (+0.004 perplexity reported); 4-bit (`q4_0`) costs measurable quality.
- No public comparison of these models on Bangla exists; the only way is our own test.

Sources: [promptquorum: best LLM for 6 GB VRAM](https://www.promptquorum.com/prompt-bites/best-local-llm-6gb-vram), [localaimaster: Ollama models for 6 GB](https://localaimaster.com/vram/best-ollama-models-6gb-vram), [runaihome: realistic list for 6 GB](https://runaihome.com/blog/best-local-llm-6gb-vram-2026/), [smcleod: K/V context quantisation in Ollama](https://smcleod.net/2024/12/bringing-k/v-context-quantisation-to-ollama/), [llmhardware: KV cache quantization](https://llmhardware.io/guides/kv-cache-quantization-ollama-llama-cpp), [Ollama: qwen3.5:4b](https://ollama.com/library/qwen3.5:4b), [Ollama: gemma4](https://registry.ollama.ai/library/gemma4), [PMC: open-weight LLMs on Bengali](https://pmc.ncbi.nlm.nih.gov/articles/PMC13742879).

## 3. Measured on the card

### 3.1 Does it stay on the card? (`llm_bench.py fit`, one short call after loading)

| model | cache | 8k | 16k | 32k | card in use at 32k |
|---|---|---:|---:|---:|---:|
| gemma3:4b | Ollama default (f16) | 100% | 100% | **78%** | 5351 MB |
| gemma3:4b | 8-bit (q8_0) + flash attention | 100% | 100% | **100%** | 5021 MB |
| qwen3.5:4b | f16 | 100% | 100% | **77%** | 5377 MB |
| qwen3.5:4b | q8_0 | 100% | 100% | **100%** | 5299 MB |
| gemma4:e2b | q8_0 | 100% | 100% | 100% | 4213 MB |
| gemma4:e4b | q8_0 | 100% | 100% | 100% | 5523 MB |

**Result 1: with Ollama's defaults, a 4B model does not fit our planning calls on this card; with the 8-bit cache and flash attention it does.** That is a setting, not a new model.

### 3.2 Real calls replayed (`llm_bench.py run`, 24 calls each: 18 frame reviews with their pictures, 6 planning calls up to 49,000 characters)

| model | valid JSON | all on card | frame review (median) | planning (median) | read tok/s | write tok/s |
|---|---:|---:|---:|---:|---:|---:|
| gemma3:4b, f16 (today) | 22/24 | 24 | 4.9 s | 6.4 s | 973 | 51 |
| gemma3:4b, q8_0 | 23/24 | 24 | 3.5 s | 6.3 s | 1005 | 52 |
| qwen3.5:4b, q8_0 | 23/24 | 24 | 4.1 s | 48.5 s | 1791 | 48 |
| gemma4:e2b, q8_0 | 21/24 | 24 | 1.3 s | 20.6 s | 5025 | 104 |
| gemma4:e4b, q8_0 | 23/24 | 24 | 4.5 s | 42.2 s | 2012 | 53 |

These replays used free JSON (the recordings had no schema then), so they compare speed and fit, not answer quality. Every AI call now records its schema (`vt/ai/talk.py`), so later replays are exact. Quality is judged on real videos (3.3).

### 3.3 The same four videos with each model directing (`compare_local_models.sh`)
Rows: `explainer-watch` (English explainer 9:16), `story-lighthouse` (English story), `stick-monday` (stick figures), `explainer-bn-payment` (Bangla).
Made on the installed server, the same scripts, voices and settings; only the model changed. Seconds = planning and building (render excluded); score = the server's retention estimate (0 to 100, higher is better).

| model | explainer (EN) | story (EN) | stick figures (EN) | Bangla explainer | look |
|---|---|---|---|---|---|
| **gemma4:e2b** | 140 s, 47 | 208 s, 83 | **157 s, 83** | 164 s, 88 | the most sensible pictures: a sunrise for "Monday morning", accurate "brush your teeth / one sock" cards |
| gemma3:4b | 250 s, 55 | 329 s, 86 | 533 s, 74 | 313 s, 86 | wrong meanings: a moon cake for "snooze", a cable car labelled "curb", "Cold = It is cold" four times |
| gemma4:e4b | 168 s, 55 | 393 s, 86 | 506 s, 85 | 273 s, **18** | the Bangla video was nearly empty (21.8 s without a picture) |
| qwen3.5:4b | 164 s, 52 | render failed | fell back | not made | wrote numbers where the story engine expects text (fixed, F11 below); then the server gave a video to another director |

Contact sheets: `E:\UltimateVideoTool\matrix\2026-11-21-local-<model>\<row>.png`. Two things no model fixed, because they come from the pipeline: the English explainer has a 13 s stretch with no picture in every version, and both stick-figure videos stand the two figures on top of each other. Those belong to `docs/plans/PLAN-PERFECT.MD`.

**Decision: gemma4:e2b is first for cards up to 12 GB** (twice as fast, best pictures, as good on Bangla and the story), gemma3:4b second. On 12 GB and up gemma3:12b stays first (not measured here: no such card on this laptop).

### F11. A number in a story text field blocked the render (fixed)
Qwen 3.5 wrote a "steps" element with items 3, 6, 9, 12 (numbers). The story drawing calls `.split` on each, threw, and the render stopped ("e.split is not a function"). Now the story check writes a number as text and says so (`vt/story/engine_validate.py`, tested in `tests/test_story_text_types.py`), and the drawing never crashes on a non-text value (`server/renderer/story/src/engine/elements.tsx`).

## 4. Plan and implementation

| # | Step | Status |
|---|---|---|
| 1 | Our Ollama starts with `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, one model and one request at a time (`vt/llm.py OLLAMA_TUNING`). The person's own environment wins. An idle older copy of ours is restarted with it; an Ollama the person runs themselves is never touched. | done, tested (`tests/test_local_ai_fit.py`) |
| 2 | Record each AI call's answer schema, so a replay asks exactly what the app asked. | done |
| 3 | The model table (`vt/engines/fit.py`) holds what was **measured**: memory at 32k with the 8-bit cache, whether it reads pictures, the largest context that stays on the card; ranked by the video comparison (3.3). | done |
| 4 | An installed model is chosen only if it fits the card (today the first name that matches `gemma3`/`gemma4` wins, even one too big). | done |
| 5 | The context we ask for is capped at what fits the card (today up to 64k on any card). | done |
| 6 | After a call, if Ollama reports part of the model off the card, say so in the AI conversation ("part of the local AI ran on the processor: slower"), so it is never silent again. | done |
| 7 | Install the update on this laptop and check that the server restarts its Ollama with the new settings and, with no model chosen, picks gemma4:e2b. | done: the old copy was restarted with `fa1-kv-q8_0-p1-m1`, gemma4:e2b was chosen, 100% on the card |
