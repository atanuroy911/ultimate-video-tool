import type { El } from "../types";

/** What a person can do to one element besides moving, sizing, turning and fading it (plan step E17). Mirrors `Transform` in server/vt/schema.py; every field is neutral by default. */
export interface Transform {
  stretch_x?: number; stretch_y?: number; skew_x?: number; skew_y?: number; flip_x?: boolean; flip_y?: boolean; pivot_x?: number; pivot_y?: number;
  tilt_x?: number; tilt_y?: number; warp?: number[][] | null; crop?: number[] | null; crop_radius?: number; blur?: number; blend?: string;
}

export const TRANSFORM_DEFAULTS = {
  stretch_x: 1, stretch_y: 1, skew_x: 0, skew_y: 0, flip_x: false, flip_y: false, pivot_x: 0.5, pivot_y: 0.5, tilt_x: 0, tilt_y: 0, warp: null, crop: null, crop_radius: 0, blur: 0, blend: "normal",
} as const;

export const BLENDS: [string, string][] = [["normal", "Normal"], ["multiply", "Darken (multiply)"], ["screen", "Lighten (screen)"], ["overlay", "Overlay"], ["darken", "Darker only"], ["lighten", "Lighter only"], ["soft-light", "Soft light"], ["difference", "Difference"]];

/** The numbers a keyframe can hold, with the range the server accepts and what each means when nothing is said (server/vt/visual_motion.py `MotionPoint`). */
export const POINT_KEYS = {
  x: [-0.5, 1.5, 0.5], y: [-0.5, 1.5, 0.5], scale: [0.05, 5, 1], rotation: [-360, 360, 0], opacity: [0, 1, 1],
  stretch_x: [0.1, 5, 1], stretch_y: [0.1, 5, 1], skew_x: [-60, 60, 0], skew_y: [-60, 60, 0], tilt_x: [-80, 80, 0], tilt_y: [-80, 80, 0], blur: [0, 60, 0],
} as const;
export type PointKey = keyof typeof POINT_KEYS;

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** The transform without anything that is just the default, or null when nothing is set: an element with nothing set is not a hand-placed one. */
export function tidy(t: Transform | null | undefined): Transform | null {
  if (!t) return null;
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(t)) {
    if (v === undefined || v === null) continue;
    if (k === "crop" && Array.isArray(v) && v.every((n) => !n)) continue;
    if (same(v, (TRANSFORM_DEFAULTS as Record<string, unknown>)[k])) continue;
    out[k] = v;
  }
  return Object.keys(out).length ? (out as Transform) : null;
}
export const hasTransform = (t: Transform | null | undefined) => tidy(t) !== null;

/** The element with one more thing of its transform changed (or reset by giving the default). */
export function withTransform(el: El, patch: Transform): El {
  return { ...el, transform: tidy({ ...(el.transform ?? {}), ...patch }) };
}

/** The four corners of a corner pin as the server wants them (top left, top right, bottom right, bottom left), each [dx, dy]; zeros when none. */
export const corners = (t: Transform | null | undefined): number[][] => (t?.warp && t.warp.length === 4 ? t.warp : [[0, 0], [0, 0], [0, 0], [0, 0]]);

/** The crop as [top, right, bottom, left]; zeros when none. */
export const cropOf = (t: Transform | null | undefined): number[] => (t?.crop && t.crop.length === 4 ? t.crop : [0, 0, 0, 0]);

/** A static change of the transform (the Position tab) applied to the keyframes of an animated element too: a stretch scales every point's stretch, the rest move every point by the difference. */
export function repositionTransform(points: Record<string, any>[], before: Transform | null | undefined, after: Transform | null | undefined): Record<string, any>[] {
  const keys = ["stretch_x", "stretch_y", "skew_x", "skew_y", "tilt_x", "tilt_y", "blur"] as const;
  return points.map((p) => {
    const next = { ...p };
    for (const key of keys) {
      const was = (before as any)?.[key] ?? (TRANSFORM_DEFAULTS as any)[key], now = (after as any)?.[key] ?? (TRANSFORM_DEFAULTS as any)[key];
      if (was === now) continue;
      const [min, max, fallback] = POINT_KEYS[key];
      const have = p[key] ?? fallback;
      next[key] = Math.max(min, Math.min(max, key.startsWith("stretch") ? have * now / was : have + now - was));
    }
    return next;
  });
}
