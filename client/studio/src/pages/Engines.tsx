import { Check, Cpu, Image as ImageIcon, MessageSquare, Mic, RefreshCw, Server } from "lucide-react";
import { useEffect, useState } from "react";
import { get, post, put } from "../api";
import { Group, Row, Steps } from "../ds";
import { useFetch } from "../hooks";
import { toast } from "../store";
import { Seg, Spinner } from "../ui";
import SetupWizard from "../components/SetupWizard";
import FindEngines from "../components/FindEngines";

/* Settings → Engines: the programs that power the videos (language AI, pictures and clips, voices). Each one runs on this computer, on another computer, or not at all.
   Plain words, no ports; the address and key live behind a Step 1-2-3 sheet. */
interface Health { ok: boolean; why_not: string; version: string; gpu: string; capabilities: string[]; models: { id: string; label?: string; ready?: boolean; why?: string; worker?: string }[]; note: string }
interface Card {
  id: string; kind: string; label: string; about: string; needs_key: boolean; default_url: string; local_install: string;
  endpoint: { mode: "local" | "remote" | "off"; url: string; has_key: boolean; workers: string[] };
  health: Health | null;
}
type Mode = "here" | "own" | "remote" | "off";
interface Here { existing: string[]; own_possible: boolean; own_installed: boolean; own_url: string }
const HERE_ENGINES = ["ollama", "comfy"];
const isHere = (u: string) => /^https?:\/\/(127\.0\.0\.1|localhost)(:|\/|$)/.test(u);
const ICON: Record<string, JSX.Element> = { llm: <MessageSquare size={18} />, image: <ImageIcon size={18} />, voice: <Mic size={18} /> };
const WORDS: Record<string, string> = {
  "llm.chat": "writes and reads", "llm.vision": "looks at pictures", "image.generate": "draws pictures", "video.generate": "makes short clips",
  "voice.speak": "speaks", "voice.list": "lists voices", "voice.clone": "clones a voice", "voice.design": "designs a voice",
};

function where(c: Card): string {
  const m = c.endpoint.mode;
  if (m === "off") return "Not set up";
  if (m === "local") return "Installed by Video Tool on this server";
  if (isHere(c.endpoint.url)) return "On this server";
  return c.endpoint.url.replace(/^https?:\/\//, "");
}

export default function Engines() {
  const list = useFetch<Card[]>("/api/engines");
  const [editing, setEditing] = useState<Card | null>(null);
  const [wizard, setWizard] = useState(false);
  const server=useFetch<{name:string;computer?:string}>("/api/server");
  return (
    <section className="card card-pad col" style={{ gap: 14 }} aria-label="AI programs" data-testid="engines">
      <div className="row wrap" style={{ gap: 8, alignItems: "center" }}>
        <h2 className="grow"><Server size={18} style={{ verticalAlign: -3 }} /> AI programs</h2>
        <button className="btn sm ghost" onClick={() => list.refetch()} aria-label="Check again" title="Check again">{list.loading ? <Spinner /> : <RefreshCw size={14} />}</button>
        <button className="btn sm" onClick={() => setWizard(true)} data-testid="run-setup">Set up…</button>
      </div>
      <p className="muted" style={{ margin: 0 }}>The programs on {server.data?.name || "this server"} that write, draw and speak for your videos.</p>
      {list.loading && !list.data && <Spinner />}
      <div className="col" style={{ gap: 10 }}>
        {(list.data ?? []).filter((c) => c.id !== "vtengine" || c.endpoint.mode !== "off").map((c) => (
          <div key={c.id} className="engine-card" data-engine={c.id}>
            <span className="engine-ic" aria-hidden>{ICON[c.kind] ?? <Cpu size={18} />}</span>
            <div className="col grow" style={{ gap: 2, minWidth: 0 }}>
              <strong>{c.label}</strong>
              <span className="small muted">{where(c)}{c.health?.gpu ? ` · ${c.health.gpu}` : ""}{c.health?.version ? ` · ${c.health.version}` : ""}</span>
              {c.health?.ok && c.health.capabilities.length > 0 && <span className="small">{c.health.capabilities.map((k) => WORDS[k] || k).join(", ")}</span>}
              {c.health && !c.health.ok && c.endpoint.mode !== "off" && <span className="small" style={{ color: "var(--err)" }}>{c.health.why_not}</span>}
              {c.health?.ok && c.health.note && <span className="small" style={{ color: "var(--warn)" }}>{c.health.note}</span>}
            </div>
            {c.endpoint.mode !== "off" && <span className={`chip ${c.health?.ok ? "ok" : "warn"}`}>{c.health?.ok ? <><Check size={12} /> Ready</> : "Not answering"}</span>}
            <button className={`btn sm${c.endpoint.mode === "off" ? " primary" : ""}`} onClick={() => setEditing(c)} aria-label={`${c.endpoint.mode === "off" ? "Set up" : "Change"} ${c.label}`}>{c.endpoint.mode === "off" ? "Set up" : "Change"}</button>
          </div>
        ))}
      </div>
      {wizard && <SetupWizard onClose={() => { setWizard(false); list.refetch(); }} />}
      {editing && <EngineSheet card={editing} onClose={() => { setEditing(null); list.refetch(); }} />}
    </section>
  );
}

/* This computer as the engine for others: the same programs, offered at one address with one code (vt engine run). */
interface HubState { running: boolean; port: number; addresses: string[]; offers?: string[]; mine: boolean; code?: string }
type ServerInfo = { name: string; exposed: boolean; addresses?: string[]; autostart?: boolean };
/** Started as a server (`vt server`), this Studio is already shared: show where to reach it. A computer on this network types an address and is in. */
function ThisServerCard({ info }: { info: ServerInfo }) {
  const [busy, setBusy] = useState(false);
  const [auto, setAuto] = useState(info.autostart);
  const toggleAuto = async () => {
    setBusy(true);
    try {
      const r = await post<{ autostart: boolean; note: string }>("/api/server/autostart", { on: !auto });
      setAuto(r.autostart);
      toast(r.note, "ok", 8000);
    } catch (e: any) {
      toast(e.errors?.[0] || e.message, "err", 8000);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="engine-card" data-testid="this-server-card">
      <span className="engine-ic" aria-hidden><Server size={18} /></span>
      <div className="col grow" style={{ gap: 4, minWidth: 0 }}>
        <strong>Reach this server</strong>
        <span className="small muted">Computers on this network find it by themselves, or can type one of these addresses.</span>
        {info.addresses?.map((a) => <span key={a} className="small bn" style={{ userSelect: "all" }}>{a.replace(/^https?:\/\//, "")}</span>)}
      </div>
      <div className="col" style={{ gap: 6, alignItems: "stretch" }}>
        {auto !== undefined && <button className="btn sm" disabled={busy} onClick={toggleAuto} data-testid="server-autostart" title="With the same engines and port as now">{auto ? "Don't start by itself" : "Start by itself"}</button>}
      </div>
    </div>
  );
}

/** For the Server page's Advanced section: look for programs on other ports or computers, and share this computer's programs. */
export function EnginesAdvanced() {
  return <div className="col" style={{ gap: 12 }}><FindEngines onUsed={() => {}} /><ShareCard /></div>;
}

function ShareCard() {
  const [server, setServer] = useState<ServerInfo | null>(null);
  useEffect(() => { get<ServerInfo>("/api/server").then(setServer).catch(() => setServer(null)); }, []);
  return server?.exposed ? <ThisServerCard info={server} /> : <HubShareCard />;
}

function HubShareCard() {
  const [h, setH] = useState<HubState | null>(null);
  const [busy, setBusy] = useState(false);
  const refresh = () => get<HubState>("/api/hub").then(setH).catch(() => setH(null));
  useEffect(() => { refresh(); }, []);
  const act = async (path: string, ok: string) => {
    setBusy(true);
    try {
      const r = await post<any>(path);
      if (r.address || r.addresses) setH((x) => ({ ...(x as HubState), ...r }));
      else if (r.code) setH((x) => ({ ...(x as HubState), code: r.code }));
      if (r.note || r.done) toast(r.note || r.done.join(" · "), "ok", 6000); else if (ok) toast(ok, "ok");
      if (path.endsWith("/stop")) setH(r);
    } catch (e: any) {
      toast(e.errors?.[0] || e.message, "err", 8000);
    } finally {
      setBusy(false);
    }
  };
  const on = !!h?.running;
  return (
    <div className="engine-card" data-testid="share-card">
      <span className="engine-ic" aria-hidden><Server size={18} /></span>
      <div className="col grow" style={{ gap: 4, minWidth: 0 }}>
        <strong>Share this computer</strong>
        <span className="small muted">{on ? "Another Video Tool server can now use this computer's AI programs. On that server: AI programs, Set up…, then this address and code." : "Let another Video Tool server use the AI programs installed here."}</span>
        {on && h?.addresses.map((a) => <span key={a} className="small bn" style={{ userSelect: "all" }}>{a.replace(/^https?:\/\//, "")}</span>)}
        {on && h?.code && <span className="small" style={{ userSelect: "all" }}>Code (works once): <strong data-testid="share-code">{h.code}</strong></span>}
      </div>
      <div className="col" style={{ gap: 6, alignItems: "stretch" }}>
        {!on && <button className="btn sm primary" disabled={busy} onClick={() => act("/api/hub/start", "")} data-testid="share-start">{busy ? <Spinner /> : "Start sharing"}</button>}
        {on && <button className="btn sm" disabled={busy} onClick={() => act("/api/hub/code", "")}>New code</button>}
        {on && <button className="btn sm" disabled={busy} onClick={() => act("/api/hub/service", "")}>Start at login</button>}
        {on && h?.mine && <button className="btn sm" disabled={busy} onClick={() => act("/api/hub/stop", "Stopped")}>Stop</button>}
      </div>
    </div>
  );
}

function EngineSheet({ card, onClose }: { card: Card; onClose: () => void }) {
  const canHere = HERE_ENGINES.includes(card.id);
  const [mode, setMode] = useState<Mode>(card.endpoint.mode === "local" ? "own" : card.endpoint.mode === "remote" && canHere && isHere(card.endpoint.url) ? "here" : card.endpoint.mode);
  const [here, setHere] = useState<Here | null>(null);
  useEffect(() => { if (canHere) get<Here>(`/api/engines/${card.id}/here`).then(setHere).catch(() => setHere(null)); }, [card.id, canHere]);
  const placed = mode === "here" || mode === "own";
  const [url, setUrl] = useState(card.endpoint.url || "");
  const [key, setKey] = useState("");
  const [workers, setWorkers] = useState((card.endpoint.workers || []).join("\n"));
  const [result, setResult] = useState<Health | null>(null);
  const [busy, setBusy] = useState(false);
  const workerList = () => workers.split(/\s+/).map((w) => w.trim()).filter(Boolean);

  const test = async () => {
    setBusy(true);
    setResult(null);
    try {
      setResult(await post<Health>(`/api/engines/${card.id}/test`, { mode: "remote", url, key: key || undefined, workers: workerList() }));
    } catch (e: any) {
      setResult({ ok: false, why_not: e.message, version: "", gpu: "", capabilities: [], models: [], note: "" });
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    try {
      if (placed) {
        const r = await post<{ note: string }>(`/api/engines/${card.id}/place`, { choice: mode === "here" ? "existing" : "own" });
        toast(r.note || `${card.label} saved`, "ok", 5000);
        onClose();
        return;
      }
      if (card.id === "vtengine" && mode !== "off" && key.trim()) { const r = await post<{ also_connected?: string[] }>(`/api/engines/vtengine/pair`, { url, code: key.trim() }); if (r.also_connected?.length) toast(`Also connected: ${r.also_connected.map((n) => (n === "ollama" ? "the writing AI" : "the picture AI")).join(", ")}`, "ok", 5000); }     // the code is traded for the key; the key is never shown
      else await put(`/api/engines/${card.id}`, { mode, url: mode === "off" ? "" : url, key: card.id === "vtengine" || key === "" ? undefined : key, workers: mode === "off" ? [] : workerList() });
      toast(mode === "off" ? `${card.label} is off` : `${card.label} saved`, "ok");
    } catch (e: any) {
      toast(e.errors?.[0] || e.message, "err", 6000);
      return;
    }
    onClose();
  };

  return (
    <Steps
      label={card.label}
      onClose={onClose}
      onDone={save}
      steps={[
        {
          title: card.label,
          subtitle: card.about,
          icon: ICON[card.kind] ?? <Cpu size={26} />,
          body: (
            <Group title="Where does it run?">
              <Row label="Choose" stack>
                <Seg<Mode> label="Where it runs" value={mode} onChange={setMode}
                  options={[
                    ...(canHere ? [{ value: "here" as Mode, label: "On this server" }] : []),
                    ...(here?.own_possible ? [{ value: "own" as Mode, label: "Video Tool's own copy" }] : []),
                    { value: "remote" as Mode, label: "Another computer" }, { value: "off" as Mode, label: "Off" }]} />
              </Row>
              {mode === "here" && here && (here.existing.length
                ? <p className="small" style={{ margin: 0 }} data-testid="here-found">Found and running. Video Tool uses it as it is and never changes it.</p>
                : <p className="small" style={{ margin: 0, color: "var(--warn)" }}>It isn't running on this server. Start it, choose Video Tool's own copy, or choose Another computer.</p>)}
              {mode === "own" && here && (here.own_installed
                ? <p className="small" style={{ margin: 0 }}>Kept apart from any other copy on this server. It starts when you press Done.</p>
                : <p className="small" style={{ margin: 0, color: "var(--warn)" }}>Not installed yet. Press <strong>Set up…</strong> under AI programs to install it.</p>)}
            </Group>
          ),
        },
        {
          title: "Connect",
          subtitle: mode === "off" ? "Video Tool works without it, using simpler built-in steps." : placed ? "Nothing to type." : "The address of the computer that runs it.",
          icon: <Server size={26} />,
          body: mode === "off" || placed ? null : (
            <>
              <Group title="Address">
                <Row label="Address" stack><input type="text" value={url} placeholder={card.default_url || "http://192.168.1.20:8188"} onChange={(e) => setUrl(e.target.value)} spellCheck={false} aria-label="Address" style={{ width: "100%" }} /></Row>
                {card.needs_key && card.id !== "vtengine" && <Row label="Key" stack><input type="password" value={key} placeholder={card.endpoint.has_key ? "Saved. Type a new one to replace it" : "Paste the key"} onChange={(e) => setKey(e.target.value)} aria-label="Key" autoComplete="off" style={{ width: "100%" }} /></Row>}
                {card.id === "vtengine" && <Row label="Pairing code" stack><input type="text" value={key} placeholder={card.endpoint.has_key ? "Linked. Type a new code to link again" : "The code shown on the other computer"} onChange={(e) => setKey(e.target.value)} aria-label="Pairing code" autoComplete="off" spellCheck={false} style={{ width: "100%" }} /></Row>}
              </Group>
              {card.kind === "image" && (
                <Group title="More computers (optional)" note="Other ComfyUI addresses, one per line. Each picture goes to one that is free.">
                  <Row label="Addresses" stack><textarea value={workers} rows={2} onChange={(e) => setWorkers(e.target.value)} spellCheck={false} aria-label="More computers" style={{ width: "100%" }} /></Row>
                </Group>
              )}
            </>
          ),
        },
        {
          title: "Try it",
          subtitle: mode === "off" ? "Press Done to turn it off." : placed ? "Press Done to use it." : "Test it, then press Done.",
          icon: <Check size={26} />,
          body: mode === "off" || placed ? null : (
            <Group>
              <Row label="Connection" stack>
                <div className="col" style={{ gap: 8, alignItems: "flex-start" }}>
                  <button className="btn" onClick={test} disabled={busy || !url.trim()}>{busy ? <Spinner /> : "Test"}</button>
                  {result && (
                    <div className={`banner ${result.ok ? "ok" : "warn"} small`} role="status" style={{ width: "100%" }}>
                      {result.ok ? (
                        <>
                          <strong>It answers{result.version ? ` (${result.version})` : ""}{result.gpu ? ` on ${result.gpu}` : ""}.</strong>
                          {result.capabilities.length > 0 && <div>It {result.capabilities.map((k) => WORDS[k] || k).join(", ")}.</div>}
                          {result.note && <div>{result.note}</div>}
                          {result.models.filter((m) => m.ready === false).slice(0, 4).map((m) => <div key={m.id} className="muted">{m.label || m.id}: {m.why || "not ready"}</div>)}
                        </>
                      ) : <strong>{result.why_not}</strong>}
                    </div>
                  )}
                </div>
              </Row>
            </Group>
          ),
        },
      ]}
    />
  );
}
