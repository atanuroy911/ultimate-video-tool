"""Pure production-contract fixture for software-browser C3/C4 checks; no project, model or media processing."""
from pathlib import Path
import json
import sys
from typing import get_args

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))

from vt.schema import Beat, Beats, CharacterId, Pose, Transcript, Word
from vt.script.compile import compile_script
from vt.script.models import VideoScript
from vt.script.story_kit import apply_story_kit

tr = Transcript(words=[Word(id="w1", text="Five", start=0, end=1)])
beats = Beats(beats=[Beat(id="b1", word_ids=["w1"], start=0, end=2, text="Five")])
script = VideoScript.model_validate({"kind": "cartoon", "cast": [{"id": "maya", "name": "Maya"}],
                                    "scenes": [{"id": "s1", "beats": ["b1"], "actions": [{"who": "maya", "do": "count", "count": 5, "at_word": "w1"}]}]})
plan = apply_story_kit(compile_script(script, tr, beats), script, tr, beats, "classic", motifs=False)
print(json.dumps({"who": get_args(CharacterId), "poses": get_args(Pose), "count5": plan.scenes[0].elements[0].model_dump(exclude_none=True)}))
