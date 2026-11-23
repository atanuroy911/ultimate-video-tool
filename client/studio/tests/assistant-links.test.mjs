import test from 'node:test';
import assert from 'node:assert/strict';
const L = await import('../src/assistant/links.ts');

test('the four kinds of link are read', () => {
  assert.deepEqual(L.parseVtLink('vt://scene/s3'), { kind: 'scene', scene: 's3' });
  assert.deepEqual(L.parseVtLink('vt://t/12.5'), { kind: 'time', t: 12.5 });
  assert.deepEqual(L.parseVtLink('vt://element/s3/2'), { kind: 'element', scene: 's3', index: 2 });
  assert.deepEqual(L.parseVtLink('vt://range/0/3.1'), { kind: 'range', from: 0, to: 3.1 });
});

test('anything else is not a link', () => {
  for (const bad of ['vt://scene/../../', 'vt://scene/', 'vt://scene/s3/extra', 'vt://t/-1', 'vt://t/1e9', 'vt://t/NaN', 'vt://element/s3/x', 'vt://element/s3/1000',
    'vt://range/5/1', 'vt://file/C:/secrets', 'vt://scene/s 3', 'http://example.com', 'javascript:alert(1)', 'VT://scene/s1', 'vt:scene/s1', '', 'vt://scene/s3?x=1', 'vt://scene/s3#a'])
    assert.equal(L.parseVtLink(bad), null, bad);
});

test('a reply is cut into text and links; a link that is not ours keeps only its words', () => {
  assert.deepEqual(L.pieces('I made [scene 3](vt://scene/s3) bigger, see [here](https://evil.example/x) and [oops](vt://scene/../..).'), [
    { text: 'I made ' }, { label: 'scene 3', link: { kind: 'scene', scene: 's3' } }, { text: ' bigger, see ' }, { text: 'here' }, { text: ' and ' }, { text: 'oops' }, { text: '.' }]);
  assert.deepEqual(L.pieces('no links'), [{ text: 'no links' }]);
  assert.deepEqual(L.pieces(''), []);
});

test('a long hostile reply does not hang the parser', () => {
  const t0 = Date.now();
  L.pieces('['.repeat(50000) + '](' + 'a'.repeat(50000));
  assert.ok(Date.now() - t0 < 500);
});
