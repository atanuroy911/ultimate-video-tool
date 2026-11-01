import { useEffect, useState } from "react";
import { Spinner } from "./ui";

/** Shown instead of the Studio when this page comes from a Video Tool server on another computer that has not been paired yet
 *  (docs/plans/PLAN-CLIENT-SERVER.MD CS4). The code is printed where the server started, and on its Engines page under "This server". */
export const PAIR_EVENT = "vt-needs-pairing";

type Card = { name: string; needs_pairing: boolean };

export function PairGate({ children }: { children: React.ReactNode }) {
  const [need, setNeed] = useState<boolean | null>(null);
  const [card, setCard] = useState<Card | null>(null);
  useEffect(() => {
    fetch("/.well-known/video-tool").then((r) => (r.ok ? r.json() : null)).then(setCard).catch(() => setCard(null));
    fetch("/api/health").then((r) => setNeed(r.status === 401)).catch(() => setNeed(false));
    const on = () => setNeed(true);
    window.addEventListener(PAIR_EVENT, on);
    return () => window.removeEventListener(PAIR_EVENT, on);
  }, []);
  if (need === null) return null;
  return need ? <PairScreen name={card?.name || "Video Tool"} /> : <>{children}</>;
}

function PairScreen({ name }: { name: string }) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const pair = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const r = await fetch("/api/pair", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) });
      if (r.ok) {
        location.reload();
        return;
      }
      const d = await r.json().catch(() => null);
      setErr(typeof d?.detail === "string" ? d.detail : "That did not work. Check the code and try again.");
    } catch {
      setErr("Could not reach the server. Is it still running?");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="col" style={{ minHeight: "100vh", alignItems: "center", justifyContent: "center", padding: 16 }} data-testid="pair-screen">
      <form className="col" onSubmit={pair} style={{ gap: 12, maxWidth: 420, width: "100%" }}>
        <h1 style={{ margin: 0 }}>Connect to {name}</h1>
        <p className="muted" style={{ margin: 0 }}>
          This Video Tool server runs on another computer. Type the pairing code shown there: where the server was started, or on its Engines page
          under <strong>This server</strong>. You only do this once on this device.
        </p>
        <input type="text" value={code} onChange={(e) => setCode(e.target.value)} placeholder="ab12-cd34-ef56" aria-label="Pairing code"
          autoFocus autoComplete="off" spellCheck={false} data-testid="pair-code" style={{ fontSize: 20, letterSpacing: 2 }} />
        {err && <span className="small" style={{ color: "var(--danger, #c33)" }} role="alert">{err}</span>}
        <button className="btn primary" type="submit" disabled={busy || !code.trim()} data-testid="pair-go">{busy ? <Spinner /> : "Connect"}</button>
      </form>
    </div>
  );
}
