import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Clock3, Copy, Download, Loader2, OctagonX, Terminal } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { get, post } from "../api";
import { jobsStore, toast, useStore } from "../store";
import type { JobInfo } from "../types";
import { ProgressBar } from "../ui";

/* What the server is working on right now, and what it did lately. Each job opens into its full log: every step it reports and every line it writes
   (server vt/server/jobs.py, GET /api/jobs/{id}/log). A running job follows itself; a finished one keeps its log until the server restarts. */
interface Line { n: number; t: number; level: string; text: string }
type Filter = "all" | "steps" | "problems";

const KIND: Record<string, string> = {
  pipeline: "Making a video", export: "Exporting", thumb: "Preview picture", thumbs: "Scene pictures for the editor", reel: "Drawing pictures", comfy: "Making a clip",
  autofix: "Fixing the things to look at", catalog: "Reading the picture library", context: "Working out what the video is about", cutout: "Cutting out a picture",
  director: "A director is working", import: "Bringing in a video", llm: "The Local AI is working", media: "Preparing your pictures and sounds", model: "Getting a model",
  overdub: "Replacing a voice", plan: "Planning the scenes", polish: "Polishing the cut", publish: "Writing the title and hashtags", qa: "Looking at every scene",
  redraw: "Drawing a picture again", setup: "Setting up the server", shorts: "Finding short clips", shorts_batch: "Making short clips", shorts_export: "Exporting a short clip",
  shorts_slice: "Cutting a short clip", sounds: "Choosing sounds",
};
const kindName = (j: JobInfo) => KIND[j.kind] ?? j.kind;
const secs = (ms: number) => { const s = Math.max(0, Math.round(ms / 1000)); return s >= 3600 ? `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min` : s >= 60 ? `${Math.floor(s / 60)} min ${s % 60} s` : `${s} s`; };
const stamp = (t: number) => new Date(t * 1000).toLocaleTimeString([], { hour12: false });
const started = (j: JobInfo) => (j.started_at ? Date.parse(j.started_at) : NaN);
const ended = (j: JobInfo) => (j.finished_at ? Date.parse(j.finished_at) : NaN);

function useNow(active: boolean) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (!active) return; const id = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(id); }, [active]);
  return now;
}

/** The job's whole log. Polls for new lines while the job runs, follows the bottom unless the person scrolls up, and can be copied or saved. */
function JobLog({ job }: { job: JobInfo }) {
  const [lines, setLines] = useState<Line[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [follow, setFollow] = useState(true);
  const [failed, setFailed] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const last = useRef(0);
  const live = job.status === "running" || job.status === "queued";

  useEffect(() => {
    let stop = false;
    const pull = () => get<{ lines: Line[] }>(`/api/jobs/${job.id}/log?after=${last.current}`)
      .then((r) => { if (stop) return; setFailed(false); if (r.lines.length) { last.current = r.lines[r.lines.length - 1].n; setLines((p) => [...p, ...r.lines]); } })
      .catch(() => { if (!stop) setFailed(true); });
    pull();
    if (!live) return () => { stop = true; };
    const id = window.setInterval(() => { if (!document.hidden) pull(); }, 1500);
    return () => { stop = true; window.clearInterval(id); };
  }, [job.id, live]);

  // one last read when a job finishes, so the closing lines are there
  useEffect(() => { if (!live) get<{ lines: Line[] }>(`/api/jobs/${job.id}/log?after=${last.current}`).then((r) => { if (r.lines.length) { last.current = r.lines[r.lines.length - 1].n; setLines((p) => [...p, ...r.lines]); } }).catch(() => {}); }, [live, job.id]);

  const shown = useMemo(() => lines.filter((l) => filter === "all" || (filter === "steps" ? l.level === "step" : ["warning", "error", "trace"].includes(l.level))), [lines, filter]);
  useEffect(() => { if (follow && box.current) box.current.scrollTop = box.current.scrollHeight; }, [shown, follow]);

  const text = () => lines.map((l) => `${stamp(l.t)} ${l.level.toUpperCase().padEnd(7)} ${l.text}`).join("\n");
  const copy = () => navigator.clipboard?.writeText(text()).then(() => toast("Log copied.", "ok", 2000)).catch(() => toast("The browser refused to copy.", "err"));
  const save = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text()], { type: "text/plain" }));
    a.download = `job-${job.id}.log`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="joblog">
      <div className="joblog-bar">
        <div className="joblog-filters" role="group" aria-label="Which lines to show">
          {(["all", "steps", "problems"] as Filter[]).map((f) => (
            <button key={f} type="button" className={`joblog-chip${filter === f ? " on" : ""}`} aria-pressed={filter === f} onClick={() => setFilter(f)}>{f === "all" ? "Everything" : f === "steps" ? "Steps" : "Problems"}</button>
          ))}
        </div>
        <label className="joblog-follow"><input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> Follow</label>
        <button type="button" className="joblog-icon" onClick={copy} aria-label="Copy the log" title="Copy the log"><Copy size={14} /></button>
        <button type="button" className="joblog-icon" onClick={save} aria-label="Save the log as a file" title="Save the log as a file"><Download size={14} /></button>
      </div>
      <div className="joblog-body" ref={box} tabIndex={0} role="log" aria-label={`Log of ${job.label}`} onWheel={() => setFollow(false)}>
        {failed && <p className="joblog-empty">The server did not answer. Trying again.</p>}
        {!failed && !shown.length && <p className="joblog-empty">{lines.length ? "Nothing matches this filter." : live ? "Waiting for the first line…" : "This job left no log (the server restarted since)."}</p>}
        {shown.map((l) => (
          <div key={l.n} className={`jl ${l.level}`}>
            <time>{stamp(l.t)}</time>
            <span className="jl-level">{l.level === "step" ? "step" : l.level}</span>
            <pre>{l.text}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}

function JobCard({ job, now, open, onToggle }: { job: JobInfo; now: number; open: boolean; onToggle: () => void }) {
  const live = job.status === "running" || job.status === "queued";
  const t0 = started(job);
  const elapsed = Number.isFinite(t0) ? (Number.isFinite(ended(job)) ? ended(job) : now) - t0 : 0;
  const eta = job.status === "running" && job.frac > 0.05 ? elapsed / job.frac - elapsed : null;
  const cancel = () => post(`/api/jobs/${job.id}/cancel`).then(() => toast("Stopping…", "ok", 2000)).catch((e) => toast(e.message, "err"));
  const Icon = job.status === "running" ? Loader2 : job.status === "queued" ? Clock3 : job.status === "done" ? CheckCircle2 : job.status === "error" ? AlertTriangle : OctagonX;
  const word = { running: "Running", queued: "Waiting", done: "Done", error: "Failed", cancelled: "Stopped" }[job.status];
  return (
    <article className={`jobcard ${job.status}${open ? " open" : ""}`} aria-label={`${kindName(job)}: ${job.label}`}>
      <header className="jobcard-head">
        <span className={`jobcard-icon ${job.status}`} aria-hidden><Icon size={16} className={job.status === "running" ? "spin" : ""} /></span>
        <div className="jobcard-title">
          <strong>{job.label || kindName(job)}</strong>
          <span className="muted small">{kindName(job)}{job.project ? <> · <Link to={`/p/${job.project}`}>Open</Link></> : null}</span>
        </div>
        <span className={`jobcard-state ${job.status}`}>{word}</span>
      </header>
      {live && (
        <div className="jobcard-progress">
          <ProgressBar frac={job.status === "queued" ? 0 : job.frac} />
          <div className="jobcard-meta small">
            <span className="jobcard-now">{job.status === "queued" ? "Waiting for the job before it to finish." : [job.stage, job.msg].filter(Boolean).join(" · ") || "Starting…"}</span>
            <span className="muted">{job.status === "running" ? `${Math.round(job.frac * 100)}%` : ""}{elapsed ? ` · ${secs(elapsed)}` : ""}{eta ? ` · about ${secs(eta)} left` : ""}</span>
          </div>
        </div>
      )}
      {!live && (
        <p className="jobcard-meta small muted" style={{ margin: 0 }}>
          {job.status === "error" ? job.error : elapsed ? `Took ${secs(elapsed)}` : ""}
        </p>
      )}
      <div className="jobcard-actions">
        <button type="button" className="btn sm ghost" onClick={onToggle} aria-expanded={open}>
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />} <Terminal size={13} /> {open ? "Hide details" : "Show details"}
        </button>
        {live && <button type="button" className="btn sm ghost danger" onClick={cancel}>Stop</button>}
      </div>
      {open && <JobLog job={job} />}
    </article>
  );
}

export default function JobsPanel() {
  const all = useStore(jobsStore);
  const list = useMemo(() => Object.values(all).sort((a, b) => (a.created_at ?? a.id) < (b.created_at ?? b.id) ? 1 : -1), [all]);
  const active = list.filter((j) => j.status === "running" || j.status === "queued").sort((a, b) => (a.status === b.status ? 0 : a.status === "running" ? -1 : 1));
  const recent = list.filter((j) => !(j.status === "running" || j.status === "queued")).slice(0, 8);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [seeAll, setSeeAll] = useState(false);
  const now = useNow(active.length > 0);
  const running = active.filter((j) => j.status === "running").length;

  // a job that starts while the page is open shows its details by itself
  const seen = useRef<Set<string>>(new Set());
  useEffect(() => {
    const fresh = active.filter((j) => j.status === "running" && !seen.current.has(j.id));
    fresh.forEach((j) => seen.current.add(j.id));
    if (fresh.length && seen.current.size <= 1) setOpen((o) => ({ ...o, [fresh[0].id]: true }));
  }, [active]);

  const toggle = (id: string) => setOpen((o) => ({ ...o, [id]: !o[id] }));
  return (
    <section className="card card-pad jobs" aria-labelledby="jobs-h" data-testid="jobs-panel">
      <div className="jobs-title">
        <h2 id="jobs-h">Jobs</h2>
        <span className="small muted" role="status">{active.length ? `${running} running${active.length - running ? ` · ${active.length - running} waiting` : ""}` : "Nothing is running"}</span>
      </div>
      {active.length === 0 && <p className="jobs-idle">Nothing is being made right now.</p>}
      <div className="jobs-list">
        {active.map((j) => <JobCard key={j.id} job={j} now={now} open={!!open[j.id]} onToggle={() => toggle(j.id)} />)}
      </div>
      {recent.length > 0 && (
        <>
          <h3 className="jobs-sub">Recent</h3>
          <div className="jobs-list">
            {(seeAll ? recent : recent.slice(0, 3)).map((j) => <JobCard key={j.id} job={j} now={now} open={!!open[j.id]} onToggle={() => toggle(j.id)} />)}
          </div>
          {recent.length > 3 && <button type="button" className="btn sm ghost" onClick={() => setSeeAll((v) => !v)}>{seeAll ? "Show fewer" : `Show ${recent.length - 3} more`}</button>}
        </>
      )}
    </section>
  );
}
