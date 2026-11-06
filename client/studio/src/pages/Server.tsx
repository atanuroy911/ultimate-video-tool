import { useEffect, useState } from "react";
import ConnectedComputers from "../components/ConnectedComputers";
import GpuChoice from "../components/GpuChoice";
import JobsPanel from "../components/JobsPanel";
import SystemPanel from "../components/SystemStats";
import ComfySettings from "./ComfySettings";
import Engines from "./Engines";
import LocalAI from "./LocalAI";

/* The computer that does the work, in one place: how busy it is, which graphics card each job uses, and the engines it runs.
   (Settings holds the person's choices; this page holds the machine. docs/plans/PLAN-CLIENT-UX.MD) */
interface Card { name: string; server: string; needs_key?: boolean }

export default function ServerPage() {
  const [card, setCard] = useState<Card | null>(null);
  useEffect(() => { fetch("/.well-known/video-tool").then((r) => (r.ok ? r.json() : null)).then(setCard).catch(() => setCard(null)); }, []);
  return (
    <div className="page-inner" style={{ maxWidth: 1060 }}>
      <h1>Server</h1>
      <p className="muted" style={{ marginTop: -8 }}>
        {card ? <><strong>{card.name}</strong> is the computer that does the work (Video Tool server {card.server}). Everything below is about it.</> : "The computer that does the work."}
      </p>
      <div className="col" style={{ gap: 18 }}>
        <JobsPanel />
        <SystemPanel />
        <ConnectedComputers />
        <GpuChoice />
        <Engines />
        <details className="card card-pad settings-more">
          <summary><strong>Language AI settings</strong> <span className="small muted">address, model version, test</span></summary>
          <LocalAI />
        </details>
        <details className="card card-pad settings-more">
          <summary><strong>Pictures &amp; clips settings</strong> <span className="small muted">address, connection check, clip models</span></summary>
          <ComfySettings />
        </details>
      </div>
    </div>
  );
}
