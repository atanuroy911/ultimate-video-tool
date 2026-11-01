import { Check, Copy, Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { get } from "../api";
import { connStore, toast, useStore } from "../store";
import { Modal, copyText } from "../ui";
import type { Scene } from "../types";
import type { Review } from "./useReview";

function sceneSummary(s: Scene): string {
  const els = s.elements.map((e) => e.type.replace("_", " ")).join(" + ") || "captions only";
  return `${s.layout} · ${els} · ${s.transition_in.replace("_", " ")}`;
}

export default function Requests({ r, sceneIndexById }: { r: Review; sceneIndexById: Record<string, number> }) {
  const conn = useStore(connStore);
  const reqs = r.rq.data ?? [];
  const queued = reqs.filter((x) => x.status === "queued");
  const withAlts = reqs.filter((x) => x.status === "done" && x.alternatives_available > 0);
  const [alt, setAlt] = useState<{ rid: string; items: Scene[] } | null>(null);
  const say = conn.mcp?.say || "plan my pending videos";

  useEffect(() => {
    if (!alt) return;
  }, [alt]);

  if (!queued.length && !withAlts.length) return null;
  return (
    <div className="col" style={{ padding: "10px 16px 0", gap: 8 }}>
      {queued.length > 0 && (
        <div className="banner">
          <Sparkles size={16} color="var(--accent)" />
          <div className="grow">
            <strong>{queued.length === 1 ? "Request queued" : `${queued.length} requests queued`}</strong>
            <div className="small muted">
              {queued.map((q) => (q.kind === "full" ? "whole video" : `scene ${(sceneIndexById[q.scene_id || ""] ?? 0) + 1}`)).join(", ")}. In Codex or Claude Code say: <code>{say}</code>
              {!conn.mcp?.connected && " (No assistant has used the connector recently. See Settings for setup.)"}
            </div>
          </div>
          <button className="btn sm" onClick={() => copyText(say)}>
            <Copy size={13} /> Copy
          </button>
          <button className="btn ghost icon sm" aria-label="Cancel requests" onClick={() => queued.forEach((q) => r.dropRequest(q.id))}>
            <X size={14} />
          </button>
        </div>
      )}
      {withAlts.map((q) => (
        <div key={q.id} className="banner ok">
          <Check size={16} color="var(--ok)" />
          <div className="grow">
            <strong>Assistant sent {q.alternatives_available} options for scene {(sceneIndexById[q.scene_id || ""] ?? 0) + 1}</strong>
          </div>
          <button
            className="btn sm primary"
            onClick={async () => setAlt({ rid: q.id, items: await get<Scene[]>(`/api/projects/${r.id}/requests/${q.id}/alternatives`) })}
          >
            Choose
          </button>
          <button className="btn ghost icon sm" aria-label="Dismiss" onClick={() => r.dropRequest(q.id)}>
            <X size={14} />
          </button>
        </div>
      ))}

      {alt && (
        <Modal title="Choose a version" wide onClose={() => setAlt(null)}>
          <div className="grid-cards" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))" }}>
            {alt.items.map((s, i) => (
              <div key={i} className="card card-pad col">
                <strong>Option {i + 1}</strong>
                <span className="small muted">{sceneSummary(s)}</span>
                <div className="col" style={{ gap: 4 }}>
                  {s.elements.map((e, k) => (
                    <span key={k} className="small bn">
                      <span className="chip accent">{e.type.replace("_", " ")}</span> {String(e.text ?? e.value ?? e.label ?? e.name ?? "").slice(0, 30)}
                    </span>
                  ))}
                </div>
                <button
                  className="btn primary"
                  onClick={async () => {
                    const res = await r.applyAlt(alt.rid, i);
                    if (res) {
                      await r.dropRequest(alt.rid);
                      setAlt(null);
                      toast("Applied. You can undo this.", "ok");
                    }
                  }}
                >
                  Use this one
                </button>
              </div>
            ))}
          </div>
        </Modal>
      )}
    </div>
  );
}
