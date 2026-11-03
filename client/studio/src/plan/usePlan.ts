import { useCallback, useEffect, useRef, useState } from "react";
import { get, post } from "../api";
import { toast, useChanged } from "../store";
import type { PlanView } from "./types";

/* The plan of one video, kept in step with the server: every edit returns the whole updated view, and a change from outside (a director, another tab) reloads it. */
export function usePlan(pid: string | undefined) {
  const [view, setView] = useState<PlanView | null>(null);
  const [busy, setBusy] = useState(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const reload = useCallback(() => {
    if (!pid) return Promise.resolve();
    return get<PlanView>(`/api/projects/${pid}/plan`).then((v) => alive.current && setView(v)).catch(() => {});
  }, [pid]);
  useEffect(() => { reload(); }, [reload]);
  useChanged(pid, reload);
  const call = useCallback(async (path: string, body?: unknown): Promise<PlanView | null> => {
    if (!pid) return null;
    setBusy(true);
    try {
      const v = await post<PlanView>(["/api/projects", pid, "plan", path.replace(/^\//, "")].join("/"), body);        // joined, so the endpoint check reads the real routes in plan_routes.py
      if (alive.current) setView(v);
      return v;
    } catch (e: any) {
      toast(e.errors?.[0] || e.message, "err", 7000);
      return null;
    } finally {
      alive.current && setBusy(false);
    }
  }, [pid]);
  const edit = useCallback((op: Record<string, unknown>) => call("/edit", { op }), [call]);
  return { view, plan: view?.plan ?? null, busy, reload, call, edit };
}
