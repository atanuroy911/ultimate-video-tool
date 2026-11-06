# K1: the cards Video Tool may use

## What changed
- `server/vt/gpuassign.py`:
  - New saved setting `gpu.allowed`: a list of card uuids. No key means the person was never asked; an empty list is an answer (no card, the processor does the work).
  - `allowed()` = the cards the launcher lets the server see, narrowed to the person's list. The launcher's own `CUDA_VISIBLE_DEVICES` is read **once, at import** (`_PIN`), because K2 will set that variable itself from the allowed list and the fence must stay what the launcher said.
  - `needs_choice()` = two or more cards and no answer that still means something (never answered, or every card they chose is gone).
  - Until the person answers, with two or more cards, Video Tool uses **one** card: the freest of the cards no other program is working on right now (programs of Video Tool's own do not count), or the freest card when every card has someone on it. Never all of them.
  - `save({"allowed": [...]})`: uuids, indexes or names, a text such as `"0, 1"`, `"all"`, or `[]`. A card that is not in this computer, or that the launcher fenced off, is refused with a sentence. A job choice made in the same save is checked against the new list. When a card stops being allowed, any choice (primary, render, speech) that pointed at it goes back to the default.
  - `_auto` and every fallback choose only among allowed cards (they always did through `resolve`, which now gets the narrower list).
  - `cuda_index()` now counts a card among the cards the process can really see (what `CUDA_VISIBLE_DEVICES` says right now, in its order), not among the allowed ones. Before K2 applies the list the process still sees every card, so counting among the allowed would have sent speech recognition to the wrong card (the V100 as device 0).
  - `describe()` gives each card `allowed` and `using` (label, GB, whether it is Video Tool's own), plus `needs_choice` and `allowed_saved`.
- Ways in: `PUT /api/system/gpu` takes `allowed`; `vt gpu` shows what is allowed and what uses each card, and says when nobody has chosen; `vt gpu allow <cards|all|none>` (new); the MCP tool `gpu_assignment` takes `allowed`.
- Tests: `tests/test_gpu_choice.py` (new, 24) and `tests/test_gpuassign.py` (9, its fixture now answers "both cards" first and sets `_PIN` where it tests the fence).

## Checks (local, fake cards, 2026-11-06)
- `tests/test_gpu_choice.py` + the older GPU and engine test files: **69 passed** (`test_engine_fit`, `test_engine_placement`, `test_gpu_detect`, `test_gpuassign`, `test_gpu_choice`, `test_gpu`).
- Cases covered: one card; two cards with training on one (the idle one is used, even when the busy one has the most room); every card busy (the freest one only); Video Tool's own programs not counted as busy; three cards, never more than one by default; no card at all; an answer limiting every job and fallback; cards named by uuid, index, name, `all`; an unknown card refused and nothing written; an empty list; the order of cards is the driver's; a job choice in the same save; taking a card away resets the choices that pointed at it; a removed card (one left: nothing to choose); every chosen card gone (the question returns, the old answer holds again if the card comes back); the launcher's fence first (and `all` means all the fence lets through); the fence is not the variable the server sets later; a card's number counted among the cards the process sees (both, fenced, reordered, `-1`); `describe()`; the Server page's route (answer, refusal as 422, an empty list is an answer); `vt gpu` and `vt gpu allow` (answer, refusal, none, two cards) and the MCP tool.
- **Nine deliberate breakages, each caught by a test:** default uses every card; own programs counted as busy; busy cards not skipped; the fence ignored; a stale answer still counted; choices not reset; a card's number counted among the allowed; a job may pick a card that is not allowed; the live variable read as the fence.

## Not done here (the next steps)
- K2 makes it real: sets `CUDA_VISIBLE_DEVICES` from the allowed list at server start, restricts `render/browser_gpu.py`'s fallback loop and every other use of a card. Until then the list is only enforced where code asks `gpuassign` (the render card choice, speech, ONNX), so nothing is deployed to the owner's server yet (it would change nothing there until K6 sets the list).
