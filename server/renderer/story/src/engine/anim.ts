// Generic animation system: every element gets enter / loop / exit / keyframe-move for free.
import { Easing, interpolate, spring } from '../rt';
import { FPS } from '../theme';
import type { El } from '../data';

const SPR = { damping: 14, stiffness: 150, mass: 0.8 };
const STAMP = { damping: 9, stiffness: 220, mass: 0.7 };
const cl = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
export const sp = (frame: number, cfg = SPR) => spring({ frame, fps: FPS, config: cfg });
export const c01 = (v: number) => Math.max(0, Math.min(1, v));

/** value of a keyframed property at time t (keyframes are absolute seconds) */
const kf = (el: El, key: 'x' | 'y' | 's' | 'rot' | 'opacity', base: number, t: number) => {
  const ks = (el.move || []).filter((m) => m[key] !== undefined).sort((a, b) => a.t - b.t);
  if (!ks.length) return base;
  const start = el.at ?? -1e9;
  const pts = [{ t: Math.min(start, ks[0].t - 0.001), v: base }, ...ks.map((m) => ({ t: m.t, v: m[key] as number }))];
  if (t <= pts[0].t) return pts[0].v;
  for (let i = 1; i < pts.length; i++) {
    if (t <= pts[i].t) {
      return interpolate(t, [pts[i - 1].t, pts[i].t], [pts[i - 1].v, pts[i].v], { ...cl, easing: Easing.inOut(Easing.cubic) });
    }
  }
  return pts[pts.length - 1].v;
};

export type AnimState = { visible: boolean; transform: string; opacity: number; k: number; x: number; y: number };

/** t = absolute seconds, f = frames since scene start */
export const animState = (el: El, t: number, f: number, sceneS: number, sceneE: number): AnimState => {
  const at = el.at ?? sceneS;
  const until = el.until ?? sceneE + 10;
  const enter = el.enter ?? (el.at !== undefined && el.at > sceneS + 0.05 ? 'pop' : 'none');
  if (t < at - 1 / FPS / 2 && enter !== 'none') return { visible: false, transform: '', opacity: 0, k: 0, x: 0, y: 0 };
  if (t > until + 0.35) return { visible: false, transform: '', opacity: 0, k: 0, x: 0, y: 0 };
  let x = kf(el, 'x', el.x ?? 0, t), y = kf(el, 'y', el.y ?? 0, t);
  let s = kf(el, 's', el.s ?? 1, t), rot = kf(el, 'rot', el.rot ?? 0, t), op = kf(el, 'opacity', el.opacity ?? 1, t);
  const fIn = (t - at) * FPS;
  const k = enter === 'none' ? 1 : sp(fIn);
  switch (enter) {
    case 'pop': s *= Math.max(0, k); op *= c01(k); break;
    case 'fade': op *= c01(fIn / 9); break;
    case 'slideL': x -= (1 - k) * 320; op *= c01(fIn / 6); break;
    case 'slideR': x += (1 - k) * 320; op *= c01(fIn / 6); break;
    case 'slideUp': y += (1 - k) * 240; op *= c01(fIn / 6); break;
    case 'slideDown': y -= (1 - k) * 240; op *= c01(fIn / 6); break;
    case 'drop': y -= (1 - k) * 500; op *= c01(fIn / 4); break;
    case 'stamp': { const kk = sp(fIn, STAMP); s *= 2.4 - 1.4 * kk; op *= c01(kk * 1.5); break; }
    case 'grow': s *= interpolate(fIn, [0, 12], [0, 1], { ...cl, easing: Easing.out(Easing.back(1.6)) }); break;
  }
  if (el.until !== undefined && t > until) {
    const o = c01(1 - (t - until) / 0.3);
    if (el.exit === 'pop') s *= o;
    if (el.exit !== 'none') op *= o;
  }
  const a = el.loopAmp ?? 1;
  switch (el.loop) {
    case 'breathe': y += Math.sin(f / 22) * 1.5 * a; break;
    case 'bob': y -= Math.abs(Math.sin(f / 5)) * 6 * a; break;
    case 'walk': y -= Math.abs(Math.sin(f / 4)) * 6 * a; rot += Math.sin(f / 4) * 1.2 * a; break;
    case 'float': y += Math.sin(f / 15) * 8 * a; break;
    case 'shake': x += Math.sin(f * 1.7) * 2.5 * a; break;
    case 'pulse': s *= 1 + 0.05 * a * Math.sin(f / 6); break;
    case 'spin': rot += f * 3 * a; break;
    case 'sway': rot += Math.sin(f / 12) * 4 * a; break;
    case 'glow': op *= 0.75 + 0.25 * Math.sin(f / 8); break;
  }
  return { visible: true, transform: `translate(${x},${y}) rotate(${rot}) scale(${s})`, opacity: c01(op), k: c01(k), x, y };
};

/** piecewise schedule helper: [{t, ...}] -> entry active at time t */
export const scheduled = <T extends { t: number }>(list: T[] | undefined, t: number): T | undefined => {
  if (!list || !list.length) return undefined;
  let cur: T | undefined;
  for (const it of [...list].sort((a, b) => a.t - b.t)) if (t >= it.t) cur = it;
  return cur;
};
