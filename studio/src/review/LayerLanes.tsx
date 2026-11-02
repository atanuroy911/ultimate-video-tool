import { AudioLines, EyeOff, Film, Image as ImageIcon, Lock, MoreHorizontal, Type, VolumeX } from "lucide-react";
import { useRef, useState } from "react";
import type { LClip, MediaItem } from "../types";
import * as Ops from "./layerOps";
import type { Layers } from "./useLayers";

interface MenuItem { label: string; run: () => void; danger?: boolean }
interface Props {
  layers: Layers;
  kind: "visual" | "audio";
  label: number;                                           // width of the track name column
  x: (t: number) => number;
  tAt: (clientX: number) => number;
  pps: number;
  v0: number;
  v1: number;
  total: number;
  drag: (e: React.PointerEvent | PointerEvent, move: (ev: PointerEvent) => void, up: (ev: PointerEvent, moved: boolean) => void, cancel?: () => void) => void;
  snapT: (t: number, alt?: boolean, withWords?: boolean) => { t: number; hit: number | null };
  setGuide: (t: number | null) => void;
  media: Map<string, MediaItem>;
  selected: string | null;
  onSelect: (id: string | null) => void;
  scrub: (e: React.PointerEvent) => void;
  menu: (x: number, y: number, items: MenuItem[]) => void;
  seek: (t: number) => void;
  peaks?: Map<string, number[]>;
  tool?: "select" | "blade";
}

const ICON = { text: Type, image: ImageIcon, video: Film, audio: AudioLines } as const;

/** The lanes of one kind of layer track (pictures, text and video above the scenes; sounds below the voice). Clips are moved and trimmed by dragging; nothing may overlap. */
export default function LayerLanes(p: Props) {
  const { layers, kind } = p;
  const doc = layers.doc;
  const tracks = doc.tracks.filter((t) => t.kind === kind);
  const [target, setTarget] = useState<string | null>(null);        // the lane a dragged clip would land in
  const laneRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const laneAt = (cx: number, cy: number, fallback: string) => {
    for (const t of tracks) {
      const r = laneRefs.current[t.id]?.getBoundingClientRect();
      if (r && cy >= r.top && cy <= r.bottom) return t.id;
    }
    return fallback;
  };
  const limitOf = (c: LClip) => {
    const m = c.media ? p.media.get(c.media) : null;
    return m && (m.kind === "video" || m.kind === "audio") ? m.duration || null : null;
  };

  const startMove = (e: React.PointerEvent, c: LClip) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    p.onSelect(c.id);
    const t = Ops.trackOf(doc, c.track);
    if (t?.locked) return;
    if (p.tool === "blade") {
      const at = p.tAt(e.clientX);
      const result = Ops.split(doc, c.id, at);
      if (result) { layers.commit(result.doc); p.onSelect(result.ids[1]); p.seek(at); }
      return;
    }
    const orig = doc;
    const grab = p.tAt(e.clientX) - c.start;
    layers.hold(true);                                                                       // a refetch must not overwrite the clip while it is dragged
    const go = (ev: PointerEvent) => {
      const lane = laneAt(ev.clientX, ev.clientY, c.track);
      const s = p.snapT(p.tAt(ev.clientX) - grab, ev.altKey, false);
      const s2 = p.snapT(p.tAt(ev.clientX) - grab + c.dur, ev.altKey, false);                  // the clip's end snaps too
      const start = s.hit != null ? s.t : s2.hit != null ? s2.t - c.dur : s.t;
      p.setGuide(s.hit ?? s2.hit);
      setTarget(lane);
      const next = Ops.move(orig, c.id, start, lane, p.total);
      if (next) layers.setLocal(next);
    };
    const done = (commit: boolean) => {
      setTarget(null);
      layers.hold(false);
      if (commit) layers.commit(); else layers.setLocal(orig);
    };
    p.drag(e, go, (_ev, moved) => done(moved), () => done(false));
  };

  const startTrim = (e: React.PointerEvent, c: LClip, side: "start" | "end") => {
    if (e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    p.onSelect(c.id);
    if (Ops.trackOf(doc, c.track)?.locked) return;
    const orig = doc;
    const lim = limitOf(c);
    const grabOffset = p.tAt(e.clientX) - (side === "start" ? c.start : c.start + c.dur);
    layers.hold(true);
    const go = (ev: PointerEvent) => {
      const s = p.snapT(p.tAt(ev.clientX) - grabOffset, ev.altKey, false);
      p.setGuide(s.hit);
      layers.setLocal(Ops.trim(orig, c.id, side, s.t, p.total, lim));
    };
    p.drag(e, go, (_ev, moved) => { layers.hold(false); if (moved) layers.commit(); else layers.setLocal(orig); }, () => { layers.hold(false); layers.setLocal(orig); });
  };

  const trackMenu = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    const t = Ops.trackOf(doc, id)!;
    const set = (patch: Partial<typeof t>) => layers.commit(Ops.patchTrack(doc, id, patch));
    const items: MenuItem[] = [
      { label: "Rename…", run: () => { const n = window.prompt("Track name", t.name); if (n && n.trim()) set({ name: n.trim().slice(0, 40) }); } },
      { label: t.hidden ? "Show" : "Hide", run: () => set({ hidden: !t.hidden }) },
      { label: t.muted ? "Unmute" : "Mute", run: () => set({ muted: !t.muted }) },
      { label: t.locked ? "Unlock" : "Lock", run: () => set({ locked: !t.locked }) },
      { label: "Move up", run: () => layers.commit(Ops.moveTrack(doc, id, -1)) },
      { label: "Move down", run: () => layers.commit(Ops.moveTrack(doc, id, 1)) },
      ...(!t.locked ? [{ label: "Delete the track and its clips", danger: true, run: () => layers.commit(Ops.removeTrack(doc, id)) }] : []),
    ];
    p.menu(e.clientX, e.clientY, items);
  };

  const clipMenu = (e: React.MouseEvent, c: LClip) => {
    e.preventDefault();
    e.stopPropagation();
    p.onSelect(c.id);
    if (Ops.trackOf(doc, c.track)?.locked) {
      p.menu(e.clientX, e.clientY, [{ label: "Unlock track to edit", run: () => layers.commit(Ops.patchTrack(doc, c.track, { locked: false })) }]);
      return;
    }
    const t = p.tAt(e.clientX);
    p.menu(e.clientX, e.clientY, [
      { label: "Split here", run: () => { const r = Ops.split(layers.doc, c.id, t); if (r) layers.commit(r.doc); } },
      { label: "Duplicate", run: () => { const r = Ops.duplicate(layers.doc, c.id, p.total); if (r) { layers.commit(r.doc); p.onSelect(r.id); } } },
      { label: "Delete", danger: true, run: () => { layers.commit(Ops.remove(layers.doc, c.id)); p.onSelect(null); } },
    ]);
  };

  const describe = (c: LClip): { text: string; icon: keyof typeof ICON } => {
    if (c.type === "text") return { text: c.text ?? "", icon: "text" };
    const m = c.media ? p.media.get(c.media) : undefined;
    return { text: m?.caption || m?.id || c.media || "", icon: c.type === "audio" ? "audio" : m?.kind === "video" || m?.kind === "gif" ? "video" : "image" };
  };

  return (
    <>
      {tracks.map((t) => (
        <div key={t.id} ref={(el) => { laneRefs.current[t.id] = el; }} className={`tl-lane layer ${kind} ${target === t.id ? "target" : ""} ${t.hidden ? "off" : ""}`} role="group" aria-label={`Track ${t.name}`}
          data-track={t.id} onPointerDown={(e) => e.target === e.currentTarget && p.scrub(e)}>
          <div className="tl-label tl-tlabel" style={{ width: p.label }}>
            <button className="tl-tname" onClick={(e) => trackMenu(e, t.id)} onContextMenu={(e) => trackMenu(e, t.id)} title={`${t.name}: click for options`} aria-label={`Options for ${t.name}`}>
              <span>{t.name}</span><MoreHorizontal size={12} />
            </button>
            <span className="tl-tstate" aria-hidden>
              {t.locked ? <Lock size={11} /> : null}{t.hidden ? <EyeOff size={11} /> : null}{t.muted ? <VolumeX size={11} /> : null}
            </span>
          </div>
          {doc.clips.filter((c) => c.track === t.id && c.start + c.dur >= p.v0 && c.start <= p.v1).map((c) => {
            const d = describe(c);
            const Icon = ICON[d.icon];
            const w = Math.max(6, c.dur * p.pps - 1);
            return (
              <div key={c.id} role="button" tabIndex={0} aria-label={`${c.type} clip ${d.text}`} aria-pressed={p.selected === c.id}
                className={`tl-lclip ${c.type} ${d.icon} ${p.selected === c.id ? "sel" : ""} ${t.locked ? "locked" : ""} ${t.muted ? "muted" : ""}`}
                style={{ left: p.x(c.start), width: w }} data-clip={c.id}
                onPointerDown={(e) => startMove(e, c)} onContextMenu={(e) => clipMenu(e, c)}
                onKeyDown={(e) => { if (e.key === "Enter") p.onSelect(c.id); }}
                title={`${d.text || c.type} · ${c.dur.toFixed(2)} s`}>
                <Icon size={12} aria-hidden /><span className="tl-lc-text">{w > 50 ? d.text : ""}</span>
                {c.type === "audio" && (c.volume ?? 1) !== 1 && w > 70 && <span className="tl-lc-db">{(c.volume ?? 1) === 0 ? "muted" : `${Math.round((c.volume ?? 1) * 100)}%`}</span>}
                {c.fade_in > 0.02 && <i className="tl-fade in" style={{ width: Math.min(w / 2, c.fade_in * p.pps) }} aria-hidden />}
                {c.fade_out > 0.02 && <i className="tl-fade out" style={{ width: Math.min(w / 2, c.fade_out * p.pps) }} aria-hidden />}
                <div role="button" className="tl-ledge l" onPointerDown={(e) => startTrim(e, c, "start")} aria-label={`Trim the start of ${d.text || c.type}`} title="Drag to trim" />
                <div role="button" className="tl-ledge r" onPointerDown={(e) => startTrim(e, c, "end")} aria-label={`Trim the end of ${d.text || c.type}`} title="Drag to trim" />
              </div>
            );
          })}
        </div>
      ))}
    </>
  );
}

