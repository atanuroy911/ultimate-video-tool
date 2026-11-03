import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { Loader2, X } from "lucide-react";
import { BusyOp, cancelOp, end, getOps, hide, subscribeOps } from "./busycore";
import { toast } from "./store";
import { ProgressBar } from "./ui";

const SHOW_AFTER = 400;       // ms: a fast operation never flashes the layer
const SHOW_AT_LEAST = 600;    // ms: once it is up it does not blink away

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** The one full-screen loading layer: shown for anything the person is waiting for, whichever page started it. */
export function BusyLayer() {
  const ops = useSyncExternalStore(subscribeOps, getOps);
  const visible = ops.filter((o) => !o.hidden);
  const [shown, setShown] = useState(false);
  const [now, setNow] = useState(Date.now());
  const since = useRef(0);
  const card = useRef<HTMLDivElement>(null);
  const before = useRef<Element | null>(null);

  useEffect(() => {
    if (visible.length) {
      if (shown) return;
      const oldest = Math.min(...visible.map((o) => o.start));
      const t = setTimeout(() => { since.current = Date.now(); setNow(since.current); setShown(true); }, Math.max(0, SHOW_AFTER - (Date.now() - oldest)));
      return () => clearTimeout(t);
    }
    if (shown) {
      const t = setTimeout(() => setShown(false), Math.max(0, SHOW_AT_LEAST - (Date.now() - since.current)));
      return () => clearTimeout(t);
    }
  }, [visible.length, shown, ops]);              // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!shown) return;
    const iv = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(iv);
  }, [shown]);

  useEffect(() => {                              // the page behind is inert while the layer is up; focus goes in and comes back
    const root = document.getElementById("root");
    if (shown) {
      before.current = document.activeElement;
      root?.setAttribute("inert", "");
      root?.setAttribute("aria-busy", "true");
      requestAnimationFrame(() => card.current?.focus());
      return () => {
        root?.removeAttribute("inert");
        root?.removeAttribute("aria-busy");
        (before.current as HTMLElement | null)?.focus?.();
      };
    }
  }, [shown]);

  useEffect(() => {
    const done = (e: Event) => { const d = (e as CustomEvent).detail; if (d.hidden) toast(`${d.title}: finished`, "ok", 4000); };
    const cancelled = (e: Event) => toast(`${(e as CustomEvent).detail.title}: cancelled`, "info", 3000);
    const failed = (e: Event) => toast(`${(e as CustomEvent).detail.title}: ${(e as CustomEvent).detail.error}`, "err", 8000);
    addEventListener("vt-job-done", done); addEventListener("vt-job-cancelled", cancelled); addEventListener("vt-job-failed", failed);
    return () => { removeEventListener("vt-job-done", done); removeEventListener("vt-job-cancelled", cancelled); removeEventListener("vt-job-failed", failed); };
  }, []);

  if (!shown || !visible.length) return null;
  const main = visible.find((o) => o.error) ?? visible[0];
  const rest = visible.filter((o) => o !== main);
  const elapsed = Math.max(0, (now - main.start) / 1000);
  const eta = main.frac && main.frac > 0.06 && main.frac < 0.98 ? (elapsed * (1 - main.frac)) / main.frac : null;
  const dismiss = (o: BusyOp) => (o.error ? end(o) : o.jobId ? hide(o) : undefined);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); if (main.error) end(main); else if (main.cancellable) cancelOp(main); else if (main.jobId) hide(main); }
    if (e.key === "Tab") {                       // keep focus inside the layer
      const items = Array.from(card.current?.querySelectorAll<HTMLElement>("button:not([disabled])") ?? []);
      if (!items.length) { e.preventDefault(); card.current?.focus(); return; }
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === card.current)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  };

  return createPortal(
    <div className="busy-layer" onKeyDown={onKey}>
      <div ref={card} className="busy-card" role="alertdialog" aria-modal="true" aria-labelledby="busy-title" aria-describedby="busy-step" tabIndex={-1}>
        {main.error ? (
          <>
            <h2 id="busy-title">{main.title} did not work</h2>
            <p id="busy-step" className="busy-error">{main.error}</p>
            <div className="row" style={{ justifyContent: "center" }}><button className="btn primary" onClick={() => end(main)}><X size={14} /> Close</button></div>
          </>
        ) : (
          <>
            <Loader2 size={38} className="spin busy-spin" aria-hidden="true" />
            <h2 id="busy-title">{main.title}</h2>
            <p id="busy-step" role="status" aria-live="polite">{main.step || "This can take a moment."}</p>
            {main.frac != null ? (
              <div className="busy-bar"><ProgressBar frac={main.frac} /><span className="small muted">{Math.round(main.frac * 100)}%</span></div>
            ) : (
              <div className="bar busy-indeterminate" aria-hidden="true"><i /></div>
            )}
            <p className="small muted">{mmss(elapsed)} passed{eta != null ? `, about ${mmss(eta)} left` : ""}</p>
            {rest.length > 0 && (
              <ul className="busy-others" aria-label="Also running">
                {rest.map((o) => <li key={o.id}><span>{o.title}</span>{o.step ? <span className="muted"> · {o.step}</span> : null}</li>)}
              </ul>
            )}
            <div className="row" style={{ justifyContent: "center", gap: 8 }}>
              {main.cancellable && <button className="btn" onClick={() => cancelOp(main)}>Cancel</button>}
              {main.jobId && <button className="btn ghost" onClick={() => dismiss(main)}>Keep working while it runs</button>}
            </div>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}
