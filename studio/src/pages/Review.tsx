import { ChevronLeft, Download, Image as ImageIcon, Pause, Play, Redo2, Scissors, Sparkles, Undo2, Wand2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { del, get, post } from "../api";
import { fmtTime } from "../api";
import { DirectorLogButton } from "../log/DirectorLog";
import { Button, MenuItem, MenuSep, Popover, Segmented, Sheet, Splitter, Tabs, Toolbar, ToolbarSep, Tooltip, useSize } from "../ds";
import { useCatalogue, useFetch, useIconPack } from "../hooks";
import { toast, useChanged } from "../store";
import AIPanel from "../review/AIPanel";
import ChatAssistant from "../review/ChatAssistant";
import CommandPalette, { SHORTCUTS, type Command } from "../review/CommandPalette";
import Inspector from "../review/Inspector";
import ModeSwitch from "../review/ModeSwitch";
import MediaBin from "../review/MediaBin";
import Preview, { PlayerHandle } from "../review/Preview";
import RedoModal from "../components/RedoModal";
import Requests from "../review/Requests";
import ScenesPanel from "../review/ScenesPanel";
import ScriptPanel from "../review/ScriptPanel";
import Timeline, { type Sel, type Tool } from "../review/Timeline";
import { timeStore } from "../review/timeStore";
import TranscriptPanel from "../review/TranscriptPanel";
import VideoInspector from "../review/VideoInspector";
import { useReview } from "../review/useReview";
import type { LClip, MediaItem, SoundEvents, UseCase } from "../types";
import LayerInspector from "../review/LayerInspector";
import * as LOps from "../review/layerOps";
import { useLayers } from "../review/useLayers";
import { Modal, Spinner, StatusChip } from "../ui";

type LeftTab = "scenes" | "script" | "words" | "media";

/** The editing window: title bar with menus, browser (scenes, words, media), canvas, context-aware inspector, and a timeline. */
export default function ReviewPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const r = useReview(id);
  const cat = useCatalogue();
  const icons = useIconPack();
  const player = useRef<PlayerHandle>(null);
  const [time, setTime] = useState(0);
  const lastT = useRef(0);
  const [tool, setTool] = useState<Tool>("select");
  const [snap, setSnap] = useState(true);
  const [sel, setSel] = useState<Sel | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [selEl, setSelEl] = useState<{ scene: string; index: number } | null>(null);
  const [videoSel, setVideoSel] = useState(false);
  const soundEvents = useFetch<SoundEvents>(`/api/projects/${id}/sound-events`);
  useChanged(id, () => soundEvents.refetch());
  const [listening, setListening] = useState(false);
  const listen = async () => {
    setListening(true);
    try {
      const j = await post<{ id: string }>(`/api/projects/${id}/sound-events`);
      for (let i = 0; i < 300; i++) {
        await new Promise((res) => setTimeout(res, 1500));
        const st = await get<{ status: string; error?: string }>(`/api/jobs/${j.id}`);
        if (st.status === "error") throw new Error(st.error);
        if (st.status === "done") break;
      }
      await soundEvents.refetch();
      toast("Listened. Press Auto-design to put pictures on the sounds.", "ok", 5000);
    } catch (e: any) {
      toast(e.errors?.[0] || e.message, "err", 6000);
    } finally {
      setListening(false);
    }
  };
  const layers = useLayers(id, r.noteLayers);
  useEffect(() => { r.setLayerHistory({ undo: layers.undo, redo: layers.redo }); return () => r.setLayerHistory(null); }, [layers.undo, layers.redo]); // eslint-disable-line react-hooks/exhaustive-deps
  const [selLayer, setSelLayer] = useState<string | null>(null);
  const mediaList = useFetch<MediaItem[]>(`/api/projects/${id}/media`);
  const soundList = useFetch<MediaItem[]>(`/api/projects/${id}/sounds`);
  useChanged(id, () => { mediaList.refetch(); soundList.refetch(); });
  const mediaMap = useMemo(() => new Map([...(mediaList.data ?? []), ...(soundList.data ?? [])].map((m) => [m.id, m])), [mediaList.data, soundList.data]);
  const clipboard = useRef<LClip | null>(null);                                  // a copied layer clip (Ctrl+C), pasted at the playhead (Ctrl+V)
  const layerClip: LClip | null = selLayer ? layers.doc.clips.find((c) => c.id === selLayer) ?? null : null;
  useEffect(() => { if (selLayer && !layers.doc.clips.some((c) => c.id === selLayer)) setSelLayer(null); }, [layers.doc, selLayer]);
  const layerAudio = useMemo(() => {
    const off = new Set(layers.doc.tracks.filter((t) => t.muted).map((t) => t.id));
    return layers.doc.clips.flatMap((c) => {
      const m = c.media ? mediaMap.get(c.media) : undefined;
      const url = m ? (m.kind === "audio" ? m.url : m.audio_file ? `/media/${id}/${m.audio_file}` : null) : null;
      return url && !off.has(c.track) && (c.volume ?? (c.type === "audio" ? 1 : 0)) > 0 && c.type !== "text"
        ? [{ id: c.id, url, start: c.start, dur: c.dur, in: c.in ?? 0, volume: c.volume ?? 1, fadeIn: c.fade_in, fadeOut: c.fade_out }] : [];
    });
  }, [layers.doc, mediaMap, id]);
  /** Put a picture, clip or sound from the bin on the timeline at the playhead. */
  const addToTimeline = (m: MediaItem) => {
    const total = r.timing.duration || 0;
    const { clip, kind } = LOps.newFromMedia(m, timeStore.t);
    const made = LOps.place(layers.doc, clip as any, kind, total);
    layers.commit(made.doc);
    setSelLayer(made.clip.id);
    setBin(false);
  };
  const [editingId, setEditingId] = useState<string | null>(null);
  const [safe, setSafe] = useState(false);
  const [bin, setBin] = useState(false);
  const [chat, setChat] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [redoOpen, setRedoOpen] = useState(false);
  const [palette, setPalette] = useState(false);
  const [keys, setKeys] = useState(false);
  const [confirmDel, setConfirmDel] = useState(false);
  const [tab, setTab] = useState<LeftTab>(() => { const q = new URLSearchParams(location.search).get("tab"); return q === "words" || q === "script" || q === "media" ? q : "scenes"; });
  const { data: useCases } = useFetch<UseCase[]>("/api/usecases");
  const [playing, setPlaying] = useState(false);
  const [stamp] = useState(() => String(Date.now()));
  const [repaceAsk, setRepaceAsk] = useState<{ pace: string; from: string } | null>(null);
  const [left, setLeft] = useSize("left", 290, 200, 460);
  const [right, setRight] = useSize("right", 350, 280, 560);
  const [tlH, setTlH] = useSize("timeline", 340, 120, 520);

  const p = r.project.data;
  const plan = r.plan;
  const scenes = plan?.scenes ?? [];

  // leave for the progress screen if the pipeline is running
  useEffect(() => {
    if (p && (p.status === "processing" || p.active_job)) nav(`/p/${id}/progress`, { replace: true });
  }, [p?.status, p?.active_job, id, nav]); // eslint-disable-line react-hooks/exhaustive-deps

  // keep the selection valid and follow the playhead
  useEffect(() => {
    if (!scenes.length) return;
    if (!selected || !scenes.some((s) => s.id === selected)) setSelected(scenes[0].id);
  }, [scenes, selected]);
  const timeOf = useMemo(() => new Map(r.timing.scenes.map((s) => [s.id, s])), [r.timing.scenes]);
  useEffect(() => {
    const cur = r.timing.scenes.find((s) => time >= s.start && time < s.end);
    if (cur && cur.id !== selected) {
      setSelected(cur.id);
      setSelEl(null);
    }
  }, [Math.floor(time * 4)]); // eslint-disable-line react-hooks/exhaustive-deps

  const seek = useCallback((t: number) => player.current?.seek(t), []);
  const pickScene = useCallback((sid: string) => {
    setSelected(sid);
    setSelEl(null);
    setVideoSel(false);
  }, []);
  useEffect(() => {
    const on = (e: Event) => pickScene((e as CustomEvent).detail);
    window.addEventListener("vt-select-scene", on);
    return () => window.removeEventListener("vt-select-scene", on);
  }, [pickScene]);

  const idx = scenes.findIndex((s) => s.id === selected);
  const scene = idx >= 0 ? scenes[idx] : null;
  const sceneWords = useMemo(() => {
    if (!scene) return [];
    const ids = new Set(scene.beats.flatMap((b) => r.beats.find((x) => x.id === b)?.word_ids ?? []));
    return r.words.filter((w) => ids.has(w.id));
  }, [scene, r.beats, r.words]);
  const curWord = useMemo(() => {
    let best = null as (typeof r.words)[number] | null;
    for (const w of r.words) {
      if (w.cut) continue;
      if (w.start <= time + 0.01) best = w;
      else break;
    }
    return best;
  }, [r.words, time]);

  const goScene = (d: number) => {
    const n = scenes[Math.max(0, Math.min(scenes.length - 1, idx + d))];
    if (n) {
      pickScene(n.id);
      const t = timeOf.get(n.id);
      if (t) seek(t.start);
    }
  };
  const exportNow = () => nav(`/p/${id}/export`);
  const progress = () => nav(`/p/${id}/progress`);
  const kind = p?.video_kind ?? "explainer";
  const dur = r.timing.duration || p?.duration || 0;

  // keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "c" && layerClip && !(el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA"))) { clipboard.current = layerClip; toast("Copied", "ok", 1200); return; }
      if (mod && e.key.toLowerCase() === "v" && clipboard.current && !(el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA"))) {
        e.preventDefault();
        const src = clipboard.current;
        const kind = layers.doc.tracks.find((t) => t.id === src.track)?.kind ?? (src.type === "audio" ? "audio" : "visual");
        const made = LOps.place(layers.doc, { ...src, id: LOps.uid("c"), start: timeStore.t } as any, kind, r.timing.duration || 0, src.track);
        layers.commit(made.doc);
        setSelLayer(made.clip.id);
        return;
      }
      if (mod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette(true);
        return;
      }
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable)) return;
      if (mod && e.key.toLowerCase() === "z") {
        e.preventDefault();
        e.shiftKey ? r.redo() : r.undo();
      } else if (mod && e.key.toLowerCase() === "y") {
        e.preventDefault();
        r.redo();
      } else if (mod && e.key === "Enter") {
        e.preventDefault();
        exportNow();
      } else if (mod && e.key.toLowerCase() === "b") {
        e.preventDefault();
        const sp = layerClip ? LOps.split(layers.doc, layerClip.id, timeStore.t) : null;
        if (sp) { layers.commit(sp.doc); setSelLayer(sp.ids[1]); } else r.audioEdit("split", { t: timeStore.t });
      } else if (mod || e.altKey) return;
      else if (e.key === "Escape") {
        if (layerClip) { setSelLayer(null); return; }
        if (sel) { setSel(null); return; }
        setSelEl(null);
        setVideoSel(true);
      } else if (e.key === "Delete" || e.key === "Backspace") {
        if (layerClip) { e.preventDefault(); layers.commit(LOps.remove(layers.doc, layerClip.id)); setSelLayer(null); return; }
        if (sel && sel.o1 - sel.o0 > 0.03) { e.preventDefault(); r.audioEdit("cut", { start: sel.o0, end: sel.o1 }); setSel(null); }
      } else if (e.key.toLowerCase() === "m" && sel) {
        const muted = !!r.audio?.mutes.some((q) => q.o0 <= sel.o0 + 0.01 && q.o1 >= sel.o1 - 0.01);
        r.audioEdit("mute", { start: sel.o0, end: sel.o1, on: !muted });
      } else if (e.key.toLowerCase() === "v") setTool("select");
      else if (e.key.toLowerCase() === "b" || e.key.toLowerCase() === "c") setTool("blade");
      else if (e.key.toLowerCase() === "n") setSnap((x) => !x);
      else if (e.key === "\\") window.dispatchEvent(new Event("vt-tl-fit"));
      else if (e.key === " ") {
        e.preventDefault();
        player.current?.toggle();
      } else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        const kept = r.words.filter((w) => !w.cut);
        const i = kept.findIndex((w) => w.id === curWord?.id);
        const n = kept[Math.max(0, Math.min(kept.length - 1, i + (e.key === "ArrowRight" ? 1 : -1)))];
        if (n) seek(n.start);
      } else if (e.key.toLowerCase() === "j") goScene(-1);
      else if (e.key.toLowerCase() === "k") goScene(1);
      else if (e.key.toLowerCase() === "e" && curWord) {
        e.preventDefault();
        setTab("words");
        setEditingId(curWord.id);
      } else if (e.key.toLowerCase() === "h" && curWord && scene) {
        const list = scene.caption.highlight_words;
        r.patchScene(scene.id, { caption: { highlight_words: list.includes(curWord.id) ? list.filter((x) => x !== curWord.id) : [...list, curWord.id].slice(-3) } });
      } else if (e.key.toLowerCase() === "r" && scene) {
        r.askClaude("scene", scene.id, "", 1).then(() => toast(`Asked the AI to redo scene ${idx + 1}`, "ok"));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const sceneIndexById = useMemo(() => Object.fromEntries(scenes.map((s, i) => [s.id, i])), [scenes]);

  const commands: Command[] = useMemo(() => {
    const c: Command[] = [
      { id: "export", title: "Export the video", group: "File", keys: "Ctrl+Enter", run: exportNow },
      { id: "projects", title: "Go to all projects", group: "File", run: () => nav("/") },
      { id: "media", title: "Open the media bin", group: "File", run: () => setBin(true) },
      { id: "undo", title: "Undo", group: "Edit", keys: "Ctrl+Z", run: r.undo, enabled: r.canUndo },
      { id: "redo", title: "Redo", group: "Edit", keys: "Ctrl+Shift+Z", run: r.redo, enabled: r.canRedo },
      { id: "safe", title: safe ? "Hide the phone safe area" : "Show the phone safe area", group: "View", run: () => setSafe((s) => !s) },
      { id: "reset", title: "Reset the panel sizes", group: "View", run: () => { setLeft(-1); setRight(-1); setTlH(-1); } },
      { id: "blade", title: "Timeline: blade tool", group: "Timeline", keys: "B", run: () => setTool("blade") },
      { id: "selecttool", title: "Timeline: select tool", group: "Timeline", keys: "V", run: () => setTool("select") },
      { id: "snap", title: snap ? "Timeline: turn snapping off" : "Timeline: turn snapping on", group: "Timeline", keys: "N", run: () => setSnap((x) => !x) },
      { id: "splitv", title: "Voice: split at the playhead", group: "Timeline", keys: "Ctrl+B", run: () => r.audioEdit("split", { t: timeStore.t }) },
      { id: "cutv", title: "Voice: cut out the selection", group: "Timeline", keys: "Delete", run: () => sel && r.audioEdit("cut", { start: sel.o0, end: sel.o1 }).then(() => setSel(null)), enabled: !!sel },
      { id: "fit", title: "Timeline: fit the whole video", group: "Timeline", keys: "\\", run: () => window.dispatchEvent(new Event("vt-tl-fit")) },
      { id: "play", title: playing ? "Pause" : "Play", group: "Playback", keys: "Space", run: () => player.current?.toggle() },
      { id: "next", title: "Next scene", group: "Playback", keys: "K", run: () => goScene(1) },
      { id: "prev", title: "Previous scene", group: "Playback", keys: "J", run: () => goScene(-1) },
      { id: "redo_ai", title: "AI: redo video with new AI model…", group: "AI", run: () => setRedoOpen(true) },
      { id: "again", title: "AI: direct the whole video again", group: "AI", run: () => post(`/api/projects/${id}/script/generate?kind=${kind}`).then(progress).catch((e: any) => toast(e.message, "err")) },
        { id: "assistant", title: "AI: plan with Codex or Claude (MCP)", group: "AI", run: () => r.askClaude("full", null, "", 1).then((x) => x && toast("Request queued for your assistant", "ok")) },
      { id: "chat", title: "AI: ask a chat assistant", group: "AI", run: () => setChat(true) },
      { id: "qa", title: "AI: check the frames", group: "AI", run: () => post(`/api/projects/${id}/qa`).then(progress).catch((e: any) => toast(e.message, "err")) },
      { id: "auto", title: "AI: auto-design every scene", group: "AI", run: () => r.replanAuto().then(progress).catch((e: any) => toast(e.message, "err")) },
      { id: "stick", title: "Make it a stick-figure video", group: "Style", run: () => post(`/api/projects/${id}/script/generate?kind=stick`).then(progress).catch((e: any) => toast(e.message, "err")), enabled: kind !== "stick" },
      { id: "pics", title: "Make it a pictures and graphics video", group: "Style", run: () => post(`/api/projects/${id}/script/generate?kind=explainer`).then(progress).catch((e: any) => toast(e.message, "err")), enabled: kind !== "explainer" },
      { id: "emoji", title: "Make it an emoji video", group: "Style", run: () => post(`/api/projects/${id}/script/generate?kind=emoji`).then(progress).catch((e: any) => toast(e.message, "err")), enabled: kind !== "emoji" },
      { id: "keys", title: "Show keyboard shortcuts", group: "Help", run: () => setKeys(true) },
    ];
    if (scene) {
      c.push({ id: "merge", title: "Merge this scene with the next", group: "Scene", run: () => r.mergeNext(scene.id), enabled: idx < scenes.length - 1 });
      c.push({ id: "delete", title: "Delete this scene", group: "Scene", run: () => setConfirmDel(true), enabled: scenes.length > 1 });
    }
    scenes.forEach((s, i) => c.push({ id: `go-${s.id}`, title: `Go to scene ${i + 1}`, group: "Go to", run: () => { pickScene(s.id); const t = timeOf.get(s.id); if (t) seek(t.start); } }));
    return c;
  }, [r.canUndo, r.canRedo, safe, playing, scene, scenes, idx, kind, id, snap, sel]); // eslint-disable-line react-hooks/exhaustive-deps

  // the timeline is the heaviest part of the page: it is rebuilt when what it shows changes, not on every tick of the clock while playing
  // (its playhead follows timeStore by itself; measured with e2e/perf_timeline.mjs)
  const timeline = useMemo(() => (
    <Timeline r={r} duration={dur} seek={seek} selected={selected} onSelect={(sid) => { setSelLayer(null); pickScene(sid); }} selectedEl={selEl} onSelectEl={(sc, i) => { setSelected(sc); setVideoSel(false); setSelEl({ scene: sc, index: i }); }}
      tool={tool} setTool={setTool} snap={snap} setSnap={setSnap} sel={sel} setSel={setSel}
      layers={layers} media={mediaMap} selLayer={selLayer} onSelectLayer={setSelLayer} onAddMedia={() => setBin(true)} sounds={soundEvents.data} onListen={listen} listening={listening} />
  ), [r.rev, r.plan, r.timing, r.words, r.wordById, r.audio, r.audioRev, r.canUndo, r.canRedo, dur, seek, pickScene, selected, selEl, tool, snap, sel, layers, mediaMap, selLayer, soundEvents.data, listening]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (r.project.error) return <div className="page-inner"><div className="banner err">Could not open this video: {r.project.error}. <Link to="/">Back to projects</Link></div></div>;
  if (!p || r.sc.loading) return <div className="page-inner"><div className="row muted"><Spinner /> Loading…</div></div>;
  if (!plan)
    return (
      <div className="page-inner">
        <div className="banner warn">This video has no plan yet. <button className="btn sm" onClick={() => post(`/api/projects/${id}/run`, {}).then(progress)}>Process the audio</button></div>
      </div>
    );

  return (
    <div className="ed">
      <h1 className="sr-only">{p.title}</h1>
      <header className="ed-title">
        <Tooltip text="All projects"><Link to="/" className="btn ghost icon sm" aria-label="All projects"><ChevronLeft size={18} /></Link></Tooltip>
        <input type="text" className="name bn" defaultValue={p.title} key={p.title} aria-label="Title" onBlur={(e) => e.target.value.trim() && e.target.value !== p.title && r.patchProject({ title: e.target.value })} />
        <StatusChip status={p.status} />
        <ModeSwitch r={r} />
        <DirectorLogButton pid={p.id} />
        <Toolbar label="Menus">
          <Popover label="File" trigger="File">
            <MenuItem onClick={exportNow} keys="Ctrl+Enter">Export…</MenuItem>
            <MenuItem onClick={() => setRedoOpen(true)}>Redo with AI model…</MenuItem>
            <MenuItem onClick={() => setBin(true)}>Media bin…</MenuItem>
            <MenuSep />
            <MenuItem onClick={() => nav("/")}>All projects</MenuItem>
          </Popover>
          <Popover label="Edit" trigger="Edit">
            <MenuItem onClick={r.undo} disabled={!r.canUndo} keys="Ctrl+Z">Undo</MenuItem>
            <MenuItem onClick={r.redo} disabled={!r.canRedo} keys="Ctrl+Shift+Z">Redo</MenuItem>
          </Popover>
          <Popover label="View" trigger="View">
            <MenuItem onClick={() => setSafe(!safe)} checked={safe}>Phone safe area</MenuItem>
            <MenuItem onClick={() => { setLeft(-1); setRight(-1); setTlH(-1); }}>Reset panel sizes</MenuItem>
          </Popover>
          <Popover label="Scene" trigger="Scene">
            <MenuItem onClick={() => goScene(-1)} keys="J" disabled={idx <= 0}>Previous scene</MenuItem>
            <MenuItem onClick={() => goScene(1)} keys="K" disabled={idx >= scenes.length - 1}>Next scene</MenuItem>
            <MenuSep />
            <MenuItem onClick={() => scene && r.mergeNext(scene.id)} disabled={!scene || idx >= scenes.length - 1}>Merge with the next scene</MenuItem>
            <MenuItem onClick={() => setConfirmDel(true)} disabled={!scene || scenes.length < 2}>Delete this scene…</MenuItem>
            <MenuSep />
            <MenuItem onClick={() => scene && r.askClaude("scene", scene.id, "", 1).then(() => toast("Request queued", "ok"))} keys="R" disabled={!scene}>Ask the AI to redo it</MenuItem>
          </Popover>
          <Popover label="Help" trigger="Help">
            <MenuItem onClick={() => setPalette(true)} keys="Ctrl+K">Command palette</MenuItem>
            <MenuItem onClick={() => setKeys(true)}>Keyboard shortcuts</MenuItem>
          </Popover>
        </Toolbar>
        <span className="spacer" />
        <Toolbar label="Playback">
          <Tooltip text={playing ? "Pause" : "Play"} keys="Space">
            <Button icon variant="ghost" size="sm" aria-label={playing ? "Pause" : "Play"} onClick={() => player.current?.toggle()} disabled={!p.audio_url}>{playing ? <Pause size={16} /> : <Play size={16} />}</Button>
          </Tooltip>
          <span className="ed-time" aria-label="Time">{fmtTime(time)} / {fmtTime(dur)}</span>
        </Toolbar>
        <ToolbarSep />
        <Segmented value={p.aspect} onChange={(a) => r.patchProject({ aspect: a })} options={[{ value: "9:16", label: "9:16" }, { value: "1:1", label: "1:1" }, { value: "16:9", label: "16:9" }]} label="Preview shape" />
        <Tooltip text="Undo" keys="Ctrl+Z"><Button icon variant="ghost" size="sm" onClick={r.undo} disabled={!r.canUndo} aria-label="Undo"><Undo2 size={16} /></Button></Tooltip>
        <Tooltip text="Redo" keys="Ctrl+Shift+Z"><Button icon variant="ghost" size="sm" onClick={r.redo} disabled={!r.canRedo} aria-label="Redo"><Redo2 size={16} /></Button></Tooltip>
        <Button size="sm" onClick={() => setRedoOpen(true)} aria-label="Redo with AI model"><Wand2 size={14} /> Redo video</Button>
        <Button size="sm" onClick={() => nav(`/p/${id}/shorts`)} aria-label="Extract shorts" title="Find viral scenes and create 9:16 shorts"><Scissors size={14} /> Extract shorts</Button>
        <Button size="sm" onClick={() => setAiOpen(true)} aria-label="AI"><Sparkles size={15} /> AI</Button>
        <Button size="sm" variant="primary" onClick={exportNow}><Download size={15} /> Export</Button>
      </header>

      {p.plan_notice && (
        <div className="banner warn" style={{ margin: "8px 12px 0" }}>
          <div className="grow"><strong>Your scene plan was replaced</strong><div className="small muted">{p.plan_notice.message}</div></div>
          <button className="btn sm" onClick={() => del(`/api/projects/${id}/plan-notice`).then(r.reloadAll)}>Got it</button>
        </div>
      )}
      {p.ai_notice && (
        <div className="banner warn" style={{ margin: "8px 12px 0" }}>
          <div className="grow"><strong>The built-in rules directed this video</strong><div className="small muted">{p.ai_notice.message} Set up an AI in Settings, then use AI → Direct the whole video again.</div></div>
          <Link className="btn sm" to="/settings">Settings</Link>
        </div>
      )}
      <Requests r={r} sceneIndexById={sceneIndexById} />

      <div className="ed-body">
        <div className="ed-cols">
          <aside className="ed-left" style={{ width: left }} aria-label="Browser">
            <Tabs<LeftTab> label="Browser" value={tab} onChange={setTab} tabs={[{ value: "scenes", label: "Scenes", badge: scenes.length }, { value: "script", label: "Script" }, { value: "words", label: "Words" }, { value: "media", label: "Media", badge: p.media?.length || 0 }]} />
            <div className={`scroll ${tab === "words" || tab === "script" ? "fill" : ""}`}>
              {tab === "scenes" && <ScenesPanel r={r} selected={selected} onSelect={pickScene} seek={seek} />}
              {tab === "script" && <ScriptPanel r={r} time={time} playing={playing} seek={seek} />}
              {tab === "words" && <TranscriptPanel r={r} time={time} playing={playing} seek={seek} selected={selected} onSelectScene={pickScene} editingId={editingId} setEditingId={setEditingId} />}
              {tab === "media" && (
                <div className="col" style={{ padding: 14 }}>
                  <p className="small muted" style={{ margin: 0 }}>Your pictures, GIFs and clips ({p.media?.length ?? 0}). The planner places them; “Show as” lets you choose how.</p>
                  <Button onClick={() => setBin(true)}><ImageIcon size={15} /> Open the media bin</Button>
                </div>
              )}
            </div>
          </aside>
          <Splitter dir="x" size={left} onSize={setLeft} label="Resize the browser" />

          <section className="ed-canvas" aria-label="Canvas">
            <Preview
              ref={player}
              projectId={id}
              aspect={p.aspect}
              audioUrl={p.audio_url ? `${p.audio_url}${p.audio_url.includes("?") ? "&" : "?"}v=${r.audioRev}` : null}
              duration={dur}
              scenes={r.timing.scenes}
              selected={selected}
              onSelectScene={pickScene}
              onTime={(t) => {
                timeStore.set(t);                                    // the timeline's playhead follows at full speed, without re-rendering this page
                if (Math.abs(t - lastT.current) >= 0.07 || t === 0) { lastT.current = t; setTime(t); }
              }}
              onPlaying={(pl) => { timeStore.playing = pl; setPlaying(pl); }}
              rev={r.rev}
              reloadKey={`${stamp}-${p.theme}`}
              safeArea={safe}
              showTimeline={false}
              layerAudio={layerAudio}
              selectedEl={selEl}
              onPick={(sc, index) => {
                if (sc) {
                  setSelected(sc);
                  setVideoSel(false);
                  setSelEl(index != null ? { scene: sc, index } : null);
                }
              }}
            />
          </section>

          <Splitter dir="x" size={right} onSize={setRight} invert label="Resize the inspector" />
          <aside className="ed-right" style={{ width: right }} aria-label="Inspector">
            {layerClip ? (
              <LayerInspector key={layerClip.id} layers={layers} clip={layerClip} media={mediaMap} total={dur} onSelect={setSelLayer} seek={seek} time={time} />
            ) : videoSel || !scene ? (
              <VideoInspector r={r} p={p} useCases={useCases ?? []} onRedirect={progress} onRepace={(pace, from) => setRepaceAsk({ pace, from })} />
            ) : (
              <Inspector key={scene.id} r={r} scene={scene} index={idx} time={timeOf.get(scene.id)} words={sceneWords} playheadWord={curWord?.id ?? null} cat={cat} icons={icons} focusEl={selEl && selEl.scene === scene.id ? selEl.index : null} />
            )}
          </aside>
        </div>

        <Splitter dir="y" size={tlH} onSize={setTlH} invert label="Resize the timeline" />
        <section className="ed-timeline" style={{ height: tlH }} aria-label="Timeline panel">
          {timeline}
        </section>
      </div>

      {chat && <ChatAssistant id={id} kind={kind} onClose={() => setChat(false)} onApplied={r.reloadAll} />}
      {bin && <MediaBin id={id} onClose={() => setBin(false)} onChange={() => { r.reloadAll(); mediaList.refetch(); soundList.refetch(); }} onAddToTimeline={addToTimeline} />}
      {aiOpen && <AIPanel r={r} id={id} scene={scene} kind={kind} onClose={() => setAiOpen(false)} onChat={() => setChat(true)} goProgress={progress} />}
      {palette && <CommandPalette commands={commands} onClose={() => setPalette(false)} />}
      {redoOpen && p && <RedoModal id={id} title={p.title} open={redoOpen} onClose={() => setRedoOpen(false)} />}
      {keys && (
        <Sheet title="Keyboard shortcuts" onClose={() => setKeys(false)}>
          <table className="table"><tbody>{SHORTCUTS.map(([k, d]) => <tr key={k}><td style={{ width: 170 }}><span className="kbd">{k}</span></td><td>{d}</td></tr>)}</tbody></table>
        </Sheet>
      )}
      {confirmDel && scene && (
        <Modal title="Delete this scene?" onClose={() => setConfirmDel(false)} footer={<><button className="btn" onClick={() => setConfirmDel(false)}>Cancel</button><button className="btn danger" onClick={() => { r.removeScene(scene.id); setConfirmDel(false); }}>Delete</button></>}>
          <p style={{ margin: 0 }}>Its sentences are given to the neighbouring scene. You can undo this.</p>
        </Modal>
      )}
      {repaceAsk && (
        <Modal
          title="Re-cut with the new pace?"
          onClose={() => setRepaceAsk(null)}
          footer={
            <>
              <button className="btn" onClick={() => setRepaceAsk(null)}>Not now</button>
              <button className="btn primary" onClick={async () => { await post(`/api/projects/${id}/run`, { from_stage: repaceAsk.from }); nav(`/p/${id}/progress`); }}>Re-cut now</button>
            </>
          }
        >
          <p style={{ margin: 0 }}>Changing the pace changes where silences are cut, so timings move. Your word fixes and scene edits are kept where they still fit.</p>
        </Modal>
      )}
    </div>
  );
}
