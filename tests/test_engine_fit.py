"""The VRAM fit (vt/engines/fit.py), the instance scan's parsing (discover.py) and the picture set written into the graph."""
from vt.engines import discover, fit


def card(vram, cc=8.6, ram=32):
    return fit.Card("x", vram, vram, cc, ram, ram)


def test_each_card_gets_the_set_that_draws_best_and_fits():
    assert fit.choose(card(12)).recipe == "klein-4b"                    # RTX 3060: measured 9 s a picture (2026-11-01)
    assert fit.choose(card(16.9, 7.0)).recipe == "klein-4b"             # V100
    assert fit.choose(card(8, 8.6, 16)).recipe == "klein-4b-fp8"
    big = fit.choose(card(48, 8.6, 128))
    assert (big.recipe, big.mode) == ("klein-4b", "resident")
    for v in (8, 12, 16.9, 24, 48):
        f = fit.choose(card(v, 8.9, 128))
        assert f.card_gb <= v * (1 - fit.MARGIN)


def test_small_and_missing_cards():
    assert fit.choose(card(4)).recipe is None
    assert "no graphics card" in fit.choose(fit.Card()).why
    assert fit.check(fit.BY_ID["zimage-nvfp4"], card(8, 8.6))["why"].startswith("needs an RTX 50")


def test_every_set_names_a_graph_whose_loaders_it_fills():
    from vt.comfy import load_workflow, picture_workflow

    for r in fit.PICTURES:
        w = picture_workflow(r.id)
        assert w.id == r.workflow and w.graph["1"]["inputs"]["unet_name"] == r.unet.rsplit("/", 1)[-1]
        assert all(f in fit.FILES and fit.FILES[f].get("url") for f in r.files())
        assert load_workflow(r.workflow).manifest["prompt"]


def test_busy_card_warns():
    c = card(12)
    c.vram_free_gb = 3
    assert any("free right now" in w for w in fit.choose(c).warnings)


def test_language_model_by_card():
    assert fit.language_model(12)["model"] == "gemma3:12b"
    assert fit.language_model(6)["model"] == "gemma3:4b"
    assert fit.language_model(0, 16)["where"] == "processor"


def test_card_from_comfy_stats():
    stats = {"system": {"ram_total": 32e9, "ram_free": 20e9}, "devices": [{"name": "cuda:0 NVIDIA GeForce RTX 3060 : cudaMallocAsync", "type": "cuda", "vram_total": 12.6e9, "vram_free": 12e9}]}
    c = fit.card_from_stats(stats)
    assert (c.name, c.vram_gb, c.compute, c.ram_gb) == ("NVIDIA GeForce RTX 3060", 12.6, 8.6, 32.0)
    assert fit.card_from_stats({"system": {}, "devices": [{"name": "cpu", "type": "cpu"}]}).vram_gb == 0


def test_tunnel_config_marks_published_ports(tmp_path, monkeypatch):
    d = tmp_path / ".cloudflared"
    d.mkdir()
    (d / "config.yml").write_text("ingress:\n  - hostname: comfy.example.com\n    service: http://127.0.0.1:8188\n  - hostname: x.example.com\n    service: https://localhost:10000\n  - service: http_status:404\n")
    monkeypatch.setattr(discover, "tunnel_dirs", lambda: [d])                          # only this folder: /etc/cloudflared on a real server holds the owner's own tunnels
    t = discover.tunnels()
    assert t[8188] == "comfy.example.com" and t[10000] == "x.example.com"


def test_scan_reads_host_and_port(monkeypatch):
    seen = {}
    monkeypatch.setattr(discover, "open_ports", lambda host, ports, timeout=0.3: seen.update(host=host, ports=ports) or [])
    out = discover.scan("http://192.168.1.20:8443/")
    assert seen["host"] == "192.168.1.20" and 8443 in seen["ports"] and out["instances"] == []


def test_recipe_rewrites_only_the_loaders():
    from vt.comfy import load_workflow, picture_workflow

    base = load_workflow("zimage_t2i")
    w = picture_workflow("zimage-fp8")
    assert w.id == "zimage_t2i"
    assert w.graph["1"]["inputs"]["weight_dtype"] == "fp8_e4m3fn"
    assert w.graph["2"]["inputs"]["clip_name"] == "qwen_3_4b_fp8_mixed.safetensors"
    assert {k: v for k, v in w.graph.items() if k not in ("1", "2", "3")} == {k: v for k, v in base.graph.items() if k not in ("1", "2", "3")}


def test_shots_must_say_where_and_how_big():
    from vt import craft

    probs = {p["shot"]: p["says"] for p in craft.place_problems([
        ("s10", "Mira polishes the big round glass of the lighthouse lamp with a cloth, warm amber reflection on her face"),
        ("a", "Mira stands next to the lighthouse, smiling"),
        ("b", "Mira stands on the beach, the lighthouse far behind her"),
        ("c", "Inside the lantern room, Mira polishes the huge glass lens, taller than she is"),
        ("d", "On one small fishing boat in the storm, her grandfather holds the tiller"),
        ("e", "her grandfather points from the lighthouse gallery to small fishing boats on the evening sea")])}
    assert "where" in probs["s10"] and "how big" in probs["a"]
    assert not {"b", "c", "d", "e"} & set(probs)


def test_place_goes_into_every_prompt():
    from vt.reel.style import prompt_for

    p = prompt_for("Mira polishes the lens", "cartoon", "a girl", "lantern room: the glass room at the top, a lens taller than a child")
    assert p.index("Mira polishes") < p.index("Setting: lantern room") < p.index("recurring figure")


def test_plan_places_edit():
    from vt.direction import plan_doc as PD

    plan = PD.PlanDoc(moments=[PD.Moment(id="s1", start=0, end=2, sentence_ids=["b1"], text="x", draw="x", media="m1", status="ready")])
    PD.apply_edit(plan, {"op": "set_place", "name": "lantern room", "text": "the glass room at the top"})
    PD.apply_edit(plan, {"op": "set_moment_place", "moment": "s1", "place": "lantern room"})
    assert plan.moments[0].place == "lantern room" and plan.moments[0].media == ""
    import pytest
    with pytest.raises(PD.PlanError):
        PD.apply_edit(plan, {"op": "set_moment_place", "moment": "s1", "place": "nowhere"})


def test_script_rules_measure_title_ease_and_questions():
    from pathlib import Path

    from vt import craft

    title = "Why Do Billionaires Pay Less Tax Than You?"
    easy = (Path(__file__).resolve().parents[1] / "samples/scripts/billionaire-tax-easy.txt").read_text(encoding="utf-8")
    assert craft.script_problems(easy, title, 95) == []
    hard = ("Imagine two men. In some years, a billionaire can legally pay less federal income tax than someone earning a normal salary, "
            "because unrealized appreciation of concentrated equity positions generally isn't subject to federal income taxation until realization.")
    rules = {x["rule"] for x in craft.script_problems(hard, title, 60)}
    assert {"script.title_first", "script.easy", "script.questions"} <= rules
