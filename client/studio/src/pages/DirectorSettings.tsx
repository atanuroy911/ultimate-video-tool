import { useFetch } from "../hooks";
import type { Settings } from "../types";
import { Field, Spinner } from "../ui";

type Director = { id: string; kind: string; label: string; available: boolean; note: string };
const DEFAULT_ORDER = ["claude-client", "codex-client", "claude-server", "local"];
const ORDERS = [
  ["claude-client,codex-client,claude-server,local", "Claude on a connected PC first"],
  ["codex-client,claude-client,claude-server,local", "Codex on a connected PC first"],
  ["local,claude-client,codex-client,claude-server", "Local AI first"],
  ["claude-client,claude-server,local", "Connected Claude, then server Claude, then Local AI"],
  ["claude-server,claude-client,local", "Server Claude, then connected Claude, then Local AI"],
  ["local,claude-client,claude-server", "Local AI, then Claude"],
];

export default function DirectorSettings({ settings, directors, loading, onSave }: {
  settings: Settings; directors?: Director[]; loading: boolean; onSave: (patch: Partial<Settings>) => void;
}) {
  const order = settings.director_order || DEFAULT_ORDER;
  const ordered = order.flatMap(kind => (directors || []).filter(d => d.id === kind || d.kind === kind));
  if (!ordered.some(d => d.id === "local")) {
    const local = directors?.find(d => d.id === "local");
    if (local) ordered.push(local);
  }
  const next = ordered.find(d => d.available);
  const value = order.join(",");
  const missing = order.filter(kind => ["claude-client", "codex-client"].includes(kind) && !ordered.some(d => d.kind === kind));
  return <section className="card card-pad col director-settings" style={{ gap: 16 }} aria-labelledby="directors-title">
    <h2 id="directors-title">Who directs your videos</h2>
    <div className="director-next" role="status" data-testid="next-director">
      {loading ? <><Spinner /> Checking which directors are ready…</> : directors ? <>
        <strong>{next ? `${next.label} directs your next video` : "No director is ready yet"}</strong>
        <span className="small muted">{next ? "If it can't finish, the next ready one in the list takes over." : "Connect Claude or Codex below, or set up the Writing AI on the Server page. Videos still work with built-in rules."}</span>
      </> : <><strong>Could not check the directors</strong><span className="small muted">Reconnect to the server, then open this page again.</span></>}
    </div>
    <Field label="Automatic tries this order">
      <select value={value} onChange={e => onSave({ director_order: e.target.value.split(",") })}>
        {ORDERS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        {!ORDERS.some(([id]) => id === value) && <option value={value}>Your saved order</option>}
      </select>
    </Field>
    <ol className="director-order" aria-label="Director fallback order">{ordered.map(d => <li key={d.id} data-director={d.id}>
      <div className="col grow" style={{ gap: 4 }}><strong>{d.label}</strong><span className="small muted">{d.available ? (d.id === next?.id ? "First ready choice in your order." : "Ready if an earlier director cannot finish.") :
        d.kind.endsWith("-client") ? "Open Ultimate Video Tool on that computer and sign in to the assistant." : d.id === "local" ? "Check the Writing AI on the Server page." : "Sign in to Claude Code on the server."}</span></div>
      <span className={`chip ${d.available ? "ok" : "warn"}`}>{d.available ? "Ready" : "Needs attention"}</span>
    </li>)}</ol>
    {missing.length > 0 && <p className="small muted" data-testid="missing-directors">{missing.map(kind => kind.startsWith("codex") ? "Codex" : "Claude").join(" and ")} on your own computer: not connected yet. Open Ultimate Video Tool on that computer; it connects by itself.</p>}
    <div className="director-options">
      <Field label="Which Claude directs"><select aria-label="Which Claude directs" value={settings.director_model || "sonnet"} onChange={e => onSave({ director_model: e.target.value })} data-testid="director-model">
        <option value="sonnet">Sonnet: faster</option><option value="opus">Opus: slower, the most careful</option>
        {settings.director_model && !["sonnet", "opus"].includes(settings.director_model) && <option value={settings.director_model}>{settings.director_model}</option>}
      </select></Field>
      <Field label="When that computer is busy, wait"><select value={String(settings.director_wait_seconds ?? 120)} onChange={e => onSave({ director_wait_seconds: e.target.value === "wait" ? "wait" : Number(e.target.value) })}>
        <option value="30">30 seconds</option><option value="120">2 minutes</option><option value="300">5 minutes</option><option value="wait">Until it is free</option>
      </select></Field>
    </div>
    <p className="small muted">This wait is for a computer that is busy with another task. A director that is working on your video is never stopped before 30 minutes.</p>
    <p className="small muted">Choose a different director for one video on Make a video or Direct again.</p>
    <HouseRules />
  </section>;
}

type Rule = { id: string; scopes: string[]; say: string; why: string };
const SCOPE: Record<string, string> = { plan: "planning", story: "story cartoons", cartoon: "cartoons", script: "the script", review: "the last look", reel: "picture videos", publish: "the title" };

/** What every director is told on top of its brief (vt/house_rules.py, GET /api/house-rules, `vt rules`), and the video that taught each lesson. */
function HouseRules() {
  const q = useFetch<Rule[]>("/api/house-rules");
  const rules = Array.isArray(q.data) ? q.data.filter(r => r && typeof r.say === "string") : [];   // an older server or a broken answer shows nothing, never a crash
  return <details className="house-rules" data-testid="house-rules">
    <summary><strong>What every director is told</strong>{rules.length > 0 && <span className="small muted"> · {rules.length} rule{rules.length === 1 ? "" : "s"}</span>}</summary>
    {q.loading && <span className="small muted"><Spinner size={12} /> Loading…</span>}
    {q.error && <span className="small muted">Could not load the rules. Reconnect to the server and open this again.</span>}
    <ol className="col" style={{ gap: 10, margin: "10px 0 0", paddingLeft: 20 }}>
      {rules.map(r => <li key={r.id} className="col" style={{ gap: 2 }}>
        <span>{r.say}</span>
        <span className="small muted">{(r.scopes || []).length ? `For ${r.scopes.map(x => SCOPE[x] ?? x).join(", ")}. ` : ""}Why: {r.why}</span>
      </li>)}
    </ol>
  </details>;
}
