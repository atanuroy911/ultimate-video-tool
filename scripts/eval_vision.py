"""Which local vision model, with which prompt, spots layout problems in our frames? Scores models x prompts against frames whose
problems are known (labelled by a person). Usage: python scripts/eval_vision.py <frames dir> <labels.json> [models,...]
labels.json: {"frame-00.png": ["cut_off"], "frame-03.png": ["overlap"], "frame-02.png": []}."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from vt.ai import vision
from vt.ai.providers import OllamaProvider, complete_json

QUESTIONS = {
    "cut_off": "Look at the left, right and top edges of the image. Is any object, drawing, piece of furniture or text sliced by the image edge so that part of it is missing?",
    "overlap": "Is any text (a title, a label or a speech bubble) partly covered by, or drawn on top of, another text or shape so that letters are hidden?",
    "unreadable": "Is any text too small, too faint or too low in contrast against what is behind it to read easily on a phone?",
    "empty": "Is most of the image empty, with nothing meaningful to look at?",
}
YESNO = {"type": "object", "properties": {"answer": {"type": "string", "enum": ["yes", "no"]}, "where": {"type": "string", "maxLength": 80}}, "required": ["answer"]}


def focused(png: Path, provider) -> list[str]:
    """One yes/no question per problem: small vision models answer a single concrete question far better than a checklist."""
    out = []
    img = [vision._png(vision.Image.open(png))]
    for k, q in QUESTIONS.items():
        r = complete_json("This is a frame of a vertical phone video.\n" + q + "\nAnswer yes or no, and say where if yes.", YESNO, img, provider=provider,
                          max_tokens=80, timeout=120, temperature=0.0, cache=False)
        if r.get("answer") == "yes":
            out.append(k)
    return out


def checklist(png: Path, provider) -> list[str]:
    return vision.check_frame(png, "(not given)", provider)["problems"]


def main() -> None:
    frames, labels = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    models = sys.argv[3].split(",") if len(sys.argv) > 3 else ["qwen2.5vl:7b", "gemma4:latest", "llama3.2-vision:latest"]
    for m in models:
        prov = OllamaProvider(m)
        for name, fn in (("checklist", checklist), ("focused", focused)):
            tp = fp = fn_ = 0
            t0 = time.time()
            for f, want in labels.items():
                try:
                    got = set(fn(frames / f, prov)) & set(QUESTIONS)
                except Exception as e:
                    print(f"  {m} {name} {f}: {type(e).__name__} {str(e)[:80]}")
                    continue
                want = set(want)
                tp += len(got & want)
                fp += len(got - want)
                fn_ += len(want - got)
            p = tp / (tp + fp) if tp + fp else 0.0
            r = tp / (tp + fn_) if tp + fn_ else 0.0
            print(f"{m:<28} {name:<10} precision {p:.2f} recall {r:.2f} (tp {tp} fp {fp} missed {fn_}) {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
