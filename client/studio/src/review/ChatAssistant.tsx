import { Copy } from "lucide-react";
import { useState } from "react";
import { get, post } from "../api";
import { toast } from "../store";
import { Modal, Spinner, copyText } from "../ui";

/** For assistants without MCP (a chat window): copy a ready-made message, paste the JSON answer back. */
export default function ChatAssistant({ id, kind, onClose, onApplied }: { id: string; kind: string; onClose: () => void; onApplied: () => void }) {
  const [msg, setMsg] = useState<string>("");
  const [answer, setAnswer] = useState("");
  const [errs, setErrs] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setBusy(true);
    try {
      const t = await get<{ message: string }>(`/api/projects/${id}/script/task?kind=${kind}`);
      setMsg(t.message);
      await copyText(t.message, "Message copied. Paste it into your assistant's chat.");
    } catch (e: any) {
      toast(e.message, "err");
    } finally {
      setBusy(false);
    }
  };
  const apply = async () => {
    setBusy(true);
    setErrs([]);
    try {
      const r = await post<{ ok: boolean; errors?: string[] }>(`/api/projects/${id}/script/paste`, { json: answer });
      if (r.ok) {
        toast("Applied", "ok", 2500);
        onApplied();
        onClose();
      } else setErrs(r.errors ?? ["Not accepted."]);
    } catch (e: any) {
      setErrs([e.message]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Ask any chat assistant" onClose={onClose} wide footer={<button className="btn primary" disabled={busy || !answer.trim()} onClick={apply}>{busy ? <Spinner /> : null} Apply the answer</button>}>
      <div className="col" style={{ gap: 12 }}>
        <p className="muted" style={{ margin: 0 }}>
          1. Copy the message below into ChatGPT, Gemini, Claude.ai or any assistant. 2. Paste its JSON answer here. If something is wrong you will see exactly what to ask it to fix.
        </p>
        <div className="row">
          <button className="btn" onClick={load} disabled={busy}><Copy size={14} /> Copy the message for the assistant</button>
          {msg && <span className="small muted">{msg.length.toLocaleString()} characters copied</span>}
        </div>
        <textarea aria-label="Assistant's answer" rows={10} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Paste the assistant's answer here (JSON)" style={{ width: "100%", fontFamily: "monospace" }} />
        {errs.length > 0 && (
          <div className="banner err" role="alert">
            <div className="grow">
              <strong>Not accepted yet. Send this back to the assistant:</strong>
              <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{errs.map((e, i) => <li key={i}>{e}</li>)}</ul>
            </div>
            <button className="btn sm" onClick={() => copyText("Please fix exactly these problems and answer again with the complete JSON:\n- " + errs.join("\n- "))}><Copy size={13} /> Copy</button>
          </div>
        )}
      </div>
    </Modal>
  );
}
