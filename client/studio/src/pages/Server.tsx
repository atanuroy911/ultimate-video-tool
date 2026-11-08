import { useEffect, useState } from "react";
import ConnectedComputers from "../components/ConnectedComputers";
import GpuChoice from "../components/GpuChoice";
import JobsPanel from "../components/JobsPanel";
import SystemPanel from "../components/SystemStats";
import ComfySettings from "./ComfySettings";
import Engines, { EnginesAdvanced } from "./Engines";
import LocalAI from "./LocalAI";
import ServerRestart from "../components/ServerRestart";

/* The computer that does the work, in one place. What people check most comes first (what it is making, whether its AI programs are ready,
   which graphics cards it may use); what they rarely touch (addresses, ports, sharing, each program's own settings) waits under Advanced.
   (Settings holds the person's choices; this page holds the machine. docs/plans/PLAN-CLIENT-UX.MD) */
interface Card { name: string; server: string; needs_key?: boolean }

export default function ServerPage() {
  const [card, setCard] = useState<Card | null>(null);
  useEffect(() => { fetch("/.well-known/video-tool").then((r) => (r.ok ? r.json() : null)).then(setCard).catch(() => setCard(null)); }, []);
  const native = (window as any).vtDesktop?.server;
  return (
    <div className="page-inner" style={{ maxWidth: 1060 }}>
      <div className="row wrap" style={{ gap: 12, alignItems: "flex-end" }}>
        <div className="col grow" style={{ gap: 2 }}>
          <h1 style={{ marginBottom: 0 }}>{card?.name || "Server"}</h1>
          <p className="muted" style={{ margin: 0 }}>The computer that makes your videos.</p>
        </div>
        {native && <button className="btn sm" onClick={() => native.choose()}>Switch server…</button>}
      </div>
      <div className="col" style={{ gap: 18, marginTop: 18 }}>
        <JobsPanel />
        <Engines />
        <GpuChoice />
        <SystemPanel />
        <ConnectedComputers />
        <ServerRestart />
        <details className="card card-pad settings-more" data-testid="server-advanced">
          <summary><strong>Advanced</strong> <span className="small muted">find programs, share this server, program settings</span></summary>
          <div className="col" style={{ gap: 18, marginTop: 14 }}>
            <EnginesAdvanced />
            <LocalAI />
            <ComfySettings />
          </div>
        </details>
      </div>
    </div>
  );
}
