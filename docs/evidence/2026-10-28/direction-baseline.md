# Our rhythm against the example reels

Measured 2026-10-28 by `scripts/eval_direction.py`. Rhythm only, not meaning.

## The reels

| name | length s | changes | per min | median gap s | longest still s | first change s | words/change | changes/sentence |
|---|---|---|---|---|---|---|---|---|
| reel-2 | 85.5 | 14 | 9.8 | 4.7 | 1.8 | 3.0 | 15.5 | 1.0 |
| reel-3 | 63.1 | 30 | 28.5 | 1.9 | 1.0 | 2.7 | 6.9 | 2.0 |
| reel-4 | 13.2 | 0 | 0.0 | 0.0 | 0.1 | - | - | - |
| reel-5 | 158.0 | 71 | 27.0 | 2.1 | 4.9 | 0.7 | 6.8 | 1.61 |
| reel-6 | 31.5 | 2 | 3.8 | 31.2 | 4.9 | 0.1 | 0.0 | - |
| reel-7 | 100.6 | 0 | 0.0 | 0.0 | 6.2 | - | - | 0.0 |
| reel-8 | 21.3 | 1 | 2.8 | 0.0 | 2.2 | 18.0 | 0.0 | - |
| reel-9 | 765.6 | 152 | 11.9 | 4.8 | 12.0 | 10.7 | 15.1 | 0.42 |
| reel | 144.5 | 5 | 2.1 | 23.05 | 5.7 | 33.2 | 84.8 | 0.22 |

The *busy* reels (at least 10 picture changes) are the model for a made video: reel-2, reel-3, reel-5, reel-9.

## Ours

| name | length s | changes | per min | median gap s | longest still s | first change s | words/change | changes/sentence |
|---|---|---|---|---|---|---|---|---|
| A1 | 22.1 | 10 | 27.1 | 2.3 | 0.7 | 3.0 | 7.5 | 0.91 |
| A9 | 6.6 | 2 | 18.1 | 2.3 | 0.4 | 3.1 | 11.5 | 0.67 |

## Against the busy reels

- how often the picture changes (per minute): ours 22.6, the busy reels 9.8 to 28.5 (median 19.45): **inside the range**
- the longest a picture stays (s): ours 0.55, the busy reels 1.0 to 12.0 (median 3.35): **below the range**
- the middle time between changes (s): ours 2.3, the busy reels 1.9 to 4.8 (median 3.4): **inside the range**
- when the first change comes (s): ours 3.05, the busy reels 0.7 to 10.7 (median 2.85): **inside the range**
- words under one picture: ours 9.5, the busy reels 6.8 to 15.5 (median 11.0): **inside the range**
- changes for each sentence: ours 0.79, the busy reels 0.42 to 2.0 (median 1.31): **inside the range**

## Which word

The 'which word' test is **pending**: the owner has not marked any reel yet (fill tests/direction_set/marks.template.json and save it as marks.json).
