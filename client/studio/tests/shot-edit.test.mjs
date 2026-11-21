import test from 'node:test';
import assert from 'node:assert/strict';
const S = await import('../src/review/shotEdit.ts');

test('an edit to one element keeps the others and writes "no edit" the same way every time', () => {
  let o = S.editElement(S.EMPTY, 'title', { x: 10, style: { color: '#ff0000' } });
  o = S.editElement(o, 'title', { style: { fontWeight: 700 } });
  assert.deepEqual(o.elements.title, { x: 10, style: { color: '#ff0000', fontWeight: 700 } });
  o = S.editElement(o, 'title', { x: 0, scale: 1, rotate: 0, hidden: false, style: { color: '', fontWeight: undefined } });
  assert.deepEqual(o, S.EMPTY, 'back to the shot as written');
  assert.deepEqual(S.resetElement(S.editElement(S.EMPTY, 'a', { x: 1 }), 'a'), S.EMPTY);
});

test('knobs are set and cleared', () => {
  const o = S.setKnob(S.EMPTY, '--accent', '#22c55e');
  assert.deepEqual(o.knobs, { '--accent': '#22c55e' });
  assert.deepEqual(S.setKnob(o, '--accent', '').knobs, {});
});

test('dragging adds to where the element already was', () => {
  const start = { x: 100, y: -20 };
  const o = S.moved(S.editElement(S.EMPTY, 'orb', start), 'orb', start, 15.333, 4);
  assert.deepEqual(o.elements.orb, { x: 115.33, y: -16 });
});

test('the corner handle scales by distance from the centre; the rotate handle turns, with steps on shift', () => {
  const rect = [0, 0, 200, 100];                                   // centre (100, 50)
  const big = S.scaled(S.EMPTY, 'a', {}, rect, [200, 50], [300, 50]);
  assert.equal(big.elements.a.scale, 2);
  const again = S.scaled(big, 'a', big.elements.a, rect, [200, 50], [150, 50]);
  assert.equal(again.elements.a, undefined, 'half the distance halves it: back to 1, which is no edit');
  assert.equal(S.scaled(S.EMPTY, 'a', {}, rect, [100, 50], [300, 50]), S.EMPTY, 'a press on the centre does nothing');
  const quarter = S.rotated(S.EMPTY, 'a', {}, rect, [200, 50], [100, 150]);
  assert.equal(quarter.elements.a.rotate, 90);
  const snapped = S.rotated(S.EMPTY, 'a', {}, rect, [200, 50], [200, 62], true);
  assert.equal(snapped.elements.a, undefined, 'a small turn snaps back to 0, which is no edit');
  const wrap = S.rotated(S.EMPTY, 'a', { rotate: 170 }, rect, [200, 50], [100, 150]);
  assert.equal(wrap.elements.a.rotate, -100, 'angles stay between -180 and 180');
});

test('undo and redo walk whole states and a new edit ends the redo list', () => {
  let h = S.historyOf(S.EMPTY);
  const a = S.setKnob(S.EMPTY, '--bg', '#000000'), b = S.setKnob(a, '--ink', '#ffffff');
  h = S.commit(S.commit(h, a), b);
  assert.equal(S.commit(h, b), h, 'the same state is not a step');
  h = S.undo(h);
  assert.deepEqual(h.now, a);
  h = S.redo(h);
  assert.deepEqual(h.now, b);
  h = S.commit(S.undo(h), S.setKnob(a, '--x', '1px'));
  assert.equal(h.future.length, 0);
  assert.equal(S.undo(S.historyOf(S.EMPTY)).now, S.EMPTY);
});

test('colours for the picker and the knobs the code declares', () => {
  assert.equal(S.asHex('#ABC'), '#aabbcc');
  assert.equal(S.asHex(' #10b981 '), '#10b981');
  assert.equal(S.asHex('rgb(1,2,3)'), null);
  assert.deepEqual(S.declaredKnobs(':root { --bg: #0f1226; --title-size: 132px; }\n#a{--no: 1}'), { '--bg': '#0f1226', '--title-size': '132px' });
});
