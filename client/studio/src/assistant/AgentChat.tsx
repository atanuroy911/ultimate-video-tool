// Claude Code in the Assistant pane (docs/plans/PLAN-WORKBENCH.MD W12.4). The real program runs in the desktop app (client/desktop/acp-agents.js); this page only
// sends what the person types and shows what comes back: the reply, the steps, and a permission card whenever the agent wants to do something that is not a Video Tool action.
import { Square, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { pieces, type VtLink } from "./links";
import "./assistant.css";

export interface AgentBridge {
  status(kind: string): Promise<{ found: boolean; logged_in: boolean; version: string; reason: string; adapter: boolean }>;
  open(kind: string, projectId: string, o?: { resume?: string; model?: string; title?: string }): Promise<{ conversationId: string; resumed: boolean; note: string }>;
  send(id: string, text: string, refs: unknown[], images: unknown[]): Promise<{ ok: boolean }>;
  stop(id: string): Promise<unknown>;
  permission(id: string, requestId: string, choice: "once" | "chat" | "deny"): Promise<unknown>;
  list(projectId: string): Promise<{ sessionId: string; title: string; at: string }[]>;
  signIn(kind: string): Promise<unknown>;
  onEvent(cb: (m: { conversationId: string; event: AgentEvent }) => void): () => void;
}
export type AgentEvent =
  | { type: "text"; text: string }
  | { type: "step"; id: string; title: string; tool?: string; status: string }
  | { type: "permission"; requestId: string; tool: string; what: string; title: string; detail: string }
  | { type: "done"; stopReason: string }
  | { type: "error"; kind: "limit" | "login" | "other"; message: string };

interface Step { id: string; title: string; status: string }
interface Turn { role: "me" | "agent"; text: string; steps: Step[] }
interface Card { requestId: string; what: string; title: string; detail: string }

export const agentBridge = (): AgentBridge | undefined => (window as any).vtDesktop?.agents;

const WHO = "Claude Code";

/** A reply with its vt:// links as buttons (never as addresses: the window does not navigate). */
function Reply({ text, onLink }: { text: string; onLink?: (l: VtLink) => void }) {
  return <p>{pieces(text).map((x, i) => "link" in x
    ? <button key={i} type="button" className="agent-link" title="Show it in the video" onClick={() => onLink?.(x.link)}>{x.label}</button>
    : <span key={i}>{x.text}</span>)}</p>;
}

export default function AgentChat({ projectId, title, onChanged, onLink }: { projectId: string; title: string; onChanged: () => void; onLink?: (l: VtLink) => void }) {
  const bridge = agentBridge();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [running, setRunning] = useState(false);
  const [card, setCard] = useState<Card | null>(null);
  const [problem, setProblem] = useState<{ kind: string; message: string } | null>(null);
  const [status, setStatus] = useState<{ found: boolean; logged_in: boolean; reason: string } | null>(null);
  const [earlier, setEarlier] = useState<{ sessionId: string; title: string } | null>(null);
  const [note, setNote] = useState("");
  const conv = useRef<string>("");
  const end = useRef<HTMLDivElement>(null);
  const denyRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!bridge) return;
    bridge.status("claude").then(setStatus).catch(() => setStatus({ found: false, logged_in: false, reason: `${WHO} could not be checked.` }));
    bridge.list(projectId).then((l) => setEarlier(l[0] ? { sessionId: l[0].sessionId, title: l[0].title } : null)).catch(() => {});
  }, [bridge, projectId]);

  const patchAgent = useCallback((fn: (t: Turn) => Turn) => setTurns((all) => {
    const last = all[all.length - 1];
    return last && last.role === "agent" ? [...all.slice(0, -1), fn(last)] : [...all, fn({ role: "agent", text: "", steps: [] })];
  }), []);

  useEffect(() => {
    if (!bridge) return;
    return bridge.onEvent(({ conversationId, event }) => {
      if (conversationId !== conv.current) return;
      if (event.type === "text") patchAgent((t) => ({ ...t, text: t.text + event.text }));
      else if (event.type === "step") patchAgent((t) => ({ ...t, steps: t.steps.some((s) => s.id === event.id) ? t.steps.map((s) => (s.id === event.id ? { ...s, status: event.status, title: event.title || s.title } : s)) : [...t.steps, { id: event.id, title: event.title, status: event.status }] }));
      else if (event.type === "permission") setCard({ requestId: event.requestId, what: event.what, title: event.title, detail: event.detail });
      else if (event.type === "done") { setRunning(false); setCard(null); onChanged(); }
      else if (event.type === "error") { setRunning(false); setCard(null); setProblem({ kind: event.kind, message: event.message }); onChanged(); }
    });
  }, [bridge, patchAgent, onChanged]);

  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [turns, card, problem]);
  useEffect(() => { if (card) denyRef.current?.focus(); }, [card]);

  if (!bridge) return <div className="agent-empty"><strong>{WHO}</strong><p>Available in the desktop app. Open the Video Tool app on this computer to use it here.</p></div>;
  if (status && !status.found) return <div className="agent-empty"><strong>{WHO} is not installed</strong><p>{status.reason || `Install ${WHO} on this computer, then come back.`}</p></div>;

  const begin = async (resume?: string) => {
    const o = await bridge.open("claude", projectId, { resume, title });
    conv.current = o.conversationId;
    setNote(o.note || (o.resumed ? "Continuing the earlier conversation." : ""));
    return o.conversationId;
  };
  const send = async () => {
    const text = draft.trim();
    if (!text || running) return;
    setProblem(null); setDraft(""); setRunning(true);
    setTurns((all) => [...all, { role: "me", text, steps: [] }]);
    try {
      const id = conv.current || await begin();
      await bridge.send(id, text, [], []);
    } catch (e: any) {
      setRunning(false);
      setProblem({ kind: "other", message: String(e?.message || e).replace(/^Error invoking remote method '[^']+': (Error: )?/, "") });
    }
  };
  const answer = async (choice: "once" | "chat" | "deny") => {
    const c = card; setCard(null);
    if (c) await bridge.permission(conv.current, c.requestId, choice).catch(() => {});
  };

  return (
    <div className="agent-chat">
      <div className="agent-log" role="log" aria-live="polite">
        {!turns.length && <div className="agent-empty"><strong>{WHO}</strong>
          <p>Ask for a change in your own words. It works on this video through Video Tool's own tools, and asks you before it does anything else.</p>
          {earlier && <button className="btn sm" onClick={async () => { setProblem(null); try { await begin(earlier.sessionId); } catch (e: any) { setProblem({ kind: "other", message: String(e?.message || e) }); } }}>Continue “{earlier.title.slice(0, 40)}”</button>}</div>}
        {note && <p className="small muted agent-note">{note}</p>}
        {turns.map((t, i) => (
          <div key={i} className={`agent-turn ${t.role}`}>
            {t.steps.length > 0 && <ul className="agent-steps">{t.steps.map((s) => <li key={s.id} className={s.status}><span className="dot" aria-hidden />{s.title}</li>)}</ul>}
            {t.text && (t.role === "agent" ? <Reply text={t.text} onLink={onLink} /> : <p>{t.text}</p>)}
          </div>
        ))}
        {card && (
          <div className="agent-card" role="alertdialog" aria-label="Permission needed">
            <strong>{WHO} wants to {card.what}</strong>
            {card.detail && <code>{card.detail.length > 300 ? card.detail.slice(0, 300) + "…" : card.detail}</code>}
            <div className="row">
              <button className="btn sm" onClick={() => answer("once")}>Allow once</button>
              <button className="btn sm" onClick={() => answer("chat")}>Allow for this chat</button>
              <button className="btn sm primary" ref={denyRef} onClick={() => answer("deny")}>Deny</button>
            </div>
          </div>
        )}
        {problem && (
          <div className="agent-problem" role="alert">{problem.message}
            {problem.kind === "login" && <button className="btn sm" onClick={() => bridge.signIn("claude").catch(() => {})}>Sign in</button>}</div>
        )}
        <div ref={end} />
      </div>
      <form className="agent-composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <textarea value={draft} rows={2} placeholder={`Tell ${WHO} what to change`} aria-label={`Message to ${WHO}`} disabled={running && !!card}
          onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
        {running
          ? <button type="button" className="btn sm" onClick={() => bridge.stop(conv.current)} aria-label="Stop"><Square size={14} /> Stop</button>
          : <button type="submit" className="btn sm primary" disabled={!draft.trim()} aria-label="Send"><Send size={14} /> Send</button>}
      </form>
    </div>
  );
}
