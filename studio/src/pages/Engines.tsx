import { Check, Cpu, Image as ImageIcon, MessageSquare, Mic, Server } from "lucide-react";
import { useEffect, useState } from "react";
import { del, get, post, put } from "../api";
import { Group, Row, Steps } from "../ds";
import { useFetch } from "../hooks";
import { toast } from "../store";
import { Seg, Spinner } from "../ui";
import SetupWizard from "../components/SetupWizard";

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
const HERE_ENGINES = ["ollama", "comfy", "voicestudio"];
const isHere = (u: string) => /^https?:\/\/(127\.0\.0\.1|localhost)(:|\/|$)/.test(u);
const ICON: Record<string, JSX.Element> = { llm: <MessageSquare size={18} />, image: <ImageIcon size={18} />, voice: <Mic size={18} /> };
const WORDS: Record<string, string> = {
  "llm.chat": "writes and reads", "llm.vision": "looks at pictures", "image.generate": "draws pictures", "video.generate": "makes short clips",
  "voice.speak": "speaks", "voice.list": "lists voices", "voice.clone": "clones a voice", "voice.design": "designs a voice",
};

function where(c: Card): string {
  const m = c.endpoint.mode;
  if (m === "off") return "Not connected";
  if (m === "local") return "Video Tool's own copy, on the server computer";
  if (isHere(c.endpoint.url)) return "Already installed on the server computer";
  return c.endpoint.url.replace(/^https?:\/\//, "");
}

export default function Engines() {
  const list = useFetch<Card[]>("/api/engines");
  const [editing, setEditing] = useState<Card | null>(null);
  const [wizard, setWizard] = useState(false);
  return (
    <section className="card card-pad col" style={{ gap: 14 }} aria-label="Engines" data-testid="engines">
      <div className="row wrap">
        <h2 className="grow"><Server size={18} style={{ verticalAlign: -3 }} /> Engines</h2>
        <button className="btn sm" onClick={() => setWizard(true)} data-testid="run-setup">Run setup</button>
        <button className="btn sm" onClick={() => list.refetch()}>{list.loading ? <Spinner /> : "Check again"}</button>
      </div>
      <p className="muted" style={{ margin: 0 }}>
        What makes your videos: a language AI, a picture and clip maker, and voices. Each can run on this computer or on another one you own. Connect what you have; the app uses its built-in
        fallbacks for the rest.
      </p>
      {list.loading && !list.data && <Spinner />}
      <div className="col" style={{ gap: 10 }}>
        {(list.data ?? []).map((c) => (
          <div key={c.id} className="engine-card" data-engine={c.id}>
            <span className="engine-ic" aria-hidden>{ICON[c.kind] ?? <Cpu size={18} />}</span>
            <div className="col grow" style={{ gap: 2, minWidth: 0 }}>
              <strong>{c.label}</strong>
              <span className="small muted">{where(c)}{c.health?.gpu ? ` · ${c.health.gpu}` : ""}{c.health?.version ? ` · ${c.health.version}` : ""}</span>
              {c.health?.ok && c.health.capabilities.length > 0 && <span className="small">{c.health.capabilities.map((k) => WORDS[k] || k).join(", ")}</span>}
              {c.health && !c.health.ok && c.endpoint.mode !== "off" && <span className="small" style={{ color: "var(--err)" }}>{c.health.why_not}</span>}
              {c.health?.ok && c.health.note && <span className="small" style={{ color: "var(--warn)" }}>{c.health.note}</span>}
            </div>
            <span className={`chip ${c.health?.ok ? "ok" : c.endpoint.mode === "off" ? "" : "warn"}`}>{c.health?.ok ? <><Check size={12} /> Ready</> : c.endpoint.mode === "off" ? "Off" : "Not ready"}</span>
            <button className="btn sm" onClick={() => setEditing(c)} aria-label={`Change ${c.label}`}>Change</button>
          </div>
        ))}
      </div>
      <ShareCard />
      {wizard && <SetupWizard onClose={() => { setWizard(false); list.refetch(); }} />}
      {editing && <EngineSheet card={editing} onClose={() => { setEditing(null); list.refetch(); }} />}
    </section>
  );
}

/* This computer as the engine for others: the same programs, offered at one address with one code (vt engine run). */
interface HubState { running: boolean; port: number; addresses: string[]; offers?: string[]; mine: boolean; code?: string }
type ServerInfo = { name: string; exposed: boolean; addresses?: string[]; autostart?: boolean };
type Device = { id: string; name: string; paired: number };

/** Started as a server (`vt server`), this Studio is already shared: show where to reach it, hand out pairing codes, list paired devices. */
function ThisServerCard({ info }: { info: ServerInfo }) {
  const [code, setCode] = useState("");
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
  const [devices, setDevices] = useState<Device[] | null>(null);
  const loadDevices = () => get<Device[]>("/api/server/clients").then(setDevices).catch(() => setDevices(null));
  useEffect(() => { if (info.addresses) loadDevices(); }, [info.addresses]);
  const revoke = async (d: Device) => {
    if (!confirm(`Turn "${d.name}" away? It will need a new pairing code to come back.`)) return;
    try {
      await del(`/api/server/clients/${d.id}`);
      toast(`${d.name} can no longer use this server`, "ok");
      loadDevices();
    } catch (e: any) {
      toast(e.errors?.[0] || e.message, "err", 8000);
    }
  };
  const newCode = async () => {
    setBusy(true);
    try {
      setCode((await post<{ code: string }>("/api/server/code")).code);
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
        <strong>This server: {info.name}</strong>
        <span className="small muted">Other computers and phones on this network can open Video Tool here. They find it by themselves, or type an address below, then enter a pairing code once.</span>
        {info.addresses?.map((a) => <span key={a} className="small bn" style={{ userSelect: "all" }}>Address: {a}</span>)}
        {code && <span className="small" style={{ userSelect: "all" }}>Pairing code (works once): <strong data-testid="server-code">{code}</strong></span>}
        {devices && devices.length > 0 && (
          <div className="col" style={{ gap: 4, marginTop: 6 }} data-testid="paired-devices">
            <span className="small muted">Paired devices</span>
            {devices.map((d) => (
              <span key={d.id} className="row small" style={{ gap: 8, alignItems: "center" }}>
                <span className="grow">{d.name} <span className="muted">· since {new Date(d.paired * 1000).toLocaleDateString()}</span></span>
                <button className="btn sm" onClick={() => revoke(d)}>Revoke</button>
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="col" style={{ gap: 6, alignItems: "stretch" }}>
        {info.addresses && <button className="btn sm primary" disabled={busy} onClick={newCode} data-testid="server-new-code">{busy ? <Spinner /> : "New pairing code"}</button>}
        {auto !== undefined && <button className="btn sm" disabled={busy} onClick={toggleAuto} data-testid="server-autostart" title="With the same engines and port as now">{auto ? "Don't start by itself" : "Start by itself"}</button>}
      </div>
    </div>
  );
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
        <span className="small muted">{on ? "Other computers can use this one's language AI and pictures. On the other computer: Engines, Another Video Tool computer." : "Let a second computer running Video Tool use the programs installed here."}</span>
        {on && h?.addresses.map((a) => <span key={a} className="small bn" style={{ userSelect: "all" }}>Address: {a}</span>)}
        {on && h?.code && <span className="small" style={{ userSelect: "all" }}>Pairing code (works once): <strong data-testid="share-code">{h.code}</strong></span>}
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
      if (card.id === "vtengine" && mode !== "off" && key.trim()) { const r = await post<{ also_connected?: string[] }>(`/api/engines/vtengine/pair`, { url, code: key.trim() }); if (r.also_connected?.length) toast(`Also connected: ${r.also_connected.map((n) => (n === "ollama" ? "language AI" : "pictures and clips")).join(", ")}`, "ok", 5000); }     // the code is traded for the key; the key is never shown
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
            <Group title="Where does it run?" note={canHere ? "\"This computer\" is the one running the Video Tool server." : undefined}>
              <Row label="Choose" stack>
                <Seg<Mode> label="Where it runs" value={mode} onChange={setMode}
                  options={[
                    ...(canHere ? [{ value: "here" as Mode, label: "Already on this computer" }] : []),
                    ...(here?.own_possible ? [{ value: "own" as Mode, label: "Video Tool's own copy" }] : []),
                    { value: "remote" as Mode, label: "Another computer" }, { value: "off" as Mode, label: "Off" }]} />
              </Row>
              {mode === "here" && here && (here.existing.length
                ? <p className="small" style={{ margin: 0 }} data-testid="here-found">Found {here.existing.length > 1 ? `${here.existing.length} running` : "one running"}: {here.existing.map((u) => u.replace(/^https?:\/\//, "")).join(", ")}. Video Tool uses {here.existing.length > 1 ? "them" : "it"} as {here.existing.length > 1 ? "they are" : "it is"} and never starts, stops or changes {here.existing.length > 1 ? "them" : "it"}.</p>
                : <p className="small" style={{ margin: 0, color: "var(--warn)" }}>Nothing answers on its usual port on this computer. Start it, choose Video Tool's own copy, or give its address under Another computer.</p>)}
              {mode === "own" && here && (here.own_installed
                ? <p className="small" style={{ margin: 0 }}>Its own folder and its own port ({here.own_url.replace(/^https?:\/\//, "")}), so it never collides with another copy on this computer. It starts when you press Done.</p>
                : <p className="small" style={{ margin: 0, color: "var(--warn)" }}>Not installed yet. Press <strong>Run setup</strong> on the Engines page to install it, then come back here.</p>)}
            </Group>
          ),
        },
        {
          title: "Connect",
          subtitle: mode === "off" ? "Nothing to connect: this engine stays off and the built-in fallback is used." : placed ? "Nothing to type: Video Tool knows where it is." : "The address of the computer that runs it, and the key if it has one.",
          icon: <Server size={26} />,
          body: mode === "off" || placed ? null : (
            <>
              <Group title="Address">
                <Row label="Address" stack><input type="text" value={url} placeholder={card.default_url || "http://192.168.1.20:8188"} onChange={(e) => setUrl(e.target.value)} spellCheck={false} aria-label="Address" style={{ width: "100%" }} /></Row>
                {card.needs_key && card.id !== "vtengine" && <Row label="Key" stack><input type="password" value={key} placeholder={card.endpoint.has_key ? "Saved. Type a new one to replace it" : "Paste the key"} onChange={(e) => setKey(e.target.value)} aria-label="Key" autoComplete="off" style={{ width: "100%" }} /></Row>}
                {card.id === "vtengine" && <Row label="Pairing code" stack><input type="text" value={key} placeholder={card.endpoint.has_key ? "Paired. Type a new code to pair again" : "The code shown on the other computer (vt serve-engine)"} onChange={(e) => setKey(e.target.value)} aria-label="Pairing code" autoComplete="off" spellCheck={false} style={{ width: "100%" }} /></Row>}
              </Group>
              {card.kind === "image" && (
                <Group title="More computers" note="Another ComfyUI on a second graphics card, one address per line. A job goes to the one that can run it.">
                  <Row label="Addresses" stack><textarea value={workers} rows={2} onChange={(e) => setWorkers(e.target.value)} spellCheck={false} aria-label="More computers" style={{ width: "100%" }} /></Row>
                </Group>
              )}
            </>
          ),
        },
        {
          title: "Try it",
          subtitle: mode === "off" ? "Press Done to turn it off." : placed ? "Press Done to use it." : "Test the connection, then press Done to save.",
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
