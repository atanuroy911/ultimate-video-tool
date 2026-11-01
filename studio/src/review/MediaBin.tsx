import { AudioLines, Eraser, Film, Image as ImageIcon, Layers as LayersIcon, Search, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { del, get, patch, post } from "../api";
import { useFetch } from "../hooks";
import { toast } from "../store";
import type { MediaItem } from "../types";
import { Modal, Seg, Spinner } from "../ui";
import CatalogList from "./CatalogList";
import MotionClip from "./MotionClip";

interface StockHit {
  id: string;
  provider: string;
  kind: "image" | "video";
  thumb: string | null;
  url: string;
  credit: string;
  query?: string;
}

/** The project's pictures, GIFs and clips (your own, or free stock). The planner places them; Show as lets you choose how. */
export default function MediaBin({ id, onClose, onChange, onAddToTimeline }: { id: string; onClose: () => void; onChange: () => void; onAddToTimeline?: (m: MediaItem) => void }) {
  const media = useFetch<MediaItem[]>(`/api/projects/${id}/media`);
  const sounds = useFetch<MediaItem[]>(`/api/projects/${id}/sounds`);
  const soundIn = useRef<HTMLInputElement>(null);
  const stockStatus = useFetch<Record<string, boolean>>("/api/stock/status");
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState("");
  const [kind, setKind] = useState<"image" | "video" | "clipart">("image");
  const [hits, setHits] = useState<StockHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [ideas, setIdeas] = useState<string[]>([]);
  useEffect(() => {
    get<string[]>(`/api/projects/${id}/stock/suggest`).then(setIdeas).catch(() => setIdeas([]));
  }, [id]);
  const fileIn = useRef<HTMLInputElement>(null);
  const hasStock = !!stockStatus.data && Object.values(stockStatus.data).some(Boolean);

  const refresh = () => {
    media.refetch();
    sounds.refetch();
    onChange();
  };

  const upload = async (files: FileList | File[]) => {
    setBusy(true);
    for (const f of Array.from(files)) {
      const fd = new FormData();
      fd.append("file", f);
      try {
        const res = await fetch(`/api/projects/${id}/media`, { method: "POST", body: fd });
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Could not add " + f.name);
      } catch (e: any) {
        toast(e.message, "err", 6000);
      }
    }
    setBusy(false);
    refresh();
  };

  const [cutting, setCutting] = useState<string | null>(null);
  /** Remove the background of a picture: a new transparent picture is added next to it (the first time downloads a 180 MB model). */
  const cutOut = async (m: MediaItem) => {
    setCutting(m.id);
    try {
      const j = await post<{ id: string }>(`/api/projects/${id}/media/${m.id}/cutout`);
      for (let i = 0; i < 600; i++) {
        await new Promise((res) => setTimeout(res, 1500));
        const st = await get<{ status: string; error?: string }>(`/api/jobs/${j.id}`);
        if (st.status === "error") throw new Error(st.error);
        if (st.status === "done") break;
      }
      toast("Background removed: the new picture is in the bin", "ok", 4000);
      refresh();
    } catch (e: any) {
      toast(e.errors?.[0] || e.message, "err", 7000);
    } finally {
      setCutting(null);
    }
  };

  const uploadSounds = async (files: FileList | File[]) => {
    setBusy(true);
    for (const f of Array.from(files)) {
      const fd = new FormData();
      fd.append("file", f);
      try {
        const res = await fetch(`/api/projects/${id}/sounds`, { method: "POST", body: fd });
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Could not add " + f.name);
      } catch (e: any) {
        toast(e.message, "err", 6000);
      }
    }
    setBusy(false);
    refresh();
  };

  const find = async () => {
    if (!q.trim()) return;
    setSearching(true);
    try {
      setHits(await get<StockHit[]>(`/api/projects/${id}/stock/search?q=${encodeURIComponent(q)}&kind=${kind}`));
    } catch (e: any) {
      toast(e.message, "err", 7000);
      setHits(null);
    } finally {
      setSearching(false);
    }
  };

  const addStock = async (h: StockHit) => {
    setBusy(true);
    try {
      await post(`/api/projects/${id}/stock/add`, { item: { ...h, query: q }, caption: q });
      toast("Added to the media bin", "ok", 2500);
      refresh();
    } catch (e: any) {
      toast(e.message, "err", 7000);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Pictures and clips" onClose={onClose} wide footer={<button className="btn primary" onClick={onClose}>Done</button>}>
      <div className="col" style={{ gap: 14 }}>
        <p className="muted small" style={{ margin: 0 }}>
          Add photos, GIFs or video clips. The planner puts each one in the scene that mentions it (use the caption words) or spreads them over the video, and text on top
          stays readable automatically. After adding, press <strong>Auto-design</strong>, or choose <strong>Show as</strong> on a scene.
        </p>
        <div className="row">
          <button className="btn" disabled={busy} onClick={() => fileIn.current?.click()}>{busy ? <Spinner /> : <Upload size={14} />} Add files…</button>
          <button className="btn" disabled={busy || !(media.data ?? []).length} title="The vision model writes a caption and tags for pictures that have none, so they can be matched to what is said"
            onClick={async () => {
              setBusy(true);
              try {
                const j = await post<{ id: string }>(`/api/projects/${id}/media/describe`);
                for (let i = 0; i < 200; i++) {
                  await new Promise((r) => setTimeout(r, 1000));
                  const st = await get<{ status: string; error: string; result?: { described: string[]; error?: string } }>(`/api/jobs/${j.id}`);
                  if (st.status === "error") throw new Error(st.error);
                  if (st.status === "done") {
                    toast(st.result?.error ? `Described ${st.result.described.length}. ${st.result.error}` : `Described ${st.result?.described.length ?? 0} picture(s)`, st.result?.error ? "info" : "ok", 5000);
                    break;
                  }
                }
                refresh();
              } catch (e: any) {
                toast(e.message, "err", 6000);
              } finally {
                setBusy(false);
              }
            }}>Describe with AI</button>
          <input ref={fileIn} type="file" multiple hidden accept="image/*,video/*,.gif" onChange={(e) => e.target.files && upload(e.target.files)} />
        </div>

        <div className="media-grid" {...((media.data?.length ?? 0) > 0 ? { role: "list", "aria-label": "Media bin" } : {})}>
          {(media.data ?? []).map((m) => (
            <div key={m.id} className="media-card" role="listitem">
              <div className="media-thumb">
                {m.kind === "image" ? <img src={m.url} alt={m.caption || m.id} /> : <video src={m.url} muted preload="metadata" />}
                <span className="chip">{m.kind === "image" ? <ImageIcon size={11} /> : <Film size={11} />} {m.role === "a_roll" ? "A-roll (speaker)" : m.kind === "gif" ? "GIF" : m.kind}{m.duration ? ` · ${m.duration.toFixed(1)}s` : ""}</span>
              </div>
              <input
                type="text" className="bn" defaultValue={m.caption} placeholder="Caption: words from the sentence to match" aria-label={`Caption for ${m.id}`}
                onBlur={(e) => e.target.value !== m.caption && patch(`/api/projects/${id}/media/${m.id}`, { caption: e.target.value }).then(refresh)}
              />
              {m.credit && <span className="small muted">© {m.credit} · {m.source}</span>}
              {onAddToTimeline && <button className="btn sm" aria-label={`Put ${m.id} on the timeline`} onClick={() => onAddToTimeline(m)}><LayersIcon size={13} /> Add to timeline</button>}
              {m.kind === "image" && <button className="btn sm ghost" disabled={cutting !== null} aria-label={`Remove the background of ${m.id}`} title="Keep the main subject, make the rest transparent" onClick={() => cutOut(m)}>{cutting === m.id ? <Spinner /> : <Eraser size={13} />} Cut out</button>}
              <button className="btn sm ghost" aria-label={`Remove ${m.id}`} onClick={() => del(`/api/projects/${id}/media/${m.id}`).then(refresh).catch((e: any) => toast(e.message, "err"))}><Trash2 size={13} /> Remove</button>
            </div>
          ))}
          {media.data && media.data.length === 0 && <div className="muted small" style={{ gridColumn: "1 / -1" }}>Nothing yet. Drop in a few pictures to make the video less abstract.</div>}
        </div>

        <MotionClip projectId={id} media={media.data ?? []} onChange={refresh} onAddToTimeline={onAddToTimeline} />

        <div className="group" style={{ gap: 10 }}>
          <h3>Sounds</h3>
          <p className="small muted" style={{ margin: 0 }}>Music, effects or a voice-over. A sound goes on a sound track of the timeline, where you can move, trim, fade and set its volume.</p>
          <div className="row">
            <button className="btn" disabled={busy} onClick={() => soundIn.current?.click()}><Upload size={14} /> Add audio files…</button>
            <input ref={soundIn} type="file" multiple hidden accept="audio/*,.mp3,.wav,.m4a,.ogg,.flac,.aac,.opus" onChange={(e) => e.target.files && uploadSounds(e.target.files)} />
          </div>
          <div className="col" style={{ gap: 6 }} {...((sounds.data?.length ?? 0) > 0 ? { role: "list", "aria-label": "Sounds" } : {})}>
            {(sounds.data ?? []).map((m) => (
              <div key={m.id} className="row" role="listitem" style={{ gap: 8 }}>
                <AudioLines size={15} aria-hidden />
                <audio src={m.url} controls preload="none" style={{ height: 30, maxWidth: 220 }} aria-label={`Play ${m.caption || m.id}`} />
                <span className="grow small" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.caption || m.id} · {m.duration.toFixed(1)}s{m.credit ? ` · © ${m.credit}` : ""}</span>
                {onAddToTimeline && <button className="btn sm" aria-label={`Put ${m.id} on the timeline`} onClick={() => onAddToTimeline(m)}><LayersIcon size={13} /> Add to timeline</button>}
                <button className="btn sm ghost" aria-label={`Remove ${m.id}`} onClick={() => del(`/api/projects/${id}/sounds/${m.id}`).then(refresh).catch((e: any) => toast(e.errors?.[0] || e.message, "err"))}><Trash2 size={13} /></button>
              </div>
            ))}
            {sounds.data && sounds.data.length === 0 && <span className="small muted">No sounds yet.</span>}
          </div>
          <details>
            <summary style={{ cursor: "pointer", fontWeight: 600 }}>Free music and sound library</summary>
            <CatalogList kind="audio" action="Add to this video" label="Free music"
              onPick={async (e) => { const r = await post<{ id: string }>(`/api/projects/${id}/catalog/${e.id}/add`); toast(`Added ${r.id}`, "ok", 2500); refresh(); }} />
          </details>
        </div>

        <details className="group" style={{ gap: 10 }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>Free library (public domain and Creative Commons, no key needed)</summary>
          <p className="small muted">Every file has its licence and source recorded, and its link was downloaded and decoded to check it works. Credits are saved next to your exports.</p>
          <CatalogList kind="video" action="Add to this video" label="Free videos"
            onPick={async (e) => { const r = await post<{ id: string }>(`/api/projects/${id}/catalog/${e.id}/add`); toast(`Added ${r.id}`, "ok", 2500); refresh(); }} />
        </details>

        <div className="group" style={{ gap: 10 }}>
          <h3>Free stock footage</h3>
          {!hasStock ? (
            <span className="small muted">Optional. Add a free Pexels or Pixabay API key in Settings to search their free photos and videos here. Credits are saved next to every export.</span>
          ) : (
            <>
              <div className="row wrap">
                <div style={{ position: "relative", flex: 1, minWidth: 200 }}>
                  <Search size={14} style={{ position: "absolute", left: 9, top: 11, color: "var(--muted)" }} />
                  <input type="search" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && find()} placeholder="e.g. village market, office meeting" style={{ paddingLeft: 30 }} aria-label="Stock search" />
                </div>
                <Seg value={kind} onChange={setKind} label="Kind" options={[{ value: "image", label: "Photos" }, { value: "clipart", label: "Clipart" }, { value: "video", label: "Videos" }]} />
                <button className="btn" onClick={find} disabled={searching || !q.trim()}>{searching ? <Spinner /> : <Search size={14} />} Search</button>
              </div>
              {ideas.length > 0 && (
                <div className="row wrap" style={{ gap: 6 }} aria-label="Ideas from your script">
                  <span className="small muted">From your script:</span>
                  {ideas.map((w) => (
                    <button key={w} className="btn sm ghost" onClick={() => setQ(w)}>{w}</button>
                  ))}
                </div>
              )}
              {hits && (
                <div className="media-grid">
                  {hits.map((h) => (
                    <button key={h.id} className="media-card stock" onClick={() => addStock(h)} disabled={busy} aria-label={`Add ${h.provider} ${h.kind} by ${h.credit}`}>
                      <div className="media-thumb">{h.thumb ? <img src={h.thumb} alt="" /> : <Film size={24} />}</div>
                      <span className="small muted">{h.credit} · {h.provider}</span>
                    </button>
                  ))}
                  {hits.length === 0 && <span className="small muted">No results.</span>}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </Modal>
  );
}
