# The direction set

Started 2026-10-28 from the ten example reels (P4-12). Not the 20-recording set of P4-01 yet.

* `reels.json`: the measured rhythm of each reel (changes, lengths, first change, words per change), made by `python scripts/eval_direction.py --seed`.
* `marks.template.json`: every sentence of the busy reels with an empty `word`. **The owner marks the word each picture should change on** (two reels are enough to start), then saves the file as `marks.json`. That is the 'which word' test.
* Still missing for P4-01: about 20 short recordings with an editor's cuts (audio and `marks.json` per recording).

Run `python scripts/eval_direction.py` to see our numbers beside the reels'.
