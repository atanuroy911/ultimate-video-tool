# Matrix findings

Found by `scripts/lab/local_matrix.py` on the installed 0.5.0 server on this laptop (Windows, RTX 4050, Claude on this PC as the director). Newest first. Each finding: what happened, the project, what was done.

## 2026-11-20

### F1. The server process died in the "Listening for sounds" step, and nothing restarted it
- First row (`explainer-watch`, English, 9:16, Claude directing), first server start after setup. The log showed `Could not load symbol cudnnGetLibConfig. Error code 127`, then `Processing server exited 3221226505` (0xC0000409). The matrix client got a connection reset. The server manager window stayed open with the server stopped.
- Environment: torch 2.6.0+cu124 (cuDNN 9.1 in `torch/lib`), ctranslate2 with its own `cudnn64_9.dll`, onnxruntime-gpu 1.26.0.
- Not reproduced: the same stage run alone in the installed environment (with and without the GPU fence, with ONNX Runtime loaded first) works, and the same row passed the stage on the second server start.
- Two separate problems: (a) an intermittent native crash in a library mix (suspect: a second `cudnn64_9.dll` loaded by name from CTranslate2's folder before torch's own); (b) the server manager does not restart a crashed server, so a person just sees nothing work. Fix (b) for sure (restart with a back-off and say so in the window). For (a), preload torch's `cudnn64_9.dll` by full path in `vt.gpu.prepare()` on Windows, so a by-name load from another package reuses it.
- Status: open.
