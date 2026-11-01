# Acceptance run, 2026-10-28

| Id | Result | Voice | Made in | Failed judges | Skipped judges |
|---|---|---|---|---|---|
| A1 | passed | (earlier run) |  s | - | - |
| A2 | FAILED | comfyvoice/design:A calm, thoughtful woman with a c | 654 s | pictures_per_words | - |
| A3 | FAILED | comfyvoice/design:A deep, serious older man speakin | 1178 s | duration, pictures_per_words | - |
| A4 | passed | comfyvoice/design:A warm, confident adult man with  | 564 s | - | - |
| A5 | passed | (earlier run) |  s | - | - |
| A6 | FAILED | (earlier run) |  s | duration, pictures_per_words | - |
| A7 | FAILED | (earlier run) |  s | duration, pictures_per_words | - |
| A8 | passed | (earlier run) |  s | - | - |
| A9 | FAILED | (earlier run) |  s | pictures_per_words | - |
| A10 | FAILED | (earlier run) |  s | duration | - |

Each judge's sentence is in `acceptance/<id>.judges.json`. A person fills the human checklist (docs/TEST-PLAN.md section 5) after the judges pass.

## A1

| Judge | Result | Says |
|---|---|---|
| first_frame | pass | The first frame has a picture and the first word comes at 0.02 s. |
| nothing_still | pass | The longest stretch with nothing new is 1.0 s (at 0.2 s). |
| no_glitches | pass | No blank or colour-washed frame. |
| duration | pass | The video is 22.1 s; the target was 22 s (1 % off, allowed 30 %). |
| loudness | pass | Loudness -14.0 LUFS, true peak -1.5 dBTP is in range. |
| change_on_word | pass | 100 % of the 29 picture changes land on a spoken word (aim for 75 %). |
| pictures_per_words | pass | 88 % of the 8 pictures carry 5 to 13 words. |
| same_design | pass | All 11 scenes use the same picture design. |

## A2

| Judge | Result | Says |
|---|---|---|
| first_frame | pass | The first frame has a picture and the first word comes at 0.01 s. |
| nothing_still | pass | The longest stretch with nothing new is 0.8 s (at 0.2 s). |
| no_glitches | pass | No blank or colour-washed frame. |
| duration | pass | The video is 29.5 s; the target was 35 s (16 % off, allowed 30 %). |
| loudness | pass | Loudness -13.8 LUFS, true peak -2.3 dBTP is in range. |
| change_on_word | pass | 97 % of the 39 picture changes land on a spoken word (aim for 75 %). |
| pictures_per_words | FAIL | 69 % of the 13 pictures carry 5 to 12 words. |
| same_design | pass | All 13 scenes use the same picture design. |

## A3

| Judge | Result | Says |
|---|---|---|
| first_frame | pass | The first frame has a picture and the first word comes at 0.00 s. |
| nothing_still | pass | The longest stretch with nothing new is 0.8 s (at 0.2 s). |
| no_glitches | pass | No blank or colour-washed frame. |
| duration | FAIL | The video is 53.6 s; the target was 40 s (34 % off, allowed 30 %). |
| loudness | pass | Loudness -14.2 LUFS, true peak -2.1 dBTP is in range. |
| change_on_word | pass | 90 % of the 72 picture changes land on a spoken word (aim for 75 %). |
| pictures_per_words | FAIL | 60 % of the 20 pictures carry 4 to 11 words. |
| same_design | pass | All 25 scenes use the same picture design. |

## A4

| Judge | Result | Says |
|---|---|---|
| first_frame | pass | The first frame has a picture and the first word comes at 0.00 s. |
| nothing_still | pass | The longest stretch with nothing new is 0.8 s (at 0.2 s). |
| no_glitches | pass | No blank or colour-washed frame. |
| duration | pass | The video is 25.8 s; the target was 30 s (14 % off, allowed 30 %). |
| loudness | pass | Loudness -14.1 LUFS, true peak -2.3 dBTP is in range. |
| change_on_word | pass | 100 % of the 34 picture changes land on a spoken word (aim for 75 %). |
| pictures_per_words | pass | 100 % of the 12 pictures carry 5 to 12 words. |
| same_design | pass | All 12 scenes use the same picture design. |

## A5

| Judge | Result | Says |
|---|---|---|
| first_frame | pass | The first frame has a picture and the first word comes at 0.04 s. |
| nothing_still | pass | The longest stretch with nothing new is 1.0 s (at 15.2 s). |
| no_glitches | pass | No blank or colour-washed frame. |
| duration | pass | The video is 24.2 s; the target was 28 s (13 % off, allowed 30 %). |
| loudness | pass | Loudness -14.0 LUFS, true peak -1.5 dBTP is in range. |
| change_on_word | pass | 100 % of the 32 picture changes land on a spoken word (aim for 75 %). |
| pictures_per_words | pass | 100 % of the 8 pictures carry 4 to 12 words. |
| same_design | pass | All 13 scenes use the same picture design. |

## A6

| Judge | Result | Says |
|---|---|---|
| first_frame | pass | The first frame has a picture and the first word comes at 0.03 s. |
| nothing_still | pass | The longest stretch with nothing new is 1.5 s (at 9.5 s). |
| no_glitches | pass | No blank or colour-washed frame. |
| duration | FAIL | The video is 19.3 s; the target was 35 s (45 % off, allowed 30 %). |
| loudness | pass | Loudness -14.1 LUFS, true peak -2.5 dBTP is in range. |
| change_on_word | pass | 100 % of the 22 picture changes land on a spoken word (aim for 75 %). |
| pictures_per_words | FAIL | 78 % of the 9 pictures carry 4 to 11 words. |
| same_design | pass | All 9 scenes use the same picture design. |

## A7

| Judge | Result | Says |
|---|---|---|
| first_frame | pass | The first frame has a picture and the first word comes at 0.02 s. |
| nothing_still | pass | The longest stretch with nothing new is 1.0 s (at 4.8 s). |
| no_glitches | pass | No blank or colour-washed frame. |
| duration | FAIL | The video is 16.3 s; the target was 28 s (42 % off, allowed 30 %). |
| loudness | pass | Loudness -13.7 LUFS, true peak -2.2 dBTP is in range. |
| change_on_word | pass | 100 % of the 21 picture changes land on a spoken word (aim for 75 %). |
| pictures_per_words | FAIL | 62 % of the 8 pictures carry 5 to 12 words. |
| same_design | pass | All 8 scenes use the same picture design. |

## A8

| Judge | Result | Says |
|---|---|---|
| first_frame | pass | The first frame has a picture and the first word comes at 0.02 s. |
| nothing_still | pass | The longest stretch with nothing new is 1.0 s (at 1.8 s). |
| no_glitches | pass | No blank or colour-washed frame. |
| duration | pass | The video is 20.1 s; the target was 25 s (20 % off, allowed 30 %). |
| loudness | pass | Loudness -14.0 LUFS, true peak -1.9 dBTP is in range. |
| change_on_word | pass | 96 % of the 26 picture changes land on a spoken word (aim for 75 %). |
| pictures_per_words | pass | 89 % of the 9 pictures carry 5 to 12 words. |
| same_design | pass | All 9 scenes use the same picture design. |

## A9

| Judge | Result | Says |
|---|---|---|
| first_frame | pass | The first frame has a picture and the first word comes at 0.02 s. |
| nothing_still | pass | The longest stretch with nothing new is 1.0 s (at 3.2 s). |
| no_glitches | pass | No blank or colour-washed frame. |
| duration | pass | The video is 6.7 s; the target was 9 s (26 % off, allowed 30 %). |
| loudness | pass | Loudness -13.9 LUFS, true peak -2.1 dBTP is in range. |
| change_on_word | pass | 100 % of the 9 picture changes land on a spoken word (aim for 75 %). |
| pictures_per_words | FAIL | 75 % of the 4 pictures carry 4 to 12 words. |
| same_design | pass | All 4 scenes use the same picture design. |

## A10

| Judge | Result | Says |
|---|---|---|
| first_frame | pass | The first frame has a picture and the first word comes at 0.02 s. |
| nothing_still | pass | The longest stretch with nothing new is 2.2 s (at 129.8 s). |
| no_glitches | pass | No blank or colour-washed frame. |
| duration | FAIL | The video is 143.6 s; the target was 210 s (32 % off, allowed 30 %). |
| loudness | pass | Loudness -14.0 LUFS, true peak -1.4 dBTP is in range. |
| change_on_word | pass | 99 % of the 176 picture changes land on a spoken word (aim for 75 %). |
| pictures_per_words | pass | 92 % of the 61 pictures carry 4 to 11 words. |
| same_design | pass | All 66 scenes use the same picture design. |
