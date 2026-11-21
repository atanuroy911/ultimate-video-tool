# Open issues (found while building, to fix later)

Newest first. Each line: what is wrong, where it was seen, how bad.

## 2026-11-22
- **First picture is slow with the card cold:** `make_picture` took 42 s the first time (model load), 12 to 14 s after. Fine, but the agent should be told to wait. (C7)
- **Kokoro warns "words count mismatch on 100% of the lines"** for a one-sentence test; word timing may be rough for agent speech. (C7, minor)
- **Media bin holds pictures and clips only**, so `speak` saves a WAV under `agent_audio/` that no scene can use yet. Needs a place in the bin or a voice-over slot. (C7)
- **Codex** is not available (owner: ignore for now; ChatGPT app is installed, not the Codex command line).

## Carried over
- gemma4:e2b cannot write valid shots (they get dropped with a note); Claude can.
- Video quality: text clipped ("outdoo|"), a tiny icon, empty stretches, stick figures overlapping (PLAN-PERFECT).
- cuDNN crash that stops the server now and then (F1); the server manager does not restart a crashed server.
- The Claude Code tab has no model chooser; it has not been tried on a rebuilt installer (W12.6).
- Studio reloads after the agent turn ends, not live while it edits (W14).
- Clips (FramePack, Wan 2.2 5B) and the voices Chatterbox, Qwen3-TTS, OmniVoice and Bangla are not measured yet (C7).
