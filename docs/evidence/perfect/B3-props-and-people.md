# B3: a prop the shot cuts, and a scene over a person

Done on 2026-11-06 (plan decision 1, same rule as B2: a scene any AI directed keeps what the AI placed, and the facts tell the director).

## What changed
| Where | Before | Now |
|---|---|---|
| `renderer/runtime/vt-stick.js` `frameProps` | a prop the shot cuts by more than a quarter was not drawn, for every plan | a directed scene draws it and records `would-drop` (`directed: true`); the rules' plan hides it as before. The entry names the scene the way the page does (`src` or `id`). |
| `compose/composer.py` `_keep_clear_of_people` | with no free room beside a person, every element of the scene was removed (`cleared_for_person`) | a directed scene keeps its elements and gets `no_room_beside_person`; the rules' plan clears as before; with room, everything goes beside the person for all of them. |
| `renderer/scripts/frame-facts.mjs` | nothing | "The prop window is cut by the shot: more than a quarter of it is outside the frame." and "There is no free room beside the person in the picture for this scene's elements: they sit on the picture." |
| `renderer/runtime/vt.js` | `guardLayout` started with `window.__guard = []` | **A bug found here:** the guard wiped what the stick scenes had pushed while they were drawn, so no cut prop was ever recorded (the rules' plan hid the prop and nothing said so). The log is now reset once at the start of `build`, and `window.__guardDone` says when the guard has finished (the page scripts wait for it instead of for the array). |

## Checks
`tests/test_director_authority.py` (now 61 checks, 11 for this step):
- a stick scene shot close (the kitchen of `scripts/qa_stick.py`, 16:9) cuts the window: the rules' plan hides it and records `dropped`, each of the three AI plans draws it, records `would-drop`, and the facts name it; the rules' facts say nothing.
- a scene over a picture whose person fills a tall crop: rules and manual clear it (as `tests/test_people.py` has it), the three AI plans keep the sticker and flag `no_room_beside_person`; in the wide frame all five put it beside the person.
- the facts for the three AI plans on the real page say there is no free room.
- Mutation checks, 5 of 5 caught: a directed scene's cut prop hidden again; a person's scene cleared again for an AI plan; the no-room fact removed; the cut-prop fact removed; the guard log wiped when the guard starts (the old way).

## Added during B7: set decoration is nobody's
A kind of place brings its own props (a classroom's board, door and window). In a portrait frame the shot cuts the ones at the sides in nearly every stick video, and the first version of B3 would have kept them for an AI's plan and reported each one. The composer now works out `set.scenery` (the kind's own props that no action or camera focus names) and the page does not draw a scenery prop the shot cuts, **for every plan**, without reporting it (half a window reads as a mistake and no director put it there). A prop a director names (an action's target or prop, the shot's focus) is kept for an AI's plan and told, as before. Two checks: the same close kitchen shot with the window named and not named (`test_director_authority.py`).
