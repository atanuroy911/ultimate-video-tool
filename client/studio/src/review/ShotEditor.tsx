// The visual editor for a code-native shot (docs/plans/PLAN-CODE-NATIVE-EDITOR.MD, C3).
// The shot runs in a sandboxed frame with no access to the Studio (server/renderer/runtime/vt-shot-bridge.js answers messages); every change here is an
// override saved next to the shot's code, never a change to the code. Click an element to select it, drag it, pull the corner to scale, the top dot to rotate.
import { Eye, EyeOff, Pause, Play, Redo2, RotateCcw, Undo2, X } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { del, get, post as apiPost, put } from "../api";
import { toast } from "../store";
import * as E from "./shotEdit";
import "./shot-editor.css";

const ShotCode = lazy(() => import("./ShotCode"));          // CodeMirror loads only when the code is opened

interface ShotInfo { id: string; title: string; duration: number; width: number; height: number; knobs: { name: string; label?: string; kind?: string }[]; html: string; ids: string[]; overrides: E.Overrides }
interface Ready { ids: string[]; texts: Record<string, string>; colours: Record<string, string | null>; duration: number; width: number; height: number }
type Drag = { kind: "move" | "scale" | "rotate"; id: string; start: E.ElementEdit; rect: E.Rect; from: [number, number] };

const WEIGHTS = [300, 400, 500, 600, 700, 800, 900];

export default function ShotEditor({ projectId, shotId, onClose, startInStudio }: { projectId: string; shotId: string; onClose: () => void; startInStudio?: boolean }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const [info, setInfo] = useState<ShotInfo | null>(null);
  const [ready, setReady] = useState<Ready | null>(null);
  const [hist, setHist] = useState<E.History>(E.historyOf(E.EMPTY));
  const [live, setLive] = useState<E.Overrides | null>(null);       // during a drag: shown, not yet a step in the history
  const [sel, setSel] = useState<string | null>(null);
  const [rect, setRect] = useState<E.Rect | null>(null);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [scale, setScale] = useState(0.3);
  const [saving, setSaving] = useState<"saved" | "saving" | "error">("saved");
  const [tab, setTab] = useState<"design" | "code" | "studio">("design");
  const [studio, setStudio] = useState<{ url?: string; state: "off" | "starting" | "open" | "saving"; note?: string }>({ state: "off" });
  const [pageRev, setPageRev] = useState(0);                       // bumps when the code changed: the frame loads the new page
  const drag = useRef<Drag | null>(null);
  const shown = live ?? hist.now;
  const base = `/api/projects/${encodeURIComponent(projectId)}/shots/${encodeURIComponent(shotId)}`;

  const post = useCallback((m: any) => frame.current?.contentWindow?.postMessage(m, "*"), []);

  useEffect(() => {
    let off = false;
    get<ShotInfo>(base).then((s) => { if (!off) { setInfo(s); setHist(E.historyOf(s.overrides)); setT(Math.max(0, s.duration - 0.05)); } })
      .catch((e) => toast(`Could not open the shot: ${e.message}`, "err"));
    return () => { off = true; };
  }, [base]);

  // The frame answers by message; only messages from our own frame count.
  useEffect(() => {
    const on = (e: MessageEvent) => {
      if (e.source !== frame.current?.contentWindow || !e.data || typeof e.data.vt !== "string") return;
      if (e.data.vt === "shot-ready") setReady(e.data);
      else if (e.data.vt === "shot-picked") { setSel(e.data.id); setRect(e.data.rect); }
      else if (e.data.vt === "shot-rect" && e.data.id === selRef.current) setRect(e.data.rect);
    };
    window.addEventListener("message", on);
    return () => window.removeEventListener("message", on);
  }, []);
  const selRef = useRef(sel);
  selRef.current = sel;

  // Keep the frame showing the current edits and moment, and the selection box where the element is now.
  useEffect(() => { if (ready) { post({ vt: "shot-overrides", overrides: shown }); post({ vt: "shot-seek", t }); if (sel) post({ vt: "shot-rect", id: sel }); } }, [ready, shown, t, sel, post]);

  // Fit the shot into the pane.
  useEffect(() => {
    const el = box.current;
    if (!el || !info) return;
    const fit = () => setScale(Math.min((el.clientWidth - 24) / info.width, (el.clientHeight - 24) / info.height));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [info]);

  // Play: step the moment forward in real time; the frame seeks, nothing else is drawn.
  useEffect(() => {
    if (!playing || !info) return;
    let raf = 0, last = performance.now();
    const step = (now: number) => {
      setT((v) => { const n = v + (now - last) / 1000; if (n >= info.duration) { setPlaying(false); return info.duration - 0.01; } return n; });
      last = now;
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing, info]);

  // Save a moment after the last change; the server checks every value.
  const saved = useRef<string>("");
  useEffect(() => {
    if (!info) return;
    const body = JSON.stringify(hist.now);
    if (!saved.current) { saved.current = body; return; }
    if (body === saved.current) return;
    setSaving("saving");
    const timer = setTimeout(() => {
      put(`${base}/overrides`, { overrides: hist.now })
        .then(() => { saved.current = body; setSaving("saved"); })
        .catch((e) => { setSaving("error"); toast(`The edit was not saved: ${e.message}`, "err"); });
    }, 400);
    return () => clearTimeout(timer);
  }, [hist.now, info, base]);

  const change = (next: E.Overrides) => setHist((h) => E.commit(h, next));

  /** New code: the server checks it, then the frame loads it; the visual edits are kept (an edit whose element is gone is listed, not lost). */
  const saveCode = async (code: string): Promise<boolean> => {
    try {
      const s = await put<ShotInfo>(base, { html: code });
      setInfo((old) => (old ? { ...old, ...s, overrides: old.overrides } : s));
      setReady(null);
      setPageRev((n) => n + 1);
      return true;
    } catch (e: any) {
      toast(`The code was not saved: ${e.message}`, "err");
      return false;
    }
  };
  /** O2 (docs/plans/PLAN-OPENMOTION.MD): the HyperFrames Studio edits this shot's code directly. The server starts it on this computer and copies its
   *  edits back into the shot when the person saves, leaves the Studio tab or closes the editor. */
  const reload = useCallback(async () => {
    const s = await get<ShotInfo>(base);
    setInfo(s);
    setReady(null);
    setPageRev((n) => n + 1);
  }, [base]);
  // The Studio refuses to be shown inside another page's frame (it sends X-Frame-Options), so it opens as its own window: an app window in the
  // desktop app, a tab in a browser. Same window name: opening again brings the same window back.
  const studioWin = useRef<Window | null>(null);
  const showStudio = (url: string) => { studioWin.current = window.open(url, "vt-hyperframes-studio"); };
  const openStudio = async () => {
    setSel(null);
    setTab("studio");
    if (studio.state === "open") return;
    setStudio({ state: "starting" });
    try {
      const s = await apiPost<{ url: string }>(`${base}/studio`);
      setStudio({ state: "open", url: s.url });
      showStudio(s.url);
    } catch (e: any) {
      setStudio({ state: "off", note: e.message });
      toast(`The Studio did not open: ${e.message}`, "err");
    }
  };
  useEffect(() => { if (startInStudio) void openStudio(); }, []); // eslint-disable-line react-hooks/exhaustive-deps   -- a scene made of HTML, opened from its menu: straight into HyperFrames
  const saveStudio = async () => {
    setStudio((s) => ({ ...s, state: "saving" }));
    try {
      const got = await apiPost<{ saved: boolean; changed?: boolean; reason?: string }>(`${base}/studio/save`);
      setStudio((s) => ({ ...s, state: "open", note: got.saved ? (got.changed ? "Saved into the video." : "Nothing new to save.") : got.reason }));
      if (got.changed) await reload();
    } catch (e: any) {
      setStudio((s) => ({ ...s, state: "open", note: e.message }));
    }
  };
  const closeStudio = useCallback(async (then?: () => void) => {
    try {
      const got = await del<{ saved?: boolean; changed?: boolean; reason?: string }>(`${base}/studio`);
      if (got.saved === false && got.reason) toast(got.reason, "err");
      if (got.changed) await reload();
    } catch (e: any) {
      toast(`The Studio's edits were not saved: ${e.message}`, "err");
    }
    try { studioWin.current?.close(); } catch { /* a window we may not close */ }
    studioWin.current = null;
    setStudio({ state: "off" });
    then?.();
  }, [base, reload]);
  const studioOn = useRef(false);
  studioOn.current = studio.state !== "off";
  useEffect(() => () => { if (studioOn.current) void del(`${base}/studio`).catch(() => {}); }, [base]);
  const leaveStudio = (next: "design" | "code") => { if (studio.state !== "off") void closeStudio(); setTab(next); };

  const orphans = Object.keys(hist.now.elements).filter((id) => info && !info.ids.includes(id));
  const el = sel ? shown.elements[sel] ?? {} : null;
  const declared = useMemo(() => E.declaredKnobs(info?.html ?? ""), [info]);

  const toShot = (e: { clientX: number; clientY: number }): [number, number] => {
    const r = frame.current!.getBoundingClientRect();
    return [(e.clientX - r.left) / scale, (e.clientY - r.top) / scale];
  };

  const down = (e: React.PointerEvent, kind: Drag["kind"]) => {
    if (!sel || !rect) return;
    e.stopPropagation();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    drag.current = { kind, id: sel, start: { ...(hist.now.elements[sel] ?? {}) }, rect, from: toShot(e) };
  };
  const moveTo = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const p = toShot(e);
    setLive(d.kind === "move" ? E.moved(hist.now, d.id, d.start, p[0] - d.from[0], p[1] - d.from[1])
      : d.kind === "scale" ? E.scaled(hist.now, d.id, d.start, d.rect, d.from, p)
      : E.rotated(hist.now, d.id, d.start, d.rect, d.from, p, e.shiftKey));
  };
  const up = () => {
    if (!drag.current) return;
    drag.current = null;
    if (live) change(live);
    setLive(null);
  };

  const onKey = (e: React.KeyboardEvent) => {
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === "z") { e.preventDefault(); setHist((h) => (e.shiftKey ? E.redo(h) : E.undo(h))); return; }
    if (mod && e.key.toLowerCase() === "y") { e.preventDefault(); setHist(E.redo); return; }
    const dir = ({ ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] } as Record<string, number[]>)[e.key];
    if (dir && sel && (e.target as HTMLElement).tagName !== "INPUT" && (e.target as HTMLElement).tagName !== "TEXTAREA") {
      e.preventDefault();
      const step = e.shiftKey ? 10 : 1, cur = hist.now.elements[sel] ?? {};
      change(E.moved(hist.now, sel, cur, dir[0] * step, dir[1] * step));
    }
    if (e.key === "Escape") setSel(null);
  };

  if (!info) return <div className="shot-editor loading" role="status">Opening the shot…</div>;
  const r = rect && sel ? { left: rect[0] * scale, top: rect[1] * scale, width: rect[2] * scale, height: rect[3] * scale } : null;

  return (
    <div className="shot-editor" onKeyDown={onKey} tabIndex={-1} aria-label={`Shot ${info.title}`}>
      <div className="shot-bar">
        <strong>{info.title}</strong>
        <div className="shot-tabs" role="tablist" aria-label="View">
          <button role="tab" aria-selected={tab === "design"} className={tab === "design" ? "on" : ""} onClick={() => leaveStudio("design")}>Design</button>
          <button role="tab" aria-selected={tab === "code"} className={tab === "code" ? "on" : ""} onClick={() => { setSel(null); leaveStudio("code"); }}>Code</button>
          <button role="tab" aria-selected={tab === "studio"} className={tab === "studio" ? "on" : ""} onClick={openStudio}
                  title="Edit in the HyperFrames Studio: move, resize, retype and animate the shot's own code, with layers and a timeline">Studio</button>
        </div>
        {tab === "studio" ? (
          <>
            <span className="muted small" role="status">{studio.state === "starting" ? "Starting the Studio…" : studio.state === "saving" ? "Saving…" : studio.note ?? "Edits go into the video when you save or leave the Studio."}</span>
            <span className="grow" />
            <button className="btn sm" disabled={studio.state !== "open"} onClick={saveStudio}>Save to video</button>
          </>
        ) : (
          <span className="muted small">{saving === "saving" ? "Saving…" : saving === "error" ? "Not saved" : "Saved"}</span>
        )}
        <span className="grow" />
        <button className="btn ghost icon sm" aria-label="Undo" title="Undo (Ctrl+Z)" disabled={!hist.past.length} onClick={() => setHist(E.undo)}><Undo2 size={15} /></button>
        <button className="btn ghost icon sm" aria-label="Redo" title="Redo (Ctrl+Shift+Z)" disabled={!hist.future.length} onClick={() => setHist(E.redo)}><Redo2 size={15} /></button>
        <button className="btn ghost sm" onClick={() => change(E.EMPTY)} disabled={!Object.keys(hist.now.elements).length && !Object.keys(hist.now.knobs).length} title="Remove every edit: the shot as its code draws it">Reset all</button>
        <button className="btn ghost icon sm" aria-label="Close the shot editor" onClick={() => (studio.state !== "off" ? closeStudio(onClose) : onClose())}><X size={16} /></button>
      </div>
      {tab === "studio" ? (
        <div className="shot-body shot-studio">
          {studio.url ? (
            <div className="shot-studio-card">
              <h3>{info.title} is open in the Studio</h3>
              <p className="small muted">Select anything on the canvas or in Layers to move, resize, retype or animate it; the timeline and keyframes are under the picture.
                Come back here and press <b>Save to video</b>, or <b>Done</b> to save and close the Studio.</p>
              <div className="row">
                <button className="btn sm" onClick={() => showStudio(studio.url!)}>Show the Studio</button>
                <button className="btn sm" disabled={studio.state !== "open"} onClick={() => closeStudio(() => setTab("design"))}>Done</button>
              </div>
            </div>
          ) : <p className="small muted" role="status">{studio.state === "starting" ? "Starting the Studio for this shot…" : studio.note ?? ""}</p>}
        </div>
      ) : (
      <div className="shot-body">
        <div className="shot-stage" ref={box}>
          <div className="shot-canvas" style={{ width: info.width * scale, height: info.height * scale }}
               onPointerDown={(e) => { if (!drag.current && tab === "design") { const p = toShot(e); post({ vt: "shot-pick", x: p[0], y: p[1] }); } }}
               onPointerMove={moveTo} onPointerUp={up} onPointerCancel={up}>
            <iframe ref={frame} title={`Shot ${info.title}`} sandbox="allow-scripts" src={`${base}/page/index.html?editor=1&v=${pageRev}`}
                    style={{ width: info.width, height: info.height, transform: `scale(${scale})` }} />
            {r && (
              <div className="shot-sel" style={r} onPointerDown={(e) => down(e, "move")} aria-label={`Selected: ${sel}. Drag to move; arrow keys move by 1, with shift by 10.`}>
                <span className="shot-handle scale" onPointerDown={(e) => down(e, "scale")} title="Drag to scale" />
                <span className="shot-handle rotate" onPointerDown={(e) => down(e, "rotate")} title="Drag to rotate (shift: 15° steps)" />
                <span className="shot-tag">{sel}</span>
              </div>
            )}
          </div>
          <div className="shot-time">
            <button className="btn ghost icon sm" aria-label={playing ? "Pause" : "Play"} onClick={() => { if (!playing && t >= info.duration - 0.02) setT(0); setPlaying(!playing); }}>{playing ? <Pause size={15} /> : <Play size={15} />}</button>
            <input type="range" min={0} max={info.duration} step={0.01} value={t} onChange={(e) => { setPlaying(false); setT(+e.target.value); }} aria-label="Moment in the shot" />
            <span className="small muted mono">{t.toFixed(2)} / {info.duration.toFixed(2)} s</span>
          </div>
        </div>
        {tab === "code" ? (
          <div className="shot-code-pane">
            <Suspense fallback={<p className="small muted" role="status">Opening the code…</p>}>
              <ShotCode key={shotId} code={info.html} onSave={saveCode} dark={document.documentElement.dataset.theme === "dark" || matchMedia("(prefers-color-scheme: dark)").matches} />
            </Suspense>
            {orphans.length > 0 && (
              <p className="small shot-orphans">Edits kept for elements the code no longer has: {orphans.map((id) => (
                <button key={id} className="btn ghost sm" onClick={() => change(E.resetElement(hist.now, id))} title="Remove this edit">{id} ×</button>))}</p>
            )}
          </div>
        ) : (
        <aside className="shot-side" aria-label="Shot settings">
          {sel && el ? (
            <section>
              <h3>{sel} <button className="btn ghost icon sm" aria-label="Reset this element" title="Back to how the code draws it" onClick={() => change(E.resetElement(hist.now, sel))}><RotateCcw size={14} /></button>
                <button className="btn ghost icon sm" aria-label={el.hidden ? "Show" : "Hide"} onClick={() => change(E.editElement(hist.now, sel, { hidden: !el.hidden }))}>{el.hidden ? <EyeOff size={14} /> : <Eye size={14} />}</button></h3>
              {ready?.texts[sel] !== undefined && (
                <label>Text<textarea key={`${sel}-${hist.past.length}`} defaultValue={el.text ?? ready.texts[sel]} rows={3}
                  onBlur={(e) => change(E.editElement(hist.now, sel, { text: e.target.value === ready.texts[sel] ? undefined : e.target.value }))} /></label>
              )}
              <div className="shot-grid">
                {(["x", "y", "scale", "rotate"] as const).map((k) => (
                  <label key={k}>{k === "rotate" ? "Turn °" : k === "scale" ? "Size ×" : k.toUpperCase()}
                    <input type="number" step={k === "scale" ? 0.05 : 1} value={el[k] ?? (k === "scale" ? 1 : 0)}
                      onChange={(e) => e.target.value !== "" && change(E.editElement(hist.now, sel, { [k]: +e.target.value }))} /></label>
                ))}
              </div>
              <div className="shot-grid">
                <label>Colour<input type="color" value={E.asHex(String(el.style?.color ?? "")) ?? ready?.colours?.[sel] ?? ""} onChange={(e) => change(E.editElement(hist.now, sel, { style: { color: e.target.value } }))} /></label>
                <label>Text size<input type="number" min={6} max={600} value={Number(el.style?.fontSize ?? "") || ""} placeholder="as coded" onChange={(e) => change(E.editElement(hist.now, sel, { style: { fontSize: e.target.value === "" ? undefined : +e.target.value } }))} /></label>
                <label>Weight<select value={String(el.style?.fontWeight ?? "")} onChange={(e) => change(E.editElement(hist.now, sel, { style: { fontWeight: e.target.value === "" ? undefined : +e.target.value } }))}>
                  <option value="">as coded</option>{WEIGHTS.map((w) => <option key={w} value={w}>{w}</option>)}</select></label>
                <label>Opacity<input type="range" min={0} max={1} step={0.05} value={Number(el.style?.opacity ?? 1)} onChange={(e) => change(E.editElement(hist.now, sel, { style: { opacity: +e.target.value === 1 ? undefined : +e.target.value } }))} /></label>
              </div>
            </section>
          ) : (
            <p className="small muted">Click something in the shot to change it. Its code stays as written; your changes are kept apart and can be undone.</p>
          )}
          {info.knobs.length > 0 && (
            <section>
              <h3>Whole shot</h3>
              {info.knobs.map((k) => {
                const value = shown.knobs[k.name] ?? declared[k.name] ?? "";
                const hex = E.asHex(value);
                return (
                  <label key={k.name} className="shot-knob">{k.label ?? k.name}
                    {k.kind === "colour" && hex !== null
                      ? <input type="color" value={hex} onChange={(e) => change(E.setKnob(hist.now, k.name, e.target.value))} />
                      : <input type="text" defaultValue={value} key={`${k.name}-${value}`} onBlur={(e) => change(E.setKnob(hist.now, k.name, e.target.value === declared[k.name] ? null : e.target.value))} />}
                    {hist.now.knobs[k.name] !== undefined && <button className="btn ghost icon sm" aria-label={`Reset ${k.label ?? k.name}`} onClick={() => change(E.setKnob(hist.now, k.name, null))}><RotateCcw size={13} /></button>}
                  </label>
                );
              })}
            </section>
          )}
          {ready && <p className="small muted">Selectable: {ready.ids.join(", ") || "nothing (the shot has no data-vt-id)"}</p>}
        </aside>
        )}
      </div>
      )}
    </div>
  );
}
