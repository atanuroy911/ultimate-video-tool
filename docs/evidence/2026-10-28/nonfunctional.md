# Non-functional measurements, 2026-10-28

Machine: Windows 10, AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD, 12 logical cores, Python 3.11.17.
Measured by `scripts/measure_nonfunctional.py`; these describe this computer only.

| What | Result |
|---|---|
| Start-up: `import vt.server.app` (cold process) | 1.4 s |
| `GET /api/health` | median 4 ms, p95 4 ms |
| `GET /api/projects` | median 4 ms, p95 5 ms |
| `GET /api/engines?health=false` | median 4 ms, p95 5 ms |
| `GET /api/setup/hardware` | median 126 ms, p95 142 ms |
| `GET /api/themes` | median 50 ms, p95 55 ms |
| Judges on `reel-voiced-by-breeze-9x16.mp4` (38 s of video) | 2.7 s, memory 83 -> 84 MB, 7 judges |
