# H5 - Server install from nothing (partly done)

2026-11-07 13:12 to 13:22, after the owner asked to delete both installs and reinstall.
- Package: `make_engine_package.py --out dist/fresh-2026-11-07 --full` (the first try without `--full` had no renderer and the install stopped at "cd app/renderer"; `--full` is needed for a server that renders).
- Install: `scripts/lab/install_server_fresh.py <package>` into `/home/roy/ultimate-video-tool-server`: `INSTALL_OK`, the user service is active, `/api/health` answers. Then `deploy_server_code.py` for the current code and launcher.
- Found: on a fresh install Video Tool treated the V100 as the card it may use and the RTX 3060 as not, the reverse of the owner's rule. Stopped the service at once, added `--gpus 1` to the launcher, restarted. `/api/system/gpus` now: V100 `allowed: false`, RTX 3060 `allowed: true`; V100 memory stayed at 5 MiB.
- **Working video:** `vt_lab.py make local cartoon h5-fresh` finished (`rendered`, director local gemma, no notice, 26 AI conversations); contact sheet `dist/lab/h5-fresh.png` viewed. The story is told, captions are clear and the voice and pictures fit the words; quality is middling (stacked stickers over the character's face: the known gemma limit, see C8).

Not done yet: installing without `--gpus` in a terminal and confirming it asks; the server manager's Applications entry; a non-default port next to a running server (this install used the usual port because the old one had been removed).
