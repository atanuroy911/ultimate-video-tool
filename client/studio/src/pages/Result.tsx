import { Copy, Download, Palette, PenLine, SlidersHorizontal, Sparkles, Wand2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { patch, post } from "../api";
import { jobsStore, toast, useChanged, useStore } from "../store";
import { useFetch, useProject, useThemes } from "../hooks";
import { copyText, ProgressBar, Spinner } from "../ui";
import RedoModal from "../components/RedoModal";
import SocialDispatch from "../components/SocialDispatch";
import { DirectorLogButton } from "../log/DirectorLog";
import QualityCheck, { type Judges } from "../components/QualityCheck";
import "./result-cleanup.css";

/* The finished video: watch it, download it, and the three things people most often want to change. Everything else is in the editor. */
interface ExportFile {
  name: string;
  url: string;
  size: number;
  retention: { verdict: string; risk: number; worst: { t: number; why: string }[] } | null;
  judges?: Judges | null;
}
interface Decision {
  text: string;
  reason: string;
}
interface CraftReport {
  score: number | null;
  violations: { rule: string; t0: number; t1: number; says: string; fix: string }[];
}
interface Kit {
  title: string;
  description: string;
  hashtags: string[];
  cover_url?: string;
  source?: string;
}
const SHAPES = [
  { aspect: "9:16", label: "Vertical", tag: "9x16" },
  { aspect: "16:9", label: "Wide", tag: "16x9" },
  { aspect: "1:1", label: "Square", tag: "1x1" },
];
const shapeOf = (name: string) => SHAPES.find((s) => name.includes(`-${s.tag}-`))?.aspect;

export default function ResultPage() {
  const { id } = useParams();
  const { data: p, refetch, error: projectError } = useProject(id);
  const files = useFetch<ExportFile[]>(id ? `/api/projects/${id}/exports` : null);
  const kit = useFetch<{ kit: Kit | null }>(id ? `/api/projects/${id}/publish` : null);
  const dec = useFetch<{ retakes: Decision[]; tighten: { target: number | null; cuts: Decision[] }; revise: { before: number; after: number; kept: boolean } | null }>(id ? `/api/projects/${id}/decisions` : null);
  const director = useFetch<{ report: { score: number; issues: { scene: string; problem: string }[] } | null; messages: { from: string; text: string }[] }>(id ? `/api/projects/${id}/director` : null);
  const craft = useFetch<CraftReport>(id ? `/api/projects/${id}/craft` : null);
  const [fixing, setFixing] = useState(false);
  const [note, setNote] = useState("");
  const ask = async (text: string) => {
    if (!text.trim()) return;
    try {
      await post(`/api/projects/${id}/director/chat`, { message: text });
      setNote("");
    } catch (e: any) {
      toast(e.message, "err", 8000);
    }
  };
  const { data: themes } = useThemes();
  const restore = async (kind: "retakes" | "tighten") => {
    try {
      await post(`/api/projects/${id}/decisions/restore`, { kind });
      toast("Putting it back and rendering again…");
    } catch (e: any) {
      toast(e.message, "err", 7000);
    }
  };
  const autofix = async () => {
    setFixing(true);
    try {
      await post(`/api/projects/${id}/autofix`, {});
      toast("Applying the suggestions and making a new video…");
    } catch (e: any) {
      toast(e.message, "err", 7000);
    } finally {
      setFixing(false);
    }
  };
  // any job on this video: the first render, another shape, a new look, a request to the director
  const mine = Object.values(useStore(jobsStore)).filter((j) => j.project === id).sort((a, b) => (a.id < b.id ? 1 : -1));
  const job = mine.find((j) => j.kind !== "thumbs" && (j.status === "queued" || j.status === "running")) || null;   // thumbnails are a background chore: they never block this page
  const lastDirector = mine.find((j) => j.kind === "director");
  const lastAutofix = mine.find((j) => j.kind === "autofix");
  useEffect(() => {
    if (lastAutofix?.status === "error") toast(lastAutofix.error || "Could not auto-fix suggestions.", "err", 9000);
    if (lastAutofix?.status === "done") {
      toast("Auto-fix applied successfully!");
      director.refetch();
      craft.refetch();
      files.refetch();
      dec.refetch();
      refetch();
    }
  }, [lastAutofix?.id, lastAutofix?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (lastDirector?.status === "error") toast(lastDirector.error || "The director could not do that.", "err", 9000);
    if (lastDirector?.status === "done") { director.refetch(); craft.refetch(); }
  }, [lastDirector?.id, lastDirector?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  const [looks, setLooks] = useState(false);
  const [redoOpen, setRedoOpen] = useState(false);
  useChanged(id, () => {
    files.refetch();
    kit.refetch();
    dec.refetch();
    director.refetch();
    craft.refetch();
    refetch();
  });
  useEffect(() => {
    if (!job) {
      files.refetch();
      kit.refetch();
    }
  }, [job?.id, job?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const list = files.data || [];
  const main = list.find((f) => shapeOf(f.name) === p?.aspect) || list[0];
  const busy = !!job && (job.status === "running" || job.status === "queued");
  const score = craft.data?.score;
  const things = craft.data?.violations ?? [];
  const hasSuggestions = things.length > 0 || (main?.retention?.risk ?? 0) > 15 || (director.data?.messages ?? []).some(m => m.from === "viewer test") || !!(dec.data?.revise && !dec.data.revise.kept);

  const render = async (aspects: string[]) => {
    try {
      await post(`/api/projects/${id}/export`, { aspects, quality: "looks" });
    } catch (e: any) {
      toast(e.message, "err", 7000);
    }
  };
  const changeLook = async (theme: string) => {
    try {
      await patch(`/api/projects/${id}`, { theme });
      setLooks(false);
      await render([p!.aspect]);
    } catch (e: any) {
      toast(e.message, "err", 7000);
    }
  };

  if (!p) return <div className="page-inner result">
    {projectError ? <div className="card card-pad col" role="alert"><h1>Could not open this video</h1><p>{projectError}</p><div className="row wrap"><button className="btn" onClick={refetch}>Try again</button><Link className="btn ghost" to="/">Back to your videos</Link></div></div> : <div className="row muted" role="status"><Spinner /> Loading your video…</div>}
  </div>;
  return (
    <div className="page-inner result">
      <div className="result-grid">
        <div className="card result-player" data-shape={p.aspect}>
          {main ? (
            <video key={main.url} src={main.url} controls autoPlay muted playsInline poster={kit.data?.kit?.cover_url} aria-label="Your video" />
          ) : (
            <div className="result-empty">
              {(p.cover_url || p.thumb) && <img src={p.cover_url || p.thumb || undefined} alt="" />}
              <span className="result-empty-msg">{busy ? "Rendering…" : "The video has not been rendered yet."}</span>
              {!busy && <button className="btn primary" onClick={() => render([p.aspect])}><Sparkles size={15} /> Render my video</button>}
            </div>
          )}
          {busy && (
            <div className="result-busy">
              <span className="small">{job!.msg || "Working…"}</span>
              <ProgressBar frac={job!.frac} />
            </div>
          )}
        </div>

        <div className="col" style={{ gap: 14 }}>
          <div className="col" style={{ gap: 4 }}>
            <h1 className="bn" style={{ margin: 0 }}>{p.title}</h1>
          </div>

          {main && (
            <a className="btn primary lg" href={main.url} download={main.name}>
              <Download size={16} /> Download
            </a>
          )}
          {id && <details className="result-quality result-disclosure">
            <summary>{craft.error ? "Quality check unavailable" : craft.loading ? "Checking quality…" : score == null ? "Quality check not available yet" : `Quality check: ${score}/100 · ${things.length ? `${things.length} ${things.length === 1 ? "thing" : "things"} to look at` : "Nothing to look at"}`}</summary>
            <div className="col result-disclosure-body">
              {craft.error && <div className="banner warn" role="alert"><span className="grow">{craft.error}</span><button className="btn sm" onClick={craft.refetch}>Try again</button></div>}
              {score != null && <span className="small muted">This score checks the current plan. The automatic checks below check the exported video.</span>}
              {things.map((v, i) => <div key={`${v.rule}-${i}`} className="col result-quality-item"><span className="small"><time>{v.t0.toFixed(1)}s</time> {v.says}</span><span className="small muted">{v.fix}</span></div>)}
              {hasSuggestions && <button className="btn sm" disabled={busy || fixing} onClick={autofix}><Sparkles size={14}/>{fixing ? "Applying suggestions…" : "Auto-fix suggestions"}</button>}
              <QualityCheck pid={id} judges={main?.judges} file={main?.name} onChecked={files.refetch} />
            </div>
          </details>}

          <div className="col result-actions" role="group" aria-label="Change this video">
            <button className="btn magic" onClick={() => setRedoOpen(true)} disabled={busy}><Wand2 size={15} /> Direct again</button>
            <button className="btn" onClick={() => setLooks(!looks)} aria-expanded={looks} disabled={busy}><Palette size={15} /> Change the look</button>
            <Link className="btn" to={`/p/${id}?tab=words`}><PenLine size={15} /> Fix a word</Link>
            <Link className="btn" to={`/p/${id}`}><SlidersHorizontal size={15} /> Edit everything</Link>
          </div>
          {looks && (
            <div className="row wrap" aria-label="Choose a look">
              {(themes || []).filter((th) => !th.name.startsWith("auto-")).slice(0, 8).map((th) => (
                <button key={th.name} className={`theme-item ${p.theme === th.name ? "sel" : ""}`} style={{ margin: 0 }} onClick={() => changeLook(th.name)} disabled={busy}>
                  <span className="swatches">{[th.color.bg, th.color.accent, th.color.accent2, th.color.ink].map((c, i) => <i key={i} style={{ background: c }} />)}</span>
                  <span style={{ fontWeight: 600 }}>{th.label || th.name}</span>
                </button>
              ))}
            </div>
          )}

          <details className="result-disclosure">
          <summary>Other shapes</summary>
          <div className="row wrap result-disclosure-body" aria-label="Other shapes">
            {SHAPES.filter((s) => s.aspect !== p.aspect).map((s) => {
              const f = list.find((x) => shapeOf(x.name) === s.aspect);
              return f ? (
                <a key={s.aspect} className="btn sm" href={f.url} download={f.name}><Download size={13} /> {s.label}</a>
              ) : (
                <button key={s.aspect} className="btn sm" disabled={busy} onClick={() => render([s.aspect])}>Make it {s.label.toLowerCase()} too</button>
              );
            })}
          </div>
          </details>

          <details className="result-disclosure" aria-label="Talk to the director">
            <summary>Talk to the director</summary>
            <div className="col result-disclosure-body" style={{ gap: 10 }}>
            {(director.data?.messages || []).slice(-4).map((m, i) => (
              m.from === "viewer test" ? <ViewerNotes key={i} text={m.text} /> : <span key={i} className={`small bn ${m.from === "director" ? "" : "muted"}`}><span className="who-says">{m.from === "director" ? "Director: " : "You: "}</span>{m.text}</span>
            ))}
            <form className="row" style={{ gap: 6 }} onSubmit={(e) => { e.preventDefault(); ask(note); }}>
              <input className="grow bn" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. make it funnier, less talking" aria-label="Note for the director" disabled={busy} />
              <button className="btn sm primary" disabled={busy || !note.trim()}>Send</button>
            </form>
            {!(director.data?.messages || []).length && (
              <div className="row wrap" style={{ gap: 6 }}>
                {["Make it funnier", "Less talking, more action", "More energy at the start"].map((s) => (
                  <button key={s} className="chip" style={{ cursor: "pointer", border: 0 }} disabled={busy} onClick={() => ask(s)}>{s}</button>
                ))}
              </div>
            )}
            {director.data?.report && director.data.report.issues.length > 0 && (
              <span className="small muted">The editor still notes: {director.data.report.issues[0].scene}: {director.data.report.issues[0].problem}</span>
            )}
            {id && <DirectorLogButton pid={id} label="How this was made" />}
            </div>
          </details>

          {dec.data && (dec.data.retakes.length > 0 || dec.data.tighten.cuts.length > 0 || dec.data.revise) && (
            <details className="result-disclosure" aria-label="What changed in this cut">
              <summary>What changed in this cut</summary>
              <div className="col result-disclosure-body" style={{ gap: 10 }}>
              {dec.data.revise && (
                <div className="col" style={{ gap: 6 }}>
                  <span className="small">
                    {dec.data.revise.kept
                      ? `Watched it back like a viewer and fixed the slow moments.`
                      : `Watched it back and tried a fix for the slow moments, but it was not better, so the first cut stays.`}
                  </span>
                </div>
              )}
              {dec.data.retakes.length > 0 && (
                <div className="col" style={{ gap: 4 }}>
                  <div className="row small">
                    <span className="grow">{dec.data.retakes.length} retake{dec.data.retakes.length === 1 ? "" : "s"} and false start{dec.data.retakes.length === 1 ? "" : "s"}</span>
                    <button className="btn sm ghost" disabled={busy} onClick={() => restore("retakes")}>Put back</button>
                  </div>
                  {dec.data.retakes.slice(0, 4).map((c, i) => <span key={i} className="small muted bn">“{c.text}” · {c.reason}</span>)}
                </div>
              )}
              {dec.data.tighten.cuts.length > 0 && (
                <div className="col" style={{ gap: 4 }}>
                  <div className="row small">
                    <span className="grow">{dec.data.tighten.cuts.length} sentence{dec.data.tighten.cuts.length === 1 ? "" : "s"} dropped to keep it near {Math.round(dec.data.tighten.target || 60)} s</span>
                    <button className="btn sm ghost" disabled={busy} onClick={() => restore("tighten")}>Put back</button>
                  </div>
                  {dec.data.tighten.cuts.slice(0, 4).map((c, i) => <span key={i} className="small muted bn">“{c.text}” · {c.reason}</span>)}
                </div>
              )}
              </div>
            </details>
          )}

          {main && <details className="result-disclosure"><summary>Share this video</summary><div className="col result-disclosure-body" style={{ gap: 14 }}>
          {kit.data?.kit && (
            <div className="card card-pad col" style={{ gap: 10 }}>
              <strong className="small">Ready to post</strong>
              {([["Title", kit.data.kit.title], ["Description", kit.data.kit.description], ["Hashtags", kit.data.kit.hashtags.map((h) => "#" + h).join(" ")]] as [string, string][]).map(([k, v]) => (
                <div key={k} className="row" style={{ alignItems: "flex-start", gap: 8 }}>
                  <div className="col grow" style={{ gap: 2 }}>
                    <span className="small muted">{k}</span>
                    <span className="small bn" style={{ whiteSpace: "pre-wrap" }}>{v}</span>
                  </div>
                  <button className="btn sm icon ghost" aria-label={`Copy ${k.toLowerCase()}`} onClick={() => copyText(v)}><Copy size={13} /></button>
                </div>
              ))}
            </div>
          )}
          <SocialDispatch projectId={id!} videoFilename={main.name} defaultTitle={kit.data?.kit?.title || p.title} defaultDescription={kit.data?.kit?.description || ""} defaultTags={kit.data?.kit?.hashtags || []} />
          </div></details>}
          <Link className="small muted" to={`/p/${id}/export`}>Export settings (quality, frame rate, music level)…</Link>
        </div>
      </div>
      <RedoModal id={id!} title={p.title} open={redoOpen} onClose={() => setRedoOpen(false)} />
    </div>
  );
}

/** The viewer test's findings as a short list, one line for each moment. */
function ViewerNotes({ text }: { text: string }) {
  const body = text.includes(": ") ? text.slice(text.indexOf(": ") + 2) : text;
  const notes = body.split(/;\s+(?=at \d|scene )/).map((n) => n.trim().replace(/\.$/, "")).filter(Boolean);
  return (
    <details className="small muted bn">
      <summary><span className="who-says">Quality check</span> found {notes.length} {notes.length === 1 ? "moment" : "moments"} people may skip</summary>
      <ul className="viewer-notes">
        {notes.map((n, i) => {
          const m = /^at (\d+(?:\.\d+)?)-(\d+(?:\.\d+)?) s: (.*)$/s.exec(n) || /^scene \S+ \(at (\d+(?:\.\d+)?) s\): ()(.*)$/s.exec(n);
          return <li key={i}><time>{m ? `${Number(m[1]).toFixed(0)}s` : ""}</time><span>{m ? m[3] : n}</span></li>;
        })}
      </ul>
    </details>
  );
}
