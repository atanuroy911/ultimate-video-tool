"""HyperFrames' pre-flight answer is turned into one flat list (vt/render/hyperframes.py::summarize_check)."""
from vt.render.hyperframes import check, summarize_check

RAW = {"ok": True, "lint": {"findings": [{"code": "negative_z_index", "severity": "warning", "message": "z-index -1", "selector": ".pill", "fixHint": "isolate"}]},
       "runtime": {"findings": [{"code": "js_error", "severity": "error", "message": "x is not defined", "time": 2.0}]},
       "layout": {"findings": [{"code": "panel", "severity": "info", "message": "off canvas"}]}, "motion": {"findings": []}, "contrast": {"findings": []}}


def test_flat_list_keeps_errors_and_warnings_and_drops_info():
    r = summarize_check(RAW)
    assert r["errors"] == 1 and r["warnings"] == 1 and r["ok"] is False
    assert {i["area"] for i in r["issues"]} == {"Composition rules", "Errors while playing"}
    assert r["issues"][0]["fix"] == "isolate"


def test_a_folder_that_cannot_be_checked_never_raises(tmp_path):
    r = check(tmp_path, timeout=30)
    assert r["ok"] is True and (r.get("unavailable") or r["issues"] == [] or r["errors"] == 0)
