import { Cpu, Pause, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { get } from "../api";
import { useT } from "../i18n";

/* How busy the computer that does the work is: processor, memory, disk, every graphics card, which one Video Tool uses and what is running on each
   (server vt/sysstats.py, GET /api/system/stats; the same numbers as `vt system`). It is the selected processing server's computer, or this computer when
   everything is installed here. One shared poll serves the sidebar and the page. Live data follows three rules: it says how old it is, it can be paused,
   and it stops asking while the window is hidden. */
interface Program { pid: number; label: string; gb: number; percent?: number | null; ours: boolean }
interface Gpu {
  index: number; name: string; percent: number | null; memory_percent: number | null; memory_used_gb: number; memory_total_gb: number;
  temperature_c: number | null; power_w: number | null; power_limit_w: number | null; clock_mhz: number | null; usable_by_video_tool: boolean; programs: Program[];
}
export interface SystemStats {
  host: { name: string; os: string };
  cpu: { model: string; cores: number; percent: number | null; video_tool_percent: number | null };
  memory: { total_gb: number | null; used_gb: number | null; available_gb: number | null; percent: number | null; swap_total_gb: number | null; swap_used_gb: number | null; video_tool_gb: number | null };
  disk: { path: string; total_gb: number | null; free_gb: number | null; percent: number | null };
  gpus: Gpu[];
  engines: {
    comfy?: { ok: boolean; gpus?: { name: string; vram_free_gb: number | null; vram_total_gb: number | null }[]; why?: string };
    ollama?: { ok: boolean; loaded?: { model: string; gb_on_card: number | null }[]; why?: string };
  };
  assignment?: { render?: number | null; speech?: number | null };
  needs_gpu_choice?: boolean;
  summary: { gpus_video_tool_can_use: string[]; gpu_in_use: string[]; busy_with_other_programs?: string[] };
}

type Reading = { stats: SystemStats | null; failed: boolean; at: number };
const listeners = new Set<(r: Reading) => void>();
let latest: Reading = { stats: null, failed: false, at: 0 };
let timer: number | undefined;
let paused = false;

function tick() {
  if (document.hidden || paused) return;                           // nothing to show, or the person paused it: do not ask
  get<SystemStats>("/api/system/stats")
    .then((stats) => { if (!stats || !Array.isArray(stats.gpus) || !stats.summary || !stats.engines) throw new Error("not a reading"); latest = { stats, failed: false, at: Date.now() }; listeners.forEach((l) => l(latest)); })      // an answer that is not a reading is treated like no answer
    .catch(() => { latest = { stats: latest.stats, failed: true, at: latest.at }; listeners.forEach((l) => l(latest)); });     // an older server has no such route
}
export function setSystemPaused(p: boolean) { paused = p; if (!p) tick(); }

/** The latest numbers, refreshed every 2 seconds while the page is visible; `failed` when the server cannot give them (an older server). */
export function useSystemReading(): Reading {
  const [r, setR] = useState<Reading>(latest);
  useEffect(() => {
    listeners.add(setR);
    if (timer === undefined) { tick(); timer = window.setInterval(tick, 2000); }
    return () => { listeners.delete(setR); if (!listeners.size && timer !== undefined) { window.clearInterval(timer); timer = undefined; } };
  }, []);
  return r;
}
export const useSystemStats = (): SystemStats | null => useSystemReading().stats;

const pct = (n: number | null | undefined) => (n == null ? "-" : `${Math.round(n)}%`);
const level = (n: number | null | undefined) => (n == null ? "var(--accent)" : n >= 90 ? "var(--err)" : n >= 75 ? "var(--warn)" : "var(--accent)");

function Meter({ value, label }: { value: number | null | undefined; label: string }) {
  return (
    <div className="bar" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value ?? 0)} style={{ flex: 1, minWidth: 80 }}>
      <i style={{ width: `${Math.max(0, Math.min(100, value ?? 0))}%`, background: level(value) }} />
    </div>
  );
}

function Line({ label, value, detail, note }: { label: string; value: number | null | undefined; detail: string; note?: string }) {
  return (
    <div className="col" style={{ gap: 3 }}>
      <div className="row" style={{ gap: 10, alignItems: "center" }}>
        <strong style={{ width: 84 }}>{label}</strong>
        <Meter value={value} label={label} />
        <span style={{ width: 44, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{pct(value)}</span>
      </div>
      <span className="small muted" style={{ marginLeft: 94 }}>{detail}{note ? ` · ${note}` : ""}</span>
    </div>
  );
}

/** The sidebar's status dot: the server answers (green) or cannot report (amber). */
export function ServerDot() {
  const { stats, failed } = useSystemReading();
  const cls = stats && !failed ? "ok" : failed ? "warn" : "";
  return <span className={`dot ${cls}`} aria-hidden style={{ marginLeft: 6 }} />;
}

/** A small dot on the Server item while two or more graphics cards still wait for the person's choice (never a banner). Read from the numbers the page already polls. */
export function ChoiceDot({ className = "" }: { className?: string }) {
  const t = useT();
  const waiting = !!useSystemReading().stats?.needs_gpu_choice;
  return waiting ? <span className={`choice-dot ${className}`} data-testid="gpu-choice-dot" role="img" aria-label={t("nav.server.choice")} /> : null;
}

/** A compact line for the sidebar: GPU, processor and memory at a glance. Opens the Server page when pressed. */
export function SystemPill() {
  const s = useSystemStats();
  const nav = useNavigate();
  if (!s) return null;
  const busiest = s.gpus.find((g) => g.index === s.assignment?.render) ?? s.gpus.filter((g) => g.usable_by_video_tool).sort((a, b) => (b.percent ?? 0) - (a.percent ?? 0))[0] ?? s.gpus[0];   // the card Video Tool renders on
  const text = [busiest ? `GPU ${pct(busiest.percent)}` : null, `CPU ${pct(s.cpu.percent)}`, `RAM ${pct(s.memory.percent)}`].filter(Boolean).join(" · ");
  const title = `${s.host.name}: ${s.cpu.model}, ${s.memory.used_gb} of ${s.memory.total_gb} GB memory${busiest ? `, ${busiest.name} (${busiest.memory_used_gb} of ${busiest.memory_total_gb} GB)` : ""}. Press for details.`;
  return (
    <button className="pill sys-pill" style={{ cursor: "pointer" }} onClick={() => nav("/server")} title={title} aria-label={`${s.host.name}: ${text}. Open the Server page.`} data-testid="system-pill">
      <Cpu size={13} aria-hidden /> <span className="hide-sm sys-stats" aria-hidden>{[busiest ? ["GPU", busiest.percent] as const : null, ["CPU", s.cpu.percent] as const, ["RAM", s.memory.percent] as const].filter((x) => !!x).map((x) => <span key={x![0]}><b>{pct(x![1])}</b><small>{x![0]}</small></span>)}</span>
    </button>
  );
}

/** The full panel: every number, which card Video Tool uses and what is on each one. */
export default function SystemPanel() {
  const { stats: s, failed, at } = useSystemReading();
  const [pausedHere, setPausedHere] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [said, setSaid] = useState("");
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t); }, []);
  useEffect(() => { setSystemPaused(pausedHere); return () => setSystemPaused(false); }, [pausedHere]);
  const busy = s ? s.summary.gpu_in_use.slice().sort().join(", ") : "";
  useEffect(() => { if (s) setSaid(busy ? `Video Tool is using ${busy}.` : "Video Tool is not using a graphics card right now."); }, [busy, !!s]);          // one calm sentence, only when it changes

  if (!s) {
    return (
      <section className="card card-pad col" style={{ gap: 8 }} aria-label="Activity" data-testid="system-panel">
        <h2><Cpu size={18} style={{ verticalAlign: -3 }} /> System</h2>
        <p className="small muted" style={{ margin: 0 }} data-testid="system-note">
          {failed ? "This server cannot report how busy it is yet. Update the server to see its processor, memory and graphics-card numbers here." : "Reading this computer's numbers…"}
        </p>
      </section>
    );
  }
  const ago = at ? Math.max(0, Math.round((now - at) / 1000)) : null;
  const stale = !pausedHere && (failed || (ago != null && ago > 10));
  const using = s.summary.gpu_in_use.length ? s.summary.gpu_in_use.join(" and ") : null;
  const usable = s.summary.gpus_video_tool_can_use;
  return (
    <section className="card card-pad col" style={{ gap: 14 }} aria-label="Activity" data-testid="system-panel">
      <div className="row wrap" style={{ gap: 8, alignItems: "center" }}>
        <h2 className="grow"><Cpu size={18} style={{ verticalAlign: -3 }} /> Activity</h2>
        <span className={`small ${stale ? "" : "muted"}`} style={stale ? { color: "var(--warn)" } : undefined} data-testid="system-age">
          {pausedHere ? "Paused" : stale ? `No update for ${ago ?? "?"} s` : "Live"}
        </span>
        <button className="btn sm" onClick={() => setPausedHere((p) => !p)} aria-pressed={pausedHere} style={{ minHeight: 44, minWidth: 44 }}>
          {pausedHere ? <><Play size={13} aria-hidden /> Resume</> : <><Pause size={13} aria-hidden /> Pause</>}
        </button>
      </div>
      <p className="small" style={{ margin: 0 }} data-testid="system-summary">
        {s.host.name} · {s.host.os}. {usable.length ? <>{using ? <>Working on <strong>{using}</strong>.</> : "Idle."}{(s.summary.busy_with_other_programs || []).length ? <> Other programs are using <strong>{(s.summary.busy_with_other_programs || []).join(" and ")}</strong>.</> : ""}</> : "Video Tool uses the processor: it may not use any graphics card."}
      </p>
      <Line label="Processor" value={s.cpu.percent} detail={`${s.cpu.model}, ${s.cpu.cores} threads`} note={s.cpu.video_tool_percent != null ? `Video Tool ${pct(s.cpu.video_tool_percent)}` : undefined} />
      <Line label="Memory" value={s.memory.percent} detail={`${s.memory.used_gb} of ${s.memory.total_gb} GB used, ${s.memory.available_gb} GB free`}
        note={[s.memory.video_tool_gb != null ? `Video Tool ${s.memory.video_tool_gb} GB` : "", s.memory.swap_total_gb ? `swap ${s.memory.swap_used_gb}/${s.memory.swap_total_gb} GB` : ""].filter(Boolean).join(" · ") || undefined} />
      <Line label="Disk" value={s.disk.percent} detail={`${s.disk.free_gb} GB free of ${s.disk.total_gb} GB`} note={s.disk.path} />
      {s.gpus.map((g) => (
        <div key={g.index} className="col" style={{ gap: 6, paddingTop: 10, borderTop: "1px solid var(--line, rgba(128,128,128,.2))" }} data-gpu={g.index}>
          <div className="row wrap" style={{ gap: 8, alignItems: "center" }}>
            <h3 className="grow" style={{ margin: 0, fontSize: 15, textTransform: "none", letterSpacing: 0 }}>{g.name}</h3>
            {s.assignment?.render === g.index && <span className="chip accent">Renders videos</span>}
            {s.assignment?.speech === g.index && <span className="chip accent">Transcribes speech</span>}
            {!g.usable_by_video_tool && <span className="chip">Not used by Video Tool</span>}
          </div>
          <Line label="In use" value={g.percent} detail={[g.temperature_c != null ? `${Math.round(g.temperature_c)} °C` : "", g.power_w != null ? `${Math.round(g.power_w)}${g.power_limit_w ? ` of ${Math.round(g.power_limit_w)}` : ""} W` : "", g.clock_mhz != null ? `${Math.round(g.clock_mhz)} MHz` : ""].filter(Boolean).join(" · ") || "graphics card"} />
          <Line label="Memory" value={g.memory_total_gb ? (g.memory_used_gb / g.memory_total_gb) * 100 : null} detail={`${g.memory_used_gb} of ${g.memory_total_gb} GB`} />
          {g.programs.length > 0 && (
            <div className="row wrap" style={{ gap: 6, marginLeft: 94 }}>
              {g.programs.map((p) => <span key={p.pid} className={`chip ${p.ours ? "accent" : ""}`} title={`process ${p.pid}`}>{p.label} · {p.gb} GB{p.percent != null ? ` · ${Math.round(p.percent)}%` : ""}</span>)}
            </div>
          )}
        </div>
      ))}
      {(s.engines.comfy || s.engines.ollama) && (
        <div className="col" style={{ gap: 4, paddingTop: 10, borderTop: "1px solid var(--line, rgba(128,128,128,.2))" }}>
          <h3 style={{ margin: 0, fontSize: 15, textTransform: "none", letterSpacing: 0 }}>AI programs</h3>
          {s.engines.comfy && <span className="small">Pictures (ComfyUI): {s.engines.comfy.ok ? <>draws on <strong>{(s.engines.comfy.gpus || []).map((x) => `${x.name}${x.vram_free_gb != null ? ` (${x.vram_free_gb} GB free)` : ""}`).join(", ") || "the processor"}</strong></> : <span style={{ color: "var(--err)" }}>not answering</span>}</span>}
          {s.engines.ollama && <span className="small">Writing AI (Ollama): {s.engines.ollama.ok ? ((s.engines.ollama.loaded || []).length ? (s.engines.ollama.loaded || []).map((m) => `${m.model}${m.gb_on_card != null ? ` (${m.gb_on_card} GB on the card)` : ""}`).join(", ") : "nothing loaded right now") : <span style={{ color: "var(--err)" }}>not answering</span>}</span>}
        </div>
      )}
      <p className="sr-only" role="status" aria-atomic="true">{said}</p>
    </section>
  );
}
