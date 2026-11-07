# E4 result page — Done by codex

2026-11-06. The local screenshot check passes. This is UI evidence with intercepted APIs, not a real export or playback check.

The Result page now leads with the video and Download, then one line from the actual `/api/projects/{id}/craft` response: a score out of 100 and the number of things to look at. Opening that line shows each measured problem and suggested fix, as well as the existing automatic checks and personal rating. The score is explicitly described as checking the current plan; automatic export checks remain separate. Missing or failed craft responses never invent a score and offer a retry.

The four main edit actions are Direct again, Change the look, Fix a word and Edit everything. Direct again is the only gradient button. Auto-fix suggestions appears in one place inside the quality details; the old risky-moments and duplicate auto-fix buttons were removed. Other shapes, director conversations/log, changes to the cut and sharing tools remain available behind named disclosures. The raw before/after risk numbers no longer appear in the change explanation.

E11 partial — Done by codex: Result now names its loading state and shows a plain project error with Try again and Back to your videos instead of leaving a spinner forever after a failed/missing project request. The fixture covers a 404 and successful retry. This does not close E11's whole-app state audit.

Validation after the implementation edit:

- `cd client/studio; npm run build` — TypeScript and Vite passed.
- `cd client/studio; node e2e/result_cleanup.mjs` — passed at 1280/light, 1280/dark, 400/light and 400/dark. It mounts the actual Result page, intercepts all APIs, uses a synthetic poster and launches software-only Chrome with `--disable-gpu`. The pre-fix run failed because two gradient actions existed.
- Assertions verify the craft score and issue text, the order and destinations of the four main edits, one auto-fix POST with its existing empty payload, one auto-fix control, no displayed `risk 47 → 11`, the look picker, collapsed details and no horizontal overflow. A 503 quality response and recovery to 100/100 are checked too.
- Screenshots read: `client/studio/e2e/out/result-cleanup/400-light.png`, `1280-dark.png`; the other theme/width variants are beside them. All four main actions remain readable on the phone; secondary actions are collapsed. The poster is a synthetic fixture illustration. No real video was played, downloaded, generated or changed.
- Existing scratch suites `quality.mjs`, `director.mjs` and `look_at.mjs` now open the new disclosure before exercising the same checks. Their assertions were retained. They were not run against a real server. The director suite requests AI work and a render, so remains paused under the owner's instruction.

No owner-server, GPU, model, ASR, social post, protected service or real export was touched.
