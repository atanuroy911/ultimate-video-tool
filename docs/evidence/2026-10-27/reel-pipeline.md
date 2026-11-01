# The reel pipeline, run for real (2026-10-27 to 28)

**What was run.** An original 15-sentence English script ("Why do rich people never keep their money in one place? ... Step one ... follow for more"), made through the Studio's own API on the scratch server with `options.look = "reel"`: Kokoro voice, speech recognition, the reading by the local AI (Ollama `gemma4`), one picture drawn for each slot by Z-Image Turbo on the V100, captions with the key word lit, plain cuts, render, audio mix.
Script: [scripts/run_reel_check.py](../../../scripts/run_reel_check.py). Result video: [reel-test-split-your-money-9x16.mp4](reel-test-split-your-money-9x16.mp4) (33.3 s, 1080x1920, H.264 + AAC). Frames looked at: [shots/reel-test-sheet3.png](shots/reel-test-sheet3.png).

| Step | Result |
|---|---|
| Reading (`vt/reel/reading.py`) | AI answered every window; kind `steps` (the numbered turns decided it, not the model), style `cartoon`, hook "question" 0.6 |
| Slots (`vt/reel/slots.py`) | 16 slots for 33 s, 0.7 to 3.2 s each; "Step one / two / three" became title cards |
| Pictures (`vt/comfy/still.py`, workflow `zimage_t2i`) | 11 drawn at 720x1280; about 13 s each warm at 576x1024, 220 s for the whole plan including the first load |
| Render | 75 s to 2 min on the CPU renderer; audio mixed; **no green frames** (0 of 333) |

## What looked right, and what did not (from the frames)
* **Right:** one figure in the same beige coat in every picture, scenes that match the sentence (a bank, a coin into a slot, a chart, a pile of coins), step cards, the key word lit in the caption ("secret", "mistake", "follow"), sharp pictures, a plain cut on each sentence.
* **Not right yet:** the figure's face and size drift from picture to picture; small text drawn inside pictures is garbled ("BAN RLK"); the caption pill covers part of the picture; caption styles are only the old pill (the reels use a single huge centre word, or the key word enlarged); no end card beyond the spoken "follow for more"; the first two seconds are a plain picture, not yet a hook treatment.

## Bugs found by this run, and fixed
| Bug | Cause | Fix | Test |
|---|---|---|---|
| **Every render hung for 20+ minutes at "assemble 99 %"** (GPU and CPU alike) when the Studio had been started without a console | `vt.util.run` let the child process inherit the server's stdin, an invalid handle; HyperFrames' ffmpeg step then waited on it | `stdin=subprocess.DEVNULL` in `vt/util.py::run`, plus a stall watchdog (`stall_seconds`, 300 s for renders): a process that prints nothing is stopped and the CPU is tried | `tests/test_reel.py::test_a_command_that_goes_silent_is_stopped_not_waited_for` |
| A bright green wipe across the first frames of a scene | the motion recipes (`vt/compose/motion.py`) put the theme accent's gradient transition on scene changes | new motion level `cuts` (plain cuts, element motion kept); the reel look sets it | `tests/test_reel.py::test_the_cuts_motion_level_keeps_plain_cuts` |
| Pictures looked blurred and washed out | the contrast engine put a blurred panel scrim over every picture to protect text that is already in its own pill | the reel plan uses no scrim | looked at: [reel-test-sheet3.png](shots/reel-test-sheet3.png) |
| A title card crashed the plan | `Title` needs `at_word` | set to the slot's first word | `tests/test_reel.py::test_a_reel_plan_without_pictures_is_valid_and_has_cards` |
| Pictures were soft | drawn at 576x1024 then enlarged 1.9 times | workflow size 720x1280 (version 2) | looked at |

## Not done
Caption presets (P4-11), the style bible as a first-class artifact (the style is picked by the reading and stored in `reel_report.json`), a consistent figure that is more than a text description, a hook treatment for the first seconds, long-form checks (reel 9 is 12 minutes; the longest test here is 33 s), Bangla scripts, and a person watching and listening to the result against a checklist (P10-17).
