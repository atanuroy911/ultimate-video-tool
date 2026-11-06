# Story Engine — voice + SRT → animated 9:16 story video, with any AI or none

This is the generalised version of the pipeline that made the "Rafi's HSC result" video.
Nothing in the renderer knows about fathers, sons or exams: every video is a **JSON spec**
(`src/spec.json`) made of scenes, backgrounds and elements. The spec can come from:

| Planner | Needs | Quality | Command |
|---|---|---|---|
| **Rules** (`planner/rules.py`) | nothing (stdlib Python) | decent, predictable | `--planner rules` |
| **LLM scene designer** (`planner/llm.py`) | any OpenAI-compatible endpoint: Gemini, Ollama, vLLM, LM Studio, OpenRouter, Groq… | best | `--planner llm` |
| **Manual / any chatbot** (`prompts/full_spec.md`) | copy-paste into any chat AI | best with big models | `--spec my.spec.json` |
| **Hand-written / your editor UI** | your own tool writes the JSON | exact | `--spec my.spec.json` |

```
voice.mp3 + voice.srt
   │  planner/common.py   parse SRT · detect voice pauses (ffmpeg) · DP-align text to the voice · build captions
   ▼
captions with real timing
   │  planner/rules.py    cast detection · speakers · scene cuts · motifs → layouts  (always runs: it is the fallback)
   │  planner/llm.py      optional: an LLM redesigns each scene (one small JSON per call, validated, auto-repaired)
   ▼
spec.json  ──  planner/validate.py  (captions == SRT words, safe zones, known types, timing coverage, auto-fixes)
   │
   ▼  Remotion (React → MP4)
src/engine/SceneView.tsx → backgrounds.tsx + elements.tsx (+ anim.ts) → out/reel.mp4 → loudnorm → final.mp4
```

---------------------------------------------------------------------------------------------------

## 1. Setup (once)

Requirements: Node ≥ 18, Python ≥ 3.9, ffmpeg/ffprobe, Pillow (`pip install pillow`) for contact sheets.

```bash
npm install                     # remotion, react, fonts
mkdir -p public/fonts && cp node_modules/@fontsource/hind-siliguri/files/hind-siliguri-bengali-{600,700}-normal.woff2 \
   node_modules/@fontsource/noto-serif-bengali/files/noto-serif-bengali-bengali-800-normal.woff2 public/fonts/
npx remotion browser ensure     # only if you have no Chrome/Chromium
```

For English or other scripts, add a font for that script to `public/fonts/` and to `FONTS` in `src/chrome.tsx`.

## 2. Make a video

```bash
# no AI at all
python3 make_video.py --mp3 voice.mp3 --srt voice.srt --out final.mp4 --planner rules

# Gemini (OpenAI-compatible endpoint)
export LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
export LLM_MODEL=gemini-2.5-flash
export LLM_API_KEY=YOUR_KEY
python3 make_video.py --mp3 voice.mp3 --srt voice.srt --out final.mp4 --planner llm

# local open-source model with Ollama
ollama pull qwen2.5:14b          # or llama3.1:8b, mistral-nemo, gemma3 …
export LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=qwen2.5:14b
python3 make_video.py --mp3 voice.mp3 --srt voice.srt --planner auto      # auto = LLM if reachable, else rules

# plan only (spec + preview stills), edit, then render the edited spec
python3 make_video.py --mp3 voice.mp3 --srt voice.srt --plan-only
#   -> out/spec.json and out/sheet_*.png  (LOOK at the sheets)
python3 make_video.py --mp3 voice.mp3 --spec out/spec.json --out final.mp4
```

Other flags: `--page-name "My Page"` (watermark pill), `--hero-female`, `--lang bn|en`, `--browser /path/chrome`, `--concurrency N`.
Render time is roughly 4–5 minutes per 60 s of video on 2 CPU cores.

## 3. The spec format (the contract every planner/AI/editor writes)

```jsonc
{
  "meta": { "total": 127.0, "pageName": "", "lang": "bn" },     // total = voice length + 1.5 s
  "characters": {                                                  // reusable cast, ids are free-form
    "hero":   { "name": "রাফি", "skin": "#A0663A", "ear": "#8F5A33", "shirt": "#5F9D7A", "pants": "#2b3150", "hair": "#141010" },
    "mother": { "name": "মা", "skin": "#9C653D", "shirt": "#B5543A", "pants": "#3b2a20", "hair": "#17120f",
                "lungi": "#7A2E3A", "bun": true, "orna": "#E8B84A" }          // lungi = long skirt/saree; bun/orna = female look
  },                                                               // also: glasses, mustache, long
  "captions": [ { "s": 9.04, "e": 10.33, "t": "“কিরে, {result} দিল?”", "who": "মা" } ],   // {red word}, \n = line break
  "speak":   { "mother": [[9.04, 10.33]] },                       // mouth moves only here AND when the voice is loud
  "tags":    [ { "s": 0, "e": 10.6, "tag": "সকাল" } ],             // big scene chip at top
  "sfx":     [ ["pop", 9.1, 0.3], ["stamp", 28.6, 0.5] ],          // tick, pop, stamp, whoosh, printer
  "scenes": [
    { "s": 3.57, "e": 10.57,
      "bg": { "type": "room", "time": "day" },
      "elements": [
        { "type": "bed", "x": 190, "y": 652 },
        { "type": "person", "char": "hero", "x": 150, "y": 560, "s": 0.8, "pose": "sit", "arm": "phone" },
        { "type": "phone", "x": 246, "y": 467 },
        { "type": "person", "char": "mother", "x": 640, "y": 520, "s": 0.8, "pose": "stand", "flip": true,
          "loop": "walk", "move": [ { "t": 7.4, "x": 420 } ] },                 // walks in
        { "type": "bubble", "text": "?", "x": 330, "y": 230, "at": 9.04 }      // pops when she speaks
      ] }
  ]
}
```

Canvas: **540 × 960 design units** (rendered ×2). Safe content zone **y 115–720**; the tag chip
lives above, captions below. Scenes must be contiguous from 0 to `meta.total`.

### 3.1 Animation — works on every element
`at`, `until`, `enter` (pop, fade, slideL/R/Up/Down, drop, stamp, grow), `exit` (fade, pop),
`loop` (breathe, bob, walk, float, shake, pulse, spin, sway, glow) + `loopAmp`,
`move: [{t, x, y, s, rot, opacity}]` eased keyframes, plus `x y s rot opacity z`.
Times are absolute seconds on the video timeline, so planners can copy caption times directly.

### 3.2 Element catalog (`src/engine/elements.tsx`)
The full prop list is in **`prompts/scene_designer.md`** (that file is also what the LLM reads, so the
docs and the AI never disagree). Summary:

- **Characters:** `person` (sit/stand, 8 expressions, 14 arm poses, timed `exprs`/`arms`, auto lip-sync, tears), `mini`, `crowd`
- **Speech:** `bubble`, `thought`
- **Text & cards:** `title`/`text` (typewriter), `pill`, `card`, `quote`, `badge`, `stamp`, `steps`, `paper`, `note`
- **Data:** `counter`, `gauge`, `progress`, `bars`, `calendar`, `clock`, `heart` (beats), `eyes`, `icon` (20 icons)
- **Devices & props:** `phone` (small in hand, or big with header/lines/typing/big number/loading/icon), `monitor`, `door` (open/close/slam), `window`, `bed`, `sofa`, `desk`, `chair`, `lamp`, `books`, `cup` (steam), `bag`, `plant`, `tree`, `house`, `car`
- **Effects:** `particles` (stars, rain, snow, hearts, confetti, sparkle), `overlay`, `ecg`, `spotlight`, `arrow`, `lines`, `shape` (raw SVG), `image`, `group`
- **Backgrounds** (`src/engine/backgrounds.tsx`): plain, gradient, room (day/morning/evening/night/dark), living, split (two rooms + doorway), street, exterior (house front), office, classroom (board text), shop, park, nightsky — all accept `dark`, `tint` (flashback), `glow`, animated darkening.

`examples/catalog.spec.json` uses every kind of element — render it to see them all:
```bash
cp examples/catalog.spec.json src/spec.json
ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t 24 public/voice.mp3 -y
python3 -c "import sys;sys.path.insert(0,'planner');from common import write_rms;write_rms('public/voice.mp3','src/rms.json')"
node gen-sfx.mjs 30 && node tools/stills.mjs && python3 tools/contact_sheet.py out/stills out/catalog
```

## 4. How each planner works (so you can port it to any language or AI)

### 4.1 Alignment (`planner/common.py`) — the part people usually get wrong
SRT blocks from TTS tools cut sentences in the middle and drift from the real audio (the Rafi SRT
drifted ~4 s by the end). So:
1. `split_units` joins all SRT text and splits it into clauses at `। ? ! . ,` and quote edges.
2. `speech_segments` runs `ffmpeg silencedetect` (‑35 dB, 0.12 s) to get the real speech islands.
3. `align` is a dynamic programme giving each clause a contiguous run of speech segments,
   minimising (duration − chars × speaking-rate)², rewarding cuts on long silences and weakly pulling
   toward the SRT's own times. Long clauses are split at their longest internal pause.
4. `units_to_captions` merges short pieces into 1–2 line captions. Caption **words never change**;
   the validator proves it by comparing word lists with the SRT.

### 4.2 Rule planner (`planner/rules.py`)
- **Cast:** role lexicon (মা, বাবা, দাদা, স্যার, বন্ধু … mother, father, teacher, friend) + proper names
  (frequent sentence-initial tokens that are not common words). Each role has a fixed colour preset,
  so a character looks the same in every video.
- **Speakers:** a quoted caption belongs to the first character mentioned in the narration just before it.
- **Scene cuts:** on place/time change, end of a quote block, pauses ≥ 0.55 s once a scene is > 3.6 s,
  motif change, or 7 s max. Cuts sit in the middle of pauses.
- **Motifs → layouts:** lexicons (`MOTIFS`, `EMOTIONS`, `TIMES`, `PLACES`) decide the template:
  hug, emotional close-up (dark), phone/number close-up (spoken numbers like "তিন দশমিক আট তিন" → ৩.৮৩),
  paper + stamp, clock, calendar, crowd, door (close/slam/knock), arrival walk-in, dialogue with bubbles,
  thought cloud, lie ✕, leave stamp, money, heart beats, and an ending "lesson" card.
- **Variety:** the same close-up template is not used twice in a row.

**Add a motif in 3 lines:** add `('rain', ['বৃষ্টি', 'rain'])` to `MOTIFS`, then in `build_scene`:
```python
if m0 == 'rain':
    els.append(dict(type='particles', kind='rain', x=270, y=480, count=40))
```

### 4.3 LLM scene designer (`planner/llm.py`)
The LLM is **not** asked to invent timing or captions — that is what makes small open models reliable.
For each scene it gets: the time window, the captions in it (with times and speaker), the cast, the
previous scene, and the rule draft; it returns `{bg, elements, sfx?, tag?}`. The answer is validated;
errors are sent back once for repair; if it still fails, the rule scene stays. Any model that speaks
the OpenAI `/chat/completions` format works (Gemini's OpenAI endpoint, Ollama, vLLM, llama.cpp server,
LM Studio, OpenRouter, Groq, Together…). `tools/mock_llm.py` is an offline fake server for testing.

Model tips: 7–8B models work per-scene but keep the draft mostly; 14B+ (Qwen2.5-14B, Gemma-3-12B,
Llama-3.1-70B) or Gemini Flash/Pro redesign scenes well. Temperature 0.3–0.5.

### 4.4 Manual mode with any chatbot
Run `--plan-only --planner rules`, then follow `prompts/full_spec.md`: paste the designer prompt and
`out/spec.json` into any chat AI, save its answer, render with `--spec`.

## 5. Extending the renderer

- **New element:** in `src/engine/elements.tsx` write `const Kite: R = (el, c) => <g>…</g>;` (draw around
  (0,0); `c.t` = seconds, `c.f` = frame in scene), add `kite: Kite` to `ELEMENTS`, add `'kite'` to
  `ELEMENTS` in `planner/validate.py`, and document its props in `prompts/scene_designer.md`.
  Animation, timing and z-order come for free.
- **New background:** add a component and a `case` in `Background` (`backgrounds.tsx`) + `BGS` in validate.py.
- **New character look:** add a preset in `PRESETS` (rules.py); new body features go in `src/figures.tsx`
  (`Person` already supports bun, orna, lungi/saree, glasses, mustache, tears, scared face).
- **New sound:** add a generator to `gen-sfx.mjs` and its name to `SFX` in validate.py.

## 6. Building your "ultimate video editor" on top

The spec is the editor's document model:
- **Live preview:** `@remotion/player` renders `<Video/>` in the browser from a spec object — swap the static
  `import spec from './spec.json'` in `src/data.ts` for props (`inputProps`) to edit without rebuilding.
- **Timeline UI:** scenes = clips (`s`/`e`), elements = layers with `at`/`until`, `move` = keyframes.
- **AI buttons:** "redesign this scene" → call `llm.design_scene(spec, i)`; "fix layout" → run `validate.py`
  and show warnings; "no-AI mode" → `rules.plan()`.
- **Server render:** `@remotion/renderer` (`renderMedia`) or Remotion Lambda for scale.
- Keep the validator in the loop for anything an AI writes.

## 7. QA checklist (before you publish)
- Caption words equal the SRT (validator error otherwise); Bengali conjuncts (শিক্ষা, প্রস্তুত) look right.
- Look at `out/sheet_*.png`: no text over faces, nothing in the top 115 / bottom 160 design px except chrome, tag chip readable.
- `ffprobe final.mp4`: 1080×1920, 30 fps, duration = meta.total, audio length = video length.

## 8. Troubleshooting
- **Blank scene** → an element type typo (validator warns "unknown type … dropped") or a JS error: run `npx tsc --noEmit`.
- **Captions early/late** → noisy voice: try `speech_segments(mp3, noise='-30dB')` or `-40dB`.
- **Mouth never moves** → speaker id in `speak` must match a `characters` key.
- **LLM returns prose** → the client retries without `response_format`; some servers need a JSON-capable model.
- **Out of memory while rendering** → lower `--concurrency`.

## 9. File map
```
make_video.py                one-command pipeline
planner/common.py            SRT, pauses, alignment, captions          (stdlib)
planner/rules.py             rule-based planner (no AI)                (stdlib)
planner/llm.py               OpenAI-compatible LLM scene designer       (stdlib)
planner/validate.py          validation + auto-fix (also a CLI)         (stdlib)
prompts/scene_designer.md    system prompt + element catalog for any AI
prompts/full_spec.md         copy-paste prompt for manual mode
src/data.ts                  spec types + loader
src/engine/anim.ts           enter/loop/exit/keyframe animation
src/engine/backgrounds.tsx   12 backgrounds
src/engine/elements.tsx      50+ elements
src/engine/SceneView.tsx     scene renderer
src/figures.tsx  src/chrome.tsx  src/theme.ts   characters, stage/captions/tag chrome, palette
tools/stills.mjs  tools/contact_sheet.py  tools/mock_llm.py  gen-sfx.mjs
examples/catalog.spec.json   every element in 24 s
examples/rafi.srt + rafi.rules.spec.json   real story planned with no AI
```
Sound is procedural (no copyrighted music). Characters are original flat-vector drawings.
