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
  const { data: p, refetch } = useProject(id);
  const files = useFetch<ExportFile[]>(id ? `/api/projects/${id}/exports` : null);
  const kit = useFetch<{ kit: Kit | null }>(id ? `/api/projects/${id}/publish` : null);
  const dec = useFetch<{ retakes: Decision[]; tighten: { target: number | null; cuts: Decision[] }; revise: { before: number; after: number; kept: boolean } | null }>(id ? `/api/projects/${id}/decisions` : null);
  const director = useFetch<{ report: { score: number; issues: { scene: string; problem: string }[] } | null; messages: { from: string; text: string }[] }>(id ? `/api/projects/${id}/director` : null);
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
    try {
      await post(`/api/projects/${id}/autofix`, {});
      toast("Auto-fixing suggestions and rendering improved cut…");
    } catch (e: any) {
      toast(e.message, "err", 7000);
    }
  };
  // any job on this video: the first render, another shape, a new look, a request to the director
  const mine = Object.values(useStore(jobsStore)).filter((j) => j.project === id).sort((a, b) => (a.id < b.id ? 1 : -1));
  const job = mine.find((j) => j.status === "queued" || j.status === "running") || null;
  const lastDirector = mine.find((j) => j.kind === "director");
  const lastAutofix = mine.find((j) => j.kind === "autofix");
  useEffect(() => {
    if (lastAutofix?.status === "error") toast(lastAutofix.error || "Could not auto-fix suggestions.", "err", 9000);
    if (lastAutofix?.status === "done") {
      toast("Auto-fix applied successfully!");
      director.refetch();
      files.refetch();
      dec.refetch();
      refetch();
    }
  }, [lastAutofix?.id, lastAutofix?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (lastDirector?.status === "error") toast(lastDirector.error || "The director could not do that.", "err", 9000);
    if (lastDirector?.status === "done") director.refetch();
  }, [lastDirector?.id, lastDirector?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  const [looks, setLooks] = useState(false);
  const [redoOpen, setRedoOpen] = useState(false);
  useChanged(id, () => {
    files.refetch();
    kit.refetch();
    dec.refetch();
    director.refetch();
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

  if (!p) return <div className="page-inner"><Spinner /></div>;
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
            {main?.retention && (
              <span className={`small ${main.retention.risk > 35 ? "warn-text" : "muted"}`} role="status">
                {main.retention.verdict}
                {main.retention.risk > 15 && <> <Link to={`/p/${id}`}>Show me</Link></>}
              </span>
            )}
          </div>

          {id && <DirectorLogButton pid={id} label="How this was made" />}
          {main && (
            <a className="btn primary lg" href={main.url} download={main.name}>
              <Download size={16} /> Download
            </a>
          )}
          <div className="row wrap" aria-label="Other shapes">
            {SHAPES.filter((s) => s.aspect !== p.aspect).map((s) => {
              const f = list.find((x) => shapeOf(x.name) === s.aspect);
              return f ? (
                <a key={s.aspect} className="btn sm" href={f.url} download={f.name}><Download size={13} /> {s.label}</a>
              ) : (
                <button key={s.aspect} className="btn sm" disabled={busy} onClick={() => render([s.aspect])}>Make it {s.label.toLowerCase()} too</button>
              );
            })}
          </div>

          {id && <QualityCheck pid={id} judges={main?.judges} file={main?.name} onChecked={files.refetch} />}

          <div className="col result-actions">
            {main?.retention && main.retention.risk > 15 && (
              <button className="btn" onClick={autofix} disabled={busy}><Sparkles size={15} /> Fix the risky moments</button>
            )}
            <button className="btn magic" onClick={() => setRedoOpen(true)} disabled={busy}><Wand2 size={15} /> Redo with AI model</button>
            <button className="btn" onClick={() => setLooks(!looks)} aria-expanded={looks} disabled={busy}><Palette size={15} /> Change the look</button>
            {looks && (
              <div className="row wrap">
                {(themes || []).filter((th) => !th.name.startsWith("auto-")).slice(0, 8).map((th) => (
                  <button key={th.name} className={`theme-item ${p.theme === th.name ? "sel" : ""}`} style={{ margin: 0 }} onClick={() => changeLook(th.name)}>
                    <span className="swatches">{[th.color.bg, th.color.accent, th.color.accent2, th.color.ink].map((c, i) => <i key={i} style={{ background: c }} />)}</span>
                    <span style={{ fontWeight: 600 }}>{th.label || th.name}</span>
                  </button>
                ))}
              </div>
            )}
            <Link className="btn" to={`/p/${id}?tab=words`}><PenLine size={15} /> Fix a word</Link>
            <Link className="btn" to={`/p/${id}`}><SlidersHorizontal size={15} /> Edit everything</Link>
          </div>

          <div className="card card-pad col" style={{ gap: 10 }} aria-label="Talk to the director">
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <strong className="small">Talk to the director</strong>
              {(director.data?.messages || []).some((m) => m.from === "viewer test") && (
                <button className="btn magic sm" onClick={autofix} disabled={busy}><Sparkles size={13} /> Auto-fix suggestions</button>
              )}
            </div>
            {(director.data?.messages || []).slice(-4).map((m, i) => (
              <span key={i} className={`small bn ${m.from === "director" ? "" : "muted"}`}>{m.from === "director" ? "🎬 " : m.from === "person" ? "You: " : "Viewer test: "}{m.text}</span>
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
          </div>

          {dec.data && (dec.data.retakes.length > 0 || dec.data.tighten.cuts.length > 0 || dec.data.revise) && (
            <div className="card card-pad col" style={{ gap: 10 }} aria-label="What the editor did">
              <strong className="small">What the editor did</strong>
              {dec.data.revise && (
                <div className="col" style={{ gap: 6 }}>
                  <span className="small">
                    {dec.data.revise.kept
                      ? `Watched it back like a viewer and fixed the slow moments (risk ${dec.data.revise.before} → ${dec.data.revise.after}).`
                      : `Watched it back and tried a fix for the slow moments, but it was not better, so the first cut stays.`}
                  </span>
                  {!dec.data.revise.kept && (
                    <button className="btn magic sm" onClick={autofix} disabled={busy} style={{ alignSelf: "flex-start" }}>
                      <Sparkles size={13} /> Auto-fix and render improved cut
                    </button>
                  )}
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
          )}

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
          {main && <SocialDispatch projectId={id!} videoFilename={main.name} defaultTitle={kit.data?.kit?.title || p.title} defaultDescription={kit.data?.kit?.description || ""} defaultTags={kit.data?.kit?.hashtags || []} />}
          <Link className="small muted" to={`/p/${id}/export`}>Export settings (quality, frame rate, music level)…</Link>
        </div>
      </div>
      <RedoModal id={id!} title={p.title} open={redoOpen} onClose={() => setRedoOpen(false)} />
    </div>
  );
}
