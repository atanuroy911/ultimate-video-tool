# Cartoon Studio (Jellypod-Inc/cartoon-studio)

Source: https://github.com/Jellypod-Inc/cartoon-studio, commit e773568f7b6e6efe8cdf4d068efddfb5e65c4169, Apache License 2.0 (LICENSE in this folder).

Taken into Video Tool (2026-10-24):
* the four character drawings (`assets/cartoon/characters/`: bill, jane, max, ted) and four painted scenes (`assets/cartoon/scenes/`:
  backyard, living room, park, street), unchanged except that bill and ted were given the mouth rig;
* the nine-shape mouth rig (Preston Blair X, A-H) and the eye-anchored mouth finder, ported to Python in `vt/art/toon.py`.

Not taken: the Electron app, the Recraft (text-to-SVG) and OpenAI calls, the speech SDK. Mouth shapes follow the loudness of the voice
in `renderer/runtime/vt-stick.js` instead of Cartoon Studio's English-letter vowel rules, so Bangla works too.
