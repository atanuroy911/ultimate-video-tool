import { useCallback, useEffect, useRef, useState } from "react";
import { get, post, put } from "../api";
import { toast, useChanged } from "../store";
import type { LDoc } from "../types";

const EMPTY: LDoc = { v: 1, tracks: [], clips: [] };
interface View { doc: LDoc; duration: number; can_undo: boolean; can_redo: boolean }

/** Keep edits local and save in order. A response may only replace the draft it was sent for. */
export function useLayers(id: string, onEdit?: () => void) {
  const [doc, setDoc] = useState<LDoc>(EMPTY);
  const [info, setInfo] = useState({ duration: 0, canUndo: false, canRedo: false });
  const [saving, setSaving] = useState(false);
  const docRef = useRef(doc);
  const saved = useRef(JSON.stringify(EMPTY));            // the last document the server confirmed
  const pending = useRef<LDoc | null>(null);
  const running = useRef(false);
  const revision = useRef(0);
  const live = useRef(0);                                  // > 0 while a drag or a save is in progress: a refetch must not overwrite local edits

  const apply = useCallback((v: View) => {
    docRef.current = v.doc;
    saved.current = JSON.stringify(v.doc);
    setDoc(v.doc);
    setInfo({ duration: v.duration, canUndo: v.can_undo, canRedo: v.can_redo });
  }, []);

  const load = useCallback(async () => {
    if (live.current || running.current || JSON.stringify(docRef.current) !== saved.current) return;
    const started = revision.current;
    try {
      const v = await get<View>(`/api/projects/${id}/layers`);
      if (started === revision.current && !live.current && !running.current) apply(v);
    } catch { /* a project without audio has no layers yet */ }
  }, [id, apply]);
  useEffect(() => { load(); }, [load]);
  useChanged(id, load);

  /** Change the local copy only (while dragging). */
  const setLocal = useCallback((d: LDoc) => { revision.current++; docRef.current = d; setDoc(d); }, []);
  const hold = useCallback((on: boolean) => { live.current += on ? 1 : -1; if (live.current < 0) live.current = 0; }, []);

  const flush = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    setSaving(true);
    try {
      while (pending.current) {
        const next = pending.current;
        pending.current = null;
        const started = revision.current;
        const previous = saved.current;
        try {
          const v = await put<View>(`/api/projects/${id}/layers`, { doc: next });
          saved.current = JSON.stringify(v.doc);
          if (saved.current !== previous) onEdit?.();
          setInfo({ duration: v.duration, canUndo: v.can_undo, canRedo: v.can_redo });
          if (!pending.current && !live.current && started === revision.current) apply(v);
        } catch (e: any) {
          toast(e.errors?.length ? e.errors.slice(0, 3).join(" · ") : e.message, "err", 6000);
          // A failed old save must not erase a newer drag or queued correction.
          if (!pending.current && !live.current && started === revision.current) {
            running.current = false;
            docRef.current = JSON.parse(saved.current);
            setDoc(docRef.current);
            await load();
            return;
          }
        }
      }
    } finally {
      running.current = false;
      setSaving(false);
    }
  }, [id, apply, load, onEdit]);

  /** Save a document (the local copy when none is given). Nothing is sent when it has not changed. */
  const commit = useCallback((d?: LDoc) => {
    const next = d ?? docRef.current;
    revision.current++;
    docRef.current = next;
    setDoc(next);
    if (JSON.stringify(next) === saved.current && !pending.current && !running.current) return;
    pending.current = next;
    flush();
  }, [flush]);

  const step = useCallback(async (what: "undo" | "redo") => {
    if (running.current || live.current) return false;
    running.current = true;
    setSaving(true);
    const started = revision.current;
    try {
      const v = await post<View>(`/api/projects/${id}/layers/${what}`);
      saved.current = JSON.stringify(v.doc);
      setInfo({ duration: v.duration, canUndo: v.can_undo, canRedo: v.can_redo });
      if (started === revision.current && !live.current) apply(v);
      return true;
    }
    catch (e: any) { toast(e.errors?.[0] || e.message, "err", 3000); return false; }
    finally { running.current = false; setSaving(false); if (pending.current) void flush(); }
  }, [id, apply, flush]);

  const saveNow = async (next:LDoc) => {
    if(running.current || live.current) {toast("Finish the current clip edit first.");return false;}
    running.current=true;setSaving(true);
    const version=++revision.current;
    try {
      const v=await put<View>(`/api/projects/${id}/layers`,{doc:next});
      const previous=saved.current;saved.current=JSON.stringify(v.doc);
      if(previous!==saved.current) onEdit?.();
      if(revision.current===version) apply(v);
      return true;
    } catch(e:any) {toast(e.message,"err");return false;}
    finally {running.current=false;setSaving(false);if(pending.current) void flush();}
  };
  return { doc, saveNow, setLocal, commit, hold, undo: () => step("undo"), redo: () => step("redo"), duration: info.duration, canUndo: !saving && info.canUndo, canRedo: !saving && info.canRedo, saving };
}
export type Layers = ReturnType<typeof useLayers>;
