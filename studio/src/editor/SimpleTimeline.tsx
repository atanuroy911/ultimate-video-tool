import { useT } from "../i18n";
import { Captions, Film, Minus, Music2, Plus, Redo2, Scissors, Trash2, Undo2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fmtTime } from "../api";
import { timeStore } from "../review/timeStore";
import type { Review } from "../review/useReview";

/* A timeline a first-time user can read: three tracks (pictures, captions, voice), one playhead, a handful of tools.
   Everything else (layers, sounds, every element) lives in the advanced editor. */
interface Props {
  r: Review;
  duration: number;
  selected: string | null;
  onSelect: (id: string) => void;
  seek: (t: number) => void;
  onSplit: () => void;
  onDelete: () => void;
  canDelete: boolean;
}

const GUTTER = 56;

function Clock({ total }: { total: number }) {
  const t0 = useT();
  const [t, setT] = useState(timeStore.t);
  useEffect(() => timeStore.subscribe((v) => setT(Math.round(v * 5) / 5)), []);
  return <span className="ce-clock" aria-label={t0("ed.tl.time")}><b>{fmtTime(t)}</b> / {fmtTime(total)}</span>;
}

function Waveform({ peaks, duration, width }: { peaks: number[]; duration: number; width: number }) {
  const t0 = useT();
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c || !peaks.length) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = Math.max(1, Math.floor(width * dpr));
    c.height = 40 * dpr;
    const g = c.getContext("2d")!;
    g.scale(dpr, dpr);
    g.clearRect(0, 0, width, 40);
    g.fillStyle = getComputedStyle(c).color || "#34c759";
    const bars = Math.floor(width / 3);
    for (let i = 0; i < bars; i++) {
      const v = peaks[Math.min(peaks.length - 1, Math.floor((i / bars) * peaks.length))] ?? 0;
      const h = Math.max(1.5, Math.min(1, v) * 36);
      g.fillRect(i * 3, 20 - h / 2, 2, h);
    }
  }, [peaks, width, duration]);
  return <canvas ref={ref} className="ce-wave" style={{ width, height: 40 }} aria-label={t0("ed.tl.wave")} />;
}

export default function SimpleTimeline({ r, duration, selected, onSelect, seek, onSplit, onDelete, canDelete }: Props) {
  const t0 = useT();
  const host = useRef<HTMLDivElement>(null);
  const head = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [boxW, setBoxW] = useState(900);
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setBoxW(el.clientWidth - GUTTER));
    ro.observe(el);
    setBoxW(el.clientWidth - GUTTER);
    return () => ro.disconnect();
  }, []);
  const total = Math.max(1, duration);
  const pps = (boxW / total) * zoom;                       // pixels per second: 1x fits the whole video
  const width = Math.max(boxW, total * pps);
  const scenes = r.plan?.scenes ?? [];
  const timing = useMemo(() => new Map(r.timing.scenes.map((s) => [s.id, s])), [r.timing.scenes]);
  const thumbs = r.th.data?.scenes ?? {};
  const wordsByScene = useMemo(() => {
    const byWord = new Map(r.words.map((w) => [w.id, w]));
    const beat = new Map(r.beats.map((b) => [b.id, b]));
    return new Map(scenes.map((s) => [s.id, s.beats.flatMap((b) => beat.get(b)?.word_ids ?? []).map((id) => byWord.get(id)).filter((w) => w && !w.cut).map((w) => w!.text).join(" ")]));
  }, [scenes, r.words, r.beats]);

  // the playhead follows the audio clock without re-rendering the timeline
  useEffect(() => {
    const move = (t: number) => { if (head.current) head.current.style.transform = `translateX(${t * pps}px)`; };
    move(timeStore.t);
    return timeStore.subscribe(move);
  }, [pps]);

  const timeAt = useCallback((clientX: number) => {
    const box = host.current!.querySelector(".ce-scroll") as HTMLElement;
    const x = clientX - box.getBoundingClientRect().left + box.scrollLeft;
    return Math.max(0, Math.min(total, x / pps));
  }, [pps, total]);
  const scrub = (e: React.PointerEvent) => {
    const go = (ev: PointerEvent | React.PointerEvent) => seek(timeAt(ev.clientX));
    go(e);
    const mv = (ev: PointerEvent) => go(ev);
    const up = () => { window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", mv);
    window.addEventListener("pointerup", up);
  };

  /** Drag the end of a picture: it snaps to the start of a sentence, so the cut always lands on a word. One undo step. */
  const [drag, setDrag] = useState<{ sid: string; t: number } | null>(null);
  const dragEdge = (e: React.PointerEvent, sid: string, i: number) => {
    e.preventDefault();
    e.stopPropagation();
    const a = scenes[i], b = scenes[i + 1];
    const pool = [...a.beats, ...b.beats].slice(1);                              // each scene keeps at least one sentence
    const starts = pool.map((id) => ({ id, t: r.beats.find((x) => x.id === id)?.start ?? 0 }));
    const nearest = (time: number) => starts.reduce((best, c) => (Math.abs(c.t - time) < Math.abs(best.t - time) ? c : best), starts[0]);
    const mv = (ev: PointerEvent) => setDrag({ sid, t: nearest(timeAt(ev.clientX)).t });
    const up = (ev: PointerEvent) => {
      window.removeEventListener("pointermove", mv);
      window.removeEventListener("pointerup", up);
      const pick = nearest(timeAt(ev.clientX));
      setDrag(null);
      if (pick && pick.id !== b.beats[0]) r.moveBoundary(sid, pick.id);
    };
    window.addEventListener("pointermove", mv);
    window.addEventListener("pointerup", up);
  };

  const nudgeEdge = (e: React.KeyboardEvent, sid: string, i: number) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const pool = [...scenes[i].beats, ...scenes[i + 1].beats];
    const k = pool.indexOf(scenes[i + 1].beats[0]) + (e.key === "ArrowRight" ? 1 : -1);
    if (k >= 1 && k < pool.length) r.moveBoundary(sid, pool[k]);
  };

  const step = total > 60 ? 10 : total > 20 ? 5 : total > 8 ? 2 : 1;
  const ticks = Array.from({ length: Math.floor(total / step) + 1 }, (_, i) => i * step);

  return (
    <div className="ce-tl" ref={host} aria-label={t0("ed.tl.timeline")}>
      <div className="ce-tools" role="toolbar" aria-label={t0("ed.tl.tools")}>
        <button className="ce-tool" onClick={r.undo} disabled={!r.canUndo} aria-label={t0("ed.tl.undo")} title={t0("ed.tl.undo") + " (Ctrl+Z)"}><Undo2 size={16} /></button>
        <button className="ce-tool" onClick={r.redo} disabled={!r.canRedo} aria-label={t0("ed.tl.redo")} title={t0("ed.tl.redo") + " (Ctrl+Shift+Z)"}><Redo2 size={16} /></button>
        <span className="ce-sep" />
        <button className="ce-tool" onClick={onSplit} aria-label={t0("ed.tl.split")} title={t0("ed.tl.splith")}><Scissors size={16} /> <span>{t0("ed.tl.split")}</span></button>
        <button className="ce-tool" onClick={onDelete} disabled={!canDelete} aria-label={t0("ed.delete")} title={t0("ed.tl.delh")}><Trash2 size={16} /> <span>{t0("ed.delete")}</span></button>
        <span className="grow" />
        <Clock total={total} />
        <span className="grow" />
        <button className="ce-tool" onClick={() => setZoom((z) => Math.max(1, z / 1.5))} aria-label={t0("ed.tl.zout")} disabled={zoom <= 1}><Minus size={16} /></button>
        <input className="ce-zoom" type="range" min={0} max={100} value={Math.round((Math.log(zoom) / Math.log(12)) * 100)} onChange={(e) => setZoom(Math.pow(12, +e.target.value / 100))} aria-label="Zoom" />
        <button className="ce-tool" onClick={() => setZoom((z) => Math.min(12, z * 1.5))} aria-label={t0("ed.tl.zin")}><Plus size={16} /></button>
      </div>

      <div className="ce-tracks">
        <div className="ce-gutter" aria-hidden>
          <div className="ce-ruler-g" />
          <div className="ce-g tall"><Film size={14} /></div>
          <div className="ce-g"><Captions size={14} /></div>
          <div className="ce-g"><Music2 size={14} /></div>
        </div>
        <div className="ce-scroll">
          <div className="ce-canvas" style={{ width }} onPointerDown={(e) => { if (e.target === e.currentTarget) scrub(e); }}>
            <div className="ce-ruler" onPointerDown={scrub}>
              {ticks.map((t) => <span key={t} style={{ left: t * pps }}>{fmtTime(t)}</span>)}
            </div>
            <div className="ce-track tall" role="group" aria-label={t0("ed.tl.pictures")}>
              {scenes.map((s, i) => {
                const t = timing.get(s.id);
                if (!t) return null;
                const w = (t.end - t.start) * pps;
                return (
                  <button key={s.id} className={`ce-clip ${selected === s.id ? "sel" : ""}`} style={{ left: t.start * pps, width: Math.max(10, w - 2), backgroundImage: thumbs[s.id] ? `url(${thumbs[s.id]})` : undefined }}
                    aria-label={t0("ed.scene").replace("{n}", String(i + 1))} aria-pressed={selected === s.id} onClick={() => { onSelect(s.id); seek(t.start); }}>
                    <i>{i + 1}</i>
                  </button>
                );
              })}
              {scenes.slice(0, -1).map((s, i) => {
                const t = timing.get(s.id);
                if (!t) return null;
                return <span key={`e${s.id}`} className="ce-edge" role="slider" tabIndex={0} aria-label={t0("ed.tl.end").replace("{n}", String(i + 1))} aria-valuenow={Math.round((drag?.sid === s.id ? drag.t : t.end) * 10) / 10}
                  style={{ left: (drag?.sid === s.id ? drag.t : t.end) * pps - 6 }} onPointerDown={(e) => dragEdge(e, s.id, i)} onKeyDown={(e) => nudgeEdge(e, s.id, i)} data-testid={`edge-${i}`} />;
              })}
            </div>
            <div className="ce-track" role="group" aria-label={t0("ed.tl.captions")}>
              {scenes.map((s) => {
                const t = timing.get(s.id);
                const text = wordsByScene.get(s.id);
                if (!t || !text) return null;
                return (
                  <button key={s.id} className={`ce-chip ${selected === s.id ? "sel" : ""}`} style={{ left: t.start * pps, width: Math.max(8, (t.end - t.start) * pps - 2) }}
                    onClick={() => { onSelect(s.id); seek(t.start); }} title={text}>
                    <span className="bn">{text}</span>
                  </button>
                );
              })}
            </div>
            <div className="ce-track" role="group" aria-label={t0("ed.tl.voice")}>
              <Waveform peaks={r.audio?.peaks?.v ?? []} duration={total} width={total * pps} />
            </div>
            <div className="ce-head" ref={head} aria-hidden><i /></div>
          </div>
        </div>
      </div>
    </div>
  );
}
