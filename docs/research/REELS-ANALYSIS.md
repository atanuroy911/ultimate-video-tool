# What the high-retention reels do (8 reels, measured and watched)

Source: the owner's folder `fb-shorts-example/` (8 files, 13 s to 158 s). Measured with [`scripts/analyze_reels.py`](../../scripts/analyze_reels.py); raw numbers per reel are in `docs/research/reels/*.json`, a contact sheet of every reel is `docs/research/reels/<name>.png` (one frame per 1 to 3 s), and the same measurements for three of our own exports are in `docs/research/ours/`. Speech was transcribed with the project's own recogniser (`large-v3`, English), so word times are approximate on stylised voices.

**Method and its limits.** *Hard cuts* come from ffmpeg's scene score at 0.30; they miss zooms and cross-fades. *Picture swaps* come from the frame-to-frame difference at 10 fps (a swap is a mean change above 14 of 255). *Longest still* is the longest run with almost no change. Eight reels is a small sample and every one was picked by the owner as a good one: nothing here says what makes a reel *fail*.

## 1. The eight reels

| File | Length | What it is | How it keeps the eye | Sound |
|---|---|---|---|---|
| `reel 3.mp4` | 63 s | A story about property investing told as a **Mr Bean-style cartoon**: one AI-made picture for every 2 to 3 s | a new picture about every 2.3 s (26 hard cuts), the same character in every picture so the story reads as one; **one huge yellow word at a time in the middle of the screen**, synced to the voice; ends on a "Subscribe" button and a wink | voice at 199 words a minute, -14.4 LUFS |
| `reel 2.mp4` | 85 s | A health explainer in **one drawing style** (grey pencil line art, same couple of stick people throughout) | 14 picture swaps, so each picture lasts about 6 s, but it is **never still**: a slow push-in and drifting detail on every picture; captions sit at the top in 2 to 4 word groups with **one yellow keyword**; each picture is one idea, in order: stress, the heart, a hug, oxytocin, calm | voice 154 wpm, quiet (-23.7 LUFS) |
| `reel 5.mp4` | 158 s (landscape) | A survival diary ("Day 1 ... Day 45") | **mixed media on purpose**: comic panels, a notebook page, a UI progress bar, a title card ("DAY 26", "LIGHT", "THE LOG"), a map of lit windows; 67 picture changes, about one every 2.3 s, and a title card whenever the story jumps | voice 185 wpm, -15 LUFS |
| `reel 7.mp4` | 101 s | One **talking stick figure** in a fixed studio room | the picture does not cut at all; the figure's mouth, face and hands move all the time and **one word at a time appears above his head** | voice 176 wpm, -14.1 LUFS |
| `reel.mp4` | 144 s | **Kinetic typography** on black with a red and a white stick figure | no photo or art; every 1 to 2 s a new line of type or a small prop (DNA strand, anchor, shield, thermometer) arrives; **the key word turns red and grows**; the figures act out the sentence; ends on "DAY 08 COMPLETE" | voice 181 wpm, -14.1 LUFS |
| `reel 8.mp4` | 21 s | A meme: two animals at a restaurant table, a "POV:" caption | the animals swap species and expression to match each line ("I'm already full", "Go ahead"), with "Her:" and "Me:" labels and a subtitle; ends on "FOLLOW FOR MORE." | no speech, music and effects, -14.3 LUFS |
| `reel 6.mp4` | 31 s | "POV: it's mid 2000s and you discovered a channel called Animax": a filmed old TV playing anime openings | the **picture inside the TV** changes every 0.5 to 1.5 s; a fixed two-line caption above | no speech, music, -14.1 LUFS |
| `reel 4.mp4` | 13 s | A small animated creature composited onto a real street | one continuous animation (it runs in, falls, hugs, holds up a flower); "for you!" appears only at the end | music and effects, -20 LUFS |

## 2. Numbers

| | Length | Picture swaps a minute | Longest almost-still | Share of time moving | Words a minute | Loudness |
|---|---|---|---|---|---|---|
| reel 3 (Bean) | 63 s | 28.5 | 1.0 s | 78 % | 199 | -14.4 |
| reel 5 (diary) | 158 s | 27.0 | 4.9 s | 5 % | 185 | -15.0 |
| reel 2 (line art) | 85 s | 9.8 | 1.8 s | 57 % | 154 | -23.7 |
| reel 7 (talker) | 101 s | 0 | 6.2 s | 14 % | 176 | -14.1 |
| reel (typography) | 144 s | 2.1 | 5.7 s | 19 % | 181 | -14.1 |
| *our* cartoon (`2026-10-23-untitled`) | 204 s | 12.0 | 3.0 s | 45 % | 172 | -14.0 |
| *our* talk snippet (`2026-10-24-p_snippet_ams_2`) | 106 s | 21.5 | 1.2 s | 66 % | 247 | -14.1 |
| *our* short (`2026-10-24-why-do-rich-people-get-richer`) | 30 s | 13.9 | 1.7 s | 49 % | 155 | -14.0 |

* **Speech runs at 154 to 199 words a minute and starts at 0.0 s.** Not one reel has an intro, a logo or a pause before the first word. Ours also start at 0.0 s and run at the same speed, so this is not a gap.
* **Loudness:** seven of the eight sit at about -14 LUFS, the usual target for social platforms; ours do too (-14.0). Not a gap. (Reel 2 is quiet; it is the one with the slowest swaps.)
* **A picture for about every 7 words** (reel 3: 7.7 words a picture, reel 5: 7.1), about 2.3 s at their speed. Where pictures change slower (reel 2, 6 s a picture) the picture itself moves all the time.
* **Do the changes land on the spoken words?** In the two reels with enough changes to say (reel 3 and reel 5), 77 % and 84 % of the changes fall within 150 ms of a word start. Because speech is so dense, a random time would do 60 % and 61 %, so the lift is 17 to 23 points: **real but modest**; this is evidence for "cut on the word" but not proof that every cut is chosen by meaning.

## 3. What they have in common (and what we do not do yet)

| # | Pattern | Seen in | Today in our tool |
|---|---|---|---|
| 1 | **One look for the whole video**: the same drawing style, palette and recurring character in every picture | reels 2, 3, 5, 7, typography | Partly. Themes exist, but pictures come from different sources (icons, stock, stickers); nothing keeps one generated-art style across a video |
| 2 | **One idea per picture, in the order of the argument**; the picture shows the thing the sentence is about (a calculator for "20 %", a bank for "mortgage", a clock for "time") | reels 2, 3, 5 | The director picks an element per scene from a catalogue; there is no step that *draws a new picture for the sentence* |
| 3 | **The text is a second channel**: a single word at a time in the middle (reel 3), a word above the head (reel 7), 2 to 4 word groups with one highlighted word (reel 2), whole lines of type with a red key word (typography) | all five narrated reels | We have word-timed captions and a highlight; we do not have the **single huge centre word** or **keyword-in-red-and-grown** styles as presets |
| 4 | **Never still**: either a new picture every 2 to 3 s, or one picture that moves the whole time (push-in, mouth, hands) | all | Meets it by the 3-second rule on average; the generated-art style would need a push-in on every still |
| 5 | **Mixed media inside one video** for rhythm: a title card at each jump, a UI bar, a notebook, a map | reel 5, typography | We have text cards and info cards; no "day counter" / progress-bar card or document-on-screen cards |
| 6 | **An end card that asks for the follow**: a Subscribe button, "FOLLOW FOR MORE.", "DAY 08 COMPLETE" | reels 3, 8, typography | Not built |
| 7 | **No dead start**: the first frame already shows the subject and the first word is spoken at 0.0 s | all | Same, by measurement |
| 8 | **The silent ones** (4, 6, 8) are built on *recognition*: a known meme, a known TV, a known pose, with music and effects | reels 4, 6, 8 | Out of scope for a narrated tool unless the owner wants music-only reels |

## 4. What this means for the plan

1. **The model of a good video is "one image per ~7 words, drawn for the sentence, in one style, with a push-in, and the key word on screen".** That is the *still-series style* of Phase 4 (P4-08) plus a generated-image fill, and it needs **no video generation at all**: reels 2, 3 and 5 are stills with motion. The 3 to 4 s silent clips from LTX or Wan are the exception, not the base.
2. **These eight reels are the first real reference set** for P4-01 in place of editor-marked recordings: each has the cut times, the spoken words with times, and the caption style. They can be used to check that our director's picture changes per sentence, words per picture and caption style are in the same range. They cannot judge *meaning*: nobody has marked which word each cut should land on.
3. **Style bible module** (new): fix one look (line art, cartoon of a named character, or kinetic type) for the whole video before any picture is drawn; every image prompt inherits it. This is the main thing the reels have that our pictures do not.
4. **Caption presets** (new, small): *single centre word*, *keyword grown and coloured*, *two to four words with one highlight*.
5. **End card** (new, small) and a **day/step counter card**.

These are added to [ROADMAP.md](../ROADMAP.md) Phase 4 as P4-09 to P4-12.

## 5. Why they work: the content, not the cuts (read from the transcripts)

The owner's point: the number of cuts is not the thing; the director must decide from the content. So here is what the five spoken reels have in common **in what they say**, read from the transcripts in `docs/research/reels/*.json` (my reading, not a measurement; I have no view counts, only the owner's word that these were watched the most).

| | Opening line (the first 3 seconds) | What kind of line it is |
|---|---|---|
| reel 2 | "Touching your girlfriend's boobs can actually save your life. It is not a joke. It is science." | a **taboo-sounding claim, then an instant guarantee** ("it is science") |
| reel 3 | "How do rich people turn one property into five?" | a **question the viewer wants answered**, about money and status |
| reel 7 | "Never put your real name on your bank account." | a **forbidden-sounding instruction**, second person, no warm-up |
| reel (typography) | "The dual mating strategy is the split in female desire between two different kinds of man..." | a **named, hidden mechanism** about sex and status ("alpha fucks, beta bucks") |
| reel 5 | "...most falls happen in the half second after you decide you are safe." | a **world with stakes**, in second person and present tense ("you stand in the balcony doorway") |

**What each one does that the pictures cannot do for it**
1. **A hook that opens a loop in one sentence**, about something people care about deeply (money, sex, fear, safety, status), phrased as a surprise, a question or a prohibition. No greeting, no topic announcement.
2. **A promise of hidden knowledge** ("the secret", "wealthiest families understood this generations ago", "is it legal? the system wrote the rules"). The viewer stays to be let in.
3. **A shape, in this order:** claim, then the stakes (what you lose), then the *mechanism* in plain steps, then a twist or objection ("But he doesn't stop there", "But here's something fascinating", "Is it legal?"), then a one-line payoff ("the rich don't hide money, they structure it"), then the ask (follow). Steps are literally numbered when the content is a procedure ("Step one... Step 2... Step 3").
4. **Concrete things, not abstractions:** $200,000, 20 %, $40,000, $2,000 a month, 32 days of food, 40 seconds of noise, "three fingers, a pause, three fingers". Every number and noun is something a picture can *show*, which is why one picture per sentence works.
5. **Contrast and a villain:** rich against most people, the taxman, creditors, the system, the lit ones. The viewer always knows who is on whose side.
6. **Short sentences, second person, a re-hook every 15 to 20 seconds** ("But...", "Now...", "Here's the secret", a new Day).
7. **Content decides the form**, which is the owner's point exactly: *steps* get a held character and a step counter (reel 7); a *story with a timeline* gets fast pictures and a title card at each jump (reels 3 and 5); a *science explanation* gets one idea per picture, a slow push-in and a highlighted keyword (reel 2); an *argument made of terms* gets typography (the black reel). The same number of cuts would be wrong in each.

**What the director has to read from a script, then** (a list for the Phase 4 and 5 modules, `understand.*`): the *kind* of content (steps, story, explanation, argument, list, opinion); the *hook* and whether it is strong (and if not, a rewrite proposal that keeps every fact); the *beats* in the order above; the *concrete nouns and numbers* (these are the picture candidates and the words to put on screen); the *loops and turns* ("but", "here's the secret", a question) where a new picture or a card should land; and the *chapter jumps* (Day 26, Step 2) where a title card belongs. Pace, medium and caption style are then *consequences* of those readings, not settings.

## 6. Reel 9: a long story (added 2026-10-28)

`reel 9.mp4`: 12 min 46 s, landscape (1280x714), a second-person survival story ("You took the quietest job on the coast, thirty days alone"), cartoon scenes of one hero (grey beanie, yellow scarf) at a lighthouse. Measured: 2,296 words at **180 a minute**, first word at 0.0 s, -14.4 LUFS, 143 hard cuts (**11 a minute, a picture held 4.9 s at the median, 17 s at the longest**).

| What it shows | So the director should know |
|---|---|
| **A long story is paced slower than a short reel**: about 5 s a picture, against 2.3 s in the 60 s reels | pace follows the length and the tension of the content. A slot's length is not a constant: `vt/reel/slots.py` now lets a picture stay 1.6 times longer when the video is over three minutes |
| **One world, one hero, one palette**, and a **second visual family** that returns on purpose: blueprint-style cards ("RESOURCES: WATER 250 L, FOOD 12 TINS", a cutaway of a rain barrel, a map of the coast, a two-panel "preparation / the descent" comic) | a story needs at least two media: *scenes* for what happens, *diagrams and cards* for facts (counts, supplies, maps, rules). Our info cards (value card, compare, counts) are the diagram family; the reading should mark "this sentence is a fact list" |
| **Establishing shots at chapter starts** (the lighthouse from far away, the boat, the cliff, the view from the balcony), then closer shots inside | the reading should mark where a chapter starts (a day, a place) so the first picture of it is wide |
| **Concrete numbers become pictures**: "Twenty tins of food", "a hundred and forty steps", "three hundred liters of rainwater", "Day one" | same rule as the short reels: numbers and nouns are the picture candidates, and the card family shows the exact figure |
| **Rising stakes with a controlled reveal**: the radio goes silent, the coast glows orange, a ship wrecks; shots get darker and wider as danger grows | the picture's mood follows the tension of the sentence, so the reading needs a tension value per sentence for the style prompt |

What this does **not** show: why 12 minutes holds attention (no retention curve is available), or how the hero stays consistent from picture to picture (the maker's tool is unknown). Our test reel (section 7 of the evidence, `docs/evidence/2026-10-27/reel-pipeline.md`) keeps one figure only by repeating a text description in every prompt, which is weaker than these pictures.
