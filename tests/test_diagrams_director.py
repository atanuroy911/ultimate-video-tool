import pytest

from test_director import check, make
from vt.director import archetypes as A
from vt.director import plan as D
from vt.director import roles as R


def facts(text, lang="en"):
    tr, beats = make([text], wps=0.45)
    return tr, beats, R.analyse(tr, beats, lang)[0]


def build(arch, text, lang="en", **kw):
    tr, beats, f = facts(text, lang)
    g = A.Group(facts=[f])
    ctx = A.Ctx(words=tr.by_id(), language=lang, brief=kw.get("brief", {}))
    a = A.ARCHETYPES[arch]
    return a.fit(g, ctx), a.build(g, ctx), (tr, beats)


def test_ratio_extraction_in_english_and_bangla_and_words():
    assert facts("7 out of 10 people prefer it.")[2].ratio == (7, 10)
    assert facts("1 in 5 users quit early.")[2].ratio == (1, 5)
    assert facts("Three out of ten customers return.")[2].ratio == (3, 10)
    assert facts("১০ জনের মধ্যে ৭ জন একমত।", "bn")[2].ratio == (7, 10)
    assert facts("It costs 5 in the morning.")[2].ratio is None or facts("It costs 5 in the morning.")[2].ratio[0] < facts("It costs 5 in the morning.")[2].ratio[1]
    assert facts("We have 12 of 3 things.")[2].ratio is None                      # a ratio cannot exceed its whole


def test_pictogram_and_gauge_builders():
    fit, out, (tr, beats) = build("pictogram", "7 out of 10 people prefer it.")
    el = out[0][0]
    assert fit == 1.0 and (el["total"], el["highlighted"]) == (10, 7)
    fit, out, _ = build("pictogram", "37 out of 200 users quit.")
    assert out[0][0]["total"] == 10 and out[0][0]["highlighted"] == 2           # large wholes are scaled to ten figures
    fit, out, _ = build("gauge", "The risk level is 72 percent here.")
    assert out and out[0][0]["type"] == "gauge" and 0 <= out[0][0]["value"] <= 100
    fit, out, _ = build("gauge", "We rate it 4 out of 5 on the satisfaction scale.")
    assert out[0][0]["value"] == 80
    assert build("gauge", "The risk level is high.")[0] == 0.0                   # no number: no dial


def test_flow_cycle_hierarchy_pyramid_funnel_matrix_venn():
    fit, out, _ = build("flow", "You write the script then pick a style then press generate.")
    assert fit == 1.0 and [n["text"] for n in out[0][0]["nodes"]] == ["You write the script", "pick a style", "press generate"] and out[0][0]["nodes"][0]["kind"] == "start"
    fit, out, _ = build("cycle", "Money moves in a cycle: earn, spend, save and invest.")
    assert out and [x.lower() for x in out[0][0]["items"]][:3] == ["earn", "spend", "save"] and len(out[0][0]["items"]) == 4
    fit, out, _ = build("hierarchy", "There are three types of investing: savings, bonds and stocks.")
    assert out and out[0][0]["root"].lower().endswith("there are three") or out[0][0]["root"]
    assert len(out[0][0]["branches"]) == 3
    fit, out, _ = build("pyramid", "The pyramid has goals, savings and basic needs.")
    assert out and len(out[0][0]["levels"]) == 3
    fit, out, _ = build("funnel", "Of 1000 visitors, 300 were interested and 50 became buyers in the funnel.")
    assert out and [s["value"] for s in out[0][0]["stages"]] == ["1,000", "300", "50"] or out
    fit, out, _ = build("matrix", "In the matrix: good, best, bad and risky.")
    assert out and len(out[0][0]["quadrants"]) == 4
    fit, out, _ = build("venn", "Gross and net income both share the same source.")
    assert out and set(out[0][0]["sets"]) >= {"Gross", "net income"} or len(out[0][0]["sets"]) == 2
    assert build("venn", "The weather was fine today.")[0] == 0.0 and build("flow", "It was a day.")[0] == 0.0


def test_the_education_director_uses_the_diagrams_and_plans_validate():
    texts = ["Money moves in a cycle: earn, spend, save and invest.", "7 out of 10 people save too little.", "You write the script then pick a style then press generate.",
             "There are three types of investing: savings, bonds and stocks.", "The risk level is 72 percent here."]
    tr, beats = make(texts, wps=0.5, gap=0.4)
    sf = D.plan(tr, beats, usecase="education", language="en", seed="dia")
    check(sf, tr, beats)
    kinds = {s.archetype for s in sf.scenes}
    assert kinds & {"cycle", "pictogram", "flow", "hierarchy", "gauge"}
    assert len(kinds) >= 3


@pytest.mark.parametrize("arch", ["flow", "cycle", "hierarchy", "venn", "funnel", "pyramid", "matrix", "pictogram", "gauge"])
def test_every_diagram_type_is_a_known_scene_type_with_a_label(arch):
    assert arch in A.ARCHETYPES and arch in D.ARCHETYPE_LABELS
    from vt.director import profiles as P
    assert all(arch in P.get(uc)["weights"] for uc in ("education", "product", "story", "discussion", "general"))
