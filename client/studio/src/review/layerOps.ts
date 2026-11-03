import type { LClip, LDoc, LTrack, MediaItem } from "../types";

/** Pure edits of the layers document. Every function returns a new document (or the same one when nothing can be done). The server checks the result again. */

export const MIN = 0.1;
let counter = 0;
export const uid = (p: string) => `${p}${Date.now().toString(36)}${(counter++).toString(36)}`;

export const trackOf = (d: LDoc, id: string) => d.tracks.find((t) => t.id === id);
export const clipsOn = (d: LDoc, track: string, except?: string) => d.clips.filter((c) => c.track === track && c.id !== except).sort((a, b) => a.start - b.start);
export const endOf = (c: LClip) => c.start + c.dur;

/** The free stretch [lo, hi] around `t` on a track (the neighbours' edges), or null when t is inside a clip. */
export function gapAt(d: LDoc, track: string, t: number, total: number, except?: string): [number, number] | null {
  let lo = 0, hi = total;
  for (const c of clipsOn(d, track, except)) {
    if (t >= c.start && t < endOf(c) - 1e-6) return null;
    if (endOf(c) <= t + 1e-6) lo = Math.max(lo, endOf(c));
    else if (c.start >= t) hi = Math.min(hi, c.start);
  }
  return [lo, hi];
}

export function addTrack(d: LDoc, kind: "visual" | "audio", top = kind === "visual"): { doc: LDoc; track: LTrack } {
  const n = d.tracks.filter((t) => t.kind === kind).length + 1;
  const track: LTrack = { id: uid("t"), name: `${kind === "visual" ? "Layer" : "Sound"} ${n}`, kind, hidden: false, muted: false, locked: false };
  return { doc: { ...d, tracks: top ? [track, ...d.tracks] : [...d.tracks, track] }, track };
}

/** Put a new clip on the first track of its kind that has room at (or after) `start`; make a track when none has room. */
export function place(d: LDoc, clip: Omit<LClip, "track" | "start"> & { start: number }, kind: "visual" | "audio", total: number, prefer?: string): { doc: LDoc; clip: LClip } {
  let doc = d;
  const order = [...(prefer ? d.tracks.filter((t) => t.id === prefer) : []), ...d.tracks.filter((t) => t.kind === kind && t.id !== prefer && !t.locked)].filter((t) => t.kind === kind && !t.locked);
  for (const t of order) {
    // the clip goes where asked when it fits, else in the next free stretch after that
    let at = Math.min(clip.start, Math.max(0, total - MIN));
    for (const c of clipsOn(doc, t.id)) {
      if (at + clip.dur <= c.start + 1e-6) break;
      if (at < endOf(c) - 1e-6) at = endOf(c);
    }
    if (at + MIN <= total) {
      const dur = Math.min(clip.dur, total - at);
      const nxt = clipsOn(doc, t.id).find((c) => c.start >= at - 1e-6);
      const room = nxt ? Math.min(dur, nxt.start - at) : dur;
      if (room >= MIN) {
        const placed = { ...clip, track: t.id, start: round(at), dur: round(room) } as LClip;
        return { doc: { ...doc, clips: [...doc.clips, placed] }, clip: placed };
      }
    }
  }
  const made = addTrack(doc, kind);
  doc = made.doc;
  const placed = { ...clip, track: made.track.id, start: round(Math.min(clip.start, Math.max(0, total - MIN))), dur: round(Math.min(clip.dur, total - Math.min(clip.start, total - MIN))) } as LClip;
  return { doc: { ...doc, clips: [...doc.clips, placed] }, clip: placed };
}

export const round = (v: number) => Math.round(v * 1000) / 1000;

export function newText(start: number, text = "Your text"): Omit<LClip, "track"> {
  return { id: uid("c"), type: "text", start, dur: 3, fade_in: 0.25, fade_out: 0.25, text, x: 0.5, y: 0.72, w: 0.8, h: null, opacity: 1, fit: "cover",
    style: { size: 0.065, color: "#ffffff", bg: "#111111", weight: 800, align: "center" } };
}

export function newFromMedia(m: MediaItem, start: number): { clip: Omit<LClip, "track">; kind: "visual" | "audio" } {
  if (m.kind === "audio") return { kind: "audio", clip: { id: uid("c"), type: "audio", start, dur: Math.max(MIN, Math.min(m.duration || 10, 600)), fade_in: 0, fade_out: 0, media: m.id, in: 0, volume: 1 } };
  const video = m.kind === "video" || m.kind === "gif";
  return { kind: "visual", clip: { id: uid("c"), type: "media", start, dur: video ? Math.max(MIN, Math.min(m.duration || 4, 8)) : 4, fade_in: 0.2, fade_out: 0.2, media: m.id, in: 0, x: 0.5, y: 0.5, w: 1, h: null, opacity: 1, fit: "cover", ...(m.kind === "video" ? { volume: 0 } : {}) } };
}

/** Move a clip to a new start (and maybe another track of the same kind), keeping it out of its neighbours. Returns null when it does not fit there. */
export function move(d: LDoc, id: string, start: number, track: string, total: number): LDoc | null {
  const c = d.clips.find((x) => x.id === id);
  const t = trackOf(d, track);
  const from = c && trackOf(d, c.track);
  if (!c || !t || !from || t.kind !== from.kind || t.locked || from.locked) return null;
  const others = clipsOn(d, track, id);
  let s = Math.max(0, Math.min(start, total - c.dur));
  // slide against the neighbours: stop at the edge of the one in the way
  for (const o of others) {
    if (s < endOf(o) - 1e-6 && s + c.dur > o.start + 1e-6) {
      const before = o.start - c.dur, after = endOf(o);
      s = Math.abs(s - before) < Math.abs(s - after) ? before : after;
    }
  }
  if (s < -1e-6 || s + c.dur > total + 1e-6) return null;
  if (others.some((o) => s < endOf(o) - 1e-6 && s + c.dur > o.start + 1e-6)) return null;
  return { ...d, clips: d.clips.map((x) => (x.id === id ? { ...x, track, start: round(Math.max(0, s)), ...(x.keyframes?{keyframes:x.keyframes.map(p=>({...p,time:round(p.time+s-x.start)}))}:{}) } : x)) };
}

/** Trim one edge. Media and sounds keep their place in the source: trimming the start moves `in` with it. `limit` is the source length (null: unlimited, as for text and pictures). */
export function trim(d: LDoc, id: string, side: "start" | "end", t: number, total: number, limit: number | null): LDoc {
  const c = d.clips.find((x) => x.id === id);
  if (!c || trackOf(d, c.track)?.locked || !Number.isFinite(t)) return d;
  const others = clipsOn(d, c.track, id);
  const prev = others.filter((o) => endOf(o) <= c.start + 1e-6).reduce((m, o) => Math.max(m, endOf(o)), 0);
  const next = others.filter((o) => o.start >= endOf(c) - 1e-6).reduce((m, o) => Math.min(m, o.start), total);
  let start = c.start, dur = c.dur, inn = c.in ?? 0;
  if (side === "start") {
    const lo = Math.max(prev, limit != null ? c.start - inn : 0);                   // cannot start before the first moment of the source
    const ns = Math.max(lo, Math.min(t, endOf(c) - MIN));
    inn = inn + (ns - c.start);
    dur = endOf(c) - ns;
    start = ns;
  } else {
    const hi = Math.min(next, limit != null ? c.start + (limit - inn) : total);
    dur = Math.max(MIN, Math.min(t, hi) - c.start);
  }
  return { ...d, clips: d.clips.map((x) => (x.id === id ? { ...x, start: round(start), dur: round(dur), fade_in: Math.min(c.fade_in, dur / 2), fade_out: Math.min(c.fade_out, dur / 2), ...(c.type !== "text" ? { in: round(Math.max(0, inn)) } : {}) } : x)) };
}

export function split(d: LDoc, id: string, t: number): { doc: LDoc; ids: [string, string] } | null {
  const c = d.clips.find((x) => x.id === id);
  if (!c || trackOf(d, c.track)?.locked || !Number.isFinite(t) || t <= c.start + MIN || t >= endOf(c) - MIN) return null;
  const a: LClip = { ...c, dur: round(t - c.start), fade_in: Math.min(c.fade_in, (t - c.start) / 2), fade_out: 0 };
  const b: LClip = { ...c, id: uid("c"), start: round(t), dur: round(endOf(c) - t), fade_in: 0, fade_out: Math.min(c.fade_out, (endOf(c) - t) / 2), ...(c.type !== "text" ? { in: round((c.in ?? 0) + (t - c.start)) } : {}) };
  return { doc: { ...d, clips: d.clips.flatMap((x) => (x.id === id ? [a, b] : [x])) }, ids: [a.id, b.id] };
}

export function remove(d: LDoc, id: string): LDoc {
  return { ...d, clips: d.clips.filter((c) => c.id !== id || trackOf(d, c.track)?.locked) };
}

export function duplicate(d: LDoc, id: string, total: number): { doc: LDoc; id: string } | null {
  const c = d.clips.find((x) => x.id === id);
  if (!c || trackOf(d, c.track)?.locked) return null;
  const copy = { ...c, id: uid("c"), start: endOf(c) };
  const kind = trackOf(d, c.track)?.kind ?? "visual";
  if (copy.start + MIN > total) return null;
  const r = place(d, { ...copy }, kind, total, c.track);
  if(c.keyframes) r.clip.keyframes=c.keyframes.map(p=>({...p,time:round(p.time+r.clip.start-c.start)}));
  return { doc: r.doc, id: r.clip.id };
}

export function patchClip(d: LDoc, id: string, patch: Partial<LClip>): LDoc {
  return { ...d, clips: d.clips.map((c) => (c.id === id && !trackOf(d, c.track)?.locked ? { ...c, ...patch, ...(patch.style ? { style: { ...c.style!, ...patch.style } } : {}) } : c)) };
}

export function patchTrack(d: LDoc, id: string, patch: Partial<LTrack>): LDoc {
  return { ...d, tracks: d.tracks.map((t) => (t.id === id ? { ...t, ...patch } : t)) };
}

export function removeTrack(d: LDoc, id: string): LDoc {
  if (trackOf(d, id)?.locked) return d;
  return { ...d, tracks: d.tracks.filter((t) => t.id !== id), clips: d.clips.filter((c) => c.track !== id) };
}

export function moveTrack(d: LDoc, id: string, dir: -1 | 1): LDoc {
  const i = d.tracks.findIndex((t) => t.id === id);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= d.tracks.length) return d;
  const tracks = [...d.tracks];
  [tracks[i], tracks[j]] = [tracks[j], tracks[i]];
  return { ...d, tracks };
}
