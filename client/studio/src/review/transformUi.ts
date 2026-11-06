import { useSyncExternalStore } from "react";

/** What the handles on the picture do: move, size and turn the selected element, or pin its four corners (plan step E17). Shared by the Position tab and the canvas. */
export type HandleMode = "move" | "warp";
let mode: HandleMode = "move";
const listeners = new Set<() => void>();
export const setHandleMode = (m: HandleMode) => { if (m !== mode) { mode = m; listeners.forEach((f) => f()); } };
const subscribe = (f: () => void) => { listeners.add(f); return () => { listeners.delete(f); }; };
export const useHandleMode = (): [HandleMode, (m: HandleMode) => void] => [useSyncExternalStore(subscribe, () => mode), setHandleMode];
