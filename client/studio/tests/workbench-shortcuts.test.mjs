import test from 'node:test';
import assert from 'node:assert/strict';
const { paneAction } = await import('../src/workbench/shortcuts.ts');
const key = (k, mods = '') => ({ key: k, ctrlKey: mods.includes('c'), metaKey: mods.includes('m'), altKey: mods.includes('a'), shiftKey: mods.includes('s') });

test('the pane keys do what VS Code people expect', () => {
  assert.equal(paneAction(key('B', 'cs'), false), 'library', 'Ctrl+Shift+B (a capital B)');
  assert.equal(paneAction(key('b', 'cs'), false), 'library');
  assert.equal(paneAction(key('b', 'ca'), false), 'assistant');
  assert.equal(paneAction(key('j', 'c'), false), 'timeline');
  assert.equal(paneAction(key('i', 'ca'), false), 'inspector');
  assert.equal(paneAction(key('l', 'c'), false), 'focus-assistant');
  assert.equal(paneAction(key('P', 'cs'), false), 'palette');
  assert.equal(paneAction(key('b', 'ms'), false), 'library', 'Cmd works as Ctrl on a Mac');
});

test('typing is never interrupted, except by the two keys meant for it', () => {
  for (const [k, mods] of [['b', 'cs'], ['b', 'ca'], ['j', 'c'], ['i', 'ca']]) assert.equal(paneAction(key(k, mods), true), null, `${k} ${mods}`);
  assert.equal(paneAction(key('l', 'c'), true), 'focus-assistant');
  assert.equal(paneAction(key('p', 'cs'), true), 'palette');
});

test('other keys and other chords are left alone', () => {
  assert.equal(paneAction(key('b', ''), false), null, 'a plain b');
  assert.equal(paneAction(key('b', 's'), false), null);
  assert.equal(paneAction(key('b', 'c'), false), null, 'Ctrl+B stays split-the-clip in the timeline');
  assert.equal(paneAction(key('i', 'cs'), false), null, 'Ctrl+Shift+I is the developer tools');
  assert.equal(paneAction(key('j', 'ca'), false), null);
  assert.equal(paneAction(key('z', 'c'), false), null);
  assert.equal(paneAction(key('p', 'c'), false), null, 'Ctrl+P alone is print');
});
