// Video Tool: edits made on the ported OpenChatCut timeline → our project's own edits (phase 2 of docs/plans/PLAN-OPENCHATCUT.MD).
// The timeline state before and after an edit are compared item by item (ids from fromProject.ts say what each item is in our project) and
// turned into the same calls our classic timeline makes, so our rules keep applying (scene edges snap to words; the server keeps undo).
//
//   layer:<clip>   → the layers document (moves, trims, splits, duplicates, deletes, fades, volume, place, track hide/mute/lock)
//   el:<scene>:<k> → element timing, split, delete
//   scene:<scene>  → scene edge moves, split, delete
//   voice          → a stretch removed from the narration becomes a cut
// Moving the narration in time is not saved from here and is reported in `ignored`; the captions track is locked (edited in the Captions panel).
import type { TimelineItem } from '../src/editor/clipTypes';
import type { TimelineState } from '../src/editor/types';
import type { LClip, LDoc } from '../../types';
import { VOICE_ID } from './fromProject';
import { hasOperationalTranscript } from '../src/transcript/types';

export type SaveOp =
  | { kind: 'layers'; doc: LDoc }
  | { kind: 'element'; scene: string; index: number; body: { start: number; end: number } | { split: number } | { delete: true } }
  | { kind: 'scene-edge'; scene: string; t: number }
  | { kind: 'scene-split'; scene: string; t: number }
  | { kind: 'scene-remove'; scene: string }
  | { kind: 'voice-cut'; start: number; end: number }
  | { kind: 'action'; scene: string; index: number; body: { patch: { start: number; end: number } } | { delete: true } }
  | { kind: 'voice-gain'; start: number; end: number; db: number }
  | { kind: 'voice-mute'; start: number; end: number };

export interface SavePlan { ops: SaveOp[]; ignored: string[] }

const sec = (frames: number, fps: number) => Math.round((frames / fps) * 1000) / 1000;
const byTrack = (s: TimelineState, pred: (id: string) => boolean) => s.items.filter((i) => pred(i.track));
const ours = (prefix: string) => (i: TimelineItem) => i.id.startsWith(prefix);
let made = 0;
const uid = () => `c${Date.now().toString(36)}${(made++).toString(36)}`;

/** The layers document the timeline now shows, built on the one it started from (fields the timeline does not know are kept). */
function layersFrom(before: LDoc, after: TimelineState, fps: number): LDoc {
  const old = new Map(before.clips.map((c) => [c.id, c]));
  const clips: LClip[] = [];
  for (const it of byTrack(after, (t) => t.startsWith('L_'))) {
    const track = it.track.slice(2);
    const prev = it.id.startsWith('layer:') ? old.get(it.id.slice(6)) : undefined;
    const type: LClip['type'] = prev?.type ?? (it.kind === 'text' ? 'text' : it.kind === 'audio' ? 'audio' : 'media');
    const base: LClip = prev ? { ...prev } : { id: uid(), track, type, start: 0, dur: 1, fade_in: 0, fade_out: 0, media: it.sourceAssetId, text: (it.props?.text as string) ?? undefined };
    const tr = it.transform ?? {};
    clips.push({
      ...base,
      id: prev ? prev.id : base.id,
      track,
      start: sec(it.startFrame, fps),
      dur: sec(it.durationInFrames, fps),
      in: it.srcInFrame ? sec(it.srcInFrame, fps) : prev?.in,
      fade_in: it.fadeInFrames != null ? sec(it.fadeInFrames, fps) : base.fade_in,
      fade_out: it.fadeOutFrames != null ? sec(it.fadeOutFrames, fps) : base.fade_out,
      volume: it.volume ?? base.volume,
      ...(type === 'text' ? { text: (it.props?.text as string) ?? base.text } : {}),
      ...(type !== 'audio' ? { x: tr.x ?? base.x, y: tr.y ?? base.y, scale: tr.scale ?? base.scale, rotation: tr.rotation ?? base.rotation, opacity: tr.opacity ?? base.opacity } : {}),
    });
  }
  const tracks = before.tracks.map((t) => {
    const f = after.tracks?.[`L_${t.id}`];
    return f ? { ...t, hidden: !!f.hidden, muted: !!f.muted, locked: !!f.locked } : t;
  });
  return { ...before, tracks, clips };
}

/** Sorted, joined [from, to) stretches (touching or overlapping ones become one). */
function merge(spans: Array<[number, number]>): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  for (const [a, b] of [...spans].sort((x, y) => x[0] - y[0])) {
    const last = out[out.length - 1];
    if (last && a <= last[1] + 0.001) last[1] = Math.max(last[1], b);
    else out.push([a, b]);
  }
  return out;
}

/** What is in `from` but not in `minus` (both merged), ignoring slivers under 20 ms (frame rounding). */
function subtract(from: Array<[number, number]>, minus: Array<[number, number]>): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  for (const [a, b] of from) {
    let at = a;
    for (const [c, d] of minus) {
      if (d <= at || c >= b) continue;
      if (c > at) out.push([at, Math.min(c, b)]);
      at = Math.max(at, d);
      if (at >= b) break;
    }
    if (at < b) out.push([at, b]);
  }
  return out.filter(([x, y]) => y - x >= 0.02).map(([x, y]) => [Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000]);
}

export function planSave(before: TimelineState, after: TimelineState, fps: number, layersBefore: LDoc | null): SavePlan {
  const ops: SaveOp[] = [];
  const ignored: string[] = [];
  const was = new Map(before.items.map((i) => [i.id, i]));
  const now = new Map(after.items.map((i) => [i.id, i]));
  const end = (i: TimelineItem) => i.startFrame + i.durationInFrames;

  // layers: one document, written when anything about them changed
  if (layersBefore) {
    const next = layersFrom(layersBefore, after, fps);
    const prev = layersFrom(layersBefore, before, fps);
    if (JSON.stringify(next) !== JSON.stringify(prev)) ops.push({ kind: 'layers', doc: next });
  }

  // scene elements: timing first, then splits and deletes from the last index back (each shifts the indexes after it)
  const elIds = before.items.filter(ours('el:')).map((i) => i.id);
  const splits: SaveOp[] = [], deletes: SaveOp[] = [];
  for (const id of elIds) {
    const [, scene, k] = id.split(':');
    const a = was.get(id)!, b = now.get(id);
    const index = Number(k);
    if (!b) { deletes.push({ kind: 'element', scene, index, body: { delete: true } }); continue; }
    const piece = after.items.find((x) => !was.has(x.id) && x.track === b.track && x.startFrame === end(b) && end(x) <= end(a) + 1);
    if (piece) { splits.push({ kind: 'element', scene, index, body: { split: sec(end(b), fps) } }); continue; }
    if (b.startFrame !== a.startFrame || b.durationInFrames !== a.durationInFrames) {
      ops.push({ kind: 'element', scene, index, body: { start: sec(b.startFrame, fps), end: sec(end(b), fps) } });
    }
  }
  const lastFirst = (x: SaveOp, y: SaveOp) => (x.kind === 'element' && y.kind === 'element' ? (x.scene === y.scene ? y.index - x.index : 0) : 0);
  ops.push(...splits.sort(lastFirst), ...deletes.sort(lastFirst));

  // scenes: edges (an edge belongs to the scene on its left), then splits, then removals
  const scenes = before.items.filter(ours('scene:')).sort((x, y) => x.startFrame - y.startFrame);
  const sceneOps: SaveOp[] = [];
  scenes.forEach((a, i) => {
    const scene = a.id.slice(6), b = now.get(a.id);
    if (!b) { sceneOps.push({ kind: 'scene-remove', scene }); return; }
    const piece = after.items.find((x) => !was.has(x.id) && x.track === 'V1' && x.startFrame === end(b));
    if (piece) { sceneOps.push({ kind: 'scene-split', scene, t: sec(end(b), fps) }); return; }
    if (end(b) !== end(a) && i < scenes.length - 1) ops.push({ kind: 'scene-edge', scene, t: sec(end(b), fps) });
    if (b.startFrame !== a.startFrame && i > 0 && now.has(scenes[i - 1].id) && end(now.get(scenes[i - 1].id)!) === end(scenes[i - 1])) {
      ops.push({ kind: 'scene-edge', scene: scenes[i - 1].id.slice(6), t: sec(b.startFrame, fps) });
    }
  });
  ops.push(...sceneOps);

  // stick-figure actions: timing, then deletes from the last index back (W11.1)
  const actDeletes: SaveOp[] = [];
  for (const id of before.items.filter(ours('act:')).map((i) => i.id)) {
    const [, scene, k] = id.split(':');
    const index = Number(k), a = was.get(id)!, b = now.get(id);
    if (!b) { actDeletes.push({ kind: 'action', scene, index, body: { delete: true } }); continue; }
    if (b.startFrame !== a.startFrame || b.durationInFrames !== a.durationInFrames)
      ops.push({ kind: 'action', scene, index, body: { patch: { start: sec(b.startFrame, fps), end: sec(end(b), fps) } } });
  }
  ops.push(...actDeletes.sort((x, y) => (x.kind === 'action' && y.kind === 'action' && x.scene === y.scene ? y.index - x.index : 0)));

  // the narration. With words, OpenChatCut edits it as a word stream: a split gives each piece its own words, deleting words in its
  // transcript view marks them deleted. So a cut is the run of our words no longer played by any piece, from its first word to the next
  // word still played (the pause after a removed phrase goes with it). Without words, what a piece plays is [srcIn, srcIn + duration).
  const voice = was.get(VOICE_ID);
  if (voice) {
    const pieces = after.items.filter((x) => x.track === voice.track && x.kind === 'audio');
    const total = sec(voice.durationInFrames, fps);
    if (hasOperationalTranscript(voice)) {
      const played = new Set<string>();
      for (const x of pieces) {
        const deleted = new Set(x.deletedWordIdx ?? []);
        (x.transcript ?? []).forEach((w, gi) => { if (!deleted.has(gi) && w.id) played.add(w.id); });
      }
      const words = voice.transcript;
      const runs: Array<[number, number]> = [];
      for (let i = 0; i < words.length; i++) {
        if (played.has(words[i].id ?? '')) continue;
        let j = i;
        while (j + 1 < words.length && !played.has(words[j + 1].id ?? '')) j++;
        const next = words[j + 1];
        runs.push([words[i].start / 1000, next ? next.start / 1000 : total]);
        i = j;
      }
      for (const [start, stop] of runs.reverse()) ops.push({ kind: 'voice-cut', start: Math.round(start * 1000) / 1000, end: Math.round(stop * 1000) / 1000 });
    } else {
      const plays = (s: TimelineState) => merge(s.items.filter((x) => x.track === voice.track && x.kind === 'audio')
        .map((x): [number, number] => [sec(x.srcInFrame ?? 0, fps), sec((x.srcInFrame ?? 0) + x.durationInFrames, fps)]));
      for (const [start, stop] of subtract(plays(before), plays(after)).reverse()) ops.push({ kind: 'voice-cut', start, end: stop });
    }
    // a narration piece whose volume changed: the same stretch of our voice gets that gain (0 = muted). The narration is the cut voice, so the
    // piece's source range is output time. (W11.1: ported from the classic timeline's Mute and Volume of the selection.)
    const beforeVol = new Map(before.items.filter((x) => x.track === voice.track && x.kind === 'audio').map((x) => [x.id, x.volume ?? 1]));
    for (const x of pieces) {
      const vol = x.volume ?? 1;
      if (Math.abs(vol - (beforeVol.get(x.id) ?? 1)) < 1e-3) continue;
      let start = sec(x.srcInFrame ?? 0, fps), stop = sec((x.srcInFrame ?? 0) + x.durationInFrames, fps);
      if (hasOperationalTranscript(voice) && x.transcript?.length) {                 // a word stream: the piece plays its own words, not a source range
        const deleted = new Set(x.deletedWordIdx ?? []);
        const heard = x.transcript.filter((_, gi) => !deleted.has(gi));
        if (!heard.length) continue;
        start = Math.min(...heard.map((w) => w.start)) / 1000;
        stop = Math.max(...heard.map((w) => w.end)) / 1000;
      }
      start = Math.round(start * 1000) / 1000; stop = Math.round(stop * 1000) / 1000;
      if (vol <= 0.001) ops.push({ kind: 'voice-mute', start, end: stop });
      else ops.push({ kind: 'voice-gain', start, end: stop, db: Math.round(20 * Math.log10(vol) * 10) / 10 });
    }
    const v = now.get(VOICE_ID);
    if (v && v.startFrame !== voice.startFrame && (v.srcInFrame ?? 0) === (voice.srcInFrame ?? 0)) ignored.push('moving the narration in time');
  }

  // captions are not compared: the track is locked here (fromProject.ts), and OpenChatCut re-points the captions' source by itself when the
  // narration is split, which is not an edit of the captions
  return { ops, ignored };
}
