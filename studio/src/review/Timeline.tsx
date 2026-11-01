import { Magnet, Minus, Plus, Scissors, MousePointer2, Maximize2, VolumeX, Volume2, Trash2, Type, Layers as LayersIcon } from "lucide-react";
import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { fmtTime } from "../api";
import type { MediaItem, SoundEvents } from "../types";
import { Menu } from "../ui";
import LayerLanes from "./LayerLanes";
import * as Ops from "./layerOps";
import type { Layers } from "./useLayers";
import { timeStore } from "./timeStore";
import type { Review } from "./useReview";

export type Tool = "select" | "blade";
export interface Sel { o0: number; o1: number }

const LABEL = 92;
const MAX_PPS = 800;
const STEPS = [0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600];

const ROW = 22;
/** Puts items that would overlap on different rows (greedy, left to right): every item gets the first row whose last item ended before it starts. */
function pack(items: { left: number; w: number }[]): { rows: number[]; count: number } {
  const order = items.map((_, i) => i).sort((a, b) => items[a].left - items[b].left);
  const ends: number[] = [];
  const rows = new Array<number>(items.length).fill(0);
  for (const i of order) {
    let r = ends.findIndex((e) => e + 3 <= items[i].left);
    if (r < 0) { r = ends.length; ends.push(0); }
    ends[r] = items[i].left + items[i].w;
    rows[i] = r;
  }
  return { rows, count: Math.max(1, ends.length) };
}
const chipW = (text: string) => Math.min(160, 14 + text.length * 6.4);

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const stamp = (t: number, step: number) => {
  const m = Math.floor(t / 60), s = t - m * 60;
  return step < 1 ? `${m}:${s.toFixed(step < 0.1 ? 2 : 1).padStart(step < 0.1 ? 5 : 4, "0")}` : `${m}:${String(Math.floor(s)).padStart(2, "0")}`;
};

interface Props {
  r: Review;
  duration: number;
  seek: (t: number) => void;
  selected: string | null;
  onSelect: (sceneId: string) => void;
  selectedEl: { scene: string; index: number } | null;
  onSelectEl: (scene: string, index: number) => void;
  tool: Tool;
  setTool: (t: Tool) => void;
  snap: boolean;
  setSnap: (b: boolean) => void;
  sel: Sel | null;
  setSel: (s: Sel | null) => void;
  layers: Layers;
  media: Map<string, MediaItem>;
  selLayer: string | null;
  onSelectLayer: (id: string | null) => void;
  onAddMedia: () => void;
  sounds?: SoundEvents | null;
  onListen?: () => void;
  listening?: boolean;
}

interface Clip { key: string; o0: number; o1: number; s: number; e: number; muted: boolean; db: number | null }

/** Moves with the audio clock without re-rendering anything. */
const Playhead = memo(function Playhead({ pps, scroller }: { pps: number; scroller: React.RefObject<HTMLDivElement | null> }) {
  const el = useRef<HTMLDivElement>(null);
  const ppsRef = useRef(pps);
  ppsRef.current = pps;
  const place = useCallback((t: number, follow = true) => {
    const h = el.current, sc = scroller.current;
    if (!h) return;
    const x = LABEL + t * ppsRef.current;
    h.style.transform = `translate3d(${x}px,0,0)`;
    if (sc && follow && !document.body.classList.contains("tl-scrubbing")) {                  // keep the playhead in view while it moves
      const a = sc.scrollLeft + LABEL + 16, b = sc.scrollLeft + sc.clientWidth - 40;
      if (x < a || x > b) sc.scrollLeft = Math.max(0, timeStore.playing ? x - sc.clientWidth * 0.3 : x - sc.clientWidth * 0.5);
    }
  }, [scroller]);
  useEffect(() => { place(timeStore.t, false); return timeStore.subscribe((t) => place(t, true)); }, [place, pps]);
  return <div className="tl-head" ref={el} aria-hidden />;
});

export default function Timeline({ r, duration, seek, selected, onSelect, selectedEl, onSelectEl, tool, setTool, snap, setSnap, sel, setSel, layers, media, selLayer, onSelectLayer, onAddMedia, sounds, onListen, listening }: Props) {
  const scroller = useRef<HTMLDivElement>(null);
  const hover = useRef<HTMLDivElement>(null);
  const [vw, setVw] = useState(900);
  const dur = Math.max(duration, 0.5);
  const fit = Math.max(4, (vw - LABEL - 24) / dur);
  const [pps, setPps] = useState(fit);
  const ppsRef = useRef(fit);
  const targetRef = useRef(fit);
  const anchorRef = useRef<{ t: number; px: number } | null>(null);
  const raf = useRef(0);
  const fitMode = useRef(true);
  const [scrollX, setScrollX] = useState(0);
  const [menu, setMenu] = useState<{ x: number; y: number; items: { label: string; run: () => void; danger?: boolean }[] } | null>(null);
  const [edge, setEdge] = useState<{ i: number; snap: number | null; land?: number | null } | null>(null);   // snap: where the edge is drawn, land: the sentence start it will settle on
  const [trim, setTrim] = useState<{ key: string; o0: number; o1: number } | null>(null);                  // a voice clip's edge while it is dragged
  const [hint, setHint] = useState<{ t: number; text: string } | null>(null);
  const [ghost, setGhost] = useState<{ o0: number; o1: number; kind: "cut" | "restore"; pending?: boolean } | null>(null);
  const [guide, setGuide] = useState<number | null>(null);
  const [actDrag, setActDrag] = useState<{ sid: string; k: number; t: number } | null>(null);
  const [gainLive, setGainLive] = useState<number | null>(null);

  const audio = r.audio;
  const scenes = r.plan?.scenes ?? [];
  const timing = useMemo(() => new Map(r.timing.scenes.map((s) => [s.id, s])), [r.timing.scenes]);
  const thumbs = r.th.data?.scenes ?? {};
  const beatById = useMemo(() => new Map(r.beats.map((b) => [b.id, b])), [r.beats]);

  /* ---------- smooth zoom: the target moves at once, the real zoom glides to it while the time under the pointer stays put ---------- */
  const glide = useCallback(() => {
    cancelAnimationFrame(raf.current);
    const step = () => {
      const cur = ppsRef.current, tgt = targetRef.current;
      let next = cur + (tgt - cur) * 0.55;                   // each step re-renders the whole timeline: about 5 steps to the target, not 15 (e2e/perf_timeline.mjs)
      if (Math.abs(tgt - next) < tgt * 0.01) next = tgt;
      ppsRef.current = next;
      setPps(next);
      if (next !== tgt) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
  }, [fit]);
  const zoomTo = useCallback((v: number, anchor?: { t: number; px: number } | null) => {
    targetRef.current = clamp(v, fit * 0.999, MAX_PPS);
    fitMode.current = targetRef.current <= fit * 1.001;
    anchorRef.current = anchor ?? null;
    glide();
  }, [fit, glide]);
  // keep the moment under the pointer where it was: after React has widened the content (so the scroll position is not clamped)
  useLayoutEffect(() => {
    const sc = scroller.current, a = anchorRef.current;
    if (!sc) return;
    if (a) sc.scrollLeft = Math.max(0, LABEL + a.t * pps - a.px);
    else if (fitMode.current && pps <= fit * 1.001) sc.scrollLeft = 0;
  }, [pps, fit]);
  useEffect(() => { if (fitMode.current) { targetRef.current = fit; ppsRef.current = fit; setPps(fit); } }, [fit]);
  useEffect(() => () => cancelAnimationFrame(raf.current), []);
  useEffect(() => {
    const on = () => zoomTo(fit, null);
    window.addEventListener("vt-tl-fit", on);
    return () => window.removeEventListener("vt-tl-fit", on);
  }, [zoomTo, fit]);

  const tAt = useCallback((clientX: number) => {
    const el = scroller.current!;
    return clamp((clientX - el.getBoundingClientRect().left + el.scrollLeft - LABEL) / ppsRef.current, 0, dur);
  }, [dur]);

  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setVw(el.clientWidth));
    ro.observe(el);
    setVw(el.clientWidth);
    const wheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;                             // pinch on a trackpad arrives as ctrl+wheel
      e.preventDefault();
      const px = e.clientX - el.getBoundingClientRect().left;
      zoomTo(targetRef.current * Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0022)), { t: tAt(e.clientX), px });
    };
    let sp = 0;
    const onScroll = () => { cancelAnimationFrame(sp); sp = requestAnimationFrame(() => setScrollX(el.scrollLeft)); };
    el.addEventListener("wheel", wheel, { passive: false });
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => { ro.disconnect(); el.removeEventListener("wheel", wheel); el.removeEventListener("scroll", onScroll); cancelAnimationFrame(sp); };
  }, [zoomTo, tAt]);

  const width = LABEL + dur * pps + 24;
  const x = (t: number) => LABEL + t * pps;
  const v0 = Math.max(0, (scrollX - LABEL - 400) / pps), v1 = (scrollX + vw - LABEL + 400) / pps;   // what is on screen (plus a margin): only that is drawn

  /* ---------- the voice as clips ---------- */
  const clips: Clip[] = useMemo(() => {
    if (!audio) return [];
    const out: Clip[] = [];
    for (const k of audio.keep) {
      const cuts = audio.splits.map((s) => s.o).filter((o) => o > k.o0 + 0.02 && o < k.o1 - 0.02).sort((a, b) => a - b);
      const edges = [k.o0, ...cuts, k.o1];
      for (let i = 0; i < edges.length - 1; i++) {
        const o0 = edges[i], o1 = edges[i + 1];
        const mid = (o0 + o1) / 2;
        const g = audio.gains.find((q) => mid >= q.o0 && mid <= q.o1);
        out.push({ key: `${o0.toFixed(3)}`, o0, o1, s: k.s + (o0 - k.o0), e: k.s + (o1 - k.o0), muted: audio.mutes.some((m) => mid >= m.o0 && mid <= m.o1), db: g ? g.db : null });
      }
    }
    return out;
  }, [audio]);

  /* ---------- snapping ---------- */
  const targets = useMemo(() => {
    const t: number[] = [0, dur];
    scenes.forEach((s) => { const tm = timing.get(s.id); if (tm) t.push(tm.start, tm.end); });
    clips.forEach((c) => t.push(c.o0, c.o1));
    audio?.cuts.forEach((c) => t.push(c.o));
    return t;
  }, [scenes, timing, clips, audio, dur]);
  const snapT = useCallback((t: number, alt = false, withWords = true) => {
    if (!snap || alt) return { t, hit: null as number | null };
    const th = 6 / ppsRef.current;
    let best: number | null = null;
    const consider = (c: number) => { if (Math.abs(c - t) <= th && (best === null || Math.abs(c - t) < Math.abs(best - t))) best = c; };
    consider(timeStore.t);
    targets.forEach(consider);
    if (withWords) for (const w of r.words) { if (w.start > t + th) break; if (w.start >= t - th) consider(w.start); }
    return best === null ? { t, hit: null } : { t: best as number, hit: best as number };
  }, [snap, targets, r.words]);

  const drag = useCallback((e: React.PointerEvent | PointerEvent, move: (ev: PointerEvent) => void, up: (ev: PointerEvent, moved: boolean) => void, cancel?: () => void) => {
    const sx = e.clientX, sy = e.clientY;
    let moved = false;
    try { (e.target as Element).setPointerCapture?.(e.pointerId); } catch { /* the element may already be gone */ }     // the drag keeps working outside the window and over the preview
    document.body.classList.add("tl-scrubbing");
    let raf = 0, last: PointerEvent | null = null;                    // at most one update per frame: the pointer can report several times in one
    const m = (ev: PointerEvent) => {
      if (!moved && Math.hypot(ev.clientX - sx, ev.clientY - sy) < 3) return;
      moved = true;
      last = ev;
      if (!raf) raf = requestAnimationFrame(() => { raf = 0; if (last) move(last); });
    };
    const done = () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", m);
      window.removeEventListener("pointerup", u);
      window.removeEventListener("keydown", k, true);
      document.body.classList.remove("tl-scrubbing");
      setGuide(null);
    };
    const u = (ev: PointerEvent) => { done(); up(ev, moved); };
    const k = (ev: KeyboardEvent) => { if (ev.key === "Escape") { ev.stopPropagation(); done(); cancel?.(); } };      // Escape drops the drag and leaves everything as it was
    window.addEventListener("pointermove", m);
    window.addEventListener("pointerup", u);
    window.addEventListener("keydown", k, true);
  }, []);

  /* ---------- scrubbing (ruler and empty lane space) ---------- */
  const scrub = (e: React.PointerEvent) => {
    e.preventDefault();
    const go = (cx: number, alt: boolean) => { const s = snapT(tAt(cx), alt); setGuide(s.hit); seek(s.t); };
    go(e.clientX, e.altKey);
    drag(e, (ev) => go(ev.clientX, ev.altKey), () => {});
  };

  const onHover = (e: React.PointerEvent) => {
    const h = hover.current, sc = scroller.current;
    if (!h || !sc) return;
    const t = tAt(e.clientX);
    h.style.display = "block";
    h.style.transform = `translate3d(${x(t)}px,0,0)`;
    h.setAttribute("data-t", stamp(t, pps > 150 ? 0.1 : 1));
  };

  /* ---------- scene edges (drag, snap to sentences) and blade on scenes ---------- */
  const startEdge = (e: React.PointerEvent, i: number) => {
    e.stopPropagation();
    e.preventDefault();
    const a = scenes[i], b = scenes[i + 1];
    const ta = a && timing.get(a.id), tb = b && timing.get(b.id);
    if (!a || !b || !ta || !tb) return;
    const pool = [...a.beats, ...b.beats].slice(1).map((id) => beatById.get(id)).filter(Boolean) as { id: string; start: number }[];
    if (!pool.length) return;
    const nearest = (t: number) => pool.reduce((best, c) => (Math.abs(c.start - t) < Math.abs(best.start - t) ? c : best), pool[0]);
    const free = (ev: PointerEvent) => clamp(tAt(ev.clientX), ta.start + 0.3, tb.end - 0.3);                  // the edge itself follows the pointer
    setEdge({ i, snap: ta.end, land: null });
    drag(e, (ev) => { const t = free(ev); setEdge({ i, snap: t, land: nearest(t).start }); }, (ev, moved) => {
      if (!moved) return setEdge(null);
      const pick = nearest(free(ev));
      if (pick.id === b.beats[0]) return setEdge(null);
      setEdge({ i, snap: pick.start, land: null });                       // settles on the sentence and stays until the new plan arrives: no jump back and forth
      Promise.resolve(r.moveBoundary(a.id, pick.id)).finally(() => setEdge(null));
    }, () => setEdge(null));
  };
  const bladeScene = (sid: string, t: number) => {
    const sc = scenes.find((q) => q.id === sid);
    if (!sc || sc.beats.length < 2) return;
    const cand = sc.beats.slice(1).map((id) => beatById.get(id)).filter(Boolean) as { id: string; start: number }[];
    const pick = cand.reduce((best, c) => (Math.abs(c.start - t) < Math.abs(best.start - t) ? c : best), cand[0]);
    r.splitScene(sid, pick.id);
  };

  /* ---------- stick action chips ---------- */
  const startAction = (e: React.PointerEvent, sid: string, k: number) => {
    e.stopPropagation();
    e.preventDefault();
    const sc = scenes.find((q) => q.id === sid);
    if (!sc) return;
    const ids = new Set(sc.beats.flatMap((b) => beatById.get(b)?.word_ids ?? []));
    const pool = r.words.filter((w) => ids.has(w.id) && !w.cut);
    if (!pool.length) return;
    const near = (t: number) => pool.reduce((best, c) => (Math.abs(c.start - t) < Math.abs(best.start - t) ? c : best), pool[0]);
    drag(e, (ev) => setActDrag({ sid, k, t: near(tAt(ev.clientX)).start }), (ev, moved) => {
      setActDrag(null);
      if (moved) r.patchAction(sid, k, { patch: { at_word: near(tAt(ev.clientX)).id } });
    });
  };

  /* ---------- the voice: select, range, trim, blade ---------- */
  const clipAt = (t: number) => clips.find((c) => t >= c.o0 && t <= c.o1) ?? null;
  const onVoiceDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const t0 = snapT(tAt(e.clientX), e.altKey).t;
    if (tool === "blade") { audio && r.audioEdit("split", { t: t0 }); return; }
    drag(e, (ev) => {
      const t1 = snapT(tAt(ev.clientX), ev.altKey);
      setGuide(t1.hit);
      setSel({ o0: Math.min(t0, t1.t), o1: Math.max(t0, t1.t) });
    }, (ev, moved) => {
      if (moved) return;
      const c = clipAt(t0);
      seek(t0);
      setSel(c ? { o0: c.o0, o1: c.o1 } : null);
    });
  };
  const adjacentCut = (clip: Clip, side: "left" | "right") => audio?.cuts.find((c) => (side === "left" ? Math.abs(c.e - clip.s) < 0.002 : Math.abs(c.s - clip.e) < 0.002)) ?? null;
  const startTrim = (e: React.PointerEvent, clip: Clip, side: "left" | "right") => {
    e.stopPropagation();
    e.preventDefault();
    if (tool === "blade") return;
    const edgeT = side === "left" ? clip.o0 : clip.o1;
    const cut = adjacentCut(clip, side);
    const shape = (t: number) => {
      const d = t - edgeT;
      if (side === "left") return d > 0 ? { o0: edgeT, o1: Math.min(clip.o1 - 0.05, t), kind: "cut" as const } : cut ? { o0: Math.max(edgeT - cut.len, t), o1: edgeT, kind: "restore" as const } : null;
      return d < 0 ? { o0: Math.max(clip.o0 + 0.05, t), o1: edgeT, kind: "cut" as const } : cut ? { o0: edgeT, o1: Math.min(edgeT + cut.len, t), kind: "restore" as const } : null;
    };
    const show = (t: number) => {
      const g = shape(t);
      setGhost(g);
      if (g && g.kind === "cut") setTrim({ key: clip.key, o0: side === "left" ? g.o1 : clip.o0, o1: side === "right" ? g.o0 : clip.o1 });     // the clip's edge moves with the pointer
      else setTrim(null);
      setHint(!g ? { t, text: "Nothing was cut here, so there is nothing to bring back" } : { t, text: `${g.kind === "cut" ? "\u2212" : "+"}${(g.o1 - g.o0).toFixed(2)} s` });
      return g;
    };
    const clear = () => { setGhost(null); setTrim(null); setHint(null); };
    drag(e, (ev) => { const s = snapT(tAt(ev.clientX), ev.altKey); setGuide(s.hit); show(s.t); }, (ev) => {
      const g = shape(snapT(tAt(ev.clientX), ev.altKey).t);
      setHint(null);
      if (!g || g.o1 - g.o0 < 0.03) return clear();
      setGhost({ ...g, pending: true });                                   // shown until the server has re-cut the audio, so nothing flickers
      const done = g.kind === "cut" ? r.audioEdit("cut", { start: g.o0, end: g.o1 }) : cut ? r.audioEdit("restore", { index: cut.index, side: side === "left" ? "end" : "start", amount: g.o1 - g.o0 }) : null;
      Promise.resolve(done).finally(clear);
    }, clear);
  };
  const dragSelEdge = (e: React.PointerEvent, which: "o0" | "o1") => {
    e.stopPropagation();
    e.preventDefault();
    if (!sel) return;
    drag(e, (ev) => { const s = snapT(tAt(ev.clientX), ev.altKey); setGuide(s.hit); setSel(which === "o0" ? { o0: Math.min(s.t, sel.o1 - 0.02), o1: sel.o1 } : { o0: sel.o0, o1: Math.max(s.t, sel.o0 + 0.02) }); }, () => {});
  };

  const selMuted = !!(sel && audio && audio.mutes.some((m) => m.o0 <= sel.o0 + 0.01 && m.o1 >= sel.o1 - 0.01));
  const selGain = useMemo(() => {
    if (!sel || !audio) return 0;
    const g = audio.gains.find((q) => q.o0 <= sel.o0 + 0.01 && q.o1 >= sel.o1 - 0.01);
    return g ? g.db : 0;
  }, [sel, audio]);
  const cutSel = () => { if (sel && sel.o1 - sel.o0 > 0.03) { r.audioEdit("cut", { start: sel.o0, end: sel.o1 }); setSel(null); } };
  const muteSel = () => { if (sel) r.audioEdit("mute", { start: sel.o0, end: sel.o1, on: !selMuted }); };
  const splitHere = () => {
    const sc = selLayer ? layers.doc.clips.find((c) => c.id === selLayer) : null;
    const res = sc ? Ops.split(layers.doc, sc.id, timeStore.t) : null;
    if (res) { layers.commit(res.doc); onSelectLayer(res.ids[1]); return; }
    if (audio) r.audioEdit("split", { t: timeStore.t });
  };
  const addText = () => {
    const made = Ops.place(layers.doc, Ops.newText(timeStore.t) as any, "visual", dur);
    layers.commit(made.doc);
    onSelectLayer(made.clip.id);
  };
  const gainTimer = useRef(0);
  const commitGain = (db: number) => {
    window.clearTimeout(gainTimer.current);
    gainTimer.current = window.setTimeout(() => { if (sel) r.audioEdit("gain", { start: sel.o0, end: sel.o1, db }).then(() => setGainLive(null)); else setGainLive(null); }, 350);
  };

  const openMenu = (e: React.MouseEvent, c: Clip | null) => {
    e.preventDefault();
    const t = tAt(e.clientX);
    const target = sel && t >= sel.o0 && t <= sel.o1 ? sel : c ? { o0: c.o0, o1: c.o1 } : null;
    if (target) setSel(target);
    setMenu({
      x: e.clientX, y: e.clientY, items: [
        ...(target ? [
          { label: "Cut out (ripple delete)", run: () => r.audioEdit("cut", { start: target.o0, end: target.o1 }), danger: true },
          { label: selMuted ? "Unmute" : "Mute", run: () => r.audioEdit("mute", { start: target.o0, end: target.o1, on: !selMuted }) },
          { label: "Volume: reset", run: () => r.audioEdit("gain", { start: target.o0, end: target.o1, db: 0 }) },
          { label: "Volume: −6 dB", run: () => r.audioEdit("gain", { start: target.o0, end: target.o1, db: -6 }) },
          { label: "Volume: +4 dB", run: () => r.audioEdit("gain", { start: target.o0, end: target.o1, db: 4 }) },
        ] : []),
        { label: "Split here", run: () => r.audioEdit("split", { t }) },
      ],
    });
  };

  /* ---------- waveform per clip (only the visible part is drawn; worked out again only when zoom, scroll or the audio change, not on every drag frame) ---------- */
  const waves = useMemo(() => new Map(clips.map((c) => [c.key, wave(c)])), [clips, audio?.peaks, pps, v0, v1]);   // eslint-disable-line react-hooks/exhaustive-deps
  function wave(c: Clip) {
    const pk = audio?.peaks;
    if (!pk || !pk.v.length) return "";
    const a = Math.max(c.o0, v0), b = Math.min(c.o1, v1);
    if (b <= a) return "";
    const px = Math.max(8, Math.min(2000, Math.round(((b - a) * pps) / 2)));
    const perSec = pk.n / pk.duration;
    let top = "", bot = "";
    for (let i = 0; i < px; i++) {
      const ta = a + ((b - a) * i) / px, tb = a + ((b - a) * (i + 1)) / px;
      const i0 = Math.floor((c.s + (ta - c.o0)) * perSec), i1 = Math.max(i0 + 1, Math.ceil((c.s + (tb - c.o0)) * perSec));
      let m = 0;
      for (let k = i0; k < i1 && k < pk.v.length; k++) if (pk.v[k] > m) m = pk.v[k];
      const xx = (ta - c.o0) * pps;
      const h = 1 + m * 17;
      top += `${i ? "L" : "M"}${xx.toFixed(1)} ${(20 - h).toFixed(1)}`;
      bot = `L${xx.toFixed(1)} ${(20 + h).toFixed(1)}` + bot;
    }
    return top + bot + "Z";
  }

  /* ---------- ruler ---------- */
  const major = STEPS.find((s) => s * pps >= 90) ?? STEPS[STEPS.length - 1];
  const minorN = major >= 1 ? (major % 5 === 0 ? 5 : major === 2 ? 4 : 2) : 5;
  const ticks: { t: number; big: boolean }[] = [];
  for (let t = Math.floor(v0 / (major / minorN)) * (major / minorN); t <= Math.min(dur, v1) + 1e-6; t += major / minorN) {
    const tt = +t.toFixed(4);
    if (tt >= 0) ticks.push({ t: tt, big: Math.abs(tt / major - Math.round(tt / major)) < 1e-4 });
  }

  const words = useMemo(() => r.words.filter((w) => w.end >= v0 && w.start <= v1), [r.words, v0, v1]);
  const wordLane = useMemo(() => words.map((w) => (
    <button key={w.id} className={`tl-word bn ${w.cut ? "cut" : ""} ${w.flag === "review" ? "flag" : ""}`} style={{ left: x(w.start), width: Math.max(4, (w.end - w.start) * pps - 1) }} onClick={() => seek(w.start)} title={w.text}>
      {(w.end - w.start) * pps > 26 ? w.text : ""}
    </button>
  )), [words, pps, seek]);                                                                                     // eslint-disable-line react-hooks/exhaustive-deps

  /* elements and actions never sit on top of each other: crowded ones go on a second row */
  const elItems = useMemo(() => scenes.flatMap((s) => s.elements.map((el, k) => ({ s, el: el as any, k, w: r.wordById.get(el.at_word) }))).filter((q) => q.w) as { s: (typeof scenes)[number]; el: any; k: number; w: NonNullable<ReturnType<typeof r.wordById.get>> }[], [scenes, r.wordById]);
  const elPack = useMemo(() => pack(elItems.map((q) => ({ left: LABEL + q.w.start * pps, w: chipW(q.el.type.replace("_", " ")) }))), [elItems, pps]);
  const actItems = useMemo(() => scenes.flatMap((s) => (s.stick?.actions ?? []).map((a: any, k: number) => ({ s, a, k }))), [scenes]);
  const actPack = useMemo(() => pack(actItems.map((q) => ({ left: LABEL + q.a.start * pps, w: Math.max(10, (q.a.end - q.a.start) * pps, chipW(q.a.do.replace("_", " "))) }))), [actItems, pps]);
  const keyZoom = { t: timeStore.t, px: x(timeStore.t) - (scroller.current?.scrollLeft ?? 0) };

  return (
    <div className="tl" aria-label="Timeline">
      <div className="tl-bar" role="toolbar" aria-label="Timeline tools">
        <button className={`tl-tool ${tool === "select" ? "on" : ""}`} onClick={() => setTool("select")} aria-pressed={tool === "select"} aria-label="Select tool" title="Select (V)"><MousePointer2 size={15} /></button>
        <button className={`tl-tool ${tool === "blade" ? "on" : ""}`} onClick={() => setTool("blade")} aria-pressed={tool === "blade"} aria-label="Blade tool" title="Blade: click the voice or a scene to split it (B)"><Scissors size={15} /></button>
        <button className={`tl-tool ${snap ? "on" : ""}`} onClick={() => setSnap(!snap)} aria-pressed={snap} aria-label="Snapping" title="Snapping (N). Hold Alt while dragging to ignore it"><Magnet size={15} /></button>
        <span className="ds-sep" aria-hidden />
        <button className="tl-tool" onClick={splitHere} aria-label="Split the voice at the playhead" title="Split the voice at the playhead (Ctrl+B)" disabled={!audio}><Scissors size={14} style={{ transform: "rotate(90deg)" }} /></button>
        <button className="tl-tool" onClick={cutSel} aria-label="Cut out the selection" title="Cut out the selection and close the gap (Delete)" disabled={!sel || sel.o1 - sel.o0 < 0.03}><Trash2 size={14} /></button>
        <button className={`tl-tool ${selMuted ? "on" : ""}`} onClick={muteSel} aria-label="Mute the selection" title="Mute or unmute the selection (M)" disabled={!sel}>{selMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}</button>
        <label className="tl-gain" title="Volume of the selection">
          <span className="small muted">Volume</span>
          <input type="range" min={-24} max={12} step={0.5} value={gainLive ?? selGain} disabled={!sel} aria-label="Volume of the selection in decibels"
            onChange={(e) => setGainLive(+e.target.value)} onPointerUp={(e) => commitGain(+(e.target as HTMLInputElement).value)} onKeyUp={(e) => (e.key.startsWith("Arrow") || e.key === "Home" || e.key === "End") && commitGain(+(e.target as HTMLInputElement).value)} />
          <span className="small" style={{ minWidth: 44, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{(gainLive ?? selGain) > 0 ? "+" : ""}{(gainLive ?? selGain).toFixed(1)} dB</span>
        </label>
        <span className="small muted" style={{ marginLeft: 8 }}>{sel ? `${stamp(sel.o0, 0.1)} – ${stamp(sel.o1, 0.1)} (${(sel.o1 - sel.o0).toFixed(2)} s)` : `${scenes.length} scenes · ${fmtTime(dur)}`}</span>
        <span className="ds-sep" aria-hidden />
        <button className="tl-tool" onClick={addText} aria-label="Add a text layer" title="Add a text layer at the playhead"><Type size={14} /></button>
        <button className="tl-tool" onClick={onAddMedia} aria-label="Add a picture, video or sound" title="Add a picture, video clip or sound from your files"><LayersIcon size={14} /></button>
        <button className="tl-tool" onClick={(e) => setMenu({ x: e.clientX, y: e.clientY, items: [{ label: "New picture / text track", run: () => layers.commit(Ops.addTrack(layers.doc, "visual").doc) }, { label: "New sound track", run: () => layers.commit(Ops.addTrack(layers.doc, "audio").doc) }] })} aria-label="Add a track" title="Add a track"><Plus size={14} /></button>
        <span className="grow" />
        <button className="btn ghost icon sm" aria-label="Zoom out" onClick={() => zoomTo(targetRef.current / 1.5, keyZoom)}><Minus size={14} /></button>
        <input type="range" min={0} max={1000} value={Math.round((Math.log(clamp(pps / fit, 1, MAX_PPS / fit)) / Math.log(MAX_PPS / fit)) * 1000)} aria-label="Timeline zoom" style={{ width: 96 }}
          onChange={(e) => zoomTo(fit * Math.pow(MAX_PPS / fit, +e.target.value / 1000), keyZoom)} />
        <button className="btn ghost icon sm" aria-label="Zoom in" onClick={() => zoomTo(targetRef.current * 1.5, keyZoom)}><Plus size={14} /></button>
        <button className="btn ghost icon sm" aria-label="Fit the whole video" title="Fit (\)" onClick={() => zoomTo(fit, null)}><Maximize2 size={14} /></button>
        <span className="small muted" style={{ minWidth: 40, textAlign: "right" }}>{Math.round((pps / fit) * 100)}%</span>
      </div>

      <div className={`tl-scroll ${tool === "blade" ? "blade" : ""}`} ref={scroller} onPointerMove={onHover} onPointerLeave={() => hover.current && (hover.current.style.display = "none")}>
        <div className="tl-inner" style={{ width }}>
          <div className="tl-ruler" onPointerDown={scrub} aria-label="Ruler: click or drag to move the playhead">
            {ticks.map((k) => (
              <div key={k.t} className={`tl-tick ${k.big ? "big" : ""}`} style={{ left: x(k.t) }}>{k.big ? stamp(k.t, major) : ""}</div>
            ))}
          </div>

          <LayerLanes kind="visual" layers={layers} label={LABEL} x={x} tAt={tAt} pps={pps} v0={v0} v1={v1} total={dur} drag={drag} snapT={snapT} setGuide={setGuide} media={media} selected={selLayer} onSelect={onSelectLayer} scrub={scrub} menu={(mx, my, items) => setMenu({ x: mx, y: my, items })} seek={seek}
 />

          <div className="tl-lane tall" role="group" aria-label="Scenes" onPointerDown={(e) => e.target === e.currentTarget && scrub(e)}>
            <div className="tl-label">Scenes</div>
            {scenes.map((s, i) => {
              const t0 = timing.get(s.id);
              if (!t0 || t0.end < v0 || t0.start > v1) return null;
              const t = edge && edge.snap != null && (i === edge.i || i === edge.i + 1) ? { ...t0, end: i === edge.i ? edge.snap : t0.end, start: i === edge.i + 1 ? edge.snap : t0.start } : t0;   // the two scenes follow the drag
              const th = thumbs[s.id];
              const w = (t.end - t.start) * pps;
              return (
                <div key={s.id} role="button" tabIndex={0} aria-label={`Scene ${i + 1}`} aria-pressed={selected === s.id} className={`tl-clip ${selected === s.id ? "sel" : ""} ${edge && edge.land == null ? "live" : ""}`}
                  style={{ left: x(t.start), width: Math.max(8, w - 2) }}
                  onClick={(e) => { if (tool === "blade") return bladeScene(s.id, tAt(e.clientX)); onSelect(s.id); seek(t.start); }}
                  onKeyDown={(e) => e.key === "Enter" && (onSelect(s.id), seek(t.start))}>
                  {th && w > 46 && <img src={th} alt="" draggable={false} />}
                  <span>{i + 1}</span>
                  {s.archetype && w > 90 && <span className="muted" style={{ fontWeight: 500 }}>{s.archetype.replace("_", " ")}</span>}
                  {i > 0 && <div className="grab l" onPointerDown={(e) => startEdge(e, i - 1)} title="Drag to move where this scene starts" aria-label={`Move the start of scene ${i + 1}`} />}
                  {i < scenes.length - 1 && <div className="grab" onPointerDown={(e) => startEdge(e, i)} title="Drag to move where this scene ends" aria-label={`Move the end of scene ${i + 1}`} />}
                </div>
              );
            })}
            {edge && edge.land != null && <div className="tl-snap land" style={{ left: x(edge.land) }} title="The scene will end here, at the start of this sentence" />}
          </div>

          <div className="tl-lane slim" role="group" aria-label="Elements" style={{ height: elPack.count * ROW + 4 }} onPointerDown={(e) => e.target === e.currentTarget && scrub(e)}>
            <div className="tl-label">Elements</div>
            {elItems.map((q, n) => {
              if (q.w.start < v0 - 2 || q.w.start > v1) return null;
              const on = selectedEl?.scene === q.s.id && selectedEl.index === q.k;
              const label = q.el.type.replace("_", " ");
              return <button key={`${q.s.id}-${q.k}`} className={`tl-chip ${on ? "sel" : ""}`} style={{ left: x(q.w.start), top: 4 + elPack.rows[n] * ROW, maxWidth: 160 }} onClick={() => onSelectEl(q.s.id, q.k)} title={`${label} appears at “${q.w.text}”`}>{label}</button>;
            })}
          </div>

          {scenes.some((s) => (s.stick?.actions?.length ?? 0) > 0) && (
            <div className="tl-lane slim" role="group" aria-label="Actions" style={{ height: actPack.count * ROW + 4 }} onPointerDown={(e) => e.target === e.currentTarget && scrub(e)}>
              <div className="tl-label">Actions</div>
              {actItems.map((q, n) => {
                const { s, a, k } = q;
                if (a.end < v0 || a.start > v1) return null;
                const live = actDrag && actDrag.sid === s.id && actDrag.k === k;
                return <span key={`a-${s.id}-${k}`} role="button" tabIndex={0} aria-label={`Action ${a.do}`} className="tl-chip" onPointerDown={(e) => startAction(e, s.id, k)}
                  style={{ left: x(live ? actDrag!.t : a.start), top: 4 + actPack.rows[n] * ROW, width: Math.max(10, (a.end - a.start) * pps), background: "var(--ok-soft)", color: "var(--ok)", cursor: "grab", opacity: live ? 0.7 : 1 }}
                  title={`${a.do.replace("_", " ")}: drag to another word`}>{a.do.replace("_", " ")}</span>;
              })}
            </div>
          )}

          {(sounds?.available || (sounds?.events.length ?? 0) > 0) && (
            <div className="tl-lane slim" role="group" aria-label="Sounds" onPointerDown={(e) => e.target === e.currentTarget && scrub(e)}>
              <div className="tl-label">Sounds</div>
              {(sounds?.events ?? []).filter((e) => e.end >= v0 && e.start <= v1).map((e, i) => (
                <button key={`${e.concept}-${e.start}-${i}`} className="tl-chip tl-sound" style={{ left: x(e.start), width: Math.max(22, (e.end - e.start) * pps - 1) }} onClick={() => seek(e.start)}
                  title={`${e.label} (${e.start.toFixed(1)}\u2013${e.end.toFixed(1)} s, ${Math.round(e.score * 100)}% sure)`}>
                  <span aria-hidden>{String.fromCodePoint(parseInt(e.emoji, 16))}</span> {(e.end - e.start) * pps > 70 ? e.label : ""}
                </button>
              ))}
              {sounds && !sounds.analyzed && onListen && (
                <button className="btn sm" style={{ position: "absolute", left: LABEL + 8, top: 2, height: 22 }} onClick={onListen} disabled={listening}>{listening ? "Listening\u2026" : "Listen for laughter, applause, music\u2026"}</button>
              )}
              {sounds && sounds.analyzed && sounds.events.length === 0 && <span className="small muted" style={{ position: "absolute", left: LABEL + 8, top: 4 }}>No sounds other than speech were found.</span>}
            </div>
          )}

          <div className="tl-lane slim" role="group" aria-label="Words" onPointerDown={(e) => e.target === e.currentTarget && scrub(e)}>
            <div className="tl-label">Words</div>
            {wordLane}
          </div>

          <div className="tl-lane voice" role="group" aria-label="Audio" onPointerDown={onVoiceDown} onContextMenu={(e) => openMenu(e, clipAt(tAt(e.clientX)))}>
            <div className="tl-label">Voice</div>
            {clips.map((c, i) => {
              if (c.o1 < v0 || c.o0 > v1) return null;
              const lv = trim && trim.key === c.key ? trim : null;
              const d0 = lv ? Math.max(c.o0, lv.o0) : c.o0, d1 = lv ? Math.min(c.o1, lv.o1) : c.o1;                  // while trimming, the clip is drawn with its new edges
              const left = x(d0), w = (d1 - d0) * pps;
              const isSel = !!sel && sel.o0 <= c.o0 + 0.01 && sel.o1 >= c.o1 - 0.01;
              const shift = Math.max(c.o0, v0) > c.o0 ? (Math.max(c.o0, v0) - c.o0) * pps : 0;
              const lead = (d0 - c.o0) * pps;
              return (
                <div key={c.key} className={`tl-aclip ${c.muted ? "muted" : ""} ${isSel ? "sel" : ""}`} style={{ left, width: Math.max(2, w - 1) }} aria-label={`Voice clip ${i + 1}`}>
                  <svg width={Math.max(2, w - 1)} height={40} aria-hidden style={{ position: "absolute", inset: 0 }}>
                    <g transform={`translate(${shift - lead} 0)`}><path d={waves.get(c.key) ?? ""} fill="currentColor" /></g>
                  </svg>
                  {c.db != null && w > 40 && <span className="tl-db">{c.db > 0 ? "+" : ""}{c.db} dB</span>}
                  <div role="button" className="trim l" onPointerDown={(e) => startTrim(e, c, "left")} title="Drag to trim" aria-label={`Trim the start of clip ${i + 1}`} />
                  <div role="button" className="trim r" onPointerDown={(e) => startTrim(e, c, "right")} title="Drag to trim" aria-label={`Trim the end of clip ${i + 1}`} />
                </div>
              );
            })}
            {audio?.cuts.map((c) => (
              c.o >= v0 - 1 && c.o <= v1 + 1 ? <button key={`cut-${c.index}`} className="tl-cutmark" style={{ left: x(c.o) }} aria-label={`Restore the ${c.len.toFixed(1)} second cut`} title={`${c.len.toFixed(2)} s was cut out here. Click to bring it back`}
                onPointerDown={(e) => e.stopPropagation()} onClick={() => r.audioEdit("restore", { index: c.index, side: "all" })} /> : null
            ))}
            {sel && (
              <div className="tl-sel" style={{ left: x(sel.o0), width: Math.max(2, (sel.o1 - sel.o0) * pps) }} aria-label="Selected range">
                <i className="h l" onPointerDown={(e) => dragSelEdge(e, "o0")} /><i className="h r" onPointerDown={(e) => dragSelEdge(e, "o1")} />
              </div>
            )}
            {ghost && <div className={`tl-ghost ${ghost.kind} ${ghost.pending ? "pending" : ""}`} style={{ left: x(ghost.o0), width: Math.max(2, (ghost.o1 - ghost.o0) * pps) }} />}
            {hint && <div className="tl-hint" style={{ left: x(hint.t) }} role="status">{hint.text}</div>}
            {!audio && <span className="small muted" style={{ position: "absolute", left: LABEL + 12, top: 12 }}>Process the audio to edit the voice.</span>}
          </div>

          <LayerLanes kind="audio" layers={layers} label={LABEL} x={x} tAt={tAt} pps={pps} v0={v0} v1={v1} total={dur} drag={drag} snapT={snapT} setGuide={setGuide} media={media} selected={selLayer} onSelect={onSelectLayer} scrub={scrub} menu={(mx, my, items) => setMenu({ x: mx, y: my, items })} seek={seek}
 />

          {guide != null && <div className="tl-snap" style={{ left: x(guide) }} />}
          <div className="tl-hover" ref={hover} aria-hidden />
          <Playhead pps={pps} scroller={scroller} />
        </div>
      </div>
      {menu && <Menu x={menu.x} y={menu.y} onClose={() => setMenu(null)}>{menu.items.map((m) => <button key={m.label} className={m.danger ? "danger" : ""} onClick={() => { m.run(); setMenu(null); }}>{m.label}</button>)}</Menu>}
    </div>
  );
}
