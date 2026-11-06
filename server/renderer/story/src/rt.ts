// The few Remotion functions the story engine uses, with the same maths, so the engine source stays as it was written.
// Time comes from a React context (the HyperFrames timeline or the Studio playhead) instead of Remotion's player.
import { createContext, useContext } from 'react';

export const FrameCtx = createContext(0);
export const useCurrentFrame = () => useContext(FrameCtx);

type Ext = 'clamp' | 'extend';
export function interpolate(v: number, input: number[], output: number[], o: { extrapolateLeft?: Ext; extrapolateRight?: Ext; easing?: (t: number) => number } = {}) {
  let i = 1;
  while (i < input.length - 1 && v > input[i]) i++;
  const a = input[i - 1], b = input[i], ya = output[i - 1], yb = output[i];
  if (v < input[0] && o.extrapolateLeft === 'clamp') return output[0];
  if (v > input[input.length - 1] && o.extrapolateRight === 'clamp') return output[output.length - 1];
  let k = b === a ? 0 : (v - a) / (b - a);
  if (o.easing) k = o.easing(Math.max(0, Math.min(1, k))) + (k < 0 || k > 1 ? k - Math.max(0, Math.min(1, k)) : 0);
  return ya + (yb - ya) * k;
}

/** Remotion's spring: a damped harmonic oscillator stepped at 1/1000 s, reported per frame (from 0 to 1). */
const springCache = new Map<string, number[]>();
export function spring({ frame, fps, config = {} }: { frame: number; fps: number; config?: { damping?: number; stiffness?: number; mass?: number } }) {
  if (frame <= 0) return 0;
  const damping = config.damping ?? 10, stiffness = config.stiffness ?? 100, mass = config.mass ?? 1;
  const key = `${damping}|${stiffness}|${mass}|${fps}`;
  let table = springCache.get(key);
  if (!table) {
    table = [0];
    let x = 0, v = 0;
    const dt = 1 / 1000, steps = Math.round(1000 / fps);
    for (let f = 1; f <= 300; f++) {
      for (let s = 0; s < steps; s++) { const a = (-stiffness * (x - 1) - damping * v) / mass; v += a * dt; x += v * dt; }
      table.push(x);
    }
    springCache.set(key, table);
  }
  const i = Math.floor(frame), k = frame - i;
  if (i >= table.length - 1) return 1;
  return table[i] + (table[i + 1] - table[i]) * k;
}

const bez = (x1: number, y1: number, x2: number, y2: number) => (t: number) => {
  let lo = 0, hi = 1, u = t;
  for (let n = 0; n < 24; n++) {
    u = (lo + hi) / 2;
    const x = 3 * (1 - u) * (1 - u) * u * x1 + 3 * (1 - u) * u * u * x2 + u * u * u;
    if (x < t) lo = u; else hi = u;
  }
  return 3 * (1 - u) * (1 - u) * u * y1 + 3 * (1 - u) * u * u * y2 + u * u * u;
};
export const Easing = {
  linear: (t: number) => t,
  cubic: (t: number) => t * t * t,
  back: (s = 1.70158) => (t: number) => t * t * ((s + 1) * t - s),
  bezier: bez,
  in: (e: (t: number) => number) => e,
  out: (e: (t: number) => number) => (t: number) => 1 - e(1 - t),
  inOut: (e: (t: number) => number) => (t: number) => (t < 0.5 ? e(t * 2) / 2 : 1 - e((1 - t) * 2) / 2),
};
