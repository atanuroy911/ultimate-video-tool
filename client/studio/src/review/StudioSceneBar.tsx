// S1 (docs/plans/PLAN-SCENE-TOOLS.MD): above the HyperFrames Studio, the scene being edited: move scene by scene (the Studio's playhead follows),
// read what is said there, and the scene's own actions, each named for what it does.
import { ChevronLeft, ChevronRight, Image as ImageIcon, MessageSquare, X } from "lucide-react";
import type { SceneTime, Word } from "../types";

export default function StudioSceneBar({ scenes, words, index, onGo, onPictures, onDirector, onBack }: {
  scenes: SceneTime[]; words: Word[]; index: number;
  onGo: (i: number) => void; onPictures: (sceneId: string) => void; onDirector: (sceneId: string) => void; onBack: () => void;
}) {
  const sc = scenes[index];
  if (!sc) return null;
  const said = words.filter((w) => !w.cut && w.start >= sc.start - 0.01 && w.start < sc.end).map((w) => w.text).join(" ");
  return (
    <div className="studio-scene-bar" role="toolbar" aria-label="Scene in HyperFrames">
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
  );
}
