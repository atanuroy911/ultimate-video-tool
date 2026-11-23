// Video Tool: our project → OpenChatCut's timeline state (docs/plans/PLAN-OPENCHATCUT.MD, "The bridge"). Phase 1 reads only: the ported
// timeline shows our scenes, elements, layers, narration and captions on OpenChatCut's tracks; edits come back in phase 2 (toProject.ts).
//
//   C1            captions, driven by the narration's words
//   layer tracks  our free layers (text, pictures, sounds), top to bottom as in our editor
//   V3…           scene elements (title, value card, icons…), packed into rows so overlapping ones do not share a row
//   V1            scenes, each with its backdrop picture or clip
//   A1            the narration after cuts, with its words in edited time
//
// Item ids name what they stand for in our project ("scene:s3", "el:s3:1", "layer:c7", "voice"), so phase 2 maps an edit straight back.
import type { MediaAsset } from '../src/editor/mediaTypes';
import type { ProjectDoc } from '../src/editor/projectTypes';
import type { TimelineItem } from '../src/editor/clipTypes';
import type { TrackFlags, TrackId } from '../src/editor/trackTypes';
import type { TranscriptWord } from '../src/transcript/types';
import { CURRENT_PROJECT_VERSION } from '../shared/project-version';
import type { LDoc, MediaItem, Plan, SceneTime, Word } from '../../types';

export interface KeepSpan { s: number; e: number; o0: number; o1: number }

export interface ProjectView {
  projectId: string;
  fps: number;
  width: number;
  height: number;
  /** seconds, edited time */
  duration: number;
  plan: Plan;
  timing: SceneTime[];
  /** "<scene id>:<element index>" → seconds, edited time */
  elementTimes?: Record<string, { start: number; end: number }>;
  words: Word[];
  /** source → edited time (audio view `keep`) */
  keep: KeepSpan[];
  audioUrl: string | null;
  layers?: LDoc | null;
  media: Record<string, MediaItem>;
  /** scene id → thumbnail url, for scenes without a picture */
  thumbs?: Record<string, string>;
  /** our element type → its name in the editor */
  elementName?: (type: string) => string;
  /** sounds found in the voice (laughter, applause...): shown on a locked track (W11.1, ported from the classic Sounds lane) */
  sounds?: { label: string; emoji?: string; start: number; end: number }[];
  /** the cuts in the voice, where they were (output time): a locked track; double-click one to bring it back (W11.1, the classic cut marks) */
  cuts?: { index: number; o: number; len: number }[];
}

export const VOICE_ID = 'voice';

const f = (seconds: number, fps: number) => Math.max(0, Math.round(seconds * fps));

/** A source-time moment (our words) in edited time, or null when it was cut. */
export function toEdited(t: number, keep: KeepSpan[]): number | null {
  for (const k of keep) if (t >= k.s && t <= k.e) return k.o0 + (t - k.s);
  return null;
}

/** A word's span in edited time. A word that overlaps a cut pause is clamped to the audio kept around it (it is still heard); only a word
 *  wholly inside a cut is gone. */
export function wordToEdited(start: number, end: number, keep: KeepSpan[]): [number, number] | null {
  const parts = keep.filter((k) => k.e > start && k.s < end);
  if (!parts.length) return null;
  const first = parts[0], last = parts[parts.length - 1];
  const s = first.o0 + (Math.max(start, first.s) - first.s);
  const e = last.o0 + (Math.min(end, last.e) - last.s);
  return e > s ? [s, e] : null;
}

/** Rows for overlapping spans: the first row with room, else a new one (the same packing our old timeline used). */
function pack<T extends { start: number; end: number }>(spans: T[]): Array<T & { row: number }> {
  const ends: number[] = [];
  return [...spans].sort((a, b) => a.start - b.start || a.end - b.end).map((s) => {
    let row = ends.findIndex((e) => e <= s.start);
    if (row < 0) { row = ends.length; ends.push(0); }
    ends[row] = s.end;
    return { ...s, row };
  });
}

function mediaKind(m: MediaItem | undefined): TimelineItem['kind'] {
  if (!m) return 'solid';
  return m.kind === 'gif' ? 'gif' : m.kind === 'audio' ? 'audio' : m.kind === 'video' ? 'video' : 'image';
}

export function fromProject(v: ProjectView): ProjectDoc {
  const { fps } = v;
  const items: TimelineItem[] = [];
  const tracks: Record<TrackId, TrackFlags> = {};
  const order: TrackId[] = [];
  const assets = new Map<string, MediaAsset>();
  const asset = (m: MediaItem): MediaAsset => {
    const a = assets.get(m.id) ?? { id: m.id, name: m.caption || m.file, kind: m.kind === 'gif' ? 'gif' : m.kind, src: m.url,
      durationInFrames: Math.max(1, f(m.duration || 5, fps)), width: m.width, height: m.height };
    assets.set(m.id, a);
    return a;
  };

  // captions, on top
  order.push('C1');
  // captions are edited in our Captions panel for now: locked here so a drag cannot look saved when it is not
  tracks.C1 = { kind: 'caption', name: 'Captions', locked: true, captions: { enabled: true, template: 'black-bar', pacing: 'phrase', sourceItemId: VOICE_ID, sourceMode: 'item' } };

  // our free layers, top to bottom
  const layerTracks = v.layers?.tracks ?? [];
  for (const lt of layerTracks) {
    const id = `L_${lt.id}`;
    tracks[id] = { kind: lt.kind === 'audio' ? 'audio' : 'video', name: lt.name, hidden: lt.hidden, muted: lt.muted, locked: lt.locked };
    if (lt.kind !== 'audio') order.push(id);
  }
  for (const c of v.layers?.clips ?? []) {
    const m = c.media ? v.media[c.media] : undefined;
    if (m) asset(m);
    items.push({
      id: `layer:${c.id}`, track: `L_${c.track}`, startFrame: f(c.start, fps), durationInFrames: Math.max(1, f(c.dur, fps)),
      name: c.type === 'text' ? (c.text || 'Text') : m?.caption || m?.file || 'Sound',
      kind: c.type === 'text' ? 'text' : c.type === 'audio' ? 'audio' : mediaKind(m),
      src: m?.url, sourceAssetId: m?.id, volume: c.volume, srcInFrame: c.in ? f(c.in, fps) : undefined,
      fadeInFrames: c.fade_in ? f(c.fade_in, fps) : undefined, fadeOutFrames: c.fade_out ? f(c.fade_out, fps) : undefined,
      props: c.type === 'text' ? { text: c.text ?? '' } : undefined,
      transform: c.type === 'audio' ? undefined : { x: c.x, y: c.y, scale: c.scale, rotation: c.rotation, opacity: c.opacity },
    });
  }

  // scene elements, packed into rows (V3 is the row nearest the scenes)
  const timeOf = new Map(v.timing.map((t) => [t.id, t]));
  const els = v.plan.scenes.flatMap((s) => s.elements.map((el, k) => {
    const t = v.elementTimes?.[`${s.id}:${k}`] ?? timeOf.get(s.id) ?? { start: 0, end: 0 };
    return { id: `el:${s.id}:${k}`, type: el.type, start: t.start, end: Math.max(t.end, t.start + 1 / fps) };
  })).filter((e) => e.end > e.start);
  const rows = pack(els);
  const rowCount = rows.reduce((n, r) => Math.max(n, r.row + 1), 0);
  for (let r = rowCount - 1; r >= 0; r--) {
    const id = `V${r + 3}`;
    tracks[id] = { kind: 'video', name: r === 0 ? 'Elements' : `Elements ${r + 1}` };
    order.push(id);
  }
  for (const e of rows) {
    items.push({ id: e.id, track: `V${e.row + 3}`, startFrame: f(e.start, fps), durationInFrames: Math.max(1, f(e.end - e.start, fps)),
      name: v.elementName ? v.elementName(e.type) : e.type, kind: 'text', props: { text: v.elementName ? v.elementName(e.type) : e.type } });
  }

  // stick-figure actions (W11.1, ported from the classic timeline): one row above the elements, moved and trimmed like any clip
  const acts = v.plan.scenes.flatMap((s) => (s.stick?.actions ?? []).map((a, k) => ({ id: `act:${s.id}:${k}`, label: `${a.who} ${a.do}`, start: a.start, end: Math.max(a.end, a.start + 1 / fps) })));
  if (acts.length) {
    tracks.V9 = { kind: 'video', name: 'Actions' };
    order.unshift('V9');
    for (const a of acts) items.push({ id: a.id, track: 'V9', startFrame: f(a.start, fps), durationInFrames: Math.max(1, f(a.end - a.start, fps)), name: a.label, kind: 'text', props: { text: a.label } });
  }

  // sounds heard in the voice: a locked track, for seeing where they are (they are found by the server, not edited here)
  const snds = (v.sounds ?? []).filter((e) => e.end > e.start);
  if (snds.length) {
    tracks.A9 = { kind: 'audio', name: 'Sounds', locked: true };
    snds.forEach((e, i) => items.push({ id: `snd:${i}`, track: 'A9', startFrame: f(e.start, fps), durationInFrames: Math.max(1, f(e.end - e.start, fps)),
      name: `${e.emoji ?? ''} ${e.label}`.trim(), kind: 'text', props: { text: e.label } }));
  }

  // scenes with their backdrop
  order.push('V1');
  tracks.V1 = { kind: 'video', name: 'Scenes' };
  v.plan.scenes.forEach((s, i) => {
    const t = timeOf.get(s.id);
    if (!t || t.end <= t.start) return;
    const m = s.backdrop?.media ? v.media[s.backdrop.media] : undefined;
    if (m) asset(m);
    items.push({
      id: `scene:${s.id}`, track: 'V1', startFrame: f(t.start, fps), durationInFrames: Math.max(1, f(t.end - t.start, fps)),
      name: `Scene ${i + 1}`, kind: m ? mediaKind(m) : v.thumbs?.[s.id] ? 'image' : 'solid',
      src: m?.url ?? v.thumbs?.[s.id], sourceAssetId: m?.id,
    });
  });

  // the narration, after cuts, with its words in edited time (captions and the transcript view read them)
  order.push('A1');
  if (tracks.A9) order.push('A9');
  const cutMarks = (v.cuts ?? []).filter((c) => c.len > 0);
  if (cutMarks.length) {
    tracks.A8 = { kind: 'audio', name: 'Cuts', locked: true };
    order.push('A8');
    for (const c of cutMarks) items.push({ id: `cut:${c.index}`, track: 'A8', startFrame: f(c.o, fps), durationInFrames: Math.max(6, f(0.25, fps)),
      name: `✂ ${c.len.toFixed(1)} s`, kind: 'text', props: { text: `cut ${c.len.toFixed(1)} s` } });
  }
  tracks.A1 = { kind: 'audio', name: 'Narration', role: 'anchor' };
  if (v.audioUrl) {
    const transcript: TranscriptWord[] = [];
    for (const w of v.words) {
      if (w.cut) continue;
      const span = wordToEdited(w.start, w.end, v.keep);
      if (!span) continue;
      const prev = transcript[transcript.length - 1];
      if (prev && /^[-\u2010-\u2014]/.test(w.text)) {                 // "five" + "-minute": one word on screen, as our captions show it
        prev.text += w.text;
        prev.end = Math.round(span[1] * 1000);
        continue;
      }
      transcript.push({ id: w.id, text: w.text, start: Math.round(span[0] * 1000), end: Math.round(span[1] * 1000) });
    }
    items.push({ id: VOICE_ID, track: 'A1', startFrame: 0, durationInFrames: Math.max(1, f(v.duration, fps)), name: 'Narration',
      kind: 'audio', src: v.audioUrl, transcript, transcriptGenerationId: `vt-${v.projectId}-${v.words.length}` });
  }

  for (const lt of layerTracks) if (lt.kind === 'audio') order.push(`L_${lt.id}`);

  const timeline = {
    id: 'main', name: 'Main', order: 0, fps, width: v.width, height: v.height,
    items, trackOrder: order, tracks, selectedId: null,
  };
  return { version: CURRENT_PROJECT_VERSION, assets: [...assets.values()], mediaFolders: [], timelines: [timeline], activeTimelineId: 'main' };
}
