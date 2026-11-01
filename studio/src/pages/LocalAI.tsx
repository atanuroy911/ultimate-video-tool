import { Check, Cpu, RefreshCw, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { get, post, put } from "../api";
import { jobsStore, toast, useStore } from "../store";
import { Field, ProgressBar, Seg, Spinner } from "../ui";

interface LlmStatus {
  llm_mode: "auto" | "off";
  ollama_url: string;
  ollama_model: string;
  llm_auto_download: boolean;
  model: string;
  recommended: string;
  reachable: boolean;
  local: boolean;
  engine_installed: boolean;
  model_ready: boolean;
  gpu_mb: number;
  models: string[];
}

/** The automatic planner: a language model on this computer or on the network (Ollama). Claude is optional on top of it. */
export default function LocalAI() {
  const [st, setSt] = useState<LlmStatus | null>(null);
  const [url, setUrl] = useState("");
  const [testing, setTesting] = useState(false);
  const [busy, setBusy] = useState(false);
  const jobs = useStore(jobsStore);
  const setup = Object.values(jobs).filter((j) => j.kind === "llm").sort((a, b) => (a.id < b.id ? 1 : -1))[0];
  const running = setup && (setup.status === "running" || setup.status === "queued");

  const load = () => get<LlmStatus>("/api/llm/status").then((s) => { setSt(s); setUrl((u) => u || s.ollama_url); }).catch(() => undefined);
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (setup?.status === "done" || setup?.status === "error") load(); }, [setup?.status]);

  const save = async (patch: Record<string, unknown>) => {
    try {
      const cur = await get<Record<string, unknown>>("/api/settings");
      await put("/api/settings", { ...cur, ...patch });
      await load();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      const r = await post<{ ok: boolean; message: string; sample?: string }>("/api/llm/test");
      toast(r.ok ? `The AI answers ${r.sample || ""} · ${r.message}` : r.message, r.ok ? "ok" : "err", 6000);
    } catch (e: any) {
      toast(e.message, "err");
    } finally {
      setTesting(false);
    }
  };

  const install = async () => {
    setBusy(true);
    try {
      await post("/api/llm/setup");
    } catch (e: any) {
      toast(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  if (!st) return null;
  const ready = st.reachable && st.model_ready;
  return (
    <section className="card card-pad col" style={{ gap: 12 }} aria-label="Local AI">
      <div className="row wrap">
        <h2 className="grow"><Cpu size={18} style={{ verticalAlign: -3 }} /> Local AI planner</h2>
        <span className={`chip ${st.llm_mode === "off" ? "" : ready ? "ok" : "warn"}`}>
          {st.llm_mode === "off" ? "Off" : ready ? <><Check size={12} /> Ready · {st.model}</> : st.reachable ? `Model ${st.model} not downloaded` : "Not running"}
        </span>
      </div>
      <p className="muted" style={{ margin: 0 }}>
        Picks the right picture for every word and designs each scene automatically, with no human step and no Claude needed. It runs on a free model through
        Ollama, on this computer or on another one on your network. Your transcript is only ever sent to the address below.
      </p>
      <Seg value={st.llm_mode} onChange={(v) => save({ llm_mode: v })} label="Local AI" options={[{ value: "auto", label: "On (automatic)" }, { value: "off", label: "Off (rules only)" }]} />
      {st.llm_mode === "auto" && (
        <>
          <div className="row wrap" style={{ gap: 12, alignItems: "flex-start" }}>
            <Field label="Ollama address" hint="Another computer on your network works too, e.g. http://192.168.1.20:11434">
              <input type="text" value={url} onChange={(e) => setUrl(e.target.value)} onBlur={() => url !== st.ollama_url && save({ ollama_url: url.trim() })} spellCheck={false} style={{ minWidth: 280 }} />
            </Field>
            <Field label="Model">
              <select value={st.ollama_model} onChange={(e) => save({ ollama_model: e.target.value })}>
                <option value="">Automatic ({st.model})</option>
                {st.models.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </Field>
          </div>
          <div className="row wrap">
            <button className="btn" onClick={load}><RefreshCw size={14} /> Check</button>
            <button className="btn" disabled={!ready || testing} onClick={test}>{testing ? <Spinner /> : <Zap size={14} />} Test</button>
          </div>
          {!ready && st.local && (
            <div className="banner small col" style={{ gap: 8 }}>
              <span>
                {st.engine_installed ? "The local AI engine is installed" : "No local AI engine was found"}
                {st.reachable ? ` but the model “${st.model}” is not downloaded.` : "."}{" "}
                One click sets everything up inside this app's own folder (about {st.engine_installed ? "" : "1.5 GB for the engine plus "}{st.model.includes("7b") ? "5" : "2"} GB for the model, once).
              </span>
              <div className="row"><button className="btn primary" disabled={busy || !!running} onClick={install}>{running ? <Spinner /> : null} Set up the local AI</button></div>
              {running && setup && <><ProgressBar frac={setup.frac ?? 0} /><span className="small muted">{setup.msg}</span></>}
              {setup?.status === "error" && <span className="small" style={{ color: "var(--err)" }}>{setup.error}</span>}
            </div>
          )}
          {!ready && !st.local && <div className="banner warn small">The server at {st.ollama_url} does not answer. Check the address, or that Ollama is running there and allows network access (set OLLAMA_HOST=0.0.0.0).</div>}
          <span className="small muted">{st.gpu_mb ? `Graphics memory here: ${Math.round(st.gpu_mb / 1024)} GB. ` : ""}If it is not available when a video is processed, the app falls back to the built-in rules automatically.</span>
        </>
      )}
    </section>
  );
}
