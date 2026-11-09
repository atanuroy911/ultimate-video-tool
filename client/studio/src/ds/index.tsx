/* Small design-system layer for the editor: tokens live in styles.css and ds.css; screens compose these pieces. */
import { useT } from "../i18n";
import { ChevronDown, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { ReactNode } from "react";
import "./ds.css";

export { Seg as Segmented } from "../ui";

/* ---------- Button ---------- */
export function Button(props: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" | "ghost" | "danger"; size?: "sm" | "md"; icon?: boolean }) {
  const { variant = "default", size = "md", icon, className = "", ...rest } = props;
  return <button type="button" {...rest} className={`btn ${variant === "default" ? "" : variant} ${size === "sm" ? "sm" : ""} ${icon ? "icon" : ""} ${className}`} />;
}

/* ---------- Kbd ---------- */
export const Kbd = ({ children }: { children: ReactNode }) => <span className="kbd">{children}</span>;

/* ---------- Tooltip: a label that shows on hover and focus, and names the control for screen readers ---------- */
export function Tooltip({ text, children, keys }: { text: string; children: ReactNode; keys?: string }) {
  return (
    <span className="ds-tip" data-tip={keys ? `${text}  ${keys}` : text}>
      {children}
    </span>
  );
}

/* ---------- Toolbar ---------- */
export const Toolbar = ({ children, label, className = "" }: { children: ReactNode; label: string; className?: string }) => (
  <div className={`ds-toolbar ${className}`} role="toolbar" aria-label={label}>
    {children}
  </div>
);
export const ToolbarSep = () => <span className="ds-sep" aria-hidden />;

/* ---------- Panel: titled section, collapsible ---------- */
export function Panel({ title, children, defaultOpen = true, actions, id }: { title: string; children: ReactNode; defaultOpen?: boolean; actions?: ReactNode; id?: string }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="ds-panel" id={id}>
      <header>
        <button type="button" className="ds-panel-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
          <ChevronDown size={14} style={{ transform: open ? "none" : "rotate(-90deg)", transition: "transform .2s" }} />
          <h3>{title}</h3>
        </button>
        {actions}
      </header>
      {open && <div className="ds-panel-body">{children}</div>}
    </section>
  );
}

/* ---------- Tabs ---------- */
export function Tabs<T extends string>({ value, onChange, tabs, label }: { value: T; onChange: (v: T) => void; tabs: { value: T; label: ReactNode; badge?: number }[]; label: string }) {
  const onKey = (e: React.KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.value === value);
    if (e.key === "ArrowRight") onChange(tabs[(i + 1) % tabs.length].value);
    else if (e.key === "ArrowLeft") onChange(tabs[(i - 1 + tabs.length) % tabs.length].value);
  };
  return (
    <div className="ds-tabs" role="tablist" aria-label={label} onKeyDown={onKey}>
      {tabs.map((t) => (
        <button key={t.value} role="tab" type="button" aria-selected={value === t.value} tabIndex={value === t.value ? 0 : -1} className={value === t.value ? "on" : ""} onClick={() => onChange(t.value)}>
          {t.label}
          {t.badge ? <span className="ds-badge">{t.badge}</span> : null}
        </button>
      ))}
    </div>
  );
}

/* ---------- Slider ---------- */
export function Slider({ value, min, max, step = 1, onChange, label }: { value: number; min: number; max: number; step?: number; onChange: (v: number) => void; label: string }) {
  return <input className="ds-slider" type="range" min={min} max={max} step={step} value={value} aria-label={label} onChange={(e) => onChange(+e.target.value)} />;
}

/* ---------- Popover + Menu ---------- */
const PopCtx = createContext<() => void>(() => {});

export function Popover({ trigger, children, align = "left", label }: { trigger: ReactNode; children: ReactNode; align?: "left" | "right"; label: string }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ left: number; top: number; up: boolean } | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  // the menu is drawn at the top of the page (a portal), so a card or panel that clips its content (overflow: hidden) cannot cut it off
  const place = useCallback(() => {
    const b = ref.current?.getBoundingClientRect();
    if (!b) return;
    const w = Math.max(210, menu.current?.offsetWidth || 210);
    const h = menu.current?.offsetHeight || 240;
    const up = b.bottom + 4 + h > window.innerHeight - 8 && b.top - 4 - h > 8;
    const left = Math.max(8, Math.min(align === "right" ? b.right - w : b.left, window.innerWidth - w - 8));
    setPos({ left, top: up ? b.top - 4 - h : b.bottom + 4, up });
  }, [align]);
  useLayoutEffect(() => {
    if (open) place();
  }, [open, place]);
  useEffect(() => {
    if (!open) return;
    const inside = (t: EventTarget | null) => (ref.current?.contains(t as Node) || menu.current?.contains(t as Node)) ?? false;
    const down = (e: MouseEvent) => !inside(e.target) && setOpen(false);
    const key = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const away = () => setOpen(false);
    window.addEventListener("mousedown", down);
    window.addEventListener("keydown", key);
    window.addEventListener("resize", away);
    window.addEventListener("scroll", away, true);
    return () => {
      window.removeEventListener("mousedown", down);
      window.removeEventListener("keydown", key);
      window.removeEventListener("resize", away);
      window.removeEventListener("scroll", away, true);
    };
  }, [open]);
  return (
    <div className="ds-pop" ref={ref}>
      <button type="button" className="btn ghost sm ds-pop-btn" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
        {trigger}
      </button>
      {open &&
        createPortal(
          <div ref={menu} className={`ds-menu fixed ${pos?.up ? "up" : ""}`} role="menu" aria-label={label}
            style={{ left: pos?.left ?? -9999, top: pos?.top ?? -9999 }}>
            <PopCtx.Provider value={close}>{children}</PopCtx.Provider>
          </div>,
          document.body
        )}
    </div>
  );
}

export function MenuItem({ children, onClick, keys, disabled, checked }: { children: ReactNode; onClick: () => void; keys?: string; disabled?: boolean; checked?: boolean }) {
  const close = useContext(PopCtx);
  return (
    <button type="button" role="menuitem" className="ds-item" disabled={disabled} aria-checked={checked} onClick={() => { onClick(); close(); }}>
      <span className="grow">{children}</span>
      {checked ? <span aria-hidden>✓</span> : null}
      {keys ? <Kbd>{keys}</Kbd> : null}
    </button>
  );
}
export const MenuSep = () => <div className="ds-menu-sep" role="separator" />;

/* ---------- Sheet: slide-over panel ---------- */
export function Sheet({ title, onClose, children, side = "right", footer }: { title: string; onClose: () => void; children: ReactNode; side?: "right" | "left"; footer?: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);
  return (
    <div className="ds-sheet-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className={`ds-sheet ${side}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref}>
        <header>
          <h2 className="grow">{title}</h2>
          <button type="button" className="btn ghost icon sm" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </header>
        <div className="ds-sheet-body">{children}</div>
        {footer && <footer>{footer}</footer>}
      </aside>
    </div>
  );
}

/* ---------- resizable sizes (kept in localStorage) ---------- */
export function useSize(key: string, initial: number, min: number, max: number) {
  const [size, setSize] = useState<number>(() => {
    try {
      const v = Number(localStorage.getItem("vt-size-" + key));
      return v >= min && v <= max ? v : initial;
    } catch {
      return initial;
    }
  });
  const set = useCallback(
    (v: number) => {
      const n = v < 0 ? initial : Math.max(min, Math.min(max, Math.round(v)));
      setSize(n);
      try {
        localStorage.setItem("vt-size-" + key, String(n));
      } catch {
        /* storage may be blocked */
      }
    },
    [key, min, max, initial]
  );
  return [size, set] as const;
}

/** A draggable divider. `dir` is the axis it resizes along; `invert` when the panel grows as the pointer moves left/up. */
export function Splitter({ dir, size, onSize, invert = false, label }: { dir: "x" | "y"; size: number; onSize: (n: number) => void; invert?: boolean; label: string }) {
  const start = useRef<{ p: number; s: number } | null>(null);
  const move = useCallback(
    (e: PointerEvent) => {
      if (!start.current) return;
      const d = (dir === "x" ? e.clientX : e.clientY) - start.current.p;
      onSize(start.current.s + (invert ? -d : d));
    },
    [dir, invert, onSize]
  );
  const up = useCallback(() => {
    start.current = null;
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    document.body.classList.remove("ds-resizing");
  }, [move]);
  return (
    <div
      className={`ds-splitter ${dir}`}
      role="separator"
      aria-orientation={dir === "x" ? "vertical" : "horizontal"}
      aria-valuenow={size}
      aria-label={label}
      tabIndex={0}
      onPointerDown={(e) => {
        start.current = { p: dir === "x" ? e.clientX : e.clientY, s: size };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", up);
        document.body.classList.add("ds-resizing");
      }}
      onKeyDown={(e) => {
        const step = e.shiftKey ? 40 : 12;
        const grow = dir === "x" ? "ArrowRight" : "ArrowDown";
        const shrink = dir === "x" ? "ArrowLeft" : "ArrowUp";
        if (e.key === grow) onSize(size + (invert ? -step : step));
        else if (e.key === shrink) onSize(size + (invert ? step : -step));
      }}
      onDoubleClick={() => onSize(-1)}
    />
  );
}

/* ---------- Steps: an Apple-style setup sheet (Cancel · Step n of N · Done, large title, grouped rows, dots, Back / Continue) ---------- */
export interface StepDef {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  body: ReactNode | ((go: { next: () => void; back: () => void }) => ReactNode);
  /** The footer's forward button for this step. Hidden, or quiet (not blue), when the body has the one main action of the screen. */
  next?: { label?: string; primary?: boolean; hidden?: boolean; onClick?: () => void };
  /** Not reachable yet (its dot is off and the forward button stops before it), with why. */
  locked?: string;
}
export function Steps({ label, steps, onClose, onDone, onStep, start = 0, doneLabel, headerDone = true, className = "", cancelLabel }: { label: string; steps: StepDef[]; onClose: () => void; onDone?: () => void; onStep?: (i: number) => void; start?: number; doneLabel?: string; headerDone?: boolean; className?: string; cancelLabel?: string }) {
  const t = useT();
  const [i, setI0] = useState(Math.min(start, steps.length - 1));
  const setI = (n: number) => { setI0(n); onStep?.(n); };
  const ref = useRef<HTMLDivElement>(null);
  const sheet = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);
  useEffect(() => {                                              // focus goes back where it was when the sheet closes
    const before = document.activeElement as HTMLElement | null;
    return () => { try { before?.focus?.(); } catch { /* gone */ } };
  }, []);
  useEffect(() => ref.current?.focus(), [i]);
  // a modal keeps the keyboard inside it: Tab from the last control goes to the first, Shift+Tab from the first to the last
  const trap = (e: React.KeyboardEvent) => {
    if (e.key !== "Tab" || !sheet.current) return;
    const all = [...sheet.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])')]
      .filter((el) => el.offsetParent !== null || el === document.activeElement);
    if (!all.length) return;
    const first = all[0], lastEl = all[all.length - 1], at = document.activeElement;
    if (e.shiftKey && (at === first || at === ref.current)) { e.preventDefault(); lastEl.focus(); }
    else if (!e.shiftKey && at === lastEl) { e.preventDefault(); first.focus(); }
  };
  const s = steps[i];
  const last = i === steps.length - 1;
  const reachable = (k: number) => !steps.slice(1, k + 1).some((st) => st.locked);
  const forward = s.next ?? {};
  const nextLocked = !last && !reachable(i + 1);
  return (
    <div className="ios-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`ios-sheet ${className}`} role="dialog" aria-modal="true" aria-label={label} ref={sheet} onKeyDown={trap}>
        <header className="ios-nav">
          <button type="button" className="ios-link" onClick={onClose}>{cancelLabel ?? t("ds.cancel")}</button>
          <span className="ios-nav-title">{t("ds.step").replace("{i}", String(i + 1)).replace("{n}", String(steps.length))}</span>
          {headerDone ? <button type="button" className="ios-link strong" onClick={onDone ?? onClose}>{t("ds.done")}</button> : <span />}
        </header>
        <div className="ios-body" key={i} tabIndex={-1} ref={ref}>
          {s.icon && <div className="ios-icon">{s.icon}</div>}
          <h2 className="ios-title">{s.title}</h2>
          {s.subtitle && <p className="ios-sub">{s.subtitle}</p>}
          {typeof s.body === "function" ? s.body({ next: () => !last && setI(i + 1), back: () => i > 0 && setI(i - 1) }) : s.body}
        </div>
        <footer className="ios-foot">
          <div className="ios-dots" role="tablist" aria-label="Steps">
            {steps.map((st, k) => (
              <button key={k} type="button" role="tab" aria-selected={k === i} aria-label={`${k + 1}. ${st.title}${!reachable(k) && st.locked ? ` (${st.locked})` : ""}`} title={!reachable(k) ? st.locked : undefined}
                className={k === i ? "on" : ""} disabled={k !== i && !reachable(k)} onClick={() => setI(k)} />
            ))}
          </div>
          <div className="row" style={{ gap: 8 }}>
            {i > 0 && <button type="button" className="btn" onClick={() => setI(i - 1)}>{t("ds.back")}</button>}
            {!forward.hidden && (
              <button type="button" className={forward.primary === false ? "btn" : "btn primary"} disabled={nextLocked && !forward.onClick}
                onClick={() => forward.onClick ? forward.onClick() : last ? (onDone ?? onClose)() : setI(i + 1)}>
                {forward.label ?? (last ? (doneLabel ?? t("ds.done")) : t("ds.continue"))}
              </button>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
}

/* grouped inset list, as in iOS Settings: a caption above, rows with the label left and the control right, a note below */
export function Group({ title, note, children }: { title?: string; note?: ReactNode; children: ReactNode }) {
  return (
    <section className="ios-group">
      {title && <h3>{title}</h3>}
      <div className="ios-rows">{children}</div>
      {note && <p className="ios-note">{note}</p>}
    </section>
  );
}
export function Row({ label, children, stack }: { label: ReactNode; children?: ReactNode; stack?: boolean }) {
  return (
    <div className={`ios-row ${stack ? "stack" : ""}`}>
      <span className="ios-row-label">{label}</span>
      {children && <div className="ios-row-ctl">{children}</div>}
    </div>
  );
}
