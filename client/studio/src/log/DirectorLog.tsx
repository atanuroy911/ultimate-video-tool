import { Copy, Download, ListTree } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Sheet } from "../ds";
import { toast } from "../store";
import { copyText, Seg } from "../ui";
import { AiTalk } from "./AiTalk";
import { LogRow, RunningRow } from "./LogRow";
import { TechnicalOutput } from "./TechnicalOutput";
import { useCallLog } from "./useCallLog";

type Filter = "all" | "ai" | "problems";

/** The "Details" button and sheet: hidden until asked, opened by the button or the L key; it never opens by itself. */
export function DirectorLogButton({ pid, label = "Details" }: { pid: string; label?: string }) {
  const [open, setOpen] = useState(false);
  const { entries, running } = useCallLog(pid, true);
  const problems = entries.filter((e) => e.level === "error").length;
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (e.key.toLowerCase() !== "l" || e.metaKey || e.ctrlKey || e.altKey) return;
      if (el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable)) return;
      setOpen((o) => !o);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  return (
    <>
      <button className="btn ghost sm" onClick={() => setOpen(true)} aria-haspopup="dialog" data-testid="log-open">
        <ListTree size={14} /> {label}
        {running.length > 0 && <span className="log-live" aria-label="running" />}
        {problems > 0 && <span className="small" style={{ color: "var(--err)" }}> · {problems} to look at</span>}
      </button>
      {open && <DirectorLog pid={pid} onClose={() => setOpen(false)} />}
    </>
  );
}

export function DirectorLog({ pid, onClose }: { pid: string; onClose: () => void }) {
  const { entries, running, error, reload } = useCallLog(pid, true);
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const [technical, setTechnical] = useState(false);
  const [pause, setPause] = useState(false);
  const end = useRef<HTMLLIElement>(null);
  const start = useMemo(() => (entries.length ? Date.parse(entries[0].t) : Date.now()), [entries]);
  const shown = entries.filter((e) => {
    if (filter === "problems" && e.level !== "error" && e.level !== "warn") return false;
    return !q.trim() || JSON.stringify(e).toLowerCase().includes(q.trim().toLowerCase());
  });
  useEffect(() => {
    if (!pause) end.current?.scrollIntoView?.({ block: "end" });
  }, [shown.length, running.length, pause]);
  const copy = () => copyText(shown.map((e) => e.plain).join("\n")).then(() => toast("Copied"));

  return (
    <Sheet title="Details" onClose={onClose}>
      <div className="col" style={{ gap: 10 }} data-testid="director-log">
        <div className="row wrap" style={{ gap: 8 }}>
          <Seg<Filter>
            label="Show"
            value={filter}
            onChange={setFilter}
            options={[{ value: "all", label: "What happened" }, { value: "ai", label: "AI conversations" }, { value: "problems", label: "Problems" }]}
          />
          {filter !== "ai" && <input className="input grow" type="search" placeholder="Search" aria-label="Search the log" value={q} onChange={(e) => setQ(e.target.value)} />}
        </div>
        {filter === "ai" ? <AiTalk pid={pid} /> : <>
        <div className="row wrap small" style={{ gap: 14 }}>
          <label className="row" style={{ gap: 6 }}>
            <input type="checkbox" className="ios-switch" checked={technical} onChange={(e) => setTechnical(e.target.checked)} />
            Technical output
          </label>
          <label className="row" style={{ gap: 6 }}>
            <input type="checkbox" className="ios-switch" checked={pause} onChange={(e) => setPause(e.target.checked)} />
            Pause scrolling
          </label>
          <span className="grow" />
          <button className="btn ghost sm" onClick={copy}><Copy size={13} /> Copy</button>
          <a className="btn ghost sm" href={`/api/projects/${pid}/calls/download`} download><Download size={13} /> Download</a>
        </div>
        {error && <div className="banner err small">{error} <button className="btn ghost sm" onClick={reload}>Try again</button></div>}
        <ul className="log-list" aria-label="What the director did" aria-live="off">
          {shown.length === 0 && running.length === 0 && (
            <li className="muted small" style={{ padding: 12 }}>{entries.length ? "Nothing matches." : "Nothing has been recorded for this video yet."}</li>
          )}
          {shown.map((e) => <LogRow key={e.seq} entry={e} start={start} showTechnical={technical} />)}
          {running.map((r) => <RunningRow key={r.id} call={r} pid={pid} />)}
          <li ref={end} aria-hidden />
        </ul>
        {technical && <TechnicalOutput pid={pid} refresh={entries.length} />}
        </>}
      </div>
    </Sheet>
  );
}
