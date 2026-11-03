import { AlertTriangle, Check, Cpu, Sparkles, Wand2, X, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { post } from "../api";
import { useFetch } from "../hooks";
import { toast } from "../store";
import { Field, Seg, Spinner } from "../ui";

export interface RedoModalProps {
  id: string;
  title?: string;
  open: boolean;
  onClose: () => void;
  defaultScope?: "plan" | "preprocess";
}

interface AIStatus {
  provider: string;
  model: string;
  available: boolean;
  images: boolean;
  claude?: {
    logged_in: boolean;
    model: string;
    calls_today: number;
    daily_cap: number;
    reason?: string;
  };
  settings?: {
    ai_provider: string;
    openai_url?: string;
    openai_model?: string;
    anthropic_model?: string;
    openai_key_set?: boolean;
    anthropic_key_set?: boolean;
  };
}

interface LLMStatus {
  llm_mode: string;
  reachable: boolean;
  model_ready: boolean;
  model: string;
  ollama_model: string;
  models: string[];
}

const PROVIDERS = [
  { id: "auto", name: "Local Ollama", desc: "Free, private, offline on this machine" },
  { id: "claude_cli", name: "Claude (my login)", desc: "Direct Anthropic via Claude Code CLI" },
  { id: "best", name: "Best Available", desc: "Claude when ready, auto-fallback to Ollama" },
  { id: "anthropic", name: "Claude API Key", desc: "Direct Anthropic API key" },
  { id: "openai", name: "OpenAI-compatible", desc: "OpenAI, Groq, or custom endpoint" },
  { id: "off", name: "Built-in Rules", desc: "Deterministic layout rules, no AI" },
];

const KINDS = [
  { value: "stick", label: "Stick figure" },
  { value: "explainer", label: "Explainer" },
  { value: "emoji", label: "Emoji" },
  { value: "infographic", label: "Infographic" },
  { value: "cartoon", label: "Cartoon" },
  { value: "mixed", label: "Mixed" },
];

export default function RedoModal({ id, title, open, onClose, defaultScope = "plan" }: RedoModalProps) {
  const nav = useNavigate();
  const ai = useFetch<AIStatus>("/api/ai/status");
  const llm = useFetch<LLMStatus>("/api/llm/status");
  const script = useFetch<{ kind: string }>(`/api/projects/${id}/script`);

  const [provider, setProvider] = useState<string>("auto");
  const [model, setModel] = useState<string>("");
  const [kind, setKind] = useState<string>("stick");
  const [scope, setScope] = useState<"plan" | "preprocess">(defaultScope);
  const [autopilot, setAutopilot] = useState<boolean>(true);
  const [busy, setBusy] = useState<boolean>(false);

  useEffect(() => {
    if (ai.data?.settings?.ai_provider) {
      setProvider(ai.data.settings.ai_provider);
    }
  }, [ai.data?.settings?.ai_provider]);

  useEffect(() => {
    if (script.data?.kind) {
      setKind(script.data.kind);
    }
  }, [script.data?.kind]);

  useEffect(() => {
    if (provider === "auto" && llm.data) {
      setModel(llm.data.ollama_model || llm.data.model || (llm.data.models?.[0] ?? ""));
    } else if (provider === "claude_cli" && ai.data?.claude) {
      setModel(ai.data.claude.model || "sonnet");
    } else if (provider === "anthropic" && ai.data?.settings) {
      setModel(ai.data.settings.anthropic_model || "claude-sonnet-4-5");
    } else if (provider === "openai" && ai.data?.settings) {
      setModel(ai.data.settings.openai_model || "gpt-4o-mini");
    }
  }, [provider, llm.data, ai.data]);

  if (!open) return null;

  const runRedo = async () => {
    setBusy(true);
    try {
      await post(`/api/projects/${id}/run`, {
        from_stage: scope,
        force: true,
        rerender: autopilot,
        ai_provider: provider,
        ai_model: model || undefined,
        video_kind: kind,
      });
      toast(`Redoing video with ${provider === "off" ? "built-in rules" : model || provider}…`, "ok");
      onClose();
      nav(`/p/${id}/progress`);
    } catch (e: any) {
      toast(e.message || "Failed to start redo", "err", 7000);
      setBusy(false);
    }
  };

  const ollamaModels = llm.data?.models || [];

  return (
    <div className="modal-back" onClick={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div className="modal" style={{ maxWidth: 580 }} role="dialog" aria-modal="true" aria-labelledby="redo-title">
        <div className="modal-head" style={{ justifyContent: "space-between" }}>
          <div className="row" style={{ gap: 10 }}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 10,
                background: "var(--grad)",
                display: "grid",
                placeItems: "center",
                color: "#fff",
              }}
            >
              <Wand2 size={18} />
            </div>
            <div className="col" style={{ gap: 1 }}>
              <strong id="redo-title" style={{ fontSize: 16 }}>Redo video with AI model</strong>
              {title && <span className="small muted bn">{title}</span>}
            </div>
          </div>
          <button
            type="button"
            className="btn icon sm ghost"
            onClick={onClose}
            disabled={busy}
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <div className="modal-body" style={{ gap: 16 }}>
          <div className="banner" style={{ fontSize: 13, gap: 10 }}>
            <Sparkles size={16} style={{ flexShrink: 0 }} />
            <span>
              Select an AI model to re-plan scenes, visuals and story graphics from your audio.
            </span>
          </div>

          <Field label="AI Provider">
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              disabled={busy}
            >
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} — {p.desc}
                </option>
              ))}
            </select>
          </Field>

          {provider === "auto" && (
            <Field
              label="Ollama Model"
              hint={
                ollamaModels.length === 0
                  ? "No models detected in Ollama. Make sure Ollama is running."
                  : undefined
              }
            >
              {ollamaModels.length > 0 ? (
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  disabled={busy}
                >
                  <option value="">Automatic ({llm.data?.model || "default"})</option>
                  {ollamaModels.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  placeholder="e.g. qwen2.5:7b or llama3.2"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  disabled={busy}
                />
              )}
            </Field>
          )}

          {provider === "claude_cli" && (
            <Field
              label="Claude Model"
              hint={
                ai.data?.claude?.logged_in
                  ? `Logged into Claude Code · ~${ai.data.claude.calls_today} calls today`
                  : "Claude Code CLI login not detected"
              }
            >
              <input
                type="text"
                placeholder="sonnet"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={busy}
              />
            </Field>
          )}

          {provider === "anthropic" && (
            <Field
              label="Anthropic Model"
              hint={ai.data?.settings?.anthropic_key_set ? "Key saved" : "Set key in Settings"}
            >
              <input
                type="text"
                placeholder="claude-sonnet-4-5"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={busy}
              />
            </Field>
          )}

          {provider === "openai" && (
            <Field
              label="OpenAI Model"
              hint={ai.data?.settings?.openai_key_set ? "Key saved" : "Set key in Settings"}
            >
              <input
                type="text"
                placeholder="gpt-4o-mini"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={busy}
              />
            </Field>
          )}

          <div className="col" style={{ gap: 6 }}>
            <span className="small muted" style={{ fontWeight: 600 }}>Visual Style</span>
            <Seg
              value={kind}
              onChange={setKind}
              label="Visual Style"
              options={KINDS}
            />
          </div>

          <div className="col" style={{ gap: 6 }}>
            <span className="small muted" style={{ fontWeight: 600 }}>What to redo</span>
            <div className="row wrap" style={{ gap: 10 }}>
              <label
                className={`card card-pad grow ${scope === "plan" ? "sel" : ""}`}
                style={{
                  cursor: "pointer",
                  display: "flex",
                  gap: 10,
                  alignItems: "flex-start",
                  boxShadow: scope === "plan" ? "0 0 0 2px var(--accent)" : undefined,
                  background: scope === "plan" ? "var(--accent-soft)" : "var(--panel-2)",
                  padding: 12,
                }}
              >
                <input
                  type="radio"
                  name="redo-scope"
                  checked={scope === "plan"}
                  onChange={() => setScope("plan")}
                  style={{ marginTop: 2 }}
                />
                <div className="col" style={{ gap: 2 }}>
                  <strong style={{ fontSize: 13 }}>Re-direct scenes & visuals</strong>
                  <span className="small muted">
                    Keeps speech timing & cuts intact. AI creates a brand new plan with fresh scenes. Fast and recommended.
                  </span>
                </div>
              </label>

              <label
                className={`card card-pad grow ${scope === "preprocess" ? "sel" : ""}`}
                style={{
                  cursor: "pointer",
                  display: "flex",
                  gap: 10,
                  alignItems: "flex-start",
                  boxShadow: scope === "preprocess" ? "0 0 0 2px var(--accent)" : undefined,
                  background: scope === "preprocess" ? "var(--accent-soft)" : "var(--panel-2)",
                  padding: 12,
                }}
              >
                <input
                  type="radio"
                  name="redo-scope"
                  checked={scope === "preprocess"}
                  onChange={() => setScope("preprocess")}
                  style={{ marginTop: 2 }}
                />
                <div className="col" style={{ gap: 2 }}>
                  <strong style={{ fontSize: 13 }}>Start completely over</strong>
                  <span className="small muted">
                    Re-processes sound, pauses, words, cuts and directs whole video from the beginning.
                  </span>
                </div>
              </label>
            </div>
          </div>

          <label className="row" style={{ gap: 12, cursor: "pointer", paddingTop: 4 }}>
            <input
              type="checkbox"
              className="ios-switch"
              checked={autopilot}
              onChange={(e) => setAutopilot(e.target.checked)}
              disabled={busy}
            />
            <div className="col" style={{ gap: 2 }}>
              <strong style={{ fontSize: 13 }}>Render finished video automatically</strong>
              <span className="small muted">
                When on, it renders the video and opens the finished export once ready.
              </span>
            </div>
          </label>
        </div>

        <div className="modal-foot">
          <button type="button" className="btn ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            type="button"
            className="btn primary"
            onClick={runRedo}
            disabled={busy}
          >
            {busy ? <Spinner /> : <Sparkles size={15} />} Redo video
          </button>
        </div>
      </div>
    </div>
  );
}
