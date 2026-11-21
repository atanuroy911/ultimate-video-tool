"""Code-native shots (docs/plans/PLAN-CODE-NATIVE-EDITOR.MD, C1): a shot is HTML an agent wrote, plus the visual editor's overrides, which are checked,
written in as CSS and text without touching the shot's code, and rendered by our renderer with the shot's own animation intact."""
import shutil
from pathlib import Path

import pytest

from vt import shots

SPIKE = Path(__file__).resolve().parents[1] / "docs" / "dev" / "spikes" / "html-shot"


@pytest.fixture()
def shot(tmp_path):
    d = tmp_path / "shots" / "intro"
    d.mkdir(parents=True)
    for name in ("index.html", "shot.json"):
        shutil.copy(SPIKE / name, d / name)
    return d


def test_a_shot_says_what_it_is_and_which_elements_can_be_selected(shot):
    i = shots.info(shot)
    assert (i["duration"], i["width"], i["height"], i["root"]) == (3.0, 1920, 1080, "root")
    assert [k["name"] for k in i["knobs"]] == ["--bg", "--ink", "--accent", "--title-size"]
    assert shots.ids_in((shot / "index.html").read_text(encoding="utf-8")) == ["orb", "title", "sub", "bar"]


def test_a_shot_without_a_timed_root_is_refused(tmp_path):
    (tmp_path / "index.html").write_text("<html><body><div>no root</div></body></html>", encoding="utf-8")
    with pytest.raises(shots.ShotError, match="data-composition-id"):
        shots.info(tmp_path)


def test_overrides_become_css_that_adds_to_the_animation():
    o = shots.check_overrides({"knobs": {"--accent": "#22c55e"},
                               "elements": {"title": {"x": 10, "y": -40.5, "scale": 1.2, "rotate": 3, "style": {"fontWeight": "700", "opacity": 0.5}},
                                            "bar": {"hidden": True}}})
    css = shots.overrides_css(o)
    assert ":root{--accent:#22c55e !important;}" in css
    assert '[data-vt-id="title"]{translate:10px -40.5px !important;scale:1.2 !important;rotate:3deg !important;font-weight:700 !important;opacity:0.5 !important;}' in css
    assert '[data-vt-id="bar"]{display:none !important;}' in css
    assert "transform" not in css, "the shot animates transform; the editor uses translate/scale/rotate so both apply"


@pytest.mark.parametrize("bad", [
    {"knobs": {"accent": "red"}},                                            # not a CSS variable
    {"knobs": {"--accent": "red;} body{display:none"}},                     # breaking out of the rule
    {"knobs": {"--accent": "url(</style><script>alert(1)</script>)"}},
    {"elements": {"title\"]{}": {"x": 1}}},                                  # a selector break-out in the id
    {"elements": {"title": {"onclick": "x"}}},                               # a field the editor does not have
    {"elements": {"title": {"style": {"color": "red; background:url(x)"}}}},
    {"elements": {"title": {"style": {"position": "fixed"}}}},
    {"elements": {"title": {"x": float("nan")}}},
    {"elements": {"title": {"scale": 0}}},
    {"elements": {"title": {"hidden": "yes"}}},
    {"elements": {"title": {"text": "x" * 3000}}},
    {"timing": {}},
])
def test_overrides_that_could_break_the_page_are_refused(bad):
    with pytest.raises(shots.ShotError):
        shots.check_overrides(bad)


def test_build_adds_the_csp_the_css_and_the_text_before_the_shots_script(shot, tmp_path):
    shots.save_overrides(shot, {"elements": {"title": {"text": "Sleep is a habit </script><b>x"}}, "knobs": {"--bg": "#fffaf0"}})
    out = shots.build(shot, tmp_path / "build")
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'http-equiv="Content-Security-Policy"' in html and "default-src 'self'" in html
    assert html.index('<style id="vt-overrides">') < html.index("</head>")
    assert "Sleep is a habit <\\/script><b>x" in html, "the text cannot close the script"
    assert html.index("Sleep is a habit") < html.index('<script src="runtime/gsap.min.js">'), "text first, then the timeline that may measure it"
    assert (out / "runtime" / "gsap.min.js").exists() and (out / "fonts" / "fonts.css").exists()
    original = (shot / "index.html").read_text(encoding="utf-8")
    assert "Sleep is a habit" not in original, "the visual editor never rewrites the shot's code"


def test_saved_overrides_are_read_back_checked(shot):
    shots.save_overrides(shot, {"elements": {"orb": {"x": -140, "scale": 0.8}}})
    assert shots.read_json(shot / "overrides.json", {})["elements"]["orb"] == {"x": -140.0, "scale": 0.8}
    (shot / "overrides.json").write_text('{"elements": {"orb": {"x": "1px; color:red"}}}', encoding="utf-8")
    with pytest.raises(shots.ShotError):
        shots.build(shot, shot.parent / "b")


@pytest.mark.slow
@pytest.mark.browser
def test_the_rendered_frame_shows_the_edits_and_is_the_same_every_time(shot, tmp_path):
    from PIL import Image

    edits = {"knobs": {"--bg": "#fffaf0", "--accent": "#22c55e"}, "elements": {"title": {"text": "Sleep is a habit", "y": -40}, "sub": {"hidden": True}}}
    a = shots.frames(shot, tmp_path / "a", [2.0], overrides=edits)
    b = shots.frames(shot, tmp_path / "b", [2.0], overrides=edits)
    plain = shots.frames(shot, tmp_path / "plain", [2.0], overrides={})
    assert a and b and plain
    ia, ib, ip = (Image.open(p).convert("RGB") for p in (a[0], b[0], plain[0]))
    assert list(ia.getdata()) == list(ib.getdata()), "the same moment draws the same pixels twice"
    corner = (10, 10)
    assert ip.getpixel(corner) == (15, 18, 38), "the shot's own background"
    assert ia.getpixel(corner) == (255, 250, 240), "the knob changed the background"
    w, h = ia.size
    orb = ia.getpixel((int(1570 * w / 1920), int(560 * h / 1080)))
    assert orb[1] > orb[0] and orb[1] > orb[2], f"the accent knob made the orb green: {orb}"
    sub_row = [ia.getpixel((int(x * w / 1920), int(585 * h / 1080))) for x in range(170, 900, 20)]
    assert all(px == (255, 250, 240) for px in sub_row), "the hidden subtitle is gone"


# ---- C2: shots on the timeline -------------------------------------------------------------------------------------------------------------------


def _with_shot(ref, scene_index=1, shot_id="intro"):
    from vt.schema import ScenesFile

    d = ref.dir / "shots" / shot_id
    d.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "shot.json"):
        shutil.copy(SPIKE / name, d / name)
    plan = ref.scenes().model_dump()
    plan["scenes"][scene_index]["shot"] = shot_id
    ref.save_scenes(ScenesFile.model_validate(plan))
    return d


def test_a_scene_with_a_shot_shows_it_full_frame_behind_its_elements(ref, monkeypatch):
    import json

    from vt.compose import compose_project

    d = _with_shot(ref)
    fake = d / "render" / "abc.mp4"
    fake.parent.mkdir()
    fake.write_bytes(b"not really a video")
    monkeypatch.setattr(shots, "cached_render", lambda shot_dir_, **k: fake)
    out = compose_project(ref, "16:9").parent
    data = json.loads((out / "data.json").read_text(encoding="utf-8"))
    sid = ref.scenes().scenes[1].id
    sc = next(s for s in data["scenes"] if s["id"] == sid)
    assert sc["backdrop"]["media"] == "shot:intro" and sc["backdrop"]["motion"] == "none"
    m = data["media"]["shot:intro"]
    assert m["kind"] == "video" and m["loop"] is False and m["role"] == "shot" and "_abs" not in m
    assert (out / m["src"]).read_bytes() == b"not really a video", "the shot's video is copied next to the page"
    others = [s for s in data["scenes"] if s["id"] != sid]
    assert not any((s.get("backdrop") or {}).get("media", "").startswith("shot:") for s in others), "no other scene borrows the shot"


def test_a_scene_naming_a_missing_shot_says_which(ref):
    from vt.compose import compose_project
    from vt.schema import ScenesFile

    plan = ref.scenes().model_dump()
    plan["scenes"][0]["shot"] = "nowhere"
    ref.save_scenes(ScenesFile.model_validate(plan))
    with pytest.raises(shots.ShotError, match="nowhere"):
        compose_project(ref, "16:9")


def test_a_shot_id_cannot_leave_the_shots_folder():
    from pydantic import ValidationError

    from vt.schema import Scene

    with pytest.raises(ValidationError):
        Scene(id="s1", shot="../../secrets")
    with pytest.raises(shots.ShotError):
        shots.shot_dir(type("P", (), {"dir": Path(".")})(), "../x")


def test_the_render_is_reused_until_something_in_the_shot_changes(shot, monkeypatch):
    drawn = []

    def fake_render(d, out, **k):
        drawn.append(out.name)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")
        return out
    monkeypatch.setattr(shots, "render", fake_render)
    a = shots.cached_render(shot)
    assert shots.cached_render(shot) == a and len(drawn) == 1, "nothing changed: no second render"
    shots.save_overrides(shot, {"knobs": {"--bg": "#ffffff"}})
    b = shots.cached_render(shot)
    assert b != a and len(drawn) == 2 and not a.exists(), "an edit draws it again and the old render is removed"
    assert [s["id"] for s in shots.list_shots(type("P", (), {"dir": shot.parent.parent})())] == ["intro"]


# ---- C2: the shot endpoints the Studio and agents use -------------------------------------------------------------------------------------------


@pytest.fixture()
def client(ref):
    from fastapi.testclient import TestClient

    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def test_an_agent_writes_a_shot_and_the_editor_edits_it(client):
    html = (SPIKE / "index.html").read_text(encoding="utf-8")
    assert client.get("/api/projects/reference/shots").json() == {"shots": []}
    made = client.put("/api/projects/reference/shots/intro", json={"html": html, "shot": {"title": "Opening"}}).json()
    assert made["title"] == "Opening" and made["ids"] == ["orb", "title", "sub", "bar"] and made["overrides"] == {"knobs": {}, "elements": {}}
    r = client.put("/api/projects/reference/shots/intro/overrides", json={"overrides": {"elements": {"title": {"text": "Edited", "x": 12}}}})
    assert r.status_code == 200
    assert client.put("/api/projects/reference/shots/intro/overrides", json={"overrides": {"knobs": {"--x": "red;}"}}}).status_code == 422
    again = client.put("/api/projects/reference/shots/intro", json={"html": html.replace("Sleep is a skill", "Sleep matters")}).json()
    assert again["overrides"]["elements"]["title"]["text"] == "Edited", "new code keeps the person's edits"
    assert again["title"] == "Opening", "shot.json is kept when only the code changes"
    page = client.get("/api/projects/reference/shots/intro/page/index.html")
    assert page.status_code == 200 and "default-src 'self'" in page.headers["content-security-policy"] and "Edited" in page.text
    assert client.get("/api/projects/reference/shots/intro/page/runtime/gsap.min.js").status_code == 200
    assert [s["id"] for s in client.get("/api/projects/reference/shots").json()["shots"]] == ["intro"]


def test_bad_shots_and_paths_are_refused(client):
    assert client.put("/api/projects/reference/shots/intro", json={"html": "<div>no root</div>"}).status_code == 422
    assert not client.get("/api/projects/reference/shots").json()["shots"], "a refused shot leaves nothing behind"
    assert client.get("/api/projects/reference/shots/nope").status_code == 404
    assert client.put("/api/projects/reference/shots/..%2Fx", json={"html": "x"}).status_code in (404, 422)
    html = (SPIKE / "index.html").read_text(encoding="utf-8")
    client.put("/api/projects/reference/shots/intro", json={"html": html})
    for bad in ("../../meta.json", "runtime/../../../meta.json", "overrides.json", "preview/index.html"):
        assert client.get(f"/api/projects/reference/shots/intro/page/{bad}").status_code in (404, 422), bad


def test_no_scene_move_or_decoration_is_added_on_top_of_a_shot():
    from vt.compose import motion as MO

    data = {"scenes": [{"id": f"s{i}", "elements": [], "backdrop": {"media": "shot:a"} if i in (0, 3) else None} for i in range(9)]}
    MO.apply(data, "auto", seed="x")
    assert not data["scenes"][0].get("moves") and not data["scenes"][3].get("moves")
    assert data["scenes"][8].get("moves"), "other scenes still get theirs"


# ---- C3: the visual editor's page and its bridge ---------------------------------------------------------------------------------------------------


def test_the_editor_page_asks_the_network_for_nothing_and_shows_the_code_without_saved_edits(shot, tmp_path):
    (shot / "assets").mkdir()
    (shot / "assets" / "dot.png").write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"))
    html = (shot / "index.html").read_text(encoding="utf-8").replace('<div id="bar" data-vt-id="bar"></div>', '<img data-vt-id="pic" src="assets/dot.png"><div id="bar" data-vt-id="bar"></div>')
    (shot / "index.html").write_text(html, encoding="utf-8")
    shots.save_overrides(shot, {"elements": {"title": {"text": "Saved edit"}}})
    page = (shots.build(shot, tmp_path / "ed", editor=True) / "index.html").read_text(encoding="utf-8")
    assert "Saved edit" not in page and "vt-overrides" in page, "the editor sends the edits itself"
    assert 'src="runtime/' not in page and 'href="fonts/' not in page and 'src="assets/' not in page, "nothing is fetched"
    assert "data:image/png;base64," in page and "font/woff2;base64," in page and "shot-ready" in page
    assert "'Inter'" in page and "'Fraunces'" not in page, "only the fonts the shot names"
    rendered = (shots.build(shot, tmp_path / "r") / "index.html").read_text(encoding="utf-8")
    assert "Saved edit" in rendered and "shot-ready" not in rendered, "a render has the edits and never the bridge"


@pytest.mark.slow
@pytest.mark.browser
def test_the_bridge_picks_moves_and_edits_live_inside_a_sandboxed_frame(shot, tmp_path):
    import json

    from vt.render.hyperframes import _browser
    from vt.util import find_tool, run

    page = shots.build(shot, tmp_path / "ed", editor=True) / "index.html"
    msgs = [{"vt": "shot-seek", "t": 2.5},
            {"vt": "shot-pick", "x": 300, "y": 440, "wait": True},
            {"vt": "shot-overrides", "overrides": {"elements": {"title": {"x": 100, "y": 50, "text": "Moved"}}, "knobs": {"--title-size": "60px"}}},
            {"vt": "shot-rect", "id": "title", "wait": True},
            {"vt": "shot-overrides", "overrides": {}},
            {"vt": "shot-rect", "id": "title", "wait": True},
            {"vt": "shot-pick", "x": 5, "y": 5, "wait": True}]
    script = Path(shots.paths.RENDERER) / "scripts" / "shot-bridge-check.mjs"
    out = json.loads(run([find_tool("node"), str(script), _browser(), str(page), json.dumps(msgs)]).strip().splitlines()[-1])
    assert out["failed"] == [], out["failed"]
    ready = out["ready"]
    assert ready["ids"] == ["orb", "title", "sub", "bar"] and ready["texts"]["title"] == "Sleep is a skill" and ready["colours"]["title"] == "#f5f3ff" and (ready["width"], ready["height"]) == (1920, 1080)
    picked, moved, back, nothing = out["answers"]
    assert picked["id"] == "title"
    assert abs(moved["rect"][0] - (picked["rect"][0] + 100)) < 2 and abs(moved["rect"][1] - picked["rect"][1] - 50) < 25, (picked, moved)
    assert moved["rect"][3] < picked["rect"][3], "the title-size knob made it smaller"
    assert [round(v) for v in back["rect"]] == [round(v) for v in picked["rect"]], "clearing the edits restores the shot as written"
    assert nothing["id"] is None


# ---- C5: the director writes shots inside its Video Script ----------------------------------------------------------------------------------------


def _shot_html(width=1080, height=1920, text="Hello"):
    return (SPIKE / "index.html").read_text(encoding="utf-8").replace("1920px", f"{width}px", 1).replace("1080px", f"{height}px", 1) \
        .replace('data-width="1920" data-height="1080"', f'data-width="{width}" data-height="{height}"').replace("Sleep is a skill", text)


def _script_with_shot(ref, html, shot_id="opener", scene_shot="opener"):
    ids = [b.id for b in ref.beats().beats]
    return {"version": "1.0", "kind": "explainer",
            "scenes": [{"id": "s1", "beats": ids[:1], "shot": scene_shot}, {"id": "s2", "beats": ids[1:],
                        "overlays": [{"type": "title", "text": "After", "at_word": ref.beats().beats[1].word_ids[0]}]}],
            "shots": [{"id": shot_id, "title": "The opener", "html": html, "knobs": [{"name": "--accent", "label": "Accent"}]}]}


def test_a_script_with_a_shot_is_applied_and_the_shot_written(ref):
    from vt.script import service

    res = service.apply_script(ref, _script_with_shot(ref, _shot_html()), planner="claude", strict=True, compose=False)
    assert res["ok"], res.get("errors")
    d = ref.dir / "shots" / "opener"
    assert "Hello" in (d / "index.html").read_text(encoding="utf-8")
    meta = shots.read_json(d / "shot.json", {})
    assert meta["title"] == "The opener" and meta["made_by"] == "claude" and meta["knobs"][0]["name"] == "--accent"
    assert ref.scenes().scenes[0].shot == "opener" and ref.scenes().scenes[1].shot is None
    shots.save_overrides(d, {"elements": {"title": {"text": "Mine"}}})
    again = service.apply_script(ref, _script_with_shot(ref, _shot_html(text="Rewritten")), planner="claude", strict=True, compose=False)
    assert again["ok"] and "Rewritten" in (d / "index.html").read_text(encoding="utf-8")
    assert shots.read_json(d / "overrides.json", {})["elements"]["title"]["text"] == "Mine", "the person's edits outlive the director's rewrite"
    from vt.script.compile import script_from_scenes

    assert script_from_scenes(ref.scenes()).scenes[0].shot == "opener", "the plan read back as a script keeps the shot"


@pytest.mark.parametrize("spoil,expect", [
    (lambda s: s["scenes"][0].update(shot="missing"), "not in `shots`"),
    (lambda s: s["shots"][0].update(html=_shot_html(1920, 1080)), "this video is 1080x1920"),
    (lambda s: s["shots"][0].update(html=_shot_html().replace("runtime/gsap.min.js", "https://cdn.example/gsap.js")), "network"),
    (lambda s: s["shots"][0].update(html=_shot_html().replace("ease:", "x: Math.random(), ease:", 1)), "paused timeline only"),
    (lambda s: s["shots"][0].update(html=_shot_html().replace("data-composition-id", "data-x")), "data-composition-id"),
    (lambda s: s["shots"].append(dict(s["shots"][0])), "share an id"),
])
def test_a_bad_shot_comes_back_as_an_error_the_director_can_fix(ref, spoil, expect):
    from vt.script import service

    s = _script_with_shot(ref, _shot_html())
    spoil(s)
    res = service.apply_script(ref, s, planner="claude", strict=True, compose=False)
    assert not res["ok"] and any(expect in e for e in res["errors"]), res["errors"]
    assert not (ref.dir / "shots" / "opener").exists(), "nothing is written from a refused script"


def test_a_shot_gets_the_videos_theme_as_css_variables_and_a_theme_change_draws_it_again(ref, shot, tmp_path, monkeypatch):
    vars_ = shots.theme_vars(ref)
    assert vars_["--vt-accent"].startswith("#") and "'" in vars_["--vt-font-headline"]
    html = (shots.build(shot, tmp_path / "b", theme=vars_) / "index.html").read_text(encoding="utf-8")
    assert f'--vt-accent:{vars_["--vt-accent"]};' in html and html.index('id="vt-theme"') < html.index("</head>")
    assert "--vt-x" not in (shots.build(shot, tmp_path / "c", theme={"--vt-x": "red;}body{x"}) / "index.html").read_text(encoding="utf-8"), "an unsafe value is dropped"
    assert shots.fingerprint(shot, 30, vars_) != shots.fingerprint(shot, 30, {**vars_, "--vt-accent": "#000000"})
