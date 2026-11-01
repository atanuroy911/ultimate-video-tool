# Browser tests

Drive the real Studio in headless Chrome. They need a running server and the demo project:

    python samples/build_reference.py reference      # the hand-built demo video (no speech model needed)
    .\scripts\start.ps1 -NoBrowser                  # in another terminal
    cd studio
    npm run e2e            # edit flows: scenes, words, inspector, undo, split, playback, requests, theme editor (26 checks)
    npm run e2e:journey    # upload -> progress -> review with the real speech model, recording, no-speech error, delete (16 checks)

`journey` needs the Bangla model and `samples/audio/` (run `python scripts/make_sample_audio.py`). Screenshots go to `studio/e2e/out/`.
Chrome is found automatically (the one HyperFrames downloads); set `VT_CHROME` to use another, `VT_URL` for another server address.

More suites (editing window, 2026-10-22):

    node e2e/editor.mjs                      # menus, command palette, canvas selection, timeline drag/zoom, splitters, AI sheet, New/Settings (24 checks)
    VT_PROJECT=<stick project> node e2e/stick.mjs   # characters panel, action list, dragging an action to another word, undo (9 checks)

The mutating suites change the project they run on: run them against a scratch server (`VT_PROJECTS=<scratch dir> vt studio --port 8771`, `VT_URL=http://127.0.0.1:8771`)
with `samples/build_reference.py reference` built there, not against your real projects folder.

QA round (2026-10-22), also against a scratch server (`VT_DATA=<scratch dir>`):

    npm run e2e:timeline   # zoom, drag, cut, trim, mute, volume, undo in the timeline
    npm run e2e:edge       # double submits, reload during a job, invalid inputs, lost connection, stale server, persistent settings
    npm run e2e:crawl      # clicks every button and link on every page and fails on any 4xx/5xx
    npm run e2e:dashboard  # the Projects page: search, sort, view, duplicate, delete
    npm run e2e:a11y       # names, focus and contrast

Real media checks (no mocks): `python scripts/qa_generate.py`, `qa_analyze.py`, `qa_media_audio.py`, `qa_catalog.py`.

Client and server (docs/plans/PLAN-CLIENT-SERVER.MD), against a scratch `vt server` opened by its network address:

    VT_URL=http://<LAN address>:8771 node e2e/connect.mjs   # Connect screen and pairing code, paired-device list, a 20 MB upload surviving a dropped chunk (11 checks)
