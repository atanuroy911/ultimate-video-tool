import { useCallback, useEffect, useRef, useState } from "react";
import { get, post, put } from "../api";
import { toast, useChanged } from "../store";
import type { LDoc } from "../types";

const EMPTY: LDoc = { v: 1, tracks: [], clips: [] };
interface View { doc: LDoc; duration: number; can_undo: boolean; can_redo: boolean }

/** The layers document. Edits happen on a local copy (so dragging is instant); `commit` saves it, one request at a time, and the answer replaces the copy. */
export function useLayers(id: string, onEdit?: () => void) {
  const [doc, setDoc] = useState<LDoc>(EMPTY);
  const [info, setInfo] = useState({ duration: 0, canUndo: false, canRedo: false });
  const [saving, setSaving] = useState(false);
  const docRef = useRef(doc);
  const saved = useRef(JSON.stringify(EMPTY));            // the last document the server confirmed
  const pending = useRef<LDoc | null>(null);
  const running = useRef(false);
  const live = useRef(0);                                  // > 0 while a drag or a save is in progress: a refetch must not overwrite local edits

  const apply = useCallback((v: View) => {
    docRef.current = v.doc;
    saved.current = JSON.stringify(v.doc);
    setDoc(v.doc);
    setInfo({ duration: v.duration, canUndo: v.can_undo, canRedo: v.can_redo });
  }, []);

  const load = useCallback(async () => {
    if (live.current || running.current) return;
    try { apply(await get<View>(`/api/projects/${id}/layers`)); } catch { /* a project without audio has no layers yet */ }
  }, [id, apply]);
  useEffect(() => { load(); }, [load]);
  useChanged(id, load);

  /** Change the local copy only (while dragging). */
  const setLocal = useCallback((d: LDoc) => { docRef.current = d; setDoc(d); }, []);
  const hold = useCallback((on: boolean) => { live.current += on ? 1 : -1; if (live.current < 0) live.current = 0; }, []);

  const flush = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    setSaving(true);
    try {
      while (pending.current) {
        const next = pending.current;
        pending.current = null;
        try {
          const v = await put<View>(`/api/projects/${id}/layers`, { doc: next });
          if (!pending.current) apply(v);
        } catch (e: any) {
          pending.current = null;
          toast(e.errors?.length ? e.errors.slice(0, 3).join(" · ") : e.message, "err", 6000);
          live.current = 0;
          running.current = false;
          setSaving(false);
          await load();                                     // show what the server really has
          return;
        }
      }
    } finally {
      running.current = false;
      setSaving(false);
    }
  }, [id, apply, load]);

  /** Save a document (the local copy when none is given). Nothing is sent when it has not changed. */
  const commit = useCallback((d?: LDoc) => {
    const next = d ?? docRef.current;
    docRef.current = next;
    setDoc(next);
    if (JSON.stringify(next) === saved.current && !pending.current) return;
    pending.current = next;
    onEdit?.();                                              // the editor's undo list notes that a layers edit happened
    flush();
  }, [flush, onEdit]);

  const step = useCallback(async (what: "undo" | "redo") => {
    try { apply(await post<View>(`/api/projects/${id}/layers/${what}`)); } catch (e: any) { toast(e.errors?.[0] || e.message, "err", 3000); }
  }, [id, apply]);

  return { doc, setLocal, commit, hold, undo: () => step("undo"), redo: () => step("redo"), duration: info.duration, canUndo: info.canUndo, canRedo: info.canRedo, saving };
}
export type Layers = ReturnType<typeof useLayers>;
