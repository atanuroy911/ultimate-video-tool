import { useEffect, useState } from "react";
import { get } from "../api";

/** The bounded tail (2,000 lines) of what ffmpeg, ComfyUI and the models said, secrets already removed by the server. */
export function TechnicalOutput({ pid, refresh }: { pid: string; refresh: number }) {
  const [text, setText] = useState("");
  useEffect(() => {
    get<{ text: string }>(`/api/projects/${pid}/calls/technical`).then((r) => setText(r.text)).catch(() => setText(""));
  }, [pid, refresh]);
  return <pre className="log-raw" data-testid="log-technical" aria-label="Technical output">{text || "Nothing recorded yet."}</pre>;
}
