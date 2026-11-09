import { Globe, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { get, post } from "../api";
import { toast } from "../store";
import { Spinner } from "../ui";
import PrepareComfy from "./PrepareComfy";

/* Every ComfyUI and Ollama on a computer, the card each one runs on, and the picture set that fits it (vt/engines/discover.py, fit.py).
   The person picks one; Video Tool puts the models that fit into that ComfyUI's own folders and uses it. Nothing found is started, stopped or changed. */
interface FitOut { recipe: string | null; label: string; mode: string; card_gb: number; ram_gb: number; why: string; warnings: string[] }
interface Instance {
  engine: "comfy" | "ollama"; url: string; port: number; version: string; local: boolean; public?: string; busy?: boolean; ours?: boolean;
  gpu?: string; vram_gb?: number; size_gb?: number; vram_free_gb?: number; ram_gb?: number; fit?: FitOut; models?: string[];
}
interface Found { host: string; local: boolean; instances: Instance[]; next: { comfy: string; ollama: string } }
interface PlanOut { url: string; recipe: string; label: string; models_dir?:string; model_locations?:string[]; files: { file: string; gb: number; have: boolean; to: string }[]; download_gb: number; problems: string[] }
interface Job { id: string; status: string; frac: number; msg: string; error: string }

export default function FindEngines({ onUsed }: { onUsed: () => void }) {
  const [host, setHost] = useState("");
  const [deep, setDeep] = useState(false);
  const [found, setFound] = useState<Found | null>(null);
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState<PlanOut | null>(null);
  const [job, setJob] = useState<Job | null>(null);

  const scan = async () => {
    setBusy(true); setPlan(null);
    try { setFound(await get<Found>(`/api/discover?host=${encodeURIComponent(host.trim() || "127.0.0.1")}&deep=${deep}`)); }
    catch (e) { toast((e as Error).message, "err"); }
    finally { setBusy(false); }
  };
  useEffect(() => { scan(); }, []);                               // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!job || job.status === "done" || job.status === "error" || job.status === "cancelled") return;
    const t = setInterval(() => get<Job>(`/api/jobs/${job.id}`).then((j) => {
      setJob(j);
      if (j.status === "done") { toast("Ready: pictures are drawn there now"); setPlan(null); onUsed(); scan(); }
      if (j.status === "error") toast(j.error, "err");
    }).catch(() => {}), 1500);
    return () => clearInterval(t);
  }, [job]);                                                      // eslint-disable-line react-hooks/exhaustive-deps

  const choose = async (inst: Instance) => {
    try { setPlan(await get<PlanOut>(`/api/discover/prepare?url=${encodeURIComponent(inst.url)}`)); }
    catch (e) { toast((e as Error).message, "err"); }
  };

  const comfy = (found?.instances ?? []).filter((i) => i.engine === "comfy");
  const ollama = (found?.instances ?? []).filter((i) => i.engine === "ollama");
  const running = job && (job.status === "queued" || job.status === "running");
  return (
    <div className="col" style={{ gap: 10 }} data-testid="find-engines">
      <div className="row wrap" style={{ gap: 8 }}>
        <strong className="grow">Find ComfyUI</strong>
        <input type="text" value={host} onChange={(e) => setHost(e.target.value)} placeholder="This server, or another computer's address" aria-label="Computer to search"
          spellCheck={false} style={{ minWidth: 220 }} onKeyDown={(e) => { if (e.key === "Enter") scan(); }} />
        <label className="small row" style={{ gap: 4 }}><input type="checkbox" checked={deep} onChange={(e) => setDeep(e.target.checked)} /> All ports</label>
        <button className="btn sm" onClick={scan} disabled={busy} data-testid="find">{busy ? <Spinner /> : <><Search size={14} /> Search</>}</button>
      </div>
      {found && !comfy.length && !busy && (
        <p className="small muted" style={{ margin: 0 }} data-testid="none-found">No ComfyUI found on {found.host}{deep ? "" : ". Try All ports"}. Or install one with Set up… under AI programs.</p>
      )}
      {comfy.map((i) => (
        <div key={i.url} className="engine-card" data-instance={i.url}>
          <div className="col grow" style={{ gap: 2, minWidth: 0 }}>
            <strong>{i.gpu || "No graphics card"}{i.size_gb ? ` · ${i.size_gb} GB` : ""}</strong>
            <span className="small muted">ComfyUI {i.version} · {i.url.replace(/^https?:\/\//, "")}{i.ram_gb ? ` · RAM ${Math.round(i.ram_gb)} GB` : ""}{i.busy ? " · busy now" : ""}</span>
            {i.public && <span className="small" style={{ color: "var(--warn)" }}><Globe size={12} style={{ verticalAlign: -2 }} /> Published at {i.public}: other people may be using it.</span>}
            <span className="small">{i.fit?.recipe ? <>Pictures: <strong>{i.fit.label}</strong>. {i.fit.why}.</> : <span style={{ color: "var(--err)" }}>{i.fit?.why}</span>}</span>
            {(i.fit?.warnings ?? []).map((w) => <span key={w} className="small" style={{ color: "var(--warn)" }}>{w}</span>)}
          </div>
          <button className="btn sm" disabled={!i.fit?.recipe || !!running} onClick={() => choose(i)}>Use this one</button>
        </div>
      ))}
      {plan && (
        <div className="card card-pad col" style={{ gap: 6 }} data-testid="prepare-plan">
          <strong>Pictures on {plan.url.replace(/^https?:\/\//, "")}</strong>
          <PrepareComfy url={plan.url} onReady={() => { toast("Ready: pictures are drawn there now"); setPlan(null); onUsed(); scan(); }} />
          <button className="btn sm ghost" style={{ alignSelf: "flex-start" }} onClick={() => setPlan(null)}>Not now</button>
        </div>
      )}
      {ollama.length > 0 && <span className="small muted">Writing AI found: {ollama.map((o) => `Ollama ${o.version} at ${o.url.replace(/^https?:\/\//, "")}`).join(", ")}.</span>}
    </div>
  );
}
