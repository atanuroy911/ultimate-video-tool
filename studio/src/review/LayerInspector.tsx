import { Copy, Scissors, Trash2 } from "lucide-react";
import { Panel } from "../ds";
import type { LClip, MediaItem } from "../types";
import * as Ops from "./layerOps";
import type { Layers } from "./useLayers";

/** A range input that shows the change at once and saves when it is let go. */
function Num({ label, value, min, max, step, unit, layers, onSet, fmt }: { label: string; value: number; min: number; max: number; step: number; unit?: string; layers: Layers; onSet: (v: number) => void; fmt?: (v: number) => string }) {
  const save = () => layers.commit();
  return (
    <label className="field"><span>{label} <em className="muted" style={{ fontStyle: "normal" }}>{fmt ? fmt(value) : `${value}${unit ?? ""}`}</em></span>
      <input type="range" min={min} max={max} step={step} value={value} aria-label={label} onChange={(e) => onSet(+e.target.value)} onPointerUp={save} onKeyUp={(e) => e.key.startsWith("Arrow") && save()} />
    </label>
  );
}

/** The inspector for a clip on an extra track: what it says or shows, where, how big, how long it fades, how loud. */
export default function LayerInspector({ layers, clip, media, total, onSelect, seek, time }: { layers: Layers; clip: LClip; media: Map<string, MediaItem>; total: number; onSelect: (id: string | null) => void; seek: (t: number) => void; time: number }) {
  const m = clip.media ? media.get(clip.media) : undefined;
  const set = (patch: Partial<LClip>) => layers.setLocal(Ops.patchClip(layers.doc, clip.id, patch));
  const commitNow = (patch: Partial<LClip>) => layers.commit(Ops.patchClip(layers.doc, clip.id, patch));
  const visual = clip.type !== "audio";
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  const canSplit = time > clip.start + Ops.MIN && time < clip.start + clip.dur - Ops.MIN;
  const track = layers.doc.tracks.find((t) => t.id === clip.track);

  return (
    <div>
      <div style={{ padding: "12px 14px 4px" }}>
        <h2>{clip.type === "text" ? "Text layer" : clip.type === "audio" ? "Sound layer" : "Picture / video layer"}</h2>
        <span className="small muted">{track?.name} · {clip.start.toFixed(2)}–{(clip.start + clip.dur).toFixed(2)} s{m ? ` · ${m.caption || m.id}` : ""}</span>
      </div>
      <Panel title="Clip">
        <div className="row wrap" style={{ gap: 6 }}>
          <button className="btn sm" disabled={!canSplit} onClick={() => { const r = Ops.split(layers.doc, clip.id, time); if (r) { layers.commit(r.doc); onSelect(r.ids[1]); } }} title="Split at the playhead"><Scissors size={13} /> Split</button>
          <button className="btn sm" onClick={() => { const r = Ops.duplicate(layers.doc, clip.id, total); if (r) { layers.commit(r.doc); onSelect(r.id); } }}><Copy size={13} /> Duplicate</button>
          <button className="btn sm danger" onClick={() => { layers.commit(Ops.remove(layers.doc, clip.id)); onSelect(null); }}><Trash2 size={13} /> Delete</button>
          <button className="btn sm ghost" onClick={() => seek(clip.start)}>Go to start</button>
        </div>
        <Num label="Fade in" value={clip.fade_in} min={0} max={Math.min(5, clip.dur / 2)} step={0.05} unit=" s" layers={layers} onSet={(v) => set({ fade_in: v })} />
        <Num label="Fade out" value={clip.fade_out} min={0} max={Math.min(5, clip.dur / 2)} step={0.05} unit=" s" layers={layers} onSet={(v) => set({ fade_out: v })} />
      </Panel>

      {clip.type === "text" && (
        <Panel title="Text">
          <label className="field"><span>What it says</span>
            <textarea rows={3} className="bn" value={clip.text ?? ""} aria-label="Text of the layer" onChange={(e) => set({ text: e.target.value })} onBlur={(e) => e.target.value.trim() ? layers.commit() : layers.commit(Ops.patchClip(layers.doc, clip.id, { text: "Your text" }))} />
          </label>
          <Num label="Size" value={clip.style?.size ?? 0.06} min={0.02} max={0.2} step={0.005} layers={layers} onSet={(v) => set({ style: { size: v } as any })} fmt={(v) => `${Math.round(v * 100)}`} />
          <div className="row" style={{ gap: 12 }}>
            <label className="field"><span>Colour</span><input type="color" value={clip.style?.color ?? "#ffffff"} aria-label="Text colour" onChange={(e) => set({ style: { color: e.target.value } as any })} onBlur={() => layers.commit()} /></label>
            <label className="field"><span>Plate</span>
              <span className="row" style={{ gap: 6 }}>
                <input type="checkbox" checked={!!clip.style?.bg} aria-label="Plate behind the text" onChange={(e) => commitNow({ style: { bg: e.target.checked ? "#111111" : null } as any })} />
                {clip.style?.bg && <input type="color" value={clip.style.bg} aria-label="Plate colour" onChange={(e) => set({ style: { bg: e.target.value } as any })} onBlur={() => layers.commit()} />}
              </span>
            </label>
          </div>
          <div className="row" style={{ gap: 6 }} role="group" aria-label="Alignment">
            {(["left", "center", "right"] as const).map((a) => <button key={a} className={`btn sm ${clip.style?.align === a ? "primary" : ""}`} aria-pressed={clip.style?.align === a} onClick={() => commitNow({ style: { align: a } as any })}>{a}</button>)}
          </div>
        </Panel>
      )}

      {visual && (
        <Panel title="Place">
          <Num label="Across" value={clip.x ?? 0.5} min={0} max={1} step={0.005} layers={layers} onSet={(v) => set({ x: v })} fmt={pct} />
          <Num label="Down" value={clip.y ?? 0.5} min={0} max={1} step={0.005} layers={layers} onSet={(v) => set({ y: v })} fmt={pct} />
          <Num label="Width" value={clip.w ?? 1} min={0.05} max={2} step={0.01} layers={layers} onSet={(v) => set({ w: v })} fmt={pct} />
          {clip.type === "media" && (
            <label className="field"><span>Height</span>
              <span className="row" style={{ gap: 8 }}>
                <input type="checkbox" checked={clip.h == null} aria-label="Keep the picture's own shape" onChange={(e) => commitNow({ h: e.target.checked ? null : 0.5 })} /> <span className="small muted">keep its own shape</span>
              </span>
            </label>
          )}
          {clip.type === "media" && clip.h != null && <Num label="Height" value={clip.h} min={0.05} max={2} step={0.01} layers={layers} onSet={(v) => set({ h: v })} fmt={pct} />}
          {clip.type === "media" && clip.h != null && (
            <div className="row" style={{ gap: 6 }} role="group" aria-label="Fit">
              {(["cover", "contain"] as const).map((f) => <button key={f} className={`btn sm ${clip.fit === f ? "primary" : ""}`} aria-pressed={clip.fit === f} onClick={() => commitNow({ fit: f })}>{f === "cover" ? "Fill the box" : "Fit inside"}</button>)}
            </div>
          )}
          <label className="field"><span>Motion</span>
            <select value={clip.anim ?? "none"} aria-label="Motion of the layer" onChange={(e) => commitNow({ anim: e.target.value })}>
              {[["none", "None"], ["zoom_in", "Slow zoom in"], ["zoom_out", "Slow zoom out"], ["slide_left", "Slide in from the right"], ["slide_right", "Slide in from the left"], ["slide_up", "Slide in from below"], ["slide_down", "Slide in from above"], ["pulse", "Gentle pulse"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <Num label="Opacity" value={clip.opacity ?? 1} min={0} max={1} step={0.01} layers={layers} onSet={(v) => set({ opacity: v })} fmt={pct} />
          <div className="row" style={{ gap: 6 }}>
            <button className="btn sm" onClick={() => commitNow({ x: 0.5, y: 0.5, w: 1, h: null })}>Full frame</button>
            <button className="btn sm" onClick={() => commitNow({ x: 0.8, y: 0.2, w: 0.3, h: null })}>Corner picture</button>
          </div>
        </Panel>
      )}

      {(clip.type === "audio" || (clip.type === "media" && m?.kind === "video" && m.audio_file)) && (
        <Panel title="Sound">
          <Num label="Volume" value={clip.volume ?? 1} min={0} max={2} step={0.05} layers={layers} onSet={(v) => set({ volume: v })} fmt={pct} />
          {clip.type === "media" && <span className="small muted">A video's own sound is off unless you turn it up here.</span>}
        </Panel>
      )}
    </div>
  );
}
