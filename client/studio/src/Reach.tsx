import { useEffect, useState } from "react";

/** Shown instead of the Studio when the server answers "not you": another computer needs the server's key (docs/plans/PLAN-WORKBENCH.MD, W2). The desktop app asks
 *  for it on its connect page and keeps it; a person sees this when the server's key changed or a server was set up to ask. */
export const REFUSED_EVENT = "vt-server-refused";

export function ReachGate({ children }: { children: React.ReactNode }) {
  const [refused, setRefused] = useState<boolean | null>(null);
  const [name, setName] = useState("Video Tool");
  const [address, setAddress] = useState("the selected server");
  useEffect(() => {
    fetch("/.well-known/video-tool").then((r) => (r.ok ? r.json() : null)).then((c) => c?.name && setName(c.name)).catch(() => {});
    fetch("/api/health").then((r) => setRefused(r.status === 401)).catch(() => setRefused(false));
    fetch("/__client/connection").then((r) => (r.ok ? r.json() : null)).then((info) => { if (info?.server) setAddress(info.server); }).catch(() => {});
    const on = () => setRefused(true);
    window.addEventListener(REFUSED_EVENT, on);
    return () => window.removeEventListener(REFUSED_EVENT, on);
  }, []);
  if (refused === null) return null;
  return refused ? <Refused name={name} address={address} /> : <>{children}</>;
}

function Refused({ name, address }: { name: string; address: string }) {
  const desktop = (window as any).vtDesktop?.server;
  return (
    <div className="col" style={{ minHeight: "100vh", alignItems: "center", justifyContent: "center", padding: 16 }} data-testid="refused-screen">
      <div className="col" style={{ gap: 12, maxWidth: 440, width: "100%" }} role="alert">
        <h1 style={{ margin: 0 }}>This server needs its key</h1>
        <p className="muted" style={{ margin: 0 }}>
          <strong>{name}</strong> at <strong>{address}</strong> asks other computers for its key. Open the server window on that computer, choose <strong>Copy key</strong>, then choose the server again and paste the key.
        </p>
        {desktop && <button className="btn primary" onClick={() => desktop.choose()} data-testid="refused-change">Choose the server and enter the key</button>}
      </div>
    </div>
  );
}
