"""The System panel says what Video Tool is doing (not what other programs do); the sidebar shows the card Video Tool uses; the Director pill names the director
that will actually be used first; the directors list says when Claude on this PC is not connected."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
C = ROOT / "client/studio/src"


def sub(path, old, new):
    s = path.read_text(encoding="utf-8")
    assert old in s, (path.name, old[:70])
    path.write_text(s.replace(old, new, 1), encoding="utf-8")


# ---- server: summary by who is using the card, and which card each job is assigned
S = ROOT / "server/vt/sysstats.py"
sub(S, '''    using = [g["name"] for g in gpus if g["usable_by_video_tool"]]''', '''    using = [g["name"] for g in gpus if g["usable_by_video_tool"]]
    ours = [g["name"] for g in gpus if any(p["ours"] or p["label"] in ("ComfyUI", "Ollama", "Video renderer", "Video Tool") for p in g["programs"])]
    others = [g["name"] for g in gpus if g["usable_by_video_tool"] and (g["percent"] or 0) >= 5 and g["name"] not in ours]
    try:
        from . import gpuassign

        assignment = {j: (gpuassign.resolve(j)[0] or {}).get("index") for j in gpuassign.JOBS}
    except Exception:                                                   # noqa: BLE001
        assignment = {}''')
sub(S, '''"summary": {"gpus_video_tool_can_use": using, "gpu_in_use": [g["name"] for g in gpus if (g["percent"] or 0) >= 5 and g["usable_by_video_tool"]]}}''',
    '''"assignment": assignment,
            "summary": {"gpus_video_tool_can_use": using, "gpu_in_use": ours, "busy_with_other_programs": others}}''')

# ---- panel and pill
P = C / "components/SystemStats.tsx"
sub(P, "  summary: { gpus_video_tool_can_use: string[]; gpu_in_use: string[] };", "  assignment?: { render?: number | null; speech?: number | null };\n  summary: { gpus_video_tool_can_use: string[]; gpu_in_use: string[]; busy_with_other_programs?: string[] };")
sub(P, '''  const busiest = s.gpus.filter((g) => g.usable_by_video_tool).sort((a, b) => (b.percent ?? 0) - (a.percent ?? 0))[0] ?? s.gpus[0];''',
    '''  const busiest = s.gpus.find((g) => g.index === s.assignment?.render) ?? s.gpus.filter((g) => g.usable_by_video_tool).sort((a, b) => (b.percent ?? 0) - (a.percent ?? 0))[0] ?? s.gpus[0];   // the card Video Tool renders on''')
sub(P, '''  const busy = s ? s.gpus.filter((g) => (g.percent ?? 0) >= 5 && g.usable_by_video_tool).map((g) => g.name).sort().join(", ") : "";
  useEffect(() => { if (s) setSaid(busy ? `Working on ${busy}.` : "No graphics card is busy."); }, [busy, !!s]);          // one calm sentence, only when it changes''',
    '''  const busy = s ? s.summary.gpu_in_use.slice().sort().join(", ") : "";
  useEffect(() => { if (s) setSaid(busy ? `Video Tool is using ${busy}.` : "Video Tool is not using a graphics card right now."); }, [busy, !!s]);          // one calm sentence, only when it changes''')
sub(P, '''        {s.host.os}. {usable.length ? <>Video Tool can use: <strong>{usable.join(", ")}</strong>.{using ? <> Working now on <strong>{using}</strong>.</> : " Nothing is drawing on it right now."}</> : "No NVIDIA graphics card is available to Video Tool: work runs on the processor."}
        {s.gpus.some((g) => !g.usable_by_video_tool) ? ` Kept free for other programs: ${s.gpus.filter((g) => !g.usable_by_video_tool).map((g) => g.name).join(", ")}.` : ""}''',
    '''        {s.host.os}. {usable.length ? <>{using ? <>Video Tool is using <strong>{using}</strong>.</> : "Video Tool is not using a graphics card right now."}{(s.summary.busy_with_other_programs || []).length ? <> Other programs are busy on <strong>{(s.summary.busy_with_other_programs || []).join(" and ")}</strong>.</> : ""}</> : "No NVIDIA graphics card is available to Video Tool: work runs on the processor."}
        {s.gpus.some((g) => !g.usable_by_video_tool) ? ` Kept free for other programs: ${s.gpus.filter((g) => !g.usable_by_video_tool).map((g) => g.name).join(", ")}.` : ""}''')
sub(P, '''            <span className={`chip ${g.usable_by_video_tool ? "ok" : ""}`}>{g.usable_by_video_tool ? "Video Tool can use it" : "kept free for you"}</span>''',
    '''            {s.assignment?.render === g.index && <span className="chip accent">Rendering</span>}
            {s.assignment?.speech === g.index && <span className="chip accent">Speech recognition</span>}
            {!g.usable_by_video_tool && <span className="chip">kept free for you</span>}''')

# ---- shell: the Director pill names the director that will be used first
SH = C / "Shell.tsx"
sub(SH, "  const conn = useStore(connStore);", '''  const conn = useStore(connStore);
  const [dirs, setDirs] = useState<{ order?: string[]; directors: { kind: string; label: string; available: boolean }[] } | null>(null);
  useEffect(() => {                                                // who will direct the next video: the first available one in the person's order
    const read = () => get<{ order?: string[]; directors: { kind: string; label: string; available: boolean }[] }>("/api/directors").then(setDirs).catch(() => {});
    read();
    const t = window.setInterval(() => { if (!document.hidden) read(); }, 15000);
    return () => window.clearInterval(t);
  }, []);
  const firstDirector = dirs ? (dirs.order || []).map((k) => dirs.directors.find((d) => d.kind === k && d.available)).find(Boolean) : null;''')
sub(SH, '<span className="hide-sm">Director: </span>{aiName}', '<span className="hide-sm">Director: </span>{firstDirector?.label ?? aiName}')

# ---- settings: one word, and a plain line when Claude on this PC is not connected
ST = C / "pages/Settings.tsx"
sub(ST, "Automatic tries these helpers in order. If one is asleep or does not answer, the next one takes over.", "Automatic tries these directors in order. If one is asleep or does not answer, the next one takes over.")
sub(ST, 'label="Try these helpers in this order"', 'label="Try these directors in this order"') if 'label="Try these helpers in this order"' in ST.read_text(encoding="utf-8") else None
s = ST.read_text(encoding="utf-8")
s = s.replace('<Field label="Try these helpers in this order">', '<Field label="Try these directors in this order">')
anchor = '        <span className="small muted">Claude today:'
assert anchor in s
s = s.replace(anchor, '''        {!(directors.data?.directors || []).some((d) => d.kind === "claude-client") && (
          <div className="row" data-testid="claude-pc-missing"><span className="chip warn">Not connected</span><strong>Claude on this PC</strong>
            <span className="small muted">Open the Ultimate Video Tool app on your PC, signed in to Claude Code, and it appears here.</span></div>
        )}
''' + anchor, 1)
ST.write_text(s, encoding="utf-8")

# ---- touch targets
css = C / "styles.css"
c = css.read_text(encoding="utf-8")
c = c.replace(".pill { display: inline-flex;", "button.pill { min-height: 32px; }\n.pill { display: inline-flex;", 1)
css.write_text(c, encoding="utf-8")
print("ok")
