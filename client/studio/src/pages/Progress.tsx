import { useT } from "../i18n";
import { AlertTriangle, ChevronDown, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { get, post } from "../api";
import { useCatalogue, useProject, useProjectJob } from "../hooks";
import { jobsStore, settingsStore, toast, useStore } from "../store";
import { ProgressBar } from "../ui";
import { DirectorLogButton } from "../log/DirectorLog";
import LiveBoard from "../plan/LiveBoard";
import PlanSheet from "../plan/PlanSheet";

/* What the app is doing, in the words a person would use. The stage names are the pipeline's; "render", "check" and "publish"
   are the autopilot's finishing steps (vt/server/app.py autopilot_finish). */
const SAY: Record<string, string> = {
  voice: "Reading your script aloud",
  preprocess: "Cleaning up the sound",
  silence: "Finding the pauses",
  asr: "Listening to every word",
  cuts: "Cutting pauses, “um”s and retakes",
  sounds: "Listening for sounds",
  aroll: "Cutting the speaker's picture",
  words: "Timing every word",
  context: "Understanding what it is about",
  tighten: "Cutting it down to the best parts",
  plan: "Directing the scenes",
  compose: "Drawing the scenes",
  render: "Rendering your video",
  check: "Watching it back like a viewer",
  publish: "Writing the title and hashtags",
};
const FINISH = ["render", "check", "publish"];

export default function ProgressPage() {
  const t = useT();
  const { id } = useParams();
  const nav = useNavigate();
  const { data: project, refetch, error: projectError } = useProject(id);
  const cat = useCatalogue();
  const settings = useStore(settingsStore);
  const autopilot = settings.autopilot !== false;
  const active = useProjectJob(id);
  const jobs = useStore(jobsStore);
  const [log, setLog] = useState<string[]>([]);
  const [details, setDetails] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const askedAbout = useRef("");
  const lastMsg = useRef("");
  const started = useRef(Date.now());
  const [, tick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => tick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, []);

  // the most recent pipeline job for this project (active, or just finished)
  const latest = Object.values(jobs)
    .filter((j) => j.project === id && j.kind === "pipeline")
    .reverse().sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))[0];
  const job = active || latest;

  useEffect(() => {
    if (job?.stage === "asr" && job.msg && job.msg !== lastMsg.current) {
      lastMsg.current = job.msg;
      setLog((l) => [...l.slice(-60), job.msg]);
    }
  }, [job?.msg, job?.stage]);

  // leave when ready: to the finished video (autopilot) or to the editor
  const dest = project?.options?.review_script ? `/p/${id}/script` : autopilot ? `/p/${id}/result` : `/p/${id}`;
  const review = project?.status === "review";
  useEffect(() => {                                           // the director has a plan and is waiting: show it once, as a sheet; nothing is made before Start
    if (review && id && askedAbout.current !== id) { askedAbout.current = id; setPlanOpen(true); }
  }, [review, id]);
  useEffect(() => {
    if (job?.status === "done") {
      let cancelled = false;
      const tm = setTimeout(async () => {                   // a job that finished because it is waiting for the plan is not a finished video
        const fresh = await get<{ status: string }>(`/api/projects/${id}`).catch(() => null);
        if (cancelled) return;
        if (fresh?.status === "review") { refetch(); setPlanOpen(true); return; }
        nav(dest, { replace: true });
      }, 700);
      return () => { cancelled = true; clearTimeout(tm); };
    }
    if (!job && project && !project.active_job && ["planned", "rendered"].includes(project.status)) nav(dest, { replace: true });
  }, [job?.status, project?.status, id, nav, job, dest]); // eslint-disable-line react-hooks/exhaustive-deps

  const stages = [...(cat?.stages || []).map((s) => s.key).filter((k) => k !== "voice" || project?.source === "script"), ...(autopilot ? FINISH : [])];
  const cur = job?.stage || "";
  const curIdx = Math.max(0, stages.indexOf(cur));
  const interrupted = job?.interrupted || (!active && project?.status === "interrupted");
  const cancelled = job?.status === "cancelled" || (!active && project?.status === "cancelled");
  const failed = job?.status === "error" || interrupted || cancelled;
  const done = job?.status === "done";
  const overall = done ? 1 : (curIdx + (job?.frac ?? 0)) / Math.max(1, stages.length);
  const elapsed = (Date.now() - started.current) / 1000;
  const left = overall > 0.08 && !done && !failed ? Math.max(0, elapsed / overall - elapsed) : null;
  const fmt = (s: number) => (s < 60 ? `${Math.round(s)} s` : `${Math.round(s / 60)} min`);

  const retry = async (from?: string) => {
    try {
      await post(`/api/projects/${id}/run`, { from_stage: from || null, force: false });
      setLog([]);
      refetch();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  if (projectError && !project) return (                       // the server cannot say what this video is: say so, with a way on, never a spinner with no end
    <div className="page-inner making" style={{ maxWidth: 640 }}>
      <div className="card card-pad col" role="alert" style={{ gap: 12 }}>
        <h1 style={{ margin: 0 }}>Could not open this video</h1>
        <p className="muted" style={{ margin: 0 }}>{projectError}</p>
        <div className="row wrap" style={{ gap: 8 }}><button className="btn" onClick={refetch}>Try again</button><Link className="btn ghost" to="/">Your videos</Link></div>
      </div>
    </div>
  );

  return (
    <div className="page-inner making" style={{ maxWidth: 640 }}>
      <div className="card card-pad col" style={{ gap: 16 }}>
        <span className="small muted bn">{project?.title}</span>
        <h1 style={{ margin: 0 }} aria-live="polite">
          {review ? t("pr.ready") : interrupted ? "The server stopped" : cancelled ? "Making this video was stopped" : failed ? "Something went wrong" : done ? "Your video is ready" : SAY[cur] || "Getting started"}
          {!failed && !done && !review && "…"}
        </h1>
        <ProgressBar frac={overall} />
        <div className="row small muted">
          <span className="grow">{done ? "Opening it…" : `Step ${curIdx + 1} of ${stages.length} · ${Math.round((job?.frac ?? 0) * 100)}%`}</span>
          {left !== null && <span>about {fmt(left)} left</span>}
        </div>
        {review && (
          <div className="col" style={{ gap: 10, alignItems: "flex-start" }}>
            <span className="small muted">{t("pr.note")}</span>
            <button className="btn primary" onClick={() => setPlanOpen(true)} data-testid="open-plan">{t("pr.look")}</button>
          </div>
        )}
        {!failed && !done && !review && <span className="small muted">You can leave this page; it keeps going. Nothing needs your attention.</span>}

        {failed && (
          <div className="banner err col" style={{ alignItems: "flex-start" }}>
            <strong>{job?.error || (interrupted || cancelled ? "You can continue; completed stages are kept." : "The job failed.")}</strong>
            <div className="row wrap">
              <button className="btn" onClick={() => retry(!interrupted && !cancelled && cur && !FINISH.includes(cur) ? cur : undefined)}>{interrupted || cancelled ? "Continue" : "Try again"}</button>
              <button className="btn ghost" onClick={() => retry("preprocess")}>Start over</button>
              <Link className="btn ghost" to={`/p/${id}`}>Open the editor</Link>
            </div>
          </div>
        )}

        {active && (
          <div className="row">
            <button className="btn ghost" onClick={() => post(`/api/jobs/${active.id}/cancel`).then(() => toast("Cancelled")).catch((e) => toast(e.message, "err"))}>
              <X size={14} /> Cancel
            </button>
          </div>
        )}
      </div>

      {id && !review && <LiveBoard pid={id} />}
      <button className="btn ghost sm" style={{ alignSelf: "flex-start" }} onClick={() => setDetails(!details)} aria-expanded={details}>
        <ChevronDown size={14} style={{ transform: details ? "rotate(180deg)" : undefined }} /> What it is doing
      </button>
      {id && <DirectorLogButton pid={id} />}
      {details && (
        <div className="card card-pad col" style={{ gap: 8 }}>
          {stages.map((k, i) => (
            <div key={k} className="row small" style={{ gap: 8, opacity: i > curIdx && !done ? 0.5 : 1 }}>
              <span style={{ width: 16 }}>{done || i < curIdx ? "✓" : i === curIdx ? (failed ? <AlertTriangle size={13} color="var(--err)" /> : "•") : ""}</span>
              <span className="grow">{SAY[k] || k}</span>
              {i === curIdx && !done && <span className="muted">{Math.round((job?.frac ?? 0) * 100)}%</span>}
            </div>
          ))}
          {log.length > 0 && <div className="log bn" aria-live="off">{log.join("\n")}</div>}
        </div>
      )}
      {planOpen && id && <PlanSheet pid={id} onClose={() => setPlanOpen(false)} onStarted={() => { setPlanOpen(false); started.current = Date.now(); refetch(); }} />}
    </div>
  );
}
