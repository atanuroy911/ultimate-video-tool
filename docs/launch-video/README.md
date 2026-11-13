# The launch video

`docs/assets/launch.mp4` (56.8 s, 1920×1080), shown on the website.

How it was made, with Ultimate Video Tool:

1. `script.txt` was typed into **New video → Type a script** (English, voice `en-US-AndrewNeural`, 16:9). The server spoke it and timed every word. The word timings are in `words.json` (text, start and end in seconds).
2. `composition.html` is a hand-written HyperFrames composition timed to those words. It uses real screenshots from `docs/assets/screens/`. Replace `__WORDS__` with the contents of `words.json` and `__DUR__` with `56.8`, then put it next to `runtime/gsap.min.js`, `fonts/` (Bricolage Grotesque, Inter, Hind Siliguri, JetBrains Mono from `server/design/fonts`) and `media/` (the screenshots, `icon.svg` and a `cartoon.png` cut from the editor screenshot).
3. It was rendered with the server's renderer: `node server/renderer/node_modules/hyperframes/bin/hyperframes.mjs render <folder> -o launch-silent.mp4 -f 30 -q looks`.
4. The narration was mixed with the bundled CC0 track `server/assets/music/upbeat-01.mp3`, ducked under the voice and normalised to −14 LUFS with FFmpeg.

The same script, directed end to end by Claude inside the app, is the project `2026-11-13-ultimate-video-tool-launch` on the development machine.
