// O4 (docs/plans/PLAN-OPENMOTION.MD): open the whole video in the HyperFrames Studio. The server bakes the current video into plain HyperFrames source
// and starts the Studio on this computer; the Studio saves its own edits, and the export draws them. The Studio refuses to sit inside another page's
// frame, so it opens as its own window (an app window in the desktop app).
import { Clapperboard } from "lucide-react";
import { useEffect, useState } from "react";
import { del, post } from "../api";
import { toast } from "../store";
import { Button, MenuItem, Popover } from "../ds";

// In the desktop app the Studio sits inside the editor (the app lets this one local page be framed); in a browser it opens its own window.
const canEmbed = () => typeof window !== "undefined" && !!(window as any).vtDesktop;

export default function StudioButton({ projectId, embedded, onEmbed, assistantShown, onAssistant }: { projectId: string; embedded?: boolean; onEmbed?: (url: string | null) => void;
  assistantShown?: boolean; onAssistant?: (on: boolean) => void }) {
  const [state, setState] = useState<"off" | "starting" | "open">("off");
  const [url, setUrl] = useState("");
  const base = `/api/projects/${encodeURIComponent(projectId)}/studio`;
  const show = (u: string) => { if (onEmbed && canEmbed()) onEmbed(u); else window.open(u, "vt-hyperframes-studio"); };

  const open = async (fresh = false) => {
    setState("starting");
    try {
      const s = await post<{ url: string; kept?: boolean; lost_count?: number }>(`${base}${fresh ? "?fresh=1" : ""}`);
      setUrl(s.url);
      setState("open");
      show(s.url);
      toast(s.kept ? "The video is open in HyperFrames with your earlier edits there. They go into the export."
        : "The video is open in HyperFrames. Select anything to move, retype or animate it; your edits go into the export.");
      if (s.lost_count) toast(`${s.lost_count} animation step(s) could not be carried into the Studio (they use code it cannot show).`, "err");
    } catch (e: any) {
      setState("off");
      toast(`HyperFrames did not open: ${e.message}`, "err");
    }
  };
  useEffect(() => {                                                      // S2: a scene's menu opens HyperFrames (the editor already moved to that scene)
    const on = () => { if (state === "open" && url) show(url); else if (state === "off") void open(); };
    window.addEventListener("vt-open-hyperframes", on);
    return () => window.removeEventListener("vt-open-hyperframes", on);
  });
  const close = async () => {
    try { await del(base); } catch { /* already stopped */ }
    setState("off");
    onEmbed?.(null);
    toast("HyperFrames is closed. Its edits stay with the video.");
  };

  if (state !== "open")
    return (
      <Button size="sm" onClick={() => open()} disabled={state === "starting"} aria-label="Edit in HyperFrames"
              title="Edit the whole video in the HyperFrames Studio: every scene on a timeline, every part selectable, keyframes and motion paths">
        <Clapperboard size={15} /> {state === "starting" ? "Opening…" : "Edit in HyperFrames"}
      </Button>
    );
  return (
    <Popover label="HyperFrames" align="right" trigger={<><Clapperboard size={15} /> HyperFrames open</>}>
      {embedded ? <MenuItem onClick={() => onEmbed?.(null)}>Back to Video Tool's editor</MenuItem> : <MenuItem onClick={() => show(url)}>Show the Studio</MenuItem>}
      {embedded && onAssistant && <MenuItem onClick={() => onAssistant(!assistantShown)}>{assistantShown ? "Hide the assistant (more room for the Studio)" : "Show the assistant beside the Studio"}</MenuItem>}
      <MenuItem onClick={() => open(true)}>Start over from the current video</MenuItem>
      <MenuItem onClick={close}>Close the Studio</MenuItem>
    </Popover>
  );
}
