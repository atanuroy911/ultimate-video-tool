# Module spike and live ComfyUI follow-up

Checked 2026-10-26 after the handoff and roadmap were updated.

## Local implementation

- Added three real adapters (`project.inspect_source`, `audio.find_retakes`, `audio.prosody`) behind a registry, artifact workspace, synchronous executor, cache, time estimate gate, resource lock, call log, CLI and MCP entry points.
- Exported the same input schema in OpenAI, Anthropic, Gemini and MCP tool shapes.
- Focused tests: [module-spike.log](module-spike.log), 13 passed including a real MCP stdio call and path escape rejection.
- Full fast pytest suite: [fast-after-modules.log](fast-after-modules.log), exit 0. This does not cover slow renders or browser suites.
- Remaining Phase 1 work: automatic prerequisite execution, asynchronous tickets/cancel, replay, pipeline wrappers and byte-equivalence proof.

## Live server

- At 21:30 local time `/system_stats` reported ComfyUI 0.42.5 and PyTorch 2.12.1+cu126 on the V100. The service environment points caches at `/mnt/bigdata/video-tool/comfyui/cache`. The model directory there is 117 GB.
- A read-only rsync comparison found matching large weight files. Differences were small `models/configs` files and changing ComfyUI logs/cache. The old root model directory remains intact.
- Fresh LTX 2.3 test on the supplied astronaut/car still: prompt `8107695e-bb67-404d-86bd-e7eb7c015fbb` succeeded; downloaded H.264 MP4, 512×320, 49 frames at 25 fps, 1.96 s. Five inspected frames show a continuous camera move and recognizable subject/car. The raw server MP4 has an audio stream; Video Tool's `normalise` path removes audio before placing generated B-roll beneath the source voice.
- Fresh Wan 2.2 test on the same still: prompt `43e33fcf-baa4-414d-8c1d-ee809f6176c8` succeeded; downloaded MP4, 512×320, 33 frames at 16 fps. Five inspected frames keep the astronaut and car stable with gentle motion. LTX made a more dynamic camera move in this pair; this is a visual observation on one prompt, not a general quality score.
- Requested ComfyUI unload its cached models after the comparison.

The temporary test clips and contact sheet are in ignored `qa_remote_comfy/`; no owner's project was changed.
