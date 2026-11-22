import VideoTools from "../review/VideoTools";
import CaptionInspector from "../review/CaptionInspector";
import { MessageSquareText, ChevronLeft, Download, Image as ImageIcon, Pause, Play, Redo2, Scissors, Sparkles, Undo2, Wand2, Menu, PanelLeftClose, PanelRightClose, Maximize2, MessageSquare, PanelBottomClose, X } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { del, get, post } from "../api";
import { fmtTime } from "../api";
import { DirectorLogButton } from "../log/DirectorLog";
import { Button, MenuItem, MenuSep, Popover, Sheet, Splitter, Tooltip, useSize } from "../ds";
import Workbench from "../workbench/Workbench";
import { paneAction } from "../workbench/shortcuts";
import { useCatalogue, useFetch, useIconPack } from "../hooks";
import { onChangeDetail, toast, useChanged } from "../store";
import AIPanel from "../review/AIPanel";
import ChatAssistant from "../review/ChatAssistant";
import CommandPalette, { SHORTCUTS, type Command } from "../review/CommandPalette";
import Inspector, { type InspectorHandle } from "../review/Inspector";
import ComponentLibrary from "../review/ComponentLibrary";
import ModeSwitch from "../review/ModeSwitch";
import MediaBin from "../review/MediaBin";
import Preview, { PlayerHandle } from "../review/Preview";
import RedoModal from "../components/RedoModal";
import Requests from "../review/Requests";
import ScenesPanel from "../review/ScenesPanel";
import ScriptPanel from "../review/ScriptPanel";
import DirectionPanel from "../review/DirectionPanel";
import Timeline, { type Sel, type Tool } from "../review/Timeline";
import { timeStore } from "../review/timeStore";
// OpenChatCut's timeline, ported into ours (docs/plans/PLAN-OPENCHATCUT.MD); loaded only when switched on
const OccTimeline = lazy(() => import("../occ/bridge/OccTimeline"));
const DirectorChat = lazy(() => import("../occ/bridge/DirectorChat"));
const ELEMENT_NAME: Record<string, string> = { value_card: "Value card", big_number: "Number", icon_row: "Icons", bar_chart: "Bar chart", media_frame: "Picture or video", speaker_card: "Speaker", cartoon: "Cartoon", story: "Story cartoon" };
const CANVAS: Record<string, { width: number; height: number }> = { "9:16": { width: 1080, height: 1920 }, "16:9": { width: 1920, height: 1080 }, "1:1": { width: 1080, height: 1080 } };
import CaptionLook from "../review/CaptionLook";
import TranscriptPanel from "../review/TranscriptPanel";
import VideoInspector from "../review/VideoInspector";
import { useReview, type DirectorState } from "../review/useReview";
import type { LClip, MediaItem, SoundEvents, UseCase } from "../types";
import LayerInspector from "../review/LayerInspector";
import * as LOps from "../review/layerOps";
import { useLayers } from "../review/useLayers";
import { Modal, Spinner, StatusChip } from "../ui";
import PictureTools from "../editor/PictureTools";
import SoundPanel from "../editor/SoundPanel";
import HookCard from "../editor/HookCard";
const ShotEditor = lazy(() => import("../review/ShotEditor"));
const AgentChat = lazy(() => import("../assistant/AgentChat"));

type LeftTab = "chat" | "scenes" | "elements" | "direction" | "script" | "words" | "media" | "sound";

/** The editing window: title bar with menus, browser (scenes, words, media), canvas, context-aware inspector, and a timeline. */
export default function ReviewPage() {
  const { id = "" } = useParams();
  return <ReviewEditor key={id} />;
}

function ReviewEditor() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const r = useReview(id);
  const cat = useCatalogue();
  const icons = useIconPack();
  const player = useRef<PlayerHandle>(null);
  const [time, setTime] = useState(0);
  const [assistantTab, setAssistantTab] = useState<"director" | "claude">("director");   // which conversation the Assistant pane shows
  const assistantTabRef = useRef(assistantTab);
  assistantTabRef.current = assistantTab;
  const [shotEdit, setShotEdit] = useState<string | null>(null);   // a code-native shot open in the visual editor (PLAN-CODE-NATIVE-EDITOR C3)
  const lastT = useRef(0);
  const [tool, setTool] = useState<Tool>("select");
  const [snap, setSnap] = useState(true);
  const [showBrowser, showBrowserState] = useState(() => window.innerWidth >= 800);
  const [showInspector, showInspectorState] = useState(() => window.innerWidth >= 1250);
  const [compact, setCompact] = useState(() => window.innerWidth < 1250);
  const inspector = useRef<InspectorHandle>(null);
  const setShowBrowser = useCallback((show: boolean) => {
    showBrowserState(show);
    if (show && window.innerWidth < 1250) showInspectorState(false);
  }, []);
  const setShowInspector = useCallback((show: boolean) => {
    showInspectorState(show);
    if (show && window.innerWidth < 1250) showBrowserState(false);
  }, []);
  useEffect(() => {
    const resize = () => {
      setCompact(window.innerWidth < 1250);
      if (window.innerWidth < 800) { showBrowserState(false); showInspectorState(false); }
      else if (window.innerWidth < 1250) showInspectorState(false);
    };
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  const [sel, setSel] = useState<Sel | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [selEl, setSelEl] = useState<{ scene: string; index: number } | null>(null);
  const askRef = useRef<() => Record<string, unknown> | null>(() => null);
  const [selAction,setSelAction]=useState<{scene:string;index:number}|null>(null);
  const [selectedWord,setSelectedWord]=useState<string|null>(null);
  const captionWord=r.words.find(w=>w.id===selectedWord);
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
  const [extracting,setExtracting]=useState(false);
  const [selLayer, setSelLayer] = useState<string | null>(null);
  const mediaList = useFetch<MediaItem[]>(`/api/projects/${id}/media`);
  const soundList = useFetch<MediaItem[]>(`/api/projects/${id}/sounds`);
  useChanged(id, () => { mediaList.refetch(); soundList.refetch(); });
  const mediaMap = useMemo(() => new Map([...(mediaList.data ?? []), ...(soundList.data ?? [])].map((m) => [m.id, m])), [mediaList.data, soundList.data]);
  const clipboard = useRef<LClip | null>(null);                                  // a copied layer clip (Ctrl+C), pasted at the playhead (Ctrl+V)
  const layerClip: LClip | null = selLayer ? layers.doc.clips.find((c) => c.id === selLayer) ?? null : null;
  useEffect(() => { if (selLayer && !layers.doc.clips.some((c) => c.id === selLayer)) setSelLayer(null); }, [layers.doc, selLayer]);
  const layerAudio = useMemo(() => {
    const off = new Set(layers.doc.tracks.filter((t) => t.muted || (t.hidden && t.kind === "visual")).map((t) => t.id));
    return layers.doc.clips.flatMap((c) => {
      const m = c.media ? mediaMap.get(c.media) : undefined;
      const url = m ? (m.kind === "audio" ? m.url : m.audio_file ? `/media/${id}/${m.audio_file}` : null) : null;
      return url && !off.has(c.track) && (c.volume ?? (c.type === "audio" ? 1 : 0)) > 0 && c.type !== "text"
        ? [{ id: c.id, url, start: c.start, dur: c.dur, in: c.in ?? 0, volume: c.volume ?? 1, fadeIn: c.fade_in, fadeOut: c.fade_out }] : [];
    });
  }, [layers.doc, mediaMap, id]);
  const visualLayers = useMemo(() => layers.doc.clips.filter(c => c.type !== "audio" && !layers.doc.tracks.find(t => t.id === c.track)?.hidden)
    .sort((a,b) => layers.doc.tracks.findIndex(t => t.id === b.track) - layers.doc.tracks.findIndex(t => t.id === a.track) || a.start - b.start)
    .map(c => ({...c, end:c.start+c.dur})), [layers.doc]);
  /** Put a picture, clip or sound from the bin on the timeline at the playhead. */
  const addToTimeline = (m: MediaItem) => {
    const total = r.timing.duration || 0;
    const { clip, kind } = LOps.newFromMedia(m, timeStore.t);
    const made = LOps.place(layers.doc, clip as any, kind, total);
    layers.commit(made.doc);
    setSelectedWord(null); setSel(null); setVideoSel(false);
    setSelLayer(made.clip.id);
    setShowInspector(true);
    setBin(false);
  };
  const [editingId, setEditingId] = useState<string | null>(null);
  const [safe, setSafe] = useState(false);
  const [bin, setBin] = useState(false);
  const [chat, setChat] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [redoOpen, setRedoOpen] = useState(false);
  const [palette, setPalette] = useState(false);
  const [keys, setKeys] = useState(false);
  const [confirmDel, setConfirmDel] = useState(false);
  const [tab, setTab] = useState<LeftTab>(() => { const q = new URLSearchParams(location.search).get("tab"); return q === "words" || q === "script" || q === "media" ? q : "scenes"; });
  const [directorMounted, setDirectorMounted] = useState(true);          // the assistant pane keeps the director conversation and its job poll alive
  const [showAssistant, setShowAssistant] = useState(() => window.innerWidth >= 1180);
  const [showTimeline, setShowTimeline] = useState(true);
  const { data: useCases } = useFetch<UseCase[]>("/api/usecases");
  const [playing, setPlaying] = useState(false);
  const [directorRunning, setDirectorRunning] = useState(false);
  const [directorChangedScenes, setDirectorChangedScenes] = useState<string[]>([]);
  useEffect(() => onChangeDetail((d) => { if (d.project === id && d.by.startsWith("mcp:") && d.scenes.length) setDirectorChangedScenes(d.scenes); }), [id]);
  const [agentTouched, setAgentTouched] = useState<{ scene: string; who: string } | null>(null);     // W14.4: the agent changed what the person has open
  const selectedRef = useRef<string | null>(null);
  useEffect(() => { selectedRef.current = selected; setAgentTouched((a) => (a && a.scene !== selected ? null : a)); }, [selected]);
  useEffect(() => onChangeDetail((d) => {
    const s = selectedRef.current;
    if (d.project === id && d.by.startsWith("mcp:") && s && d.scenes.includes(s)) setAgentTouched({ scene: s, who: d.by === "mcp:claude" ? "Claude" : d.by === "mcp:codex" ? "Codex" : "The assistant" });
  }), [id]);
  useEffect(() => {                                    // the Classic timeline and the scene list glow too (the new timeline does it itself)
    if (!directorChangedScenes.length) return;
    const els = directorChangedScenes.flatMap((s) => [...document.querySelectorAll<HTMLElement>(`[data-scene-clip="${CSS.escape(s)}"], [data-scene="${CSS.escape(s)}"]`)]);
    els.forEach((e) => e.classList.add("vt-changed"));
    const t = window.setTimeout(() => els.forEach((e) => e.classList.remove("vt-changed")), 7000);
    return () => { window.clearTimeout(t); els.forEach((e) => e.classList.remove("vt-changed")); };
  }, [directorChangedScenes, r.rev]);   // W14.2: an agent's change glows like the Director's
  const [directorRemovedScenes, setDirectorRemovedScenes] = useState<string[]>([]);
  const [newTimeline, setNewTimeline] = useState(() => { try { return localStorage.getItem("vt-timeline") === "new"; } catch { return false; } });
  // edits made on the new timeline, as our own edit calls (src/occ/bridge/toProject.ts); one after the other, then the page reloads
  const saveTimeline = async (ops: import("../occ/bridge/toProject").SaveOp[]) => {
    for (const op of ops) {
      const ok = op.kind === "layers" ? await layers.saveNow(op.doc)
        : op.kind === "element" ? await r.patchElement(op.scene, op.index, op.body)
        : op.kind === "scene-edge" ? await r.moveEdge(op.scene, op.t)
        : op.kind === "scene-split" ? await r.splitAt(op.scene, op.t)
        : op.kind === "scene-remove" ? await r.removeScene(op.scene)
        : await r.audioEdit("cut", { start: op.start, end: op.end });
      if (ok === null || ok === false) { await r.reloadAll(); throw new Error("the server did not accept the change; the timeline shows what is saved"); }
    }
    await r.reloadAll();
  };
  const chooseTimeline = (next: boolean) => { setNewTimeline(next); try { localStorage.setItem("vt-timeline", next ? "new" : "classic"); } catch { /* not kept */ } };
  const [stamp] = useState(() => String(Date.now()));
  const [repaceAsk, setRepaceAsk] = useState<{ pace: string; from: string } | null>(null);
  const [left, setLeft] = useSize("left", 290, 200, 460);
  const [right, setRight] = useSize("right", 350, 280, 560);
  const [tlH, setTlH] = useSize("timeline", 260, 180, 520);
  useEffect(() => { timeStore.set(0); timeStore.playing = false; }, []);

  const p = r.project.data;
  const plan = r.plan;
  const scenes = plan?.scenes ?? [];

  // leave for the progress screen if the pipeline is running
  useEffect(() => {
    if (p && (p.status === "processing" || (p.active_job && p.active_job.kind !== "export"))) nav(`/p/${id}/progress`, { replace: true });   // a download rendering in the background does not take the editor away
  }, [p?.status, p?.active_job, id, nav]); // eslint-disable-line react-hooks/exhaustive-deps

  // keep the selection valid and follow the playhead
  useEffect(() => {
    if (!scenes.length) return;
    if (!selected || !scenes.some((s) => s.id === selected)) setSelected(scenes[0].id);
  }, [scenes, selected]);
  const timeOf = useMemo(() => new Map(r.timing.scenes.map((s) => [s.id, s])), [r.timing.scenes]);
  askRef.current = () => {                                   // what Ctrl+L points at: the selected element, else the selected scene
    const sid = selEl?.scene ?? selected;
    if (!sid) return null;
    const t = timeOf.get(sid) as { start?: number; end?: number } | undefined;
    const span = t && t.start != null && t.end != null ? { from: +t.start.toFixed(2), to: +t.end.toFixed(2) } : {};
    const n = (r.plan?.scenes ?? []).findIndex((s) => s.id === sid) + 1;
    if (selEl) {
      const el = (r.plan?.scenes ?? []).find((s) => s.id === sid)?.elements?.[selEl.index] as { type?: string; text?: string } | undefined;
      return { kind: "element", scene: sid, index: selEl.index, ...span, label: `${el?.text || ELEMENT_NAME[el?.type ?? ""] || el?.type || "element"} in scene ${n}`.slice(0, 120) };
    }
    return { kind: "scene", scene: sid, ...span, label: `Scene ${n}` };
  };
  useEffect(() => {
    const cur = r.timing.scenes.find((s) => time >= s.start && time < s.end);
    if (playing && !selEl && !selLayer && !selAction && !videoSel && cur && cur.id !== selected) {
      setSelected(cur.id);
      setSelEl(null);
    }
  }, [Math.floor(time * 4)]); // eslint-disable-line react-hooks/exhaustive-deps

  const seek = useCallback((t: number) => player.current?.seek(t), []);
  const pickScene = useCallback((sid: string) => {
    setSelectedWord(null);
    setSel(null);
    setSelLayer(null);
    setSelected(sid);
    setSelEl(null);
    setSelAction(null);
    setVideoSel(false);
  }, []);
  useEffect(() => {
    const on = (e: Event) => pickScene((e as CustomEvent).detail);
    window.addEventListener("vt-select-scene", on);
    return () => window.removeEventListener("vt-select-scene", on);
  }, [pickScene]);

  useEffect(()=>{
    const on=(event:Event)=>{const a=(event as CustomEvent).detail;pickScene(a.scene);setSelAction(a);setShowInspector(true);};
    window.addEventListener("vt-action-select",on);return()=>window.removeEventListener("vt-action-select",on);
  },[pickScene,setShowInspector]);
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
  useEffect(() => { setSel(null); }, [JSON.stringify(r.audio?.keep)]);
  useEffect(() => {
    if (r.audioSaving && player.current?.isPlaying()) player.current.toggle();
  }, [r.audioSaving]);
  const selectLayer = (clipId: string | null) => {
    setSelectedWord(null);
    setSelLayer(clipId); setSel(null); setSelEl(null); setVideoSel(false);
    if (clipId) setShowInspector(true);
  };
  const selectVoice = (range: Sel | null) => {
    setSelectedWord(null);
    setSel(range); setSelLayer(null); setSelEl(null); setVideoSel(false); if(range) setShowInspector(true);
  };

  // keyboard shortcuts
  useEffect(() => {
    // the panes' own keys work everywhere in the editor, also while the director works or the new timeline has the keyboard
    const onPaneKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (e.defaultPrevented || el?.closest('[role="dialog"], [role="menu"]')) return;
      const typing = !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
      const act = paneAction(e, typing);
      if (!act) return;
      e.preventDefault();
      if (act === "library") setShowBrowser(!showBrowser);
      else if (act === "inspector") setShowInspector(!showInspector);
      else if (act === "timeline") setShowTimeline(!showTimeline);
      else if (act === "assistant") setShowAssistant(!showAssistant);
      else if (act === "palette") setPalette(true);
      else if (act === "focus-assistant") {
        setShowAssistant(true);
        const ref = askRef.current();                                  // W13.3: Ctrl+L with something selected points Claude Code at it
        if (ref) {                                                     // Claude Code in the desktop app, else the Director
          const claude = !!(window as any).vtDesktop?.agents && assistantTabRef.current !== "director";
          if (claude) setAssistantTab("claude");
          setTimeout(() => window.dispatchEvent(new CustomEvent(claude ? "vt-ask-about" : "vt-ask-director", { detail: ref })), 250);
        }
        setTimeout(() => document.querySelector<HTMLTextAreaElement>(".wb-assistant textarea")?.focus(), 60);
      }
    };
    window.addEventListener("keydown", onPaneKey);
    return () => window.removeEventListener("keydown", onPaneKey);
  }, [showBrowser, showInspector, showTimeline, showAssistant]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (directorRunning) return;                              // the gradient shield owns the timeline until the Director commits or fails
      if (newTimeline) return;                                // the new timeline has its own shortcuts (src/occ/src/shortcuts); one owner per key
      const el = e.target as HTMLElement;
      if (e.defaultPrevented || el?.closest('[role="dialog"], [role="menu"]')) return;
      const mod = e.ctrlKey || e.metaKey;
      const typing = el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
      if (mod && e.key.toLowerCase() === "c" && layerClip && !typing) { clipboard.current = layerClip; toast("Copied", "ok", 1200); return; }
      if (mod && e.key.toLowerCase() === "v" && clipboard.current && !typing) {
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
      if (typing) return;
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
        if(selEl) {r.patchElement(selEl.scene,selEl.index,{split:timeStore.t});return;}
        const sp = layerClip ? LOps.split(layers.doc, layerClip.id, timeStore.t) : null;
        if (layerClip) { if (sp) { layers.commit(sp.doc); selectLayer(sp.ids[1]); } }
        else r.audioEdit("split", { t: timeStore.t });
      } else if (mod || e.altKey) return;
      else if (e.key === "Escape") {
        if (layerClip) { setSelLayer(null); return; }
        if (sel) { setSel(null); return; }
        setSelEl(null);
        setVideoSel(true);
      } else if (e.key === "Delete" || e.key === "Backspace") {
        if(selEl) {e.preventDefault();r.patchElement(selEl.scene,selEl.index,{delete:true});setSelEl(null);return;}
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
        setShowBrowser(true);
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
      { id: "video-tools", title: "Browse all video tools", group: "Tools", run: () => setToolsOpen(true) },
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
      { id: "splitv", title: "Voice: split at the playhead", group: "Timeline", run: () => r.audioEdit("split", { t: timeStore.t }), enabled: !r.audioSaving },
      { id: "cutv", title: "Voice: cut out the selection", group: "Timeline", keys: "Delete", run: () => sel && r.audioEdit("cut", { start: sel.o0, end: sel.o1 }).then(() => setSel(null)), enabled: !!sel },
      { id: "fit", title: "Timeline: fit the whole video", group: "Timeline", keys: "\\", run: () => window.dispatchEvent(new Event("vt-tl-fit")) },
      { id: "play", title: playing ? "Pause" : "Play", group: "Playback", keys: "Space", run: () => player.current?.toggle() },
      { id: "next", title: "Next scene", group: "Playback", keys: "K", run: () => goScene(1) },
      { id: "prev", title: "Previous scene", group: "Playback", keys: "J", run: () => goScene(-1) },
      { id: "redo_ai", title: "Director: direct this video again…", group: "AI", run: () => setRedoOpen(true) },
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
    <Timeline r={r} duration={dur} seek={seek} selected={selected} onSelect={pickScene} selectedEl={selEl} onSelectEl={(sc, i) => { setSelectedWord(null); setSel(null); setSelLayer(null); setSelected(sc); setVideoSel(false); setShowInspector(true); setSelEl({ scene: sc, index: i }); }}
      tool={tool} setTool={setTool} snap={snap} setSnap={setSnap} sel={sel} setSel={selectVoice}
      layers={layers} media={mediaMap} selLayer={selLayer} onSelectLayer={selectLayer} onAddMedia={() => setBin(true)} sounds={soundEvents.data} onListen={listen} listening={listening} onEditWord={wid => { setSelectedWord(wid); setSel(null); setSelLayer(null); setSelEl(null); setSelAction(null); setVideoSel(false); setShowInspector(true); const w=r.words.find(w=>w.id===wid); if(w) {const start=w.caption_start??w.start,end=w.caption_end??w.end;seek(Math.min(dur,start+Math.min(.1,(end-start)/2)));} }} />
  ), [r.rev, r.plan, r.timing, r.words, r.wordById, r.audio, r.audioRev, r.audioSaving, r.canUndo, r.canRedo, dur, seek, pickScene, selected, selEl, tool, snap, sel, layers, mediaMap, selLayer, soundEvents.data, listening]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (r.project.error) return <div className="page-inner"><div className="banner err">Could not open this video: {r.project.error}. <Link to="/">Back to projects</Link></div></div>;
  if (!p || r.sc.loading) return <div className="page-inner"><div className="row muted"><Spinner /> Opening your video…</div></div>;
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
        <Button size="sm" variant="ghost" onClick={() => window.dispatchEvent(new Event("vt-app-menu"))} aria-label="Open app navigation"><Menu size={16} /></Button>
        <Tooltip text="Your videos"><Link to="/" className="btn ghost icon sm" aria-label="Your videos"><ChevronLeft size={18} /></Link></Tooltip>
        <input type="text" className="name bn" defaultValue={p.title} key={p.title} aria-label="Title" onBlur={(e) => e.target.value.trim() && e.target.value !== p.title && r.patchProject({ title: e.target.value })} />
        <Popover label="Editor commands" trigger="Edit ▾">
          <MenuItem onClick={r.undo} disabled={!r.canUndo} keys="Ctrl+Z">Undo</MenuItem>
          <MenuItem onClick={r.redo} disabled={!r.canRedo} keys="Ctrl+Shift+Z">Redo</MenuItem>
          <MenuItem onClick={() => setBin(true)}>Add pictures, video or sound…</MenuItem>
          <MenuSep />
          <MenuItem onClick={() => goScene(-1)} keys="J" disabled={idx <= 0}>Previous scene</MenuItem>
          <MenuItem onClick={() => goScene(1)} keys="K" disabled={idx >= scenes.length - 1}>Next scene</MenuItem>
          <MenuItem onClick={() => scene && r.mergeNext(scene.id)} disabled={!scene || idx >= scenes.length - 1}>Merge with next scene</MenuItem>
          <MenuItem onClick={() => setConfirmDel(true)} disabled={!scene || scenes.length < 2}>Delete this scene…</MenuItem>
          <MenuSep />
          <MenuItem onClick={() => setRedoOpen(true)}>Direct this video again…</MenuItem>
          <MenuItem onClick={() => nav(`/p/${id}/shorts`)}>Make short clips…</MenuItem>
          <MenuItem onClick={() => setSafe(!safe)} checked={safe}>Phone safe area</MenuItem>
          <MenuItem onClick={() => { setLeft(-1); setRight(-1); setTlH(-1); }}>Reset panel sizes</MenuItem>
          <MenuSep />
          <MenuItem onClick={() => setPalette(true)} keys="Ctrl+K">Find any command…</MenuItem>
          <MenuItem onClick={() => setKeys(true)}>Keyboard shortcuts</MenuItem>
        </Popover>
        <div className="ed-history">
          <Tooltip text="Undo" keys="Ctrl+Z"><Button icon variant="ghost" size="sm" onClick={r.undo} disabled={!r.canUndo} aria-label="Undo"><Undo2 size={16}/></Button></Tooltip>
          <Tooltip text="Redo" keys="Ctrl+Shift+Z"><Button icon variant="ghost" size="sm" onClick={r.redo} disabled={!r.canRedo} aria-label="Redo"><Redo2 size={16}/></Button></Tooltip>
        </div>
        <Button size="sm" onClick={() => nav(`/p/${id}/script`)} aria-label="Director's script"><MessageSquareText size={15}/> Script</Button>
        <Button size="sm" onClick={() => setAiOpen(true)} aria-label="AI assistant"><Sparkles size={15}/> AI</Button>
        <Button size="sm" variant="primary" onClick={exportNow}><Download size={15}/> Export</Button>
      </header>
      <div className="ed-workspace-bar">
        <div className="ed-panel-actions">
          <button className={`btn sm ${showBrowser ? "selected" : ""}`} aria-pressed={showBrowser} onClick={() => setShowBrowser(!showBrowser)}><PanelLeftClose size={15}/> Tools</button>
          <button className={`btn sm ${showInspector ? "selected" : ""}`} aria-pressed={showInspector} onClick={() => { if(videoSel) { setVideoSel(false); setShowInspector(true); } else setShowInspector(!showInspector); }}><PanelRightClose size={15}/> Details</button>
          <button className={`btn sm ${showAssistant ? "selected" : ""}`} aria-pressed={showAssistant} title="Assistant (Ctrl+Alt+B)" onClick={() => setShowAssistant(!showAssistant)}><MessageSquare size={15}/> Assistant</button>
          <button className={`btn sm ${showTimeline ? "selected" : ""}`} aria-pressed={showTimeline} title="Timeline (Ctrl+J)" onClick={() => setShowTimeline(!showTimeline)}><PanelBottomClose size={15}/> Timeline</button>
          <button className="btn ghost sm" title="Give the video all the available space" onClick={() => { const show = !showBrowser && !showInspector; setShowBrowser(show); if(!compact || !show) setShowInspector(show); }}><Maximize2 size={15}/> {!showBrowser && !showInspector ? "Show panels" : "Focus"}</button>
        </div>
        <span className="ed-save-status small muted" role="status">{r.audioSaving || layers.saving ? "Saving…" : "Preview updates as you edit"}</span>
        <button className={`btn sm ${videoSel ? "primary" : ""}`} aria-pressed={videoSel && showInspector} onClick={() => { setVideoSel(v => !v); setShowInspector(true); }}>Video settings</button>
      </div>

      {p.plan_notice && (
        <div className="banner warn" style={{ margin: "8px 12px 0" }}>
          <div className="grow"><strong>Your scene plan was replaced</strong><div className="small muted">{p.plan_notice.message}</div></div>
          <button className="btn sm" onClick={() => del(`/api/projects/${id}/plan-notice`).then(r.reloadAll)}>Got it</button>
        </div>
      )}
      {p.ai_notice && (
        <div className="banner warn" style={{ margin: "8px 12px 0" }}>
          <div className="grow"><strong>The built-in rules directed this video</strong><div className="small muted">{p.ai_notice.message} Try AI → Direct the whole video again, or check the AI in Settings. Details → AI conversations shows what it answered.</div></div>
          <Link className="btn sm" to="/settings">Settings</Link>
        </div>
      )}
      {!!p.notices?.length && (
        <div className="banner" role="status" style={{ margin: "8px 12px 0" }}>
          <div className="grow"><strong>{p.notices.length === 1 ? "One extra was skipped" : `${p.notices.length} extras were skipped`}</strong>
            <ul className="small muted" style={{ margin: "4px 0 0", paddingLeft: 18 }}>{p.notices.map((n, i) => <li key={i} title={n.error}>{n.message}</li>)}</ul></div>
          <button className="btn sm" onClick={() => del(`/api/projects/${id}/notices`).then(r.reloadAll)}>Got it</button>
        </div>
      )}
      <Requests r={r} sceneIndexById={sceneIndexById} />

      <div className="ed-body">
        <Workbench layoutKey="editor" shown={{ library: showBrowser, inspector: showInspector, timeline: showTimeline, assistant: showAssistant }} panes={{
          library: (<aside className="ed-left" aria-label="Editing tools panel">
            <div className="ed-panel-heading"><strong>Build your video</strong><button className="btn ghost icon sm" aria-label="Close tools panel" onClick={() => setShowBrowser(false)}><X size={16}/></button></div>
            <nav className="ed-tool-grid" aria-label="Editing tools">
              {([ ["scenes", "Scenes", "Arrange the story"], ["direction", "Direction", "Edit instructions and regenerate a scene"], ["elements", "Elements", "Add text, shapes and diagrams"], ["script", "Script", "Read and correct lines"], ["words", "Captions", "Fix individual words"], ["media", "Pictures", "Add or replace pictures and clips"], ["sound", "Sound", "Voice, music and effects"] ] as const).map(([value, label, hint]) => <button key={value} title={hint} aria-pressed={tab === value} className={tab === value ? "on" : ""} onClick={() => { setTab(value); if(value === "elements") { setSelectedWord(null); setSel(null); setSelLayer(null); setVideoSel(false); } }}>{label}</button>)}
            </nav>
            <div className={`scroll ${tab === "words" || tab === "script" || tab === "chat" ? "fill" : ""}`}>
              {tab === "elements" && <ComponentLibrary catalogue={cat} disabled={!scene}
                reason={!scene ? "Select a scene in the timeline first." : `Adding to scene ${idx + 1}`}
                onAdd={spec => {
                  const added = inspector.current?.add(spec);
                  if(added != null && scene) { setSelectedWord(null); setSelEl({scene:scene.id,index:added}); setShowInspector(true); }
                }}/>}
              {tab === "scenes" && <ScenesPanel r={r} selected={selected} onSelect={pickScene} seek={seek} />}
              {tab === "direction" && (scene?<DirectionPanel key={scene.id} r={r} sid={scene.id} onElement={index=>{setSelectedWord(null);setSel(null);setSelLayer(null);setVideoSel(false);setSelEl({scene:scene.id,index});setShowInspector(true);if(compact)setShowBrowser(false);}}/>:<p className="small muted" style={{padding:16}}>Select a scene in the timeline.</p>)}
              {tab === "script" && <><HookCard pid={id} onApplied={progress} /><ScriptPanel r={r} time={time} playing={playing} seek={seek} /></>}
              {tab === "sound" && <div style={{padding:16}}><SoundPanel r={r} /></div>}
              {tab === "words" && <CaptionLook r={r} />}
              {tab === "words" && <TranscriptPanel r={r} time={time} playing={playing} seek={seek} selected={selected} onSelectScene={pickScene} editingId={editingId} setEditingId={setEditingId} />}
              {tab === "media" && (
                <div className="col" style={{ padding: 14 }}>
                  <p className="small muted" style={{ margin: 0 }}>Your pictures, GIFs and clips ({p.media?.length ?? 0}). The planner places them; “Show as” lets you choose how.</p>
                  <Button onClick={() => setBin(true)}><ImageIcon size={15} /> Open the media bin</Button>
                  {scene && <PictureTools key={scene.id} pid={id} sid={scene.id} media={mediaList.data ?? []} onChanged={r.reloadAll} />}
                </div>
              )}
            </div>
          </aside>),

          viewer: (<section className="ed-canvas" aria-label="Canvas">
            {shotEdit ? (
              <Suspense fallback={<Spinner />}>
                <ShotEditor projectId={id} shotId={shotEdit} onClose={() => { setShotEdit(null); r.reloadAll(); }} />
              </Suspense>
            ) : <>
            {scene?.shot && <button className="btn sm shot-open" onClick={() => setShotEdit(scene.shot!)} title="Change this shot's text, colours, sizes and positions without touching its code">Edit shot</button>}
            <Preview
              ref={player}
              projectId={id}
              aspect={p.aspect}
              canvas={p.canvas}
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
              visualLayers={visualLayers}
              selectedEl={selEl}
              onPick={(sc, index) => {
                if (sc) {
                  setSelectedWord(null);
                  setSel(null); setSelLayer(null); setShowInspector(true);
                  setSelected(sc);
                  setVideoSel(false);
                  setSelEl(index != null ? { scene: sc, index } : null);
                }
              }}
            />
            </>}
          </section>),

          inspector: (<aside className="ed-right" aria-label="Selection details">
            <div className="ed-panel-heading"><div><strong>{videoSel ? "Whole video" : captionWord ? "Selected caption" : sel ? "Selected voice" : layerClip ? "Selected clip" : "Selected scene"}</strong><span>{videoSel ? "Changes here apply to the whole video." : captionWord ? "Edit the word and when it appears." : sel ? "Only this voice range will change." : layerClip ? "Change its content, timing and appearance." : "Choose a scene or a visual in the timeline."}</span></div><button className="btn ghost icon sm" aria-label="Close details panel" onClick={() => setShowInspector(false)}><X size={16}/></button></div>
            {videoSel && <button className="btn ghost sm" onClick={() => setVideoSel(false)}>← Back to selection</button>}
            {!videoSel && sel ? <div className="ed-selection-card">
              <h2>Voice selection</h2><p className="small muted">Removing this range shortens the video. Muting keeps its length.</p>
              <div className="ed-time-fields">
                {(["o0", "o1"] as const).map(edge => <label key={edge}>{edge === "o0" ? "Start" : "End"} (seconds)<input
                  key={`${sel.o0}-${sel.o1}-${edge}`} aria-label={`Voice selection ${edge === "o0" ? "start" : "end"}`} type="number"
                  min={edge === "o0" ? 0 : sel.o0 + 0.03} max={edge === "o0" ? sel.o1 - 0.03 : dur} step={0.001} defaultValue={sel[edge].toFixed(3)}
                  onKeyDown={e => { if(e.key === "Enter") e.currentTarget.blur(); }} onBlur={e => {
                    const n = Number(e.currentTarget.value);
                    const value = e.currentTarget.value.trim() && Number.isFinite(n)
                      ? edge === "o0" ? Math.max(0,Math.min(n,sel.o1 - 0.03)) : Math.min(dur,Math.max(n,sel.o0 + 0.03)) : sel[edge];
                    e.currentTarget.value = value.toFixed(3); setSel({...sel,[edge]:value});
                  }} /></label>)}
              </div><strong>{(sel.o1-sel.o0).toFixed(3)} seconds selected</strong>
              <button className="btn" onClick={() => seek(sel.o0)}>Preview from start</button>
              <button className="btn danger" disabled={r.audioSaving} onClick={async () => { const result = await r.audioEdit("cut",{start:sel.o0,end:sel.o1}); if(result) { seek(Math.min(sel.o0,result.duration)); setSel(null); } }}>Remove selected time</button>
              <button className="btn" disabled={extracting || r.audioSaving || layers.saving} onClick={async()=>{
                if(!sel) return; setExtracting(true);
                try {
                  const m=await post<MediaItem>(`/api/projects/${id}/audio/extract`,{start:sel.o0,end:sel.o1});
                  await soundList.refetch();
                  const {clip,kind}=LOps.newFromMedia(m,sel.o0);
                  const made=LOps.place(layers.doc,{...clip,dur:sel.o1-sel.o0} as any,kind,dur);
                  if(!await layers.saveNow(made.doc)) return;
                  const muted=await r.audioEdit("mute",{start:sel.o0,end:sel.o1,on:true});
                  if(!muted) {await layers.undo();toast("Could not separate the original audio; the added clip was rolled back.","err");return;}
                  selectLayer(made.clip.id);
                } catch(e:any) {toast(e.message,"err");} finally {setExtracting(false);}
              }}>{extracting?"Separating audio…":"Make a separate sound clip"}</button>
              <p className="small muted">Separate it to move, trim, duplicate, change volume or add fades independently. This lifts the whole selected recording, including any speech mixed with the sound.</p>
              <button className="btn ghost" onClick={() => setSel(null)}>Clear selection</button>
            </div> : !videoSel && layerClip ? (
              <LayerInspector key={layerClip.id} layers={layers} clip={layerClip} media={mediaMap} total={dur} onSelect={setSelLayer} seek={seek} time={time} />
            ) : !videoSel && captionWord ? (
              <CaptionInspector key={captionWord.id} word={captionWord} r={r} total={dur} seek={seek}/>
            ) : videoSel || !scene ? (
              <><div className="ed-project-info"><StatusChip status={p.status}/><ModeSwitch r={r}/><DirectorLogButton pid={p.id}/></div><VideoInspector r={r} p={p} useCases={useCases ?? []} onRedirect={progress} onRepace={(pace, from) => setRepaceAsk({ pace, from })} /></>
            ) : (
              <>{agentTouched && agentTouched.scene === scene.id && <div className="banner vt-agent-touched" role="status">{agentTouched.who} just changed this.
                <button className="btn sm" onClick={async () => { setAgentTouched(null); await r.undo(); }}>Undo</button>
                <button className="btn sm ghost" aria-label="Dismiss" onClick={() => setAgentTouched(null)}>OK</button></div>}
              <Inspector seek={seek} focusAction={selAction?.scene===scene.id?selAction.index:null} ref={inspector} key={scene.id} r={r} scene={scene} index={idx} time={timeOf.get(scene.id)} words={sceneWords.length ? sceneWords : r.words.filter(w=>!w.cut)} playheadWord={curWord?.id ?? null} cat={cat} icons={icons} focusEl={selEl && selEl.scene === scene.id ? selEl.index : null} /></>
            )}
          </aside>),

          timeline: (<section className="ed-timeline occ-switchable" aria-label="Timeline panel" aria-busy={directorRunning}>
          <div className="seg occ-switch" role="group" aria-label="Which timeline">
            <button type="button" className={newTimeline ? "" : "on"} aria-pressed={!newTimeline} onClick={() => chooseTimeline(false)}>Classic</button>
            <button type="button" className={newTimeline ? "on" : ""} aria-pressed={newTimeline} onClick={() => chooseTimeline(true)}>New timeline</button>
          </div>
          {newTimeline ? (
            <Suspense fallback={<div className="row muted" style={{ padding: 12 }}><Spinner /> Opening the new timeline…</div>}>
              <OccTimeline player={player} playing={playing} revision={`${r.rev}-${r.audioRev}-${JSON.stringify(layers.doc).length}`}
                onSave={saveTimeline} onUndo={() => void r.undo()} onRedo={() => void r.redo()}
                disabled={directorRunning}
                highlightScenes={directorChangedScenes}
                view={{ projectId: id, fps: 30, ...(p.canvas ?? CANVAS[p.aspect] ?? CANVAS["9:16"]), duration: dur, plan, timing: r.timing.scenes,
                  elementTimes: r.sc.data?.elements, words: r.words, keep: r.audio?.keep ?? [],
                  audioUrl: p.audio_url ? `${p.audio_url}${p.audio_url.includes("?") ? "&" : "?"}v=${r.audioRev}` : null,
                  layers: layers.doc, media: Object.fromEntries(mediaMap), elementName: (t) => ELEMENT_NAME[t] ?? t.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()) }} />
            </Suspense>
          ) : <div className="occ-classic">{timeline}</div>}
          {directorRunning && <div className="occ-director-timeline-block" role="status" aria-live="polite" data-testid="director-timeline-block">
            <div className="occ-director-timeline-block-card"><Sparkles size={19} aria-hidden="true" />
              <div><strong>Director is updating the video</strong><span>Timeline editing unlocks as soon as it finishes.</span></div>
            </div>
          </div>}
        </section>),

          assistant: (<div className="wb-assistant-body" aria-label="Assistant">
            <div className="wb-pane-heading"><strong>Assistant</strong><div className="wb-assistant-tabs" role="tablist" aria-label="Who to talk to"><button role="tab" aria-selected={assistantTab === "director"} className={assistantTab === "director" ? "on" : ""} onClick={() => setAssistantTab("director")}>Director</button><button role="tab" aria-selected={assistantTab === "claude"} className={assistantTab === "claude" ? "on" : ""} onClick={() => setAssistantTab("claude")}>Claude Code</button></div><span className="grow" /><button className="btn ghost icon sm" aria-label="Close the assistant" onClick={() => setShowAssistant(false)}><X size={16} /></button></div>
            <div className="wb-assistant-scroll">{assistantTab === "claude" && <Suspense fallback={<div className="row muted" style={{ padding: 12 }}><Spinner /> Opening…</div>}><AgentChat projectId={id} title={p.title || id} onChanged={r.reloadAll} onLink={(l) => { if (l.kind === "time") seek(l.t); else if (l.kind === "range") seek(l.from); else if (l.kind === "scene") { pickScene(l.scene); const s = r.timing.scenes.find((x) => x.id === l.scene); if (s) seek(s.start); } else { pickScene(l.scene); setSelEl({ scene: l.scene, index: l.index }); setShowInspector(true); } }} /></Suspense>}{directorMounted && <div style={{ height: "100%", display: assistantTab === "director" ? undefined : "none" }}><Suspense fallback={<div className="row muted" style={{ padding: 12 }}><Spinner /> Opening the chat…</div>}><DirectorChat projectId={id}
                onStarted={r.beginDirectorChange}
                onRunningChange={setDirectorRunning}
                onChanged={async (result, token) => {
                  r.finishDirectorChange(token, result?.ok ? result.previous_state as unknown as DirectorState | null | undefined : null);
                  setDirectorChangedScenes(result?.ok ? result.changed_scenes ?? [] : []);
                  setDirectorRemovedScenes(result?.ok ? result.removed_scenes ?? [] : []);
                  await r.reloadAll();
                }}
                director={p.director?.who} historyAction={r.directorHistory} onHistoryAction={r.toggleDirectorChange}
                changedScenes={directorChangedScenes} removedScenes={directorRemovedScenes} /></Suspense></div>}</div>
          </div>),
        }} />
      </div>

      {chat && <ChatAssistant id={id} kind={kind} onClose={() => setChat(false)} onApplied={r.reloadAll} />}
      {bin && <MediaBin id={id} onClose={() => setBin(false)} onChange={() => { r.reloadAll(); mediaList.refetch(); soundList.refetch(); }} onAddToTimeline={addToTimeline} />}
      {toolsOpen && <VideoTools id={id} onClose={()=>setToolsOpen(false)} onChanged={()=>r.reloadAll()}/> }
      {aiOpen && <AIPanel r={r} id={id} scene={scene} kind={kind} onClose={() => setAiOpen(false)} onChat={() => setChat(true)} onTools={() => {setAiOpen(false);setToolsOpen(true);}} goProgress={progress} />}
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
