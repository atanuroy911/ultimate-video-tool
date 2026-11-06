# M5b: no pairing (owner's decision, 2026-11-05)

Owner: "remove the key pairing altogether... Just let user put the ip address."

## The rule now (server/vt/server/serve.py)
- **Trusted** = the sender is this computer, or on a private, link-local or Tailscale (100.64.0.0/10) address; nothing forwarded the request (`X-Forwarded-For`, `Forwarded`, `X-Real-IP`, `CF-Connecting-IP`); its `Host` is an address or a local name (`.local .lan .home.arpa .internal .localdomain .localhost .ts.net`, or a name with no dot); and its `Origin`, if any, is this same server.
- A trusted request needs **no key** on `/api`, `/ws`, `/media` and `/mcp`.
- Everything else needs the server's own key (`Authorization: Bearer`, the `vt_token` cookie or `?token=`). The 401 says: "This Video Tool server only accepts computers on its own network."
- Why those two safety rules stay, in plain words: without the first, publishing the port (the owner already publishes other ports through a Cloudflare tunnel) would open the machine to the internet; without the second, any web page the person visits could use their server, because a page can reach a private address through the person's own browser.
- A computer names itself with the `X-VT-Device` header (the helper and the app send it, kept in `device.json`). A browser tab names nothing and cannot become a director.

## Removed
`/api/pair`, `/api/server/code`, `/api/server/clients` (list and revoke), `/api/directors/token`, per-device tokens (`server/vt/server/clients.py`), the pairing code in `vt server`, discovery and `vt servers`, the "Approve this PC" screen, the code and device list on the Engines page, the code in both server manager windows (Windows and GTK), on the server's own pages, `--code` and `pairFromCommandLine` in the app, and the key the one-click assistant connection used to hand out. The assistant connection and the helper still accept a key, for a server outside the person's network.

## Left alone on purpose
The separate "share this computer's engines" feature: `vt engine run/pair`, `/v1/pair`, the Engines page "Share this computer's engines" card and the engine installers (`install-engine.sh/.ps1`, Docker). It has its own code and was not part of this decision.

## Checks
- `tests/test_server_auth.py` (25 tests): ten kinds of own-network address need nothing on every guarded path including the websocket and `/mcp`; seven kinds of outside address are refused with the new text; the key still works as header, cookie and query; a forwarded request is refused even from this computer; a foreign `Origin`, `Origin: null`, a rebound name and a mismatched `Origin` are refused while `Host` values for real use (IP, `[ipv6]`, `localhost`, a plain machine name, `.local`, `.lan`, `.home.arpa`, `.ts.net`) pass; a helper named by header can register and a browser tab (no, bad, short or long header) cannot, checked while connected; the old routes answer 404.
- Eight deliberate breakages are each caught: any address trusted, the Tailscale range not trusted, no web-page check, no rebinding check, no forwarded check, no key check, `/mcp` open to everyone, a tab able to name a device.
- Also changed and passing: `test_server_merge.py`, `test_mcp_network.py`, `test_discovery.py`, `test_upload_resume.py` (the ticket test now uses an outside address); 129 passed with the director and API files; `client/desktop` and `server/desktop` `npm test`, the Studio build and `test:timeline` pass.
- **On the real server (deployed 23:09, boot time unchanged):** from this PC with no key, `/api/health` and `/api/directors` answer 200, `/.well-known/video-tool` says `needs_key: false`; a foreign `Origin`, a rebound `Host` and an `X-Forwarded-For` get 401; `/api/pair` and `/api/server/code` give 404; `/mcp` is let through.
- **The real helper** (plain Node on this PC, nothing else running), added by address only: connected, announced Claude 2.1.314, and the server listed "Claude on MSI-LAPTOP, ready"; after it stopped, "Not connected. Open Video Tool on that computer; its helper starts with it and reconnects by itself." Idle memory 55.7 MB.
- **The real app run from source** with a brand-new data folder and `--server=192.168.123.47` only: it connected, made its device name, the window opened ("Ultimate Video Tool Studio"), the server listed "Claude on MSI-LAPTOP, ready", and it closed cleanly with nothing but two lines in its log. No code anywhere.
- I removed the three test devices this made from the server's remembered-computers file afterwards.

## Not done
- The packaged installer was not rebuilt or run: that is H1 and M6.
- The old companion still announces Codex even when it is not installed ("Codex on MSI-LAPTOP, not ready"); the helper does not (M6 switches the app over).
