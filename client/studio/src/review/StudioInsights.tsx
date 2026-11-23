// O7 (docs/plans/PLAN-OPENMOTION.MD): what only Video Tool knows, beside the HyperFrames Studio. "Outline": the talk's sections and examples, each
// example marked with whether it got B-roll; "Checks": the retention check of the newest export and the notices (extras that were skipped).
// Every time is a button that moves the Studio there.
import { AlertTriangle, CheckCircle2, Image as ImageIcon, Loader2, Mic } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { del, get, post } from "../api";

interface Outline {
  sections: { start: number; end: number; point: string }[];
  examples: { kind: string; about: string; show: string; start: number; end: number; scenes: string[]; broll: boolean }[];
  keep: { start: number; end: number; why: string }[];
  summary: string; covered: number;
}
interface Retention { file: string; checked: boolean; risk?: number; score?: number; verdict?: string; worst?: { t0: number; t1: number; kind: string; message: string }[] }
interface Insights { outline: Outline | null; retention: Retention | null; notices: { at: string; stage: string; message: string; error?: string }[] }

export const clock = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;

export default function StudioInsights({ projectId, view, version, onSeek }: {
  projectId: string; view: "outline" | "checks"; version?: number; onSeek: (t: number) => void;
}) {
  const [data, setData] = useState<Insights | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const base = `/api/projects/${encodeURIComponent(projectId)}`;
  const load = useCallback(() => get<Insights>(`${base}/insights`).then(setData).catch((e) => setProblem(e.message)), [base]);
  useEffect(() => { load(); }, [load, version]);

  if (!data) return <div className="studio-insights muted small">{problem || "Loading…"}</div>;
  const at = (t: number) => <button className="btn ghost sm studio-time" onClick={() => onSeek(t)} title="Show this moment in HyperFrames">{clock(t)}</button>;

  if (view === "outline") {
    const o = data.outline;
    if (!o) return <div className="studio-insights small muted">This video has no outline. Long talks get one when they are planned: the sections, and the examples that get pictures.</div>;
    return (
      <div className="studio-insights" aria-label="Outline of the talk">
        <p className="small"><strong>{o.examples.length} examples</strong>, {o.covered} with B-roll{o.examples.length > o.covered ? `, ${o.examples.length - o.covered} on the speaker` : ""}.</p>
        <ol className="studio-outline" aria-label="Sections">
          {o.sections.map((s, i) => {
            const ex = o.examples.filter((e) => e.start >= s.start - 0.01 && e.start < s.end + 0.01);
            return (
              <li key={i}>
                <div className="row">{at(s.start)}<strong className="small">{s.point}</strong></div>
                {ex.length > 0 && <ul className="studio-examples" aria-label={`Examples in ${s.point}`}>
                  {ex.map((e, k) => (
                    <li key={k} className={e.broll ? "has" : "none"}>
                      <div className="row">{at(e.start)}
                        {e.broll ? <ImageIcon size={13} aria-label="has B-roll" /> : <Mic size={13} aria-label="on the speaker" />}
                        <span className="small"><span className="muted">{e.kind}:</span> {e.about}</span></div>
                      {!e.broll && <div className="small muted studio-show" title="What the outline says a viewer should see here">Could show: {e.show}</div>}
                    </li>))}
                </ul>}
              </li>);
          })}
        </ol>
      </div>
    );
  }

  const r = data.retention;
  const check = async () => {
    setChecking(true); setProblem(null);
    try { await post(`${base}/retention`, {}); await load(); } catch (e: any) { setProblem(e.message); } finally { setChecking(false); }
  };
  return (
    <div className="studio-insights" aria-label="Checks">
      <section aria-label="Retention">
        <div className="row"><strong className="small">Will viewers stay?</strong><span className="grow" />
          {r && <button className="btn sm" disabled={checking} onClick={check}>{checking ? <><Loader2 className="spin" size={13} /> Checking…</> : r.checked ? "Check again" : "Check the export"}</button>}</div>
        {!r && <p className="small muted">Export the video first; the check looks at the finished video.</p>}
        {r && !r.checked && <p className="small muted">The newest export ({r.file}) has not been checked yet.</p>}
        {r?.checked && <>
          <p className="small">{(r.score ?? 0) >= 80 ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />} Score {r.score} of 100. {r.verdict}</p>
          <ul className="studio-worst" aria-label="Moments where viewers may leave">
            {(r.worst ?? []).map((m, i) => <li key={i} className="row">{at(m.t0)}<span className="small">{m.message}</span></li>)}
          </ul>
          <p className="small muted">From {r.file}. A change made since shows after the next export.</p>
        </>}
      </section>
      <section aria-label="Notices">
        <div className="row"><strong className="small">Skipped extras</strong><span className="grow" />
          {data.notices.length > 0 && <button className="btn ghost sm" onClick={() => del(`${base}/notices`).then(load)}>Got it</button>}</div>
        {data.notices.length === 0 ? <p className="small muted">Nothing was skipped.</p>
          : <ul className="studio-notices">{data.notices.map((n, i) => <li key={i} className="small" title={n.error}>{n.message}</li>)}</ul>}
      </section>
      {problem && <p className="small scene-pics-problem" role="alert">{problem}</p>}
    </div>
  );
}
