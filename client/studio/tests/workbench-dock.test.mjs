import test from 'node:test';
import assert from 'node:assert/strict';
const D = await import('../src/workbench/dock.ts');

const all = new Set(D.PANES);
const view = { width: 1440, height: 860 };
const area = (r) => r.width * r.height;
const overlap = (a, b) => a.left < b.left + b.width && b.left < a.left + a.width && a.top < b.top + b.height && b.top < a.top + a.height;

test('the default tree has every pane once, and reads back as itself', () => {
  const tree = D.defaultDockTree();
  assert.deepEqual(D.readDockTree(JSON.parse(JSON.stringify(tree)), D.PANES), tree);
});

test('the default layout is the OpenFilm shape: library | viewer | inspector over a full-width timeline, the assistant as tall as the window', () => {
  const { panels } = D.dockFrames(D.defaultDockTree(), view, all);
  assert.equal(panels.assistant.height, view.height, 'the assistant takes the full height');
  assert.equal(panels.assistant.width, D.DEFAULT_SIZES.assistant);
  assert.equal(panels.timeline.left, 0);
  assert.equal(panels.timeline.height, D.DEFAULT_SIZES.timeline);
  assert.ok(panels.library.left < panels.viewer.left && panels.viewer.left < panels.inspector.left);
  assert.equal(panels.library.width, D.DEFAULT_SIZES.library);
  assert.equal(panels.inspector.width, D.DEFAULT_SIZES.inspector);
  assert.ok(panels.timeline.top >= panels.viewer.top + panels.viewer.height, 'the timeline is under the three panes');
});

test('panes never overlap and fill the window apart from one-pixel seams', () => {
  const { panels, seams } = D.dockFrames(D.defaultDockTree(), view, all);
  const list = Object.values(panels);
  for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) assert.ok(!overlap(list[i], list[j]), `${i} and ${j} overlap`);
  const filled = list.reduce((s, r) => s + area(r), 0) + seams.reduce((s, x) => s + area(x.rect), 0);
  assert.ok(Math.abs(filled - view.width * view.height) / (view.width * view.height) < 0.01, `filled ${filled}`);
  assert.equal(seams.length, 4);
});

test('a hidden pane gives its room to its neighbours and keeps its place', () => {
  const tree = D.defaultDockTree();
  const without = new Set(D.PANES.filter((p) => p !== 'inspector'));
  const a = D.dockFrames(tree, view, all).panels, b = D.dockFrames(tree, view, without).panels;
  assert.equal(b.inspector, undefined);
  assert.ok(b.viewer.width > a.viewer.width, 'the viewer takes the inspector\'s room');
  const back = D.dockFrames(tree, view, all).panels;
  assert.deepEqual(back.inspector, a.inspector, 'showing it again restores it');
  const alone = D.dockFrames(tree, view, new Set(['viewer'])).panels;
  assert.deepEqual(alone.viewer, { left: 0, top: 0, width: view.width, height: view.height }, 'the viewer alone fills the window');
});

test('a small window shrinks the panes but never below their minimums where it can help it', () => {
  const small = { width: 1000, height: 600 };
  const { panels } = D.dockFrames(D.defaultDockTree(), small, all);
  assert.ok(panels.viewer.width >= 100 && panels.viewer.height > 0);
  for (const [name, r] of Object.entries(panels)) assert.ok(r.width >= 0 && r.height >= 0, name);
  const total = panels.library.width + panels.viewer.width + panels.inspector.width + panels.assistant.width;
  assert.ok(total <= small.width, 'the columns fit');
});

test('the top inset leaves room for the bar above', () => {
  const { panels, root } = D.dockFrames(D.defaultDockTree(), view, all, undefined, 40);
  assert.equal(root.top, 40);
  assert.equal(panels.assistant.top, 40);
  assert.equal(panels.assistant.height, view.height - 40);
});

test('dragging a seam sets a ratio and ends the fixed size; sizes keep to their range', () => {
  let tree = D.defaultDockTree();
  const { seams } = D.dockFrames(tree, view, all);
  const outer = seams.find((s) => s.path === '');
  tree = D.resizeDock(tree, '', 0.6);
  const moved = D.dockFrames(tree, view, all).panels;
  assert.ok(Math.abs(moved.assistant.width - (view.width - 1) * 0.4) < 3, `assistant ${moved.assistant.width}`);
  const squeezed = D.dockFrames(D.resizeDock(D.defaultDockTree(), '', 0.3), view, all).panels;
  assert.ok(squeezed.library.width >= D.MINIMUMS.library[0] && squeezed.viewer.width >= D.MINIMUMS.viewer[0], 'a seam never squeezes panes below their minimums');
  assert.equal(outer.axis, 'x');
  const bigger = D.withPaneSize(D.defaultDockTree(), 'assistant', 10000);
  assert.equal(D.paneSizeOf(bigger, 'assistant'), D.SIZE_RANGE.assistant[1]);
  const smaller = D.withPaneSize(D.defaultDockTree(), 'library', 5);
  assert.equal(D.paneSizeOf(smaller, 'library'), D.SIZE_RANGE.library[0]);
  assert.equal(D.paneSizeOf(D.defaultDockTree(), 'timeline'), D.DEFAULT_SIZES.timeline);
});

test('moving a pane puts it beside another, on the window edge, or swaps two', () => {
  const tree = D.defaultDockTree();
  const swapped = D.moveDock(tree, 'library', 'inspector', 'center');
  const f = D.dockFrames(swapped, view, all).panels;
  assert.ok(f.inspector.left < f.viewer.left && f.viewer.left < f.library.left, 'library and inspector changed places');
  const edge = D.moveDock(tree, 'timeline', 'root', 'top');
  const g = D.dockFrames(edge, view, all).panels;
  assert.ok(g.timeline.top < g.viewer.top && g.timeline.width === view.width, 'the timeline is now across the top');
  const beside = D.moveDock(tree, 'assistant', 'library', 'bottom');
  const h = D.dockFrames(beside, view, all).panels;
  assert.ok(h.assistant.top > h.library.top && Object.keys(h).length === 5, 'every pane is still there');
  assert.equal(D.moveDock(tree, 'viewer', 'viewer', 'left'), tree, 'moving onto itself does nothing');
});

test('drop targets: the middle swaps, the sides split, the window edge is its own target', () => {
  const { panels, root } = D.dockFrames(D.defaultDockTree(), view, all);
  const v = panels.viewer;
  const centre = D.dockDropAt(panels, root, v.left + v.width / 2, v.top + v.height / 2, 'library');
  assert.deepEqual([centre.target, centre.edge], ['viewer', 'center']);
  const left = D.dockDropAt(panels, root, v.left + 5, v.top + v.height / 2, 'library');
  assert.deepEqual([left.target, left.edge], ['viewer', 'left']);
  assert.ok(Math.abs(left.preview.width - v.width / 2) < 1);
  const edge = D.dockDropAt(panels, root, 3, 400, 'library');
  assert.deepEqual([edge.target, edge.edge], ['root', 'left']);
  assert.equal(D.dockDropAt(panels, root, -50, 400, 'library'), null);
  const self = D.dockDropAt(panels, root, v.left + v.width / 2, v.top + v.height / 2, 'viewer');
  assert.notEqual(self && self.target, 'viewer', 'a pane is never dropped on itself');
});

test('a saved tree that is damaged or incomplete is refused, not trusted', () => {
  const good = JSON.parse(JSON.stringify(D.defaultDockTree()));
  assert.ok(D.readDockTree(good, D.PANES));
  assert.equal(D.readDockTree(null, D.PANES), null);
  assert.equal(D.readDockTree({ panel: 'viewer' }, D.PANES), null, 'a tree with panes missing');
  assert.equal(D.readDockTree({ axis: 'x', ratio: 5, first: { panel: 'viewer' }, second: { panel: 'library' } }), null, 'a ratio out of range');
  assert.equal(D.readDockTree({ axis: 'x', ratio: 0.5, first: { panel: 'viewer' }, second: { panel: 'viewer' } }), null, 'a pane twice');
  assert.equal(D.readDockTree({ axis: 'z', ratio: 0.5, first: { panel: 'viewer' }, second: { panel: 'library' } }), null, 'an unknown axis');
  assert.equal(D.readDockTree({ panel: 'Bad Name' }), null, 'a pane name that is not a name');
  const deep = (n) => n === 0 ? { panel: 'a' + n } : { axis: 'x', ratio: 0.5, first: deep(n - 1), second: { panel: 'b' + n } };
  assert.equal(D.readDockTree(deep(30)), null, 'absurd depth');
});
