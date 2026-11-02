import { useEffect, useSyncExternalStore } from "react";
import { get } from "./api";
import type { JobInfo, McpStatus, Settings } from "./types";

type Listener = () => void;

/** A tiny observable store (no state library needed for this app). */
class Store<T> {
  private v: T;
  private ls = new Set<Listener>();
  constructor(init: T) {
    this.v = init;
  }
  get = () => this.v;
  set = (next: T | ((p: T) => T)) => {
    this.v = typeof next === "function" ? (next as (p: T) => T)(this.v) : next;
    this.ls.forEach((l) => l());
  };
  subscribe = (l: Listener) => {
    this.ls.add(l);
    return () => this.ls.delete(l);
  };
}

export function useStore<T>(s: Store<T>): T {
  return useSyncExternalStore(s.subscribe, s.get);
}

export const settingsStore = new Store<Settings>({
  default_theme: "auto",
  default_aspect: "9:16",
  default_pace: "normal",
  default_music: "auto",
  director_order: ["claude-client", "claude-server", "local"],
  director_wait_seconds: 120,
  ui_language: (localStorage.getItem("vt-lang") as "en" | "bn") || "en",
});
export const jobsStore = new Store<Record<string, JobInfo>>({});
export const connStore = new Store<{ ws: boolean; mcp: McpStatus | null }>({ ws: false, mcp: null });
export interface Toast {
  id: number;
  kind: "info" | "ok" | "err";
  text: string;
}
export const toastStore = new Store<Toast[]>([]);

let toastId = 0;
export function toast(text: string, kind: Toast["kind"] = "info", ms = 4500) {
  const id = ++toastId;
  toastStore.set((t) => [...t, { id, kind, text }]);
  setTimeout(() => toastStore.set((t) => t.filter((x) => x.id !== id)), ms);
}

/** Event bus for "something changed on the server" (file watcher, other tabs, Claude via MCP). */
const handlers = new Set<(project: string) => void>();
export const onChanged = (fn: (project: string) => void) => {
  handlers.add(fn);
  return () => {
    handlers.delete(fn);
  };
};
/** The director's call log events (`call`, `ticket`) from the server, for the Details sheet. */
const callHandlers = new Set<(m: any) => void>();
export const onCallEvent = (fn: (m: any) => void) => {
  callHandlers.add(fn);
  return () => {
    callHandlers.delete(fn);
  };
};
export const emitChanged = (project: string) => handlers.forEach((h) => h(project));

export function useChanged(project: string | undefined, fn: () => void) {
  useEffect(() => {
    if (!project) return;
    return onChanged((p) => p === project && fn());
  }, [project, fn]);
}

/* ---------------- websocket ---------------- */
let started = false;
export function startRealtime() {
  if (started) return;
  started = true;
  let delay = 500;
  const connect = () => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    const desktopDirector = (window as any).vtDesktop?.director as undefined | {
      status: () => Promise<{ found: boolean; logged_in: boolean; version: string }>;
      run: (task: any) => Promise<{ ok: boolean; error?: string }>;
      onLog: (fn: (value: any) => void) => () => void;
    };
    let stopLogs: undefined | (() => void);
    ws.onopen = () => {
      delay = 500;
      connStore.set((c) => ({ ...c, ws: true }));
      desktopDirector?.status().then((s) => ws.send(JSON.stringify({ type: "director", director: "claude", version: s.version, logged_in: s.found && s.logged_in }))).catch(() => {});
      if (desktopDirector) stopLogs = desktopDirector.onLog((m) => ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify({ type: "director_log", ...m })));
    };
    ws.onclose = () => {
      stopLogs?.();
      connStore.set((c) => ({ ...c, ws: false }));
      setTimeout(connect, delay);
      delay = Math.min(delay * 2, 8000);
    };
    ws.onmessage = (ev) => {
      let m: any;
      try {
        m = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (m.type === "hello") {
        const map: Record<string, JobInfo> = {};
        (m.jobs as JobInfo[]).forEach((j) => (map[j.id] = j));
        jobsStore.set((p) => ({ ...p, ...map }));
      } else if (m.type === "job") {
        const j = m.job as JobInfo;
        jobsStore.set((p) => ({ ...p, [j.id]: j }));
        if ((j.status === "done" || j.status === "error") && j.project && j.kind !== "thumbs") emitChanged(j.project);
      } else if (m.type === "changed") emitChanged(m.project);
      else if (m.type === "direct" && desktopDirector) {
        desktopDirector.run(m).then((result) => ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify({ type: "director_done", request: m.request, ...result })))
          .catch((e) => ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify({ type: "director_done", request: m.request, ok: false, error: e?.message || String(e) })));
      }
      else if (m.type === "call" || m.type === "ticket" || m.type === "call_started") callHandlers.forEach((h) => h(m));
    };
  };
  connect();
  const poll = () => get<McpStatus>("/api/mcp/status").then((s) => connStore.set((c) => ({ ...c, mcp: s }))).catch(() => {});
  poll();
  setInterval(poll, 8000);
  get<Settings>("/api/settings").then((s) => settingsStore.set((p) => ({ ...p, ...s, ui_language: (localStorage.getItem("vt-lang") as any) || s.ui_language }))).catch(() => {});
}
