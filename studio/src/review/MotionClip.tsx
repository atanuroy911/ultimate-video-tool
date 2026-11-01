import { Clapperboard, Dices, Layers as LayersIcon, RefreshCw, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { get, post } from "../api";
import { useFetch } from "../hooks";
import { jobsStore, toast, useStore } from "../store";
import type { MediaItem } from "../types";
import { Seg, Spinner } from "../ui";

/* Generate motion clip: a still from the media bin becomes a few seconds of silent B-roll made by the ComfyUI server.
   The result lands in the media bin like any other clip (marked "generated"); nothing is placed in the video until the person says so. */
interface ComfyWorkflow { id: string; label: string; status: string; sizes: Record<string, number[]>; fps: number; notes: string; ready?: boolean; problems?: string[] }
interface ComfyStatus { ok: boolean; url: string; error?: string; version?: string; devices?: { name: string; vram_total: number; vram_free: number }[]; queue_running?: number; queue_pending?: number; workflows: ComfyWorkflow[] }
interface ClipRecord { key: string; media: string; source_media?: string | null; prompt: string; seed: number; workflow: string; aspect: string; seconds_taken: number; frames: number }

const SECONDS = [2, 3, 4, 5] as const;
const gigabytes = (bytes: number) => `${Math.round(bytes / 1e9)} GB`;

/** The picture with the clip's window on it: click where the subject is and the window moves there. Same maths as the server's crop_box. */
function Framing({ still, shape, focus, onFocus }: { still: MediaItem; shape: number[]; focus: { x: number; y: number }; onFocus: (x: number, y: number) => void }) {
  const ratio = shape[0] / shape[1];
  const wide = still.width / still.height > ratio;
  const w = wide ? (still.height * ratio) / still.width : 1;                           // window size as fractions of the picture
  const h = wide ? 1 : still.width / ratio / still.height;
  const left = Math.min(Math.max(focus.x - w / 2, 0), 1 - w);
  const top = Math.min(Math.max(focus.y - h / 2, 0), 1 - h);
  return (
    <div className="col" style={{ gap: 4 }}>
      <div role="button" tabIndex={0} aria-label="Click where the subject is" style={{ position: "relative", width: 260, maxWidth: "100%", cursor: "crosshair", overflow: "hidden", borderRadius: 10, lineHeight: 0 }}
        onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); onFocus((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height); }}>
        <img src={still.url} alt="" style={{ width: "100%", display: "block" }} draggable={false} />
        <div style={{ position: "absolute", left: `${left * 100}%`, top: `${top * 100}%`, width: `${w * 100}%`, height: `${h * 100}%`, boxShadow: "0 0 0 999px rgba(0,0,0,.5)", outline: "2px solid #fff", pointerEvents: "none" }} />
      </div>
      <span className="small muted">The bright window is what the clip will show. Click where the subject is.</span>
    </div>
  );
}

export default function MotionClip({ projectId, media, onChange, onAddToTimeline }: { projectId: string; media: MediaItem[]; onChange: () => void; onAddToTimeline?: (m: MediaItem) => void }) {
  const status = useFetch<ComfyStatus>("/api/comfy/status?check=true");
  const clips = useFetch<{ clips: ClipRecord[] }>(`/api/projects/${projectId}/comfy/clips`);
  const jobs = useStore(jobsStore);
  const stills = useMemo(() => media.filter((m) => m.kind === "image"), [media]);
  const [still, setStill] = useState<string>("");
  const [prompt, setPrompt] = useState("");
  const [workflowId, setWorkflowId] = useState("");
  const [aspect, setAspect] = useState<"9:16" | "16:9">("9:16");
  const [seconds, setSeconds] = useState<number>(3);
  const [seed, setSeed] = useState<string>("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [focus, setFocus] = useState<{ x: number; y: number } | null>(null);          // null: the subject the app found

  const workflows = status.data?.workflows ?? [];
  const workflow = workflows.find((w) => w.id === workflowId) ?? workflows.find((w) => w.ready !== false && w.status === "verified") ?? workflows.find((w) => w.ready !== false) ?? workflows[0];
  useEffect(() => {
    if (!still && stills.length) setStill(stills[0].id);
  }, [stills, still]);
  useEffect(() => setFocus(null), [still]);
  const stillItem = stills.find((m) => m.id === still);
  useEffect(() => {
    if (!workflowId && workflow) setWorkflowId(workflow.id);
  }, [workflow, workflowId]);

  const job = jobId ? jobs[jobId] : undefined;
  const working = !!job && (job.status === "queued" || job.status === "running");
  useEffect(() => {
    if (!job) return;
    if (job.status === "done") {
      toast("The clip is in the media bin", "ok", 4000);
      setJobId(null);
      clips.refetch();
      onChange();
    } else if (job.status === "error") {
      toast(job.error || "The clip could not be made", "err", 12000);
      setJobId(null);
    } else if (job.status === "cancelled") {
      setJobId(null);
    }
  }, [job?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = async (useSeed: string, usePrompt: string = prompt, useStill: string = still) => {
    if (!useStill || usePrompt.trim().length < 3 || !workflow) return;
    try {
      const j = await post<{ id: string }>(`/api/projects/${projectId}/comfy/generate`, {
        media_id: useStill, prompt: usePrompt.trim(), workflow: workflow.id, aspect, seconds, seed: useSeed.trim() === "" ? null : Number(useSeed),
        focus_x: useStill === still && focus ? focus.x : null, focus_y: useStill === still && focus ? focus.y : null,
      });
      setJobId(j.id);
    } catch (e: any) {
      toast(e.message, "err", 8000);
    }
  };
  const cancel = () => jobId && post(`/api/jobs/${jobId}/cancel`).catch(() => {});

  if (status.loading && !status.data) return null;
  if (!status.data?.ok) {
    return (
      <div className="group" style={{ gap: 6 }}>
        <h3>Generate motion clip</h3>
        <span className="small muted">ComfyUI is not reachable{status.data?.url ? ` at ${status.data.url}` : ""}. Set its address in Settings to turn pictures into short clips.</span>
      </div>
    );
  }
  const gpu = status.data.devices?.[0];
  const made = (clips.data?.clips ?? []).slice().reverse();
  const mediaById = new Map(media.map((m) => [m.id, m]));

  return (
    <div className="group" style={{ gap: 10 }} aria-label="Generate motion clip">
      <h3><Clapperboard size={15} style={{ verticalAlign: "-2px" }} /> Generate motion clip</h3>
      <p className="small muted" style={{ margin: 0 }}>
        Pick a picture and say what should move. The server makes a few seconds of silent footage; your voice and captions stay as they are.
        {gpu ? ` ${gpu.name.replace(/^cuda:\d+\s*/, "").replace(/\s*:\s*cudaMallocAsync$/, "")}, ${gigabytes(gpu.vram_free)} free` : ""}{status.data.queue_pending ? ` · ${status.data.queue_pending} waiting in its queue` : ""}.
      </p>

      {stills.length === 0 ? (
        <span className="small muted">Add a picture above first: it becomes the first frame of the clip.</span>
      ) : (
        <>
          <div className="row wrap" role="radiogroup" aria-label="First frame" style={{ gap: 8 }}>
            {stills.map((m) => (
              <button key={m.id} type="button" role="radio" aria-checked={still === m.id} className={`tf-choice ${still === m.id ? "sel" : ""}`} style={{ padding: 4, width: 76 }} onClick={() => setStill(m.id)} title={m.caption || m.id}>
                <img src={m.url} alt={m.caption || m.id} style={{ width: "100%", aspectRatio: "1", objectFit: "cover", borderRadius: 8 }} />
              </button>
            ))}
          </div>
          {stillItem && workflow?.sizes[aspect] && <Framing still={stillItem} shape={workflow.sizes[aspect]} focus={focus ?? { x: stillItem.fx ?? 0.5, y: stillItem.fy ?? 0.5 }} onFocus={(x, y) => setFocus({ x, y })} />}
          <textarea rows={2} value={prompt} maxLength={600} onChange={(e) => setPrompt(e.target.value)} aria-label="What should happen" disabled={working}
            placeholder="What moves, and how the camera moves: “the fox trots through the snow, slow push-in”" />
          <div className="row wrap" style={{ gap: 10 }}>
            <label className="field" style={{ minWidth: 170 }}><span>Engine</span>
              <select value={workflow?.id ?? ""} onChange={(e) => setWorkflowId(e.target.value)} disabled={working} aria-label="Engine">
                {workflows.map((w) => <option key={w.id} value={w.id} disabled={w.ready === false}>{w.label}{w.ready === false ? " (not installed)" : w.status !== "verified" ? " (untested)" : ""}</option>)}
              </select>
            </label>
            <Seg value={aspect} onChange={setAspect} label="Shape" options={[{ value: "9:16", label: "Vertical" }, { value: "16:9", label: "Wide" }]} />
            <Seg value={String(seconds)} onChange={(v) => setSeconds(Number(v))} label="Length" options={SECONDS.map((s) => ({ value: String(s), label: `${s} s` }))} />
            <label className="field" style={{ width: 120 }}><span>Seed (optional)</span>
              <input type="number" min={0} value={seed} onChange={(e) => setSeed(e.target.value)} placeholder="random" disabled={working} aria-label="Seed" />
            </label>
          </div>
          {workflow && workflow.ready === false && workflow.problems?.length ? <div className="banner warn small">{workflow.label} cannot run on this server: {workflow.problems[0]}</div> : null}
          <div className="row" style={{ gap: 8 }}>
            {working ? (
              <>
                <button className="btn" disabled><Spinner /> {job?.msg || "Working"}{job && job.frac > 0 ? ` ${Math.round(job.frac * 100)}%` : ""}</button>
                <button className="btn ghost" onClick={cancel}><X size={13} /> Cancel</button>
              </>
            ) : (
              <button className="btn primary" disabled={!still || prompt.trim().length < 3 || !workflow || workflow.ready === false} onClick={() => start(seed)}><Clapperboard size={14} /> Make the clip</button>
            )}
            <span className="small muted">The first clip loads the model and can take several minutes.</span>
          </div>
        </>
      )}

      {made.length > 0 && (
        <div className="col" style={{ gap: 8 }}>
          <span className="small muted" style={{ fontWeight: 600 }}>Made so far</span>
          {made.map((c) => {
            const item = mediaById.get(c.media);
            return (
              <div key={c.key + c.seed} className="row" style={{ gap: 10, alignItems: "flex-start" }}>
                {item ? <video src={item.url} muted loop playsInline controls preload="metadata" style={{ width: 96, borderRadius: 8 }} /> : <div className="muted small" style={{ width: 96 }}>removed</div>}
                <div className="col grow" style={{ gap: 4, minWidth: 0 }}>
                  <span className="small bn" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={c.prompt}>{c.prompt}</span>
                  <span className="small muted">{c.workflow} · {c.aspect} · {c.frames} frames · seed {c.seed} · {Math.round(c.seconds_taken)} s to make</span>
                  <div className="row" style={{ gap: 6 }}>
                    {item && onAddToTimeline && <button className="btn sm" onClick={() => onAddToTimeline(item)}><LayersIcon size={13} /> Use in the video</button>}
                    <button className="btn sm ghost" disabled={working} onClick={() => { const from = c.source_media && mediaById.has(c.source_media) ? c.source_media : still; setPrompt(c.prompt); setSeed(""); setStill(from); start("", c.prompt, from); }} title="The same picture and words, a different random result"><RefreshCw size={13} /> Regenerate</button>
                    <button className="btn sm ghost" disabled={working} onClick={() => { setPrompt(c.prompt); setSeed(String(c.seed)); }} title="Use this seed again to fine-tune the words"><Dices size={13} /> Reuse seed</button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
