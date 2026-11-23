// S1 / S3 (docs/plans/PLAN-SCENE-TOOLS.MD): above the HyperFrames Studio, the scene being edited: move scene by scene (the Studio's playhead follows),
// read what is said there, pick one of the scene's parts by name (the Studio selects it), and the scene's own actions, each named for what it does.
import { ChevronLeft, ChevronRight, Image as ImageIcon, MessageSquare, X } from "lucide-react";
import { useEffect, useState } from "react";
import { get } from "../api";
import type { SceneTime, Word } from "../types";

export interface StudioPart { id: string; file: string; scene: string | null; tag: string; text: string }

// "s4-defn-term" -> "Definition term", "s3-bd-scrim" -> "Backdrop shade", "s2-bar-val-2" -> "Bar value 2"; boxes with no name of their own are left out
const WORDS: Record<string, string> = { defn: "definition", bd: "backdrop", scrim: "shade", vcard: "card", num: "number", val: "value", eq: "equals",
  art: "picture", img: "picture", kw: "keyword", cap: "caption", bg: "background", txt: "text", desc: "description", lbl: "label", hdr: "heading" };
export const isBox = (id: string) => /^(scene|stage|div|wrap|inner|root|group)(-\d+)?$/.test(id.replace(/^s\d+[a-z0-9]*-/, ""));
export function partName(id: string): string {
  const bits = id.replace(/^s\d+[a-z0-9]*-/, "").split(/[-_]+/).filter(Boolean).map((w) => WORDS[w] ?? w);
  const name = bits.join(" ");
  return name.charAt(0).toUpperCase() + name.slice(1);
}

export default function StudioSceneBar({ projectId, scenes, words, index, version, selected, onGo, onSelect, onPictures, onDirector, onBack }: {
  projectId: string; scenes: SceneTime[]; words: Word[]; index: number; version?: number; selected?: string | null;
  onGo: (i: number) => void; onSelect: (part: StudioPart | null) => void;
  onPictures: (sceneId: string) => void; onDirector: (sceneId: string) => void; onBack: () => void;
}) {
  const sc = scenes[index];
  const [parts, setParts] = useState<StudioPart[]>([]);
  useEffect(() => {
    if (!sc) return;
    let live = true;
    get<StudioPart[]>(`/api/projects/${encodeURIComponent(projectId)}/studio/parts?scene=${encodeURIComponent(sc.id)}`)
      .then((p) => live && setParts(p.filter((x) => !isBox(x.id))))
      .catch(() => live && setParts([]));
    return () => { live = false; };
  }, [projectId, sc?.id, version]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!sc) return null;
  const said = words.filter((w) => !w.cut && w.start >= sc.start - 0.01 && w.start < sc.end).map((w) => w.text).join(" ");
  return (
    <div className="studio-scene-bar" role="toolbar" aria-label="Scene in HyperFrames">
      <div className="studio-scene-row">
        <button className="btn ghost icon sm" aria-label="Previous scene" disabled={index <= 0} onClick={() => onGo(index - 1)}><ChevronLeft size={16} /></button>
        <strong className="studio-scene-name" aria-live="polite">Scene {index + 1} of {scenes.length}</strong>
        <button className="btn ghost icon sm" aria-label="Next scene" disabled={index >= scenes.length - 1} onClick={() => onGo(index + 1)}><ChevronRight size={16} /></button>
        <span className="studio-scene-said small muted" title={said}>{said ? `“${said}”` : "No words in this scene"}</span>
        <span className="grow" />
        <button className="btn sm" onClick={() => onPictures(sc.id)} title="Generate pictures or clips for this scene and choose one">
          <ImageIcon size={14} /> Pictures for this scene</button>
        <button className="btn sm" onClick={() => onDirector(sc.id)} title="Ask the Director to redo this scene in your words">
          <MessageSquare size={14} /> Redo with the Director</button>
        <button className="btn ghost sm" onClick={onBack} title="Back to Video Tool's own editor (the HyperFrames edits stay)"><X size={14} /> Back to the editor</button>
      </div>
      {parts.length > 0 && (
        <div className="studio-scene-parts" role="group" aria-label="Parts of this scene">
          <span className="small muted">Select:</span>
          {parts.map((p) => (
            <button key={p.id} className={`studio-part ${selected === p.id ? "on" : ""}`} aria-pressed={selected === p.id}
              title={`${p.id}${p.text ? ` · “${p.text}”` : ""}`} onClick={() => onSelect(selected === p.id ? null : p)}>
              {partName(p.id)}{p.text && p.text.length <= 24 ? <span className="muted"> {p.text}</span> : null}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
