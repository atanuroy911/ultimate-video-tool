import { ArrowDown, ArrowUp, Copy, Crosshair, Diamond, Play, Plus, Trash2, Users } from "lucide-react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { StoryScene, stageFor } from "@story/StoryScene";
import { SPEC, STORE, setSpeak } from "@story/data";
import { animState } from "@story/engine/anim";
import { put } from "../../api";
import { useFetch } from "../../hooks";
import { toast } from "../../store";
import type { El, MediaItem } from "../../types";
import { Seg } from "../../ui";
import { timeStore } from "../timeStore";
import JsonField from "../JsonField";
import "./story.css";

/* Cartoon 2 scene editor. The stage is the same engine source the renderer bundles (server/renderer/story/src), drawn at the playhead, so what
   you drag here is exactly what is exported. Every item is a layer; every property the engine reads has a field (the catalog comes from
   GET /api/story/catalog, vt/story/catalog.py), and anything else can be edited as JSON. Times are video seconds. */

type Spec = { k: string; label?: string; min?: number; max?: number; step?: number; options?: string[]; key?: string; default?: any };
type Catalog = {
  elements: Record<string, { group: string; label: string; props: Record<string, Spec> }>;
  common: Record<string, Spec>; backgrounds: Record<string, { label: string; props: Record<string, Spec> }>;
  background_common: Record<string, Spec>; character: Record<string, Spec>;
};
type Item = Record<string, any> & { type: string };
type Cast = Record<string, Record<string, any>>;
interface Props {
  value: El; onChange: (v: El, immediate?: boolean) => void;
  cast: Cast; projectId: string; onCastSaved: () => void;
  aspect: string; language: string; start: number; end: number; seek?: (t: number) => void; media: MediaItem[];
  extrasOnly?: boolean;                 // Cartoon 1's extras: only the items, drawn over a see-through stage
}

const SIZE: Record<string, [number, number]> = { "9:16": [1080, 1920], "16:9": [1920, 1080], "1:1": [1080, 1080] };
const r2 = (v: number) => Math.round(v * 100) / 100;
const words = (s: string) => s.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/^./, (c) => c.toUpperCase());

/** Sensible starting props for a new item, so it is visible and readable at once. */
function starter(type: string, at: number, cast: Cast): Item {
  const firstChar = Object.keys(cast)[0];
  const base: Item = { type, x: 270, y: 420, at: r2(at) };
  const extra: Record<string, Item | Record<string, any>> = {
    person: { char: firstChar, pose: "stand", s: 0.8, y: 520, expr: "smile" }, mini: { char: firstChar, s: 2, y: 620 }, crowd: { count: 5, y: 600 },
    bubble: { text: "Hi!", y: 220 }, thought: { text: "?", y: 260 }, title: { text: "Title", size: 52, y: 200 }, text: { text: "Text", size: 36 },
    pill: { text: "Label" }, card: { title: "Card", text: "Text", w: 300, h: 200 }, quote: { text: "A quote" }, badge: { text: "1" },
    stamp: { text: "DONE", enter: "stamp", rot: -10 }, steps: { items: ["First", "Second"], y: 260 }, paper: { title: "Paper" },
    counter: { from: 0, to: 100, latin: true }, gauge: { label: "Level", value: 0.7, y: 300 }, progress: { label: "Progress", value: 0.6 },
    bars: { values: [2, 5, 3], labels: ["A", "B", "C"], y: 560 }, calendar: { count: 5, x: 110, y: 260 }, clock: { hour: 10 }, heart: { s: 1.5 },
    icon: { name: "star" }, phone: { header: "Message", lines: [{ text: "Hello", at: r2(at + 0.3) }] }, door: { x: 420, y: 610 },
    bed: { y: 652 }, sofa: { y: 615 }, desk: { y: 654 }, particles: { kind: "sparkle", count: 20 }, arrow: { dx: 0, dy: 120 },
    shape: { shape: "rect", w: 120, h: 80, fill: "#E8B84A" }, image: { w: 240, h: 240 },
  };
  return { ...base, ...(extra[type] || {}) };
}

function label(it: Item, cat: Catalog | null, cast: Cast): string {
  const name = cat?.elements[it.type]?.label ?? it.type;
  const who = it.char ? cast[it.char]?.name || it.char : "";
  const text = it.text ?? it.title ?? it.label ?? it.header ?? it.name ?? (Array.isArray(it.items) ? it.items.join(", ") : "");
  return [name, who, text].filter(Boolean).join(" · ").slice(0, 44);
}

/* ------------------------------------------------------------------ one property field */
function Field({ name, spec, value, set, t, seek, cast, media }: { name: string; spec: Spec; value: any; set: (v: any) => void; t: number; seek?: (t: number) => void; cast: Cast; media: MediaItem[] }) {
  const title = spec.label ?? words(name);
  const unset = value === undefined || value === null || value === "";
  const clear = !unset && <button type="button" className="se-clear" aria-label={`Clear ${title}`} title="Back to the default" onClick={() => set(undefined)}>×</button>;
  switch (spec.k) {
    case "num":
      return <label className="se-f"><span>{title}{clear}</span><div className="se-num">
        <input type="range" min={spec.min} max={Math.min(spec.max ?? 100, 2000)} step={spec.step} value={value ?? spec.default ?? spec.min ?? 0} onChange={(e) => set(+e.target.value)} />
        <input type="number" step={spec.step} value={value ?? ""} placeholder={spec.default != null ? String(spec.default) : "auto"} onChange={(e) => set(e.target.value === "" ? undefined : +e.target.value)} />
      </div></label>;
    case "bool":
      return <label className="se-f se-check"><input type="checkbox" checked={!!value} onChange={(e) => set(e.target.checked || undefined)} /><span>{title}</span></label>;
    case "color":
      return <label className="se-f"><span>{title}{clear}</span><div className="se-color">
        <input type="color" value={/^#[0-9a-f]{6}$/i.test(value ?? "") ? value : "#888888"} onChange={(e) => set(e.target.value)} />
        <input value={value ?? ""} placeholder="default" onChange={(e) => set(e.target.value || undefined)} />
      </div></label>;
    case "enum":
      return <label className="se-f"><span>{title}</span><select value={value ?? ""} onChange={(e) => set(e.target.value || undefined)}>
        <option value="">Default</option>{(spec.options ?? []).filter(Boolean).map((o) => <option key={o} value={o}>{words(o)}</option>)}</select></label>;
    case "char":
      return <label className="se-f"><span>{title}</span><select value={value ?? ""} onChange={(e) => set(e.target.value || undefined)}>
        <option value="">Nobody</option>{Object.entries(cast).map(([id, c]) => <option key={id} value={id}>{c.name || id}</option>)}</select></label>;
    case "time":
      return <div className="se-f"><span>{title}{clear}</span><div className="se-time">
        <input type="number" step={0.05} value={value ?? ""} placeholder="scene start" onChange={(e) => set(e.target.value === "" ? undefined : +e.target.value)} />
        <button type="button" className="btn icon sm" title="Use the playhead" aria-label="Use the playhead" onClick={() => set(r2(t))}><Crosshair size={13} /></button>
        {!unset && seek && <button type="button" className="btn icon sm" title="Go there" aria-label="Go there" onClick={() => seek(value)}><Play size={13} /></button>}
      </div></div>;
    case "times": case "numbers":
      return <div className="se-f"><span>{title}{clear}</span><div className="se-time">
        <input value={Array.isArray(value) ? value.join(", ") : ""} placeholder="comma separated" onChange={(e) => { const v = e.target.value.split(",").map((x) => x.trim()).filter(Boolean).map(Number).filter((n) => !isNaN(n)); set(v.length ? v : undefined); }} />
        {spec.k === "times" && <button type="button" className="btn icon sm" title="Add the playhead" aria-label="Add the playhead" onClick={() => set([...(value ?? []), r2(t)].sort((a, b) => a - b))}><Plus size={13} /></button>}
      </div></div>;
    case "list":
      return <label className="se-f"><span>{title}{clear}</span><textarea rows={3} value={Array.isArray(value) ? value.join("\n") : ""} placeholder="one per line"
        onChange={(e) => { const v = e.target.value.split("\n"); set(v.some((x) => x.trim()) ? v : undefined); }} /></label>;
    case "schedule": {
      const rows: any[] = Array.isArray(value) ? value : [];
      const key = spec.key ?? "value";
      const setRow = (i: number, patch: any) => set(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
      return <div className="se-f"><span>{title}</span>
        {rows.map((r, i) => <div key={i} className="se-row">
          <input type="number" step={0.05} value={r.t} aria-label="At second" onChange={(e) => setRow(i, { t: +e.target.value })} />
          <select value={r[key] ?? ""} aria-label={key} onChange={(e) => setRow(i, { [key]: e.target.value })}>{(spec.options ?? []).map((o) => <option key={o} value={o}>{words(o)}</option>)}</select>
          <button type="button" className="btn icon sm" aria-label="Remove" onClick={() => { const n = rows.filter((_, j) => j !== i); set(n.length ? n : undefined); }}><Trash2 size={13} /></button>
        </div>)}
        <button type="button" className="btn sm" onClick={() => set([...rows, { t: r2(t), [key]: spec.options?.[0] }].sort((a, b) => a.t - b.t))}><Plus size={13} /> Change at the playhead</button>
      </div>;
    }
    case "lines": {
      const rows: any[] = Array.isArray(value) ? value : [];
      const setRow = (i: number, patch: any) => set(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
      return <div className="se-f"><span>{title}</span>
        {rows.map((r, i) => <div key={i} className="se-row">
          <input value={r.text ?? ""} aria-label="Line" onChange={(e) => setRow(i, { text: e.target.value })} />
          <input type="number" step={0.05} value={r.at ?? ""} placeholder="at" aria-label="Appears at" onChange={(e) => setRow(i, { at: e.target.value === "" ? undefined : +e.target.value })} />
          <button type="button" className="btn icon sm" aria-label="Remove" onClick={() => { const n = rows.filter((_, j) => j !== i); set(n.length ? n : undefined); }}><Trash2 size={13} /></button>
        </div>)}
        <button type="button" className="btn sm" onClick={() => set([...rows, { text: "New line", at: r2(t) }])}><Plus size={13} /> Line at the playhead</button>
      </div>;
    }
    case "media":
      return <label className="se-f"><span>{title}</span><select value={value ?? ""} onChange={(e) => set(e.target.value || undefined)}>
        <option value="">Choose a picture</option>{media.filter((m) => m.kind === "image" || m.kind === "gif").map((m) => <option key={m.id} value={m.id}>{m.caption || m.file}</option>)}</select></label>;
    case "keyframes":
      return null;                                         // its own tab
    case "json":
      return <JsonField title={title} value={value} set={set} />;
    default:
      return <label className="se-f"><span>{title}{clear}</span><input value={value ?? ""} onChange={(e) => set(e.target.value || undefined)} /></label>;
  }
}

function Fields({ specs, obj, set, t, seek, cast, media, skip = [] }: { specs: Record<string, Spec>; obj: Record<string, any>; set: (k: string, v: any) => void; t: number; seek?: (t: number) => void; cast: Cast; media: MediaItem[]; skip?: string[] }) {
  return <div className="se-fields">{Object.entries(specs).filter(([k]) => !skip.includes(k)).map(([k, sp]) =>
    <Field key={k} name={k} spec={sp} value={obj[k]} set={(v) => set(k, v)} t={t} seek={seek} cast={cast} media={media} />)}</div>;
}

/* ------------------------------------------------------------------ the editor */
export default function StoryEditor(p: Props) {
  const cat = useFetch<Catalog>("/api/story/catalog").data ?? null;
  const story = p.value as any as { bg: any; items: Item[]; tag?: string; push?: number; speak?: Record<string, number[][]> };
  const [draft, setDraft] = useState<Item[] | null>(null);         // items while a drag is under way (saved on release)
  const items = draft ?? story.items ?? [];
  const [sel, setSel] = useState<number | null>(null);
  const [tab, setTab] = useState<"look" | "place" | "time" | "move" | "json">("look");
  const [panel, setPanel] = useState<"layers" | "scene" | "cast">("layers");
  const [t, setT] = useState(() => Math.min(Math.max(timeStore.t, p.start), p.end - 0.01));
  const [record, setRecord] = useState(false);
  const [box, setBox] = useState<{ l: number; t: number; w: number; h: number } | null>(null);
  const [adding, setAdding] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const drag = useRef<{ i: number; x: number; y: number; base: Item[]; moved: boolean } | null>(null);

  useEffect(() => timeStore.subscribe((v) => { if (!drag.current) setT(Math.min(Math.max(v, p.start), p.end - 0.01)); }), [p.start, p.end]);
  useEffect(() => { if (sel != null && sel >= items.length) setSel(null); }, [items.length, sel]);

  const [W, H] = SIZE[p.aspect] ?? SIZE["9:16"];
  const stage = stageFor(W, H);
  const viewH = p.aspect === "9:16" ? 400 : p.aspect === "1:1" ? 300 : 210;
  const viewW = Math.round(viewH * W / H);

  // the engine reads these module settings while drawing (the editor shows the mouths closed; the preview shows them talking)
  SPEC.characters = p.cast as any;
  setSpeak((story.speak as any) || {});
  STORE.lang = p.language || "en";
  STORE.loud = () => 0;
  STORE.fonts = { head: "Georgia, serif", body: "Inter, system-ui, sans-serif" };
  Object.assign(STORE.stage, stage);
  STORE.uid = "ed";

  const save = (next: Partial<typeof story>, immediate = true) => p.onChange({ ...(p.value as any), ...next, edited: true }, immediate);
  const setItems = (next: Item[], immediate = true) => save({ items: next }, immediate);
  const patchItem = (i: number, patch: Record<string, any>) => {
    const next = items.map((it, j) => { if (j !== i) return it; const n = { ...it, ...patch }; for (const k of Object.keys(patch)) if (patch[k] === undefined) delete n[k]; return n; });
    setItems(next);
  };

  // selection outline: measured from the drawing itself, so it fits whatever the item is
  useLayoutEffect(() => {
    const svg = wrap.current?.querySelector("svg");
    const g = sel != null ? svg?.querySelector(`[data-item="${sel}"]`) : null;
    if (!svg || !g) { setBox(null); return; }
    const a = svg.getBoundingClientRect(), b = (g as SVGGElement).getBoundingClientRect();
    setBox(b.width || b.height ? { l: b.left - a.left, t: b.top - a.top, w: b.width, h: b.height } : null);
  }, [sel, t, items, viewW, viewH]);

  const scene = { s: p.start, e: p.end, bg: story.bg, push: 0, tag: story.tag, elements: items as any };
  const unitsPerPx = stage.w / viewW;

  /** Where an item is drawn at the playhead (keyframes included), in design units. */
  const shownAt = (it: Item) => animState(it as any, t, (t - p.start) * 30, p.start, p.end);
  const placeKey = (it: Item, x: number, y: number): Item => {
    const keyed = record || (it.move ?? []).some((m: any) => m.x !== undefined || m.y !== undefined);
    if (!keyed) return { ...it, x: r2(x), y: r2(y) };
    const tt = r2(t), move = [...(it.move ?? [])].filter((m: any) => Math.abs(m.t - tt) > 0.02);
    const same = (it.move ?? []).find((m: any) => Math.abs(m.t - tt) <= 0.02) ?? {};
    return { ...it, move: [...move, { ...same, t: tt, x: r2(x), y: r2(y) }].sort((a: any, b: any) => a.t - b.t) };
  };

  const down = (i: number, e: React.PointerEvent) => {
    e.stopPropagation();
    setSel(i);
    setPanel("layers");
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    drag.current = { i, x: e.clientX, y: e.clientY, base: items.map((x) => ({ ...x })), moved: false };
  };
  const move = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const dx = (e.clientX - d.x) * unitsPerPx, dy = (e.clientY - d.y) * unitsPerPx;
    if (!d.moved && Math.hypot(dx, dy) < 2) return;
    d.moved = true;
    const it = d.base[d.i], at = shownAt(it);
    const keyed = record || (it.move ?? []).some((m: any) => m.x !== undefined || m.y !== undefined);
    const x = (keyed ? at.x : it.x ?? 0) + dx, y = (keyed ? at.y : it.y ?? 0) + dy;
    setDraft(d.base.map((x0, j) => (j === d.i ? placeKey(x0, x, y) : x0)));
  };
  const up = () => {
    const d = drag.current;
    drag.current = null;
    if (d?.moved && draft) setItems(draft);
    setDraft(null);
  };
  const wheel = (e: React.WheelEvent) => {
    if (sel == null) return;
    e.preventDefault();
    const it = items[sel];
    if (e.altKey) patchItem(sel, { rot: r2((it.rot ?? 0) + (e.deltaY > 0 ? 3 : -3)) });
    else patchItem(sel, { s: Math.max(0.05, r2((it.s ?? 1) * (e.deltaY > 0 ? 0.95 : 1.05))) });
  };
  const key = (e: React.KeyboardEvent) => {
    if (sel == null) return;
    const step = e.shiftKey ? 10 : 1, it = items[sel];
    const nudge: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (nudge[e.key]) { e.preventDefault(); const [dx, dy] = nudge[e.key]; setItems(items.map((x, j) => (j === sel ? placeKey(x, (shownAt(it).x) + dx, (shownAt(it).y) + dy) : x))); }
    if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); remove(sel); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "d") { e.preventDefault(); duplicate(sel); }
  };
  const remove = (i: number) => { setItems(items.filter((_, j) => j !== i)); setSel(null); };
  const duplicate = (i: number) => { const c = { ...structuredClone(items[i]), x: (items[i].x ?? 0) + 20, y: (items[i].y ?? 0) + 20 }; setItems([...items.slice(0, i + 1), c, ...items.slice(i + 1)]); setSel(i + 1); };
  const reorder = (i: number, d: -1 | 1) => { const j = i + d; if (j < 0 || j >= items.length) return; const n = items.map((x) => { const { z, ...rest } = x; return rest as Item; }); [n[i], n[j]] = [n[j], n[i]]; setItems(n); setSel(j); };
  const add = (type: string) => { setItems([...items, starter(type, t, p.cast)]); setSel(items.length); setAdding(false); setTab("look"); };

  const it = sel != null ? items[sel] : null;
  const typeProps = it && cat ? cat.elements[it.type]?.props ?? {} : {};
  const groups = useMemo(() => { const g: Record<string, [string, string][]> = {}; for (const [k, v] of Object.entries(cat?.elements ?? {})) (g[v.group] ||= []).push([k, v.label]); return g; }, [cat]);
  const fieldsCtx = { t, seek: p.seek, cast: p.cast, media: p.media };
  const commonOf = (keys: string[]) => Object.fromEntries(keys.map((k) => [k, cat!.common[k]]).filter(([, v]) => v));

  return (
    <div className="se">
      <div className="se-stage-wrap">
        <div ref={wrap} className={`se-stage${p.extrasOnly ? " see-through" : ""}`} style={{ width: viewW, height: viewH }} tabIndex={0} aria-label="Scene drawing: drag to move, scroll to resize, Alt+scroll to turn, arrows to nudge"
          onPointerMove={move} onPointerUp={up} onPointerCancel={up} onWheel={wheel} onKeyDown={key} onPointerDown={() => setSel(null)}>
          <StoryScene scene={scene as any} t={t} width={viewW} height={viewH} chrome={true} onItemDown={down} />
          {box && <div className="se-box" style={{ left: box.l, top: box.t, width: box.w, height: box.h }} />}
        </div>
        <div className="se-stage-bar">
          <span className="mono small">{t.toFixed(2)} s</span>
          <label className="se-check small" title="When on, dragging adds a movement point at the playhead"><input type="checkbox" checked={record} onChange={(e) => setRecord(e.target.checked)} /> Record movement</label>
        </div>
      </div>

      {!p.extrasOnly && <Seg value={panel} onChange={setPanel} label="Story editor" options={[{ value: "layers", label: `Layers (${items.length})` }, { value: "scene", label: "Scene" }, { value: "cast", label: "Cast" }]} />}

      {panel === "layers" && <>
        <ul className="se-layers" aria-label="Layers, top first">
          {items.map((x, i) => ({ x, i })).sort((a, b) => (b.x.z ?? b.i) - (a.x.z ?? a.i)).map(({ x, i }) => (
            <li key={i} className={sel === i ? "on" : ""}>
              <button type="button" className="se-layer" onClick={() => { setSel(i); if (x.at != null && p.seek && (t < x.at || (x.until != null && t > x.until))) p.seek(x.at + 0.05); }}>
                <span className="se-dot" data-group={cat?.elements[x.type]?.group ?? ""} />{label(x, cat, p.cast)}
                <span className="muted small">{x.at != null ? `${x.at.toFixed(1)}s` : ""}{x.until != null ? `–${x.until.toFixed(1)}s` : ""}</span>
              </button>
              <button type="button" className="btn ghost icon sm" aria-label="Bring forward" onClick={() => reorder(i, 1)}><ArrowUp size={13} /></button>
              <button type="button" className="btn ghost icon sm" aria-label="Send back" onClick={() => reorder(i, -1)}><ArrowDown size={13} /></button>
              <button type="button" className="btn ghost icon sm" aria-label="Duplicate" onClick={() => duplicate(i)}><Copy size={13} /></button>
              <button type="button" className="btn ghost icon sm" aria-label="Delete" onClick={() => remove(i)}><Trash2 size={13} /></button>
            </li>
          ))}
        </ul>
        {!adding ? <button type="button" className="btn sm" onClick={() => setAdding(true)}><Plus size={14} /> Add to the scene</button> : (
          <div className="se-add">{Object.entries(groups).map(([g, list]) => <div key={g}><h4>{g}</h4><div className="se-add-list">
            {list.map(([k, l]) => <button key={k} type="button" className="chip" onClick={() => add(k)}>{l}</button>)}</div></div>)}
            <button type="button" className="btn ghost sm" onClick={() => setAdding(false)}>Cancel</button></div>)}

        {it && cat && sel != null && <div className="se-props">
          <Seg wrap value={tab} onChange={setTab} label="Item properties" options={[{ value: "look", label: "Look" }, { value: "place", label: "Place" }, { value: "time", label: "Timing" }, { value: "move", label: "Movement" }, { value: "json", label: "JSON" }]} />
          {tab === "look" && <>
            <label className="se-f"><span>Kind</span><select value={it.type} onChange={(e) => patchItem(sel, { type: e.target.value })}>
              {Object.entries(cat.elements).map(([k, v]) => <option key={k} value={k}>{v.group} · {v.label}</option>)}</select></label>
            {Object.keys(typeProps).length ? <Fields specs={typeProps} obj={it} set={(k, v) => patchItem(sel, { [k]: v })} {...fieldsCtx} /> : <p className="muted small">This item has nothing else to set.</p>}
          </>}
          {tab === "place" && <Fields specs={commonOf(["x", "y", "s", "rot", "opacity", "z", "flip"])} obj={it} set={(k, v) => patchItem(sel, { [k]: v })} {...fieldsCtx} />}
          {tab === "time" && <Fields specs={commonOf(["at", "until", "enter", "exit", "loop", "loopAmp"])} obj={it} set={(k, v) => patchItem(sel, { [k]: v })} {...fieldsCtx} />}
          {tab === "move" && <Keyframes it={it} t={t} seek={p.seek} now={shownAt(it)} set={(m) => patchItem(sel, { move: m.length ? m : undefined })} />}
          {tab === "json" && <JsonField title="Everything about this item" rows={12} value={it} set={(v) => { if (v && typeof v === "object" && v.type) setItems(items.map((x, j) => (j === sel ? v : x))); }} />}
        </div>}
      </>}

      {panel === "scene" && cat && <div className="se-props">
        <label className="se-f"><span>Place</span><select value={story.bg?.type ?? "plain"} onChange={(e) => save({ bg: { ...story.bg, type: e.target.value } })}>
          {Object.entries(cat.backgrounds).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
        <Fields specs={{ ...(cat.backgrounds[story.bg?.type ?? "plain"]?.props ?? {}), ...cat.background_common }} obj={story.bg ?? {}}
          set={(k, v) => { const bg = { ...story.bg, [k]: v }; if (v === undefined) delete bg[k]; save({ bg }); }} {...fieldsCtx} />
        <label className="se-f"><span>Scene label (top chip)</span><input value={story.tag ?? ""} maxLength={24} placeholder="none" onChange={(e) => save({ tag: e.target.value }, false)} /></label>
        <label className="se-f"><span>Slow push-in</span><input type="range" min={0} max={0.4} step={0.01} value={story.push ?? 0.05} onChange={(e) => save({ push: +e.target.value }, false)} /></label>
        <Speaking speak={story.speak ?? {}} cast={p.cast} t={t} set={(speak) => save({ speak })} />
        <JsonField title="The whole scene as JSON" rows={8} value={{ bg: story.bg, tag: story.tag, push: story.push, speak: story.speak, items }}
          set={(v) => { if (v && typeof v === "object" && Array.isArray(v.items)) save(v); }} />
      </div>}

      {panel === "cast" && cat && <CastPanel cast={p.cast} spec={cat.character} projectId={p.projectId} onSaved={p.onCastSaved} />}
    </div>
  );
}

function Keyframes({ it, t, now, set, seek }: { it: Item; t: number; now: { x: number; y: number }; set: (m: any[]) => void; seek?: (t: number) => void }) {
  const rows: any[] = [...(it.move ?? [])].sort((a, b) => a.t - b.t);
  const setRow = (i: number, patch: any) => set(rows.map((r, j) => (j === i ? Object.fromEntries(Object.entries({ ...r, ...patch }).filter(([, v]) => v !== undefined && v !== "")) : r)));
  const num = (v: string) => (v === "" ? undefined : +v);
  return <div className="se-fields">
    <p className="muted small">Each point says where the item is at that second; in between it glides. Turn on “Record movement” and drag to add points.</p>
    {rows.map((r, i) => <div key={i} className="se-kf">
      <button type="button" className="btn icon sm" aria-label="Go to this point" onClick={() => seek?.(r.t)}><Diamond size={12} /></button>
      {(["t", "x", "y", "s", "rot", "opacity"] as const).map((k) => <label key={k}><span>{k === "t" ? "at" : k}</span>
        <input type="number" step={k === "t" ? 0.05 : k === "s" || k === "opacity" ? 0.05 : 1} value={r[k] ?? ""} onChange={(e) => setRow(i, { [k]: num(e.target.value) })} /></label>)}
      <button type="button" className="btn icon sm" aria-label="Remove point" onClick={() => set(rows.filter((_, j) => j !== i))}><Trash2 size={13} /></button>
    </div>)}
    <button type="button" className="btn sm" onClick={() => set([...rows.filter((r) => Math.abs(r.t - t) > 0.02), { t: r2(t), x: r2(now.x), y: r2(now.y) }].sort((a, b) => a.t - b.t))}><Plus size={13} /> Point at the playhead</button>
  </div>;
}

function Speaking({ speak, cast, t, set }: { speak: Record<string, number[][]>; cast: Cast; t: number; set: (s: Record<string, number[][]>) => void }) {
  const ids = Object.keys(cast);
  const upd = (id: string, spans: number[][]) => { const n = { ...speak, [id]: spans }; if (!spans.length) delete n[id]; set(n); };
  return <div className="se-f"><span>Who talks when (their mouth moves with the voice)</span>
    {ids.map((id) => <div key={id} className="se-speak"><strong>{cast[id].name || id}</strong>
      {(speak[id] ?? []).map((sp, i) => <span key={i} className="se-row">
        <input type="number" step={0.05} value={sp[0]} aria-label="From" onChange={(e) => upd(id, (speak[id] ?? []).map((x, j) => (j === i ? [+e.target.value, x[1]] : x)))} />
        <input type="number" step={0.05} value={sp[1]} aria-label="To" onChange={(e) => upd(id, (speak[id] ?? []).map((x, j) => (j === i ? [x[0], +e.target.value] : x)))} />
        <button type="button" className="btn icon sm" aria-label="Remove" onClick={() => upd(id, (speak[id] ?? []).filter((_, j) => j !== i))}><Trash2 size={13} /></button></span>)}
      <button type="button" className="btn ghost sm" onClick={() => upd(id, [...(speak[id] ?? []), [r2(t), r2(t + 2)]])}><Plus size={13} /> Talks from the playhead</button></div>)}
  </div>;
}

function CastPanel({ cast, spec, projectId, onSaved }: { cast: Cast; spec: Record<string, Spec>; projectId: string; onSaved: () => void }) {
  const [doc, setDoc] = useState<Cast>(cast);
  const [busy, setBusy] = useState(false);
  useEffect(() => setDoc(cast), [JSON.stringify(cast)]); // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = JSON.stringify(doc) !== JSON.stringify(cast);
  const save = async () => {
    setBusy(true);
    try { await put(`/api/projects/${projectId}/story-cast`, { cast: doc }); toast("Cast saved: every scene uses the new looks.", "ok", 2500); onSaved(); }
    catch (e: any) { toast(e.message, "err", 7000); }
    finally { setBusy(false); }
  };
  const addOne = () => { let n = 1; while (doc[`person${n}`]) n++; setDoc({ ...doc, [`person${n}`]: { name: `Person ${n}`, skin: "#A86D40", shirt: "#6E96BB", pants: "#2A3550", hair: "#15110e" } }); };
  return <div className="se-props">
    <p className="muted small"><Users size={13} /> A look changed here changes that character in every scene.</p>
    {Object.entries(doc).map(([id, c]) => <details key={id} className="se-char">
      <summary><span className="se-swatch" style={{ background: c.shirt }} /><span className="se-swatch" style={{ background: c.skin }} />{c.name || id} <span className="muted small">{id}</span></summary>
      <Fields specs={spec} obj={c} set={(k, v) => { const n = { ...c, [k]: v }; if (v === undefined) delete n[k]; setDoc({ ...doc, [id]: n }); }} t={0} cast={doc} media={[]} />
      <button type="button" className="btn ghost sm danger" onClick={() => { const n = { ...doc }; delete n[id]; setDoc(n); }}><Trash2 size={13} /> Remove {c.name || id}</button>
    </details>)}
    <div className="row"><button type="button" className="btn sm" onClick={addOne}><Plus size={13} /> Add a character</button>
      <button type="button" className="btn primary sm" disabled={!dirty || busy} onClick={save}>Save the cast</button></div>
  </div>;
}
