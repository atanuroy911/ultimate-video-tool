import { Brush, Image as ImageIcon, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { get, post } from "../api";
import { useT } from "../i18n";
import { toast } from "../store";
import { Spinner } from "../ui";

/* Change the picture of one scene without redoing the video: draw it again, describe it differently, go back to an earlier try, or use your own picture. */
interface Info {
  scene: string; draw: string; media: string | null; url: string | null; reel: boolean;
  tries: { media: string; url: string; draw: string; current: boolean }[];
}

export default function PictureTools({ pid, sid, media, onChanged }: { pid: string; sid: string; media: { id: string; url: string; caption?: string }[]; onChanged: () => void }) {
  const tr = useT();
  const [info, setInfo] = useState<Info | null>(null);
  const [draw, setDraw] = useState("");
  const [job, setJob] = useState<string | null>(null);
  const [own, setOwn] = useState(false);
  const load = useCallback(() => get<Info>(`/api/projects/${pid}/scenes/${sid}/picture`).then((d) => { setInfo(d); setDraw(d.draw); }).catch(() => setInfo(null)), [pid, sid]);
  useEffect(() => { setJob(null); setOwn(false); load(); }, [load]);
  useEffect(() => {
    if (!job) return;
    const t = setInterval(async () => {
      try {
        const j = await get<{ status: string; error: string }>(`/api/jobs/${job}`);
        if (j.status === "done") { setJob(null); toast(tr("ed.pic.in"), "ok"); load(); onChanged(); }
        else if (j.status === "error" || j.status === "cancelled") { setJob(null); toast(j.error || tr("ed.pic.fail"), "err", 9000); }
      } catch { /* keep trying */ }
    }, 1500);
    return () => clearInterval(t);
  }, [job]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!info?.reel) return null;
  const again = (body: { draw?: string; seed?: number }) => post<{ id: string }>(`/api/projects/${pid}/scenes/${sid}/redraw`, body).then((j) => setJob(j.id)).catch((e) => toast(e.errors?.[0] || e.message, "err", 8000));
  const use = (m: string) => post(`/api/projects/${pid}/scenes/${sid}/picture/use`, { media: m }).then(() => { load(); onChanged(); }).catch((e) => toast(e.message, "err"));
  const changed = draw.trim() !== info.draw.trim();
  return (
    <div className="ce-picture" data-testid="picture-tools">
      <h3>{tr("ed.pic.this")}</h3>
      {job ? (
        <div className="row small muted" role="status"><Spinner /> {tr("ed.pic.drawing")}</div>
      ) : (
        <>
          <div className="ce-tries" role="group" aria-label={tr("ed.pic.earlier")}>
            {info.tries.map((t) => (
              <button key={t.media} className={t.current ? "on" : ""} aria-pressed={t.current} title={t.draw} onClick={() => !t.current && use(t.media)}>
                <img src={t.url} alt={t.draw || tr("ed.pic.anearlier")} />
              </button>
            ))}
          </div>
          <div className="ce-props-actions">
            <button className="btn sm" onClick={() => again({})} data-testid="draw-again"><RefreshCw size={13} /> {tr("ed.pic.again")}</button>
            <button className="btn sm" onClick={() => setOwn(!own)} aria-expanded={own}><ImageIcon size={13} /> {tr("ed.pic.mine")}</button>
          </div>
          {own && (
            <div className="ce-media" role="group" aria-label={tr("ed.pic.yours")}>
              {media.filter((m) => m.url).slice(0, 18).map((m) => <button key={m.id} className="ce-own" onClick={() => { use(m.id); setOwn(false); }} title={m.caption || m.id}><img src={m.url} alt={m.caption || m.id} /></button>)}
              {!media.length && <span className="muted small">{tr("ed.pic.addfirst")}</span>}
            </div>
          )}
          <label className="small muted" htmlFor="draw-text">{tr("ed.pic.describe")}</label>
          <textarea id="draw-text" className="bn" rows={3} value={draw} onChange={(e) => setDraw(e.target.value)} style={{ width: "100%" }} />
          <button className="btn sm primary" disabled={!changed} onClick={() => again({ draw })} data-testid="draw-described"><Brush size={13} /> {tr("ed.pic.drawthis")}</button>
        </>
      )}
    </div>
  );
}
