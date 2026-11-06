import { useEffect, useState } from "react";

/** Shown instead of the Studio when the server answers "not you": it only accepts computers on its own network (docs/plans/PLAN-PERFECT.MD, decision 7).
 *  On the server's network there is nothing to enter, so a person normally never sees this. */
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
        <h1 style={{ margin: 0 }}>This server is not open to this computer</h1>
        <p className="muted" style={{ margin: 0 }}>
          <strong>{name}</strong> at <strong>{address}</strong> only accepts computers on its own network. Connect from a computer on the same network, using the server's address, or choose another server.
        </p>
        {desktop && <button className="btn primary" onClick={() => desktop.choose()} data-testid="refused-change">Choose another server</button>}
      </div>
    </div>
  );
}
