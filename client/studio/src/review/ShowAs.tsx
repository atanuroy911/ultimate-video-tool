import { LayoutTemplate } from "lucide-react";
import { useEffect, useState } from "react";
import { get, post } from "../api";
import { toast } from "../store";
import type { MediaItem, Scene } from "../types";
import type { Review } from "./useReview";

interface Option {
  id: string;
  label: string;
  fit: number;
  current: boolean;
}

const MEDIA_TYPES = new Set(["media_hero", "media_frame", "device"]);

/** Show the same sentences as another kind of scene: a chart, steps, a cartoon, a picture... Only the types the sentences can support are offered. */
export default function ShowAs({ r, id, scene, media }: { r: Review; id: string; scene: Scene; media: MediaItem[] }) {
  const [opts, setOpts] = useState<Option[]>([]);
  const [busy, setBusy] = useState("");
  const [mediaId, setMediaId] = useState("");

  useEffect(() => {
    let live = true;
    get<Option[]>(`/api/projects/${id}/scenes/${scene.id}/shows`).then((o) => live && setOpts(o)).catch(() => live && setOpts([]));
    return () => {
      live = false;
    };
  }, [id, scene.id, scene.archetype, media.length]);

  useEffect(() => setMediaId((m) => (media.some((x) => x.id === m) ? m : media[0]?.id ?? "")), [media]);

  const all = [...opts];
  if (media.length) for (const [k, label] of [["media_hero", "Full-screen picture"], ["media_frame", "Framed picture"], ["device", "Device mockup"]] as const) if (!all.some((o) => o.id === k)) all.push({ id: k, label, fit: 0.5, current: scene.archetype === k });

  const apply = async (o: Option) => {
    if (o.current && !MEDIA_TYPES.has(o.id)) return;
    setBusy(o.id);
    try {
      await post(`/api/projects/${id}/scenes/${scene.id}/reshow`, { archetype: o.id, media: MEDIA_TYPES.has(o.id) ? mediaId || undefined : undefined });
      r.reloadAll();
    } catch (e: any) {
      toast(e.message, "err", 6000);
    } finally {
      setBusy("");
    }
  };

  if (!all.length) return null;
  return (
    <div className="col" style={{ gap: 6 }}>
      <h3 className="row" style={{ gap: 6 }}><LayoutTemplate size={14} /> Show as</h3>
      <div className="row wrap" role="group" aria-label="Show this scene as" style={{ gap: 6 }}>
        {all.map((o) => (
          <button key={o.id} type="button" className={`btn sm ${o.current ? "primary" : ""}`} aria-pressed={o.current} disabled={!!busy} onClick={() => apply(o)} title={o.current ? "How it is shown now" : `Fit ${Math.round(o.fit * 100)}%`}>
            {busy === o.id ? "…" : o.label}
          </button>
        ))}
      </div>
      {media.length > 0 && all.some((o) => MEDIA_TYPES.has(o.id)) && (
        <label className="field"><span className="small muted">Picture to use for the picture types</span>
          <select value={mediaId} onChange={(e) => setMediaId(e.target.value)} aria-label="Picture to use">
            {media.map((m) => <option key={m.id} value={m.id}>{m.caption || m.id}</option>)}
          </select>
        </label>
      )}
      <span className="small muted">Only what the sentences can support is offered (a chart needs numbers, steps need a sequence).</span>
    </div>
  );
}
