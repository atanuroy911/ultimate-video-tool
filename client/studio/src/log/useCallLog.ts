import { useCallback, useEffect, useRef, useState } from "react";
import { get } from "../api";
import { onCallEvent } from "../store";

export interface LogEntry {
  seq: number;
  t: string;
  id: string;
  level: "info" | "ok" | "warn" | "error";
  module: string;
  plain: string;
  why?: string;
  caller?: { kind: string; who: string };
  cost?: Record<string, number>;
  status?: string;
  cached?: boolean;
  fix?: string | null;
  inputs?: Record<string, unknown>;
  wrote?: unknown[];
}
export interface RunningCall {
  id: string;
  module: string;
  plain: string;
  caller: string;
  elapsed: number;
  estimate: number;
  frac?: number;
  msg?: string;
}

/** The project's call log: loaded when the sheet opens, topped up by the server's `call` and `ticket` events and a slow poll. */
export function useCallLog(pid: string | undefined, open: boolean) {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [running, setRunning] = useState<RunningCall[]>([]);
  const [error, setError] = useState("");
  const [loaded,setLoaded]=useState(false);
  const last = useRef(0);

  const load = useCallback(async () => {
    if (!pid) return;
    try {
      const r = await get<{ entries: LogEntry[]; running: RunningCall[] }>(`/api/projects/${pid}/calls?after=${last.current}`);
      if (r.entries.length) {
        last.current = r.entries[r.entries.length - 1].seq;
        setEntries((e) => [...e, ...r.entries.filter((n) => !e.some((x) => x.seq === n.seq))]);
      }
      setRunning((old) =>
        r.running.map((n) => {
          const before = old.find((o) => o.id === n.id);
          return before ? { ...n, frac: before.frac, msg: before.msg } : n;
        }),
      );
      setError("");
      setLoaded(true);
    } catch (e: any) {
      setError(e.message || "Could not read the log");
    }
  }, [pid]);

  useEffect(() => {
    last.current = 0;
    setEntries([]);
    setRunning([]);
    setLoaded(false);
  }, [pid]);

  useEffect(() => {
    if (!open) return;
    load();
    const poll = setInterval(load, 3000);
    const off = onCallEvent((m) => {
      if (m.project !== pid) return;
      if (m.type === "ticket") setRunning((r) => r.map((x) => (x.id === m.id ? { ...x, frac: m.frac, msg: m.msg } : x)));
      load();
    });
    return () => {
      clearInterval(poll);
      off();
    };
  }, [open, pid, load]);

  return { entries, running, error, loaded, reload: load };
}
