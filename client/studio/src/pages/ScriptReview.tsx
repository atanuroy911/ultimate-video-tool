import { ArrowLeft, Bot, ShieldCheck, Check, ChevronDown, ChevronRight, Loader2, MessageSquareText, RotateCcw, Send, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { get, patch, post } from "../api";
import { toast } from "../store";
import "./script-review.css";

/* The director's script, one scene at a time, after the direction is done: the words, what the director chose for them, options you can change by hand,
   a way to send the director a sentence of feedback (one scene or the whole script) and a place to choose among its answers. Approve when it reads right.
   Server: vt/server/script_review_routes.py. */
interface Req { id: string; status: "queued" | "done" | "failed"; hint: string; error: string; alternatives_available: number; scene_id: string | null }
interface Row {
  id: string; number: number; start: number; end: number; narration: string; archetype: string | null; role: string | null; layout: string; transition_in: string;
  transition_effect: string; camera_move: string; elements: string[]; request: Req | null;
}
interface View {
  title: string; status: string; planner: string; director: string; director_used: Record<string, any>; kept_as_recorded: boolean; recording_edit: string; scenes: Row[]; whole_request: Req | null; approved: boolean; approved_at: string;
  rounds: { at: string; scene: string; note: string; request: string }[]; options: { layouts: string[]; transitions: string[] };
}

const LAYOUT_HELP: Record<string, string> = { stack: "Pieces stacked top to bottom", split: "Two halves", hero: "One big piece", grid: "A grid of pieces", side: "Picture beside text", lower: "Content low on the screen", upper: "Content high on the screen" };
const TRANSITION_NAME: Record<string, string> = { cut: "Cut", fade: "Fade", slide_up: "Slide up", slide_left: "Slide left", zoom: "Zoom", wipe: "Wipe", whip: "Whip" };
const QUICK = ["Make it more visual", "Fewer words on screen", "A stronger opening", "Calmer, less busy", "Use bigger numbers", "More variety between scenes"];
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const words = (s: string) => s.replace(/_/g, " ");

function LayoutGlyph({ kind }: { kind: string }) {
  const boxes: Record<string, [number, number, number, number][]> = {
    stack: [[4, 3, 28, 7], [4, 13, 28, 7], [4, 23, 28, 7]], split: [[3, 3, 14, 26], [19, 3, 14, 26]], hero: [[4, 4, 28, 24]], grid: [[3, 3, 14, 11], [19, 3, 14, 11], [3, 17, 14, 11], [19, 17, 14, 11]],
    side: [[3, 4, 15, 24], [20, 6, 13, 6], [20, 16, 13, 6]], lower: [[4, 18, 28, 10], [4, 4, 28, 4]], upper: [[4, 4, 28, 10], [4, 24, 28, 4]],
  };
  return <svg viewBox="0 0 36 32" width="36" height="32" aria-hidden>{(boxes[kind] ?? boxes.stack).map(([x, y, w, h], i) => <rect key={i} x={x} y={y} width={w} height={h} rx="2" fill="currentColor" opacity={i === 0 ? 1 : 0.55} />)}</svg>;
}

interface Preflight { ok: boolean; errors: number; warnings: number; unavailable?: string; issues: { area: string; severity: string; message: string; fix: string; time: number }[] }

/* HyperFrames' own pre-flight over the composition: broken scripts, missing files, text leaving the picture, unreadable text. Runs in a few seconds, before any render. */
function PreflightCard({ pid }: { pid: string }) {
  const [r, setR] = useState<Preflight | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { setR(await get<Preflight>(`/api/projects/${pid}/script-review/render-check`)); }
    catch (e: any) { toast(e.message, "err", 6000); }
    finally { setBusy(false); }
  };
  return (
    <section className="card card-pad sr-pre" aria-labelledby="sr-pre-h">
      <div className="sr-pre-head">
        <h2 id="sr-pre-h"><ShieldCheck size={16} /> Check before making</h2>
        <button type="button" className="btn sm" disabled={busy} onClick={run}>{busy ? <Loader2 size={13} className="spin" /> : <ShieldCheck size={13} />} {r ? "Check again" : "Run the check"}</button>
      </div>
      <p className="muted small">HyperFrames plays the video in a browser for a few seconds and looks for broken parts, text that leaves the picture and text that is hard to read.</p>
      {r?.unavailable && <p className="sr-note">The check could not run here: {r.unavailable}</p>}
      {r && !r.unavailable && (r.issues.length === 0 ? <p className="sr-note ok"><Check size={14} /> Nothing found.</p> : (
        <ul className="sr-issues">
          {r.issues.map((i, k) => <li key={k} className={i.severity}><strong>{i.area}</strong> · {i.time.toFixed?.(1) ?? i.time}s<br />{i.message}{i.fix && <span className="muted small"><br />Fix: {i.fix}</span>}</li>)}
        </ul>
      ))}
    </section>
  );
}

function Answers({ pid, req, onApplied }: { pid: string; req: Req; onApplied: () => void }) {
  const [alts, setAlts] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { get<any[]>(`/api/projects/${pid}/requests/${req.id}/alternatives`).then(setAlts).catch(() => setAlts([])); }, [pid, req.id]);
  if (alts === null) return <p className="sr-note"><Loader2 size={14} className="spin" /> Loading the director’s answers…</p>;
  if (!alts.length) return <p className="sr-note">The director answered, but there is nothing to choose between.</p>;
  const apply = async (i: number) => {
    setBusy(true);
    try { await post(`/api/projects/${pid}/requests/${req.id}/apply`, { index: i }); toast("Scene updated.", "ok", 2500); onApplied(); }
    catch (e: any) { toast(e.errors?.join(" · ") || e.message, "err", 7000); }
    finally { setBusy(false); }
  };
  return (
    <div className="sr-answers" role="group" aria-label="The director's answers">
      <strong>The director suggests {alts.length === 1 ? "one change" : `${alts.length} options`}</strong>
      <div className="sr-alts">
        {alts.map((a, i) => (
          <article key={i} className="sr-alt">
            <header>Option {i + 1}<span className="muted small">{a.archetype ? words(a.archetype) : a.layout}</span></header>
            <ul>{(a.elements ?? []).slice(0, 5).map((e: any, j: number) => <li key={j}>{words(String(e.type))}{e.text || e.title || e.value ? `: ${String(e.text || e.title || e.value).slice(0, 48)}` : ""}</li>)}</ul>
            <button type="button" className="btn sm primary" disabled={busy} onClick={() => apply(i)}><Check size={13} /> Use this</button>
          </article>
        ))}
      </div>
    </div>
  );
}

function Ask({ placeholder, onSend, busy }: { placeholder: string; onSend: (note: string) => void; busy: boolean }) {
  const [note, setNote] = useState("");
  const send = () => { if (note.trim()) { onSend(note.trim()); setNote(""); } };
  return (
    <div className="sr-ask">
      <input value={note} placeholder={placeholder} aria-label={placeholder} onChange={(e) => setNote(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") send(); }} />
      <button type="button" className="btn sm" disabled={busy || !note.trim()} onClick={send}>{busy ? <Loader2 size={13} className="spin" /> : <Send size={13} />} Ask</button>
    </div>
  );
}

export default function ScriptReviewPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [v, setV] = useState<View | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState("");
  const timer = useRef<number | undefined>(undefined);

  const load = () => get<View>(`/api/projects/${id}/script-review`).then((d) => { setV(d); setError(""); }).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [id]);        // eslint-disable-line react-hooks/exhaustive-deps
  const waiting = !!v && (v.whole_request?.status === "queued" || v.scenes.some((s) => s.request?.status === "queued"));
  useEffect(() => {                                     // the director answers on its own time: look again while a question is open
    window.clearInterval(timer.current);
    if (waiting) timer.current = window.setInterval(() => { if (!document.hidden) load(); }, 3000);
    return () => window.clearInterval(timer.current);
  }, [waiting, id]);        // eslint-disable-line react-hooks/exhaustive-deps

  const ask = async (note: string, scene?: string) => {
    setBusy(scene ?? "*");
    try { setV(await post<View>(`/api/projects/${id}/script-review/ask`, { note, scene_id: scene ?? null, alternatives: 2 })); if (scene) setOpen((o) => ({ ...o, [scene]: true })); }
    catch (e: any) { toast(e.message, "err", 7000); }
    finally { setBusy(""); }
  };
  const change = async (sid: string, body: Record<string, unknown>) => {
    try { await patch(`/api/projects/${id}/scenes/${sid}`, body); await load(); }
    catch (e: any) { toast(e.errors?.join(" · ") || e.message, "err", 7000); }
  };
  const addGraphics = async () => {
    setBusy("graphics");
    try { await post(`/api/projects/${id}/script-review/add-graphics`); toast("The director is planning titles and callouts.", "ok", 3500); nav(`/p/${id}/progress`); }
    catch (e: any) { toast(e.message, "err", 7000); }
    finally { setBusy(""); }
  };
  const approve = async () => {
    setBusy("approve");
    try { await post(`/api/projects/${id}/script-review/approve`); toast("Script approved.", "ok", 2500); nav(`/p/${id}`); }
    catch (e: any) { toast(e.message, "err", 7000); }
    finally { setBusy(""); }
  };

  if (error) return <div className="page-inner"><p role="alert">{error}</p><Link className="btn" to={`/p/${id}`}>Back to the video</Link></div>;
  if (!v) return <div className="page-inner"><p className="muted"><Loader2 size={14} className="spin" /> Reading the director’s script…</p></div>;
  const rounds = v.rounds.length;

  return (
    <div className="page-inner sr" style={{ maxWidth: 920 }}>
      <Link className="btn ghost" style={{ alignSelf: "flex-start" }} to={`/p/${id}`}><ArrowLeft size={15} /> Back to the video</Link>
      <header className="sr-head">
        <div>
          <h1>Director’s script</h1>
          <p className="muted">{v.title} · {v.scenes.length} scenes · planned by {v.planner === "rules" ? "the built-in director" : v.planner}</p>
        </div>
        <span className={`sr-state ${v.approved ? "ok" : ""}`}>{v.approved ? <><Check size={13} /> Approved</> : waiting ? <><Loader2 size={13} className="spin" /> Director is answering</> : "In review"}</span>
      </header>

      {v.kept_as_recorded && (
        <section className="card card-pad sr-kept" aria-labelledby="sr-kept-h">
          <h2 id="sr-kept-h"><ShieldCheck size={16} /> Your recording is kept exactly as recorded</h2>
          <p className="muted small">This video was set to “Keep my video”, so the director has nothing to plan: the picture and pauses stay as they are, and only captions and music are added. That is why there is one scene below and no director was asked.</p>
          <div className="row"><button type="button" className="btn primary" disabled={!!busy} onClick={addGraphics}>{busy === "graphics" ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />} Let the director add titles and callouts</button><span className="muted small">The picture stays whole; the director adds text on top where it helps, and you review it here.</span></div>
        </section>
      )}
      {!v.kept_as_recorded && (
      <section className="card card-pad sr-whole" aria-labelledby="sr-whole-h">
        <h2 id="sr-whole-h"><Bot size={16} /> Tell the director what to change</h2>
        <p className="muted small">Describe the whole script in a sentence. The director plans the scenes again and sends back options to choose from. {rounds ? `${rounds} round${rounds > 1 ? "s" : ""} so far.` : ""}</p>
        <div className="sr-quick">{QUICK.map((q) => <button key={q} type="button" className="chip" disabled={!!busy} onClick={() => ask(q)}>{q}</button>)}</div>
        <Ask placeholder="Or write your own, e.g. “open with the number, then explain”" busy={busy === "*"} onSend={(n) => ask(n)} />
        {v.whole_request?.status === "queued" && <p className="sr-note"><Loader2 size={14} className="spin" /> Waiting for the director: “{v.whole_request.hint}”</p>}
        {v.whole_request?.status === "failed" && <p className="sr-note bad">The director could not do that: {v.whole_request.error || "no reason given"}.</p>}
        {v.whole_request?.status === "done" && <p className="sr-note ok"><Sparkles size={14} /> The director answered. Open the scenes below to see what it suggests.</p>}
      </section>
      )}

      <ol className="sr-list">
        {v.scenes.map((s) => {
          const isOpen = !!open[s.id] || s.request?.status === "done";
          return (
            <li key={s.id} className={`sr-scene${isOpen ? " open" : ""}`}>
              <button type="button" className="sr-scene-head" aria-expanded={isOpen} onClick={() => setOpen((o) => ({ ...o, [s.id]: !isOpen }))}>
                <span className="sr-num">{s.number}</span>
                <span className="sr-time">{mmss(s.start)}–{mmss(s.end)}</span>
                <span className="sr-say">“{s.narration || "(no words: a visual-only scene)"}”</span>
                <span className="sr-tags">{s.archetype && <i>{words(s.archetype)}</i>}{s.role && s.role !== s.archetype && <i className="role">{words(s.role)}</i>}</span>
                {s.request?.status === "queued" ? <Loader2 size={15} className="spin" aria-label="The director is answering" /> : s.request?.status === "done" ? <Sparkles size={15} aria-label="The director has answers" /> : null}
                {isOpen ? <ChevronDown size={16} aria-hidden /> : <ChevronRight size={16} aria-hidden />}
              </button>
              {isOpen && (
                <div className="sr-body">
                  <div className="sr-block">
                    <h3>On screen</h3>
                    {s.elements.length ? <ul className="sr-els">{s.elements.map((e, i) => <li key={i}>{words(e)}</li>)}</ul> : <p className="muted small">Nothing but the captions.</p>}
                  </div>
                  <div className="sr-block">
                    <h3>Layout</h3>
                    <div className="sr-opts" role="radiogroup" aria-label={`Layout of scene ${s.number}`}>
                      {v.options.layouts.map((l) => (
                        <button key={l} type="button" role="radio" aria-checked={s.layout === l} className={`sr-opt${s.layout === l ? " sel" : ""}`} title={LAYOUT_HELP[l]} onClick={() => s.layout !== l && change(s.id, { layout: l })}>
                          <LayoutGlyph kind={l} /><span>{l}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="sr-block">
                    <h3>How it begins</h3>
                    <div className="sr-opts" role="radiogroup" aria-label={`Transition into scene ${s.number}`}>
                      {v.options.transitions.map((t) => (
                        <button key={t} type="button" role="radio" aria-checked={s.transition_in === t} className={`sr-opt text${s.transition_in === t ? " sel" : ""}`} onClick={() => s.transition_in !== t && change(s.id, { transition_in: t })}>{TRANSITION_NAME[t]}</button>
                      ))}
                    </div>
                  </div>
                  <div className="sr-block wide">
                    <h3><MessageSquareText size={14} /> Ask the director about this scene</h3>
                    <Ask placeholder="e.g. show this as a chart, or make it a quote" busy={busy === s.id} onSend={(n) => ask(n, s.id)} />
                    {s.request?.status === "queued" && <p className="sr-note"><Loader2 size={14} className="spin" /> Waiting for the director: “{s.request.hint}”</p>}
                    {s.request?.status === "failed" && <p className="sr-note bad">The director could not do that: {s.request.error || "no reason given"}.</p>}
                    {s.request?.status === "done" && s.request.alternatives_available > 0 && <Answers pid={id} req={s.request} onApplied={load} />}
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ol>

      <PreflightCard pid={id} />

      {rounds > 0 && (
        <details className="card card-pad sr-history">
          <summary>History of your feedback ({rounds})</summary>
          <ol>{[...v.rounds].reverse().map((r) => <li key={r.request}><span className="muted small">{new Date(r.at).toLocaleTimeString()}</span> {r.scene ? `Scene ${v.scenes.find((s) => s.id === r.scene)?.number ?? r.scene}` : "Whole script"}: “{r.note}”</li>)}</ol>
        </details>
      )}

      <div className="sr-bar">
        <span className="muted small">{v.approved ? "You approved this script." : "Happy with it? Approve and continue in the editor."}</span>
        <span className="grow" />
        {v.approved && <button type="button" className="btn ghost" onClick={() => post(`/api/projects/${id}/script-review/reopen`).then(load)}><RotateCcw size={14} /> Reopen</button>}
        <button type="button" className="btn primary" disabled={busy === "approve" || waiting} onClick={approve}>{busy === "approve" ? <Loader2 size={14} className="spin" /> : <Check size={14} />} Approve and open the editor</button>
      </div>
    </div>
  );
}
