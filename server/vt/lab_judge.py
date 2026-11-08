"""D1 checks for an existing export and composition. No export or plan is created."""
from __future__ import annotations

import argparse
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import craft, retention
from .ai import talk
from .compose import FORMATS
from .judges import LOUDNESS_RANGE
from .modules.calls import redact
from .project import Project
from .render.hyperframes import frame_acceptance
from .secure_paths import project_file
from .server.review_routes import export_aspect, judge_export
from .util import CREATE_NO_WINDOW, find_tool, read_json


@dataclass(frozen=True)
class Check:
    title: str
    passed: bool
    detail: str


def _reason(exc: Exception) -> str:
    return str(redact(str(exc))).split("\n", 1)[0][:200] or type(exc).__name__


def _checked(title: str, check: Callable[[], tuple[bool, str]]) -> Check:
    try:
        passed, detail = check()
        return Check(title, passed, detail)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, IndexError, subprocess.SubprocessError) as exc:
        return Check(title, False, _reason(exc))


def _export(project: Project, name: str | None) -> Path:
    folder = project_file(project.dir, "exports")
    if name is not None:
        if Path(name).name != name or name.startswith(".") or not name.endswith(".mp4") or any(c in name for c in "/\\:"):
            raise ValueError("Choose an MP4 filename from this project's exports.")
        video = project_file(folder, name)
        if not video.is_file():
            raise FileNotFoundError("The requested export does not exist.")
        return video
    candidates = [project_file(folder, file.name) for file in folder.glob("*.mp4") if not file.name.startswith(".")]
    files = [file for file in candidates if file.is_file()]
    if not files:
        raise FileNotFoundError("This project has no exported MP4 to judge.")
    return max(files, key=lambda file: (file.stat().st_mtime_ns, file.name))


def _director(project: Project, actual: str) -> tuple[bool, str]:
    if actual.startswith(("claude@", "codex@")):
        expected = actual.split("@", 1)[0] + "-pc"
    else:
        expected = {"local": "ollama", "claude-server": "claude-cli"}.get(actual)
    rows = talk.load(project.dir)
    voices = {str(row["who"]) for row in rows if row.get("who")}
    observed = ", ".join(sorted(voices)) or "none"
    if expected and voices == {expected}:
        return True, f"{actual} matches all {len(rows)} conversation rows."
    return False, f"Recorded director {actual or 'none'}. Conversation directors {observed}."


def _fallback(project: Project, authority: dict) -> tuple[bool, str]:
    notice = read_json(project_file(project.dir, "ai_notice.json"), {}) or {}
    message = authority.get("fallback_reason") or notice.get("message")
    if message:
        return False, str(redact(message)).split("\n", 1)[0][:200]
    return True, "No fallback was recorded."


CROSSING = ("walk_in", "walk_out")                     # a figure walking on or off the screen crosses its edge on purpose


def _crossing(comp: dict, label: str, t: float) -> bool:
    """Whether a cartoon figure called `label` is walking on or off the screen at t (a walk-in sampled half-way was failed, 2026-11-08)."""
    for sc in comp.get("scenes", []):
        st = sc.get("stick") or {}
        ids = {c.get("id") for c in st.get("cast") or [] if label in (c.get("name"), c.get("id"))}
        if ids and any(a.get("who") in ids and a.get("do") in CROSSING and float(a.get("start", -1)) - 0.05 <= t <= float(a.get("end", -1)) + 0.05
                       for a in st.get("actions") or []):
            return True
    return False


def _frame_checks(comp_dir: Path, comp: dict) -> list[Check]:
    titles = ("Face coverage", "Inside the frame", "First frame subject")
    try:
        times = {0.0}
        if not comp:
            raise FileNotFoundError("This export has no saved composition to inspect.")
        scenes = comp.get("scenes")
        if not scenes:
            raise ValueError("The composition has no scenes.")
        for scene in scenes:
            start, end = float(scene["start"]), float(scene["end"])
            if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end):
                raise ValueError("The composition has an invalid scene time.")
            times.add((start + end) / 2)
        measured = frame_acceptance(comp_dir, sorted(times))
        # Missing samples or an older probe without structured data must fail.
        covered = [(t, hit) for t in sorted(times) for hit in measured[t]["coveredFaces"] if hit["percent"] > 10]
        outside = [(t, label) for t in sorted(times) for label in measured[t]["outside"] if not _crossing(comp, label, t)]
        subject = measured[0.0]["subject"] is True
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, IndexError, subprocess.SubprocessError) as exc:
        return [Check(title, False, f"Frame measurement failed. {_reason(exc)}") for title in titles]

    coverage = f"No detected face is more than 10% covered across {len(times)} samples."
    if covered:
        t, hit = covered[0]
        coverage = f"{hit['by']} covers {hit['percent']:.2f}% of {hit['face']}'s face at {t:.2f} s."
    bounds = f"Measured subjects and captions stay in frame across {len(times)} samples."
    if outside:
        t, label = outside[0]
        bounds = f"{label} extends outside the frame at {t:.2f} s."
    return [Check(titles[0], not covered, coverage), Check(titles[1], not outside, bounds),
            Check(titles[2], subject, "A visible subject is present at 0 s." if subject else "No visible subject at 0 s.")]


def _one_picture(comp: dict) -> tuple[bool, str]:
    """A cartoon shows one picture at a time over its drawing (owner, 2026-11-08). Two separate pictures (not a sticker and its label,
    which arrive together) may share the frame only while one hands over to the other: 0.4 s."""
    from .compose.composer import PAGEABLE, TOGETHER

    for sc in comp.get("scenes", []):
        if not sc.get("stick"):
            continue
        shown = sorted(((float(e["at"]), float(e.get("until", sc["end"])), e) for e in sc.get("elements", []) if e.get("type") in PAGEABLE),
                       key=lambda x: x[0])
        for i, (a0, a1, a) in enumerate(shown):
            for b0, b1, b in shown[i + 1:]:
                if b0 - a0 > TOGETHER and min(a1, b1) - b0 > 0.4:
                    what = lambda e: e.get("label") or e.get("name") or e.get("emoji") or e["type"]  # noqa: E731
                    return False, f"{what(a)} and {what(b)} share the frame for {min(a1, b1) - b0:.1f} s from {b0:.2f} s (scene {sc['id']})."
    return True, "Cartoon scenes show one picture at a time."


def _craft(project: Project) -> tuple[bool, str]:
    result = craft.check(project)
    if result["score"] is None:
        return False, "There is no scene plan to check."
    serious = [v for v in result["violations"] if v["severity"] in ("critical", "major")]
    if serious:
        return False, f"{len(serious)} critical or major finding(s). {serious[0]['says']}"
    return True, "No critical or major craft findings."


def _retention(project: Project, video: Path, aspect: str, comp: dict) -> tuple[bool, str]:
    audio = project_file(project.dir, "audio.cut.wav")
    card = retention.scorecard(video, aspect, comp, audio if audio.is_file() else None)
    risk = float(card["risk"])
    return math.isfinite(risk) and 0 <= risk <= 15, f"Risk {risk:g}/100. Strong requires 15 or less."


def _automatic(project: Project, video: Path) -> tuple[Check, Check]:
    try:
        result = judge_export(project, video, persist=False)
        names = ", ".join(result["failed"])
        details = f"Failed checks include {names}." if names else "All applicable automatic judges passed."
        if result["skipped"]:
            details += " The automatic judges skipped " + ", ".join(result["skipped"]) + "."
        judges = Check("Automatic judges", result["passed"] is True and not names, details)
        loudness = next((v for v in result["verdicts"] if v["judge"] == "loudness"), {})
        lufs = (loudness.get("value") or {}).get("lufs")
        if lufs is None:
            return judges, Check("Loudness", False, "No integrated loudness was measured.")
        lo, hi = LOUDNESS_RANGE
        return judges, Check("Loudness", math.isfinite(lufs) and lo <= lufs <= hi,
                             f"{lufs:.1f} LUFS. Required range {lo:g} to {hi:g} LUFS.")
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, IndexError, subprocess.SubprocessError) as exc:
        return Check("Automatic judges", False, _reason(exc)), Check("Loudness", False, "Automatic measurement failed.")


def _blackdetect(video: Path) -> tuple[bool, str]:
    result = subprocess.run([find_tool("ffmpeg"), "-hide_banner", "-nostdin", "-nostats", "-xerror", "-hwaccel", "none",
                             "-i", str(video), "-map", "0:v:0", "-vf", "blackdetect=d=0.1:pix_th=0.12", "-an", "-f", "null", "-"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240, creationflags=CREATE_NO_WINDOW)
    if result.returncode != 0:
        return False, f"FFmpeg could not decode the video (exit {result.returncode})."
    flashes = re.findall(r"black_start:([\d.]+) black_end:[\d.]+ black_duration:([\d.]+)", result.stderr)
    if flashes:
        start, duration = flashes[0]
        return False, f"{len(flashes)} black section(s). First at {start} s for {duration} s."
    return True, "No black section of 0.1 s or longer."


def judge_project(project: Project, name: str | None = None) -> list[Check]:
    for filename in ("project.json", "transcript.json", "beats.json", "scenes.json", "context.json", "reel_report.json", "plan_doc.json"):
        project_file(project.dir, filename)
    meta = project.meta()
    video = _export(project, name)
    aspect = export_aspect(project, video)
    comp_dir = project_file(project.dir, f"composition/{FORMATS[aspect]['tag']}")
    comp = read_json(project_file(comp_dir, "data.json"), {}) or {}
    project_file(comp_dir, "index.html")
    authority = meta.director or {}
    checks = [
        _checked("One director", lambda: _director(project, authority.get("who", ""))),
        _checked("Fallback notice", lambda: _fallback(project, authority)),
        *_frame_checks(comp_dir, comp),
        _checked("One picture at a time", lambda: _one_picture(comp)),
        _checked("Craft", lambda: _craft(project)),
        _checked("Retention", lambda: _retention(project, video, aspect, comp)),
        *_automatic(project, video),
        _checked("Black flashes", lambda: _blackdetect(video)),
    ]
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--data", type=Path, required=True, help="Data folder containing the projects")
    parser.add_argument("--file", help="Export filename. Defaults to the newest finished MP4")
    args = parser.parse_args(argv)

    try:
        pid = args.project
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", pid) or pid in (".", ".."):
            raise ValueError("Invalid project ID.")
        projects = project_file(args.data, "projects")
        if not project_file(projects, pid).is_dir():
            raise FileNotFoundError(f"Project '{pid}' was not found.")
        checks = judge_project(Project(pid, projects), args.file)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        checks = [Check("Project and export", False, _reason(exc))]
    for check in checks:
        detail = " ".join(str(redact(check.detail)).splitlines())
        print(f"{'PASS' if check.passed else 'FAIL'}  {check.title} — {detail}")
    print("Visual review remains separate. Watch the first three seconds and inspect the contact sheet for meaning, numbers, continuity, readability and engagement.")
    return int(any(not check.passed for check in checks))


if __name__ == "__main__":
    raise SystemExit(main())
