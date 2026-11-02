"""Exercise editing APIs on an explicitly supplied disposable project copy."""
import argparse
import json
from copy import deepcopy
from urllib.request import Request, urlopen


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--base", default="http://127.0.0.1:8878")
    args.add_argument("--project", required=True)
    opt = args.parse_args()
    if not opt.project.endswith("-copy"):
        raise SystemExit("Use a disposable project whose ID ends in -copy")
    root = f"{opt.base}/api/projects/{opt.project}/audio"

    def call(path="", body=None):
        req = Request(root + path, data=json.dumps(body).encode() if body is not None else None,
                      headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=120) as response:
            return json.load(response)

    def close(a, b):
        assert abs(a - b) < 0.002, (a, b)

    before = call()
    split = call("/split", {"t": 2.137})
    assert any(abs(s["o"] - 2.137) < 0.002 for s in split["splits"])
    close(split["duration"], before["duration"])
    cut = call("/cut", {"start": 2.137, "end": 2.637})
    close(cut["duration"], before["duration"] - 0.5)
    assert any(abs(c["o"] - 2.137) < 0.002 and abs(c["len"] - 0.5) < 0.002 for c in cut["cuts"])
    close(call("/undo", {})["duration"], before["duration"])
    close(call("/redo", {})["duration"], before["duration"] - 0.5)
    close(call("/undo", {})["duration"], before["duration"])
    muted = call("/mute", {"start": 1, "end": 1.5, "on": True})
    assert any(abs(m["o0"] - 1) < 0.002 and abs(m["o1"] - 1.5) < 0.002 for m in muted["mutes"])
    gain = call("/gain", {"start": 1, "end": 1.5, "db": -6})
    assert any(g["db"] == -6 and abs(g["o0"] - 1) < 0.002 for g in gain["gains"])
    call("/undo", {})  # gain
    call("/undo", {})  # mute
    restored = call("/undo", {})  # split
    close(restored["duration"], before["duration"])
    assert restored["splits"] == before["splits"]
    print("PASS: exact split 2.137s; exact 0.500s removal; undo/redo; mute; gain; restored baseline")

    def request(path, body=None, method=None):
        req = Request(opt.base + path, data=json.dumps(body).encode() if body is not None else None,
                      headers={"Content-Type": "application/json"}, method=method)
        with urlopen(req, timeout=120) as response:
            return json.load(response)

    path = f"/api/projects/{opt.project}/layers"
    baseline = request(path)["doc"]
    working = deepcopy(baseline)
    working["tracks"].insert(0, {"id": "qa-precision", "name": "QA precision", "kind": "visual"})
    working["clips"].append({"id": "qa-clip", "track": "qa-precision", "type": "text", "text": "WALK",
                              "start": 1.137, "dur": 3.5, "fade_in": 0, "fade_out": 0})
    try:
        working = request(path, {"doc": working}, "PUT")["doc"]
        clip = next(c for c in working["clips"] if c["id"] == "qa-clip")
        clip.update(text="RUN", start=2.137, dur=1.5, x=0.35, opacity=0.8)
        saved = request(path, {"doc": working}, "PUT")["doc"]
        for shape in ("9x16", "1x1", "16x9"):
            data = request(f"/media/{opt.project}/composition/{shape}/data.json")
            rendered = next(c for c in data["layers"] if c["id"] == "qa-clip")
            assert rendered["text"] == "RUN"
            close(rendered["start"], 2.137)
            close(rendered["end"], 3.637)
            close(rendered["x"], 0.35)
            close(rendered["opacity"], 0.8)
        undone = request(path + "/undo", {})["doc"]
        assert next(c for c in undone["clips"] if c["id"] == "qa-clip")["text"] == "WALK"
        assert request(path + "/redo", {})["doc"] == saved
        print("PASS: layer text, trim, position and opacity reach all three preview formats; undo/redo")
    finally:
        request(path, {"doc": baseline}, "PUT")


if __name__ == "__main__":
    main()
