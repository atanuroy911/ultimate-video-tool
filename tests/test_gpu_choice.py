"""Which graphics cards Video Tool may use (server/vt/gpuassign.py, PLAN-PERFECT K1): the person's list, the safe default before they answer, the launcher's fence,
a card that was removed, and no card at all. Fake cards stand in for nvidia-smi, so this runs on any machine."""
import pytest

from vt import gpuassign, paths, sysstats

V100 = {"index": 0, "name": "Tesla V100-PCIE-16GB", "uuid": "GPU-v100", "free_gb": 5.0, "total_gb": 16.0, "load": 96.0}
RTX = {"index": 1, "name": "NVIDIA GeForce RTX 3060", "uuid": "GPU-3060", "free_gb": 9.0, "total_gb": 12.0, "load": 8.0}
BIG = {"index": 2, "name": "NVIDIA GeForce RTX 3090", "uuid": "GPU-3090", "free_gb": 20.0, "total_gb": 24.0, "load": 0.0}
TRAINING = {"label": "python3", "gb": 9.7, "ours": False}
OURS = {"label": "Video renderer", "gb": 1.0, "ours": True}


class Box:
    def __init__(self):
        self.cards = [dict(V100), dict(RTX)]
        self.programs: dict[str, list] = {}


@pytest.fixture()
def box(tmp_path, monkeypatch):
    b = Box()
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    monkeypatch.setattr(gpuassign, "_cards", lambda: [dict(c) for c in b.cards])
    monkeypatch.setattr(gpuassign, "_PIN", None)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setattr(sysstats, "_gpus", lambda: [{"index": c["index"], "name": c["name"], "uuid": c["uuid"], "programs": list(b.programs.get(c["uuid"], []))} for c in b.cards])
    return b


def uuids(cards):
    return [c["uuid"] for c in cards]


# ----------------------------------------------------------------------------------------------------------------------------------- nobody has been asked yet
def test_one_card_has_nothing_to_ask(box):
    box.cards = [dict(RTX)]
    assert not gpuassign.needs_choice()
    assert uuids(gpuassign.allowed()) == ["GPU-3060"]


def test_two_cards_and_no_answer_asks_and_uses_only_the_card_nobody_else_works_on(box):
    box.programs = {"GPU-v100": [TRAINING]}
    assert gpuassign.needs_choice()
    assert uuids(gpuassign.allowed()) == ["GPU-3060"]
    card, why = gpuassign.resolve("render")
    assert card["uuid"] == "GPU-3060"


def test_the_training_card_is_never_the_default_even_when_it_has_the_most_room(box):
    box.cards = [{**V100, "free_gb": 22.0, "total_gb": 32.0}, dict(RTX)]
    box.programs = {"GPU-v100": [TRAINING]}
    assert uuids(gpuassign.allowed()) == ["GPU-3060"]


def test_every_card_busy_uses_the_freest_one_only(box):
    box.programs = {"GPU-v100": [TRAINING], "GPU-3060": [{"label": "ComfyUI", "gb": 2.0, "ours": False}]}
    assert uuids(gpuassign.allowed()) == ["GPU-3060"]                                 # 9 GB free against 5


def test_video_tools_own_programs_do_not_make_a_card_busy(box):
    box.programs = {"GPU-v100": [OURS], "GPU-3060": [TRAINING]}
    assert uuids(gpuassign.allowed()) == ["GPU-v100"]


def test_the_default_is_never_all_the_cards(box):
    box.cards = [dict(V100), dict(RTX), dict(BIG)]
    for programs in ({}, {"GPU-v100": [TRAINING]}, {"GPU-v100": [TRAINING], "GPU-3060": [TRAINING], "GPU-3090": [TRAINING]}):
        box.programs = programs
        assert len(gpuassign.allowed()) == 1, programs


def test_no_answer_and_no_card_is_the_processor(box):
    box.cards = []
    assert gpuassign.allowed() == [] and not gpuassign.needs_choice()
    card, why = gpuassign.resolve("render")
    assert card is None and "no NVIDIA" in why


# ----------------------------------------------------------------------------------------------------------------------------------- the person's answer
def test_the_answer_limits_every_job_and_every_fallback(box):
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert not gpuassign.needs_choice()
    assert uuids(gpuassign.allowed()) == ["GPU-3060"]
    assert gpuassign.resolve("render")[0]["uuid"] == "GPU-3060"
    assert gpuassign.resolve("speech")[0]["uuid"] == "GPU-3060"
    with pytest.raises(ValueError, match="not a card"):
        gpuassign.save({"primary": "0"})                                            # the V100 is not allowed
    with pytest.raises(ValueError, match="not a card"):
        gpuassign.save({"render": "Tesla V100-PCIE-16GB"})


def test_cards_can_be_named_three_ways_or_all(box):
    gpuassign.save({"allowed": ["Tesla V100-PCIE-16GB"]})
    assert uuids(gpuassign.allowed()) == ["GPU-v100"]
    gpuassign.save({"allowed": "0, 1"})
    assert uuids(gpuassign.allowed()) == ["GPU-v100", "GPU-3060"]
    gpuassign.save({"allowed": ["GPU-3060"]})
    gpuassign.save({"allowed": "all"})
    assert uuids(gpuassign.allowed()) == ["GPU-v100", "GPU-3060"]
    assert gpuassign.saved_allowed() == ["GPU-v100", "GPU-3060"]


def test_a_card_that_is_not_here_cannot_be_allowed(box):
    with pytest.raises(ValueError, match="not a card"):
        gpuassign.save({"allowed": ["GPU-nothing"]})
    assert gpuassign.saved_allowed() is None                                        # nothing was written


def test_an_empty_list_is_an_answer_and_means_the_processor(box):
    gpuassign.save({"allowed": []})
    assert gpuassign.saved_allowed() == []
    assert gpuassign.allowed() == []
    assert not gpuassign.needs_choice()                                             # they answered: no card
    card, why = gpuassign.resolve("render")
    assert card is None and "no NVIDIA" in why
    assert gpuassign.cuda_index("speech") == 0
    d = gpuassign.describe()
    assert [c["allowed"] for c in d["cards"]] == [False, False] and d["jobs"]["render"]["gpu"] is None


def test_the_order_of_the_cards_is_the_drivers_not_the_order_they_were_given(box):
    gpuassign.save({"allowed": ["GPU-3060", "GPU-v100"]})
    assert uuids(gpuassign.allowed()) == ["GPU-v100", "GPU-3060"]                   # CUDA numbers them this way once the server fences itself to them


def test_a_choice_made_in_the_same_save_is_checked_against_the_new_list(box):
    gpuassign.save({"allowed": ["GPU-3060"], "primary": "GPU-3060"})
    assert gpuassign.config()["primary"] == "GPU-3060"
    with pytest.raises(ValueError, match="not a card"):
        gpuassign.save({"allowed": ["GPU-3060"], "primary": "GPU-v100"})
    assert gpuassign.config()["primary"] == "GPU-3060"                              # the refused save changed nothing


def test_taking_a_card_away_sends_the_choices_that_pointed_at_it_back_to_the_default(box):
    gpuassign.save({"allowed": "all", "primary": "GPU-v100", "render": "GPU-v100", "speech": "GPU-3060"})
    assert gpuassign.config() == {"primary": "GPU-v100", "render": "GPU-v100", "speech": "GPU-3060", "ai": "primary", "pictures": "primary"}
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert gpuassign.config() == {"primary": "auto", "render": "primary", "speech": "GPU-3060", "ai": "primary", "pictures": "primary"}
    assert gpuassign.resolve("render")[0]["uuid"] == "GPU-3060"


def test_other_changes_keep_the_answer(box):
    gpuassign.save({"allowed": ["GPU-3060"]})
    gpuassign.save({"primary": "auto"})
    gpuassign.save({"render": "primary"})
    assert gpuassign.saved_allowed() == ["GPU-3060"]


def test_unknown_things_are_refused_with_a_sentence(box):
    with pytest.raises(ValueError, match="not something"):
        gpuassign.save({"voice": "0"})
    with pytest.raises(ValueError, match="primary card"):
        gpuassign.save({"primary": "primary"})


# ----------------------------------------------------------------------------------------------------------------------------------- a card that went away
def test_a_removed_card_drops_out_and_the_rest_carry_on(box):
    gpuassign.save({"allowed": "all", "primary": "GPU-v100"})
    box.cards = [dict(RTX)]
    assert uuids(gpuassign.allowed()) == ["GPU-3060"]
    card, why = gpuassign.resolve("render")
    assert card["uuid"] == "GPU-3060" and "not available" in why
    assert not gpuassign.needs_choice()                                             # one card left: nothing to choose


def test_when_every_card_the_person_chose_is_gone_the_question_comes_back(box):
    gpuassign.save({"allowed": ["GPU-v100"]})
    box.cards = [dict(RTX), dict(BIG)]
    assert gpuassign.needs_choice()
    assert len(gpuassign.allowed()) == 1                                            # the safe default, not everything
    box.cards = [dict(V100), dict(RTX)]                                             # it came back: the old answer holds again
    assert not gpuassign.needs_choice() and uuids(gpuassign.allowed()) == ["GPU-v100"]


# ----------------------------------------------------------------------------------------------------------------------------------- the launcher's fence
def test_the_launcher_fence_comes_first(box, monkeypatch):
    monkeypatch.setattr(gpuassign, "_PIN", "GPU-3060")
    assert uuids(gpuassign.allowed()) == ["GPU-3060"] and not gpuassign.needs_choice()
    with pytest.raises(ValueError, match="not a card"):
        gpuassign.save({"allowed": ["GPU-v100"]})                                   # fenced off by whoever started the server
    gpuassign.save({"allowed": "all"})
    assert uuids(gpuassign.allowed()) == ["GPU-3060"]                               # "all" means all that the fence lets through


def test_the_fence_is_what_the_launcher_said_not_what_the_server_sets_later(box, monkeypatch):
    gpuassign.save({"allowed": "all"})
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-v100")                          # the server's own use of the variable (K2) must not shrink the fence
    assert uuids(gpuassign.allowed()) == ["GPU-v100", "GPU-3060"]


# ----------------------------------------------------------------------------------------------------------------------------------- counting cards the way CUDA does
def test_a_cards_number_is_counted_among_the_cards_the_process_can_see(box, monkeypatch):
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert gpuassign.cuda_index("speech") == 1                                      # the process still sees both cards: the 3060 is device 1
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-3060")
    assert gpuassign.cuda_index("speech") == 0                                      # fenced to the 3060 alone: device 0
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-3060,GPU-v100")
    assert gpuassign.cuda_index("speech") == 0                                      # CUDA numbers them in the order the variable lists them
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "-1")
    assert gpuassign.cuda_index("speech") == 0                                      # nothing visible: nothing to count


# ----------------------------------------------------------------------------------------------------------------------------------- what the Server page shows
def test_describe_says_what_each_card_is_doing_and_whether_to_ask(box):
    box.programs = {"GPU-v100": [TRAINING, OURS]}
    d = gpuassign.describe()
    assert d["needs_choice"] is True and d["allowed_saved"] is None
    v100, rtx = d["cards"]
    assert v100["using"] == [{"label": "python3", "gb": 9.7, "ours": False}, {"label": "Video renderer", "gb": 1.0, "ours": True}]
    assert (v100["allowed"], rtx["allowed"]) == (False, True) and rtx["using"] == []
    gpuassign.save({"allowed": "all"})
    d = gpuassign.describe()
    assert d["needs_choice"] is False and d["allowed_saved"] == ["GPU-v100", "GPU-3060"] and [c["allowed"] for c in d["cards"]] == [True, True]


# ----------------------------------------------------------------------------------------------------------------------------------- the ways in: the Server page's route, `vt gpu`, the MCP tool
def test_the_server_page_can_answer_and_gets_the_new_picture_back(box):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from vt.server import system_routes

    app = FastAPI()
    app.include_router(system_routes.router)
    c = TestClient(app)
    assert c.get("/api/system/gpus").json()["needs_choice"] is True
    r = c.put("/api/system/gpu", json={"allowed": ["GPU-3060"]})
    assert r.status_code == 200 and r.json()["allowed_saved"] == ["GPU-3060"] and r.json()["needs_choice"] is False
    r = c.put("/api/system/gpu", json={"primary": "GPU-v100"})
    assert r.status_code == 422 and "not a card" in r.json()["detail"]
    assert c.put("/api/system/gpu", json={"allowed": []}).json()["allowed_saved"] == []                  # an empty list is an answer, not "nothing sent"


def test_vt_gpu_allow_and_the_mcp_tool_make_the_same_choice(box):
    from typer.testing import CliRunner

    from vt.cli import app
    from vt.mcp import server as mcp_server

    runner = CliRunner()
    shown = runner.invoke(app, ["gpu"])
    assert shown.exit_code == 0 and "Nobody has chosen" in shown.output
    done = runner.invoke(app, ["gpu", "allow", "1"])
    assert done.exit_code == 0 and gpuassign.saved_allowed() == ["GPU-3060"] and "RTX 3060" in done.output
    bad = runner.invoke(app, ["gpu", "allow", "9"])
    assert bad.exit_code != 0 and gpuassign.saved_allowed() == ["GPU-3060"]
    assert runner.invoke(app, ["gpu", "allow", "none"]).exit_code == 0 and gpuassign.saved_allowed() == []
    assert runner.invoke(app, ["gpu", "allow", "0", "1"]).exit_code == 0 and gpuassign.saved_allowed() == ["GPU-v100", "GPU-3060"]
    tool = getattr(mcp_server.gpu_assignment, "fn", mcp_server.gpu_assignment)
    assert tool(allowed="GPU-3060")["allowed_saved"] == ["GPU-3060"]
    assert tool(allowed="none")["allowed_saved"] == []
    assert tool(allowed="all", job="render", gpu="GPU-v100")["jobs"]["render"]["name"] == "Tesla V100-PCIE-16GB"


# ----------------------------------------------------------------------------------------------------------------------------------- servers set up before the question existed
def test_a_card_the_person_already_picked_counts_as_their_answer_until_they_say_otherwise(box):
    from vt.util import write_json

    box.programs = {"GPU-3060": [{"label": "ComfyUI", "gb": 3.0, "ours": False}]}           # the picked card is busy, the other one idle: the idle one is still not used
    write_json(paths.SETTINGS, {"gpu": {"primary": "GPU-3060", "render": "primary", "speech": "primary"}})
    assert uuids(gpuassign.allowed()) == ["GPU-3060"]
    assert gpuassign.resolve("render")[0]["uuid"] == "GPU-3060" and gpuassign.resolve("speech")[0]["uuid"] == "GPU-3060"
    assert gpuassign.needs_choice()                                                         # the question is still to be answered, but nothing moves meanwhile
    write_json(paths.SETTINGS, {"gpu": {"primary": "GPU-3060", "render": "GPU-v100", "speech": "primary"}})
    assert uuids(gpuassign.allowed()) == ["GPU-v100", "GPU-3060"]                           # a card picked for one job is a card they use
    write_json(paths.SETTINGS, {"gpu": {"primary": "auto", "render": "primary", "speech": "primary"}})
    assert len(gpuassign.allowed()) == 1                                                    # nothing picked: the safe default
