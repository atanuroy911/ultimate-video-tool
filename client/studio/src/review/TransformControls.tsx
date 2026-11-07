import { Diamond, FlipHorizontal2, FlipVertical2, RotateCcw } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import type { El } from "../types";
import { BLENDS, TRANSFORM_DEFAULTS, corners, cropOf, hasTransform, tidy, type Transform } from "./transformMath.ts";
import { saveMotionPoint } from "./motionMath.ts";
import { timeStore } from "./timeStore";
import type { PointKey } from "./transformMath.ts";

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

/** One value, three ways to set it: a slider, a number to type, and a button back to the default. `shown` converts what is stored to what is read (fractions to percent). */
export function Value({ label, aria, value, def, min, max, step, unit, shown = 1, onChange, onKeyframe }: { label: string; aria?: string; value: number; def: number; min: number; max: number; step: number; unit: string; shown?: number; onChange: (v: number) => void; onKeyframe?: () => void }) {
  const read = (v: number) => Math.round(v * shown * 10) / 10;                                  // one decimal is plenty to read; what is stored keeps what the hand made
  const set = (v: number) => Number.isFinite(v) && onChange(Math.max(min, Math.min(max, v / shown)));
  return (
    <div className={`value-row${onKeyframe ? " keyable" : ""}`} data-testid={`value-${slug(label)}`}>
      <span className="value-label">{label}</span>
      <input aria-label={aria ?? label} type="range" min={min * shown} max={max * shown} step={step} value={read(value)} onChange={(e) => set(Number(e.target.value))} onDoubleClick={() => onChange(def)} title="Double-click to go back to normal" />
      <input className="num" aria-label={`${aria ?? label}, as a number`} type="number" min={min * shown} max={max * shown} step={step} value={read(value)} onChange={(e) => set(Number(e.target.value))} />
      <span className="unit" aria-hidden>{unit}</span>
      <button className="btn ghost icon sm" aria-label={`Reset ${label}`} title="Back to normal" disabled={Math.abs(value - def) < 1e-9} onClick={() => onChange(def)}><RotateCcw size={13} /></button>
      {onKeyframe && <button className="btn ghost icon sm" aria-label={`Keyframe ${label}`} title="Save this value at the playhead" onClick={onKeyframe}><Diamond size={13} /></button>}
    </div>
  );
}

function Group({ title, set, hint, children }: { title: string; set: boolean; hint?: string; children: ReactNode }) {
  const [shown, setShown] = useState(set);                                   // open when something in it is set, and it stays as the person leaves it (a reset does not fold it away)
  useEffect(() => { if (set) setShown(true); }, [set]);
  return (
    <details className="transform-group" open={shown} onToggle={(e) => setShown(e.currentTarget.open)} data-testid={`group-${slug(title)}`}>
      <summary><strong>{title}</strong>{set && <span className="small muted"> · changed</span>}</summary>
      {hint && <p className="small muted">{hint}</p>}
      <div className="col" style={{ gap: 4 }}>{children}</div>
    </details>
  );
}

/** Everything a person can do to one element by hand (plan step E17): move, size, turn and fade it, stretch, slant, flip, tilt it in 3D around a pivot, crop it, pin its four corners,
 *  blur it and blend it. `patch` changes the element (and, for an animated one, every point of its motion with it). */
export default function TransformControls({ value, patch, pinning, onPin, bounds, defaultY=.45 }: { value: Record<string, any>; patch: (p: Record<string, any>) => void; pinning?: boolean; onPin?: (on: boolean) => void; bounds?: {start:number;end:number}; defaultY?:number }) {
  const t: Transform = value.transform ?? {};
  const get = <K extends keyof typeof TRANSFORM_DEFAULTS>(k: K) => ((t as any)[k] ?? TRANSFORM_DEFAULTS[k]) as any;
  const set = (p: Transform) => patch({ transform: tidy({ ...t, ...p }) });
  const crop = cropOf(t), pins = corners(t);
  const setCrop = (i: number, v: number) => set({ crop: crop.map((n, j) => (j === i ? Math.min(v,.95-crop[(i+2)%4]) : n)) });
  const setPin = (i: number, axis: 0 | 1, v: number) => set({ warp: pins.map((c, j) => (j === i ? c.map((n, k) => (k === axis ? v : n)) : c)) });
  const names = ["Top left", "Top right", "Bottom right", "Bottom left"];
  const frame = (key: PointKey) => () => patch({keyframes:saveMotionPoint({...value,y:value.y??defaultY},timeStore.t,bounds?.start ?? value.start ?? 0,bounds?.end ?? value.end ?? 0,key)});
  return (
    <div className="col transform-controls" style={{ gap: 6 }}>
      <h3>Move &amp; size</h3>
      <Value onKeyframe={frame("x")} label="Left ↔ right" value={value.x ?? 0.5} def={0.5} min={0} max={1} step={1} unit="%" shown={100} onChange={(v) => patch({ x: v })} />
      <Value onKeyframe={frame("y")} label="Top ↔ bottom" value={value.y ?? defaultY} def={defaultY} min={0} max={1} step={1} unit="%" shown={100} onChange={(v) => patch({ y: v })} />
      <Value onKeyframe={frame("scale")} label="Size" value={value.scale ?? 1} def={1} min={0.05} max={5} step={1} unit="%" shown={100} onChange={(v) => patch({ scale: v })} />
      <Value onKeyframe={frame("rotation")} label="Rotate" value={value.rotation ?? 0} def={0} min={-180} max={180} step={1} unit="°" onChange={(v) => patch({ rotation: v })} />
      <Value onKeyframe={frame("opacity")} label="Opacity" value={value.opacity ?? 1} def={1} min={0} max={1} step={1} unit="%" shown={100} onChange={(v) => patch({ opacity: v })} />

      <Group title="Stretch, slant and flip" set={["stretch_x", "stretch_y", "skew_x", "skew_y", "flip_x", "flip_y"].some((k) => get(k as any) !== (TRANSFORM_DEFAULTS as any)[k])}>
        <Value onKeyframe={frame("stretch_x")} label="Stretch across" value={get("stretch_x")} def={1} min={0.1} max={5} step={1} unit="%" shown={100} onChange={(v) => set({ stretch_x: v })} />
        <Value onKeyframe={frame("stretch_y")} label="Stretch up and down" value={get("stretch_y")} def={1} min={0.1} max={5} step={1} unit="%" shown={100} onChange={(v) => set({ stretch_y: v })} />
        <Value onKeyframe={frame("skew_x")} label="Slant sideways" value={get("skew_x")} def={0} min={-60} max={60} step={1} unit="°" onChange={(v) => set({ skew_x: v })} />
        <Value onKeyframe={frame("skew_y")} label="Slant up and down" value={get("skew_y")} def={0} min={-60} max={60} step={1} unit="°" onChange={(v) => set({ skew_y: v })} />
        <div className="row wrap" style={{ gap: 6 }}>
          <button className="btn sm" aria-pressed={!!get("flip_x")} onClick={() => set({ flip_x: !get("flip_x") })}><FlipHorizontal2 size={14} /> Mirror left ↔ right</button>
          <button className="btn sm" aria-pressed={!!get("flip_y")} onClick={() => set({ flip_y: !get("flip_y") })}><FlipVertical2 size={14} /> Mirror top ↔ bottom</button>
        </div>
      </Group>

      <Group title="Tilt in 3D" set={get("tilt_x") !== 0 || get("tilt_y") !== 0} hint="Lean it toward or away from the viewer, or turn it like a door.">
        <Value onKeyframe={frame("tilt_x")} label="Lean back or forward" value={get("tilt_x")} def={0} min={-80} max={80} step={1} unit="°" onChange={(v) => set({ tilt_x: v })} />
        <Value onKeyframe={frame("tilt_y")} label="Turn left or right" value={get("tilt_y")} def={0} min={-80} max={80} step={1} unit="°" onChange={(v) => set({ tilt_y: v })} />
      </Group>

      <Group title="Pivot" set={get("pivot_x") !== 0.5 || get("pivot_y") !== 0.5} hint="The point it turns, slants and tilts around. 50% and 50% is the middle.">
        <Value label="Pivot across" value={get("pivot_x")} def={0.5} min={0} max={1} step={1} unit="%" shown={100} onChange={(v) => set({ pivot_x: v })} />
        <Value label="Pivot up and down" value={get("pivot_y")} def={0.5} min={0} max={1} step={1} unit="%" shown={100} onChange={(v) => set({ pivot_y: v })} />
      </Group>

      <Group title="Crop" set={crop.some((n) => n > 0) || get("crop_radius") > 0} hint="Cut away the edges. Rounded corners make it a card, a pill or a circle.">
        {["Crop the top", "Crop the right", "Crop the bottom", "Crop the left"].map((label, i) => (
          <Value key={label} label={label} value={crop[i]} def={0} min={0} max={0.95} step={1} unit="%" shown={100} onChange={(v) => setCrop(i, v)} />
        ))}
        <Value label="Rounded corners" value={get("crop_radius")} def={0} min={0} max={1} step={1} unit="%" shown={100} onChange={(v) => set({ crop_radius: v })} />
      </Group>

      <Group title="Corner pin (warp)" set={hasTransform({ warp: t.warp })} hint="Move each corner on its own, to fit a screen, a sign or a wall.">
        <div className="row wrap" style={{ gap: 6 }}>
          {onPin && <button className="btn sm" aria-pressed={!!pinning} onClick={() => onPin(!pinning)}>{pinning ? "Done pinning" : "Pin the corners on the picture"}</button>}
          <button className="btn ghost sm" disabled={!t.warp} onClick={() => set({ warp: null })}>Reset corners</button>
        </div>
        {pins.map((c, i) => (
          <div key={names[i]} className="col" style={{ gap: 2 }}>
            <span className="small muted">{names[i]}</span>
            <Value label={`${names[i]} across`} value={c[0]} def={0} min={-1} max={1} step={1} unit="%" shown={100} onChange={(v) => setPin(i, 0, v)} />
            <Value label={`${names[i]} up and down`} value={c[1]} def={0} min={-1} max={1} step={1} unit="%" shown={100} onChange={(v) => setPin(i, 1, v)} />
          </div>
        ))}
      </Group>

      <Group title="Blur and blend" set={get("blur") > 0 || get("blend") !== "normal"}>
        <Value onKeyframe={frame("blur")} label="Blur" value={get("blur")} def={0} min={0} max={60} step={1} unit="px" onChange={(v) => set({ blur: v })} />
        <label className="field"><span>Blend with what is behind it</span>
          <select value={get("blend")} onChange={(e) => set({ blend: e.target.value })}>{BLENDS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>
        </label>
      </Group>

      <button className="btn ghost sm" disabled={!hasTransform(t)} onClick={() => patch({ transform: null })}>Reset stretch, tilt, crop, corners and effects</button>
    </div>
  );
}
