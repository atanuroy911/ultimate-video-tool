import { useCallback, useEffect, useRef, useState } from "react";
import { get } from "./api";
import { jobsStore, useChanged, useStore } from "./store";
import { BACK_EVENT } from "./connection";
import type { Catalogue, JobInfo, MusicTrack, ProjectSummary, Theme } from "./types";

/** Fetch with loading/error state and manual refetch. */
export function useFetch<T>(url: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const dataUrl = useRef<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!url);
  const seq = useRef(0);
  const refetch = useCallback(async () => {
    if (!url) return;
    const my = ++seq.current;
    try {
      const d = await get<T>(url);
      if (my === seq.current) {
        dataUrl.current = url;
        setData(d);
        setError(null);
      }
    } catch (e: any) {
      if (my === seq.current) setError(e.message || "Failed to load");
    } finally {
      if (my === seq.current) setLoading(false);
    }
  }, [url]);
  useEffect(() => {
    // A resource change must never display or submit the previous resource.
    ++seq.current;
    setData(null);
    setError(null);
    setLoading(!!url);
    refetch();
    return () => { ++seq.current; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ...deps]);
  const failed = useRef(false);
  failed.current = error !== null;
  useEffect(() => {                                                    // the server is back: whatever failed to load because it was away asks again by itself
    const again = () => { if (failed.current) refetch(); };
    window.addEventListener(BACK_EVENT, again);
    return () => window.removeEventListener(BACK_EVENT, again);
  }, [refetch]);
  return { data: dataUrl.current === url ? data : null, error, loading, refetch, setData };
}

export function useProject(id: string | undefined) {
  const r = useFetch<ProjectSummary>(id ? `/api/projects/${id}` : null);
  useChanged(id, r.refetch);
  return r;
}

export function useProjectJob(projectId: string | undefined): JobInfo | null {
  const jobs = useStore(jobsStore);
  if (!projectId) return null;
  const mine = Object.values(jobs).filter((j) => j.project === projectId && j.kind === "pipeline");
  mine.reverse().sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
  const active = mine.find((j) => j.status === "queued" || j.status === "running");
  return active || null;
}

let catPromise: Promise<Catalogue> | null = null;
export function useCatalogue() {
  const [c, setC] = useState<Catalogue | null>(null);
  useEffect(() => {
    catPromise = catPromise || get<Catalogue>("/api/catalogue");
    catPromise.then(setC).catch(() => {});
  }, []);
  return c;
}

let iconPromise: Promise<Record<string, string>> | null = null;
export function useIconPack() {
  const [c, setC] = useState<Record<string, string>>({});
  useEffect(() => {
    iconPromise = iconPromise || get<Record<string, string>>("/api/icon-pack");
    iconPromise.then(setC).catch(() => {});
  }, []);
  return c;
}

export function useThemes() {
  const r = useFetch<Theme[]>("/api/themes");
  return r;
}

export function useMusic() {
  return useFetch<MusicTrack[]>("/api/music");
}

/** Run a callback on a fixed interval while mounted. */
export function useInterval(fn: () => void, ms: number | null) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    if (ms == null) return;
    const id = setInterval(() => ref.current(), ms);
    return () => clearInterval(id);
  }, [ms]);
}
