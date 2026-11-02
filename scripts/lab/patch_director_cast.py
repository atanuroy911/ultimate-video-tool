"""The local director keeps the script's people (owner's billionaire script: Jack and Mr. Rich became 'a generic figure') and puts no words
in pictures. It returns a cast (name -> look) that goes into the plan like the places."""
from pathlib import Path

R = Path(__file__).resolve().parents[2]


def sub(path, old, new):
    p = R / path
    s = p.read_text(encoding="utf-8")
    assert old in s, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


F = "vt/reel/reading.py"
sub(F, '''"Never describe a real person's face or likeness; use a generic figure. Draw SCENES, not icons: for each sentence describe one scene in which the recurring "''',
    '''"Never describe a real, famous person's face or likeness. People the script names (Jack, Mr. Rich, Mira) are characters: call them by their name in "
    "every `draw` (never 'a figure', 'a man', 'someone') and give each a look once in `cast`. Pictures carry no words, letters, numbers or signs (the "
    "captions say them): show an amount as things you can see (a thick stack of cash, a tall glass office tower). Draw SCENES, not icons: for each sentence describe one scene in which the recurring "''')
sub(F, '''"and ALWAYS a short generic description of ONE recurring figure who appears in the pictures (age, clothes, hair; no real person; for a science or health topic a simple stick-like person is fine). Rate how strong the first sentence "''',
    '''"the `cast`: for every person the script names, their name and a short look (age, build, clothes, hair) that tells them apart at a glance; and "
        "ALWAYS a short generic description of ONE recurring figure for when no one is named (no real person; for a science or health topic a simple stick-like person is fine). Rate how strong the first sentence "''')
sub(F, '''        "character": {"type": "string"},
''', '''        "character": {"type": "string"},
        "cast": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "looks": {"type": "string"}}, "required": ["name", "looks"]}},
''')
sub(F, '''            base.places = {''', '''            base.cast = {str(c.get("name", "")).strip()[:30]: str(c.get("looks", ""))[:160] for c in (data.get("cast") or [])[:6] if c.get("name") and c.get("looks")}
            base.places = {''')
sub(F, '''    places: dict[str, str] = Field(default_factory=dict, description="name''', '''    cast: dict[str, str] = Field(default_factory=dict, description="name -> how the person looks; every picture that names them gets the look")
    places: dict[str, str] = Field(default_factory=dict, description="name''')
sub("vt/direction/plan_doc.py", '''places=dict(reading.places), pace=pace,''', '''places=dict(reading.places), cast=dict(reading.cast), pace=pace,''')
print("ok")
