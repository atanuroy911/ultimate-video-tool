# E3 Settings clarity — Done by codex

2026-11-06. Checked locally with the actual Settings page in a software browser. No owner-server access or model calls.

The Directors page now leads with a single fallback-order list and a plain answer to who is ready next. Disconnected PCs have a next action; missing helpers are explained. The model and wait choices remain beside that list, with the existing Helper on this PC card below it. Connection/provider configuration and addresses are inside a closed Server details disclosure. The Automatic service's advanced status counts a ready local model instead of treating an offline Claude login as proof that Automatic is unavailable.

Preferences aligns Theme, Shape and Pace at desktop width and stacks them on phones. Help & checks names what each component does and gives a plain recovery instruction. Commands, runtime versions and server addresses are kept inside Technical details. Provider changes now save only the changed fields and accept the server's public settings response instead of sending a stale full settings object.

Validation:

- `npm.cmd run build` — TypeScript and Vite passed.
- `node e2e/settings_clarity.mjs` — passed at 1280 and 400 pixels, light and dark. The fixture mounts the actual Settings page with in-memory API responses, and launches Chrome with `--disable-gpu`. It checks the next director as readiness changes, a single everyday director heading, collapsed addresses, a ready Automatic service when Local AI is ready, model and address saves sending only the changed fields, aligned labels, plain Help recovery text, no horizontal overflow and no page errors.
- Screenshots saved under `client/studio/e2e/out/settings-clarity`; inspected the desktop light director/preferences pages and phone dark director/light help pages. The next-director answer is visible above the list.

This is deterministic page and screenshot evidence, not a claim of a new-person usability study or a live assistant connection. Rendering remains paused under the owner's instruction.
