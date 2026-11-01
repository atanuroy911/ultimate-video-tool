import { Check, Clapperboard, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { get, put } from "../api";
import { useFetch } from "../hooks";
import { toast } from "../store";
import { Field, Spinner } from "../ui";

/* Settings → ComfyUI: where the video-generation server is, whether it answers, what GPU it has, and which engines can run there. */
interface ComfyWorkflow { id: string; label: string; status: string; ready?: boolean; problems?: string[]; notes: string }
interface ComfyStatus { ok: boolean; url: string; error?: string; version?: string; devices?: { name: string; vram_total: number; vram_free: number }[]; queue_running?: number; queue_pending?: number; workflows: ComfyWorkflow[] }

export default function ComfySettings() {
  const status = useFetch<ComfyStatus>("/api/comfy/status?check=true");
  const [address, setAddress] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (status.data?.url && !address) setAddress(status.data.url);
  }, [status.data?.url]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async () => {
    if (!address.trim() || address.trim() === status.data?.url) return;
    setSaving(true);
    try {
      const current = await get<Record<string, unknown>>("/api/settings");
      await put("/api/settings", { ...current, comfy_url: address.trim() });
      status.refetch();
    } catch (e: any) {
      toast(e.message, "err");
    } finally {
      setSaving(false);
    }
  };

  const data = status.data;
  const gpu = data?.devices?.[0];
  return (
    <section className="card card-pad col" style={{ gap: 12 }} aria-label="ComfyUI">
      <div className="row wrap">
        <h2 className="grow"><Clapperboard size={18} style={{ verticalAlign: -3 }} /> Video generation (ComfyUI)</h2>
        {status.loading && !data ? <Spinner /> : <span className={`chip ${data?.ok ? "ok" : "warn"}`}>{data?.ok ? <><Check size={12} /> Connected{data.version ? ` · ${data.version}` : ""}</> : "Not reachable"}</span>}
      </div>
      <p className="muted" style={{ margin: 0 }}>
        Turns a picture into a few seconds of silent motion footage on a ComfyUI server, for the media bin. Your voice, captions and the rest of the video stay yours.
        Only the picture and the words you type are sent to the address below.
      </p>
      <div className="row wrap" style={{ gap: 12, alignItems: "flex-end" }}>
        <Field label="ComfyUI address" hint="Another computer on your network, e.g. http://192.168.1.20:8188">
          <input type="text" value={address} onChange={(e) => setAddress(e.target.value)} onBlur={save} onKeyDown={(e) => e.key === "Enter" && save()} spellCheck={false} style={{ minWidth: 300 }} aria-label="ComfyUI address" />
        </Field>
        <button className="btn" disabled={saving || status.loading} onClick={() => status.refetch()}>{saving || status.loading ? <Spinner /> : <RefreshCw size={14} />} Check again</button>
      </div>
      {data && !data.ok && <div className="banner warn small">{data.error}</div>}
      {data?.ok && (
        <>
          <span className="small muted">
            {gpu ? `${gpu.name.replace(/^cuda:\d+\s*/, "").replace(/\s*:\s*cudaMallocAsync$/, "")} · ${Math.round(gpu.vram_free / 1e9)} of ${Math.round(gpu.vram_total / 1e9)} GB free` : "No GPU reported"} · {data.queue_running ?? 0} running, {data.queue_pending ?? 0} waiting
          </span>
          <div className="col" style={{ gap: 6 }}>
            {data.workflows.map((w) => (
              <div key={w.id} className="row" style={{ gap: 8 }}>
                <strong>{w.label}</strong>
                <span className={`chip ${w.ready === false ? "warn" : w.status === "verified" ? "ok" : ""}`}>{w.ready === false ? "Not installed" : w.status === "verified" ? "Tested" : "Untested"}</span>
                <span className="small muted grow">{w.ready === false ? w.problems?.[0] : w.notes}</span>
              </div>
            ))}
            {data.workflows.length === 0 && <span className="small muted">No engines are set up yet.</span>}
          </div>
        </>
      )}
    </section>
  );
}
