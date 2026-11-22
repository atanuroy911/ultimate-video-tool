# Browser suites: triage (W3.5), 2026-11-22

Run on this laptop against a scratch server (127.0.0.1:8791, `E:\UltimateVideoTool\scratch\c2-projects`) and the Studio dev server (5174).
First run: all suites one after another on one shared project (`c2-mix`). Second run: each failing suite on its own copy of `c6-shot` (`e2e-<suite>`), to separate real failures from suites changing each other's project.

| Suite | Result | Cause | Outcome |
|---|---|---|---|
| scroll, design, a11y, workbench, timeline2, script, retention, layers_media, assistant-agent | pass | | keep; add to nightly `browser` job |
| layers | pass alone (20/20); failed on the shared project | another suite moved the clip | keep; needs its own project copy |
| shot-editor | pass alone (17/17 earlier); failed on the shared project | another suite removed the scene's shot | keep; its own copy of a project with a shot |
| contrast | one theme fails (`auto-026-10-31-lab-mixed-wide`: text 1.14:1) and the suite timed out over 90+ themes | **real**: an old auto theme has unreadable text; the suite is too slow to check every saved theme | issue noted; limit the suite to built-in themes plus new auto themes |
| crawl | 4 problems: 404s on a project deleted mid-run | another suite deleted the project | keep; run alone |
| editor | 20/20 after the rewrite (2026-11-22: workbench page; picks a scene with two or more elements; pane resizing left to e2e/workbench.mjs; Settings sections) | old /pro page + demo project | rewritten |
| journey | 16/16 after the rewrite (2026-11-22: a fresh English Kokoro sample in E:/UltimateVideoTool/scratch/samples, the new question screens, Try again / Start over, delete through the card menu; up to 15 minutes for a laptop to make the video) | retired sample + old layout | rewritten |
| export | 8/8 after the rewrite (2026-11-22: the project is a parameter, not the old "reference" demo) | hardcoded demo project | rewritten |
| sounds | 5/5 after the rewrite (2026-11-22: workbench page; needs a project never listened to: delete its sounds_events.json) | old /pro page | rewritten |
| context | 5/5 after the rewrite (2026-11-22: opens Video settings in the workbench layout) | old /pro page | rewritten |
| edge | 9/9 after the rewrite (and it now cancels the jobs it started, which held the queue for later suites) (2026-11-22: new layout classes; the failing edit is "Merge with next" from a scene's menu) | stale selectors | rewritten |
| stick | 9/9 after the rewrite (2026-11-22: workbench page; a copy of a stick-figure video from the installed server's own projects; the list heading is "Stick Actions & Poses") | stale + needs its own project | rewritten |
| dashboard | 10/10 after the rewrite (2026-11-22: any video with a title of its own; the status and format filters are expected). Found a real bug on the way: copied project folders shared one id, the dashboard kept stale cards; the folder name is now the id (vt/project.py, test) | stale + real bug | rewritten, bug fixed |
| timeline3 | drag lags the pointer by 28 to 56 px | ran while speech recognition used every processor core and a video model used the card; timing-sensitive | re-run on a quiet machine before calling it a bug |

**Rule from this run:** a suite must never share a project with another suite. Each suite should copy a fixture project to its own id first (see the second run's script, `E:\UltimateVideoTool\scratch\e2e\run2.sh`).

**Copying a project for a suite:** set the copy's `id` in its `project.json` to the folder name, or the page reads the original project's data (the context panel showed "Not read yet" because of this).
