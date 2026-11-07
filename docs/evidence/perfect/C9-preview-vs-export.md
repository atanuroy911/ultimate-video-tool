# C9 - Preview and export match

`scripts/qa_preview_export.py` builds one composition (cartoon market, cartoon nature, ring, steps, stat row), takes a snapshot (what the Studio preview shows) and renders the MP4 (what is exported), then compares 5 moments in each of 3 styles: paper, dark-neon, style-chalkboard (16:9, drawn on the processor).

Mean difference per moment: 0.97 to 1.57 of 255; at most 0.32% of pixels differ a lot (dark-neon, last moment). The difference images (`dist/lab/c9/c9-<style>.png`, right column) show only thin outlines on edges and text, which is video compression. Same layout, colours, characters, text and motion position at every moment.

Check met: they look the same; the only difference is compression and it is explained.
