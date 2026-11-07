import type { El } from "../types";
import { corners, tidy } from "./transformMath.ts";

/** What a hand does to one element on the canvas (plan step E17). Distances are in frame pixels since the gesture began; the Inspector turns them into the element's own numbers. */
export type Gesture =
  | { kind: "move"; dx: number; dy: number }
  | { kind: "scale"; factor: number }
  | { kind: "rotate"; degrees: number }
  | { kind: "pin"; corner: 0 | 1 | 2 | 3; dx: number; dy: number };

/** The element as it was when the gesture began, and where it is on the frame: the middle of its box, the frame's size and its own size before any transform. */
export interface Start { el: El; center: [number, number]; frame: [number, number]; size: [number, number]; quad?: number[][] }

/** Map a screen point back to a plane through four measured corners. This
 * undoes the actual perspective, slant, stretch and rotation together. */
function unproject(src: number[][], dst: number[][], point: number[]): number[] | null {
  const rows: number[][] = [];
  src.forEach(([x,y],i) => {
    const [u,v] = dst[i];
    rows.push([x,y,1,0,0,0,-u*x,-u*y,u], [0,0,0,x,y,1,-v*x,-v*y,v]);
  });
  for(let col=0;col<8;col++) {
    let pivot=col;
    for(let r=col+1;r<8;r++) if(Math.abs(rows[r][col])>Math.abs(rows[pivot][col])) pivot=r;
    [rows[col],rows[pivot]]=[rows[pivot],rows[col]];
    const divisor=rows[col][col];
    if(Math.abs(divisor)<1e-10) return null;
    for(let k=col;k<=8;k++) rows[col][k]/=divisor;
    for(let r=0;r<8;r++) if(r!==col) {
      const f=rows[r][col];
      for(let k=col;k<=8;k++) rows[r][k]-=f*rows[col][k];
    }
  }
  const h=rows.map(row=>row[8]),[x,y]=point,den=h[6]*x+h[7]*y+1;
  if(Math.abs(den)<1e-10) return null;
  return [(h[0]*x+h[1]*y+h[2])/den,(h[3]*x+h[4]*y+h[5])/den];
}

const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n));
const round = (n: number, digits = 4) => Math.round(n * 10 ** digits) / 10 ** digits;
const turn = (deg: number) => { const d = ((deg + 180) % 360 + 360) % 360 - 180; return d === -180 ? 180 : d; };

/** The change a gesture makes, as a patch of the element. An element nobody has placed yet (automatic layout put it there) first takes over where it is, so it does not jump. */
export function applyGesture(start: Start, g: Gesture): Record<string, any> {
  const { el, center, frame } = start;
  const x0 = el.x ?? center[0] / frame[0], y0 = el.y ?? center[1] / frame[1], scale0 = el.scale ?? 1, rotation0 = el.rotation ?? 0;
  const here = { x: round(clamp(x0, 0, 1)), y: round(clamp(y0, 0, 1)) };
  if (g.kind === "move") return { x: round(clamp(x0 + g.dx / frame[0], 0, 1)), y: round(clamp(y0 + g.dy / frame[1], 0, 1)) };
  if (g.kind === "scale") return { ...here, scale: round(clamp(scale0 * g.factor, 0.05, 5)) };
  if (g.kind === "rotate") return { ...here, rotation: round(turn(rotation0 + g.degrees), 2) };
  // a corner pin: the corner moves by the hand's distance, taken back through the element's own turn and size into a fraction of its box
  const t = el.transform ?? {}, a = (-rotation0 * Math.PI) / 180;
  if(start.quad?.length === 4) {
    const base = [[0,0],[1,0],[1,1],[0,1]], pins=corners(t);
    const local=base.map((p,i)=>[(p[0]+pins[i][0])*start.size[0],(p[1]+pins[i][1])*start.size[1]]);
    const corner=start.quad[g.corner];
    const target=unproject(start.quad,local,[corner[0]+g.dx,corner[1]+g.dy]);
    if(target) {
      const warp=pins.map((p,i)=>i===g.corner ? [round(clamp(target[0]/start.size[0]-base[i][0],-1,1)),round(clamp(target[1]/start.size[1]-base[i][1],-1,1))] : p);
      // Pinning changes the shape, not its anchor (the quad's centre moves).
      return {transform:tidy({...t,warp})};
    }
    return {}; // a collapsed plane has no inverse; keep the last valid shape
  }
  const lx = g.dx * Math.cos(a) - g.dy * Math.sin(a), ly = g.dx * Math.sin(a) + g.dy * Math.cos(a);
  const sx = scale0 * (t.stretch_x ?? 1) * (t.flip_x ? -1 : 1), sy = scale0 * (t.stretch_y ?? 1) * (t.flip_y ? -1 : 1);
  const warp = corners(t).map((c, i) => (i === g.corner ? [round(clamp(c[0] + lx / sx / start.size[0], -1, 1)), round(clamp(c[1] + ly / sy / start.size[1], -1, 1))] : c));
  return { ...here, transform: tidy({ ...t, warp }) };
}

/** The distance of the hand from the middle, and the angle around it: what the resize and turn handles measure. */
export const reach = (p: [number, number], c: [number, number]) => Math.hypot(p[0] - c[0], p[1] - c[1]);
export const bearing = (p: [number, number], c: [number, number]) => (Math.atan2(p[1] - c[1], p[0] - c[0]) * 180) / Math.PI;

/** How far a turn went, however it wrapped (350° to 10° is 20°, not -340°). */
export const turned = (from: number, to: number) => turn(to - from);
