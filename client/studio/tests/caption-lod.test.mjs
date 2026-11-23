import test from 'node:test';
import assert from 'node:assert/strict';
const { mergeNarrow, wordSpots, wordTicks } = await import('../src/occ/bridge/captionLod.ts');

const w = (text, start, end) => ({ text, start, end });
const pages = [
  { words: [w('Your', 0, 280), w('smartwatch', 290, 840)], start: 0, end: 900 },
  { words: [w('battery', 910, 1290), w('is', 1300, 1410), w('not', 1420, 1640)], start: 910, end: 1700 },
  { words: [w('dying', 3000, 3400)], start: 3000, end: 3400 },              // after a long pause
];

test('zoomed out, narrow lines join until readable; a long pause keeps them apart', () => {
  const far = mergeNarrow(pages, 0.05);                                       // 50 px a second: each line is under 84 px
  assert.equal(far.length, 2);
  assert.deepEqual(far[0].words.map((x) => x.text), ['Your', 'smartwatch', 'battery', 'is', 'not']);
  assert.equal(far[1].words[0].text, 'dying');
  const near = mergeNarrow(pages, 0.2);                                       // 200 px a second: every line has room
  assert.equal(near.length, 3);
  assert.equal(pages[0].words.length, 2, 'the pages given are not changed');
});

test('words are drawn one by one only when each has room, ticks otherwise', () => {
  assert.equal(wordSpots(pages[1], 0.05), null);
  assert.equal(wordSpots(pages[1], 0.1), null, "\"is\" is 12 px at this zoom: not yet");
  const spots = wordSpots(pages[1], 0.4);
  assert.deepEqual(spots.map((s) => s.text), ['battery', 'is', 'not']);
  assert.ok(spots.every((s) => s.width >= 22));
  assert.equal(spots[1].left, (1300 - 910) * 0.4);
  assert.deepEqual(wordTicks(pages[1], 0.05), [20, 26]);
});
