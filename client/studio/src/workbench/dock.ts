// Ported from OpenFilm (MIT, github.com/openfilm/openfilm) packages/openfilm/studio/ui/src/lib/workspace-dock.ts @ a1b8d75. See THIRD-PARTY.md.
// Changed for Video Tool: our five panes (viewer, library, inspector, timeline, assistant) instead of its plugin blocks, no plugin arrangement spec,
// the top inset is a parameter, and sizes are kept as plain numbers. The tree, the frame maths, resizing, moving and drop targets are its own, unchanged in behaviour.
//
// A workspace is a tree of splits over the panes. A split holds either a ratio of its parent, or a fixed size on one side (`size` and `anchor`), which is what
// a person means by "the assistant is 400 wide". Hidden panes keep their place in the tree, so showing one again restores its position.

export type PaneId = 'viewer' | 'library' | 'inspector' | 'timeline' | 'assistant';
export const PANES: readonly PaneId[] = ['viewer', 'library', 'inspector', 'timeline', 'assistant'];
/** The viewer is the main pane: it is always shown and takes what is left. */
export const MAIN_PANE: PaneId = 'viewer';

export type DockPanel = string;
export type DockEdge = 'left' | 'right' | 'top' | 'bottom' | 'center';
export type DockNode = { panel: DockPanel } | { axis: 'x' | 'y'; ratio: number; first: DockNode; second: DockNode; size?: number; anchor?: 'first' | 'second' };
export type DockRect = { left: number; top: number; width: number; height: number };
export type DockSeam = { path: string; axis: 'x' | 'y'; rect: DockRect; parent: DockRect; ratio: number; min: number; max: number };

export interface PaneSizes { library: number; inspector: number; timeline: number; assistant: number }
export const DEFAULT_SIZES: Readonly<PaneSizes> = { library: 280, inspector: 300, timeline: 300, assistant: 400 };
/** How far each pane may be dragged: [smallest, largest] of its size (width, or height for the timeline). */
export const SIZE_RANGE: Readonly<Record<keyof PaneSizes, readonly [number, number]>> = {
  library: [220, 480], inspector: [240, 480], timeline: [160, 600], assistant: [320, 640],
};
/** The smallest each pane is drawn, as [width, height]. */
export const MINIMUMS: Readonly<Record<PaneId, readonly [number, number]>> = {
  viewer: [320, 200], library: [200, 140], inspector: [240, 140], timeline: [320, 140], assistant: [320, 180],
};

const leaf = (panel: DockPanel): DockNode => ({ panel });
const split = (axis: 'x' | 'y', first: DockNode, second: DockNode, size: number, anchor: 'first' | 'second'): DockNode => ({ axis, first, second, ratio: 0.5, size, anchor });

/**
 * The tree as the panes first sit: the assistant is outermost on one side and as tall as the window; inside it the timeline spans the bottom under
 * library | viewer | inspector (the layout of OpenFilm's editor).
 */
export function defaultDockTree(sizes: PaneSizes = DEFAULT_SIZES, assistantSide: 'left' | 'right' = 'right'): DockNode {
  const middle = split('x', leaf('viewer'), leaf('inspector'), sizes.inspector, 'second');
  const top = split('x', leaf('library'), middle, sizes.library, 'first');
  const main = split('y', top, leaf('timeline'), sizes.timeline, 'second');
  return assistantSide === 'left' ? split('x', leaf('assistant'), main, sizes.assistant, 'first') : split('x', main, leaf('assistant'), sizes.assistant, 'second');
}

const KEY = /^[a-z][a-z0-9-]{0,31}$/;
/** A tree of splits as kept: each panel once, named as a pane is; `keys`, when given, the panels it must have, all of them. Anything else reads as null. */
export function readDockTree(value: unknown, keys?: readonly DockPanel[]): DockNode | null {
  const seen = new Set<DockPanel>();
  const read = (value: unknown, depth: number): DockNode | null => {
    if (!value || typeof value !== 'object' || Array.isArray(value) || depth > 12) return null;
    const node = value as Record<string, unknown>;
    if ('panel' in node) {
      if (typeof node.panel !== 'string' || !KEY.test(node.panel) || seen.has(node.panel) || (keys && !keys.includes(node.panel)) || seen.size >= 40) return null;
      seen.add(node.panel); return leaf(node.panel);
    }
    if (!['x', 'y'].includes(node.axis as string) || typeof node.ratio !== 'number' || !Number.isFinite(node.ratio) || node.ratio < 0.02 || node.ratio > 0.98) return null;
    if (node.size !== undefined && (typeof node.size !== 'number' || !Number.isFinite(node.size) || node.size < 1 || node.size > 4000 || !['first', 'second'].includes(node.anchor as string))) return null;
    const first = read(node.first, depth + 1), second = read(node.second, depth + 1);
    return first && second ? { axis: node.axis as 'x' | 'y', ratio: node.ratio, first, second, ...(node.size !== undefined ? { size: node.size as number, anchor: node.anchor as 'first' | 'second' } : {}) } : null;
  };
  const node = read(value, 0);
  return node && (!keys || seen.size === keys.length) ? node : null;
}

/** Where every visible panel goes in a window, and the seams between them to drag. Hidden panels give their room to their neighbours. */
export function dockFrames(tree: DockNode, viewport: { width: number; height: number }, visible: ReadonlySet<DockPanel>,
  minimumOf: (panel: DockPanel) => readonly [number, number] = (p) => MINIMUMS[p as PaneId] ?? [240, 180], topInset = 0) {
  const panels: Partial<Record<DockPanel, DockRect>> = {}, seams: DockSeam[] = [];
  const minimum = (node: DockNode): readonly [number, number] | null => {
    if ('panel' in node) return visible.has(node.panel) ? minimumOf(node.panel) : null;
    const a = minimum(node.first), b = minimum(node.second);
    if (!a) return b; if (!b) return a;
    return node.axis === 'x' ? [a[0] + b[0] + 1, Math.max(a[1], b[1])] : [Math.max(a[0], b[0]), a[1] + b[1] + 1];
  };
  const walk = (node: DockNode, rect: DockRect, path: string) => {
    if ('panel' in node) { if (visible.has(node.panel)) panels[node.panel] = rect; return; }
    const a = minimum(node.first), b = minimum(node.second);
    if (!a) { if (b) walk(node.second, rect, path + '1'); return; }
    if (!b) { walk(node.first, rect, path + '0'); return; }
    const horizontal = node.axis === 'x', room = Math.max(0, (horizontal ? rect.width : rect.height) - 1);
    const minA = a[horizontal ? 0 : 1], minB = b[horizontal ? 0 : 1];
    const fit = Math.min(1, room / (minA + minB)), lo = minA * fit, hi = room - minB * fit;
    const preferred = node.size === undefined ? room * node.ratio : node.anchor === 'first' ? node.size : room - node.size;
    const first = Math.max(0, Math.min(room, Math.round(Math.max(lo, Math.min(hi, preferred)))));
    const second = Math.max(0, room - first), gap = Math.min(1, horizontal ? rect.width : rect.height);
    const seam = horizontal ? { left: rect.left + first, top: rect.top, width: gap, height: rect.height } : { left: rect.left, top: rect.top + first, width: rect.width, height: gap };
    seams.push({ path, axis: node.axis, rect: seam, parent: rect, ratio: room ? first / room : 0.5, min: room ? lo / room : 0.5, max: room ? hi / room : 0.5 });
    walk(node.first, { ...rect, ...(horizontal ? { width: first } : { height: first }) }, path + '0');
    walk(node.second, { ...rect, ...(horizontal ? { left: rect.left + first + gap, width: second } : { top: rect.top + first + gap, height: second }) }, path + '1');
  };
  const root = { left: 0, top: topInset, width: Math.max(0, viewport.width), height: Math.max(0, viewport.height - topInset) };
  walk(tree, root, '');
  return { panels, seams, root };
}

/** Drag a seam: the split at `path` takes this ratio of its parent (and stops being a fixed size). */
export function resizeDock(tree: DockNode, path: string, ratio: number): DockNode {
  if ('panel' in tree) return tree;
  if (!path) { const { size: _size, anchor: _anchor, ...node } = tree; return { ...node, ratio: Math.max(0.02, Math.min(0.98, ratio)) }; }
  return path[0] === '0' ? { ...tree, first: resizeDock(tree.first, path.slice(1), ratio) } : { ...tree, second: resizeDock(tree.second, path.slice(1), ratio) };
}

/** Drop a panel beside another (`edge` left, right, top or bottom of `target`), on the window's edge (`target` = 'root'), or swap two (`edge` = 'center'). */
export function moveDock(tree: DockNode, panel: DockPanel, target: DockPanel | 'root', edge: DockEdge): DockNode {
  if (panel === target) return tree;
  if (edge === 'center' && target !== 'root') {
    const swap = (node: DockNode): DockNode => 'panel' in node ? leaf(node.panel === panel ? target : node.panel === target ? panel : node.panel) : { ...node, first: swap(node.first), second: swap(node.second) };
    return swap(tree);
  }
  const remove = (node: DockNode): DockNode | null => {
    if ('panel' in node) return node.panel === panel ? null : node;
    const a = remove(node.first), b = remove(node.second);
    return a && b ? { ...node, first: a, second: b } : a ?? b;
  };
  const beside = (node: DockNode): DockNode => {
    const before = edge === 'left' || edge === 'top';
    return { axis: edge === 'left' || edge === 'right' ? 'x' : 'y', ratio: 0.5, first: before ? leaf(panel) : node, second: before ? node : leaf(panel) };
  };
  const rest = remove(tree); if (!rest) return tree;
  if (target === 'root') return beside(rest);
  const insert = (node: DockNode): DockNode => 'panel' in node ? node.panel === target ? beside(node) : node : { ...node, first: insert(node.first), second: insert(node.second) };
  return insert(rest);
}

/** Where a panel dragged to (x, y) would land: on which panel and edge (the middle swaps), or the window's own edge. null outside the window. */
export function dockDropAt(panels: Partial<Record<DockPanel, DockRect>>, root: DockRect, x: number, y: number, source: DockPanel): { target: DockPanel | 'root'; edge: DockEdge; preview: DockRect } | null {
  if (x < root.left || y < root.top || x > root.left + root.width || y > root.top + root.height) return null;
  const preview = (r: DockRect, edge: DockEdge): DockRect => edge === 'center' ? r : edge === 'left' ? { ...r, width: r.width / 2 } : edge === 'right' ? { ...r, left: r.left + r.width / 2, width: r.width / 2 } : edge === 'top' ? { ...r, height: r.height / 2 } : { ...r, top: r.top + r.height / 2, height: r.height / 2 };
  const outer: DockEdge | null = x - root.left < 16 ? 'left' : root.left + root.width - x < 16 ? 'right' : y - root.top < 16 ? 'top' : root.top + root.height - y < 16 ? 'bottom' : null;
  if (outer) return { target: 'root', edge: outer, preview: preview(root, outer) };
  for (const [panel, r] of Object.entries(panels) as [DockPanel, DockRect][]) {
    if (panel === source || x < r.left || x > r.left + r.width || y < r.top || y > r.top + r.height) continue;
    const px = (x - r.left) / r.width, py = (y - r.top) / r.height;
    const edge: DockEdge = px > 0.28 && px < 0.72 && py > 0.28 && py < 0.72 ? 'center' : Math.min(px, 1 - px) < Math.min(py, 1 - py) ? px < 0.5 ? 'left' : 'right' : py < 0.5 ? 'top' : 'bottom';
    return { target: panel, edge, preview: preview(r, edge) };
  }
  return null;
}

/** The size a fixed-size split gives a pane, read back from a tree (for saving what the person dragged). */
export function paneSizeOf(tree: DockNode, panel: DockPanel): number | null {
  if ('panel' in tree) return null;
  const hasPanel = (n: DockNode, p: DockPanel): boolean => 'panel' in n ? n.panel === p : hasPanel(n.first, p) || hasPanel(n.second, p);
  if (tree.size !== undefined) {
    const side = tree.anchor === 'first' ? tree.first : tree.second;
    if ('panel' in side && side.panel === panel) return tree.size;
  }
  return hasPanel(tree.first, panel) ? paneSizeOf(tree.first, panel) : hasPanel(tree.second, panel) ? paneSizeOf(tree.second, panel) : null;
}

/** A pane's fixed size, changed (kept inside its range); a tree whose split for it has no fixed size is returned as it is. */
export function withPaneSize(tree: DockNode, panel: DockPanel, size: number): DockNode {
  if ('panel' in tree) return tree;
  const range = SIZE_RANGE[panel as keyof PaneSizes];
  const side = tree.size !== undefined ? (tree.anchor === 'first' ? tree.first : tree.second) : null;
  if (side && 'panel' in side && side.panel === panel && range) return { ...tree, size: Math.max(range[0], Math.min(range[1], Math.round(size))) };
  return { ...tree, first: withPaneSize(tree.first, panel, size), second: withPaneSize(tree.second, panel, size) };
}
