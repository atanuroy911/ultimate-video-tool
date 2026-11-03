"""The reel look: a script becomes a video of one picture drawn for each stretch of speech, in one style, with the key word lit in the caption.

reading.py  read the script like a director (kind of video, hook, what each sentence should show, the turns), AI first, rules as the safety net
style.py    one drawing style for the whole video, and the picture prompt
slots.py    group sentences into slots from the content (steps are slower than a story; a new point starts a slot)
plan.py     draw a picture for each slot on the ComfyUI server and write the scenes
"""
