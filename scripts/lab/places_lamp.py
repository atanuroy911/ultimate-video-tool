"""Give The Last Lamp its places (as the director now must), fix the shots that leaned on context, check, and save as a new project."""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\Roy\Desktop\ultimate-video-tool")
from vt import craft  # noqa: E402
from vt.direction import plan_doc as PD  # noqa: E402

PROJ = Path(r"C:\Users\Roy\Videos\Video Tool Lab\story\projects")
SRC, DST = PROJ / "the-last-lamp-onegpu", PROJ / "the-last-lamp-places"
if not DST.exists():
    shutil.copytree(SRC, DST, ignore=shutil.ignore_patterns("exports", "composition", "snapshots", "cover_*", "qa_frames", "reel_report.json"))
    meta = json.loads((DST / "project.json").read_text(encoding="utf-8"))
    meta.update(id=DST.name, title="The Last Lamp (places)")
    (DST / "project.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

plan = PD.PlanDoc.model_validate(json.loads((DST / "plan_doc.json").read_text(encoding="utf-8")))
plan.state = "draft"
PLACES = {
    "cliff": "a tall white lighthouse on a rocky cliff above the sea, the lighthouse many times taller than a person, the glass lantern room at its very top",
    "lantern room": "inside the round glass lantern room at the very top of the lighthouse: windows all round, an iron floor, and in the middle a tall brass lamp "
                    "inside a beehive-shaped glass lens that is taller than a child",
    "gallery": "the narrow iron balcony that rings the outside of the lantern room at the top of the lighthouse, high above the sea, iron railing at waist height",
    "stairs": "inside the lighthouse tower: a narrow stone spiral staircase with an iron handrail winding up out of sight, small deep-set windows, curved white walls",
    "tower foot": "inside the bottom of the lighthouse tower: a small round stone room with a heavy wooden door, the first steps of the spiral stairs, pipes on the wall",
    "sea": "the open sea at night, seen from high above, the boats tiny on the water",
    "boat": "aboard a small wooden fishing boat on the open sea, the person at the stern",
    "harbour": "a small fishing harbour with little houses along the shore, the lighthouse small and far away on the cliff",
}
for name, text in PLACES.items():
    PD.apply_edit(plan, {"op": "set_place", "name": name, "text": text})
WHERE = {"s1": "cliff", "s2": "harbour", "s3": "cliff", "s4": "lantern room", "s5": "lantern room", "s6": "lantern room", "s7": "gallery", "s8": "tower foot",
         "s9": "stairs", "s10": "lantern room", "s11": "gallery", "s12": "sea", "s13": "cliff", "s14": "lantern room", "s15": "sea", "s16": "boat",
         "s17": "tower foot", "s18": "tower foot", "s19": "tower foot", "s20": "stairs", "s21": "lantern room", "s22": "lantern room", "s23": "lantern room",
         "s24": "cliff", "s25": "harbour", "s26": "stairs", "s27": "lantern room", "s28": "lantern room", "s29": "lantern room"}
GIRL, OLD = ("Mira, an eleven-year-old girl with a dark braid and a mustard-yellow raincoat",
             "her grandfather, an old fisherman with a short white beard and a navy wool sweater")
DRAW = {
    "s3": "The lighthouse on the cliff in a violent night storm, its glass lantern room at the top completely black and unlit, rain slanting, one flash of "
          "lightning showing the dark tower, wide view",
    "s10": f"{GIRL} stands on a small wooden step and polishes the huge glass lens of the lamp with a cloth, the lens taller than she is, warm amber glow "
           "on her face, medium close-up",
    "s21": f"{GIRL} turns an old bicycle upside down so it stands on its seat and handlebars on the iron floor, its wheels in the air, next to the tall dark lamp",
    "s22": f"{GIRL} kneels beside an upside-down bicycle that stands on its seat and handlebars, turning a pedal fast with her hand so the back wheel spins, "
           "a small bicycle headlamp tied to the frame, storm at the windows",
}
for mid, text in DRAW.items():
    PD.apply_edit(plan, {"op": "set_prompt", "moment": mid, "text": text})
for mid, name in WHERE.items():
    PD.apply_edit(plan, {"op": "set_moment_place", "moment": mid, "place": name})
for m in plan.moments:                              # keep every picture except the ones the edits asked to redraw
    m.status = "ready" if m.media else "planned"
PD.save(DST, plan)

shots = [(m.id, f"{m.draw} {plan.idea.places.get(m.place, '')}") for m in plan.moments if m.medium == "made"]
probs = craft.place_problems(shots)
print("place problems:", probs or "none")
print("to redraw:", [m.id for m in plan.moments if not m.media])
