import { FileText, Mic, UserSquare } from "lucide-react";
import { useState } from "react";
import { post } from "../api";
import { Segmented } from "../ds";
import { toast } from "../store";
import type { Review } from "./useReview";

/* The project's mode, in the editor's title bar. A video with a speaker can switch between keeping the speaker on screen
   and graphics only (one undo step); a voice recording or a script just says what it is. */
export default function ModeSwitch({ r }: { r: Review }) {
  const project = r.project.data;
  const [switching, setSwitching] = useState(false);
  if (!project) return null;
  const hasSpeakerPicture = (project.media ?? []).some((m: any) => m.role === "a_roll");
  if (!hasSpeakerPicture) {
    const isScript = project.source === "script";
    return (
      <span className="chip mode-chip" title={isScript ? "Made from a script read by an AI voice" : "Made from a voice recording: every picture is generated"}>
        {isScript ? <FileText size={12} /> : <Mic size={12} />} {isScript ? "Script" : "Voice only"}
      </span>
    );
  }
  const speakerShown = (r.plan?.scenes ?? []).some((scene) => scene.backdrop?.media === "aroll");
  const setSpeaker = async (show: boolean) => {
    if (show === speakerShown || switching) return;
    setSwitching(true);
    try {
      await post(`/api/projects/${project.id}/aroll/apply?on=${show}`);
      r.reloadAll();
    } catch (e: any) {
      toast(e.message, "err");
    } finally {
      setSwitching(false);
    }
  };
  return (
    <Segmented<"speaker" | "graphics">
      label="Mode"
      value={speakerShown ? "speaker" : "graphics"}
      onChange={(value) => setSpeaker(value === "speaker")}
      options={[{ value: "speaker", label: <span className="row" style={{ gap: 4 }}><UserSquare size={13} /> Talking head</span> }, { value: "graphics", label: "Graphics only" }]}
    />
  );
}
