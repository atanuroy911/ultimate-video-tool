import { Mic, Square, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { del } from "../api";
import { useFetch } from "../hooks";
import { toast } from "../store";
import { Spinner } from "../ui";

interface Voice { id: string; name: string; seconds: number; created: string; consent: boolean }

/** Voices you may clone: a few seconds of your own voice (or of someone who agreed), kept on this computer. Used as the "My own voice" engine for typed scripts. */
export default function MyVoices() {
  const list = useFetch<{ voices: Voice[]; available: boolean }>("/api/my-voices");
  const [name, setName] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [rec, setRec] = useState<{ mr: MediaRecorder; chunks: Blob[]; t0: number } | null>(null);
  const [secs, setSecs] = useState(0);
  const file = useRef<HTMLInputElement>(null);

  const send = async (blob: Blob, filename: string) => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", blob, filename);
      fd.append("name", name);
      fd.append("consent", String(consent));
      const res = await fetch("/api/my-voices", { method: "POST", body: fd });
      const j = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(j?.detail?.errors?.[0] || j?.detail || "Could not add this voice");
      toast(`Added the voice "${j.name}"`, "ok", 3000);
      setName("");
      setConsent(false);
      list.refetch();
    } catch (e: any) {
      toast(e.message, "err", 7000);
    } finally {
      setBusy(false);
    }
  };

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      mr.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        void send(new Blob(chunks, { type: mr.mimeType || "audio/webm" }), "recording.webm");
        setRec(null);
      };
      mr.start();
      const t0 = Date.now();
      setRec({ mr, chunks, t0 });
      setSecs(0);
      const tick = window.setInterval(() => { setSecs((Date.now() - t0) / 1000); if (mr.state === "inactive") window.clearInterval(tick); }, 250);
    } catch {
      toast("The microphone could not be opened. Allow it in the browser, or upload a recording instead.", "err", 6000);
    }
  };

  const ready = consent && name.trim().length > 0 && !busy;
  return (
    <section id="voices" className="card card-pad col" style={{ gap: 12 }}>
      <h2>My own voice (cloning)</h2>
      <p className="muted small" style={{ margin: 0 }}>
        Record or upload 10 to 30 seconds of clear speech in English and the app can read typed scripts in that voice, offline. Only use <strong>your own voice</strong> or the voice of
        someone who agreed. The recording stays on this computer.
      </p>
      {list.data && !list.data.available && (
        <div className="banner" role="note">Voice cloning cannot run on this computer (ONNX Runtime is missing). Reinstall the app's Python packages.</div>
      )}
      <div className="row wrap" style={{ gap: 10 }}>
        <label className="field" style={{ minWidth: 200 }}><span>Name of the voice</span>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={40} aria-label="Name of the voice" placeholder="e.g. My voice" />
        </label>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} aria-label="This is my own voice, or the speaker allowed it" />
          <span className="small">This is my own voice, or the speaker allowed me to use it.</span>
        </label>
      </div>
      <div className="row wrap" style={{ gap: 8 }}>
        {!rec ? (
          <button className="btn" disabled={!ready} onClick={start}><Mic size={14} /> Record</button>
        ) : (
          <button className="btn danger" onClick={() => rec.mr.stop()}><Square size={14} /> Stop and save ({secs.toFixed(0)} s)</button>
        )}
        <button className="btn" disabled={!ready || !!rec} onClick={() => file.current?.click()}>{busy ? <Spinner /> : <Upload size={14} />} Upload a recording…</button>
        <input ref={file} type="file" accept="audio/*,.wav,.mp3,.m4a,.ogg,.flac,.webm" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) void send(f, f.name); e.target.value = ""; }} />
      </div>
      <div className="col" style={{ gap: 6 }} {...((list.data?.voices.length ?? 0) > 0 ? { role: "list", "aria-label": "My voices" } : {})}>
        {(list.data?.voices ?? []).map((v) => (
          <div key={v.id} className="row" role="listitem" style={{ gap: 10, alignItems: "center" }}>
            <strong style={{ minWidth: 120 }}>{v.name}</strong>
            <audio src={`/api/my-voices/${v.id}/sample`} controls preload="none" style={{ height: 30 }} aria-label={`Listen to ${v.name}`} />
            <span className="small muted">{v.seconds} s</span>
            <span className="grow" />
            <button className="btn sm ghost" aria-label={`Delete the voice ${v.name}`} onClick={() => del(`/api/my-voices/${v.id}`).then(() => list.refetch()).catch((e: any) => toast(e.message, "err"))}><Trash2 size={13} /></button>
          </div>
        ))}
        {list.data && list.data.voices.length === 0 && <span className="small muted">No voices yet.</span>}
      </div>
    </section>
  );
}
