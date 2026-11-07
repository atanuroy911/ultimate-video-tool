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
import DirectorSettings from "./DirectorSettings";
import { explainCheck } from "./settingsChecks";
import "../settings-clarity.css";

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
        <div className="settings-preferences">
          <Field label="Look">
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
      <DirectorSettings settings={settings} directors={directors.data?.directors} loading={directors.loading} onSave={save} />
      <HelperCard />
      <span className="small muted">Claude today: {directors.data?.claude_usage_today.calls || 0} calls · {Math.round(directors.data?.claude_usage_today.seconds || 0)} seconds.</span>
      <AIAssistants />
      </div>
      <div id="stock"><StockKeys /></div>



      <section id="system" className="card card-pad col" style={{ gap: 8 }}>
        <div className="row">
          <h2 className="grow">Is everything working?</h2>
          <button className="btn sm" onClick={() => doctor.refetch()}><RefreshCw size={13} /> Re-check</button>
        </div>
        {doctor.loading && <div className="row muted"><Spinner /> Checking…</div>}
        <ul className="settings-checks">{(doctor.data || []).map((d) => {
          const plain = explainCheck(d);
          return <li key={d.name}>
            {d.ok ? <Check size={17} color="var(--ok)" aria-label="Ready" /> : <X size={17} color="var(--warn)" aria-label="Needs attention" />}
            <div className="col" style={{ gap: 4 }}><strong>{plain.title}</strong><span className="small muted">{plain.message}</span>
              <details><summary>Technical details</summary><p className="small muted">{d.detail}</p>{!d.ok && d.fix && <code>{d.fix}</code>}</details>
            </div>
          </li>;
        })}</ul>
        {doctor.error && <p role="alert">Could not check this server. Reconnect, then press Re-check.</p>}
      </section>
      </div>
      </div>
    </div>
  );
}
