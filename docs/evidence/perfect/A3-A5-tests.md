# A3, A4, A5 - the whole suite on the server

- **A3 baseline** (2026-11-07 10:05, after the power cut, on the RTX 3060 only): `A3-baseline.txt`, last line `4 failed, 1878 passed, 9 skipped in 735.55s`. On 2026-11-05 it was 13 failed, 9 errors; at midnight on 2026-11-07, 11 failed.
- **A4** the four that were left:
  - three golden sheets `phase2-{9x16,1x1,16x9}-b` (mean difference 9 to 15): looked at old and new side by side (`goldens/phase2-*-b-old-new.png`); only the caption chunks changed (shorter, as `_tidy_chunks` makes them), every graphic is the same, so the goldens were refreshed. `test_phase2_render.py` and `test_render_golden.py`: 15 passed.
  - `test_recordings_are_byte_identical[bn_plain]`: A5 below.
  - Final run: `A4-final.txt`, `1882 passed, 9 skipped in 689.64s`, 0 failed, 0 errors. The 9 skips are named in the run (the English sample file is not on the PC, and others that need hardware or accounts).
- **A5 the cause:** `_compare` now prints which files differ and, for a JSON file, the first differing key with both values. It said `project.json -> /director/at: legacy 10:22:27 != modules 10:22:31`: the record of who directed (`directors.record`, `now_iso()`) carries a time that the test did not freeze the way it freezes the other three clocks. Nothing in the program is unrepeatable; the test bench was. The test now freezes `vt.directors.now_iso` too. It passes twice in a row (`2 passed, 1 skipped` both times).
