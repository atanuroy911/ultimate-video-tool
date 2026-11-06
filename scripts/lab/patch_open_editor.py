"""A finished video that is only exporting opens in the editor, not on the Progress page (owner, 2026-11-03: "clicking it goes to export, not the timeline")."""
from pathlib import Path

S = Path(__file__).resolve().parents[2] / "client/studio/src/pages"


def sub(name, old, new):
    p = S / name
    s = p.read_text(encoding="utf-8")
    assert old in s, (name, old[:60])
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


old = 'const isBusy = (project: ProjectSummary) => project.status === "processing" || !!project.active_job;'
sub("Projects.tsx", old, old + '''
/** The video is still being made (not just a download being rendered): only then does opening it show progress. A finished video that is exporting opens in the editor. */
export const isBeingMade = (project: ProjectSummary) => project.status === "processing" || (!!project.active_job && project.active_job.kind !== "export");''')
sub("Projects.tsx", "nav(isBusy(project) ? `/p/${project.id}/progress` : `/p/${project.id}`);",
    "nav(isBeingMade(project) ? `/p/${project.id}/progress` : `/p/${project.id}`);")
sub("Review.tsx", 'if (p && (p.status === "processing" || p.active_job)) nav(`/p/${id}/progress`, { replace: true });',
    'if (p && (p.status === "processing" || (p.active_job && p.active_job.kind !== "export"))) nav(`/p/${id}/progress`, { replace: true });   // a download rendering in the background does not take the editor away')
print("ok")
