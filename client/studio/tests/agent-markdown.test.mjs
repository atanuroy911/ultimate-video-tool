import test from 'node:test';
import assert from 'node:assert/strict';
const { blocks, inline } = await import('../src/assistant/markdown.ts');

test('paragraphs, lists, bold and code, and nothing becomes markup', () => {
  const b = blocks('I changed **two** things:\n\n- the `title` size\n- scene 3\n\n1. one\n2. two\n\n<script>alert(1)</script>');
  assert.deepEqual(b.map((x) => x.kind), ['p', 'ul', 'ol', 'p']);
  assert.deepEqual(b[0].lines[0], [{ kind: 'text', text: 'I changed ' }, { kind: 'bold', text: 'two' }, { kind: 'text', text: ' things:' }]);
  assert.deepEqual(b[1].items[0][1], { kind: 'code', text: 'title' });
  assert.equal(b[3].lines[0][0].text, '<script>alert(1)</script>', 'stays text');
  assert.deepEqual(inline('a ** b'), [{ kind: 'text', text: 'a ** b' }]);
});
