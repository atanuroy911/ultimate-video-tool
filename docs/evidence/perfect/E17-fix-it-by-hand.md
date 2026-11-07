# E17: fix any element by hand (decision 9, human in the loop)

Done on 2026-11-06. The owner: "having comprehensive edit option in the timeline per element like all kinds of transform warp etc.. i can fix them.... human in the loop".

## What a person can do to one element now
Everything is on the element in the editor (Position tab and Motion tab) and on the picture itself:
- **Move and size, as before:** left and right, up and down, size, rotate, opacity, each now with a slider, a number to type and a way back (double-click the slider too).
- **Stretch and slant:** stretch across and up and down on top of size (10 % to 500 %), slant sideways and up and down (±60°), mirror left and right and top and bottom.
- **Tilt in 3D:** lean back or forward, turn left or right (±80°, with perspective).
- **Pivot:** the point it turns, slants and tilts around.
- **Crop:** cut away the top, right, bottom, left, with rounded corners (a card, a pill, a circle).
- **Corner pin (warp):** each of the four corners moves on its own.
- **Blur and blend:** blur up to 60 px; normal, multiply, screen, overlay, darker only, lighter only, soft light, difference.
- **Motion points** hold stretch, slant, tilt and blur as well (the Motion tab), animated on the video clock.
- **On the picture:** a box with handles around the selected element: drag to move, a corner to size, the knob to turn; a **Pin the corners** mode puts four pins on the real corners (rotation, tilt and warp included). The arrow keys nudge by 1 %, with shift by 10 %.
- Undo and redo cover every change (the editor's own history). One button takes all the new effects away.

## How it is built
- **Data** (`schema.py` `Transform`, one optional `transform` on every element, `visual_motion.py` `MotionPoint` with seven more numbers). Everything is neutral by default and out of the way: an element with nothing set is not a hand-placed one and nothing changes for old plans or for the directors' prompts (the schema adds one small `$ref`, not fifteen fields per element). An element with anything set is a free element, as with x and y: no rule moves it.
- **Renderer** (`vt-keyframes.js` `look`, `warp`, `keyframes`): one function builds the look for preview, editor and export. Size, stretch, flip, rotation, slant, tilt, pivot and opacity go through GSAP on the element's own wrapper, so keyframes tween the same values. The corner pin is a projective `matrix3d` worked out from the four corners once the box is measured (after the fonts). The crop is `clip-path: inset(... round ...)`.
- **Studio:** `TransformControls.tsx` (the controls), `TransformHandles.tsx` and `gestures.ts` (the hand on the picture, pure maths that the node tests cover), `transformMath.ts` (what is neutral, how a change moves a whole animated path), the page reports where the real corners are (`rect` message).
- A **bug found on the way:** an automatic element that was first changed jumped to the middle of the frame (x and y defaulted to 50 % and 45 %). Gestures now take over where it is.

## Checks
- `tests/test_element_transform.py`, 43 checks: the data (defaults change nothing; each of 15 fields validates and round-trips; 13 values that cannot be drawn are refused in a sentence; a neutral transform is not free, any set one is; old keyframe points mean what they meant), the real page (stretch changes width and height apart; a slant widens the box by exactly `height * tan(angle)`; a flip mirrors without moving; the pivot is what it swings around; a tilt foreshortens; a corner pin moves the four corners; crop, blur and blend are set; keyframes tween the new values on the clock; an old element draws as it did), recomposing keeps every field, no rule hides or fits a transformed element (the guard drops the automatic tag of a crowd and not the person's), and **the export draws what the preview draws** (the HyperFrames frame and a browser screenshot of the same composition differ by under 2.5 of 255, and the transform really changed the frame).
- `client/studio/tests/element-transform.test.mjs`, 9 checks of the Studio's own maths (transform tidy, the live preview's free flag, move, size, turn, corner pin through size and rotation, a motion path following a stretch, sampled points).
- `client/studio/e2e/transform.mjs`, 42 browser checks: typing a number saves it and the picture follows; undo, redo, double-click and the reset button; the flip toggle; tilt, crop, rounded corners, blur and blend together; the handles move, size, turn and pin; the arrow keys; motion points keep the new values; phone width in light and dark (a finger-sized number and reset, no sideways scroll). Screenshots viewed (`client/studio/e2e/out/transform/`).
- Mutation checks: see the end of this file.

## Left (in BREAKING.md)
- The keyframe diamond beside each value is not there: points are added in the Motion tab ("Save a point here"), where every value of the point has its slider.
- A corner pin set while the element is also tilted or slanted moves the pin by the hand's distance without undoing the tilt (right for turn and size).
- Media layers (the timeline's own clips) use the same keyframe code, so stretch, slant, tilt and blur animate on them, but they have no static look controls yet.

Mutation checks: 16 of 16 caught on the data and page side, 9 of 9 on the Studio maths (one first missed: the take-over test now uses an off-centre element).
