# M8: show the helper in the app

## What changed
- **Settings, Directors** (`client/studio/src/components/HelperCard.tsx`, first card of that section): "Helper on this PC".
  - Running or not (a green "Running" chip, or an amber "Not running" with a "Start the helper" button and, in words, what stops working while it is off).
  - The servers it reaches, one row each, the same at every width: the address with "Remove" on its right (it sends the whole address to the helper, which forgets that server), and under the address the state ("Connected", "Connecting…" or "Can't reach it") with the reason beside it.
  - Claude and Codex on this computer, each "Ready" (with its version), "Sign in" (with what to do) or "Not installed".
  - A real switch (role `switch`, named, a row at least 44 px tall, the words beside it work as the button too): "Keep Claude and Codex ready when the app is closed". When the app runs from source it is off limits and says "Available in the installed app." (M7 registers the entry in an installed build).
  - "Check again" and "Stop".
  - It reads everything through `window.vtDesktop.helper` (M6). In a plain browser there is no such bridge, and the card says the desktop app is needed ("Install and open the app on that computer, and its helper joins this server by itself.").
- **Server page** (`client/studio/src/components/ConnectedComputers.tsx`, between the system panel and the graphics-card control): "Computers using this server". One row per computer from `/api/directors` (by device, named by the name the helper sent), with a chip per director it offers ("Claude · Ready", "Codex · Needs sign-in"). A computer that was here and is not now stays listed as "Not connected · last seen 3 hours ago" (the server remembers them for 60 days, M5). With none, it says what to do ("Open Ultimate Video Tool on a computer, and its helper joins by itself.").
- Settings text that used to tell people to "open the app" now says to install and open the app and that its helper joins this server by itself. The notes the server gives for each computer (`directors.py` `listing()`, M5) say "Ready on this device.", "Open Claude Code on this device and sign in." and "Not connected. Open Video Tool on that computer; its helper starts with it and reconnects by itself." They name the helper; the last one still names the app because until the start-with-the-computer entry exists (M7) opening the app is what starts the helper.
- `styles.css`: `.helper-list`, `.helper-heading`, `.helper-address`, `.helper-server`, `.switch-row`, `.switch` (slides like iOS, `prefers-reduced-motion` turns the slide off, focus ring 3 px), and a new colour token `--switch-on` in light and dark. On a phone or any touch screen every button in the card is 44 px tall (the rest of the Studio's small buttons stay 30 px).
- `i18n.ts`: English and Bangla for every word on both cards. The helper itself speaks English (`last_error`, `reason`); the ten sentences it always says are mapped to the page's language (`helper.msg.*`), and any other text is shown as it came.

## Found and fixed on the way
- First screenshots in Bangla showed English sentences under the Bangla headings ("The server is not answering.", "Open Claude Code once and log in."). Fixed by the `helper.msg.*` map above, and a check that fails if either sentence is still English in Bangla.
- In the 400 px screenshots the "Remove" button dropped under the address on one row and stayed beside it on the next, and it was 30 px tall. The rows are now a grid (address and Remove on the first line, state and reason under), and a check measures every button in the card on a phone.

## Checks
- `client/studio/e2e/helper_card.mjs` (new), run against the real Studio code in headless Chrome (`--disable-gpu`) with a stand-in for the app's bridge: **27 passed, 0 failed**, no page errors. Breaking the touch-size rule on purpose made exactly one check fail (it listed every 30 px and 36 px button); with the rule back, 27 pass.
  - Every state (running, stopped, trouble, run from source) x wide 1280 and phone 400 x light and dark x English and Bangla (32 pages), plus the plain-browser page: none scrolls sideways, and on a phone every button is at least 44 px tall.
  - Behaviour: the switch is a named `role="switch"`, on/off follows `aria-checked`, its row is at least 44 px tall, a click on it or on its words sends `setAutostart`; Remove sends the full address and the list then says "None yet"; Check again asks for a new look; Stop shows the consequence in words and Start comes back.
  - Trouble: an unreachable server says so with the reason, a connecting one says it is connecting; Claude asks to be signed in with the reason; Codex ready; the switch off.
  - Source build: the switch is disabled and says why. Plain browser: the card says the app is needed.
  - Bangla: the card is Bangla (product names stay as they are) and so are the helper's problem sentences.
  - Server page, 8 combinations of size, theme and language: two computers listed, one connected (Claude ready, Codex needs sign-in), one remembered (not connected, last seen 3 hours ago); with none listed it says what to do.
- `npx tsc --noEmit` clean; `npm run build` ok.
- **Screenshots looked at** (in `client/studio/e2e/out/helper/`, 41 files: `helper-{running,stopped,trouble,source}-{wide,phone}-{light,dark}-{en,bn}.png`, `computers-...`, `helper-no-app-wide-light-en.png`). Reviewed after the last change: running wide light English, trouble phone dark English; before it: stopped wide dark English, source phone light English, trouble phone dark Bangla, computers wide light English, computers phone dark Bangla. All readable, no clipped words, contrast fine, the chips and the switch are not crowded at 400 px; the Bangla headings and sentences wrap cleanly. The rest of the 41 files are generated by the same code and were checked for sideways scrolling and button size, not each looked at.

## Not done here
- It is a stand-in for the app's bridge, not the real app window: the real bridge was proven in M6 with the packaged app and the helper's own HTTP calls; this step proves the page. Clicking the switch in a real installed app waits for M7 (registering the entry) and H1.
- The Bangla wording is mine; the owner reads it in E10.

## Note, 2026-11-06
The Bangla screens described above were removed on the owner's decision (plan decision 8, step E10): the interface is English only. The English checks stand.
