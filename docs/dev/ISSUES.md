# Open issues (found while building, to fix later)

Newest first. Each line: what is wrong, where it was seen, how bad.

## 2026-11-22 (C7)
- **First picture is slow with the card cold:** `make_picture` took 42 s the first time (model load), 12 to 14 s after. Fine, but the agent should be told to wait. (C7)
- **Kokoro warns "words count mismatch on 100% of the lines"** for a one-sentence test; word timing may be rough for agent speech. (C7, minor)
- **Media bin holds pictures and clips only**, so `speak` saves a WAV under `agent_audio/` that no scene can use yet. Needs a place in the bin or a voice-over slot. (C7)
- **Codex** is not available (owner: ignore for now; ChatGPT app is installed, not the Codex command line).

## Carried over
- gemma4:e2b cannot write valid shots (they get dropped with a note); Claude can.
- Video quality: text clipped ("outdoo|"), a tiny icon, empty stretches, stick figures overlapping (PLAN-PERFECT).
- cuDNN crash that stops the server now and then (F1); the server manager does not restart a crashed server.
- The Claude Code tab has a model chooser (fake-agent test only; the real adapter has not been tried with each model); it has not been tried on a rebuilt installer (W12.6).
- Studio reloads after the agent turn ends, not live while it edits (W14).
- Clips (FramePack, Wan 2.2 5B) and the voices Chatterbox, Qwen3-TTS, OmniVoice and Bangla are not measured yet (C7).

## 2026-11-22 (C8)
- **"Open in VS Code" opens the agent folder only.** Claude Code inside VS Code has no Video Tool tools there, because giving it the server key means writing the key to a file. Needs the small VS Code extension (C8 rest) so the key stays in the app.
- **Chatterbox Turbo is far too slow here:** about 17 s of work for each second of speech (56 s for 3.2 s) on this laptop, on the card or the processor alike. A 1-minute video would take ~17 minutes. Look at whether the ONNX run really uses the card (probably the CPU build of onnxruntime), or use it only for short lines. (C7)
- **Qwen3-TTS, OmniVoice, Bangla voices** are not installed or measured; each needs a model download and an engine recipe that does not exist yet. (C7)
- **Server restart after a crash (F1) is written but not tried live:** `server/desktop/main.js` now starts the server again after an unexpected nonzero exit (3 times in 10 minutes at most). It is only syntax-checked; it needs a test that kills the server on purpose on a rebuilt Server app.
- **W14 is half done:** the change event names scenes and who (only when the MCP server acted in the last 4 s), the Studio toasts it. Done since: glow, waiting while the person edits, selection kept (6/6). Still missing: the event from every save, `by` for person and director, refetching only the changed scenes. Ctrl+Z now undoes an agent change (7/7), but only changes made while the editor is open.
- ~~Real Claude Code asking for a picture and speech~~ done 2026-11-22 (5/5) with a loopback test server (`VT_LOCAL_MCP=1`). Note: Claude reused a cached picture on the second run, by design (same prompt, same picture).
- **VS Code extension (`client/vscode/`) is written but never run inside VS Code** (only its helper functions are tested, `node client/vscode/test.js`). It is not packaged or published; to try it: open VS Code with `--extensionDevelopmentPath=client/vscode`. It cannot write shots, only preview them; live "edits in VS Code show in the app" (C8 check) is not built.
- **Pointing (W13) is Ctrl+L only:** no right-click "Ask the assistant about this", no Alt-drag region with a cropped picture, no Shift-drag time range, no drag-in. (W13.3)
- **Test projects are shared between suites:** the browser suites edit the same scratch project (c2-mix), so a suite run at the same time as another sees scenes merged or moved. Give each suite its own copy of the project.
- **An old auto theme has unreadable text** (`auto-026-10-31-lab-mixed-wide`, 1.14:1 contrast), found by e2e contrast. Check that new auto themes can never be saved below 3:1. The contrast suite also takes too long over 90+ saved themes.
- **timeline3 drag lag (28 to 56 px)** seen while the machine was busy; re-run on a quiet machine.
- **(fixed 2026-11-22: stages/asr.py free_card asks local ComfyUI and Ollama to let go first; not yet re-timed) Speech recognition ran on the processor** for the 16.5-minute talk (about 40 minutes and counting) while ComfyUI held 5 GB of the card. The pipeline should ask ComfyUI to free the card first (gen.free_memory exists), as the language model does.
- **Clips on a 6 GB card are possible but very slow:** Wan 2.2 TI2V 5B (Q4) made a 2 s 640x352 clip in 22.6 minutes (machine busy with speech recognition). Re-time on a quiet machine; try fewer steps (a 4-step distilled LoRA) before offering clips on small cards. FramePack not tried. (C7)
- **(fixed 2026-11-22) A-roll failed when the project is on another drive than the system temp folder** (WinError 17 moving C: temp to E:). Now built in a temp folder inside the project.
- **gemma4:e2b reads a long talk badly** (C10 outline): it skipped the lists when they were optional, took the seconds on each line for sentence numbers, and from run to run found 2 to 13 examples. Fixed what is ours (required lists first, no times on lines, a limit of 15 sentences per example with one retry). gemma4:e4b on the same talk: 17 good examples over the whole 14 minutes in 114 s. The outline should prefer e4b when it fits the card.

## 2026-11-22 (C10, the owner's 16.5-minute talk, local AI directing)
Result: all 17 examples the reader found got B-roll (10 pictures drawn on this laptop + designed graphics), 1 B-roll scene outside an example, opening and close on the speaker. Sheet: `docs/dev/spikes/html-shot/c10-owner-talk-sheet.png`. Problems seen:
- **(fixed 2026-11-22: aroll.keep_screen_clear, last step before saving; 94 scenes cleared on the owner's talk) A slide recording is treated as a talking head.** The talk is a screen recording of slides; the speaker scenes put stickers and words over the slides ("box" over the problem statement, "Robotics" over the logo). Detect a slide/screen recording (the `recording_edit` "screen" path already protects the picture) and never cover it.
- **Random keywords over pictures** from the local planner: "avoidance" over the beetle, "-star", "inside"; a bar chart labelled "4 / 10 version version". The local picture planner's word picks need teaching (PLAN-PERFECT).
- **A generated picture has garbled lettering** ("RRRUSTIER") despite "no text" in the prompt; FLUX.2 Klein draws words anyway. Try a negative prompt or a checker that rejects pictures with text.
- **Slow on this laptop:** speech recognition 28 min (processor), sounds 16 min, planning about 11 min, 10 pictures about 6 min. The sounds step (16 min for 16 min of audio) needs a look.
- Claude directing this talk has not been tried yet (C10 check).
