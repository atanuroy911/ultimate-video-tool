import { CheckCircle2, ClipboardCheck, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { get, post, put } from "../api";
import { Sheet } from "../ds";
import { toast } from "../store";

/* The automatic checks of a finished video and the ten-question rating a person fills in under a minute (docs/TEST-PLAN.md sections 3 and 5). */
export interface Judges {
  passed: boolean;
  failed: string[];
  skipped: string[];
  says: string[];
  at: string;
}
/** What is left to look at in the cut: the director's own plan (what the page still measures wrong after its rounds) or the rules' plan (what the layout guard changed). */
interface LookAt {
  planner: string;
  looked: boolean;
  current: boolean;
  left: { scene: string; number?: number | null; facts: string[] }[];
  changed: { scene: string; number?: number | null; says: string[] }[];
  guard_current: boolean;
}
interface Checklist {
  questions: { id: string; q: string }[];
  answers: Record<string, string>;
  notes: Record<string, string>;
  at: string;
}
const NAMES: Record<string, string> = {
  first_frame: "First frame", nothing_still: "Something new every 3 s", no_glitches: "No flashes or blank frames", duration: "Length", loudness: "Loudness",
  change_on_word: "Pictures change on words", pictures_per_words: "Words per picture", same_design: "One design throughout", audio_sync: "Captions on the words", captions: "Captions readable",
};

export default function QualityCheck({ pid, judges, file, onChecked }: { pid: string; judges: Judges | null | undefined; file?: string; onChecked: () => void }) {
  const [busy, setBusy] = useState(false);
  const [rate, setRate] = useState(false);
  const [look, setLook] = useState<LookAt | null>(null);
  useEffect(() => { get<LookAt>(`/api/projects/${pid}/look-at`).then(setLook).catch(() => setLook(null)); }, [pid, judges]);      // an older server has no such answer: nothing is shown
  const run = async () => {
    setBusy(true);
    try {
      const q = file ? "?name=" + encodeURIComponent(file) : "";
      await post(`/api/projects/${pid}/judge` + q);
      onChecked();
    } catch (e: any) {
      toast(e.message, "err", 7000);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="card card-pad col" style={{ gap: 8 }} aria-label="Quality checks" data-testid="quality">
      <div className="row" style={{ alignItems: "center", gap: 8 }}>
        <strong className="small grow">Quality checks</strong>
        <button className="btn sm ghost" onClick={run} disabled={busy || !file} data-testid="quality-run">{busy ? "Checking…" : judges ? "Check again" : "Check it"}</button>
        <button className="btn sm" onClick={() => setRate(true)} data-testid="quality-rate"><ClipboardCheck size={13} /> Rate it</button>
      </div>
      {judges && (
        <>
          <span className={`small ${judges.passed ? "" : "warn-text"}`} role="status">
            {judges.passed ? <><CheckCircle2 size={13} /> Every automatic check passed.</> : <><ShieldAlert size={13} /> {judges.failed.map((f) => NAMES[f] || f).join(", ")} did not pass.</>}
          </span>
          {judges.says.map((s, i) => <span key={i} className="small muted">{s}</span>)}
        </>
      )}
      {!judges && <span className="small muted">Not checked yet.</span>}
      {look && look.left.length > 0 && (
        <div className="col" style={{ gap: 3 }} data-testid="look-left">
          <span className="small"><strong>Left to look at</strong>{!look.current && " (the plan has changed since the director looked)"}</span>
          {look.left.flatMap((r) => r.facts.map((f, i) => <span key={`${r.scene}-${i}`} className="small muted">Scene {r.number ?? r.scene}: {f}</span>))}
        </div>
      )}
      {look && look.looked && look.current && look.left.length === 0 && <span className="small muted" data-testid="look-none">The director looked at every scene, and nothing is left to fix.</span>}
      {look && look.changed.length > 0 && (
        <div className="col" style={{ gap: 3 }} data-testid="look-changed">
          <span className="small"><strong>Changed by the layout guard</strong>{!look.guard_current && " (the plan has changed since)"}</span>
          {look.changed.map((r) => <span key={r.scene} className="small muted">Scene {r.number ?? r.scene}: {r.says.join("; ")}.</span>)}
          <span className="small muted">The rules planned this video, so the guard hides or shrinks what does not fit. A video an AI directs is never changed this way: the director is told and fixes it.</span>
        </div>
      )}
      {rate && <RateSheet pid={pid} onClose={() => setRate(false)} />}
    </div>
  );
}

function RateSheet({ pid, onClose }: { pid: string; onClose: () => void }) {
  const [c, setC] = useState<Checklist | null>(null);
  useEffect(() => { get<Checklist>(`/api/projects/${pid}/checklist`).then(setC).catch((e) => toast(e.message, "err")); }, [pid]);
  if (!c) return <Sheet title="Rate this video" onClose={onClose}><span className="muted">Loading…</span></Sheet>;
  const set = (id: string, v: string) => setC({ ...c, answers: { ...c.answers, [id]: v } });
  const save = async () => {
    try {
      await put(`/api/projects/${pid}/checklist`, { answers: c.answers, notes: c.notes });
      toast("Saved");
      onClose();
    } catch (e: any) {
      toast(e.message, "err", 7000);
    }
  };
  return (
    <Sheet title="Rate this video" onClose={onClose} footer={<button className="btn primary" onClick={save} data-testid="rate-save">Save</button>}>
      <div className="col" style={{ gap: 14 }}>
        {c.questions.map((q) => (
          <fieldset key={q.id} className="col" style={{ gap: 6, border: 0, padding: 0, margin: 0 }}>
            <legend className="small" style={{ fontWeight: 600 }}>{q.q}</legend>
            <div className="row" style={{ gap: 6 }} role="radiogroup" aria-label={q.q}>
              {["yes", "no"].map((v) => (
                <button key={v} role="radio" aria-checked={c.answers[q.id] === v} className={`btn sm ${c.answers[q.id] === v ? "primary" : ""}`} onClick={() => set(q.id, v)} data-testid={`rate-${q.id}-${v}`}>{v === "yes" ? "Yes" : "No"}</button>
              ))}
            </div>
            {c.answers[q.id] === "no" && (
              <input className="bn" placeholder="One sentence: what is wrong?" aria-label={`What is wrong: ${q.q}`} value={c.notes[q.id] || ""} onChange={(e) => setC({ ...c, notes: { ...c.notes, [q.id]: e.target.value } })} />
            )}
          </fieldset>
        ))}
      </div>
    </Sheet>
  );
}
