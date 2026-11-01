import { RefreshCw, X } from "lucide-react";
import { useEffect, useState } from "react";
import { get, post, put } from "../api";
import { Panel } from "../ds";
import { useFetch } from "../hooks";
import { toast, useChanged } from "../store";
import { Spinner } from "../ui";

interface Ent { name: string; type: string; mentions: string[]; source: string; note?: string }
interface Sec { start_beat: string; end_beat: string; title: string }
interface Ctx { source: string; topic: string; summary: string; domain: string[]; mood: string; entities: Ent[]; sections: Sec[]; sentences: { beat: string; idea: string; importance: number; intent: string }[]; notes: string[] }
interface View { context: Ctx | null; stale: boolean; ai_available: boolean }
const TYPES = ["company", "product", "person", "place", "country", "language", "organisation", "event", "concept", "name"];

/** What the video is about, as the app understands it: topic, named things (with their type: "Amazon" is a company here, not the river), sections. The owner can correct all of it. */
export default function ContextPanel({ id }: { id: string }) {
  const v = useFetch<View>(`/api/projects/${id}/context`);
  useChanged(id, () => v.refetch());
  const [busy, setBusy] = useState(false);
  const [topic, setTopic] = useState("");
  const c = v.data?.context;
  useEffect(() => { if (c) setTopic(c.topic); }, [c?.topic]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = async () => {
    setBusy(true);
    try {
      const j = await post<{ id: string }>(`/api/projects/${id}/context`);
      for (let i = 0; i < 400; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        const st = await get<{ status: string; error?: string }>(`/api/jobs/${j.id}`);
        if (st.status === "error") throw new Error(st.error);
        if (st.status === "done") break;
      }
      await v.refetch();
      toast("Read the video again", "ok", 2500);
    } catch (e: any) {
      toast(e.errors?.[0] || e.message, "err", 6000);
    } finally {
      setBusy(false);
    }
  };
  const saveTopic = async () => {
    if (!c || topic.trim() === c.topic || !topic.trim()) return setTopic(c?.topic ?? "");
    try { await put(`/api/projects/${id}/context/topic`, { topic }); await v.refetch(); toast("Saved. New pictures will follow this.", "ok", 2500); } catch (e: any) { toast(e.errors?.[0] || e.message, "err"); }
  };
  const fix = async (name: string, body: { type?: string; remove?: boolean }) => {
    try { await put(`/api/projects/${id}/context/entity`, { name, ...body }); await v.refetch(); } catch (e: any) { toast(e.errors?.[0] || e.message, "err"); }
  };

  return (
    <Panel title="What the video is about" defaultOpen={false}
      actions={<button className="btn sm ghost" disabled={busy} onClick={refresh} aria-label="Read the video again" title="Read the video again (about half a minute with the AI)">{busy ? <Spinner /> : <RefreshCw size={13} />}</button>}>
      {!c ? (
        <span className="small muted">Not read yet. <button className="btn sm" disabled={busy} onClick={refresh}>{busy ? <Spinner /> : null} Read the video</button></span>
      ) : (
        <div className="col" style={{ gap: 10 }}>
          {v.data?.stale && <div className="banner" role="status">The words changed since this was read. <button className="btn sm" disabled={busy} onClick={refresh}>Read again</button></div>}
          <label className="field"><span>Topic <em className="muted" style={{ fontStyle: "normal" }}>({c.source === "ai" ? "understood with the AI" : c.source === "failed" ? "could not be read" : "rough, from the words"})</em></span>
            <input type="text" value={topic} aria-label="Topic of the video" maxLength={80} onChange={(e) => setTopic(e.target.value)} onBlur={saveTopic} onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} />
          </label>
          {c.summary && <span className="small muted">{c.summary}</span>}
          {c.domain.length > 0 && <div className="row wrap" style={{ gap: 6 }} aria-label="Fields">{c.domain.map((d) => <span key={d} className="chip">{d}</span>)}</div>}
          <div className="col" style={{ gap: 6 }}>
            <strong className="small">Named things</strong>
            {c.entities.length === 0 && <span className="small muted">None found.</span>}
            {c.entities.map((e) => (
              <div key={e.name} className="row" style={{ gap: 6, alignItems: "center" }}>
                <span style={{ minWidth: 90, fontWeight: 600 }}>{e.name}</span>
                <select value={e.type} aria-label={`What ${e.name} is`} onChange={(ev) => fix(e.name, { type: ev.target.value })} style={{ flex: 1 }}>
                  {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <span className="small muted" title={`Said ${e.mentions.length} time(s)`}>{e.mentions.length}x</span>
                <button className="btn sm ghost icon" aria-label={`${e.name} is not a name`} title="Not a name" onClick={() => fix(e.name, { remove: true })}><X size={13} /></button>
              </div>
            ))}
          </div>
          {c.sections.length > 0 && (
            <div className="col" style={{ gap: 4 }}>
              <strong className="small">Sections</strong>
              <ol style={{ margin: 0, paddingLeft: 18 }}>{c.sections.map((s, i) => <li key={i} className="small">{s.title || `Sentences ${s.start_beat.replace("b", "")}-${s.end_beat.replace("b", "")}`}</li>)}</ol>
            </div>
          )}
          {c.notes.length > 0 && <details><summary className="small muted">Notes</summary>{c.notes.map((n, i) => <div key={i} className="small muted">{n}</div>)}</details>}
        </div>
      )}
    </Panel>
  );
}
