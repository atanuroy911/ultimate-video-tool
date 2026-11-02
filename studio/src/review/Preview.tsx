import { applyPreviewEdit } from "./previewEdits";
import { Pause, Play, Volume2 } from "lucide-react";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useLayoutEffect, useRef, useState } from "react";
import { fmtTime } from "../api";
import { toast } from "../store";
import type { Aspect, SceneTime, LClip } from "../types";

export interface PlayerHandle {
  seek: (t: number) => void;
  toggle: () => void;
  isPlaying: () => boolean;
}

interface Props {
  projectId: string;
  aspect: Aspect;
  audioUrl: string | null;
  duration: number;
  scenes: SceneTime[];
  selected: string | null;
  onSelectScene: (id: string) => void;
  onTime: (t: number) => void;
  onPlaying?: (playing: boolean) => void;
  rev: number; // bumps when the composition data changed -> hot-swap data in the iframe
  reloadKey: string; // changes when the iframe must reload (theme / aspect / fonts)
  safeArea: boolean;
  onPick?: (scene: string | null, index: number | null) => void;
  selectedEl?: { scene: string; index: number } | null;
  showTimeline?: boolean;
  layerAudio?: LayerSound[];       // sounds on the layers' audio tracks, played in step with the voice
  visualLayers?: (LClip & { end: number })[];
}

export interface LayerSound { id: string; url: string; start: number; dur: number; in: number; volume: number; fadeIn: number; fadeOut: number }

const SIZES = { "9:16": { w: 1080, h: 1920, box: 300 }, "1:1": { w: 1080, h: 1080, box: 420 }, "16:9": { w: 1920, h: 1080, box: 600 } } as const;
const TAGS = { "9:16": "9x16", "1:1": "1x1", "16:9": "16x9" } as const;
const CHROME_H = 130;
const CHROME_COMPACT = 64; // timeline + transport + caption lines under the phone

const Preview = forwardRef<PlayerHandle, Props>(function Preview(p, ref) {
  const frame = useRef<HTMLIFrameElement>(null);
  const composition = useRef<any>(null);
  const visualLayersRef = useRef(p.visualLayers);
  visualLayersRef.current = p.visualLayers;
  const audio = useRef<HTMLAudioElement>(null);
  const [ready, setReady] = useState(false);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const playingRef = useRef(false);
  playingRef.current = playing;
  const propsRef = useRef(p);
  propsRef.current = p;
  const [rate, setRate] = useState(1);
  const [muted, setMuted] = useState(false);
  const [selRect, setSelRect] = useState<number[] | null>(null);
  const onPickRef = useRef(p.onPick);
  onPickRef.current = p.onPick;
  const raf = useRef(0);
  const layerEls = useRef(new Map<string, HTMLAudioElement>());
  const layerRef = useRef<LayerSound[]>(p.layerAudio ?? []);
  layerRef.current = p.layerAudio ?? [];
  const mutedRef = useRef(false);
  const rateRef = useRef(1);
  /** Keep the layers' sounds in step with the voice: start them inside their range, stop them outside it, follow the volume and the fades. */
  const syncLayers = useCallback((t: number, play: boolean) => {
    const els = layerEls.current;
    const live = new Set(layerRef.current.map((c) => c.id));
    for (const [id, el] of els) if (!live.has(id)) { el.pause(); els.delete(id); }
    for (const c of layerRef.current) {
      let el = els.get(c.id);
      if (!el || el.getAttribute("src") !== c.url) {
        el?.pause(); el = new Audio(c.url); el.preload = "auto"; els.set(c.id, el);
      }
      const active = play && t >= c.start && t < c.start + c.dur;
      if (!active) { if (!el.paused) el.pause(); continue; }
      const into = t - c.start, left = c.start + c.dur - t;
      const fade = Math.min(1, c.fadeIn > 0 ? into / c.fadeIn : 1, c.fadeOut > 0 ? left / c.fadeOut : 1);
      el.volume = mutedRef.current ? 0 : Math.max(0, Math.min(1, c.volume * fade));
      el.playbackRate = rateRef.current;
      const want = c.in + into;
      if (el.paused) { try { el.currentTime = want; } catch { /* not loaded yet */ } el.play().catch(() => {}); }
      else if (Math.abs(el.currentTime - want) > 0.3) el.currentTime = want;
    }
  }, []);
  useEffect(() => () => { layerEls.current.forEach((el) => el.pause()); layerEls.current.clear(); }, []);
  useEffect(() => p.onPlaying?.(playing), [playing]); // eslint-disable-line react-hooks/exhaustive-deps
  const timeRef = useRef(0);
  const host = useRef<HTMLDivElement>(null);
  const [avail, setAvail] = useState({ w: 600, h: 560 });
  // fit the phone to the space the column actually has, so the transcript below always keeps room
  useLayoutEffect(() => {
    const el = host.current?.parentElement;
    if (!el) return;
    const ro = new ResizeObserver(() => setAvail({ w: el.clientWidth - 32, h: el.clientHeight }));
    ro.observe(el);
    setAvail({ w: el.clientWidth - 32, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);
  const base = SIZES[p.aspect];
  const maxH = p.showTimeline === false ? Math.max(60, avail.h - CHROME_COMPACT - 28) : Math.max(100, avail.h * 0.62 - CHROME_H);
  const box = Math.round(Math.max(32, Math.min(p.showTimeline === false ? 1200 : base.box, avail.w, (maxH * base.w) / base.h)));
  const sz = { ...base, box };
  const tag = TAGS[p.aspect];
  const scale = sz.box / sz.w;
  const boxH = sz.h * scale;
  const dur = Math.max(p.duration, 0.1);

  const post = useCallback((msg: any) => frame.current?.contentWindow?.postMessage(msg, "*"), []);

  const seek = useCallback(
    (t: number) => {
      const tt = Math.max(0, Math.min(dur, t));
      timeRef.current = tt;
      if (audio.current) audio.current.currentTime = tt;
      post({ vt: "seek", t: tt });
      syncLayers(tt, playingRef.current);
      setTime(tt);
      p.onTime(tt);
    },
    [dur, post, p]
  );

  const loop = useCallback(() => {
    const a = audio.current;
    if (a) {
      const t = a.currentTime;
      timeRef.current = t;
      post({ vt: "seek", t });
      setTime(t);
      propsRef.current.onTime(t);
      if (a.ended || t >= propsRef.current.duration - 0.02) {
        a.pause();
        syncLayers(t, false);
        setPlaying(false);
        return;
      }
      syncLayers(t, true);
    }
    raf.current = requestAnimationFrame(loop);
  }, [dur, post, p, syncLayers]);

  const play = useCallback(() => {
    const a = audio.current;
    if (!a) return;
    if (a.currentTime >= dur - 0.05) a.currentTime = 0;
    a.playbackRate = rate;
    a.play().then(() => {
      setPlaying(true);
      cancelAnimationFrame(raf.current);
      raf.current = requestAnimationFrame(loop);
    }).catch(() => { setPlaying(false); toast("The preview could not play. Try again once the audio finishes loading.", "err"); });
  }, [dur, loop, rate]);

  const pause = useCallback(() => {
    audio.current?.pause();
    cancelAnimationFrame(raf.current);
    layerEls.current.forEach((el) => el.pause());
    setPlaying(false);
  }, []);

  useImperativeHandle(ref, () => ({ seek, toggle: () => (playing ? pause() : play()), isPlaying: () => playing }), [seek, playing, play, pause]);

  // iframe messages
  useEffect(() => {
    const on = (e: MessageEvent) => {
      if (e.source !== frame.current?.contentWindow) return;
      if (e.data?.vt === "ready") {
        setReady(true);
        post({ vt: "seek", t: timeRef.current });
      } else if (e.data?.vt === "picked") onPickRef.current?.(e.data.scene, e.data.index);
      else if (e.data?.vt === "rect") setSelRect(e.data.box);
    };
    window.addEventListener("message", on);
    return () => window.removeEventListener("message", on);
  }, [post]);

  useEffect(() => { setReady(false); composition.current = null; }, [p.reloadKey, p.aspect, p.projectId]);

  // open on a poster frame: the first moment where something is on screen, instead of a blank first frame
  const poster = useRef(false);
  useEffect(() => {
    poster.current = false;
  }, [p.reloadKey, p.aspect, p.projectId]);
  useEffect(() => {
    if (!ready || poster.current) return;
    poster.current = true;
    fetch(`/media/${p.projectId}/composition/${tag}/data.json?v=poster`, { cache: "no-store" })
      .then((r) => { if (!r.ok) throw new Error("Preview data unavailable"); return r.json(); })
      .then((d) => {
        const first = Math.min(...d.scenes.flatMap((s: any) => s.elements.map((e: any) => e.at)).concat([d.duration]));
        if (timeRef.current === 0) seek(Math.min(d.duration, first + 1.1));
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, tag, p.projectId]);

  // hot-swap composition data after edits (no reload, no flicker)
  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    const controller = new AbortController();
    fetch(`/media/${p.projectId}/composition/${tag}/data.json?v=${p.rev}`, { cache: "no-store", signal: controller.signal })
      .then((r) => { if (!r.ok) throw new Error(`Preview update failed (${r.status})`); return r.json(); })
      .then((data) => {
        if (!cancelled) {
          composition.current = data;
          post({ vt: "data", data: {...data, ...(visualLayersRef.current ? {layers: visualLayersRef.current} : {})} });
          post({ vt: "seek", t: Math.min(timeRef.current, data.duration ?? timeRef.current) });
        }
      })
      .catch((error) => { if (!cancelled) toast(error.message || "Could not update the preview", "err"); });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [p.rev, ready, tag, p.projectId, post]);

  useEffect(() => {
    if(!ready) return;
    const draw = (data:any) => { post({vt:"data",data:{...data,layers:visualLayersRef.current ?? data.layers}}); post({vt:"seek",t:timeRef.current}); };
    const edit = (event:Event) => { if(composition.current) draw(applyPreviewEdit(composition.current,(event as CustomEvent).detail)); };
    const elements = (event:Event) => {
      if(!composition.current) return;
      const {scene,elements}=(event as CustomEvent).detail;
      let data=composition.current;
      elements.forEach((el:any,index:number)=>{data=applyPreviewEdit(data,{kind:"element",scene,index,patch:el});}); draw(data);
    };
    window.addEventListener("vt-preview-edit",edit); window.addEventListener("vt-preview-elements",elements);
    return ()=>{window.removeEventListener("vt-preview-edit",edit);window.removeEventListener("vt-preview-elements",elements);};
  },[ready,post]);

  // Local layer edits follow the pointer/text field before the save completes.
  useEffect(() => {
    if (!ready || !composition.current || !p.visualLayers) return;
    const id = requestAnimationFrame(() => {
      post({vt:"data", data:{...composition.current, layers:visualLayersRef.current}});
      post({vt:"seek", t:timeRef.current});
    });
    return () => cancelAnimationFrame(id);
  }, [p.visualLayers, ready, post]);

  useEffect(() => {
    if (timeRef.current > dur) seek(dur);
  }, [dur]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    rateRef.current = rate;
    if (audio.current) audio.current.playbackRate = rate;
  }, [rate]);
  useEffect(() => { mutedRef.current = muted; }, [muted]);
  useEffect(() => () => cancelAnimationFrame(raf.current), []);
  // a voice edit replaces the audio file: come back to the same moment
  useEffect(() => {
    const a = audio.current;
    if (!a) return;
    const back = () => {
      a.currentTime = Math.min(timeRef.current, a.duration || timeRef.current);
      a.playbackRate = rateRef.current;
      if (playingRef.current) a.play().catch(() => pause());
    };
    a.addEventListener("loadedmetadata", back, { once: true });
    return () => a.removeEventListener("loadedmetadata", back);
  }, [p.audioUrl]);

  // outline of the selected element on the canvas: ask the page where it is (after the playhead settles)
  const selKey = p.selectedEl ? `${p.selectedEl.scene}:${p.selectedEl.index}` : "";
  useEffect(() => {
    if (!ready || !p.selectedEl) {
      setSelRect(null);
      return;
    }
    const tm = setTimeout(() => post({ vt: "rect", scene: p.selectedEl!.scene, index: p.selectedEl!.index }), 120);
    return () => clearTimeout(tm);
  }, [ready, selKey, p.rev, time, post]); // eslint-disable-line react-hooks/exhaustive-deps

  const sel = p.scenes.find((s) => s.id === p.selected);

  return (
    <div className="preview-stage" ref={host}>
      <div
        className="phone"
        style={{ width: sz.box, height: boxH, cursor: p.onPick ? "crosshair" : p.audioUrl ? "pointer" : "default" }}
        onClick={(e) => {
          if (!p.onPick) return p.audioUrl && (playing ? pause() : play());
          const r = e.currentTarget.getBoundingClientRect();
          post({ vt: "pick", x: (e.clientX - r.left) / scale, y: (e.clientY - r.top) / scale });
        }}
        title={p.onPick ? "Click an element to select it" : "Click to play or pause"}
      >
        <iframe
          ref={frame}
          title="Video preview"
          src={`/media/${p.projectId}/composition/${tag}/index.html?v=${encodeURIComponent(p.reloadKey)}`}
          style={{ width: sz.w, height: sz.h, transform: `scale(${scale})`, pointerEvents: "none" }}
          sandbox="allow-scripts allow-same-origin"
        />
        {selRect && p.selectedEl && <div className="sel-box" style={{ left: selRect[0] * scale - 3, top: selRect[1] * scale - 3, width: selRect[2] * scale + 6, height: selRect[3] * scale + 6 }} aria-hidden />}
        {p.safeArea && p.aspect !== "16:9" && <div className="safe" title="Phone apps cover this area with buttons and captions" />}
      </div>

      {p.showTimeline !== false && (
      <div className="timeline" aria-label="Scenes">
        {p.scenes.map((s) => (
          <button
            key={s.id}
            className={`seg-block ${s.id === p.selected ? "sel" : ""}`}
            style={{ left: `${(s.start / dur) * 100}%`, width: `${((s.end - s.start) / dur) * 100}%` }}
            onClick={() => {
              p.onSelectScene(s.id);
              seek(s.start);
            }}
            title={`${s.id}: ${fmtTime(s.start)}–${fmtTime(s.end)}`}
          >
            {s.id.replace("s", "")}
          </button>
        ))}
        <div className="head" style={{ left: `${(time / dur) * 100}%` }} />
      </div>
      )}

      <div className="scrub">
        <button className="btn icon" onClick={() => (playing ? pause() : play())} aria-label={playing ? "Pause" : "Play"} disabled={!p.audioUrl}>
          {playing ? <Pause size={16} /> : <Play size={16} />}
        </button>
        <input type="range" min={0} max={dur} step={0.01} value={time} onChange={(e) => seek(+e.target.value)} aria-label="Seek" />
        <span className="small muted" style={{ fontVariantNumeric: "tabular-nums", minWidth: 80, textAlign: "right" }}>
          {fmtTime(time)} / {fmtTime(dur)}
        </span>
        <select value={rate} onChange={(e) => setRate(+e.target.value)} aria-label="Speed" style={{ width: 66 }}>
          {[0.5, 0.75, 1, 1.25, 1.5, 2].map((r) => (
            <option key={r} value={r}>
              {r}×
            </option>
          ))}
        </select>
        <button className="btn ghost icon sm" onClick={() => setMuted(!muted)} aria-label="Mute" aria-pressed={muted} style={{ opacity: muted ? 0.4 : 1 }}>
          <Volume2 size={16} />
        </button>
      </div>
      {sel && p.showTimeline !== false && <span className="small muted center" style={{ maxWidth: box + 80 }}>Scene {sel.id.replace("s", "")} · {fmtTime(sel.start)}–{fmtTime(sel.end)} · the preview plays your voice only (music and effects are added on export)</span>}
      <audio ref={audio} src={p.audioUrl || undefined} preload="auto" muted={muted} onEnded={() => setPlaying(false)} />
    </div>
  );
});

export default Preview;
