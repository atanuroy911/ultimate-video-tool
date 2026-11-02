"""Claude as the director of the billionaire video: the same plan operations MCP exposes (set_cast, set_place, merge, set_prompt,
set_moment_place, set_medium), applied to a copy of the local AI's draft so both directors start from the same moments."""
import json
import shutil
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vt import craft  # noqa: E402
from vt.direction import plan_doc as PD  # noqa: E402
from vt.project import Project  # noqa: E402

P = Path(r"C:\Users\Roy\Videos\Video Tool Lab\story\projects")
SRC, DST = P / "2026-11-01-billionaire-tax-local-ai", P / "2026-11-01-billionaire-tax-claude"
if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST, ignore=shutil.ignore_patterns("exports", "composition", "snapshots", "cover_*", "qa_frames", "media", "comfy_stills.json"))
meta = json.loads((DST / "project.json").read_text(encoding="utf-8"))
meta.update(id=DST.name, title="Billionaire tax (claude)", media=[])
(DST / "project.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
proj = Project(DST.name, DST.parent)
plan = PD.PlanDoc.model_validate(json.loads((DST / "plan_doc.json").read_text(encoding="utf-8")))
plan.state = "draft"
for m in plan.moments:
    m.media, m.status, m.place = "", "planned", ""


def op(**o):
    return PD.apply_edit(plan, o, proj)


def at(text):                                         # the moment whose line starts with this text (ids shift after merges)
    return next(m.id for m in plan.moments if m.text.startswith(text))


# the cast: two people the viewer tells apart at a glance
plan.idea.cast = {}
op(op="set_cast", name="Jack", text="a man of about thirty, slim, short messy brown hair, a blue work shirt with rolled sleeves")
op(op="set_cast", name="Mr. Rich", text="a round man of about sixty, bald with a grey moustache, a navy three-piece suit and a gold pocket watch")
plan.idea.character = ""
# the places: what is visible, and how big
plan.idea.places = {}
for name, text in {
    "flat": "Jack's small rented flat: a tiny kitchen table by a window, a kettle, a pile of envelopes, the ceiling just above his head",
    "tower office": "on the top floor of a glass office tower: a long dark desk, a huge window, the city far below and tiny",
    "bank": "a marble bank hall: columns ten times taller than a person, a loan desk with a green lamp",
    "mansion": "outside a white mansion: a fountain, a long gravel drive, the house many times taller than a person",
    "newsroom": "a reporters' office at night: desks under lamps, tall stacks of paper files and folders",
    "street": "a city street: Jack's small brick block of flats on one side, a glass tower rising far behind it",
}.items():
    op(op="set_place", name=name, text=text)
# whole sentences, one picture each, where the voice split them
for first in ("Some years, Mr.", "In 2021, reporters at", "In 2021, reporters at", "Jeff Bezos paid no federal", "Jeff Bezos paid no federal",
              "And the price the tax"):
    op(op="merge", moment=at(first))

DRAW = [  # (line starts with, place, what the picture shows)
    ("Why do billionaires", "street", "Wide view: Jack stands small on the pavement, looking up at a glass tower that rises far above him into the clouds"),
    ("Meet Jack.", "flat", "Jack smiles at the viewer, holding a mug of tea at his kitchen table, medium shot"),
    ("Jack earns", "flat", "Jack opens a pay envelope at his kitchen table, a modest fan of banknotes inside, pleased"),
    ("Every month he gets paid", "flat", "Close-up of Jack's hand pinning a pay envelope to a kitchen calendar full of crossed-off days"),
    ("Every month he pays tax", "flat", "Jack hands a third of his banknotes across the table to a grey-suited tax clerk, his face falling"),
    ("Now meet Mr. Rich", "tower office", "Mr. Rich leans back in a huge leather chair behind his long desk, hands folded, smiling"),
    ("owns a company", "tower office", "Mr. Rich stands at the huge window, looking down at a whole skyline of glass towers below him"),
    ("Some years, Mr.", "street", "Jack bent under a heavy sack on his back, while Mr. Rich strolls beside him twirling a feather"),
    ("And it is legal", "tower office", "Mr. Rich shrugs at the viewer with a calm smile, a closed law book on the desk under his hand"),
    ("Here is the secret", "flat", "Jack holds up his pay envelope toward the viewer, close-up"),
    ("Mr. Rich gets richer", "tower office", "Mr. Rich watches a stack of gold coins on his desk grow taller than his head"),
    ("Mr. Rich owns shares", "tower office", "Mr. Rich fans out a thick stack of ornate paper certificates on his desk"),
    ("One share is worth", "tower office", "Close-up of one ornate paper certificate next to a single small stack of coins"),
    ("A year later", "tower office", "The same certificate now next to two stacks of coins, twice as tall, a calendar page flying away"),
    ("He is richer", "tower office", "Mr. Rich hugs his stack of certificates to his chest, every one still in his arms"),
    ("So there is no paycheck", "tower office", "Mr. Rich holds up a flat, empty pay envelope between two fingers, eyebrows raised"),
    ("And no paycheck means", "tower office", "The grey-suited tax clerk stands at Mr. Rich's desk with an empty tray, puzzled"),
    ("But then how does he buy", "mansion", "Mr. Rich gazes up at the white mansion from the gravel drive, hands in his pockets"),
    ("He goes to a bank", "bank", "Mr. Rich walks into the marble bank hall, small between the giant columns"),
    ("He says: lend me", "bank", "Mr. Rich sits at the loan desk, sliding his stack of certificates toward a banker in glasses"),
    ("If I don't pay you back", "bank", "Close-up of the banker's hand resting on top of Mr. Rich's certificates"),
    ("you can keep some", "bank", "The banker shakes hands with Mr. Rich and pushes a big bundle of banknotes across the desk"),
    ("He buys the mansion", "mansion", "Mr. Rich holds up a large brass key in front of the white mansion, beaming"),
    ("So no tax.", "mansion", "The grey-suited tax clerk stands at the mansion gate with an empty tray, looking in"),
    ("Of course, he must pay", "bank", "Mr. Rich hands the banker a small bag of coins while the banker writes in a ledger"),
    ("But he can pay it", "bank", "Mr. Rich takes a second bundle of banknotes from the banker and passes it straight back, winking"),
    ("Does anyone really", "street", "Jack stops on the pavement and frowns up at the glass tower, scratching his head"),
    ("In 2021, reporters", "newsroom", "Two reporters lean over a desk piled with thick folders of tax records under a lamp, one pointing at a page"),
    ("Jeff Bezos paid no", "newsroom", "Close-up of a newspaper front page on the reporters' desk, a large photograph of a glass tower on it, a coffee cup beside it"),
    ("So what happens when", "tower office", "Mr. Rich holds his stack of certificates over a paper shredder, then pulls it back, thinking"),
    ("He pays tax on his profit", "tower office", "Mr. Rich sits in his chair, arms crossed, eyes closed, a clock on the wall behind him"),
    ("And waits.", "tower office", "The same office, the window behind Mr. Rich now dark with night and stars, Mr. Rich still sitting"),
    ("When he dies", "mansion", "Two young adults in black stand on the mansion steps, holding Mr. Rich's stack of certificates"),
    ("And the price the tax", "tower office", "Close-up of an old brass desk counter whose wheels spin back to zero"),
    ("Years of profit", "mansion", "The grey-suited tax clerk walks away down the gravel drive with an empty tray, shoulders slumped"),
    ("Why can't Jack", "flat", "Jack sits at his kitchen table, chin on his hand, looking at the pile of envelopes"),
    ("Because Jack needs", "flat", "Jack counts banknotes into an envelope while his landlord waits at the open door"),
    ("Mr. Rich can wait", "tower office", "Mr. Rich naps in his leather chair, feet up on the desk"),
    ("The tax system does not", "street", "Jack and Mr. Rich stand side by side on the pavement, the tower behind them"),
    ("So here is the real", "flat", "Jack looks straight at the viewer, close-up"),
    ("If owning things", "street", "Jack looks up at the glass tower from his doorstep, thoughtful, wide view"),
    ("why were we only", "flat", "Jack holds his pay envelope in one hand and a single ornate certificate in the other, looking from one to the other"),
]
for start, place, draw in DRAW:
    mid = at(start)
    op(op="set_prompt", moment=mid, text=draw)
    op(op="set_moment_place", moment=mid, place=place)
for start, word in (("People call it", "BUY. BORROW. DIE."), ("It taxes how money", "HOW MONEY REACHES YOU")):
    m = plan.moment(at(start))
    m.card = word
    op(op="set_medium", moment=m.id, medium="card")
PD.save(DST, plan)

made = [m for m in plan.moments if m.medium == "made"]
left = [m.id for m in made if not any(m.text.startswith(s) for s, _, _ in DRAW)]
print(len(plan.moments), "moments,", len(made), "pictures, not directed:", left)
shots = [(m.id, f"{m.draw} {plan.idea.places.get(m.place, '')}") for m in made]
print("place problems:", craft.place_problems(shots) or "none")
print("drawable problems:", craft.drawable_problems([(m.id, m.draw) for m in plan.moments]) or "none")
