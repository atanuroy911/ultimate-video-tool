# Plan: voice direction and vocal events in the director

Owner's request (2026-10-28), from the Breeze TTS 2 description:
* **Voice Direction**: clone a voice from reference audio while steering **tone, emotion, pace and delivery**.
* **Vocal Events**: expressive inline events in the text, `(laugh) (cough) (clears throat) (sigh)` in English and `[笑] [咳嗽] [清嗓子] [叹气]` in Chinese.
* "We need these in direction as well": the director (the AI that reads the script and decides how the video is made) must be able to use them, not only a person typing them.

## 1. One vocabulary, many engines
`server/vt/voice_direction.py` defines what a director can ask for, per sentence, **independent of the voice model**:
| Thing | Written in a script as | Meaning |
|---|---|---|
| **Direction** | `{slowly, with a restrained, serious tone} Never put your name on it.` (curly braces at the start of a sentence) | a free-text instruction for how to deliver this sentence |
| **Vocal event** | `(laugh)`, `(sigh)`, `(cough)`, `(clears throat)`, `(breath)` anywhere; the Chinese forms and VoiceStudio's `[laughter]` and `[sigh]` are accepted too | a sound that is not a word |
Any other bracket or parenthesis is ordinary text and stays (`(about 20 dollars)` is spoken). The captions, the word timings and the transcript are made from the **words only**; notes and sounds never appear on screen.

## 2. Each engine speaks a dialect
`render()` turns a parsed sentence into what the engine can use, and says what it could not do:
| Dialect | Used by | Events | Direction |
|---|---|---|---|
| `breeze` | Breeze TTS 2 (ComfyUI `breeze_direction`, `breeze_design`) | `(laugh) (sigh) (cough) (clears throat)` | free text (CFG 4); with a reference recording the identity is kept and the delivery steered |
| `omnivoice` | OmniVoice (ComfyUI, and VoiceStudio's default engine) | `[laughter] [sigh]` | only `whisper`; anything else becomes a **speed change** |
| `cosyvoice` | CosyVoice 3 | `[laughter] [breath]` | free text |
| `voxcpm2` | VoxCPM2 | none | a parenthetical prefix, adherence varies |
| `indextts2` | IndexTTS-2 | none | an emotion text or vector |
| `none` | Edge, Kokoro, KittenTTS, MMS | none: dropped | none: the pace words ("slowly", "quickly") become a speed factor (0.9 or 1.1) |
Nothing is silently pretended: the sentence's record keeps `direction.dropped` (for example "(cough) is not something VoiceStudio default (OmniVoice) can do"), and the Details log can say it.

## 3. Who writes the notes
1. **The author**, in the script, with the syntax above. Always honoured when the engine can follow it.
2. **The director**, when the author left a sentence plain: `server/vt/voice_direction.py::suggest()` asks the AI for notes (JSON schema, validated, one retry; `check` rejects a note for a sentence that does not exist), then **caps events at one for every six sentences** and never changes a word. With no AI, **rules** give only what punctuation says ("!" -> energetic and emphatic, "..." -> slow and thoughtful) and **never an event**: a rule does not invent a laugh.
3. It only runs when the chosen voice can follow direction (`dialect != none`), so a Kokoro or Edge video costs nothing extra and is spoken exactly as before (the stage's cache key is unchanged for those voices; nothing already made is re-spoken).
4. The project option **`voice_direction`**: `auto` (default) or `off` (the notes are stripped and ignored).

## 4. How it flows
```
 script  ->  split sentences  ->  parse notes and events (author's)
                              ->  suggest() for plain sentences (director's), only if the voice can follow
                              ->  render() for the engine's dialect  ->  speak each sentence (cached by text, voice, direction)
                              ->  words + timings from the words only  ->  the rest of the pipeline is unchanged
```
`tts.synthesize(text, ..., notes=..., direction=..., language=...)` carries it; `Pipeline.stage_voice` is the caller.

## 5. Still to do
| Task | What | Done when |
|---|---|---|
| VD-1 | **Timing of sound events.** A laugh or a sigh adds real audio time that the letter-count word timing spreads over the words. Fix with word alignment (`audio.align_words`, Phase 4) or by measuring each sentence's event gap | caption words land on the spoken words within 100 ms on a sentence with an event |
| VD-2 | **The editor**: in the Text panel, a sentence's *Delivery* field and a row of sound chips (laugh, sigh, cough, clears throat); *Say it again* re-speaks that one sentence and splices it (one undo step) | a person changes one sentence's delivery without redoing the video |
| VD-3 | **The New flow**: a short tip under the script box ("`{whispering}` at the start of a sentence, `(laugh)` anywhere") and a switch *Let the AI direct the delivery* (the `voice_direction` option) that is shown only for voices that can follow it | the switch appears for Breeze and not for Edge |
| VD-4 | **Voice cast from the reading**: `server/vt/reel/reading.py` suggests a *voice design* description from the content (a calm woman for a health explainer, a brisk man for steps) and the director passes it to `design:` voices | a reel gets a voice chosen from its content |
| VD-5 | **Measure whether direction helps**: the same script with and without notes, listened to by a person; the notes that do not change what is heard are not worth sending | a short table in the evidence |
| VD-6 | **Chinese**: the Chinese tag forms are parsed and rendered for Breeze; a Chinese script has not been run end to end | one Chinese sentence spoken with `[笑]` |
| VD-7 | **One voice for the whole script** (owner, 2026-10-31: "generating audio in chunks gives multiple voices and tones that are incoherent"). **Built** in `server/vt/voice_lock.py` and `server/vt/tts.py::synthesize`: a designed voice is cast once on the script's opening and every sentence is cloned from that reference (VoiceStudio's default voice gets a profile made from it); every VoiceStudio request carries a fixed seed; whether the script is directed is decided once, so the workflow never switches mid-script; a pace note moves one sentence by at most 5%; each sentence's speech is brought to one level; every take's voice signature is compared with the reference and a drifted take is spoken again with other seeds. Tests: `tests/test_voice_lock.py` (fakes). **Not yet**: the thresholds are uncalibrated (no real takes measured); a listening test; speaking a paragraph at a time for continuous prosody (needs measured word times, P4-02) | on three scripts (English, Bangla, a dialogue) on the real servers, no sentence is flagged and a person hears one narrator; before/after pair kept in evidence |

## 6. Tests (all in the repository, run on every change)
`tests/test_voice_direction.py`: notes and events are taken out of the words; ordinary brackets stay; the Chinese and VoiceStudio forms; each dialect's rendering and its `dropped` list; a voice without direction keeps the speed; `synthesize` keeps notes out of captions and timings and passes the direction through; the director's suggestions, the one-in-six cap, the rules' notes and no invented events.
`tests/test_comfy_voice.py`: the workflow is checked against the server before queueing, written into, cached; a cloned voice uploads its recording and transcript; the choice of model follows language and direction; a voice is made on the worker that has the model.
