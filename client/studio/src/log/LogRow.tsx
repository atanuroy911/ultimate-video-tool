import { AlertTriangle, Check, ChevronRight, Info, X } from "lucide-react";
import { useState } from "react";
import { post } from "../api";
import { toast } from "../store";
import type { LogEntry, RunningCall } from "./useCallLog";

const ICON = { ok: Check, info: Info, warn: AlertTriangle, error: X } as const;
const WHO: Record<string, string> = { rules: "Rules", person: "You", claude: "Claude", codex: "Codex", gemini: "Gemini", assistant: "Assistant" };

export const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const who = (e: LogEntry) => (e.caller?.kind === "rules" ? "" : WHO[e.caller?.kind || ""] || e.caller?.kind || "");
const took = (s: number) => (s < 1 ? "under a second" : s < 60 ? `${Math.round(s)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`);

/** A labelled reading of the inputs a step used (never raw JSON in the main view). */
function used(inputs?: Record<string, unknown>) {
  return Object.entries(inputs || {})
    .filter(([k, v]) => k !== "force" && v !== null && v !== "" && typeof v !== "object")
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v).slice(0, 60)}`);
}

export function RunningRow({ call, pid }: { call: RunningCall; pid: string }) {
  const frac = call.frac && call.frac > 0 ? call.frac : Math.min(0.95, call.elapsed / Math.max(1, call.estimate));
  return (
    <li className="log-row running" data-testid="log-running">
      <div className="log-head">
        <span className="log-ic" aria-hidden>●</span>
        <span className="log-plain">{call.plain}</span>
        <span className="muted small">{clock(call.elapsed)} of about {clock(call.estimate)}</span>
        <button className="btn ghost sm" onClick={() => post(`/api/projects/${pid}/calls/${call.id}/cancel`).catch((e) => toast(e.message, "err"))}>
          Cancel
        </button>
      </div>
      <div className="log-bar" role="progressbar" aria-label="Progress" aria-valuenow={Math.round(frac * 100)} aria-valuemin={0} aria-valuemax={100}>
        <i style={{ width: `${Math.round(frac * 100)}%` }} />
      </div>
    </li>
  );
}

export function LogRow({ entry, start, showTechnical }: { entry: LogEntry; start: number; showTechnical: boolean }) {
  const [open, setOpen] = useState(entry.level === "error");
  const Icon = ICON[entry.level] || Info;
  const at = (Date.parse(entry.t) - start) / 1000;
  const seconds = entry.cost?.seconds;
  const facts = used(entry.inputs);
  return (
    <li className={`log-row ${entry.level}`} data-testid="log-row" data-level={entry.level}>
      <button className="log-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="log-ic" aria-hidden><Icon size={13} /></span>
        <span className="muted small log-at">{clock(Math.max(0, at))}</span>
        <span className="log-plain">{entry.plain || entry.module}</span>
        <span className="muted small">
          {[who(entry), seconds !== undefined ? took(seconds) : ""].filter(Boolean).join(" · ")}
          {entry.cached ? " · reused" : ""}
        </span>
        <ChevronRight size={13} className="log-chev" aria-hidden />
      </button>
      {open && (
        <div className="log-more small">
          {entry.why && entry.why !== "Classic recipe" && <div><strong>Why:</strong> {entry.why}</div>}
          {facts.length > 0 && <div><strong>Used:</strong> {facts.join(" · ")}</div>}
          {entry.fix && <div className="log-fix"><strong>What to do:</strong> {entry.fix}</div>}
          {showTechnical && <pre className="log-raw">{JSON.stringify({ module: entry.module, status: entry.status, inputs: entry.inputs, wrote: entry.wrote }, null, 2)}</pre>}
        </div>
      )}
    </li>
  );
}
