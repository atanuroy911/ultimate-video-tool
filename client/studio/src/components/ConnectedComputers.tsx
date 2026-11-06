import { Check } from "lucide-react";
import { useEffect } from "react";
import { useFetch } from "../hooks";
import { useT } from "../i18n";

/** Which computers keep Claude or Codex ready for this server, and what each offers (the helpers there call this server; this card only reads the list).
 *  A computer that was here and is not now stays listed as "Not connected" until it comes back. */
type Director = { id: string; kind: string; label: string; available: boolean; device?: string; device_name?: string; last_seen?: string };
const NAMES: Record<string, string> = { "claude-client": "Claude", "codex-client": "Codex" };

/** "5 minutes ago". */
function ago(iso: string | undefined): string {
  const at = iso ? Date.parse(iso) : NaN;
  if (!Number.isFinite(at)) return "";
  const seconds = (Date.now() - at) / 1000, f = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (seconds < 90) return f.format(0, "minute");
  if (seconds < 5400) return f.format(-Math.round(seconds / 60), "minute");
  if (seconds < 129600) return f.format(-Math.round(seconds / 3600), "hour");
  return f.format(-Math.round(seconds / 86400), "day");
}

export default function ConnectedComputers() {
  const t = useT();
  const list = useFetch<{ directors: Director[] }>("/api/directors");
  useEffect(() => {
    const timer = window.setInterval(() => list.refetch(), 5000);
    return () => window.clearInterval(timer);
  }, [list.refetch]);
  const byComputer = new Map<string, { name: string; items: Director[] }>();
  for (const d of list.data?.directors || []) {
    if (!NAMES[d.kind] || !d.device) continue;
    const row = byComputer.get(d.device) || { name: d.device_name || d.label.replace(/^(Claude|Codex) on /, ""), items: [] };
    row.items.push(d);
    byComputer.set(d.device, row);
  }
  const computers = [...byComputer.entries()].map(([id, c]) => ({ id, ...c }));
  return (
    <section className="card card-pad col" style={{ gap: 12 }} aria-labelledby="computers-title" data-testid="connected-computers">
      <h2 id="computers-title">{t("computers.title")}</h2>
      <p className="muted" style={{ margin: 0 }}>{t("computers.what")}</p>
      {list.data && computers.length === 0 && <p className="small muted" style={{ margin: 0 }} data-testid="computers-empty">{t("computers.empty")}</p>}
      {computers.length > 0 && (
        <ul className="helper-list">
          {computers.map((c) => {
            const connected = c.items.some((i) => i.last_seen === undefined);
            return (
              <li key={c.id} data-testid="computer-row" data-connected={connected}>
                <span className="col grow" style={{ gap: 2, minWidth: 0 }}>
                  <strong>{c.name}</strong>
                  {!connected && <span className="small muted">{t("computers.not_connected")}{c.items[0].last_seen ? ` · ${t("computers.last_seen")} ${ago(c.items[0].last_seen)}` : ""}</span>}
                </span>
                <span className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                  {c.items.map((i) => connected
                    ? <span key={i.id} className={`chip ${i.available ? "ok" : "warn"}`}>{i.available ? <Check size={12} /> : null} {NAMES[i.kind]} · {i.available ? t("computers.ready") : t("computers.sign_in")}</span>
                    : <span key={i.id} className="chip">{NAMES[i.kind]}</span>)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
