import { Check, Gauge } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { get, post, put } from "../api";
import { useT } from "../i18n";
import { toast } from "../store";
import { Spinner } from "../ui";

/* Which graphics cards Video Tool may use, and which of them does what (server vt/gpuassign.py; `vt gpu`).
   A switch per card says whether Video Tool may use it at all: a card that is switched off is never touched. Below that, when two or more cards are on,
   each job (primary card, rendering, speech recognition, Video Tool's own language AI and picture engine) can use a different one.
   An Ollama or ComfyUI that was already running is a separate program: it is described, left as it is, and when it sits on a card Video Tool may not use the card says so
   in words and offers Video Tool's own copy. The same component is the setup question ("setup" mode: only the cards, with "Use these cards" and "Not now"). */
interface Using { label: string; gb: number | null; ours: boolean }
interface Card { index: number; name: string; uuid: string; free_gb: number; total_gb: number; load: number; allowed: boolean; using: Using[] }
interface Job { gpu: string | null; name: string | null; index: number | null; why: string }
interface EngineCard { index: number; name: string; gb: number | null; allowed: boolean }
interface EngineRow { id: string; label: string; source: string; code: string; message: string; on: EngineCard[]; offer_own: boolean; own_installed: boolean }
type JobKey = "render" | "speech" | "ai" | "pictures";
interface Gpus {
  cards: Card[]; saved: Record<"primary" | JobKey, string>;
  allowed_saved: string[] | null; needs_choice: boolean; restart_needed: boolean;
  jobs: Record<JobKey, Job>;
  engines?: EngineRow[]; restarting?: string[];
  pinned_by_launcher: string | null;
}
const JOBS: JobKey[] = ["render", "speech", "ai", "pictures"];
/** An older server answers with less (no `using`, no `needs_choice`, no engines): it cannot be shown this way, and must not break the page. */
const understood = (x: any): x is Gpus => !!x && Array.isArray(x.cards) && typeof x.needs_choice === "boolean" && !!x.saved && !!x.jobs && x.cards.every((c: any) => Array.isArray(c.using));
const fill = (s: string, v: Record<string, string | number>) => Object.entries(v).reduce((a, [k, x]) => a.split(`{${k}}`).join(String(x)), s);

/** A card's name; its number only when two cards share a name (two "RTX 3060"s), the way a person tells them apart. */
function cardName(c: { index: number; name: string }, all: { name: string }[]): string {
  return all.filter((x) => x.name === c.name).length > 1 ? `${c.name} (${c.index + 1})` : c.name;
}

/** What the launcher limited this server to, in words: "-1" (or nothing) means no card at all; numbers or ids become card names. */
function pinnedNote(d: { pinned_by_launcher: string | null; cards: { index: number; name: string; uuid: string }[] }, t: (k: string) => string): string {
  const ids = String(d.pinned_by_launcher || "").split(",").map((x) => x.trim()).filter((x) => x && x !== "-1");
  if (!ids.length) return t("gpu.pinned.none");
  const names = ids.map((x) => d.cards.find((c) => String(c.index) === x || c.uuid === x)?.name || x);
  return t("gpu.pinned").replace("{cards}", names.join(", "));
}

export default function GpuChoice({ mode = "page", onAnswered, onSkip }: { mode?: "page" | "setup"; onAnswered?: () => void; onSkip?: () => void }) {
  const t = useT();
  const [d, setD] = useState<Gpus | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [said, setSaid] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback(() => get<Gpus>("/api/system/gpus").then((x) => {
    if (!understood(x)) { setError(t("gpu.older")); return; }
    setD((was) => (JSON.stringify(was) === JSON.stringify(x) ? was : x));                  // the same answer changes nothing on screen
    setError("");
  }).catch((e) => setError(e.message || "")), []);                                           // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    load();
    if (mode !== "page") return;
    const timer = window.setInterval(load, 5000);                       // what is using each card changes while the page is open
    return () => window.clearInterval(timer);
  }, [load, mode]);

  const engineName = (id: string) => t("gpu.engine." + id);
  const save = async (patch: Record<string, string | string[]>, say: (next: Gpus) => string): Promise<boolean> => {
    setSaving(true);
    try {
      const next = await put<Gpus>("/api/system/gpu", patch);
      if (!understood(next)) { setError(t("gpu.older")); return false; }
      setD(next);
      const again = (next.restarting || []).map(engineName);
      setSaid(say(next) + (again.length ? " " + fill(t("gpu.restarting"), { what: again.join(" / ") }) : ""));
      return true;
    } catch (e: any) { toast(e.message, "err"); return false; } finally { setSaving(false); }
  };
  const allowedNames = (g: Gpus) => g.cards.filter((c) => c.allowed).map((c) => c.name).join(", ") || t("gpu.no_card");
  const answer = (cards: Card[]) => cards.filter((c) => c.allowed).map((c) => c.uuid);
  const toggle = (g: Gpus, c: Card) => save({ allowed: c.allowed ? answer(g.cards).filter((u) => u !== c.uuid) : [...answer(g.cards), c.uuid] }, (n) => fill(t("gpu.said.allowed"), { cards: allowedNames(n) }));
  const keep = (g: Gpus) => save({ allowed: answer(g.cards) }, (n) => fill(t("gpu.said.allowed"), { cards: allowedNames(n) }));
  const choose = (key: "primary" | JobKey, value: string) => save({ [key]: value }, (n) => (key === "primary" ? fill(t("gpu.said.primary"), { card: value === "auto" ? t("gpu.auto.short") : n.cards.find((c) => c.uuid === value)?.name ?? "" }) : fill(t("gpu.said.job"), { job: t("gpu.job." + key), card: n.jobs[key].name ?? "" })));
  const switchToOwn = async (id: string) => {
    setBusy(id);
    try {
      await post("/api/system/engine-own", { engine: id });
      setSaid(fill(t("gpu.said.own"), { what: engineName(id) }));
      await load();
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };

  const page = mode === "page";
  const frame = page ? "card card-pad col gpu-card" : "col gpu-card";                        // as a step of the setup wizard it has no frame and no title of its own: the wizard shows them
  const head = page ? <div className="row" style={{ alignItems: "center" }}><h2 className="grow"><Gauge size={18} style={{ verticalAlign: -3 }} aria-hidden /> {t("gpu.title")}</h2>{saving && <Spinner />}</div> : null;
  if (error) return (
    <section className={frame} style={{ gap: 8 }} aria-label={t("gpu.title")} data-testid="gpu-assignment">
      {head}
      <p className="small muted" style={{ margin: 0 }}>{t("gpu.unavailable")} ({error})</p>
    </section>
  );
  if (!d) return <section className={frame} aria-label={t("gpu.title")}><Spinner /></section>;
  if (!d.cards.length) return mode === "setup" ? null : (
    <section className={frame} style={{ gap: 8 }} aria-label={t("gpu.title")} data-testid="gpu-assignment">
      {head}
      <p className="small muted" style={{ margin: 0 }}>{t("gpu.none")}</p>
    </section>
  );

  const on = d.cards.filter((c) => c.allowed);
  const usingText = (c: Card) => (c.using.length
    ? c.using.map((p) => (p.ours ? (p.gb ? fill(t("gpu.card.ours"), { gb: p.gb }) : t("gpu.card.ours_nogb")) : p.gb ? fill(t("gpu.card.program"), { name: p.label, gb: p.gb }) : fill(t("gpu.card.program_nogb"), { name: p.label }))).join(" ")
    : t("gpu.card.idle"));
  const cardOption = (c: Card) => <option key={c.uuid} value={c.uuid}>{`${cardName(c, d.cards)} (${fill(t("gpu.card.mem"), { free: c.free_gb, total: c.total_gb })})`}</option>;
  const row = (id: "primary" | JobKey, hint: string, value: string, first: { value: string; label: string }, job?: Job) => (       // a plain function, not a component: the list stays put while the page refreshes
    <div key={id} className="row wrap" style={{ gap: 10, alignItems: "center", padding: "8px 0" }}>
      <label htmlFor={`gpu-${id}`} className="col" style={{ gap: 2, flex: "1 1 220px", minWidth: 0 }}>
        <strong>{t("gpu.job." + id)}</strong>
        <span className="small muted">{hint}{job?.name ? ` ${fill(t("gpu.job.uses"), { card: job.name || "" })}` : ""}</span>
      </label>
      <select id={`gpu-${id}`} value={value} onChange={(e) => choose(id, e.target.value)} disabled={saving} style={{ flex: "1 1 260px", minHeight: 44 }}>
        <option value={first.value}>{first.label}</option>
        {on.map(cardOption)}
      </select>
    </div>
  );

  return (
    <section className={frame} style={{ gap: 8 }} aria-label={t("gpu.title")} data-testid="gpu-assignment" data-mode={mode}>
      {head}
      {page && <p className="muted" style={{ margin: 0 }}>{t("gpu.intro")}</p>}

      {d.needs_choice && (
        <div className="notice" role="note" data-testid="gpu-needs-choice" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <span className="grow" style={{ flex: "1 1 240px" }}>{fill(t("gpu.needs_choice"), { card: allowedNames(d) })}</span>
          {mode === "page" && <button className="btn sm" disabled={saving} onClick={() => keep(d)} data-testid="gpu-keep">{t("gpu.keep")}</button>}
        </div>
      )}
      {!d.needs_choice && on.length === 0 && <p className="notice warn" role="note" style={{ margin: 0 }} data-testid="gpu-none-on">{t("gpu.none_warn")}</p>}
      {d.restart_needed && <p className="notice" role="note" style={{ margin: 0 }} data-testid="gpu-restart">{t("gpu.restart")}</p>}
      {d.pinned_by_launcher != null && <p className="small muted" style={{ margin: 0 }}>{pinnedNote(d, t)}</p>}

      <h3 className="helper-heading" id="gpu-cards-title">{t("gpu.cards.title")}</h3>
      <ul className="helper-list" data-testid="gpu-cards" aria-labelledby="gpu-cards-title">
        {d.cards.map((c) => (
          <li key={c.uuid} className="gpu-row" data-testid={`gpu-card-${c.index}`} data-allowed={c.allowed}>
            <span className="col grow" style={{ gap: 2, minWidth: 0 }}>
              <span id={`gpu-name-${c.index}`} style={{ fontWeight: 600 }}>{cardName(c, d.cards)}</span>
              <span className="small muted">{fill(t("gpu.card.mem"), { free: c.free_gb, total: c.total_gb })}</span>
              <span className="small muted" data-testid={`gpu-using-${c.index}`}>{usingText(c)}</span>
            </span>
            <button type="button" role="switch" aria-checked={c.allowed} aria-label={`${t("gpu.card.switch")}: ${c.name}`} className="switch" disabled={saving}
              onClick={() => toggle(d, c)} data-testid={`gpu-switch-${c.index}`} />
          </li>
        ))}
      </ul>

      {mode === "setup" && (
        <div className="row wrap" style={{ gap: 8 }}>
          <button className="btn primary" disabled={saving} onClick={async () => { if (await keep(d)) onAnswered?.(); }} data-testid="gpu-use-these">{t("gpu.use_these")}</button>
          <button className="btn ghost" disabled={saving} onClick={() => onSkip?.()} data-testid="gpu-not-now">{t("gpu.not_now")}</button>
        </div>
      )}

      {mode === "page" && on.length >= 2 && (
        <div className="col" style={{ gap: 2, paddingTop: 8, borderTop: "1px solid var(--border)" }} data-testid="gpu-jobs">
          <h3 className="helper-heading">{t("gpu.jobs.title")}</h3>
          <p className="small muted" style={{ margin: 0 }}>{t("gpu.jobs.intro")}</p>
          {row("primary", t("gpu.job.primary.hint"), d.saved.primary, { value: "auto", label: t("gpu.auto") })}
          {JOBS.map((j) => row(j, t(`gpu.job.${j}.hint`), d.saved[j], { value: "primary", label: t("gpu.same_primary") }, d.jobs[j]))}
        </div>
      )}

      {mode === "page" && (d.engines || []).length > 0 && (
        <div className="col" style={{ gap: 4, paddingTop: 8, borderTop: "1px solid var(--border)" }} data-testid="gpu-engines">
          <h3 className="helper-heading">{t("gpu.engines.title")}</h3>
          <ul className="helper-list">
            {(d.engines || []).map((e) => (
              <li key={e.id} data-testid={`engine-${e.id}`} data-code={e.code}>
                <span className="col grow" style={{ gap: 2, minWidth: 0 }}>
                  <span style={{ fontWeight: 600 }}>{engineName(e.id)}</span>
                  <span className="small muted">{e.message}</span>
                  {e.offer_own && !e.own_installed && <span className="small muted">{t("gpu.engine.not_installed")}</span>}
                </span>
                {e.offer_own && e.own_installed && (
                  <button className="btn sm" disabled={!!busy} onClick={() => switchToOwn(e.id)} data-testid={`engine-${e.id}-own`}>{busy === e.id ? <Spinner /> : t("gpu.engine.use_own")}</button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="sr-only" role="status" aria-atomic="true">{said}</p>
      {said && mode === "setup" && <p className="small muted" style={{ margin: 0 }} aria-hidden><Check size={12} /> {said}</p>}
    </section>
  );
}
