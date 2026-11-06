"""Which graphics card each of Video Tool's own jobs uses (server/vt/gpuassign.py): automatic choice, per-job choice, the launcher's fence, a vanished card."""
import pytest

from vt import gpuassign, paths

V100 = {"index": 0, "name": "Tesla V100-PCIE-16GB", "uuid": "GPU-v100", "free_gb": 5.0, "total_gb": 16.0, "load": 96.0}
RTX = {"index": 1, "name": "NVIDIA GeForce RTX 3060", "uuid": "GPU-3060", "free_gb": 9.0, "total_gb": 12.0, "load": 8.0}


@pytest.fixture()
def box(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    monkeypatch.setattr(gpuassign, "_cards", lambda: [dict(V100), dict(RTX)])
    monkeypatch.setattr(gpuassign, "_PIN", None)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    gpuassign.save({"allowed": "all"})                                     # the person has answered "which cards may Video Tool use": both (that question has its own tests, test_gpu_choice.py)
    return tmp_path


def test_automatic_picks_the_freest_card(box):
    card, why = gpuassign.resolve("render")
    assert card["uuid"] == "GPU-3060" and "freest" in why


def test_the_primary_card_is_what_jobs_follow(box):
    gpuassign.save({"primary": "0"})
    assert gpuassign.resolve("render")[0]["uuid"] == "GPU-v100"
    assert gpuassign.resolve("speech")[0]["uuid"] == "GPU-v100"


def test_a_job_can_differ_from_the_primary_and_can_be_named_three_ways(box):
    gpuassign.save({"primary": "GPU-3060"})
    gpuassign.save({"render": "Tesla V100-PCIE-16GB"})
    assert gpuassign.resolve("render")[0]["uuid"] == "GPU-v100"
    assert gpuassign.resolve("speech")[0]["uuid"] == "GPU-3060"
    gpuassign.save({"render": "primary"})
    assert gpuassign.resolve("render")[0]["uuid"] == "GPU-3060"


def test_bad_choices_are_refused_with_a_sentence(box):
    with pytest.raises(ValueError, match="not a card"):
        gpuassign.save({"render": "7"})
    with pytest.raises(ValueError, match="cannot be assigned|not something"):
        gpuassign.save({"voice": "0"})
    with pytest.raises(ValueError, match="primary card"):
        gpuassign.save({"primary": "primary"})


def test_the_launcher_fence_limits_the_choice_and_renumbers(box, monkeypatch):
    monkeypatch.setattr(gpuassign, "_PIN", "GPU-3060")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-3060")
    assert [c["uuid"] for c in gpuassign.allowed()] == ["GPU-3060"]
    with pytest.raises(ValueError):
        gpuassign.save({"primary": "0"})                                   # the V100 is fenced off
    assert gpuassign.cuda_index("speech") == 0                              # the 3060 is the only card this process sees: its device 0
    monkeypatch.setattr(gpuassign, "_PIN", "0,1")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,1")
    gpuassign.save({"primary": "GPU-3060"})
    assert gpuassign.cuda_index("speech") == 1                              # both visible: the 3060 is device 1


def test_a_card_that_went_away_falls_back_and_says_so(box, monkeypatch):
    gpuassign.save({"primary": "GPU-v100"})
    monkeypatch.setattr(gpuassign, "_cards", lambda: [dict(RTX)])
    card, why = gpuassign.resolve("render")
    assert card["uuid"] == "GPU-3060" and "not available" in why


def test_no_nvidia_card_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    monkeypatch.setattr(gpuassign, "_cards", lambda: [])
    card, why = gpuassign.resolve("render")
    assert card is None and "no NVIDIA" in why
    assert gpuassign.cuda_index("speech") == 0


def test_the_onnx_voice_paths_follow_the_chosen_card(box):
    from vt import gpu

    gpuassign.save({"primary": "GPU-3060"})
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        pytest.skip("onnxruntime is not installed")
    prov = gpu.onnx_providers()
    cuda = [p for p in prov if isinstance(p, tuple)]
    if cuda:
        assert cuda[0][1]["device_id"] == 1


def test_a_screen_recording_starts_protected_unless_the_person_chose():
    from vt.source_inspect import default_recording_edit as d

    video = {"mode": "video", "has_picture": True}
    assert d(video) == "subtitles"                                          # no face on camera: its picture and pauses are kept, captions added
    assert d(video, "screen") == "screen" and d(video, "subtitles") == "subtitles"      # an explicit choice always stands
    assert d({"mode": "talking_head", "has_picture": True}) == "auto"       # a person talking to the camera: the normal editing
    assert d({"mode": "audio", "has_picture": False}) == "auto"
