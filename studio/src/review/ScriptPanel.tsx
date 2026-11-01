import { ClipboardPaste, Copy, Mic, Undo2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { fmtTime, post, put } from "../api";
import { useFetch } from "../hooks";
import { toast } from "../store";
import { copyText, Modal, Spinner } from "../ui";
import type { Review } from "./useReview";

interface Change { id: string; from: string; to: string | null }
interface Result { changed: number; changes: Change[]; applied: boolean }

/** The whole text, one box per sentence: paste the correct text of any sentence and it is lined up with the real word times. Follows the playback. */
export default function ScriptPanel({ r, time, playing, seek }: { r: Review; time: number; playing: boolean; seek: (t: number) => void }) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const mine = useFetch<{ voices: { id: string; name: string }[]; available: boolean }>("/api/my-voices");
  const [saying, setSaying] = useState<string | null>(null);
  const voice = mine.data?.available ? mine.data.voices[0] : undefined;
  /** Speak this sentence again in the saved voice: the new audio goes on a sound track and the original words are muted. */
  const sayAgain = async (id: string, start: number, end: number, text: string) => {
    if (!voice) return;
    setSaying(id);
    try {
      const j = await post<{ id: string }>(`/api/projects/${r.id}/voice/overdub`, { text, voice: voice.id, start, end });
      for (let i = 0; i < 600; i++) {
        await new Promise((res) => setTimeout(res, 1500));
        const st = await fetch(`/api/jobs/${j.id}`).then((x) => x.json());
        if (st.status === "error") throw new Error(st.error);
        if (st.status === "done") break;
      }
      r.reloadAll();
      toast(`Said again in ${voice.name}'s voice. It is on the "My voice" sound track.`, "ok", 5000);
    } catch (e: any) {
      toast(e.errors?.[0] || e.message, "err", 8000);
    } finally {
      setSaying(null);
    }
  };
  const refs = useRef<Record<string, HTMLDivElement | null>>({});
  const wrap = useRef<HTMLDivElement>(null);

  const wordsById = useMemo(() => new Map(r.words.map((w) => [w.id, w])), [r.words]);
  const rows = useMemo(() => r.beats.map((b) => ({ id: b.id, start: b.start, end: b.end, text: b.word_ids.map((i) => wordsById.get(i)).filter((w) => w && !w.cut).map((w) => w!.text).join(" ") })), [r.beats, wordsById]);
  const cur = rows.find((b) => time >= b.start - 0.02 && time <= b.end + 0.3)?.id;

  // keep the sentence being spoken in view while playing (only inside this panel)
  useEffect(() => {
    const c = wrap.current, el = cur ? refs.current[cur] : null;
    if (!playing || !c || !el) return;
    const top = el.offsetTop - c.scrollTop;
    if (top < c.clientHeight * 0.08 || top > c.clientHeight * 0.6) c.scrollTo({ top: Math.max(0, el.offsetTop - c.clientHeight * 0.25), behavior: "smooth" });
  }, [cur, playing]);

  const save = async (id: string, text: string) => {
    const row = rows.find((x) => x.id === id);
    const clean = text.trim();
    if (!row || !clean || clean === row.text) return setDrafts((d) => { const n = { ...d }; delete n[id]; return n; });
    setSaving(id);
    try {
      const res = await put<Result>(`/api/projects/${r.id}/transcript`, { text: clean, beat: id });
      toast(res.changed ? `Corrected ${res.changed} word${res.changed === 1 ? "" : "s"}` : "No change", "ok", 2000);
      r.reloadAll();
    } catch (e: any) {
      toast(e.errors?.length ? e.errors.join(" · ") : e.message, "err", 5000);
    } finally {
      setSaving(null);
      window.setTimeout(() => setDrafts((d) => { const n = { ...d }; delete n[id]; return n; }), 1500);        // keep what was typed on screen until the corrected words have been fetched
    }
  };
  const undo = async () => {
    try { await post(`/api/projects/${r.id}/transcript/undo`); r.reloadAll(); toast("Text change undone", "ok", 2000); } catch (e: any) { toast(e.errors?.join(" ") || e.message, "err"); }
  };

  return (
    <div className="script-panel" style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div className="row" style={{ padding: "10px 12px", gap: 6, flexWrap: "wrap", borderBottom: "0.5px solid var(--border)" }}>
        <button className="btn sm" onClick={() => setAll(true)}><ClipboardPaste size={13} /> Paste all text</button>
        <button className="btn sm ghost" onClick={() => copyText(rows.map((x) => x.text).join("\n"), "Text copied")}><Copy size={13} /> Copy</button>
        <button className="btn sm ghost" onClick={undo} aria-label="Undo the last text change"><Undo2 size={13} /> Undo</button>
        <span className="small muted" style={{ flex: "1 1 100%" }}>Paste the correct text into a sentence and press Ctrl+Enter or click away. Timing stays with the voice.</span>
      </div>
      <div ref={wrap} style={{ overflow: "auto", flex: 1, padding: "6px 10px 40px", position: "relative" }} {...(rows.length ? { role: "list", "aria-label": "Sentences" } : {})}>
        {rows.map((x, i) => (
          <div key={x.id} ref={(el) => { refs.current[x.id] = el; }} role="listitem" className={`script-row ${cur === x.id ? "cur" : ""}`}
            style={{ display: "flex", gap: 8, padding: "6px 4px", borderRadius: 8, background: cur === x.id ? "var(--accent-soft)" : "transparent" }}>
            <button className="btn ghost sm" style={{ flex: "0 0 auto", fontVariantNumeric: "tabular-nums", minWidth: 44 }} onClick={() => seek(x.start)} title="Go to this sentence" aria-label={`Go to sentence ${i + 1}`}>{fmtTime(x.start)}</button>
            <textarea aria-label={`Sentence ${i + 1}`} className="bn" rows={Math.max(1, Math.min(6, Math.ceil((drafts[x.id] ?? x.text).length / 34)))} value={drafts[x.id] ?? x.text}
              onChange={(e) => setDrafts((d) => ({ ...d, [x.id]: e.target.value }))} onBlur={(e) => drafts[x.id] != null && save(x.id, e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); (e.target as HTMLTextAreaElement).blur(); } e.stopPropagation(); }}
              style={{ flex: 1, resize: "none", font: "inherit", border: "0.5px solid var(--border)", borderRadius: 8, padding: "6px 8px", background: "var(--bg-elev, var(--bg))", color: "inherit", outline: drafts[x.id] != null ? "2px solid var(--accent)" : "none" }} />
            {saving === x.id && <Spinner />}
            {voice && (
              <button className="btn ghost sm" style={{ flex: "0 0 auto" }} disabled={saying !== null} onClick={() => sayAgain(x.id, x.start, x.end, drafts[x.id] ?? x.text)}
                aria-label={`Say sentence ${i + 1} again in my voice`} title={`Say this sentence again in ${voice.name}'s voice (the original is muted)`}>{saying === x.id ? <Spinner /> : <Mic size={13} />}</button>
            )}
          </div>
        ))}
        {!rows.length && <p className="muted small" style={{ padding: 14 }}>There is no text yet. Process the audio first.</p>}
      </div>
      {all && <PasteAll r={r} onClose={() => setAll(false)} />}
    </div>
  );
}

function PasteAll({ r, onClose }: { r: Review; onClose: () => void }) {
  const [text, setText] = useState("");
  const [res, setRes] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const check = async () => {
    setBusy(true);
    try { setRes(await put<Result>(`/api/projects/${r.id}/transcript`, { text, dry: true })); } catch (e: any) { toast(e.errors?.join(" · ") || e.message, "err"); } finally { setBusy(false); }
  };
  const apply = async () => {
    setBusy(true);
    try { await put(`/api/projects/${r.id}/transcript`, { text }); r.reloadAll(); toast("Text corrected", "ok", 2000); onClose(); } catch (e: any) { toast(e.errors?.join(" · ") || e.message, "err"); } finally { setBusy(false); }
  };
  return (
    <Modal title="Paste the whole correct text" onClose={onClose} wide footer={<>
      <button className="btn" disabled={busy || !text.trim()} onClick={check}>{busy ? <Spinner /> : null} Show what changes</button>
      <button className="btn primary" disabled={busy || !res || !res.changed} onClick={apply}>Apply {res?.changed ? `${res.changed} changes` : ""}</button></>}>
      <div className="col" style={{ gap: 10 }}>
        <p className="muted small" style={{ margin: 0 }}>Words that match keep their real time. Different words are lined up around them. Nothing is applied until you press Apply.</p>
        <textarea aria-label="The correct text" rows={9} value={text} onChange={(e) => { setText(e.target.value); setRes(null); }} className="bn" style={{ width: "100%", font: "inherit" }} placeholder="Paste the full correct text here" />
        {res && (
          <div role="status" style={{ maxHeight: 200, overflow: "auto" }}>
            <strong>{res.changed ? `${res.changed} word${res.changed === 1 ? "" : "s"} will change` : "Nothing would change"}</strong>
            <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{res.changes.slice(0, 80).map((c) => <li key={c.id}><s className="muted">{c.from}</s> {c.to == null ? <em>removed</em> : <>→ {c.to}</>}</li>)}</ul>
          </div>
        )}
      </div>
    </Modal>
  );
}
