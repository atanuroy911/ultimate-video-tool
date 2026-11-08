import { Check, ExternalLink, Film, Image as ImageIcon, Music, RefreshCw } from "lucide-react";
import { useState } from "react";
import { get, post } from "../api";
import type { JobInfo } from "../types";
import { useFetch } from "../hooks";
import { toast } from "../store";
import { Spinner } from "../ui";

export interface CatalogEntry {
  id: string;
  kind: "video" | "audio" | "image";
  role: string;
  title: string;
  source: string;
  page_url: string;
  licence: string;
  creator: string;
  attribution: string;
  status: "ok" | "failed" | null;
  validated_at: string | null;
  error?: string;
  bytes?: number;
  format?: { container?: string; duration?: number; video?: { codec: string; width: number; height: number; fps: number } | null; audio?: { codec: string; sample_rate: number; channels: number } | null };
}

/** Free media with a known licence and a checked link. `onPick` runs the action for one entry (add to the media bin, install as music, make a video from it). */
export default function CatalogList({ kind, role, action, onPick, label }: { kind: string; role?: string; action: string; onPick: (e: CatalogEntry) => Promise<unknown>; label: string }) {
  const q = useFetch<{ entries: CatalogEntry[]; summary: { ok: number; failed: number } }>(`/api/catalog?kind=${kind}${role ? `&role=${role}` : ""}`);
  const [busy, setBusy] = useState<string>("");
  const entries = q.data?.entries ?? [];
  const run = async (e: CatalogEntry) => {
    setBusy(e.id);
    try {
      await onPick(e);
    } catch (err: any) {
      toast(err.errors?.[0] || err.message, "err", 7000);
      q.refetch();
    } finally {
      setBusy("");
    }
  };
  const recheck = async (e: CatalogEntry) => {
    setBusy("check-" + e.id);
    try {
      await post(`/api/catalog/${e.id}/check`);
      q.refetch();
    } catch (err: any) {
      toast(err.message, "err");
    } finally {
      setBusy("");
    }
  };
  /* The same job as `vt catalog refresh` (POST /api/catalog/refresh): look for new free media and check every link again. */
  const [finding, setFinding] = useState("");
  const findMore = async () => {
    setFinding("Starting…");
    try {
      let j = await post<JobInfo>("/api/catalog/refresh");
      while (j.status === "queued" || j.status === "running") {
        setFinding(j.msg || "Looking for free media…");
        await new Promise((r) => setTimeout(r, 1500));
        j = await get<JobInfo>(`/api/jobs/${j.id}`);
      }
      if (j.status === "error") toast(j.error || "Could not update the free media.", "err", 7000);
      else if (j.status === "done") toast("Free media updated.", "ok");
      q.refetch();
    } catch (err: any) {
      toast(err.message, "err", 7000);
    } finally {
      setFinding("");
    }
  };
  return (
    <div className="col" style={{ gap: 8 }} aria-label={label}>
      {q.loading && <div className="row muted"><Spinner /> Loading…</div>}
      {q.data && entries.length === 0 && !finding && <span className="small muted">No free media yet.</span>}
      {q.data && (
        <div className="row" style={{ gap: 8 }}>
          <button className="btn sm" disabled={!!finding || !!busy} onClick={findMore} title="Looks for new free media and checks every link again (downloads each file, so it can take a few minutes)">
            {finding ? <Spinner size={12} /> : <RefreshCw size={13} />} Look for new free media
          </button>
          {finding && <span className="small muted" role="status">{finding}</span>}
        </div>
      )}
      <div className="catalog-grid">
        {entries.map((e) => {
          const f = e.format;
          const dim = f?.video ? `${f.video.width}×${f.video.height}` : "";
          return (
            <div key={e.id} className={`card card-pad catalog-card ${e.status === "failed" ? "bad" : ""}`}>
              <div className="row" style={{ gap: 6 }}>
                {e.kind === "video" ? <Film size={14} /> : e.kind === "audio" ? <Music size={14} /> : <ImageIcon size={14} />}
                <strong className="grow small" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={e.title}>{e.title}</strong>
                {e.status === "ok" ? <span className="chip ok"><Check size={11} /> checked</span> : <span className="chip warn" title={e.error}>link failed</span>}
              </div>
              <span className="small muted">{[f?.duration ? `${f.duration.toFixed(0)} s` : "", dim, f?.video?.codec, f?.audio ? `${f.audio.codec} ${Math.round(f.audio.sample_rate / 1000)} kHz` : "", e.bytes ? `${(e.bytes / 1e6).toFixed(1)} MB` : ""].filter(Boolean).join(" · ")}</span>
              <span className="small muted">{e.licence} · {e.creator}</span>
              <div className="row" style={{ gap: 6 }}>
                <button className="btn sm primary" disabled={e.status !== "ok" || !!busy} onClick={() => run(e)}>{busy === e.id ? <Spinner size={12} /> : null} {action}</button>
                <a className="btn sm ghost icon" href={e.page_url} target="_blank" rel="noreferrer" aria-label={`Open the source page of ${e.title}`}><ExternalLink size={13} /></a>
                <button className="btn sm ghost icon" aria-label={`Check ${e.title} again`} title="Download and decode it again" disabled={!!busy} onClick={() => recheck(e)}>{busy === "check-" + e.id ? <Spinner size={12} /> : <RefreshCw size={13} />}</button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
