import { Music2 } from "lucide-react";
import { useMusic } from "../hooks";
import type { Review } from "../review/useReview";
import { useT } from "../i18n";
import { Seg } from "../ui";

/* Music and sound effects, in plain words: which music, how loud, how many effects. Changes the whole video and renders again when you export. */
export default function SoundPanel({ r }: { r: Review }) {
  const t = useT();
  const { data: tracks } = useMusic();
  const o = r.project.data?.options;
  if (!o) return null;
  const set = (patch: Record<string, unknown>) => r.patchProject({ options: patch });
  const music = o.music ?? "";
  return (
    <div className="col" style={{ gap: 8 }} data-testid="sound-panel">
      <h3><Music2 size={14} /> {t("ed.snd.title")}</h3>
      <label className="small muted" htmlFor="ce-music">{t("ed.snd.music")}</label>
      <select id="ce-music" className="ce-select" value={music} onChange={(e) => set({ music: e.target.value || null })} aria-label={t("ed.snd.music")}>
        <option value="">{t("ed.snd.none")}</option>
        <option value="auto">{t("ed.snd.auto")}</option>
        {(tracks ?? []).map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
      </select>
      <label className="small muted" htmlFor="ce-music-vol">{t("ed.snd.loud")}</label>
      <input id="ce-music-vol" type="range" min={0} max={40} value={Math.round((o.music_volume ?? 0.14) * 100)} disabled={!music}
        onChange={(e) => set({ music_volume: +e.target.value / 100 })} aria-label={t("ed.snd.loud")} />
      <span className="small muted">{t("ed.snd.sfx")}</span>
      <Seg<string> label={t("ed.snd.sfx")} value={o.sfx ? o.sfx_level : "off"} onChange={(v) => set({ sfx: v !== "off", sfx_level: v === "off" ? "normal" : v })}
        options={[{ value: "off", label: t("ed.snd.none") }, { value: "subtle", label: t("ed.snd.few") }, { value: "normal", label: t("ed.snd.some") }, { value: "rich", label: t("ed.snd.many") }]} />
    </div>
  );
}
