import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { del, patch, post, put } from "../api";
import { useFetch, useProject } from "../hooks";
import { jobsStore, toast, useChanged, useStore } from "../store";
import type { Beat, PlanRequest, Plan, ScenesResponse, TranscriptData, Word } from "../types";

type ThumbsResp = { hash: string | null; scenes: Record<string, string> };

/** All server state for the Review screen plus the edit actions (each records an undo step). */
export interface AudioView {
  duration: number;
  source_duration: number;
  keep: { s: number; e: number; o0: number; o1: number }[];
  cuts: { index: number; s: number; e: number; o: number; len: number }[];
  mutes: { o0: number; o1: number; s: number; e: number }[];
  gains: { o0: number; o1: number; s: number; e: number; db: number }[];
  splits: { s: number; o: number }[];
  can_undo: boolean;
  can_redo: boolean;
  peaks: { n: number; duration: number; v: number[] };
}
type Kind = "plan" | "audio" | "layers" | "words";

export function useReview(id: string) {
  const project = useProject(id);
  const tr = useFetch<TranscriptData>(`/api/projects/${id}/transcript`);
  const sc = useFetch<ScenesResponse>(`/api/projects/${id}/scenes`);
  const rq = useFetch<PlanRequest[]>(`/api/projects/${id}/requests`);
  const aud = useFetch<AudioView>(`/api/projects/${id}/audio`);
  const aspect = project.data?.aspect ?? "9:16";
  const th = useFetch<ThumbsResp>(`/api/projects/${id}/thumbnails?aspect=${aspect}`, [aspect]);
  const [rev, setRev] = useState(0);
  const [audioRev, setAudioRev] = useState(0);
  const [audioSaving, setAudioSaving] = useState(false);
  const audioBusy = useRef(false);
  const [order, setOrder] = useState<Kind[]>([]);          // what was edited, oldest first: plan edits and audio edits share one undo history
  const [ofut, setOfut] = useState<Kind[]>([]);
  const layerUndo = useRef<{ undo: () => Promise<unknown>; redo: () => Promise<unknown> } | null>(null);       // the layers keep their own history; this list only says in which order things happened
  const [past, setPast] = useState<Plan[]>([]);
  const [future, setFuture] = useState<Plan[]>([]);
  const busy = useRef(false);
  const mutationQueue = useRef(Promise.resolve());

  const reloadAll = useCallback(async () => {
    await Promise.all([project.refetch(), tr.refetch(), sc.refetch(), rq.refetch(), aud.refetch()]);
    setRev((r) => r + 1);
  }, [project.refetch, tr.refetch, sc.refetch, rq.refetch, aud.refetch]); // eslint-disable-line react-hooks/exhaustive-deps
  useChanged(id, reloadAll);

  const plan = sc.data?.plan ?? null;
  const planRef = useRef(plan);                                  // the last plan that was on screen: an edit made while the plan is reloading must still be undoable
  useEffect(()=>{if(plan) planRef.current=plan;},[plan]);
  const timing = sc.data?.timing ?? { scenes: [], duration: project.data?.duration ?? 0 };
  const words: Word[] = tr.data?.transcript.words ?? [];
  const beats: Beat[] = tr.data?.beats.beats ?? [];
  const wordById = useMemo(() => new Map(words.map((w) => [w.id, w])), [words]);

  /* ---- thumbnails: regenerate (debounced) when the plan changes; refetch when the job finishes ---- */
  const planKey = useMemo(() => JSON.stringify(plan) + "|" + (project.data?.theme ?? "") + "|" + aspect, [plan, project.data?.theme, aspect]);
  useEffect(() => {
    if (!plan) return;
    const tm = setTimeout(() => post(`/api/projects/${id}/thumbnails?aspect=${aspect}`).catch(() => {}), 1600);
    return () => clearTimeout(tm);
  }, [planKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const jobs = useStore(jobsStore);
  const doneThumbs = Object.values(jobs).filter((j) => j.kind === "thumbs" && j.project === id && j.status === "done").length;
  useEffect(() => {
    th.refetch();
  }, [doneThumbs]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ---- mutations ---- */
  const run = useCallback(
    async <T,>(fn: () => Promise<T>, record = true): Promise<T | null> => {
      const previous = mutationQueue.current;
      let release!:()=>void;
      mutationQueue.current = new Promise<void>(resolve=>{release=resolve;});
      await previous;
      const before = planRef.current;
      try {
        const res = await fn();
        if (record && before) {
          setPast((p) => [...p.slice(-49), before]);
          setFuture([]);
          setOrder((o) => [...o.slice(-99), "plan"]);
          setOfut([]);
        }
        if((res as any)?.plan) planRef.current=(res as any).plan;
        await reloadAll();
        return res;
      } catch (e: any) {
        toast(e.errors?.length ? e.errors.slice(0, 3).join(" · ") : e.message, "err", 7000);
        return null;
      } finally { release(); }
    },
    [plan, reloadAll]
  );

  const moveEdge = (sid: string, t: number) => run(() => post(`/api/projects/${id}/scenes/${sid}/edge`, {t}));
  const splitAt = (sid: string, t: number) => run(() => post(`/api/projects/${id}/scenes/${sid}/split-at`, {t}));
  const patchElement = (sid: string, index: number, body: Record<string, any>) => run(() => patch(`/api/projects/${id}/scenes/${sid}/elements/${index}`, body));
  const patchScene = (sid: string, body: Record<string, any>) => run(() => patch(`/api/projects/${id}/scenes/${sid}`, body));
  const splitScene = (sid: string, atBeat: string) => run(() => post(`/api/projects/${id}/scenes/${sid}/split`, { at_beat: atBeat }));
  const mergeNext = (sid: string) => run(() => post(`/api/projects/${id}/scenes/${sid}/merge-next`));
  const removeScene = (sid: string) => run(() => del(`/api/projects/${id}/scenes/${sid}`));
  const moveBoundary = (sid: string, atBeat: string) => run(() => post(`/api/projects/${id}/scenes/${sid}/boundary`, { at_beat: atBeat }));
  const replanRules = () => run(() => post(`/api/projects/${id}/replan-rules`));
  const replanAuto = () => post(`/api/projects/${id}/replan`);
  const editWord = (wid: string, body: { text?: string; cut?: boolean; restore?: boolean; start?:number; end?:number; reset_timing?:boolean }) => run(() => put(`/api/projects/${id}/words/${wid}`, body), false).then(res=>{
    if(res) {setOrder(o=>[...o.slice(-99),"words"]);setOfut([]);} return res;
  });
  const addGlossary = (term: string, replacement: string) => run(() => post(`/api/projects/${id}/glossary`, { term, replacement }), false);
  const applyAlt = (rid: string, index: number) => run(() => post(`/api/projects/${id}/requests/${rid}/apply`, { index }));
  const askClaude = (kind: "full" | "scene", sceneId: string | null, hint: string, alternatives: number) =>
    run(() => post(`/api/projects/${id}/requests`, { kind, scene_id: sceneId, hint, alternatives }), false);
  const dropRequest = (rid: string) => run(() => del(`/api/projects/${id}/requests/${rid}`), false);
  const patchAction = (sid: string, index: number, body: { patch?: Record<string, any>; delete?: boolean }) => run(() => patch(`/api/projects/${id}/scenes/${sid}/actions/${index}`, body));
  const addAction = (sid: string, action: Record<string, any>) => run(() => post(`/api/projects/${id}/scenes/${sid}/actions`, action));
  const patchCast = (cid: string, body: Record<string, any>) => run(() => patch(`/api/projects/${id}/cast/${cid}`, body));
  const patchProject = (body: Record<string, any>) => run(() => patch(`/api/projects/${id}`, body), false);

  const planUndo = async () => {
    if (!past.length || !plan) return false;
    const prev = past[past.length - 1];
    try {
      await put(`/api/projects/${id}/scenes`, prev);
      setPast((p) => p.slice(0, -1));
      setFuture((f) => [...f, plan]);
      reloadAll();
      return true;
    } catch (e: any) {
      toast(e.message, "err");
      return false;
    }
  };
  const planRedo = async () => {
    if (!future.length || !plan) return false;
    const next = future[future.length - 1];
    try {
      await put(`/api/projects/${id}/scenes`, next);
      setFuture((f) => f.slice(0, -1));
      setPast((p) => [...p, plan]);
      reloadAll();
      return true;
    } catch (e: any) {
      toast(e.message, "err");
      return false;
    }
  };

  /** One voice edit (cut, mute, gain, split, restore): the server re-cuts the audio, words and plan follow; returns the new view. */
  const audioEdit = (what: "cut" | "mute" | "gain" | "split" | "restore", body: Record<string, any>): Promise<AudioView | null> => {
    if (audioBusy.current) { toast("Finishing your previous voice edit. Try again when Saving disappears."); return Promise.resolve(null); }
    return audioEditNow(what, body);
  };
  const audioEditNow = async (what: "cut" | "mute" | "gain" | "split" | "restore", body: Record<string, any>) => {
    audioBusy.current = true;
    setAudioSaving(true);
    try {
      const res = await post<AudioView>(`/api/projects/${id}/audio/${what}`, body);
      if (what !== "split") setAudioRev((n) => n + 1);
      setOrder((o) => [...o.slice(-99), "audio"]);
      setOfut([]);
      await reloadAll();
      return res;
    } catch (e: any) {
      toast(e.errors?.length ? e.errors.slice(0, 2).join(" · ") : e.message, "err", 5000);
      return null;
    } finally {
      audioBusy.current = false;
      setAudioSaving(false);
    }
  };
  const audioHistory = async (dir: "undo" | "redo") => {
    audioBusy.current = true;
    setAudioSaving(true);
    try {
      await post(`/api/projects/${id}/audio/${dir}`);
      setAudioRev((n) => n + 1);
      await reloadAll();
      return true;
    } catch (e: any) {
      toast(e.message, "err");
      return false;
    } finally { audioBusy.current = false; setAudioSaving(false); }
  };
  const wordHistory = async (dir:"undo"|"redo")=>{
    try {await post(`/api/projects/${id}/words/history/${dir}`);await reloadAll();return true;}
    catch(e:any) {toast(e.message,"err");return false;}
  };
  const undo = async () => {
    const k = order[order.length - 1];
    if (!k || busy.current || audioBusy.current) return;
    busy.current = true;
    try {
      const ok = k === "words" ? await wordHistory("undo") : k === "plan" ? await planUndo() : k === "layers" ? await layerUndo.current?.undo() : await audioHistory("undo");
      if (!ok) return;
      setOrder((o) => o.slice(0, -1));
      setOfut((f) => [...f, k]);
    } finally { busy.current = false; }
  };
  const redo = async () => {
    const k = ofut[ofut.length - 1];
    if (!k || busy.current || audioBusy.current) return;
    busy.current = true;
    try {
      const ok = k === "words" ? await wordHistory("redo") : k === "plan" ? await planRedo() : k === "layers" ? await layerUndo.current?.redo() : await audioHistory("redo");
      if (!ok) return;
      setOfut((f) => f.slice(0, -1));
      setOrder((o) => [...o, k]);
    } finally { busy.current = false; }
  };

  return {
    id, project, audio: aud.data, audioRev, audioSaving, audioEdit, tr, sc, rq, th, rev, reloadAll,
    plan, timing, words, beats, wordById, aspect,
    noteLayers: () => { setOrder((o) => [...o.slice(-99), "layers"]); setOfut([]); },
    setLayerHistory: (h: { undo: () => Promise<unknown>; redo: () => Promise<unknown> } | null) => { layerUndo.current = h; },
    canUndo: order.length > 0 && !audioSaving, canRedo: ofut.length > 0 && !audioSaving, undo, redo,
    moveEdge, splitAt, patchElement, patchScene, splitScene, mergeNext, removeScene, moveBoundary, replanRules, replanAuto, editWord, addGlossary,
    applyAlt, askClaude, dropRequest, patchProject, patchAction, addAction, patchCast,
  };
}
export type Review = ReturnType<typeof useReview>;
