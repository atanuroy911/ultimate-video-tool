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
        <strong>{next ? `Next ready director: ${next.label}` : "No director is ready yet"}</strong>
        <span className="small muted">{next ? "New videos set to Automatic use this order. If a director cannot finish, the next one takes over." : "Connect an assistant below or set up Local AI in Server details. Built-in rules can still make a video."}</span>
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
        d.kind.endsWith("-client") ? "Start the helper on that computer and sign in to its assistant." : d.id === "local" ? "Open Server details below to check the local model and connection." : "Sign in to Claude Code on the server, then check again."}</span></div>
      <span className={`chip ${d.available ? "ok" : "warn"}`}>{d.available ? "Ready" : "Needs attention"}</span>
    </li>)}</ol>
    {missing.length > 0 && <p className="small muted" data-testid="missing-directors">{missing.map(kind => kind.startsWith("codex") ? "Codex" : "Claude").join(" and ")} on a connected PC: no helper is connected yet. Open the desktop app on that PC, start its helper below and sign in to the assistant.</p>}
    <div className="director-options">
      <Field label="Claude model"><select aria-label="Claude model" value={settings.director_model || "sonnet"} onChange={e => onSave({ director_model: e.target.value })} data-testid="director-model">
        <option value="sonnet">Sonnet: faster</option><option value="opus">Opus: more careful</option>
        {settings.director_model && !["sonnet", "opus"].includes(settings.director_model) && <option value={settings.director_model}>{settings.director_model}</option>}
      </select></Field>
      <Field label="Wait for another computer"><select value={String(settings.director_wait_seconds ?? 120)} onChange={e => onSave({ director_wait_seconds: e.target.value === "wait" ? "wait" : Number(e.target.value) })}>
        <option value="30">30 seconds</option><option value="120">2 minutes</option><option value="300">5 minutes</option><option value="wait">Wait for me</option>
      </select></Field>
    </div>
    <p className="small muted">Choose a different director for one video on Make a video or Direct again.</p>
  </section>;
}
