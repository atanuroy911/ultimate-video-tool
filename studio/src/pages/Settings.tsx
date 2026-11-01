import { Check, Copy, Download, RefreshCw, X } from "lucide-react";
import { useEffect } from "react";
import { post, put } from "../api";
import { useFetch, useMusic, useThemes } from "../hooks";
import { setLanguage } from "../i18n";
import { connStore, jobsStore, settingsStore, toast, useStore } from "../store";
import type { DoctorRow, McpStatus, ModelInfo, Settings } from "../types";
import { Field, ProgressBar, Seg, Spinner, copyText } from "../ui";
import AIAssistants from "./AIAssistants";
import ComfySettings from "./ComfySettings";
import Engines from "./Engines";
import LocalAI from "./LocalAI";
import MyVoices from "./MyVoices";
import StockKeys from "./StockKeys";

export default function SettingsPage() {
  const settings = useStore(settingsStore);
  const mcp = useStore(connStore).mcp;
  const doctor = useFetch<DoctorRow[]>("/api/doctor");
  const models = useFetch<ModelInfo[]>("/api/models");
  const { data: themes } = useThemes();
  const { data: music } = useMusic();
  const jobs = useStore(jobsStore);
  const pulls = Object.values(jobs).filter((j) => j.kind === "model");

  useEffect(() => {
    if (pulls.some((j) => j.status === "done")) {
      models.refetch();
      doctor.refetch();
    }
  }, [pulls.map((j) => j.status).join()]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (patch: Partial<Settings>) => {
    const next = { ...settings, ...patch };
    settingsStore.set(next);
    try {
      await put("/api/settings", next);
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  const pending = (mcp as McpStatus | null)?.pending ?? 0;
  return (
    <div className="page-inner" style={{ maxWidth: 1060 }}>
      <h1>Settings</h1>
      <div className="settings-layout">
      <nav className="settings-nav" aria-label="Settings sections">
        {[["general", "General"], ["speech", "Speech"], ["engines", "Engines"], ["ai", "AI and assistants"], ["stock", "Stock and keys"], ["claude", "Claude (MCP)"], ["codex", "Codex (MCP)"], ["system", "System check"]].map(([k, l]) => (
          <a key={k} href={`#${k}`} onClick={(e) => { e.preventDefault(); document.getElementById(k)?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>{l}</a>
        ))}
      </nav>
      <div className="settings-body">
      <section id="general" className="card card-pad col" style={{ gap: 12 }}>
        <h2>Defaults for new videos</h2>
        <label className="row" style={{ gap: 12 }}>
          <input type="checkbox" className="ios-switch" checked={settings.autopilot !== false} onChange={(e) => save({ autopilot: e.target.checked })} aria-label="Autopilot" />
          <span className="col" style={{ gap: 2 }}>
            <strong>Autopilot</strong>
            <span className="small muted">After you speak, the app edits, renders, checks and writes the title by itself, and opens the finished video. Off: it stops at the editor.</span>
          </span>
        </label>
        <div className="col" style={{ gap: 6 }} data-testid="plan-review-setting">
          <strong>Show me the plan first</strong>
          <Seg<"when_expensive" | "always" | "never"> label="Show me the plan first" value={(settings.plan_review as any) || "when_expensive"} onChange={(v) => save({ plan_review: v })}
            options={[{ value: "when_expensive", label: "When it is big" }, { value: "always", label: "Always" }, { value: "never", label: "Never" }]} />
          <span className="small muted">Before any picture is drawn, a reel shows what it plans: you can change it, then press Start. Only reels have a plan to look at.</span>
        </div>
        <div className="row wrap" style={{ gap: 16, alignItems: "flex-end" }}>
          <Field label="Theme">
            <select value={settings.default_theme} onChange={(e) => save({ default_theme: e.target.value })}>
              <option value="auto">Automatic (a new look that matches each video)</option>
              {(themes || []).map((t) => <option key={t.name} value={t.name}>{t.label || t.name}</option>)}
            </select>
          </Field>
          <div className="col" style={{ gap: 5 }}>
            <span className="small muted" style={{ fontWeight: 600 }}>Shape</span>
            <Seg value={settings.default_aspect} onChange={(v) => save({ default_aspect: v })} label="Default shape" options={[{ value: "9:16", label: "9:16" }, { value: "1:1", label: "1:1" }, { value: "16:9", label: "16:9" }]} />
          </div>
          <div className="col" style={{ gap: 5 }}>
            <span className="small muted" style={{ fontWeight: 600 }}>Pace</span>
            <Seg value={settings.default_pace as any} onChange={(v) => save({ default_pace: v })} label="Default pace" options={[{ value: "calm", label: "Calm" }, { value: "normal", label: "Normal" }, { value: "fast", label: "Fast" }]} />
          </div>
          <Field label="Music">
            <select value={settings.default_music || ""} onChange={(e) => save({ default_music: e.target.value || null })}>
              <option value="auto">Auto: fits the video</option>
              <option value="">No music</option>
              {(music || []).map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
            </select>
          </Field>
          <div className="col" style={{ gap: 5 }}>
            <span className="small muted" style={{ fontWeight: 600 }}>App language</span>
            <Seg value={settings.ui_language} onChange={(v) => { setLanguage(v); save({ ui_language: v }); }} label="App language" options={[{ value: "en", label: "English" }, { value: "bn", label: "বাংলা" }]} />
          </div>
        </div>
      </section>

      <MyVoices />

      <section id="speech" className="card card-pad col" style={{ gap: 12 }}>
        <h2>Speech recognition models</h2>
        <table className="table">
          <thead><tr><th>Model</th><th>About</th><th /></tr></thead>
          <tbody>
            {(models.data || []).map((m) => {
              const job = pulls.find((j) => j.label.endsWith(m.key) && (j.status === "running" || j.status === "queued"));
              return (
                <tr key={m.key}>
                  <td><strong>{m.key}</strong></td>
                  <td className="muted">{m.note}</td>
                  <td style={{ width: 200 }}>
                    {m.installed ? <span className="chip ok"><Check size={12} /> installed</span> : job ? (
                      <div className="col" style={{ gap: 4 }}><ProgressBar frac={job.frac} /><span className="small muted">{job.msg || "downloading…"}</span></div>
                    ) : (
                      <button className="btn sm" onClick={() => post(`/api/models/${m.key}/pull`).then(() => toast("Download started. It can take several minutes."))}><Download size={13} /> Download</button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <span className="small muted">Models download once into the app folder. Without a graphics card, transcription runs on the CPU and is slower.</span>
      </section>

      <div id="engines" className="col" style={{ gap: 22 }}>
      <Engines />
      </div>
      <div id="ai" className="col" style={{ gap: 22 }}>
      <AIAssistants />
      <LocalAI />
      <ComfySettings />
      </div>
      <div id="stock"><StockKeys /></div>

      <section id="claude" className="card card-pad col" style={{ gap: 12 }}>
        <div className="row">
          <h2 className="grow">Claude connection (optional)</h2>
          <span className={`chip ${mcp?.connected ? "ok" : "warn"}`}>
            {mcp?.connected ? <Check size={12} /> : null} {mcp?.connected ? `Connected · last used ${mcp.seconds_ago}s ago` : "Not connected yet"}
          </span>
        </div>
        <p style={{ margin: 0 }} className="muted">
          Scene planning is done by Claude Code through a local connector. The app never needs an API key and nothing is sent anywhere else. Without Claude the app still makes a complete draft with its built-in rules.
        </p>
        <ol style={{ margin: 0, paddingLeft: 20, display: "flex", flexDirection: "column", gap: 8 }}>
          <li>
            One-time setup: run this in a terminal.
            <div className="row" style={{ marginTop: 6 }}>
              <pre className="code grow" tabIndex={0}>{mcp?.add_command ?? "…"}</pre>
              <button className="btn sm" onClick={() => mcp && copyText(mcp.add_command)}><Copy size={13} /> Copy</button>
            </div>
          </li>
          <li>Open Claude Code in this project folder (it also adds the <code>/vt-plan</code> command).</li>
          <li>Press <strong>Plan with Claude</strong> in a video, then tell Claude Code: <code>{mcp?.say ?? "plan my pending videos"}</code></li>
        </ol>
        <span className="small muted">{pending} request{pending === 1 ? "" : "s"} waiting right now.</span>
      </section>

      <section id="codex" className="card card-pad col" style={{ gap: 12 }}>
        <div className="row"><h2 className="grow">Codex connection</h2><span className={`chip ${mcp?.codex_connected ? "ok" : "warn"}`}>{mcp?.codex_connected ? `Connected · last used ${mcp.codex_seconds_ago}s ago` : "Waiting for a Codex tool call"}</span></div>
        <p className="muted" style={{ margin: 0 }}>Codex can read the transcript, direct every scene through the Video Script, inspect preview frames, revise the plan, and render through the same local MCP server.</p>
        <div className="row wrap"><pre className="code grow" tabIndex={0}>{mcp?.codex_add_command || "Loading…"}</pre><button className="btn sm" onClick={() => mcp && copyText(mcp.codex_add_command)}><Copy size={13} /> Copy</button></div>
        <button className="btn sm primary" onClick={() => post<{ note: string }>("/api/mcp/connect-codex").then(r => toast(r.note, "ok", 7000)).catch(e => toast(e.message, "err", 7000))}>Connect Codex on this computer</button>
        <span className="small muted">Then restart Codex and ask it to make a video or direct an existing project with the Video Tool tools.</span>
      </section>

      <section id="system" className="card card-pad col" style={{ gap: 8 }}>
        <div className="row">
          <h2 className="grow">System check</h2>
          <button className="btn sm" onClick={() => doctor.refetch()}><RefreshCw size={13} /> Re-check</button>
        </div>
        {doctor.loading && <div className="row muted"><Spinner /> Checking…</div>}
        <table className="table">
          <tbody>
            {(doctor.data || []).map((d) => (
              <tr key={d.name}>
                <td style={{ width: 28 }}>{d.ok ? <Check size={15} color="var(--ok)" /> : <X size={15} color="var(--err)" />}</td>
                <td><strong>{d.name}</strong></td>
                <td className="muted">{d.detail}{!d.ok && d.fix ? <div className="small" style={{ color: "var(--warn)" }}>Fix: <code>{d.fix}</code></div> : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      </div>
      </div>
    </div>
  );
}
