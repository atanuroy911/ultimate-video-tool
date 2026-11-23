// The editor's panes (library, viewer, inspector, timeline, assistant) laid out as a tree of splits (dock.ts, ported from OpenFilm, MIT): drag a divider, or focus it
// and use the arrow keys; hide a pane and its neighbours take its room; the sizes are remembered per layout. The panes themselves are the parent's: this only places them.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { DEFAULT_SIZES, MAIN_PANE, PANES, dockFrames, defaultDockTree, readDockTree, resizeSeam, type DockNode, type DockSeam, type PaneId } from "./dock";
import "./workbench.css";

const KEY = "vt.workbench.v1.";
const TOP = 0;

function load(layoutKey: string): DockNode {
  try {
    const raw = localStorage.getItem(KEY + layoutKey);
    return (raw && readDockTree(JSON.parse(raw), PANES)) || defaultDockTree();
  } catch { return defaultDockTree(); }
}
function save(layoutKey: string, tree: DockNode) {
  try { localStorage.setItem(KEY + layoutKey, JSON.stringify(tree)); } catch { /* private window: it just is not remembered */ }
}

export interface WorkbenchProps {
  /** What goes in each pane. A pane that is not given is simply not there. */
  panes: Partial<Record<PaneId, ReactNode>>;
  /** Which panes are shown; the viewer always is. */
  shown: Partial<Record<PaneId, boolean>>;
  /** Where the sizes are remembered. */
  layoutKey: string;
  /** Called with the window's size in pixels whenever it changes (for the parent's own small-window rules). */
  onSize?: (size: { width: number; height: number }) => void;
}

export default function Workbench({ panes, shown, layoutKey, onSize }: WorkbenchProps) {
  const root = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [tree, setTree] = useState<DockNode>(() => load(layoutKey));
  const [dragging, setDragging] = useState<string | null>(null);
  const treeRef = useRef(tree);
  treeRef.current = tree;

  useEffect(() => { setTree(load(layoutKey)); }, [layoutKey]);
  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const measure = () => { const r = el.getBoundingClientRect(); setSize((s) => (s.width === r.width && s.height === r.height ? s : { width: r.width, height: r.height })); };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  useEffect(() => { onSize?.(size); }, [size, onSize]);

  const visible = useMemo(() => new Set<string>(PANES.filter((p) => panes[p] != null && (p === MAIN_PANE || shown[p]))), [panes, shown]);
  const { panels, seams } = useMemo(() => dockFrames(tree, size, visible, undefined, TOP), [tree, size, visible]);

  const move = useCallback((seam: DockSeam, pixels: number) => {
    // `pixels`: where the first pane should end, from the start of the split's own rectangle
    const horizontal = seam.axis === "x";
    const room = Math.max(1, (horizontal ? seam.parent.width : seam.parent.height) - 1);
    const lo = seam.min * room, hi = seam.max * room;
    setTree((t) => resizeSeam(t, seam.path, Math.max(lo, Math.min(hi, pixels)), room));
  }, []);

  const onPointerDown = (seam: DockSeam) => (e: React.PointerEvent) => {
    e.preventDefault();
    (e.target as Element).setPointerCapture?.(e.pointerId);
    setDragging(seam.path);
    const horizontal = seam.axis === "x";
    const origin = horizontal ? seam.parent.left : seam.parent.top;
    const rootBox = root.current!.getBoundingClientRect();
    const onMove = (ev: PointerEvent) => move(seam, (horizontal ? ev.clientX - rootBox.left : ev.clientY - rootBox.top) - origin);
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      setDragging(null);
      save(layoutKey, treeRef.current);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const onKey = (seam: DockSeam) => (e: React.KeyboardEvent) => {
    const horizontal = seam.axis === "x";
    const room = Math.max(1, (horizontal ? seam.parent.width : seam.parent.height) - 1);
    const step = e.shiftKey ? 64 : 16;
    const grow = horizontal ? "ArrowRight" : "ArrowDown", shrink = horizontal ? "ArrowLeft" : "ArrowUp";
    if (e.key !== grow && e.key !== shrink && e.key !== "Home" && e.key !== "End") return;
    e.preventDefault();
    const now = seam.ratio * room;
    move(seam, e.key === "Home" ? 0 : e.key === "End" ? room : now + (e.key === grow ? step : -step));
    save(layoutKey, treeRef.current);
  };

  const reset = (seam: DockSeam) => () => { const t = defaultDockTree(); setTree(t); save(layoutKey, t); void seam; };

  return (
    <div className={`wb${dragging ? " wb-dragging" : ""}`} ref={root} data-testid="workbench">
      {PANES.map((p) => {
        const r = panels[p];
        if (panes[p] == null) return null;
        return (
          <div key={p} className={`wb-pane wb-${p}`} data-pane={p} data-open={r ? "true" : "false"} hidden={!r}
            style={r ? { left: r.left, top: r.top, width: r.width, height: r.height } : undefined}>
            {panes[p]}
          </div>
        );
      })}
      {seams.map((s) => (
        <div key={s.path} role="separator" aria-orientation={s.axis === "x" ? "vertical" : "horizontal"} tabIndex={0}
          aria-label={s.axis === "x" ? "Resize the panes (left and right arrows; double-click resets)" : "Resize the panes (up and down arrows; double-click resets)"}
          aria-valuenow={Math.round(s.ratio * 100)} aria-valuemin={Math.round(s.min * 100)} aria-valuemax={Math.round(s.max * 100)}
          className={`wb-seam wb-seam-${s.axis}${dragging === s.path ? " on" : ""}`}
          style={{ left: s.rect.left, top: s.rect.top, width: s.rect.width, height: s.rect.height }}
          onPointerDown={onPointerDown(s)} onKeyDown={onKey(s)} onDoubleClick={reset(s)} />
      ))}
    </div>
  );
}

export { DEFAULT_SIZES };
