// The bridge between our project and the ported OpenChatCut timeline (src/occ/bridge, docs/plans/PLAN-OPENCHATCUT.MD phase 1): what our
// project looks like on its tracks, and that OpenChatCut's own editing engine accepts the result and edits it.
import test from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';

// Node's native TypeScript loader, with Vite's extensionless imports and OpenChatCut's ".js" imports of ".ts" files.
registerHooks({ resolve(id, context, next) {
  try { return next(id, context); }
  catch (error) {
    if (id.startsWith('.') && id.endsWith('.js')) return next(id.slice(0, -3) + '.ts', context);
    if (id.startsWith('.')) { try { return next(`${id}.ts`, context); } catch { return next(`${id}.tsx`, context); } }
    throw error;
  }
} });
globalThis.localStorage = { getItem: () => null, setItem: () => {} };
const { fromProject, wordToEdited, VOICE_ID } = await import('../src/occ/bridge/fromProject.ts');
const { makeDraft } = await import('../src/occ/src/editor/store.ts');

const keep = [{ s: 0, e: 1.63, o0: 0, o1: 1.63 }, { s: 1.83, e: 4.95, o0: 1.63, o1: 4.75 }];
const word = (id, text, start, end, cut = false) => ({ id, text, start, end, cut, conf: 1, lang: 'en', flag: null });
const view = {
  projectId: 'p1', fps: 30, width: 1080, height: 1920, duration: 4.75,
  plan: { theme: 'paper', planner: 'claude', scenes: [
    { id: 's1', beats: [], layout: 'stack', transition_in: 'cut', elements: [{ type: 'title' }, { type: 'icon_row' }], caption: { highlight_words: [] }, backdrop: { media: 'm1', motion: 'kenburns', scrim: { ink: 'light', kind: 'none', strength: 0, ratio: 0 } } },
    { id: 's2', beats: [], layout: 'stack', transition_in: 'cut', elements: [], caption: { highlight_words: [] } },
  ] },
  timing: [{ id: 's1', start: 0, end: 2.2 }, { id: 's2', start: 2.2, end: 4.75 }],
  elementTimes: { 's1:0': { start: 0, end: 2.2 }, 's1:1': { start: 0.5, end: 1.5 } },
  words: [word('w1', 'Small', 0.1, 0.5), word('w2', 'A', 1.48, 1.72), word('w3', 'five', 1.72, 2.04), word('w4', '-minute', 2.04, 2.3),
    word('w5', 'gone', 1.65, 1.8), word('w6', 'um', 3.0, 3.2, true)],
  keep, audioUrl: '/media/p1/audio.cut.wav',
  layers: { v: 1, tracks: [{ id: 't1', name: 'Text', kind: 'visual', hidden: false, muted: false, locked: false }],
    clips: [{ id: 'c1', track: 't1', type: 'text', start: 1, dur: 2, fade_in: 0, fade_out: 0, text: 'Hello' }] },
  media: { m1: { id: 'm1', file: 'still.jpg', url: '/media/p1/media/still.jpg', kind: 'image', caption: 'A woman', tags: [], width: 720, height: 1280, duration: 0, source: 'comfyui' } },
  elementName: (t) => ({ title: 'Title', icon_row: 'Icons' })[t] ?? t,
};

test('a word that overlaps a cut pause keeps the part that is heard; one wholly inside a cut is gone', () => {
  assert.deepEqual(wordToEdited(1.48, 1.72, keep).map((x) => +x.toFixed(2)), [1.48, 1.63]);
  assert.deepEqual(wordToEdited(1.72, 2.04, keep).map((x) => +x.toFixed(2)), [1.63, 1.84]);
  assert.equal(wordToEdited(1.65, 1.8, keep), null);
});

test('our project on OpenChatCut tracks: captions, layers, elements in rows, scenes with their picture, the narration', () => {
  const doc = fromProject(view);
  const tl = doc.timelines[0];
  assert.deepEqual(tl.trackOrder, ['C1', 'L_t1', 'V4', 'V3', 'V1', 'A1']);
  assert.equal(tl.tracks.C1.captions.sourceItemId, VOICE_ID, 'the captions are the narration\'s words');
  const byId = Object.fromEntries(tl.items.map((i) => [i.id, i]));
  assert.equal(byId['scene:s1'].track, 'V1');
  assert.equal(byId['scene:s1'].src, '/media/p1/media/still.jpg');
  assert.equal(byId['scene:s2'].kind, 'solid', 'a scene without a picture is still a clip');
  assert.equal(byId['scene:s2'].startFrame, 66);
  assert.notEqual(byId['el:s1:0'].track, byId['el:s1:1'].track, 'overlapping elements get their own rows');
  assert.equal(byId['layer:c1'].track, 'L_t1');
  assert.deepEqual(doc.assets.map((a) => a.id), ['m1']);
  const words = byId[VOICE_ID].transcript.map((w) => w.text);
  assert.deepEqual(words, ['Small', 'A', 'five-minute'], 'cut words and words wholly in a cut pause are gone; "-minute" joins "five"');
});

test("OpenChatCut's own engine takes the result and edits it (move, trim, delete)", () => {
  const draft = makeDraft(fromProject(view));
  draft.commands.moveItem('layer:c1', { startFrame: 45 });
  draft.commands.setItemTiming('layer:c1', { startFrame: 45, durationInFrames: 30 });
  draft.commands.removeItem('el:s1:1');
  const items = draft.getState().items;
  const layer = items.find((i) => i.id === 'layer:c1');
  assert.equal(layer.startFrame, 45);
  assert.equal(layer.durationInFrames, 30);
  assert.equal(items.some((i) => i.id === 'el:s1:1'), false);
  assert.ok(draft.takeActions().length >= 3, 'each edit is a recorded action (phase 2 sends them to our server)');
});

// Phase 2: edits made with OpenChatCut's commands → our own edit calls (src/occ/bridge/toProject.ts)
const { planSave } = await import('../src/occ/bridge/toProject.ts');
const { activeEditorState } = await import('../src/occ/src/editor/types.ts');
const edit = (fn) => {
  const doc = fromProject(view);
  const draft = makeDraft(doc);
  fn(draft.commands, draft);
  return planSave(activeEditorState(doc), draft.getState(), 30, view.layers);
};

test('nothing changed (or only the selection) saves nothing', () => {
  assert.deepEqual(edit((c) => c.selectItem('scene:s1')).ops, []);
});

test('a layer moved or trimmed is saved in the layers document, other clip fields kept', () => {
  const { ops } = edit((c) => { c.moveItem('layer:c1', { startFrame: 45 }); c.setItemTiming('layer:c1', { startFrame: 45, durationInFrames: 30 }); });
  assert.equal(ops.length, 1);
  assert.equal(ops[0].kind, 'layers');
  const clip = ops[0].doc.clips.find((x) => x.id === 'c1');
  assert.deepEqual([clip.start, clip.dur, clip.text, clip.track], [1.5, 1, 'Hello', 't1']);
});

test('a layer split is two clips; a deleted one is gone; hiding its track is saved', () => {
  const split = edit((c) => c.splitItem('layer:c1', 60)).ops[0].doc.clips;
  assert.equal(split.length, 2);
  assert.deepEqual(split.map((x) => [x.start, x.dur]).sort(), [[1, 1], [2, 1]]);
  assert.equal(edit((c) => c.removeItem('layer:c1')).ops[0].doc.clips.length, 0);
  const hidden = edit((c) => c.updateTrack('L_t1', { hidden: true })).ops[0].doc.tracks[0];
  assert.equal(hidden.hidden, true);
});

test('an element trimmed, split or deleted becomes our element calls, deletes from the last index back', () => {
  assert.deepEqual(edit((c) => c.setItemTiming('el:s1:1', { startFrame: 15, durationInFrames: 20 })).ops,
    [{ kind: 'element', scene: 's1', index: 1, body: { start: 0.5, end: 1.167 } }]);
  assert.deepEqual(edit((c) => c.splitItem('el:s1:0', 30)).ops, [{ kind: 'element', scene: 's1', index: 0, body: { split: 1 } }]);
  const del = edit((c) => { c.removeItem('el:s1:0'); c.removeItem('el:s1:1'); }).ops;
  assert.deepEqual(del.map((o) => o.index), [1, 0]);
});

test("a scene's edge moved is our edge move on the scene to its left; a split and a removal too", () => {
  // scenes touch end to end in our project: the server moves the shared edge and closes any gap
  assert.deepEqual(edit((c) => c.setItemTiming('scene:s1', { durationInFrames: 60 })).ops, [{ kind: 'scene-edge', scene: 's1', t: 2 }]);
  assert.deepEqual(edit((c) => c.setItemTiming('scene:s2', { startFrame: 72, durationInFrames: 70 })).ops, [{ kind: 'scene-edge', scene: 's1', t: 2.4 }]);
  assert.deepEqual(edit((c) => c.splitItem('scene:s2', 100)).ops, [{ kind: 'scene-split', scene: 's2', t: 3.333 }]);
  assert.deepEqual(edit((c) => c.removeItem('scene:s2')).ops, [{ kind: 'scene-remove', scene: 's2' }]);
});

test('words removed from the narration become a cut, up to the next word still heard', () => {
  // OpenChatCut splits a narration with words into word streams: here "Small" | "A five-minute" | (tail); the middle piece is removed
  const { ops } = edit((c, d) => {
    c.splitItem(VOICE_ID, 30);
    const right = d.getState().items.find((i) => i.track === 'A1' && i.id !== VOICE_ID);
    c.splitItem(right.id, 60);
    c.removeItem(right.id);
  });
  // 4.767 s: the clip's length in whole frames (the narration is 4.75 s; the server clamps a cut to the end of the audio)
  assert.deepEqual(ops, [{ kind: 'voice-cut', start: 1.48, end: 4.767 }], '"A five-minute" and the pause after it (nothing is said after it)');
  // deleting a word in the transcript view: "A" (index 1) is cut up to "five-minute", the next word still heard
  assert.deepEqual(edit((c) => c.deleteWords(VOICE_ID, [1])).ops, [{ kind: 'voice-cut', start: 1.48, end: 1.63 }]);
  const tl = fromProject(view).timelines[0];
  assert.equal(tl.tracks.C1.locked, true, 'the captions track is locked: edited in the Captions panel for now');
});

test('a narration piece turned down or muted becomes the same gain or mute on our voice (W11.1, ported from the classic timeline)', () => {
  const quieter = edit((c, d) => {
    c.splitItem(VOICE_ID, 30);
    const right = d.getState().items.find((i) => i.track === 'A1' && i.id !== VOICE_ID);
    c.setItemVolume(right.id, 0.5);
  }).ops;
  assert.equal(quieter.length, 1);
  assert.equal(quieter[0].kind, 'voice-gain');
  assert.equal(quieter[0].start, 1.48, 'from the first word the piece plays');
  assert.equal(quieter[0].db, -6);
  const muted = edit((c) => c.setItemVolume(VOICE_ID, 0)).ops;
  assert.deepEqual(muted.map((o) => o.kind), ['voice-mute']);
});

test('stick-figure actions are a track; moving or deleting one is saved as the same action edit as on the classic timeline (W11.1)', () => {
  const stick = { cast: [], actions: [{ who: 'A', do: 'wave', at_word: 'w1', start: 0.5, end: 1.5 }, { who: 'B', do: 'jump', at_word: 'w2', start: 1.6, end: 2.0 }] };
  const withActs = { ...view, plan: { ...view.plan, scenes: view.plan.scenes.map((s, i) => (i === 0 ? { ...s, stick } : s)) } };
  const doc = fromProject(withActs);
  const items = doc.timelines[0].items.filter((i) => i.id.startsWith('act:'));
  assert.deepEqual(items.map((i) => [i.id, i.name]), [['act:s1:0', 'A wave'], ['act:s1:1', 'B jump']]);
  const draft = makeDraft(doc);
  draft.commands.removeItem('act:s1:1');
  draft.commands.moveItem('act:s1:0', { startFrame: 30 });
  const { ops } = planSave(activeEditorState(doc), draft.getState(), 30, withActs.layers);
  assert.deepEqual(ops.filter((o) => o.kind === 'action'), [
    { kind: 'action', scene: 's1', index: 0, body: { patch: { start: 1, end: 2 } } },
    { kind: 'action', scene: 's1', index: 1, body: { delete: true } },
  ]);
});

test('sounds heard in the voice are a locked track that saves nothing (W11.1)', () => {
  const doc = fromProject({ ...view, sounds: [{ label: 'laughter', emoji: '😂', start: 1, end: 1.5 }] });
  const tl = doc.timelines[0];
  assert.equal(tl.tracks.A9.locked, true);
  assert.deepEqual(tl.items.filter((i) => i.id.startsWith('snd:')).map((i) => i.name), ['😂 laughter']);
  const draft = makeDraft(doc);
  draft.commands.selectItem('snd:0');
  assert.deepEqual(planSave(activeEditorState(doc), draft.getState(), 30, view.layers).ops, []);
});
