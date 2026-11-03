# Cloud AI through OpenRouter: one key, a budget, and the "collage promo" video

Status: **plan only, not started** (owner, 2026-11-01: "plan for it, don't implement yet").

## Why

A prompt the owner shared ("a 30–60 s whimsical hand-drawn collage animation about YOURDOMAIN.com, highest production value, max OpenRouter
spend $10") gets strong results because one OpenRouter key gives the agent better models for the script, the voice, the pictures, and a
second model (for example Gemini Pro) as director and critic, for about $3 a video. Video Tool already has the parts that run locally
(pipeline, HTML/GSAP renderer, ComfyUI, local TTS, craft rules, retention scorecard). What is missing:

1. a **one-time, secure** way to give the app a cloud key, with a hard budget;
2. **cloud boosters** that use it where they beat the local models, each with the local path as the fallback;
3. the **collage promo** video type that the prompt makes, done by our pipeline instead of a one-off agent run.

Everything stays optional: with no key, the app works exactly as now.

## 1. The key: asked once, stored safely

**Where the person gives it** (all three do the same thing):

- First-run wizard: a step "Cloud AI (optional)", after the engines step.
- Settings → AI → "Cloud AI (OpenRouter)": paste the key, press Test, set the budget.
- CLI: `vt keys set openrouter`, which prompts with hidden input. The key never goes on the command line, where shell history would keep it.

The screen says plainly: **"One-time setup. Video Tool keeps this key safely on the server computer and never asks again. You can remove
it here at any time."**

**Test before saving.** `GET https://openrouter.ai/api/v1/key` with the key: it is valid, shows the key's own spend limit and usage, and
whether it is a free-tier key. The key is saved only when the test passes.

**Found already.** When `OPENROUTER_API_KEY` is in the environment or in a `.env` next to the app or data folder, the screen offers "Use
the key found in .env". On yes, the key moves into the secure store and the person is told the `.env` line can be deleted. The app never
reads `.env` silently on every start; that is a one-time import.

**Where it is stored**, on the computer that runs the pipeline (the server):

| OS | Store |
|---|---|
| Windows | Windows Credential Manager (`keyring`), encrypted under the user's login (DPAPI) |
| macOS | Keychain (`keyring`) |
| Linux desktop | Secret Service, through gnome-keyring or KWallet (`keyring`) |
| Linux headless (the GPU server: no keyring daemon) | `<data>/secrets/openrouter.key`, file mode 600, folder 700, owned by the service user; documented as "protected by file permissions" |

- `server/vt/secrets.py` holds `get(name)`, `set(name, value)`, `delete(name)`, `where(name)` (for the UI: "Windows Credential Manager"), and `masked(name)` ("sk-or-…3f9a").
- It is one module so the other keys move there too. Today `settings.json` holds `openai_key` and the engine keys **in plain text**; they migrate with a one-time move.

**Rules that never bend:**

- The key never leaves the server. It is never returned by any API (the Studio sees only "set" or "not set" and the masked form), never sent to MCP clients or the assistant, never written to logs, job records or crash reports. A redaction filter covers `sk-or-` patterns.
- From a remote Studio (client on a laptop, server on the GPU box), the key is typed in the client and sent once to the server over the paired, token-authenticated connection, then forgotten by the client.
  - The LAN connection is plain HTTP today, so the screen warns "send this only on your own network".
  - The client/server TLS work (PLAN-CLIENT-SERVER) removes that warning.
- MCP can ask "is cloud AI set up, and how much budget is left" and can never set or read the key. Setting it is the person's act, in the UI or the terminal.
- `.env` and `.env.*` are in `.gitignore` (done 2026-11-01).

## 2. The budget: a hard stop, not a hope

- Two caps, set on the same screen: **per video** (default $3) and **per month** (default $10).
- They are enforced in the app, not only by the key. The screen also recommends a limit on the key itself in OpenRouter's dashboard as a second wall.
- **Before a run:** an estimate from OpenRouter's model price list (`GET /api/v1/models` returns prices per token, image and request) times the plan's sizes. Shown in the plan ("about $1.40 of your $3"); a run over the cap asks first.
- **During a run:** every call records its real cost from the response's usage, with OpenRouter's usage accounting turned on. It goes into `<data>/cloud_usage.json`, the same pattern as `claude_usage.json`.
- **At the cap:** the next cloud call is refused before it is sent, and that step falls back to the local model. The person is told: "Cloud budget for this video reached; finished with the local models."
- The Progress page shows the live total.

## 3. Cloud boosters (each optional, each with the local path as fallback)

One provider class, `OpenRouterProvider`. It's the existing `OpenAIProvider` (OpenAI-compatible) pointed at `https://openrouter.ai/api/v1`, with the key from `server/vt/secrets.py`, budget accounting, and model choice by role. Roles, with a Settings choice of model per role:

| Role | What it does | Local fallback today |
|---|---|---|
| **writer** | script and shot list from a brief or URL, grounded in fetched facts | Ollama (gemma) |
| **director** | the plan doc: places, cast, moments, drawable prompts (rules `picture.place`, `picture.drawable`) | local director |
| **critic** | looks at rendered frames (vision) and the craft check; returns fixes; one or two revise rounds | rules only |
| **voice** | text to speech, where OpenRouter offers a TTS model at a fair price; otherwise the cloud key is not used for voice | Edge TTS, local voices |
| **pictures** | hero pictures from a cloud image model, when the person chooses it over the local ComfyUI | ComfyUI (Z-Image / FLUX.2 Klein) |

**Before building:** check which audio (TTS) and image-output models OpenRouter offers at that time and what they cost. Its catalogue changes, so none of this is assumed. A role whose model is missing falls back to local without asking.

The writer and director stay bound by the owner's rule: **never invent facts.** For a URL, the site is fetched first. Every claim in the script must be found in the fetched text, and the craft check `sync.numbers_true` already enforces numbers.

## 4. The "collage promo" video type

The prompt's output, made a repeatable type:

- **Input:** a domain or URL, plus one call to action ("try it free", "book a demo"), plus a length (30–60 s).
- **Concept:**
  - The writer reads the fetched site and writes a concept plus a 30–60 s script with a hook, the problem, what the site does (from the site), and the call to action.
  - The director makes a shot plan in the collage language: paper cut-outs, torn edges, hand-drawn doodles, stop-motion wobble at 12 fps, kraft/paper backgrounds.
- **Assets:**
  - Pictures go through ComfyUI, or the cloud when chosen.
  - Cut-outs come from BiRefNet background removal (Comfy-Org has it; a local GPU job).
  - Hand-drawn doodles come from the icon set in line style.
  - Paper textures already exist (`server/design/textures`).
- **Voice and music:** the voice role; local music (ACE-Step) or the music library.
- **Animation:** our HTML/GSAP renderer with a new theme pack `style-collage`:
  - a cut-out entrance (slide plus rotate plus a paper shadow);
  - a wobble that holds 2–3 frames;
  - a scribble reveal;
  - the stop-motion step timing.

  It's the same renderer and same export, so it gets the timeline, captions, retention scorecard and 9:16/16:9/1:1 for free.
- **Critic loop:** render a low-resolution preview, then the critic looks at about 12 frames plus the craft check, then up to two revise rounds, all inside the per-video budget.
- **Where it shows:** New → "Promo from a website", in the UI, the CLI (`vt promo URL --cta "..."`) and MCP, the same function behind all three.

## 5. Steps (each tested before the next)

1. `server/vt/secrets.py` (keyring + headless fallback + migration of plain-text keys), redaction filter, tests.
2. Key setup in the wizard, Settings, the CLI and the `.env` import; the test call; the "one-time setup" notice; never-returned API (test: no route ever returns the key).
3. Budget: estimate, live accounting, hard stop, Progress display; tests with a fake OpenRouter.
4. `OpenRouterProvider` with roles; wire writer and director; fallback tests.
5. Critic loop on rendered frames.
6. Check OpenRouter's current TTS and image models; add the voice and pictures roles where they pay off.
7. `style-collage` theme and motion; the promo video type; e2e on a real site with a $3 cap; judge by the retention scorecard.

## Open questions for the owner

- **Default caps:** $3 per video and $10 per month, or other numbers?
- **Which roles first:** director + critic only (cheapest, biggest gain), or the cloud voice too?
- **Where the key lives:** only on the server (recommended), or also allowed on a standalone client with no server?
