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
| editor | fails at "elements carry an index" | the old `/pro` page and the "reference" demo project (the retired "yield" sample) | rewrite in W15.2 |
| journey | `samples/audio/bn_plain.mp3` missing | the sample was removed with the "yield" sample | rewrite in W15.2 with a fresh test recording |
| export | waits for "Exporting…" | export UI moved in the workbench layout | rewrite in W15.2 |
| sounds | "Listen for laughter" button not found | the Sounds lane moved | rewrite in W15.2 |
| context | "Topic of the video" field not found | the context panel moved | rewrite in W15.2 |
| edge | 9/9 after the rewrite (2026-11-22: new layout classes; the failing edit is "Merge with next" from a scene's menu) | stale selectors | rewritten |
| stick | needs a stick-figure project; the Characters inspector moved | stale + needs its own project | rewrite in W15.2 |
| dashboard | no "Reference frame" card | needs the old demo project | rewrite in W15.2 |
| timeline3 | drag lags the pointer by 28 to 56 px | ran while speech recognition used every processor core and a video model used the card; timing-sensitive | re-run on a quiet machine before calling it a bug |

**Rule from this run:** a suite must never share a project with another suite. Each suite should copy a fixture project to its own id first (see the second run's script, `E:\UltimateVideoTool\scratch\e2e\run2.sh`).
