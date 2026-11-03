# Independent client and server

The products are now physically and independently packaged in **client/** and **server/**. The client owns the editor and local Claude/Codex companion. The server owns processing, engines, rendering assets and its management panel; it does not ship or serve the editor.

See [client instructions](client/README.md), [server instructions](server/README.md), and [agent-friendly development installation](docs/DEVELOPMENT-INSTALL.md). Windows and Linux developer scripts are scripts/dev-install.ps1 and scripts/dev-install.sh. Earlier instructions below are historical unless updated to the split roots.

# Video Tool

Documentation starts at [docs/README.md](docs/README.md): the phased [roadmap](docs/ROADMAP.md), the [implementation status with evidence](docs/STATUS.md), and the [handoff guide](docs/HANDOFF.md). The vision and owner rules are in [plan.md](plan.md).

Record your voice, **or just type a script**, in Bangla, English or **Banglish**, and get a finished, faceless motion-graphics video:
word-timed captions, silences and "um"s cut automatically, pictures that match what is being said (colour emoji stickers, line icons,
big keywords, number cards), a look designed for each video, transitions, sound effects and music that ducks under the voice.
Everything is automatic and runs on your computer with open-source parts. A **local AI model** (Ollama, on this computer or any
computer on your network) chooses the pictures; **Claude is optional** (through a local connector, no API key).

```
voice recording ─► clean audio ─► cut silences ─► transcribe (GPU) ─► time every word ─► sentences
typed script ───► speak it (voice engine) ───────────────► (exact words and times)             │
                                                                                               ▼
   final .mp4 ◄─ render (HyperFrames) ◄─ HTML composition ◄─ scene plan ◄─ local AI (Ollama) / Claude (MCP) / built-in rules
                                                                  ▲
                                          picture dictionary (145,000 English words, Bangla via translation) + emphasis from the audio
```

It is not a timeline editor. You review a transcript and a list of scenes, fix words, adjust visuals, and export.

## Install

| You want | Do this |
|---|---|
| **A normal app** (Windows, macOS, Linux) | Download the installer from the Releases page (built by `.github/workflows/release.yml`; the Windows one is `client/desktop/dist/Video Tool Setup x.y.z.exe` after `cd desktop && npm run dist`). The first start sets up its own Python, Node and speech libraries inside your user folder (10 to 20 minutes, internet needed once, no administrator rights). Your videos, models and themes live in a separate data folder and survive updates. The installers are not code-signed, so Windows SmartScreen and macOS Gatekeeper show a one-time warning ("More info" > "Run anyway"; on macOS right-click > Open). |
| **A server for the models** (a GPU computer) | The **Video Tool Engine** package from the Releases page (`.zip` / `.tar.gz`, or the Docker image): run its install script, it downloads Ollama, ComfyUI and the models, then prints an address and a pairing code. Pair it in the app: Settings, Engines. See [docs/plans/PLAN-PACKAGING.MD](docs/plans/PLAN-PACKAGING.MD). The app and the engine can be on the same computer or on two. |
| **From the browser** | Run the app (below), open it in Chrome or Edge and choose **Install** in the address bar: it becomes a client/desktop/phone app (PWA). |
| **From source** | The quick start below. |

## Quick start (Windows, from source)

Needs Node 20+, FFmpeg on PATH, and (optionally) an NVIDIA graphics card. Everything else is installed for you.

```powershell
.\scripts\setup.ps1          # ~20 min the first time (PyTorch + the 3 GB Bangla model). -CpuOnly if no NVIDIA card
.\scripts\start.ps1          # opens http://127.0.0.1:8765
```

Then **New video** → record, upload, or **Type a script** → **Generate**. Nothing else needs doing: the look, pictures and sound are chosen for you. A 90-second recording takes about a minute to process and about
three minutes to render on an RTX 4050 laptop (measured: 17 s of audio → 12 s, 48 s → 21 s; 35 s video → 62 s render).

## Using the Studio

| Screen | What it is for |
|---|---|
| **Projects** | Your videos with status and thumbnails. |
| **New video** | Record in the browser (level meter, clipping warnings, script prompter), upload a file, type a script and pick a voice (it is spoken for you), or **paste a link** (YouTube or a direct audio/video file: the audio and subtitles are downloaded, only for material you may reuse). Pick shape (9:16 or 16:9), look (**Auto** by default), pace, music. |
| **Progress** | Seven stages with live progress; plain-language errors with *Retry this step*. |
| **Review** | Scenes (left), live preview with transcript (centre), scene inspector (right). Click a word to jump, double-click to fix a spelling, right-click for more. |
| **Design Studio** | 10 looks × 18 palettes (every pair readable), 11 backgrounds including moving ones, **Surprise me**, plus the full kit: colours, fonts (Bangla + English pairs), shapes, soft shadows, motion, captions. Live preview of a sample using every element. Save as new, import/export `.vttheme`. |
| **Export** | 720p/1080p, 30/60 fps, quality, captions burned in or `.srt`, music volume, sound effects, both shapes in one go. |
| **Settings** | Local AI (address, model, one-click setup), Claude connection, defaults, speech models, system check. |

Shortcuts in Review: `Space` play · `←` `→` previous/next word · `J` `K` previous/next scene · `E` fix word · `H` highlight word ·
`R` ask Claude to redo scene · `Ctrl+Z` / `Ctrl+Shift+Z` undo/redo · `Ctrl+Enter` export.

## Automatic by default

* **Look**: with *Auto*, the app reads what the video is about (by meaning, locally) and designs a look for it from the Design Studio kit; each video gets its own.
* **Pictures**: for each sentence the app finds the words that deserve a picture (loudness, pitch and length of the speaker's voice, rarity of the word)
  and shows several ideas per sentence ("His son was lazy and careless" → boy, sloth, shrug), each appearing as its word is spoken. Bangla and other
  non-English words are translated to English (Google Translate through `deep-translator`, MyMemory as backup; single words only, cached on disk,
  set `VT_TRANSLATE=0` to switch it off) and matched to the nearest picture. Numbers and currencies follow the speaker's language ("৳১০০" for Bangla, "$100" or "₹500" for English).
* **Local AI planner**: the language model reads the story and picks the right picture for each word *in its sentence* from real candidates only
  (it cannot invent or break anything; a scene it fails keeps the rule planner's version). Settings > Local AI planner: address (default
  `http://127.0.0.1:11434`; any Ollama server on your network works), model (automatic: the best general model already installed there). If nothing runs on this
  computer, **Set up the local AI** downloads a portable Ollama into the app's data folder and a model sized to your graphics card. If the AI is unreachable the video is still planned by the built-in rules, and Review says why.
* **Type a script**: the text is spoken sentence by sentence (online Microsoft neural voices through `edge-tts`, best Bangla; or the offline Meta MMS voice, non-commercial licence), words are timed from the real audio, and the usual pipeline continues. No speech recognition is involved.

## Kinds of video, infographics, cartoons and your own media

Choose **Auto** or one of: **Product showcase**, **Storytelling**, **Discussion**, **Education** (a **General** picture-per-sentence style also exists).
Each kind is a profile in `server/design/profiles/*.json` (pacing, which scene types it favours, looks, transitions, sound) that you can edit or copy.

* **Scene director** (rules, no AI needed): every sentence gets a role (question, definition, step, price, call to action, quote, comparison, list, date,
  story...) in Bangla or English, sentences are grouped into scenes by pace, and each scene is shown as the best fitting of 21 scene types: big number, percentage
  ring, key figures, bar/compare, trend line, timeline, steps, checklist, definition, question, pros and cons, quote, cartoon scene, feature cards, price / call
  to action, device mockup, full-screen or framed picture, speaker card, title, or pictures and keywords. Only what was said is shown: charts need spoken numbers,
  steps need a sequence. Variety rules stop the same look repeating. The same project always gives the same video.
* **Infographics** are HTML/SVG drawn by the renderer and animated on one paused timeline (preview equals export): rings and lines that draw themselves, ticking checklists,
  count-up numbers, price tags with a struck-out old price, phone/laptop/browser mockups with callouts.
* **Cartoons without video AI**: characters, sets, speech bubbles and props are generated from the cast description; characters blink, breathe, walk, point and wave, and
  their mouths follow the real loudness of the voice. In a discussion each speaker gets a card with a talking avatar and an equaliser.
* **Discussions**: write a script as `Riya: ...` / `Sam: ...` lines. Each speaker gets a different voice, speaker changes are hard cuts, and the video becomes a discussion automatically.
* **Your pictures, GIFs and clips** (New video, or the **Media** button in Review): they are matched to the sentences by their caption (or spread evenly), shown framed, in a device,
  or full screen. **Text over a picture is always readable**: the contrast engine measures the worst pixels (several frames for a clip) and picks the lightest scrim that reaches
  4.5:1 contrast, and the text colour (light or dark). Tested against rendered frames.
* **Show as**: in Review, pick another scene type for any scene; only the types its sentences support are offered. Claude can do the same through MCP.
* **Free stock footage (optional)**: add your own free Pexels or Pixabay key in Settings, search inside the media bin, and the photographer credits are saved next to every export.

## Videos from links, and drawn clipart

* **From a link**: `vt link <url>` or the *From a link* tab downloads the audio with yt-dlp (limit 40 minutes, public addresses only). Subtitles decide the words
  when they are the author's own (or automatic ones for Bangla, where there is no better option); automatic English captions are skipped by default because the
  local speech model is more accurate (*Fast* mode trusts them anyway). The source, uploader and licence are saved with the project and written to the
  `.credits.txt` next to every export. Use only your own, public-domain or Creative Commons material.
* **Clipart for ideas without an emoji**: 31 drawings made by code (black hole, galaxy, nebula, supernova, atom, DNA, solar system, water cycle,
  photosynthesis, neural network, inflation, supply and demand...) are preferred automatically when a sentence says those words (English or Bangla, plural forms and
  two-word ideas like "black holes"). They are ordinary stickers, so Claude, *Show as* and the Inspector can use them (`art-black-hole`). The Media bin can also search
  Pixabay *Clipart* (vector illustrations) with your own free key. A small image model (SD-Turbo, tested on this machine at 0.5 s per picture) was tried and **not**
  shipped: it draws objects like tractors well but space and abstract ideas poorly, with busy backgrounds that cannot be cut out cleanly.

## Letting Claude plan the scenes (optional, no API key)

Claude is optional: the local AI or the built-in rules already produce a complete plan. For the best scenes:

1. One-time: open Claude Code in this folder. The project ships a `.mcp.json`, so the **video-tool** connector is offered
   automatically (approve it). Or run: `claude mcp add video-tool -- .venv\Scripts\python.exe -m vt.mcp.server`
2. In a video press **Plan with Claude** (or **Ask Claude to redo this scene**, with an optional hint such as "make it a comparison").
3. In Claude Code say **plan my pending videos** (or run `/vt-plan`). Claude reads the sentences and the component catalogue, submits a
   plan, fixes any validation errors the server reports, and can look at preview frames to check its own work.
4. The Studio updates live. Alternatives for a scene appear as options to choose from. Every change can be undone.

The connector also lets Claude create projects, fix transcript words, edit scenes, change themes and render (`vt-mcp` tools are listed in
`.claude/skills/video-tool/SKILL.md`).

## AI directors, your own assistant, and stick-figure videos

The app can let an AI write the whole plan (the **Video Script**, `server/vt/script/`): scenes, graphics, and for stick-figure videos a cast, a set and timed actions.
The built-in rules always remain the fallback, so a video is made even when no AI answers.

- **Settings → AI that directs your videos**: local Ollama (default), any OpenAI-compatible service, or the Claude API (your own key, kept on this computer).
- **Settings → Use your own AI assistant**: copy-paste setup for Claude Code, Claude Desktop (one button), Cursor, VS Code, Gemini CLI, and a token-protected
  HTTP address for ChatGPT and other remote assistants (`vt-mcp --http --port 8766`; a tunnel makes your local tools reachable, so keep the token secret).
  No MCP? In a video open **AI → Ask a chat assistant**, paste the message into any chat, paste its JSON answer back; mistakes come back as a list to forward.
- **Drawing style**: New video → *Stick figures*, or switch in the Video inspector. A stick-figure teacher (15-joint rig, IK arms, feet that stay on the
  floor, 29 verbs, 10 sets, speech bubbles, camera moves, lip sync to your voice) acts out the sentences next to the usual graphics for numbers and terms.
- **AI → Check the frames** looks at one frame per scene (vision model, else pixel checks), can fix cut-off or crowded scenes, and can let the vision model pick
  between candidate pictures. **AI → Check the transcript** suggests fixes for recognition mistakes (never applied without your say-so).
  **Media bin → Describe with AI** captions and tags your pictures. **Export → Publishing kit** writes a title, description, hashtags and a cover image.
- The dashboard (Projects): summary, continue card, quick-start tiles, filters, search, sort, grid/list, rename, duplicate, bulk delete.
- The editor: title bar with menus, browser (scenes, words, media), canvas (click an element to select it), a context inspector, a timeline with
  draggable scene edges that snap to sentences, a command palette (Ctrl+K), resizable panels.

## Free media, voice editing and the Projects page

* **Free media catalogue** (`vt catalog list|refresh|check`, Media tab, New page "try a sample"): validated CC0 / public-domain / CC BY speech, music and video from the Internet Archive and Wikimedia Commons, each with licence, author and link. Anything NC, ND or share-alike is refused. Credits for what you use are added to the export.
* **Emoji videos** (drawing style *Emoji*): colour emoji and big words only, no charts, never the same emoji twice in a row. *Stick* gives a stick figure that acts the sentences; *Pictures* is the default.
* **Voice on the timeline**: cut (ripple delete), trim, split, mute and volume for any range, with undo and redo; the picture, words and captions follow.
* **Projects page**: search, filters, sort, grid or list, duplicate, delete, open the last export.
* If a button answers "405" or "not found", the Studio on your computer is older than the page: restart it (`.\scripts\start.ps1`). The Studio now says so in a banner.

## Sounds, offline voices and your own voice

* **Sounds that are not speech.** The app listens for laughter, applause, music, rain, animals and more (an AudioSet model, runs on the GPU when there is one). A matching emoji appears in the scene where the sound happens, a **Sounds** lane shows them on the timeline, and a recording with no speech at all becomes a video with sound captions such as "[Baby laughing]". Turn it off with `sound_events: off` in the project options.
* **Offline voices (Kokoro).** For typed scripts in English or Hindi there is a free offline voice engine with 54 voices (Apache 2.0). The model (about 120 MB) downloads the first time you use it. Bangla keeps its own voices.
* **My own voice (cloning, English).** Record or upload 10 to 30 seconds of clear speech in **Settings > My own voice**, tick that it is your own voice (or the speaker allowed it), and choose "My own voice" when you make a video from a script. In the editor, the microphone button on a sentence in the **Script** tab says it again in your voice and mutes the original. Cloning runs inside the app itself (the Chatterbox Turbo model through ONNX Runtime, on the GPU when there is one, faster than real time on an RTX 4050); its model, about 1.1 GB, downloads the first time you use a voice.

  Nothing is cloned automatically and no voice is ever taken from a download or a project. The recording stays in the `voices` folder on your computer.

## Talking-head videos (A-roll), cutout, voice cleanup

* **Import a video** (a talking head, an interview) and the speaker's picture is kept, cut exactly like the voice. The speaker is shown on the opening and wherever the words need no picture of their own; graphics fill the rest. Words, emoji and stickers are placed only in free space: **never on a person** (in a tall 9:16 crop that fills with the speaker they are left out). The crop follows the head. "The speaker's picture" in the video inspector switches this on and off.
* **Cut out** (media bin): removes the background of a picture and adds a transparent PNG that can go on a layer above other pictures.
* **Clean up the voice** (Export page): less hiss and hum, clearer, more even.
* **Layers**: text, pictures, video clips and sounds on extra tracks of the timeline; Ctrl+C / Ctrl+V copy a clip, each picture or text clip can have a slow zoom or slide.
* **Optional Concat engine** (`tools/concat`, AGPL-3.0): a GPU video engine driven headless (`server/vt/concat_client.py`, `scripts/spike_concat.py`). Nothing needs it yet.

## Banglish (Bangla with English words)

* The speech model is a **Bangla fine-tune of Whisper medium** (`bengaliAI/tugstugi_bengaliai-asr_whisper-medium`, converted to
  CTranslate2, fp16 on the GPU). On synthetic clips it beat `large-v3` by a wide margin for Bangla (7–15% vs ~50% word error).
* It writes English words in Bangla script (ফ্ল্যাট, নেট ইয়েল্ড). Each project chooses how they appear:
  **Keep English letters** (default: `flat`, `net yield`) or **Bangla script**. A starter dictionary is in `server/design/terms.json`;
  add your own pairs per project in *Banglish & advanced → Glossary* (`yield=ইয়েল্ড`). Your edits and glossary always win.
* Words the model is unsure about are underlined in the transcript; *Next to check* cycles through them.

## Command line

```
vt link <url> [--lang en] [--subs auto|any|off]   # from a YouTube / audio link, then vt run <project>
vt new "Title" --audio rec.wav [--aspect 16:9] [--theme paper] [--pace calm|normal|fast] [--music lofi-01]
vt run <project> [--from asr] [--force]         # clean → cut → transcribe → time → plan → compose
vt render <project> [--aspect both] [--quality draft|looks|delivery] [--cpu]
vt studio | vt list | vt status <p> | vt snapshot <p> --at 3,9 | vt plan-request <p> [--scene s2 --hint "…"]
vt models list|pull <name> | vt themes | vt music | vt doctor | vt demo
```

## How it is built

| Part | Choice | Why |
|---|---|---|
| Video rendering | **HyperFrames** (Apache-2.0): HTML + CSS + GSAP in headless Chrome → FFmpeg | One HTML composition is both the live preview and the render source; browser text shaping renders Bangla conjuncts correctly. Revideo's maintenance was unclear and Remotion is free only for ≤3-person companies. |
| Speech | faster-whisper (CTranslate2), Silero VAD gate | GPU, word timestamps, fast. |
| Cutting | own energy-based detector with adaptive threshold, 10 ms crossfades | Needs no ML and follows the room's noise floor. |
| Planner | Claude via an MCP server, rule-based fallback | No API key, nothing leaves the machine. |
| App | FastAPI + WebSocket, React + Vite (no UI framework) | Small, fast, easy to read. |
| Audio | FFmpeg: loudness normalise (−16 LUFS), sidechain ducking, limiter | |
| Assets | Fonts SIL OFL, icons Lucide (ISC), music/SFX synthesised by `scripts/make_assets.py` (CC0) | Everything redistributable. |

```
server/vt/                  Python package: stages/ (audio, asr, chunks, align, words, terms), planner/, compose/, render/,
                     server/ (FastAPI + jobs), mcp/ (Claude connector), pipeline.py, planning.py, scene_ops.py, cli.py
server/renderer/runtime/    vt.js + vt.css: the in-page engine that builds the video from data (components, transitions, captions)
server/design/              themes/*.json, fonts (generated), icons (generated), terms.json, textures/
client/studio/              React app (src/) and browser tests (e2e/)
server/assets/              music + sfx (generated)         samples/   demo project builder and test audio
projects/            your videos (one folder each: input, transcript.json, scenes.json, composition/, exports/)
models/              downloaded speech models        tests/     70 Python tests
```

**Data contract:** `scenes.json` lists scenes with elements anchored to **word ids** (`"at_word": "w17"`), never to seconds, so plans survive
spelling fixes and re-cuts. Captions always come from the transcript. Every component's fields and limits are defined once
(`server/vt/schema.py`) and drive validation, the Studio's forms and Claude's task.

**Adding a component:** a pydantic model in `server/vt/schema.py`, an example in `server/vt/planner/catalogue.py`, a builder in `server/renderer/runtime/vt.js`
and CSS in `vt.css`. The catalogue test fails until all four agree; add the element to `server/vt/compose/specimen.py` to see it in the Theme editor.

## Tests

```powershell
.venv\Scripts\python -m pytest -m "not slow"     # 61 fast tests (cuts, words, schema, planner, director, contrast, media, stock, visuals, designer, TTS, local AI planner, composer, API, MCP over stdio…)
.venv\Scripts\python -m pytest -m slow           # 9 tests: real speech model + pixel-compared renders (tests/golden)
cd studio; npm run e2e; npm run e2e:editor; npm run e2e:design; npm run e2e:phase2; npm run e2e:journey; npm run e2e:export   # browser checks (see client/studio/e2e/README.md)
python scripts/asr_bakeoff.py bn-medium,large-v3 samples/audio/banglish.mp3   # model comparison
```

## Troubleshooting

* **Model download stalls at 0 bytes** — the app disables Hugging Face's Xet transfer (it stalled on Windows during testing). Run
  `vt models pull bn-medium` again; downloads resume.
* **Port in use** — `.\scripts\start.ps1 -Port 9000`.
* **"No speech was found"** — the recording is silent or only noise; check the microphone level.
* **No NVIDIA card** — `setup.ps1 -CpuOnly`; transcription falls back to the CPU (slower), rendering uses the CPU encoder automatically.
* **`vt doctor`** lists what is missing and the command that fixes it.
* HyperFrames telemetry and cloud features are switched off for every call the app makes.

## Known limits

* Phase 2: two voices in a recording are told apart by pitch and tone only (no model): similar voices, more than two people or noisy rooms are left as one
  speaker, and `Name: text` scripts are always exact. The cartoon art is simple generated vector drawing. Maps, Lottie props and picture-embedding matching are not
  built. Faces are found with a classic detector (good for frontal faces, weaker for profiles); pictures with no clear face just get the contrast scrim.

* The local AI chooses pictures well for concrete words (people, objects, feelings) and falls back to big typography for abstract ones; some
  picks are still odd. A 7-8 billion parameter model plans about 30 scenes in 2 minutes. Claude (optional) is better at storytelling.
* Typed-script word timings are estimated from the audio (within roughly 0.1 to 0.15 s of speech recognition), so caption highlights can be slightly off.
* The desktop installers are built and tested on Windows only; the macOS and Linux builds come from the CI workflow and have not been run by hand.

* Recognition quality on **real** recordings is not yet measured: all benchmarks here use synthetic speech (generated with
  `scripts/make_sample_audio.py`, which sends the sample text to Microsoft's online voices). Expect more errors on noisy rooms and
  accents; the review screen exists for that.
* Bangla app-interface text is a first draft and should be reviewed by a native speaker. The bundled music and effects are simple
  synthesised loops; they were not auditioned by ear. Drop your own tracks into `server/assets/music/user/`.
* Windows is the tested platform. Single user, local only. Preview plays voice only (music and effects are mixed on export).
# Shorts and social publishing

Open **Shorts** in Studio to import a YouTube or supported video link, or select an existing project. After transcription, choose **Find Viral Highlights**. Audition the proposed ranges, create editable 9:16 child projects, or batch export MP4s. Each child project appears in Projects and can be opened in the editor. Imported source video is used as A-roll where available. Link imports are limited to 60 minutes.

Open **Social** to add channels and make groups. The **mock** platform exercises the full local task flow without an external account. Live connections require platform developer credentials and publishing permission. Meta Pages and linked Instagram Business accounts can be added by exchanging a Meta app user token; YouTube and TikTok accept access and refresh token details in the account credentials form. Credentials are stored in `VT_DATA/social/social.db` and are never included in account list responses. Use the finished video's **Publish to social channels** card to edit metadata, select a group, and dispatch immediately or schedule later. The task flow shows progress, links, failures, and retry actions; logs remain in the same database after restarts.

Platform APIs can limit publishing based on account permission, app review, media specifications, and quotas. A queued task will show the API error if that platform rejects it. TikTok posts from unaudited developer apps may be restricted to private visibility. The local mock flow is suitable for testing group fan-out before connecting live accounts.

## Codex and GPT directors

In **Settings → Codex connection**, choose **Connect Codex on this computer**, or copy the displayed `codex mcp add` command. Restart Codex after registration. The local MCP server then gives Codex the same project, transcript, Video Script, scene editing, preview, and render tools already used by Claude. In Codex, ask: “Use Video Tool to list my projects, direct the whole video for project `<id>`, inspect frames, and render it.” For queued Studio requests, ask: “Plan my pending videos.”

For API-backed GPT, choose **OpenAI GPT / compatible API** in **Settings → AI and assistants**, enter an API key and model, and turn on **Let AI direct all video types**. The existing whole-video Video Script planner then uses that provider. ChatGPT can also use the MCP server as a custom connector when the local HTTP endpoint is made reachable through a secure tunnel; Settings shows its URL and token instructions.

# ultimate-video-tool
# ultimate-video-tool
