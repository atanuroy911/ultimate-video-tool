import { Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { get, post } from "../api";
import { useT } from "../i18n";
import { toast } from "../store";

/* A weak opening ("Hi everyone, welcome back...") gets up to two better ones to choose from. Nothing changes unless the person picks one. */
interface Proposal { id: string; why: string; kind: string; script: string }

export default function HookCard({ pid, onApplied }: { pid: string; onApplied: () => void }) {
  const t = useT();
  const [d, setD] = useState<{ weak: boolean; first: string; proposals: Proposal[] } | null>(null);
  useEffect(() => { get<typeof d>(`/api/projects/${pid}/hook?ai=false`).then(setD).catch(() => setD(null)); }, [pid]);
  if (!d || !d.weak || !d.proposals.length) return null;
  const apply = (p: Proposal) => post(`/api/projects/${pid}/hook/apply`, { script: p.script }).then(() => { toast(t("ed.hook.making"), "ok"); onApplied(); }).catch((e) => toast(e.errors?.[0] || e.message, "err", 8000));
  return (
    <div className="card card-pad col" style={{ gap: 8 }} data-testid="hook-card">
      <strong className="small"><Sparkles size={13} /> {t("ed.hook.title")}</strong>
      <span className="small muted bn">{t("ed.hook.now")}: “{d.first}”</span>
      {d.proposals.map((p) => (
        <div key={p.id} className="col" style={{ gap: 4 }}>
          <span className="small">{p.why}</span>
          <span className="small muted bn">“{p.script.split(/(?<=[.!?])\s+/)[0]}”</span>
          <button className="btn sm" onClick={() => apply(p)}>{t("ed.hook.use")}</button>
        </div>
      ))}
    </div>
  );
}
