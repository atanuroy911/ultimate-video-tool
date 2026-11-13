// Video Tool: talk to the director beside the timeline (phase 4 of docs/plans/PLAN-OPENCHATCUT.MD). The messages are drawn with
// OpenChatCut's chat components (ChatMessage, ChatRunStatus); the conversation is our director's (GET /api/projects/{id}/director,
// POST …/director/chat), run by whichever AI is chosen in Settings. While it works, each step it reports shows as a line, the current one
// live; when it is done its reply says what changed, and the project (timeline, preview) reloads.
import { useEffect, useMemo, useRef, useState } from 'react';
import { get, post } from '../../api';
import '../occ.css';
import { ChatMessage } from '../src/components/chat/ChatMessage';
import { ChatRunStatus } from '../src/components/chat/ChatRunStatus.tsx';
import type { DisplayMessage } from '../src/agent/agent-session';

interface Said { from: string; text: string; ok?: boolean; at?: string }
interface DirectorResult { ok: boolean; reply: string; previous_state?: Record<string, unknown> | null; changed_scenes?: string[]; removed_scenes?: string[] }
interface Job { id: string; status: string; msg: string; error: string; frac: number; kind?: string; project?: string | null; result?: DirectorResult | null }

/** Who directs, in the words the rest of the editor uses (review/AIPanel.tsx). */
export function directorName(who: string): string {
  return who === 'local' ? 'Local AI' : who === 'claude-server' ? 'Claude on the server' : who.startsWith('claude@') ? 'Claude on this PC'
    : who === 'rules' ? 'Built-in rules' : who.startsWith('codex') ? 'Codex' : who;
}

/** Our director's conversation as OpenChatCut's display messages. */
export function toDisplay(messages: Said[]): DisplayMessage[] {
  return messages.map((m): DisplayMessage => m.from === 'person' ? { role: 'user', text: m.text }
    : m.from === 'director' ? (m.ok === false ? { role: 'error', text: m.text } : { role: 'assistant', text: m.text })
    : { role: 'note', text: `${m.from}: ${m.text}` });
}

const sceneName = (id: string) => /^s\d+$/.test(id) ? `Scene ${id.slice(1)}` : `Scene ${id}`;

export default function DirectorChat({ projectId, onStarted, onChanged, onRunningChange, director, historyAction, onHistoryAction, changedScenes = [], removedScenes = [] }: {
  projectId: string;
  onStarted: () => number;
  onChanged: (result: DirectorResult | null, token: number | null) => Promise<void> | void;
  onRunningChange: (running: boolean) => void;
  director?: string;
  historyAction?: 'undo' | 'redo' | null;
  onHistoryAction?: () => Promise<unknown> | void;
  changedScenes?: string[];
  removedScenes?: string[];
}) {
  const [said, setSaid] = useState<Said[]>([]);
  const [draft, setDraft] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const [steps, setSteps] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [startedAt, setStartedAt] = useState(0);
  const [historyBusy, setHistoryBusy] = useState(false);
  const list = useRef<HTMLDivElement>(null);
  const handled = useRef(new Set<string>());
  const turnToken = useRef<number | null>(null);
  const running = submitting || finishing || (!!job && ['queued', 'running'].includes(job.status));
  useEffect(() => { onRunningChange(running); return () => onRunningChange(false); }, [running, onRunningChange]);

  const load = () => get<{ messages: Said[] }>(`/api/projects/${projectId}/director`).then((d) => setSaid(d.messages ?? [])).catch(() => {});
  useEffect(() => { void load(); }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps
  // a director job already under way on this video (opened from elsewhere, or the page was reloaded)
  useEffect(() => {
    get<Job[]>('/api/jobs').then((js) => {
      const j = js.find((x) => x.kind === 'director' && x.project === projectId && ['queued', 'running'].includes(x.status));
      if (j) { if (turnToken.current == null) turnToken.current = onStarted(); setJob(j); setStartedAt(Date.now()); }
    }).catch(() => {});
  }, [projectId]);
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => {
      get<Job>(`/api/jobs/${job!.id}`).then((j) => {
        setJob(j);
        if (j.msg) setSteps((s) => (s[s.length - 1] === j.msg ? s : [...s, j.msg]));
        if (j.status === 'done' && !handled.current.has(j.id)) {
          handled.current.add(j.id);
          void load();
          const token = turnToken.current;
          turnToken.current = null;
          setFinishing(true);
          void Promise.resolve(onChanged(j.result ?? null, token)).finally(() => setFinishing(false));
          setSteps([]);
        }
        if (j.status === 'error' && !handled.current.has(j.id)) {
          handled.current.add(j.id);
          const token = turnToken.current;
          turnToken.current = null;
          setFinishing(true);
          void Promise.resolve(onChanged(null, token)).finally(() => setFinishing(false));
          setError(j.error || 'The director could not do that.');
          void load();
          setSteps([]);
        }
        if (j.status === 'cancelled' && !handled.current.has(j.id)) {
          handled.current.add(j.id);
          const token = turnToken.current;
          turnToken.current = null;
          setFinishing(true);
          void Promise.resolve(onChanged(null, token)).finally(() => setFinishing(false));
          setError('The Director request was cancelled.');
          setSteps([]);
        }
      }).catch(() => {});
    }, 1000);
    return () => clearInterval(timer);
  }, [job?.id, running]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { list.current?.scrollTo({ top: list.current.scrollHeight }); }, [said.length, steps.length, running]);

  const send = async () => {
    const text = draft.trim();
    if (!text || running) return;
    setError('');
    setSubmitting(true);
    const token = onStarted();
    turnToken.current = token;
    try {
      const j = await post<Job>(`/api/projects/${projectId}/director/chat?quiet=1`, { message: text });   // the chat shows the steps itself; editing goes on
      setSaid((s) => [...s, { from: 'person', text }]);
      setDraft('');
      setSteps([]);
      setStartedAt(Date.now());
      setJob(j);
      setSubmitting(false);
    } catch (e: unknown) {
      setSubmitting(false);
      turnToken.current = null;
      onChanged(null, token);
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const shown = useMemo(() => [
    ...toDisplay(said),
    ...(running ? steps.slice(0, -1).map((s): DisplayMessage => ({ role: 'note', text: s })) : []),
    ...(error ? [{ role: 'error', text: error } as DisplayMessage] : []),
  ], [said, steps, running, error]);

  return (
    <section className="occ-chat" aria-label="Talk to the director" data-testid="director-chat">
      <header className="occ-chat-head">
        <strong>Director</strong>
        <span className="small muted">{director ? `${directorName(director)} directs this video` : 'Tell it what to change; it edits the video and says what it did.'}</span>
      </header>
      <div className="occ-chat-list" ref={list} role="log" aria-live="polite">
        {!shown.length && !running && (
          <p className="occ-chat-empty">Ask for a change in your own words, for example “make the second scene calmer” or “show a dog instead of the cat”. You can keep editing the timeline while it works.</p>
        )}
        {shown.map((m, i) => <ChatMessage key={i} msg={m} running={running} />)}
        <ChatRunStatus running={running} liveTool={running && steps.length ? { name: 'director', partial: steps[steps.length - 1] } : null}
          streamingThinking={false} phraseSeed={said.length} startedAt={startedAt || Date.now()} />
        {!!(changedScenes.length || removedScenes.length) && !running && (
          <div className="occ-chat-scenes" role="group" aria-label="Scenes changed by the Director">
            <span className="small muted">Changed:</span>
            {changedScenes.map((scene) => <button type="button" className="btn ghost sm" key={scene} onClick={() => {
              window.dispatchEvent(new CustomEvent('vt-select-scene', { detail: scene }));
              window.dispatchEvent(new CustomEvent('vt-occ-select-item', { detail: `scene:${scene}` }));
              document.querySelector<HTMLElement>(`[data-item-id="scene:${CSS.escape(scene)}"]`)?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
            }}>{sceneName(scene)}</button>)}
            {removedScenes.map((scene) => <span className="small muted" key={`removed:${scene}`}>{sceneName(scene)} removed</span>)}
          </div>
        )}
        {historyAction && onHistoryAction && !running && (
          <div className="occ-chat-change-actions">
            <button type="button" className="btn ghost sm" data-testid="director-history" disabled={historyBusy} onClick={async () => {
              setHistoryBusy(true);
              try { await onHistoryAction(); } finally { setHistoryBusy(false); }
            }}>{historyBusy ? 'Restoring…' : historyAction === 'undo' ? "Undo the Director's change" : "Redo the Director's change"}</button>
            <span className="small muted">{historyAction === 'undo' ? 'Ctrl+Z does the same.' : 'Ctrl+Shift+Z does the same.'}</span>
          </div>
        )}
      </div>
      <form className="occ-chat-compose" onSubmit={(e) => { e.preventDefault(); void send(); }}>
        <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={3} aria-label="Message to the director" data-cc-shortcut-surface="agent-input"
          placeholder={running ? 'The director is working…' : 'Tell the director what to change'} disabled={running}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(); } }} />
        <button type="submit" className="btn primary" disabled={running || !draft.trim()}>{running ? 'Working…' : 'Send'}</button>
      </form>
    </section>
  );
}
