# The end-to-end test plan

What it takes to say "this video tool works" and to keep saying it. It covers the whole system: the Python backend, the engines (Ollama, ComfyUI, VoiceStudio), the Studio, the renderer, the setup, and **the finished video itself**. It is the plan the owner asked for on 2026-10-28 ("plan the tests end to end"). The state of each layer today is in [STATUS.md](STATUS.md); the logs that prove it are in `docs/evidence/<date>/`.

## 0. Principles
1. **Truth is a log.** Nothing is "done" without a saved log or a looked-at frame in `docs/evidence/`. `scripts/run_all_checks.py` writes them.
2. **Test the layer that can fail.** Contracts and logic are tested without a GPU against **fake servers** (a fake ComfyUI, a fake VoiceStudio); the real servers are tested by a small number of **smoke runs** that use real models and are slow; the **video is judged by a person against a checklist**, because a pipeline that passes every unit test can still make a video that makes no sense (the owner's point of 2026-10-27).
3. **A bug found by testing gets a regression test first**, and the test must fail without the fix (checked by reverting the fix once).
4. **Tests never touch the owner's data.** Mutating suites run on a scratch server (`VT_DATA`, port 8777); tests that write to the repository's data folders monkeypatch `paths.DATA`; `tests/conftest.py` isolates `projects/`, `settings.json` and the glossary.
5. **Real GPU work is budgeted and named.** A real-model test says what it spends (minutes of GPU, which card) and is opt-in (`VT_REAL=1`, or `-m slow`).
6. **Failure is part of the plan.** Every external dependency has an injected-failure test: down, slow, wrong key, missing model, full disk, cancelled.

## 1. The layers
| Layer | What it proves | How it runs | Where it lives | Cost |
|---|---|---|---|---|
| **L1 Unit and contract** | each function and module does what its contract says; every module has a summary, an example, a cost and a log line; the registry lints clean | `pytest -m "not slow"` | `tests/` (92 files; 880 or so tests) | about 6 minutes, no GPU |
| **L2 Component with fake servers** | the clients and the routing work against a pretend ComfyUI, VoiceStudio and Ollama: health, errors in words, caching, workers, direction dialects, keys never returned | same | `tests/test_voicestudio.py`, `tests/test_comfy_voice.py`, `tests/test_comfy.py`, `tests/test_voice_direction.py`, `tests/test_reel.py` | seconds |
| **L3 Equivalence** | the module path gives byte-identical output to the old pipeline; a second run changes nothing | `pytest tests/test_modules_equivalence.py` | | minutes |
| **L4 Slow** | real frames are rendered, the real speech model runs, goldens match | `pytest -m slow` | `tests/golden/`, the slow marks | about 15 minutes, CPU |
| **L5 Browser** | every Studio screen behaves: New flow, editor, Settings, Engines, Details log, dashboard | `node studio/e2e/<suite>.mjs` against the scratch server | `studio/e2e/` (about 28 suites) | 10 to 40 minutes |
| **L6 Live engines smoke** | the real servers are reachable and each does one real job | `python scripts/run_all_checks.py --live` | `scripts/run_all_checks.py` | about 15 minutes of GPU |
| **L7 End-to-end videos** | a real script becomes a real video through the real servers | `python scripts/run_reel_check.py` and the acceptance corpus (section 4) | `docs/evidence/` | 5 to 30 minutes each |
| **L8 Human review** | the video makes sense, sounds right, looks right, and a viewer would not leave | the checklist (section 5), by a person | evidence tables | 5 minutes a video |
| **L9 Non-functional** | speed, memory, disk, concurrency, security, accessibility | section 6 | | varies |
| **L10 Clean machine** | the setup works from nothing on a computer that has only Windows and a GPU | a VM or a second PC | evidence | an hour |

## 2. The automated battery: `scripts/run_all_checks.py`
One command, with flags, that runs what can be run and writes `docs/evidence/<date>/checks.md` (a table: step, command, result, seconds, log file):
| Step | Command | Needs |
|---|---|---|
| docs | `python scripts/check_docs.py` | nothing |
| types and build | `tsc --noEmit`, `npm run build` in `studio/` | node |
| unit | `pytest -q -m "not slow"` | nothing |
| slow | `pytest -q -m slow` (flag `--slow`) | ffmpeg, a browser |
| browser | the suites listed in `scripts/collect_evidence.py` against a scratch server it starts and stops itself (flag `--e2e`) | a browser |
| live engines | `--live`: health of the three engines; one Ollama answer; one Z-Image picture; one voice sentence per ready voice workflow; their timings against the budgets in section 6 | the GPU machine |
| reel | `--reel`: a 15-sentence script to a finished video, then the automatic judges (section 3) | the GPU machine |
A step that cannot run (no server) is recorded as **skipped, with the reason**, never as passed.

## 3. The automatic judges (a video is checked before a person sees it)
Implemented as `judge.*` modules and used by both the tests and the director; each returns numbers and a plain sentence.
| Judge | Rule | Threshold (starting values, tuned on the nine example reels and the owner's own videos) |
|---|---|---|
| first frame | the first frame is not blank and has the subject; the first word is spoken within 0.3 s | pass or fail |
| nothing still | no stretch longer than 3.0 s without a visible change (picture swap, push-in, caption word, character motion); measured by frame difference at 10 fps | longest still at most 3.0 s (the tool's own rule; the reels reach 6.2 s with a moving figure, so a moving subject is credited) |
| pictures per words | words per picture in the range of the content kind (steps 6 to 12, story 5 to 9, explanation 6 to 10) | within range for at least 90 % of pictures |
| change on the word | the share of picture changes within 150 ms of a spoken word start | at least 75 % (the reels: 77 % and 84 %; chance is about 60 %) |
| facts | every number, name and claim on screen is in the speech (`judge.facts`) | zero invented |
| captions | each caption is readable (contrast at least 4.5:1), inside the safe area, and matches the spoken words | zero violations |
| loudness | integrated loudness near -14 LUFS, true peak under -1 dBTP | -16 to -12 LUFS |
| no glitches | no fully green, black or white frame inside the video; no frame where a transition leaves a colour wash (the bug of 2026-10-27) | zero |
| audio sync | the caption word at time t is the word the voice says at t (measured with the recogniser's word times) | median error under 150 ms |
| duration | within the target the person gave | within 10 % |

## 4. The acceptance corpus (L7): what "works" means for a video
Ten scripts, fixed in the repository (`tests/acceptance/scripts/*.txt`), run through the whole pipeline on the real servers. Each is run as a **script**; three are also run as a **voice recording** and one as a **link**.
| # | Script | Kind | Language | Length | Voice | What it checks |
|---|---|---|---|---|---|---|
| A1 | split your money (exists) | steps | English | 35 s | Kokoro, KittenTTS, Breeze | step cards, fact order, three voices of one script |
| A2 | a health explainer (stress, oxytocin) | explanation | English | 60 s | Breeze design | line-art style, one idea per picture, a sigh event |
| A3 | a survival story with days | story | English | 90 s | Breeze clone | day cards, one hero, long hold |
| A4 | an argument made of terms | argument | English | 60 s | OmniVoice | kinetic type, term cards |
| A5 | a list of five tips | list | English | 45 s | Edge | numbered cards |
| A6 | a Bangla story | story | Bangla | 60 s | Edge, then OmniVoice | Bangla captions, picture prompts translated, the voice |
| A7 | a Banglish explainer | explanation | mixed | 45 s | Edge | mixed script captions |
| A8 | a hook-weak script (greeting first) | explanation | English | 30 s | any | the hook proposal appears and keeps every fact |
| A9 | a very short script (3 sentences) | opinion | English | 12 s | any | nothing breaks when there is little to cut |
| A10 | a 5-minute story | story | English | 5 min | any | chaptering, resumable drawing, memory |
For each: the automatic judges pass, then a person fills the checklist. **A video that fails a judge is a bug report, not a note.**

## 5. The human checklist (L8), one table per video
Filled in `docs/evidence/<date>/acceptance.md`. Yes, no, or a number, plus one sentence for every "no".
1. Does the first second make me want the next one?
2. Does each picture show what the sentence says (not only something related)?
3. Does the picture change when the sentence changes, on the right word?
4. Is every claim, number and name something the speaker said?
5. Does anything look broken (a green flash, a cut-off picture, garbled text in a picture, a figure that changes into someone else)?
6. Do the captions help (readable, on the right word, the key word lit)?
7. Does the voice sound right for the content, and are the sighs and laughs, if any, in the right places?
8. Does the music or sound help or fight the voice?
9. Would I post it under my name? If not, what is the one thing to change?
10. For a long video: does it still feel like one world at minute 5?

## 6. Non-functional tests (L9)
| Aspect | Test | Budget |
|---|---|---|
| **Speed** | a picture, a clip, a sentence of speech, a render: timed on each GPU, cold and warm, and compared with the table in [research/BEST-MODELS.md](research/BEST-MODELS.md) | picture 13 s warm on the V100; clip about 70 s warm; a sentence of voice under 8 s warm; a 35 s reel render about 75 s on the CPU renderer; a regression of more than 30 % fails |
| **Memory** | the V100 and the RTX 3060 free memory before and after each job; ComfyUI's RAM after two clips (the 38 GB incident) | memory returns to within 2 GB of the start after `/free` |
| **Disk** | the models folder and the output folders do not fill the drive; the app refuses to start a job below 10 GB free | |
| **Concurrency** | two jobs at once: a voice and a picture run together (two cards); two pictures queue; cancelling one does not disturb the other | no crash, no lost job |
| **Resilience** | kill ComfyUI mid-picture, restart Ollama, pull the network cable, fill the disk, send a wrong key, accept a wrong address | each ends with a sentence a person can act on and a resumable job, never a hang (the render hang of 2026-10-27 is the model case: `tests/test_reel.py::test_a_command_that_goes_silent_is_stopped_not_waited_for`) |
| **Security** | keys never leave `settings.json` through the API (tested); prompt injection inside a transcript or a script does not change the director's behaviour (tests with hostile text); `voice.atanusroy.com` refuses requests without the key; path traversal in project ids and media names | zero leaks |
| **Accessibility** | the Studio's new screens pass axe; every control has a name; the editor is usable by keyboard; contrast in light and dark | axe clean |
| **Languages** | English, Bangla and Banglish through script, voice and captions; Chinese tags parse | A6, A7 |
| **Upgrade** | a project made by an older version still opens and renders; settings from before the engines block still connect Ollama and ComfyUI | `tests/test_voicestudio.py::test_the_old_settings_still_connect_ollama_and_comfy` |

## 7. Setup and clean-machine tests (L10), for the wizard and the installers
Run on a Windows machine with only a GPU driver, and again on one with no GPU:
1. First run shows the welcome step and detects the hardware in plain words.
2. Choosing "set it up here" for Ollama downloads it and a small model, with progress and a resume after a killed download.
3. Choosing "connect to my server" for ComfyUI with a wrong address says what is wrong; with a right address lists what it can do.
4. A model folder on another drive is honoured by every engine.
5. `vt models status` after a deleted models folder lists exactly what is missing; `restore` brings it back (checksums verified).
6. The Engine Server on a second computer is paired by code and used by the first.
7. With nothing installed and no server, the app still makes a video with the built-in fallbacks and says what is slower.

## 8. Reporting
* `docs/evidence/<date>/checks.md` from the battery; `acceptance.md` from the people; both linked from [STATUS.md](STATUS.md) section 7.
* A failing or skipped step is a row in STATUS section 9 with an owner and a task id in [ROADMAP.md](ROADMAP.md) Phase 10 (verification).
* Before any release: the battery with `--slow --e2e --live --reel` is green, A1 to A10 are accepted, and the clean-machine list passed on both machines.

## 9. What exists today, and the gaps (so the plan is honest)
| Layer | Today | Gap |
|---|---|---|
| L1 to L4 | 880 or so fast tests pass, 65 slow pass | L1 gaps: `vt/doctor.py`, `vt/visuals/icons.py`, `vt/visuals/terms.py`, `vt/shorts/prompts.py` have no tests (P10-14) |
| L5 | 13 of 24 older suites pass, 11 are stale or fail ([STATUS](STATUS.md) section 6); new suites `editor_simple`, `log`, `engines` pass | P10-06, P10-11, P10-12 |
| L6, L7 | the battery's `--live` step runs (health of three engines and one real sentence from each of the five voice workflows on both ComfyUI servers); a voiced reel by hand | the acceptance corpus A1 to A10 is not written yet (T-2) |
| L8 | the owner looks at videos; no checklist is filled | T-3 |
| Judges | `judge.facts` and `judge.impact_alignment` exist as starters; the others are not written | T-4 |
| L9, L10 | none | T-5, T-6 |

| Id | Task | Done when |
|---|---|---|
| T-1 | `scripts/run_all_checks.py` with the steps of section 2 | **DONE 2026-10-28**: writes `docs/evidence/<date>/checks.md`; skipped steps say why; its first live run found the OmniVoice vocabulary bug ([evidence](evidence/2026-10-28/checks.md)) |
| T-2 | the acceptance scripts and a runner (`scripts/run_acceptance.py`) | A1 to A10 produce videos and judge reports **PARTLY DONE 2026-10-28 (all ten were run through a real Studio and the GPU server; 4 pass the automatic judges (A1, A4, A5, A8), 6 fail (A2, A3, A6, A7, A9, A10); no person has rated any, so the gate is not met; see [acceptance.md](evidence/2026-10-28/acceptance.md))**: `scripts/run_acceptance.py`, `tests/acceptance/`; the other eight are still to run |
| T-3 | the checklist as a form in the Studio (a Result-page sheet) that saves to the project | a person fills it in under a minute **DONE 2026-10-28**: the Result page's *Rate it* sheet saves to `checklist.json` |
| T-4 | the judges of section 3 as modules with tests on fixture videos (a green-frame video must fail) | each judge has a passing and a failing fixture **DONE 2026-10-28**: `vt/judges.py`, each judge with a passing and a failing fixture video (`tests/test_judges.py`) |
| T-5 | the non-functional tests of section 6 | a table of measured numbers in evidence **PARTLY DONE 2026-10-28:** `scripts/measure_nonfunctional.py` ([numbers](evidence/2026-10-28/nonfunctional.md)): start-up, API speed, judge time and memory; the long-video memory, power-cut and two-machine tests are not run |
| T-6 | the clean-machine run | the checklist of section 7 passes on two machines |
