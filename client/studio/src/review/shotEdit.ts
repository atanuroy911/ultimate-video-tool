// The visual editor's edits to a code-native shot (docs/plans/PLAN-CODE-NATIVE-EDITOR.MD, C3). Pure functions: no React, no network.
// An edit never touches the shot's code; it is a small overrides object the server checks (server/vt/shots.py check_overrides) and draws as CSS.

export type StyleName = "color" | "background" | "fontSize" | "fontWeight" | "fontFamily" | "letterSpacing" | "opacity";
export interface ElementEdit { text?: string; x?: number; y?: number; scale?: number; rotate?: number; hidden?: boolean; style?: Partial<Record<StyleName, string | number>> }
export interface Overrides { knobs: Record<string, string>; elements: Record<string, ElementEdit> }
export type Rect = [number, number, number, number];            // left, top, width, height in shot pixels

export const EMPTY: Overrides = { knobs: {}, elements: {} };
const round = (n: number, places = 2) => Math.round(n * 10 ** places) / 10 ** places;
const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n));

/** A copy without empty entries, so "no edit" is always written the same way. */
export function tidy(o: Overrides): Overrides {
  const elements: Record<string, ElementEdit> = {};
  for (const [id, e] of Object.entries(o.elements)) {
    const out: ElementEdit = {};
    for (const [k, v] of Object.entries(e) as [keyof ElementEdit, any][]) {
      if (v === undefined || v === null) continue;
      if (k === "style") {
        const s = Object.fromEntries(Object.entries(v).filter(([, x]) => x !== undefined && x !== null && x !== ""));
        if (Object.keys(s).length) out.style = s;
      } else if (k === "hidden") { if (v) out.hidden = true; }
      else if ((k === "x" || k === "y" || k === "rotate") && v === 0) continue;
      else if (k === "scale" && v === 1) continue;
      else (out as any)[k] = v;
    }
    if (Object.keys(out).length) elements[id] = out;
  }
  const knobs = Object.fromEntries(Object.entries(o.knobs).filter(([, v]) => v !== "" && v != null));
  return { knobs, elements };
}

export function editElement(o: Overrides, id: string, patch: ElementEdit): Overrides {
  const cur = o.elements[id] ?? {};
  const style = patch.style ? { ...(cur.style ?? {}), ...patch.style } : cur.style;
  return tidy({ ...o, elements: { ...o.elements, [id]: { ...cur, ...patch, ...(style ? { style } : {}) } } });
}

export function resetElement(o: Overrides, id: string): Overrides {
  const { [id]: _gone, ...rest } = o.elements;
  return { ...o, elements: rest };
}

export function setKnob(o: Overrides, name: string, value: string | null): Overrides {
  const knobs = { ...o.knobs };
  if (value == null || value === "") delete knobs[name]; else knobs[name] = value;
  return { ...o, knobs };
}

/** Dragging an element by (dx, dy) shot pixels from where it was when the drag began. */
export function moved(o: Overrides, id: string, start: ElementEdit, dx: number, dy: number): Overrides {
  return editElement(o, id, { x: round((start.x ?? 0) + dx), y: round((start.y ?? 0) + dy) });
}

/** A corner handle: the scale grows with the pointer's distance from the element's centre (rect is the element as drawn when the drag began). */
export function scaled(o: Overrides, id: string, start: ElementEdit, rect: Rect, from: [number, number], to: [number, number]): Overrides {
  const cx = rect[0] + rect[2] / 2, cy = rect[1] + rect[3] / 2;
  const d0 = Math.hypot(from[0] - cx, from[1] - cy), d1 = Math.hypot(to[0] - cx, to[1] - cy);
  if (d0 < 4) return o;
  return editElement(o, id, { scale: round(clamp((start.scale ?? 1) * d1 / d0, 0.05, 20), 3) });
}

/** The rotate handle: the angle the pointer turned around the element's centre; with shift, in 15 degree steps. */
export function rotated(o: Overrides, id: string, start: ElementEdit, rect: Rect, from: [number, number], to: [number, number], snap = false): Overrides {
  const cx = rect[0] + rect[2] / 2, cy = rect[1] + rect[3] / 2;
  const a0 = Math.atan2(from[1] - cy, from[0] - cx), a1 = Math.atan2(to[1] - cy, to[0] - cx);
  let deg = (start.rotate ?? 0) + (a1 - a0) * 180 / Math.PI;
  deg = ((deg + 540) % 360) - 180;
  if (snap) deg = Math.round(deg / 15) * 15;
  return editElement(o, id, { rotate: round(deg, 1) });
}

/** Undo and redo over whole override states. */
export interface History { past: Overrides[]; now: Overrides; future: Overrides[] }
export const historyOf = (o: Overrides): History => ({ past: [], now: o, future: [] });
export function commit(h: History, next: Overrides, limit = 100): History {
  if (JSON.stringify(next) === JSON.stringify(h.now)) return h;
  return { past: [...h.past, h.now].slice(-limit), now: next, future: [] };
}
export const undo = (h: History): History => h.past.length ? { past: h.past.slice(0, -1), now: h.past[h.past.length - 1], future: [h.now, ...h.future] } : h;
export const redo = (h: History): History => h.future.length ? { past: [...h.past, h.now], now: h.future[0], future: h.future.slice(1) } : h;

/** A colour value the colour picker can show (#rrggbb), or null when the knob is not a plain colour. */
export function asHex(v: string | undefined): string | null {
  if (!v) return null;
  const s = v.trim();
  if (/^#[0-9a-f]{6}$/i.test(s)) return s.toLowerCase();
  if (/^#[0-9a-f]{3}$/i.test(s)) return ("#" + s.slice(1).split("").map((c) => c + c).join("")).toLowerCase();
  return null;
}

/** The knob values the shot's own code declares on :root (what it looks like with no edit). */
export function declaredKnobs(html: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const block of html.match(/:root\s*\{[^}]*\}/g) ?? [])
    for (const m of block.matchAll(/(--[A-Za-z0-9_-]+)\s*:\s*([^;}]+)/g)) out[m[1]] = m[2].trim();
  return out;
}
