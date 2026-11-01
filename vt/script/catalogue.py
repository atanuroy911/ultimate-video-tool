"""Everything a Video Script may name. Prompts, validation, repair and the stick engine all read this one file, so they cannot drift apart."""
from __future__ import annotations

RIGS = {"stick-basic": "A 15-joint stick figure (round head, neck, chest, hips, two-bone arms and legs)."}
HEADS = ["round", "oval", "square"]
ACCESSORIES = ["none", "glasses", "hat", "tie", "labcoat", "hair", "cap", "scarf", "beard", "bow", "crown", "headband", "apron", "backpack", "helmet", "mask"]
HEIGHTS = ["child", "adult", "elder"]                       # how tall and how stooped a figure is
HAIRS = ["none", "short", "long", "bun", "curly"]
KINDS_OF_CAST = ["person", "emoji", "toon"]                  # "toon": an illustrated cartoon character from assets/cartoon (vt/art/toon.py), named by `art`
TOON_CHARACTERS = {"bill": "a boy in a cap and hoodie", "ted": "a curly-haired boy in a green jacket", "jane": "a girl in a pink dress", "max": "a white dog in a red hoodie"}
TOON_SCENES = {"backyard": "a backyard with a tree and a picnic table", "living_room": "a living room with a sofa", "park": "a park with trees and a bench", "street": "a street with houses"}                          # an "emoji" cast member is an actor drawn from a sticker: an animal, a coin, a wallet, a bulb
TIMES = ["day", "dawn", "evening", "night"]
WEATHERS = ["none", "rain", "snow"]
MARKS = ["exclaim", "question", "idea", "heart", "anger", "sweat", "zzz", "sparkle"]      # a small sign that pops above a head or an object
ROLES = ["narrator", "teacher", "student", "customer", "seller", "scientist", "boss", "worker", "friend", "child", "elder", "robot",
         "doctor", "farmer", "cook", "police", "thief", "king", "artist", "athlete", "driver", "animal", "object"]

# verb -> (what it looks like, default seconds, required params)
VERBS: dict[str, tuple[str, float, tuple[str, ...]]] = {
    "idle": ("stands and breathes", 1.0, ()),
    "walk_in": ("walks onto the screen from a side to a position", 1.4, ("from",)),
    "walk_out": ("walks off the screen to a side", 1.2, ("to_side",)),
    "walk_to": ("walks to a position", 1.2, ("to",)),
    "run": ("runs to a position (faster, leaning forward)", 0.8, ("to",)),
    "turn": ("turns to face left or right", 0.5, ("side",)),
    "point": ("extends an arm to point at a prop, a character or the viewer", 0.9, ("target",)),
    "wave": ("waves a hand hello or goodbye", 1.2, ()),
    "nod": ("nods yes", 0.7, ()),
    "shake_head": ("shakes the head no", 0.8, ()),
    "shrug": ("shrugs with open palms: unsure", 1.0, ()),
    "think": ("hand on chin, a thought mark appears", 1.5, ()),
    "explain": ("open palms, talking with the hands", 1.8, ()),
    "count": ("counts on fingers (1 to 5)", 1.5, ("count",)),
    "carry": ("picks up and carries a prop", 1.3, ("prop",)),
    "drop": ("puts a carried prop down", 0.8, ()),
    "push": ("pushes a prop or a person", 1.0, ("target",)),
    "pull": ("pulls a prop or a person", 1.0, ("target",)),
    "sit": ("sits down", 0.9, ()),
    "stand": ("stands up", 0.9, ()),
    "jump": ("jumps in the air", 0.8, ()),
    "fall": ("trips and falls", 1.0, ()),
    "celebrate": ("both arms up, cheering", 1.5, ()),
    "facepalm": ("hand on forehead: oops", 1.2, ()),
    "write_board": ("writes on the board", 1.8, ("bubble",)),
    "hold_sign": ("holds up a sign with text or a number", 2.0, ("bubble",)),
    "look_at": ("turns the head toward a prop or character", 0.7, ("target",)),
    "say": ("speaks: a speech bubble with the words, mouth moves", 2.0, ("bubble",)),
    "react": ("shows a feeling with face and body", 1.2, ("emotion",)),
    "high_five": ("high-fives another character", 1.0, ("target",)),
    "handshake": ("shakes hands with another character", 1.2, ("target",)),
    # --- added by Phase 13: things a story needs besides talking
    "clap": ("claps hands", 1.2, ()),
    "bow": ("bows politely", 1.0, ()),
    "laugh": ("laughs out loud, shoulders shaking", 1.4, ()),
    "cry": ("cries, hands to the face", 1.6, ()),
    "yawn": ("yawns and stretches", 1.5, ()),
    "dance": ("dances, arms and knees swinging", 1.8, ()),
    "phone": ("holds a phone to the ear", 1.8, ()),
    "type": ("types on a keyboard", 1.6, ()),
    "eat": ("eats or drinks, hand to mouth", 1.4, ()),
    "lift": ("strains to lift something heavy", 1.5, ("prop",)),
    "throw": ("throws a prop toward a character or a spot", 1.1, ("prop", "target")),
    "give": ("hands a prop to another character", 1.3, ("prop", "target")),
    "chase": ("runs after someone or something, leaning forward", 1.0, ("to",)),
    "follow": ("walks behind a character", 1.3, ("to",)),
    "sneak": ("tiptoes low and quiet", 1.4, ("to",)),
    "hide": ("ducks behind a prop", 1.2, ("target",)),
    "peek": ("leans out to look", 1.0, ()),
    "hug": ("hugs another character", 1.5, ("target",)),
    "argue": ("shakes a fist and shouts", 1.6, ()),
    "wave_both": ("waves both arms: look here", 1.2, ()),
    "mark": ("a small sign pops above the head: !, ?, light bulb, heart, anger, sweat, zzz", 1.2, ("mark",)),
    "bounce": ("an actor or prop bounces up and down", 1.0, ()),
    "spin": ("an actor or prop spins around", 1.0, ()),
    "grow": ("an actor or prop swells bigger", 1.0, ()),
    "appear": ("an actor or prop pops into view", 0.7, ()),
    "fly": ("an actor or prop flies across to a position", 1.2, ("to",)),
}
VERB_SYNONYMS = {
    "walk": "walk_to", "enter": "walk_in", "exit": "walk_out", "leave": "walk_out", "sprint": "run", "hurry": "run", "come_in": "walk_in", "pointing": "point",
    "talk": "say", "speak": "say", "shout": "say", "ask": "say", "answer": "say", "tell": "say", "smile": "react", "laugh": "react", "cry": "react",
    "wonder": "think", "ponder": "think", "cheer": "celebrate", "clap": "celebrate", "write": "write_board", "draw": "write_board", "show": "hold_sign",
    "sign": "hold_sign", "look": "look_at", "watch": "look_at", "gesture": "explain", "present": "explain", "lift": "carry", "pick_up": "carry",
    "put_down": "drop", "sit_down": "sit", "stand_up": "stand", "hello": "wave", "bye": "wave", "agree": "nod", "disagree": "shake_head",
    "hi5": "high_five", "trip": "fall", "giggle": "laugh", "weep": "cry", "sob": "cry", "stretch": "yawn", "call": "phone", "dial": "phone", "drink": "eat", "hand_over": "give",
    "pass": "give", "toss": "throw", "run_after": "chase", "tiptoe": "sneak", "duck": "hide", "lean_out": "peek", "fight": "argue", "shout_at": "argue", "swell": "grow", "pop": "appear",
    "fly_to": "fly", "jig": "dance", "type_on": "type", "applaud": "clap",
}
EMOTIONS = ["neutral", "happy", "sad", "angry", "surprised", "confused", "scared"]
EMOTION_SYNONYMS = {"shocked": "surprised", "amazed": "surprised", "excited": "happy", "joy": "happy", "glad": "happy", "upset": "sad", "worried": "scared",
                    "afraid": "scared", "mad": "angry", "puzzled": "confused", "curious": "confused", "calm": "neutral"}

SETS: dict[str, tuple[str, ...]] = {
    "plain": ("sign",),
    "classroom": ("board", "desk", "door", "window", "book"),
    "office": ("desk", "laptop", "door", "chart", "plant"),
    "street": ("lamp", "bench", "car", "shop", "tree"),
    "nature": ("tree", "rock", "river", "sun", "flower"),
    "lab": ("table", "flask", "board", "microscope", "door"),
    "space": ("planet", "rocket", "star", "moon"),
    "home": ("sofa", "table", "tv", "door", "window"),
    "stage": ("podium", "screen", "curtain"),
    "market": ("stall", "basket", "scale", "sign"),
    # --- added by Phase 13
    "kitchen": ("table", "stove", "fridge", "window", "plate"),
    "school_yard": ("tree", "bench", "ball", "swing", "fence"),
    "bank": ("desk", "safe", "sign", "plant", "door"),
    "hospital": ("bed", "screen", "door", "plant", "lamp"),
    "shop_inside": ("shelf", "counter", "basket", "sign", "door"),
    "factory": ("machine", "pipe", "crate", "gauge", "lamp"),
    "farm": ("barn", "fence", "tree", "haystack", "sun"),
    "airport": ("sign", "bench", "plane", "suitcase", "window"),
    "city": ("tower", "lamp", "car", "tree", "sign"),
    "mountain": ("peak", "tree", "rock", "sun", "flag"),
    "island": ("palm", "rock", "river", "sun", "boat"),
    "courtroom": ("podium", "desk", "scale", "door", "window"),
    "screen_world": ("screen", "chart", "laptop", "sign", "star"),
}
SIDES = ["left", "right", "top", "bottom"]
SHOTS = ["wide", "medium", "close"]
MOVES = ["none", "push_in", "pull_out", "pan_left", "pan_right", "follow", "shake", "zoom_to"]      # zoom_to: push toward the `focus` prop or character of the scene
SFX = ["pop", "ding", "whoosh", "click"]
KINDS = ["stick", "emoji", "explainer", "infographic", "cartoon", "mixed"]
SPECIAL_TARGETS = ("viewer", "board", "camera")


def verb_seconds(verb: str) -> float:
    return VERBS[verb][1]


def catalogue_text() -> str:
    """The catalogue as the plain text a prompt includes."""
    lines = ["RIGS: " + ", ".join(f"{k} ({v})" for k, v in RIGS.items()),
             "CHARACTER STYLE: head " + "/".join(HEADS) + "; accessory " + "/".join(ACCESSORIES) + "; role " + "/".join(ROLES),
             "VERBS (do): "]
    for v, (desc, secs, req) in VERBS.items():
        lines.append(f"  - {v}: {desc} (~{secs}s)" + (f"; needs {', '.join(req)}" if req else ""))
    lines += ["EMOTIONS: " + ", ".join(EMOTIONS), "SETS AND THEIR PROPS:"]
    lines += [f"  - {k}: {', '.join(v)}" for k, v in SETS.items()]
    lines += ["SIDES: " + ", ".join(SIDES), "CAMERA shot: " + ", ".join(SHOTS) + "; move: " + ", ".join(MOVES),
              "SFX: " + ", ".join(SFX), "special targets: " + ", ".join(SPECIAL_TARGETS) + " or a cast id or a prop of the scene's set"]
    return "\n".join(lines)
