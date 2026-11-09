import { Check, Copy, Cpu, Key, Plug, RefreshCw, Sparkles, Star, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { get, post, put } from "../api";
import { useFetch } from "../hooks";
import { settingsStore, toast } from "../store";
import type { Settings } from "../types";
import { Field, Spinner, copyText } from "../ui";

interface AIStatus {
  provider: string;
  model: string;
  available: boolean;
  images: boolean;
  reason?: string;
  claude?: { found: boolean; logged_in: boolean; plan: string; reason: string; model: string; daily_cap: number; calls_today: number; cost_usd_today: number };
  settings: { ai_provider: string; ai_script: boolean; openai_url: string; openai_model: string; anthropic_model: string; openai_key_set: boolean; anthropic_key_set: boolean };
}

interface Connect {
  token: string;
  http_url: string;
  http_command: string;
  claude_code: string;
  codex: string;
  claude_desktop: unknown;
  cursor: unknown;
  gemini_cli: unknown;
  vscode: unknown;
  chatgpt: string;
}

interface OllamaModel {
  name: string;
}

const copy = (text: string) => copyText(text);

function Snippet({ label, text }: { label: string; text: string }) {
  return (
    <div className="col" style={{ gap: 4 }}>
      <span className="small muted" style={{ fontWeight: 600 }}>{label}</span>
      <div className="row">
        <pre className="code grow" tabIndex={0} style={{ margin: 0, maxHeight: 130, overflow: "auto" }}>{text}</pre>
        <button className="btn sm" onClick={() => copy(text)} aria-label={`Copy ${label}`}><Copy size={13} /> Copy</button>
      </div>
    </div>
  );
}

const onServerItself = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname);

type AssistantRow = { id: string; label: string; installed: boolean; connected: boolean; to: string | null; restart: boolean };
type DesktopAssistants = { status: () => Promise<AssistantRow[]>; connect: (id: string, remote?: { url: string; token?: string }) => Promise<{ note: string }> };
const desktop = (window as any).vtDesktop?.assistants as DesktopAssistants | undefined;

/** One click per assistant (vt/assistants.py on the server computer; desktop/assistants.js when this app is a client of a server elsewhere). */
function OneClickAssistants() {
  const mode: "here" | "desktop" | "browser" = onServerItself ? "here" : desktop ? "desktop" : "browser";
  const [rows, setRows] = useState<AssistantRow[] | null>(null);
  const [busy, setBusy] = useState("");
  const load = async () => {
    try {
      setRows(mode === "here" ? (await get<{ assistants: AssistantRow[] }>("/api/assistants")).assistants : mode === "desktop" ? await desktop!.status() : []);
    } catch {
      setRows([]);
    }
  };
  useEffect(() => { load(); }, []);
  if (mode === "browser") return null;
  const act = async (r: AssistantRow, on: boolean) => {
    setBusy(r.id);
    try {
      let note: string;
      if (mode === "here") note = (await post<{ note: string }>(on ? `/api/assistants/${r.id}/connect` : `/api/assistants/${r.id}/disconnect`)).note;
      else {
        const key = await post<{ url: string; token?: string }>("/api/server/assistant", { name: `${r.label} on this device` });
        note = (await desktop!.connect(r.id, { url: key.url, token: key.token })).note;
      }
      toast(note, "ok", 8000);
      await load();
    } catch (e: any) {
      toast(e.errors?.[0] || e.message, "err", 9000);
    } finally {
      setBusy("");
    }
  };
  return (
    <div className="col" style={{ gap: 8 }} data-testid="one-click-assistants">
      {rows === null && <div className="row muted"><Spinner /> Looking for assistants on this computer…</div>}
      {rows?.map((r) => (
        <div key={r.id} className="row" style={{ gap: 12, alignItems: "center", padding: "10px 12px", borderRadius: 12, background: "var(--panel, transparent)", border: "1px solid var(--line, rgba(128,128,128,.25))" }}>
          <span className="col grow" style={{ gap: 2 }}>
            <strong>{r.label}</strong>
            <span className="small muted">
              {r.connected ? <><Check size={12} /> Connected{r.to && r.to !== "here" ? " to this server" : ""}. {r.restart ? "Restart it once to load the tools." : "Ask it to make a video."}</>
                : r.installed ? "Installed. Not connected yet." : "Not found on this computer."}
            </span>
          </span>
          {r.installed && (
            <button className={`btn sm${r.connected ? "" : " primary"}`} disabled={!!busy} onClick={() => act(r, !r.connected || mode === "desktop")} data-testid={`assistant-${r.id}`}>
              {busy === r.id ? <Spinner /> : r.connected ? (mode === "desktop" ? "Connect again" : "Disconnect") : "Connect"}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

/** An assistant on another computer (or this device, when the Studio comes from a server elsewhere) uses the server's tools at /mcp. On the server's own
 *  network it needs no key (docs/plans/PLAN-CLIENT-SERVER.MD CS6; docs/plans/PLAN-PERFECT.MD decision 7). */
function NetworkAssistant() {
  const server = useFetch<{ exposed: boolean }>("/api/server");
  const [made, setMade] = useState<{ url: string; mcp_json: unknown } | null>(null);
  const [busy, setBusy] = useState(false);
  if (!server.data?.exposed) return null;
  const make = async () => {
    setBusy(true);
    try {
      setMade(await post("/api/server/assistant", { name: onServerItself ? "AI assistant (another computer)" : "AI assistant on this device" }));
    } catch (e: any) {
      toast(e.errors?.[0] || e.message, "err", 8000);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="col" style={{ gap: 10 }} data-testid="network-assistant">
      <span style={{ fontWeight: 600 }}>{onServerItself ? "An assistant on another computer" : "An assistant on this device"}</span>
      <span className="small muted">
        Claude Code, Cursor and others on {onServerItself ? "another computer" : "this device"} can use this server's tools over the network. Nothing to sign in to: the
        computer only has to be on the same network as this server.
      </span>
      {!made && <div><button className="btn sm primary" disabled={busy} onClick={make} data-testid="make-assistant-key">{busy ? <Spinner /> : "Show how to connect an assistant"}</button></div>}
      {made && (
        <>
          <Snippet label="Claude Code: run once on that computer" text={`claude mcp add --transport http video-tool ${made.url}`} />
          <Snippet label="Or put this in .mcp.json (Claude Code, Cursor and others)" text={JSON.stringify(made.mcp_json, null, 2)} />
          <span className="small muted">Run it once on that computer. It works as long as that computer can reach this server.</span>
        </>
      )}
    </div>
  );
}

interface ProviderCardProps {
  id: string;
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  selected: boolean;
  status?: React.ReactNode;
  onSelect: () => void;
  children?: React.ReactNode;
}

function ProviderCard({ id, icon, title, subtitle, selected, status, onSelect, children }: ProviderCardProps) {
  return (
    <div className={`provider-card ${selected ? "selected" : ""}`} onClick={onSelect} id={`provider-${id}`}>
      <div className="provider-card-header" role="radio" aria-checked={selected} tabIndex={0} aria-label={title}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onSelect())}>
        <div className={`provider-icon ${selected ? "selected" : ""}`}>{icon}</div>
        <div className="col grow" style={{ gap: 2, minWidth: 0 }}>
          <div className="row" style={{ gap: 8 }}>
            <strong style={{ fontSize: 14 }}>{title}</strong>
            {status}
          </div>
          <span className="small muted">{subtitle}</span>
        </div>
        <div className={`provider-radio ${selected ? "checked" : ""}`}>
          {selected && <Check size={11} />}
        </div>
      </div>
      {selected && children && (
        <div className="provider-card-body" onClick={(e) => e.stopPropagation()}>
          {children}
        </div>
      )}
    </div>
  );
}

/** Settings: which AI directs the videos, and how other assistants (Claude, ChatGPT, Cursor ...) connect through MCP. */
export default function AIAssistants() {
  const st = useFetch<AIStatus>("/api/ai/status");
  const con = useFetch<Connect>("/api/mcp/connect");
  const [test, setTest] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [showToken, setShowToken] = useState(false);
  const s = st.data?.settings;

  // Fetch Ollama models for the local provider card
  const ollamaModels = useFetch<OllamaModel[] | string[]>("/api/llm/status");

  const save = async (patch: Record<string, unknown>) => {
    try {
      const confirmed = await put<Settings>("/api/settings", patch);
      settingsStore.set(current => ({ ...current, ...confirmed }));
      st.refetch();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };
  const runTest = async () => {
    setBusy(true);
    setTest("");
    try {
      const r = await post<{ ok: boolean; message: string; sample?: string }>("/api/ai/test");
      setTest(`${r.ok ? "Works" : "Failed"}: ${r.message}${r.sample ? ` ${r.sample}` : ""}`);
    } catch (e: any) {
      setTest(`Failed: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };
  const j = (v: unknown) => JSON.stringify(v, null, 2);
  const provider = s?.ai_provider ?? "auto";

  // Extract Ollama models list from the llm/status response
  const llmStatus = ollamaModels.data as any;
  const ollamaModelList: string[] = llmStatus?.models ?? [];
  const currentOllamaModel = llmStatus?.ollama_model ?? "";
  const recommendedModel = llmStatus?.model ?? "";

  const providers = [
    {
      id: "auto",
      icon: <Cpu size={18} />,
      title: "Local AI (Ollama)",
      subtitle: "Private; runs on the server or your GPU server",
    },
    {
      id: "claude_cli",
      icon: <Star size={18} />,
      title: "Claude on the server",
      subtitle: "Uses a Claude login on the server computer. Claude on your own PC is set in the list above",
    },
    {
      id: "best",
      icon: <Sparkles size={18} />,
      title: "Automatic (recommended)",
      subtitle: "Uses the best helper that is ready",
    },
    {
      id: "anthropic",
      icon: <Key size={18} />,
      title: "Claude with a key",
      subtitle: "Use your own paid Claude key",
    },
    {
      id: "openai",
      icon: <Zap size={18} />,
      title: "Another online AI",
      subtitle: "OpenAI, Groq, or anything that works the same way",
    },
    {
      id: "off",
      icon: <span style={{ fontSize: 18, lineHeight: 1 }}>✕</span>,
      title: "Off",
      subtitle: "Use built-in rules only, no AI",
    },
  ];

  return (
    <>
      <details className="card card-pad ai-server-details" data-testid="server-details">
        <summary>Writing AI on the server</summary>
      <section className="col" style={{ gap: 16 }} aria-label="Server AI connection">
        <div className="row">
          <h3 className="grow">Connection</h3>
          {st.data && (
            <span className={`chip ${st.data.available ? "ok" : "warn"}`}>
              {st.data.available ? <Check size={12} /> : null} {st.data.provider}{st.data.model ? ` · ${st.data.model}` : ""}{st.data.available ? "" : " · not available"}
            </span>
          )}
        </div>
        <p className="muted" style={{ margin: 0 }}>
          Connection and account settings for AI steps that run on the server. Your next director is shown in the order above.
        </p>

        <div className="provider-grid" role="radiogroup" aria-label="Director">
          {providers.map((p) => {
            const isSelected = provider === p.id;
            let statusNode: React.ReactNode = null;
            let bodyNode: React.ReactNode = null;

            if (p.id === "auto") {
              const ready = llmStatus?.reachable && llmStatus?.model_ready;
              statusNode = llmStatus ? (
                <span className={`chip ${llmStatus.llm_mode === "off" ? "" : ready ? "ok" : "warn"}`} style={{ fontSize: 11 }}>
                  {llmStatus.llm_mode === "off" ? "Off" : ready ? <><Check size={10} /> Ready</> : llmStatus.reachable ? "Model not ready" : "Not running"}
                </span>
              ) : null;
              bodyNode = (
                <div className="col" style={{ gap: 12 }}>
                  {ollamaModelList.length > 0 ? (
                    <Field label="AI version">
                      <select value={currentOllamaModel} onChange={(e) => save({ ollama_model: e.target.value })}>
                        <option value="">Automatic ({recommendedModel || "auto"})</option>
                        {ollamaModelList.map((m: string) => <option key={m} value={m}>{m}</option>)}
                      </select>
                    </Field>
                  ) : (
                    <span className="small muted">No models found. Make sure the Local AI (Ollama) is running and has at least one model.</span>
                  )}
                  <Field label="Address" hint="Where Ollama is running">
                    <input
                      key={llmStatus?.ollama_url ?? "none"}
                      aria-label="Ollama address"
                      type="text"
                      defaultValue={llmStatus?.ollama_url ?? "http://localhost:11434"}
                      placeholder="http://localhost:11434"
                      spellCheck={false}
                      onBlur={(e) => save({ ollama_url: e.target.value.trim() })}
                    />
                  </Field>
                </div>
              );
            } else if (p.id === "claude_cli" || p.id === "best") {
              const cl = st.data?.claude;
              const ready = !!cl?.logged_in || (p.id === "best" && !!llmStatus?.reachable && !!llmStatus?.model_ready && llmStatus?.llm_mode !== "off");
              statusNode = cl || llmStatus ? (
                <span className={`chip ${ready ? "ok" : "warn"}`} style={{ fontSize: 11 }}>
                  {ready ? <><Check size={10} /> Ready</> : "Needs attention"}
                </span>
              ) : null;
              bodyNode = cl ? (
                <div className="col" style={{ gap: 10 }}>
                  {!cl.logged_in && <span className="small muted">{cl.reason}</span>}
                  {p.id === "best" && <span className="small muted">Uses Claude while ready, falls back to Ollama automatically. Pictures are always processed by the local model.</span>}
                  {p.id === "claude_cli" && <span className="small muted">Your Claude subscription, no API key. What the AI reads is sent to Anthropic as when you use Claude yourself.</span>}
                  <div className="row wrap" style={{ gap: 12 }}>
                    <Field label="Model"><input type="text" defaultValue={cl.model} placeholder="sonnet" onBlur={(e) => save({ claude_cli_model: e.target.value.trim() || "sonnet" })} /></Field>
                    <Field label="Calls per day"><input type="number" min={1} max={5000} defaultValue={cl.daily_cap} onBlur={(e) => save({ claude_cli_daily_cap: Math.max(1, Number(e.target.value) || 200) })} /></Field>
                    <span className="small muted" role="status">Today: {cl.calls_today} calls · ~${cl.cost_usd_today.toFixed(2)}</span>
                  </div>
                  <button className="btn sm ghost" onClick={() => st.refetch()} aria-label="Check again"><RefreshCw size={13} /> Refresh status</button>
                </div>
              ) : null;
            } else if (p.id === "anthropic") {
              bodyNode = (
                <div className="row wrap" style={{ gap: 12 }}>
                  <Field label="Model"><input type="text" defaultValue={s?.anthropic_model} placeholder="claude-sonnet-4-5" onBlur={(e) => save({ anthropic_model: e.target.value })} /></Field>
                  <Field label={s?.anthropic_key_set ? "Key (saved)" : "Key"}><input type="password" placeholder={s?.anthropic_key_set ? "••••••••" : "sk-ant-…"} onBlur={(e) => e.target.value && save({ anthropic_key: e.target.value })} /></Field>
                </div>
              );
            } else if (p.id === "openai") {
              bodyNode = (
                <div className="row wrap" style={{ gap: 12 }}>
                  <Field label="Address"><input type="text" defaultValue={s?.openai_url} placeholder="https://api.openai.com/v1" onBlur={(e) => save({ openai_url: e.target.value })} /></Field>
                  <Field label="Model"><input type="text" defaultValue={s?.openai_model} placeholder="gpt-4o-mini" onBlur={(e) => save({ openai_model: e.target.value })} /></Field>
                  <Field label={s?.openai_key_set ? "Key (saved)" : "Key"}><input type="password" placeholder={s?.openai_key_set ? "••••••••" : "sk-…"} onBlur={(e) => e.target.value && save({ openai_key: e.target.value })} /></Field>
                </div>
              );
            }

            return (
              <ProviderCard
                key={p.id}
                id={p.id}
                icon={p.icon}
                title={p.title}
                subtitle={p.subtitle}
                selected={isSelected}
                status={statusNode}
                onSelect={() => save(p.id === "openai" ? { ai_provider: p.id, ai_script: true } : { ai_provider: p.id })}
              >
                {bodyNode}
              </ProviderCard>
            );
          })}
        </div>

        <div className="row" style={{ borderTop: "0.5px solid var(--border)", paddingTop: 12, flexWrap: "wrap", gap: 10 }}>
          <label className="row" style={{ gap: 6 }}>
            <input type="checkbox" checked={!!s?.ai_script} onChange={(e) => save({ ai_script: e.target.checked })} />
            <span>Let AI direct all video types (not only stick-figure videos)</span>
          </label>
          <div className="spacer" />
          <button className="btn sm" onClick={runTest} disabled={busy}>{busy ? <Spinner /> : <Plug size={13} />} Test AI connection</button>
          {test && <span className="small muted" role="status">{test}</span>}
        </div>
        <span className="small muted">Keys are kept on the server and never shown again.</span>
      </section>
      </details>

      <section className="card card-pad col" style={{ gap: 12 }} aria-label="AI assistants">
        <div className="row">
          <h2 className="grow">Use your own AI assistant</h2>
          <button className="btn sm" onClick={() => con.refetch()}><RefreshCw size={13} /> Refresh</button>
        </div>
        <p className="muted" style={{ margin: 0 }}>
          Claude and Codex can make and edit videos with your own subscription. One click connects them.
        </p>
        <OneClickAssistants />
        {!onServerItself && !desktop && <NetworkAssistant />}
        {onServerItself && <NetworkAssistant />}
        {onServerItself && con.data && (
          <>
            <details>
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>Set up Claude Code or Codex by hand</summary>
              <div className="col" style={{ gap: 10, marginTop: 10 }}>
                <Snippet label="Claude Code (terminal or VS Code): run once" text={con.data.claude_code} />
                <Snippet label="Codex (terminal or IDE): run once" text={con.data.codex} />
              </div>
            </details>
            <details data-testid="other-assistants">
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>Other assistants: Cursor, Windsurf, VS Code, Gemini</summary>
            <Snippet label="Cursor (.cursor/mcp.json) / Windsurf" text={j(con.data.cursor)} />
            <Snippet label="VS Code Copilot agent mode (.vscode/mcp.json)" text={j(con.data.vscode)} />
            <Snippet label="Gemini CLI (~/.gemini/settings.json)" text={j(con.data.gemini_cli)} />
            </details>
            <details>
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>ChatGPT and other online assistants</summary>
              <div className="col" style={{ gap: 10, marginTop: 10 }}>
                <p className="small muted" style={{ margin: 0 }}>{con.data.chatgpt}</p>
                <Snippet label="1. Start the HTTP server" text={con.data.http_command} />
                <Snippet label="2. Address (before the tunnel)" text={con.data.http_url} />
                <div className="col" style={{ gap: 4 }}>
                  <span className="small muted" style={{ fontWeight: 600 }}>3. Token (send as "Authorization: Bearer …")</span>
                  <div className="row">
                    <pre className="code grow" tabIndex={0} style={{ margin: 0 }}>{showToken ? con.data.token : "•".repeat(24)}</pre>
                    <button className="btn sm" onClick={() => setShowToken(!showToken)}>{showToken ? "Hide" : "Show"}</button>
                    <button className="btn sm" onClick={() => copy(con.data!.token)}><Copy size={13} /> Copy</button>
                    <button className="btn sm danger" onClick={() => post("/api/mcp/token/revoke").then(() => { con.refetch(); toast("Old token revoked", "ok"); })}>Revoke</button>
                  </div>
                </div>
              </div>
            </details>
            <p className="small muted" style={{ margin: 0 }}>
              Another chat assistant? In a video, choose <strong>Ask any chat assistant</strong>, paste the message into it, and paste its answer back.
            </p>
          </>
        )}
      </section>
    </>
  );
}
