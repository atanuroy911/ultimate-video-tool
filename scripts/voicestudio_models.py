"""List, restore and verify the models of a VoiceStudio server, so any agent can rebuild them when the drive that held them is gone.

    export OMNIVOICE_API_KEY=...                       # the key from /mnt/bigdata/video-tool/voicestudio/voicestudio.env on the server
    python scripts/voicestudio_models.py --url http://192.168.123.47:3900 status
    python scripts/voicestudio_models.py --url ... restore               # installs the wanted models that are missing and have no licence gate
    python scripts/voicestudio_models.py --url ... restore --accept-licences "k2-fsa/OmniVoice"   # a PERSON decides this; the script never does it by default

`status` and `restore` read the server's own catalogue (`GET /models`), so they keep working when VoiceStudio adds models. The wanted list is `assets/voicestudio/model-manifest.json`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "assets" / "voicestudio" / "model-manifest.json"


def call(base: str, key: str, path: str, body: dict | None = None, timeout: float = 60):
    req = urllib.request.Request(base.rstrip("/") + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode("utf-8", "replace")[:300]}


def accept(base: str, key: str, repo_id: str) -> None:
    """Record a person's acceptance of one model's licence on the server. The caller must have been told to by a person (--accept-licences)."""
    from urllib.parse import quote

    details = call(base, key, "/models/licenses/details/" + quote(repo_id, safe=""))
    fingerprint = (details.get("acceptance") or {}).get("fingerprint")
    if not fingerprint:
        print("no licence fingerprint for", repo_id, details, file=sys.stderr)
        return
    print("accepting", repo_id, (details.get("info") or {}).get("license"), call(base, key, "/models/licenses/accept", {"repo_id": repo_id, "fingerprint": fingerprint, "accepted": True}))


def wanted() -> list[str]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["wanted"] if MANIFEST.exists() else []


def status(base: str, key: str) -> list[dict]:
    models = call(base, key, "/models").get("models", [])
    want = set(wanted())
    rows = []
    for m in models:
        li = m.get("license_info") or {}
        acc = (m.get("license_acceptance") or {})
        rows.append({"repo_id": m["repo_id"], "role": m.get("role"), "size_gb": m.get("size_gb"), "installed": bool(m.get("installed")), "wanted": m["repo_id"] in want,
                     "licence": li.get("license_category"), "licence_accepted": acc.get("accepted") if acc.get("required") else None})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("VOICESTUDIO_URL", "http://127.0.0.1:3900"))
    ap.add_argument("--key-env", default="OMNIVOICE_API_KEY")
    ap.add_argument("cmd", choices=["status", "restore"])
    ap.add_argument("--accept-licences", nargs="*", default=[], help="repo ids whose licence a person has read and accepts; without this a gated model is only listed")
    a = ap.parse_args()
    key = os.environ.get(a.key_env, "")
    if not key:
        print(f"set the key in ${a.key_env} first", file=sys.stderr)
        return 2
    rows = status(a.url, key)
    for r in rows:
        mark = "installed" if r["installed"] else ("MISSING (wanted)" if r["wanted"] else "-")
        gate = "" if r["licence_accepted"] in (None, True) else "  [licence not accepted]"
        print(f"{mark:18s} {r['role'] or '':12s} {r['repo_id']:60s} {r['size_gb']} GB  {r['licence']}{gate}")
    if a.cmd == "status":
        return 0
    todo = [r for r in rows if r["wanted"] and not r["installed"]]
    for extra in a.accept_licences:                              # licences of parts a model needs (for example its audio tokenizer) are passed by name too
        if extra not in {r["repo_id"] for r in todo}:
            accept(a.url, key, extra)
    for r in todo:
        if r["licence_accepted"] is False:
            if r["repo_id"] not in a.accept_licences:
                print(f"skipped {r['repo_id']}: its licence ({r['licence']}) needs a person's decision", file=sys.stderr)
                continue
            accept(a.url, key, r["repo_id"])
        print("installing", r["repo_id"], call(a.url, key, "/models/install", {"repo_id": r["repo_id"]}))
        for _ in range(720):
            time.sleep(10)
            if any(x["repo_id"] == r["repo_id"] and x["installed"] for x in status(a.url, key)):
                print("done", r["repo_id"])
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
