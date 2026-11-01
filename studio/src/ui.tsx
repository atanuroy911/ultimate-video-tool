import { Check, Loader2, X } from "lucide-react";
import React, { useEffect, useRef } from "react";
import { toast, toastStore, useStore } from "./store";
import { useT } from "./i18n";

export function Toasts() {
  const toasts = useStore(toastStore);
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`}>
          {t.text}
        </div>
      ))}
    </div>
  );
}

export function Modal(props: { title: string; onClose: () => void; children: React.ReactNode; footer?: React.ReactNode; wide?: boolean }) {
  const t = useT();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && props.onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [props]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && props.onClose()}>
      <div className={`modal ${props.wide ? "wide" : ""}`} role="dialog" aria-modal="true" aria-label={props.title}>
        <div className="modal-head">
          <h2 className="grow">{props.title}</h2>
          <button className="btn ghost icon sm" onClick={props.onClose} aria-label={t("common.close")}>
            <X size={16} />
          </button>
        </div>
        <div className="modal-body">{props.children}</div>
        {props.footer && <div className="modal-foot">{props.footer}</div>}
      </div>
    </div>
  );
}

export function Seg<T extends string>(props: { value: T; options: { value: T; label: React.ReactNode }[]; onChange: (v: T) => void; label?: string; wrap?: boolean }) {
  const i = Math.max(0, props.options.findIndex((o) => o.value === props.value));
  return (
    <div className={props.wrap ? "seg wrap" : "seg"} role="group" aria-label={props.label} style={{ ["--n" as any]: props.options.length, ["--i" as any]: i }}>
      <i className="thumb" aria-hidden />
      {props.options.map((o) => (
        <button key={o.value} className={props.value === o.value ? "on" : ""} onClick={() => props.onChange(o.value)} aria-pressed={props.value === o.value} type="button">
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Field(props: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span>{props.label}</span>
      {props.children}
      {props.hint && <span className="small muted" style={{ fontWeight: 400 }}>{props.hint}</span>}
    </label>
  );
}

export function Check2(props: { checked: boolean; onChange: (v: boolean) => void; children: React.ReactNode }) {
  return (
    <label className="check">
      <input type="checkbox" checked={props.checked} onChange={(e) => props.onChange(e.target.checked)} />
      <span>{props.children}</span>
    </label>
  );
}

export function Spinner({ size = 16 }: { size?: number }) {
  return <Loader2 size={size} className="spin" aria-label="Loading" />;
}

const STATUS_TONE: Record<string, string> = {
  planned: "ok",
  rendered: "accent",
  processing: "warn",
  waiting_for_claude: "warn",
  error: "err",
  draft: "",
};
export function StatusChip({ status }: { status: string }) {
  const t = useT();
  const key = `status.${status}`;
  const label = t(key) === key ? status : t(key);
  return (
    <span className={`chip ${STATUS_TONE[status] ?? ""}`}>
      {status === "processing" && <Spinner size={12} />}
      {status === "planned" && <Check size={12} />}
      {label}
    </span>
  );
}

export function ProgressBar({ frac }: { frac: number }) {
  return (
    <div className="bar" role="progressbar" aria-label="Progress" aria-valuenow={Math.round(frac * 100)} aria-valuemin={0} aria-valuemax={100}>
      <i style={{ width: `${Math.max(2, Math.min(100, frac * 100))}%` }} />
    </div>
  );
}

/** Copy to the clipboard and say what happened. Browsers refuse without permission or on an insecure page: fall back to the old way; if that fails too the user is told
 *  (never an unhandled error, never a "Copied" that did not happen). Resolves true when the text was copied. */
export async function copyText(text: string, ok: string = "Copied"): Promise<boolean> {
  let done = false;
  try {
    await navigator.clipboard.writeText(text);
    done = true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      done = document.execCommand("copy");
      ta.remove();
    } catch {
      done = false;
    }
  }
  toast(done ? ok : "Copying is not allowed here. Select the text and copy it by hand.", done ? "ok" : "err", done ? 1500 : 5000);
  return done;
}

/** A context menu at a point on screen (closes on outside click, Escape and scroll). */
export function Menu(props: { x: number; y: number; onClose: () => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const down = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) props.onClose();
    };
    const key = (e: KeyboardEvent) => e.key === "Escape" && props.onClose();
    window.addEventListener("mousedown", down);
    window.addEventListener("keydown", key);
    window.addEventListener("scroll", props.onClose, true);
    return () => {
      window.removeEventListener("mousedown", down);
      window.removeEventListener("keydown", key);
      window.removeEventListener("scroll", props.onClose, true);
    };
  }, [props]);
  const left = Math.min(props.x, window.innerWidth - 220);
  const top = Math.min(props.y, window.innerHeight - 260);
  return (
    <div ref={ref} className="menu" style={{ left, top }} role="menu">
      {props.children}
    </div>
  );
}

/** A 24x24 line icon from the icon pack (its inner SVG markup). */
export function PackIcon({ inner, size = 20 }: { inner?: string; size?: number }) {
  return inner ? (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: inner }} />
  ) : (
    <span style={{ width: size, height: size, display: "inline-block" }} />
  );
}

/** WCAG contrast ratio between two #rrggbb colours (0 when either is not a plain hex colour). */
export function contrastRatio(a: string, b: string): number {
  const lum = (hex: string) => {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
    if (!m) return null;
    const n = parseInt(m[1], 16);
    const c = (v: number) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * c((n >> 16) & 255) + 0.7152 * c((n >> 8) & 255) + 0.0722 * c(n & 255);
  };
  const x = lum(a), y = lum(b);
  if (x == null || y == null) return 0;
  const [hi, lo] = x > y ? [x, y] : [y, x];
  return (hi + 0.05) / (lo + 0.05);
}
