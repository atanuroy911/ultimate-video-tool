import { useEffect, useRef, useState } from "react";

/** Edit anything as JSON: it is applied only when it parses, and the server still validates it. Used where no form exists yet, and as the
 *  "everything" view of an element, a story item or a scene, so no part of a layer is out of reach. */
export default function JsonField({ title, value, set, rows = 4 }: { title: string; value: any; set: (v: any) => void; rows?: number }) {
  const show = (v: any) => (v === undefined ? "" : JSON.stringify(v, null, 1));
  const [text, setText] = useState(() => show(value));
  const [bad, setBad] = useState(false);
  const sent = useRef<string | null>(null);                  // what this field last applied: its echo must not reformat what is being typed
  const incoming = JSON.stringify(value ?? null);
  useEffect(() => {
    if (incoming === sent.current) return;
    setText(show(value));
    setBad(false);
  }, [incoming]); // eslint-disable-line react-hooks/exhaustive-deps
  const change = (raw: string) => {
    setText(raw);
    if (!raw.trim()) { setBad(false); sent.current = "null"; set(undefined); return; }
    try {
      const v = JSON.parse(raw);
      setBad(false);
      sent.current = JSON.stringify(v);
      set(v);
    } catch {
      setBad(true);
    }
  };
  return (
    <label className="se-f json-field">
      <span>{title}</span>
      <textarea rows={rows} className={`mono${bad ? " bad" : ""}`} value={text} spellCheck={false} onChange={(e) => change(e.target.value)} />
      {bad && <small className="se-bad">Not valid JSON yet; nothing is saved until it is.</small>}
    </label>
  );
}
