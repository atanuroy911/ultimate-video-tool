import { useRef } from "react";
import type { Gesture } from "./gestures.ts";
import { bearing, reach, turned } from "./gestures.ts";
import type { HandleMode } from "./transformUi";

/** Where the page says the selected element is: its box on the frame, its own size, the real position of its four corners (a hand-placed one) and the frame's size. */
export interface Located { box: number[]; size: number[] | null; quad: number[][] | null; free: boolean; frame: number[] }

/** What the Inspector hears (it owns the element and saves it): a hand began, moved, or let go. */
export interface GestureEvent { scene: string; index: number; phase: "start" | "move" | "end"; gesture?: Gesture; center: [number, number]; frame: [number, number]; size: [number, number] }
export const sendGesture = (detail: GestureEvent) => window.dispatchEvent(new CustomEvent("vt-element-gesture", { detail }));

const NAMES = ["top left", "top right", "bottom right", "bottom left"];

/** Where the middle of the element is, how big the frame is and how big the element is by itself: what every gesture is measured from. */
export function startOf(at: Located, fallback: [number, number]): { center: [number, number]; frame: [number, number]; size: [number, number]; quad: [number, number][] } {
  const quad = (at.quad ?? [[at.box[0], at.box[1]], [at.box[0] + at.box[2], at.box[1]], [at.box[0] + at.box[2], at.box[1] + at.box[3]], [at.box[0], at.box[1] + at.box[3]]]) as [number, number][];
  return { quad, center: [quad.reduce((s, p) => s + p[0], 0) / 4, quad.reduce((s, p) => s + p[1], 0) / 4], frame: [at.frame?.[0] || fallback[0], at.frame?.[1] || fallback[1]], size: [at.size?.[0] || at.box[2], at.size?.[1] || at.box[3]] };
}

/** The handles on the picture for the selected element (plan step E17): drag the element to move it, a corner to size it, the knob to turn it; in the pin mode each corner moves on its own
 *  (a corner-pin warp). Everything is measured in frame pixels, so what the hand does is what the export draws. */
export default function TransformHandles({ at, scale, mode, scene, index, width, height }: { at: Located; scale: number; mode: HandleMode; scene: string; index: number; width: number; height: number }) {
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<null | { kind: "move" | "scale" | "rotate" | "pin"; corner: 0 | 1 | 2 | 3; from: [number, number]; center: [number, number]; frame: [number, number]; size: [number, number] }>(null);
  const { quad, center, frame, size } = startOf(at, [width / scale, height / scale]);
  const px = (p: number[]) => `${p[0] * scale},${p[1] * scale}`;
  const top = [(quad[0][0] + quad[1][0]) / 2, (quad[0][1] + quad[1][1]) / 2];                         // the middle of the top edge, and which way is out from the middle
  const out = Math.hypot(top[0] - center[0], top[1] - center[1]) || 1;
  const knob = [top[0] + ((top[0] - center[0]) / out) * (30 / scale), top[1] + ((top[1] - center[1]) / out) * (30 / scale)];

  const frameAt = (e: React.PointerEvent): [number, number] => { const r = svg.current!.getBoundingClientRect(); return [(e.clientX - r.left) / scale, (e.clientY - r.top) / scale]; };
  const begin = (kind: "move" | "scale" | "rotate" | "pin", corner: 0 | 1 | 2 | 3 = 0) => (e: React.PointerEvent) => {
    e.stopPropagation(); e.preventDefault();
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    drag.current = { kind, corner, from: frameAt(e), center, frame, size };
    sendGesture({ scene, index, phase: "start", center, frame, size });
  };
  const gesture = (e: React.PointerEvent): Gesture | null => {
    const d = drag.current;
    if (!d) return null;
    const p = frameAt(e);
    if (d.kind === "move") return { kind: "move", dx: p[0] - d.from[0], dy: p[1] - d.from[1] };
    if (d.kind === "pin") return { kind: "pin", corner: d.corner, dx: p[0] - d.from[0], dy: p[1] - d.from[1] };
    if (d.kind === "scale") return { kind: "scale", factor: Math.max(0.05, reach(p, d.center) / Math.max(1, reach(d.from, d.center))) };
    return { kind: "rotate", degrees: turned(bearing(d.from, d.center), bearing(p, d.center)) };
  };
  const move = (e: React.PointerEvent) => { const g = gesture(e); if (g && drag.current) sendGesture({ scene, index, phase: "move", gesture: g, center: drag.current.center, frame: drag.current.frame, size: drag.current.size }); };
  const end = (e: React.PointerEvent) => {
    const d = drag.current, g = gesture(e);
    drag.current = null;
    if (d && g) sendGesture({ scene, index, phase: "end", gesture: g, center: d.center, frame: d.frame, size: d.size });
  };
  const live = { onPointerMove: move, onPointerUp: end, onPointerCancel: end };
  const pinning = mode === "warp";
  return (
    <svg ref={svg} className="xform" width={width} height={height} data-testid="transform-handles" aria-label="Handles for the selected picture" style={{ position: "absolute", left: 0, top: 0, pointerEvents: "none", touchAction: "none", overflow: "visible" }}>
      <polygon points={quad.map(px).join(" ")} className="xform-body" data-testid="handle-move" style={{ pointerEvents: "all", cursor: "move" }} onPointerDown={begin("move")} onClick={(e) => e.stopPropagation()} {...live}><title>Drag to move</title></polygon>
      {quad.map((p, i) => (
        <g key={i} style={{ pointerEvents: "all", cursor: pinning ? "crosshair" : "nwse-resize" }} onPointerDown={begin(pinning ? "pin" : "scale", i as 0 | 1 | 2 | 3)} onClick={(e) => e.stopPropagation()} {...live} data-testid={pinning ? `handle-pin-${i}` : `handle-scale-${i}`}>
          <circle cx={p[0] * scale} cy={p[1] * scale} r={22} fill="transparent" />
          {pinning ? <circle cx={p[0] * scale} cy={p[1] * scale} r={8} className="xform-pin" /> : <rect x={p[0] * scale - 6} y={p[1] * scale - 6} width={12} height={12} rx={3} className="xform-corner" />}
          <title>{pinning ? `Drag the ${NAMES[i]} corner` : "Drag to resize"}</title>
        </g>
      ))}
      {!pinning && (
        <g style={{ pointerEvents: "all", cursor: "grab" }} onPointerDown={begin("rotate")} onClick={(e) => e.stopPropagation()} {...live} data-testid="handle-rotate">
          <line x1={top[0] * scale} y1={top[1] * scale} x2={knob[0] * scale} y2={knob[1] * scale} className="xform-line" />
          <circle cx={knob[0] * scale} cy={knob[1] * scale} r={22} fill="transparent" />
          <circle cx={knob[0] * scale} cy={knob[1] * scale} r={7} className="xform-knob" />
          <title>Drag to turn</title>
        </g>
      )}
    </svg>
  );
}
