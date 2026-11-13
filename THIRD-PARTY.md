# Third-party software, models and media

Ultimate Video Tool itself is licensed under the [GNU AGPL-3.0-or-later](LICENSE). It builds on the work below, and each part keeps its own licence. Where a component is downloaded at setup time rather than shipped in this repository, that is noted.

## Code in this repository

| Component | Where | Licence |
|---|---|---|
| [OpenChatCut](https://github.com/0xsline/OpenChatCut) timeline, captions and agent parts | `client/studio/src/occ/src`, `client/studio/src/occ/shared` | AGPL-3.0-or-later. See `client/studio/src/occ/NOTICE.md`. |
| cartoon-studio | `third_party/cartoon-studio` | Apache-2.0 (its `LICENSE`) |
| video-shotcraft | `third_party/video-shotcraft` | Apache-2.0 (its `LICENSE`) |

## Libraries (installed by the package managers)

The full lists are `server/pyproject.toml` with `server/uv.lock`, and the `package.json` / `package-lock.json` files under `client/` and `server/`. Notable ones:

| Component | Used for | Licence |
|---|---|---|
| [HyperFrames](https://www.npmjs.com/package/hyperframes) | rendering HTML compositions to video | Apache-2.0 |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) / CTranslate2 | speech recognition | MIT |
| [PyTorch](https://pytorch.org), [Transformers](https://github.com/huggingface/transformers) | models | BSD-3-Clause, Apache-2.0 |
| [FastAPI](https://fastapi.tiangolo.com), [Typer](https://typer.tiangolo.com), [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | API, CLI, MCP | MIT |
| [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | offline English and Hindi voices | MIT (Kokoro model: Apache-2.0) |
| [edge-tts](https://github.com/rany2/edge-tts) | online neural voices | LGPL-3.0. It uses Microsoft's online service under Microsoft's terms. |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | importing links | Unlicense |
| [OpenCV](https://opencv.org) | face detection, so text stays off faces | Apache-2.0 |
| [React](https://react.dev), [Vite](https://vite.dev), [Electron](https://www.electronjs.org) | editor and desktop apps | MIT |
| [Lucide](https://lucide.dev) | icons | ISC |
| [FFmpeg](https://ffmpeg.org) | audio and video processing (not bundled; used from the system or downloaded) | LGPL/GPL |

## Engines and models (downloaded by setup, not in this repository)

| Component | Used for | Licence |
|---|---|---|
| [Ollama](https://ollama.com) | running local language models | MIT |
| Gemma and other Ollama models | the local AI director | Each model's own licence (e.g. Gemma Terms of Use) |
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | the picture engine | GPL-3.0. It runs as a separate program. |
| FLUX.2 Klein 4B | generated pictures | See its model card. Larger FLUX variants may be non-commercial. |
| bengaliAI `tugstugi_bengaliai-asr_whisper-medium` | Bangla speech recognition | See its model card |
| Meta MMS TTS | the offline Bangla voice | **CC-BY-NC 4.0: non-commercial use only** |

Before you publish videos commercially, check the licence of every model you choose in setup.

## Media

| Asset | Licence |
|---|---|
| [Twemoji](https://github.com/jdecked/twemoji) colour stickers | CC-BY 4.0. Credit is added to exports. |
| Music and sound effects in `server/assets/music` and `server/assets/sfx`, made by `scripts/make_assets.py` | CC0 1.0. See `server/assets/LICENSES.md`. |
| Fonts built by `server/renderer/scripts/build-fonts.mjs` | SIL Open Font License 1.1 (each font's own) |
| Free media catalogue (Internet Archive, Wikimedia Commons) | Per item: CC0, public domain or CC BY. Credits are written next to every export. |

If you believe something here is listed wrongly, please open an issue.
