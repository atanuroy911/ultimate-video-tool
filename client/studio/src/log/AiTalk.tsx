import { Bot, ChevronRight, Copy, Wrench } from "lucide-react";
import { useEffect, useState } from "react";
import { get } from "../api";
import { toast } from "../store";
import { copyText } from "../ui";

interface TalkRow { seq: number; at: string; stage: string; who: string; model: string; kind: string; seconds: number; error: string; cached: boolean; images: number; preview: string; size: number }
interface TalkFull extends TalkRow { system: string; prompt: string; answer: string }

const STAGE: Record<string, string> = { voice: "Voice", context: "Understanding the video", plan: "Planning the scenes", tighten: "Tightening", compose: "Putting it together", render: "Rendering", check: "Watching it back", publish: "Publishing" };
const NAMES: Record<string, string> = { ollama: "Local AI", claude: "Claude", "claude-pc": "Claude on this PC", "codex-pc": "Codex on this PC", "claude-cli": "Claude on the server", anthropic: "Claude (API key)", openai: "OpenAI", assistant: "Assistant", codex: "Codex", fake: "Test AI" };
const name = (r: TalkRow) => NAMES[r.who] || r.who.replace(/^(\w)/, (c) => c.toUpperCase());
const action = (r: TalkRow) => r.kind === "tool" ? `used ${r.preview}` : r.kind === "sent" ? "was asked to direct this video" : r.kind === "finished" ? "finished" : r.error ? "failed" : "answered";

function Block({ title, text }: { title: string; text: string }) {
  if (!text) return null;
  return (
    <section className="talk-block">
      <header><strong>{title}</strong>
        <button className="btn ghost sm" aria-label={`Copy: ${title}`} onClick={() => copyText(text).then(() => toast("Copied"))}><Copy size={12} /> Copy</button>
      </header>
      <pre tabIndex={0}>{text}</pre>
    </section>
  );
}

function Row({ pid, row }: { pid: string; row: TalkRow }) {
  const [full, setFull] = useState<TalkFull | null>(null);
  const [open, setOpen] = useState(false);
  const toggle = () => {
    setOpen(!open);
    if (!full) get<TalkFull>(`/api/projects/${pid}/ai-talk/${row.seq}`).then(setFull).catch((e) => toast(e.message, "err"));
  };
  const Icon = row.kind === "tool" ? Wrench : Bot;
  return (
    <li className={`talk-row${row.error ? " bad" : ""}`}>
      <button className="talk-head" onClick={toggle} aria-expanded={open}>
        <Icon size={14} aria-hidden />
        <span className="talk-title"><strong>{name(row)}</strong> {action(row)}
          <span className="muted small">{STAGE[row.stage] || row.stage}{row.seconds ? ` · ${row.seconds} s` : ""}{row.cached ? " · saved answer, not asked again" : ""}{row.images ? ` · ${row.images} pictures` : ""}</span>
        </span>
        <ChevronRight size={13} className="log-chev" aria-hidden />
      </button>
      {open && (
        <div className="talk-body">
          {!full && <p className="muted small">Loading…</p>}
          {full && <>
            {full.model && <p className="muted small">Model: {full.model}</p>}
            {full.error && <p className="banner err small">{full.error}</p>}
            <Block title="Its instructions" text={full.system} />
            <Block title={row.kind === "tool" ? "What it called" : "What it was asked"} text={full.prompt} />
            <Block title={row.kind === "tool" ? "What it got back" : "What it answered"} text={full.answer} />
          </>}
        </div>
      )}
    </li>
  );
}

/** Every prompt and every answer of this video, in order: which AI was asked what, and what it said (vt/ai/talk.py). */
export function AiTalk({ pid }: { pid: string }) {
  const [rows, setRows] = useState<TalkRow[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    const load = () => get<{ rows: TalkRow[] }>(`/api/projects/${pid}/ai-talk`).then((d) => { if (live) { setRows(d.rows); setError(""); } }).catch((e) => { if (live) setError(e.message); });
    load();
    const timer = window.setInterval(load, 4000);
    return () => { live = false; window.clearInterval(timer); };
  }, [pid]);
  if (error) return <div className="banner err small">{error}</div>;
  if (!rows) return <p className="muted small">Loading…</p>;
  if (!rows.length) return <p className="muted small" style={{ padding: 12 }}>No AI has been asked anything for this video yet. Videos made before this update have no record.</p>;
  const minds = Array.from(new Set(rows.map(name)));
  return (
    <div className="col" style={{ gap: 10 }} data-testid="ai-talk">
      <p className="small talk-minds"><strong>{minds.length === 1 ? "One AI worked on this video:" : `${minds.length} AIs worked on this video:`}</strong> {minds.join(", ")}</p>
      <ul className="talk-list">{rows.map((r) => <Row key={r.seq} pid={pid} row={r} />)}</ul>
    </div>
  );
}
