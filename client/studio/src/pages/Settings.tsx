import { Check, Download, RefreshCw, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { get, post, put } from "../api";
import { useFetch, useMusic, useThemes } from "../hooks";
import { jobsStore, settingsStore, toast, useStore } from "../store";
import type { DoctorRow, ModelInfo, Settings } from "../types";
import { Field, ProgressBar, Seg, Spinner } from "../ui";
import AIAssistants from "./AIAssistants";
import HelperCard from "../components/HelperCard";
import MyVoices from "./MyVoices";
import StockKeys from "./StockKeys";

export default function SettingsPage() {
  const [params, setParams] = useSearchParams();
  const keys = ["general", "voice", "directors", "libraries", "help"];
  const [section, setSectionState] = useState(() => (keys.includes(params.get("s") || "") ? (params.get("s") as string) : "general"));
  const setSection = (k: string) => { setSectionState(k); setParams({ s: k }, { replace: true }); };           // a link such as /settings?s=directors opens that section
  useEffect(() => { const k = params.get("s"); if (k && keys.includes(k)) setSectionState(k); }, [params]);       // eslint-disable-line react-hooks/exhaustive-deps
  const sections = [
    ["general", "Preferences", "Default shape, pace, music, theme and language for new videos."],
    ["voice", "Voice & speech", "The voices that read your script, and the models that understand speech."],
    ["directors", "Directors & assistants", "Who plans each scene, and connecting Claude or Codex."],
    ["libraries", "Picture libraries", "Free photo and video libraries."],
    ["help", "Help & checks", "See what is working and what needs attention."],
  ];
  const settings = useStore(settingsStore);
  const doctor = useFetch<DoctorRow[]>("/api/doctor");
  const models = useFetch<ModelInfo[]>("/api/models");
  const { data: themes } = useThemes();
  const { data: music } = useMusic();
  const directors = useFetch<{ directors: { id: string; kind: string; label: string; available: boolean; note: string }[]; claude_usage_today: { calls: number; seconds: number } }>("/api/directors");
  const jobs = useStore(jobsStore);
  const pulls = Object.values(jobs).filter((j) => j.kind === "model");

  useEffect(() => {
    if (pulls.some((j) => j.status === "done")) {
      models.refetch();
      doctor.refetch();
    }
  }, [pulls.map((j) => j.status).join()]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveQueue = useRef(Promise.resolve());
  const pendingSaves = useRef(0);
  const [saving, setSaving] = useState(false);
  const save = (patch: Partial<Settings>) => {
    settingsStore.set(current => ({ ...current, ...patch }));
    pendingSaves.current++;
    setSaving(true);
    saveQueue.current = saveQueue.current.then(async () => {
      try {
        // Send only this choice; a stale page must never overwrite other settings.
        await put("/api/settings", patch);
      } catch (e: any) {
        toast(`Could not save your choice: ${e.message}`, "err");
      } finally {
        if (--pendingSaves.current === 0) {
          try {
            const confirmed = await get<Settings>("/api/settings");
            if (pendingSaves.current === 0) {
              settingsStore.set(confirmed);
            }
          } catch { toast("Could not check saved settings. Reconnect and try again.", "err"); }
          setSaving(pendingSaves.current > 0);
        }
      }
    });
  };

  return (
    <div className="page-inner settings-organized" data-section={section} style={{ maxWidth: 1060 }}>
      <h1>Settings</h1>
      {saving && <p role="status" className="small muted">Saving your choices…</p>}
      <div className="settings-layout">
      <nav className="settings-nav" aria-label="Settings sections">
        {sections.map(([k, l, description]) => (
          <button type="button" key={k} title={description} aria-current={section === k ? "page" : undefined} className={section === k ? "selected" : ""} onClick={() => setSection(k)}><strong>{l}</strong></button>
        ))}
      </nav>
      <div className="settings-body">
      <section id="general" className="card card-pad col" style={{ gap: 12 }}>
        <h2>How new videos start</h2>
        <label className="row" style={{ gap: 12 }}>
          <input type="checkbox" className="ios-switch" checked={settings.autopilot !== false} onChange={(e) => save({ autopilot: e.target.checked })} aria-label="Autopilot" />
          <span className="col" style={{ gap: 2 }}>
            <strong>Finish the video automatically</strong>
            <span className="small muted">After you speak, the app edits, renders, checks and writes the title by itself, and opens the finished video. Off: it stops at the editor.</span>
          </span>
        </label>
        <div className="col" style={{ gap: 6 }} data-testid="plan-review-setting">
          <strong>Show me the plan first</strong>
          <Seg<"when_expensive" | "always" | "never"> label="Show me the plan first" value={(settings.plan_review as any) || "when_expensive"} onChange={(v) => save({ plan_review: v })}
            options={[{ value: "when_expensive", label: "When it is big" }, { value: "always", label: "Always" }, { value: "never", label: "Never" }]} />
          <span className="small muted">Before any picture is drawn, a reel shows what it plans: you can change it, then press Start. Only reels have a plan to look at.</span>
        </div>
        <div className="row wrap" style={{ gap: 16, alignItems: "flex-start" }}>
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
        </div>
      </section>

      <section id="elevenlabs" className="card card-pad col" style={{ gap: 10 }}>
        <h2>ElevenLabs</h2>
        <p className="small muted" style={{ margin: 0 }}>Your account's voices appear in the voice list of every new video. Each sentence uses your ElevenLabs credits.</p>
        <label className="field">API key{(settings as any).stock_keys?.elevenlabs ? " (saved)" : ""}
          <input type="password" autoComplete="off" data-testid="elevenlabs-key" placeholder={(settings as any).stock_keys?.elevenlabs ? "••••••••" : "From elevenlabs.io, Developers, API keys"} onBlur={(e) => { if (e.target.value) { save({ elevenlabs_key: e.target.value, stock_keys: { ...(settings as any).stock_keys, elevenlabs: true } } as any); e.target.value = ""; } }} />
        </label>
      </section>

      <div id="voices"><MyVoices /></div>

      <section id="speech" className="card card-pad col" style={{ gap: 12 }}>
        <h2>Speech recognition</h2>
        <p className="muted" style={{ margin: 0 }}>A bigger speech reader is usually more accurate but takes more space. Download one once; the app uses it automatically.</p>
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

      <div id="ai" className="col" style={{ gap: 22 }}>
      <HelperCard />
      <section className="card card-pad col" style={{ gap: 12 }}>
        <h2>Who directs your videos</h2>
        <p className="muted" style={{ margin: 0 }}>Automatic tries these directors in order. If one is asleep or does not answer, the next one takes over.</p>
        <Field label="Try these directors in this order">
          <select value={(settings.director_order || ["claude-client", "codex-client", "claude-server", "local"]).join(",")} onChange={(e) => save({ director_order: e.target.value.split(",") })}>
            <option value="claude-client,codex-client,claude-server,local">This PC’s Claude → this PC’s Codex → server AI</option>
            <option value="codex-client,claude-client,claude-server,local">This PC’s Codex → this PC’s Claude → server AI</option>
            <option value="local,claude-client,codex-client,claude-server">Server AI → this PC’s assistants</option>
            <option value="claude-client,claude-server,local">This PC's Claude → server Claude → local AI</option>
            <option value="claude-server,claude-client,local">Server Claude → this PC's Claude → local AI</option>
            <option value="local,claude-client,claude-server">Local AI first</option>
          </select>
        </Field>
        <Field label="Which Claude directs">
          <select value={settings.director_model || "sonnet"} onChange={(e) => save({ director_model: e.target.value })} data-testid="director-model">
            <option value="sonnet">Sonnet: faster</option>
            <option value="opus">Opus: slower, the most careful</option>
            {settings.director_model && !["sonnet", "opus"].includes(settings.director_model) && <option value={settings.director_model}>{settings.director_model}</option>}
          </select>
        </Field>
        <Field label="How long to wait for another computer">
          <select value={String(settings.director_wait_seconds ?? 120)} onChange={(e) => save({ director_wait_seconds: e.target.value === "wait" ? "wait" : Number(e.target.value) })}>
            <option value="30">30 seconds</option><option value="120">2 minutes</option><option value="300">5 minutes</option><option value="wait">Wait for me</option>
          </select>
        </Field>
        <div className="col" style={{ gap: 6 }}>{(directors.data?.directors || []).filter((d) => d.id !== "best").map((d) => <div className="row" key={d.id}><span className={`chip ${d.available ? "ok" : "warn"}`}>{d.available ? "Ready" : "Unavailable"}</span><strong>{d.label}</strong><span className="small muted">{d.note}</span></div>)}</div>
        {!(directors.data?.directors || []).some((d) => d.kind === "claude-client") && (
          <div className="row" data-testid="claude-pc-missing"><span className="chip warn">Not connected</span><strong>Claude on this PC</strong>
            <span className="small muted">Install and open the Ultimate Video Tool app on your PC, signed in to Claude Code. Its helper joins this server by itself and appears here.</span></div>
        )}
        <span className="small muted">Claude today: {directors.data?.claude_usage_today.calls || 0} calls · {Math.round(directors.data?.claude_usage_today.seconds || 0)} seconds.</span>
      </section>
      <AIAssistants />
      </div>
      <div id="stock"><StockKeys /></div>



      <section id="system" className="card card-pad col" style={{ gap: 8 }}>
        <div className="row">
          <h2 className="grow">Is everything working?</h2>
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
