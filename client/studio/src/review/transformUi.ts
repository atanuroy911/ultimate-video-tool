import { useSyncExternalStore } from "react";

/** What the handles on the picture do: move, size and turn the selected element, or pin its four corners (plan step E17). Shared by the Position tab and the canvas. */
export type HandleMode = "move" | "warp";
let mode: HandleMode = "move";
const listeners = new Set<() => void>();
export const setHandleMode = (m: HandleMode) => { if (m !== mode) { mode = m; listeners.forEach((f) => f()); } };
const subscribe = (f: () => void) => { listeners.add(f); return () => { listeners.delete(f); }; };
export const useHandleMode = (): [HandleMode, (m: HandleMode) => void] => [useSyncExternalStore(subscribe, () => mode), setHandleMode];

/** The selected element as the page last measured it (the preview's `rect` message): where it is and, for an element automatic layout placed,
 *  the scale that keeps its current size once a hand takes it over (gestures.fitOf). Typing a value in the Position tab uses it the way a drag
 *  does, so the first edit of a laid-out element never makes it jump to its own size. */
export interface Measured { scene: string; index: number; free: boolean; fit?: number; cx?: number; cy?: number }
let measured: Measured | null = null;
export const setMeasured = (m: Measured | null) => { measured = m; };
export const measuredFor = (scene: string, index: number) => (measured && measured.scene === scene && measured.index === index ? measured : null);
