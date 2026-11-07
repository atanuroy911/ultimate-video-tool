import { Panel, Segmented } from "../ds";
import { useFetch } from "../hooks";
import { useThemes } from "../hooks";
import { post } from "../api";
import { toast } from "../store";
import type { MediaItem, ProjectSummary } from "../types";
import type { Review } from "./useReview";
import ContextPanel from "./ContextPanel";

/** The Inspector when nothing is selected: settings of the whole video. */
export default function VideoInspector({ r, p, useCases, onRedirect, onRepace }: { r: Review; p: ProjectSummary; useCases: { id: string; label: string }[]; onRedirect: () => void; onRepace: (pace: string, from: string) => void }) {
  const { data: themes } = useThemes();
  const kind = p.video_kind ?? "explainer";
  const media = useFetch<MediaItem[]>(`/api/projects/${p.id}/media`);
  const speaker = (media.data ?? []).find((m) => m.role === "a_roll");
  return (
    <div>
      <div style={{ padding: "12px 14px 4px" }}>
        <h2>Video</h2>
        <span className="small muted">Choose the look, captions and shape for the whole video. Return to selection to keep editing an individual item.</span>
      </div>
      <Panel title="Look">
        <label className="field"><span>Look</span>
          <select value={p.theme} onChange={(e) => r.patchProject({ theme: e.target.value })}>
            {(themes || []).map((t) => <option key={t.name} value={t.name}>{t.label || t.name}</option>)}
          </select>
        </label>
        <div className="col" style={{ gap: 5 }}>
          <span className="small muted" style={{ fontWeight: 600 }}>Style</span>
          <Segmented value={kind as "explainer" | "stick" | "emoji"} label="Style" onChange={(k) => post(`/api/projects/${p.id}/script/generate?kind=${k}`).then(onRedirect).catch((e: any) => toast(e.message, "err"))}
            options={[{ value: "explainer", label: "Pictures" }, { value: "stick", label: "Stick figures" }, { value: "emoji", label: "Emoji" }]} />
        </div>
        <label className="field"><span>Purpose</span>
          <select value={p.usecase ?? "auto"} onChange={(e) => r.patchProject({ usecase: e.target.value }).then(() => toast("Changed. Use AI → Direct the whole video again to apply.", "ok", 4000))}>
            {useCases.map((u) => <option key={u.id} value={u.id}>{u.id === "auto" && p.usecase_used ? `Auto (${p.usecase_used.profile})` : u.label}</option>)}
          </select>
        </label>
      </Panel>
      {speaker && (
        <Panel title="The speaker's picture">
          <span className="small muted">This video was made from a video, so the speaker's own picture is kept (cut like the voice). The speaker is shown where the words need no picture of their own, and always at the start.</span>
          <div className="row wrap" style={{ gap: 6 }}>
            <button className="btn sm" onClick={() => post(`/api/projects/${p.id}/aroll/apply`).then((x: any) => { r.reloadAll(); toast(`The speaker is on ${x.scenes} scene${x.scenes === 1 ? "" : "s"}`, "ok", 3000); }).catch((e: any) => toast(e.errors?.[0] || e.message, "err"))}>Show the speaker where it fits</button>
            <button className="btn sm ghost" onClick={() => post(`/api/projects/${p.id}/aroll/apply?on=false`).then(() => { r.reloadAll(); toast("Graphics only", "ok", 2500); }).catch((e: any) => toast(e.errors?.[0] || e.message, "err"))}>Graphics only</button>
          </div>
        </Panel>
      )}
      <ContextPanel id={p.id} />
      <Panel title="Pace and shape">
        <div className="col" style={{ gap: 5 }}>
          <span className="small muted" style={{ fontWeight: 600 }}>How tightly pauses are cut</span>
          <Segmented value={p.pace} label="Pace" onChange={(v) => r.patchProject({ pace: v }).then((res: any) => res?.needs_reprocess_from && onRepace(v, res.needs_reprocess_from))} options={[{ value: "calm", label: "Calm" }, { value: "normal", label: "Normal" }, { value: "fast", label: "Fast" }]} />
        </div>
        <div className="col" style={{ gap: 5 }}>
          <span className="small muted" style={{ fontWeight: 600 }}>Shape</span>
          <Segmented value={p.aspect} label="Shape" onChange={(v) => r.patchProject({ aspect: v })} options={[{ value: "9:16", label: "9:16" }, { value: "1:1", label: "1:1" }, { value: "16:9", label: "16:9" }]} />
        </div>
      </Panel>
      <Panel title="Facts" defaultOpen={false}>
        <div className="small muted">
          {r.plan?.scenes.length ?? 0} scenes · {r.words.length} words · planner: {r.plan?.planner}
          {p.ai_brief?.topic ? <div>Topic: {p.ai_brief.topic}</div> : null}
          {p.ai_brief?.summary ? <div>{p.ai_brief.summary}</div> : null}
        </div>
      </Panel>
    </div>
  );
}
