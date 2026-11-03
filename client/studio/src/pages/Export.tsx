import { ArrowLeft, Copy, Download, FolderOpen, Film, Sparkles, Wand2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fmtSize, get, post } from "../api";
import { useFetch, useMusic, useProject } from "../hooks";
import { jobsStore, toast, useChanged, useStore } from "../store";
import type { ExportFile } from "../types";
import { Steps } from "../ds";
import { Check2, Field, ProgressBar, Seg, Spinner, copyText } from "../ui";
import CatalogList from "../review/CatalogList";
import RedoModal from "../components/RedoModal";

type Preset = "social" | "youtube" | "square" | "custom";
const PRESETS: Record<Preset, { label: string; hint: string; aspects: "9:16" | "1:1" | "16:9"; res: "1080" | "720"; fps: "30" | "60"; quality: "draft" | "looks" | "delivery" }> = {
  social: { label: "TikTok · Reels · Shorts", hint: "9:16 vertical, 1080p, 30 fps. Captions stay clear of the app buttons.", aspects: "9:16", res: "1080", fps: "30", quality: "looks" },
  youtube: { label: "YouTube", hint: "16:9 wide, 1080p, 30 fps.", aspects: "16:9", res: "1080", fps: "30", quality: "looks" },
  square: { label: "Square", hint: "1:1, 1080p, 30 fps. Feeds and posts.", aspects: "1:1", res: "1080", fps: "30", quality: "looks" },
  custom: { label: "Custom", hint: "Choose everything yourself.", aspects: "9:16", res: "1080", fps: "30", quality: "looks" },
};
interface Kit { title: string; description: string; hashtags: string[]; hook: string; source: string; cover_url?: string; cover_error?: string }

const STAGE = { compose: "Preparing", render: "Rendering frames", mux: "Mixing audio" } as Record<string, string>;

export default function ExportPage() {
  const { id = "" } = useParams();
  const { data: p, refetch } = useProject(id);
  const { data: music, refetch: refetchMusic } = useMusic();
  const files = useFetch<ExportFile[]>(`/api/projects/${id}/exports`);
  const outVideo = useRef<HTMLVideoElement>(null);
  const [scoring, setScoring] = useState(false);
  useChanged(id, () => files.refetch());
  const jobs = useStore(jobsStore);
  const [aspects, setAspects] = useState<"9:16" | "1:1" | "16:9" | "both">("9:16");
  const [res, setRes] = useState<"1080" | "720">("1080");
  const [quality, setQuality] = useState<"draft" | "looks" | "delivery">("looks");
  const [fps, setFps] = useState<"30" | "60">("30");
  const [captions, setCaptions] = useState(true);
  const [cleanVoice, setCleanVoice] = useState(false);
  const [srt, setSrt] = useState(true);
  const [mus, setMus] = useState<string>("project");
  const [vol, setVol] = useState(0.14);
  const [sfx, setSfx] = useState<"off" | "subtle" | "normal" | "rich">("normal");
  const [started, setStarted] = useState<number | null>(null);
  const [preset, setPreset] = useState<Preset>("social");
  const kit = useFetch<{ kit: Kit | null }>(`/api/projects/${id}/publish`);
  const gpuInfo = useFetch<{ available: boolean; name: string | null; cuda_version: string | null; vram_mb: number | null; nvenc_available: boolean }>("/api/gpu");
  const [kitBusy, setKitBusy] = useState(false);
  const [redoOpen, setRedoOpen] = useState(false);
  const [more, setMore] = useState(false);
  const pick = (pr: Preset) => {
    setPreset(pr);
    if (pr === "custom") setMore(true);
    if (pr !== "custom") {
      const x = PRESETS[pr];
      setAspects(x.aspects);
      setRes(x.res);
      setFps(x.fps);
      setQuality(x.quality);
    }
  };
  const makeKit = async () => {
    setKitBusy(true);
    try {
      const j = await post<{ id: string }>(`/api/projects/${id}/publish`);
      for (let i = 0; i < 300; i++) {
        await new Promise((r) => setTimeout(r, 1000));
        const st = await get<{ status: string; error: string }>(`/api/jobs/${j.id}`);
        if (st.status === "error") throw new Error(st.error || "Failed");
        if (st.status === "done") break;
      }
      kit.refetch();
    } catch (e: any) {
      toast(e.message, "err", 7000);
    } finally {
      setKitBusy(false);
    }
  };

  useEffect(() => {
    if (p) {
      setAspects(p.aspect);
      setVol(p.options.music_volume);
      setSfx(p.options.sfx ? p.options.sfx_level : "off");
      setMus(p.options.music || "none");
    }
  }, [p?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const job = Object.values(jobs).filter((j) => j.project === id && j.kind === "export").sort((a, b) => (a.id < b.id ? 1 : -1))[0];
  const running = job && (job.status === "running" || job.status === "queued");
  useEffect(() => {
    if (job?.status === "done") {
      files.refetch();
      refetch();
    }
  }, [job?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    try {
      await post(`/api/projects/${id}/export`, {
        aspects: aspects === "both" ? ["9:16", "1:1", "16:9"] : [aspects],
        quality,
        gpu: true,
        music: mus === "none" ? "none" : mus,
        music_volume: vol,
        sfx_level: sfx,
        fps: +fps,
        short_side: res === "720" ? 720 : null,
        captions,
        clean_voice: cleanVoice,
      });
      setStarted(Date.now());
    } catch (e: any) {
      toast(e.message, "err", 7000);
    }
  };

  const elapsed = started && running ? (Date.now() - started) / 1000 : 0;
  const eta = running && job.frac > 0.05 ? Math.max(0, elapsed / job.frac - elapsed) : null;
  const latest = files.data?.[0];

  return (
    <div className="page-inner">
      <div className="row">
        <Link className="btn ghost" to={`/p/${id}`}><ArrowLeft size={15} /> Back to review</Link>
        <h1 className="grow bn" style={{ marginLeft: 8 }}>Export · {p?.title}</h1>
        <button className="btn magic" onClick={() => setRedoOpen(true)}><Wand2 size={15} /> Redo with AI model</button>
      </div>

      <div className="two-col">
        <div className="card card-pad col" style={{ gap: 14 }}>
          <div className="col" style={{ gap: 5 }}>
            <span className="small muted" style={{ fontWeight: 600 }}>Where will you post it?</span>
            <Seg<Preset> value={preset} onChange={pick} wrap label="Export preset" options={(Object.keys(PRESETS) as Preset[]).map((k) => ({ value: k, label: PRESETS[k].label }))} />
            <span className="small muted">{PRESETS[preset].hint}</span>
          </div>
          <button className="btn" onClick={() => setMore(true)} data-testid="export-more">More options…</button>
          {more && (
            <Steps label="Export options" onClose={() => setMore(false)} start={0}
              steps={[
                { title: "Size and quality", subtitle: "How big the picture is, and how sharp.", body: (<div className="col" style={{ gap: 14 }}>
          <div className="col" style={{ gap: 5 }}>
            <span className="small muted" style={{ fontWeight: 600 }}>Shape</span>
            <Seg value={aspects} onChange={setAspects} options={[{ value: "9:16", label: "9:16 vertical" }, { value: "1:1", label: "1:1 square" }, { value: "16:9", label: "16:9 wide" }, { value: "both", label: "All three" }]} />
          </div>
          <div className="row wrap" style={{ gap: 18 }}>
            <div className="col" style={{ gap: 5 }}>
              <span className="small muted" style={{ fontWeight: 600 }}>Resolution</span>
              <Seg value={res} onChange={setRes} options={[{ value: "720", label: "720p" }, { value: "1080", label: "1080p" }]} />
            </div>
            <div className="col" style={{ gap: 5 }}>
              <span className="small muted" style={{ fontWeight: 600 }}>Frame rate</span>
              <Seg value={fps} onChange={setFps} options={[{ value: "30", label: "30 fps" }, { value: "60", label: "60 fps" }]} />
            </div>
          </div>
          <Field label="Quality" hint={quality === "draft" ? "Fast and small. Good for checking." : quality === "looks" ? "Sharp, balanced size. Recommended." : "Highest quality, largest file."}>
            <select value={quality} onChange={(e) => setQuality(e.target.value as any)}>
              <option value="draft">Draft</option>
              <option value="looks">Standard</option>
              <option value="delivery">High</option>
            </select>
          </Field>
          <div className="col" style={{ gap: 6 }}>
            <strong className="small">Graphics acceleration · Automatic</strong>
            {gpuInfo.data?.available ? (
              <div className="row small" style={{ alignItems: "center", gap: 6, color: "var(--ok)", background: "var(--fill)", padding: "6px 10px", borderRadius: 8 }}>
                <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: "var(--ok)", flexShrink: 0 }} />
                <span>{gpuInfo.data.name} detected. The renderer uses available graphics acceleration automatically.</span>
              </div>
            ) : gpuInfo.data ? (
              <span className="small muted">The renderer checks your server's graphics hardware when export starts, including supported NVIDIA, AMD, Intel and Apple encoders.</span>
            ) : null}
          </div>
</div>) },
                { title: "Words", subtitle: "Captions and the voice.", body: (<div className="col" style={{ gap: 14 }}>
          <Check2 checked={captions} onChange={setCaptions}>Burn captions into the video</Check2>
          <Check2 checked={cleanVoice} onChange={setCleanVoice}>Clean up the voice (less noise, clearer, more even)</Check2>
          <Check2 checked={srt} onChange={setSrt}>Also save a subtitle file (.srt)</Check2>
</div>) },
                { title: "Sound", subtitle: "Music under the voice, and sound effects.", body: (<div className="col" style={{ gap: 14 }}>
          <Field label="Background music">
            <select value={mus} onChange={(e) => setMus(e.target.value)}>
              <option value="none">No music</option>
              {(music || []).map((m) => <option key={m.id} value={m.id}>{m.title} · {m.mood}</option>)}
            </select>
          </Field>
          <details>
            <summary style={{ cursor: "pointer", fontWeight: 600 }}>Get free music</summary>
            <p className="small muted">Public-domain and Creative Commons tracks with a checked link. Installing one adds it to the list above and puts its credit in the export's credits file.</p>
            <CatalogList kind="audio" role="music" action="Install" label="Free music"
              onPick={async (e) => { const r = await post<{ music: string }>(`/api/catalog/${e.id}/music`); toast("Installed. Choose it in the music list.", "ok", 3500); refetchMusic(); setMus(r.music); }} />
          </details>
          <label className="field">
            <span>Music volume under your voice: {Math.round(vol * 100)}%</span>
            <input type="range" min={0.02} max={0.4} step={0.01} value={vol} onChange={(e) => setVol(+e.target.value)} disabled={mus === "none"} />
          </label>
          <Field label="Sound effects" hint={{ off: "Voice and music only.", subtle: "Only transitions and big moments.", normal: "A sound for each thing that appears. Recommended.", rich: "Also ticks for every list item, risers and camera-style cuts." }[sfx]}>
            <Seg value={sfx} onChange={setSfx} options={[{ value: "off", label: "Off" }, { value: "subtle", label: "Subtle" }, { value: "normal", label: "Normal" }, { value: "rich", label: "Rich" }]} />
          </Field>
</div>) },
              ]} />
          )}
          <button className="btn primary lg" onClick={start} disabled={!!running}>
            {running ? <Spinner /> : <Film size={16} />} {running ? "Rendering…" : "Render video"}
          </button>
        </div>

        <div className="col" style={{ gap: 16 }}>
          {job && (job.status === "running" || job.status === "queued") && (
            <div className="card card-pad col">
              <strong>{STAGE[job.stage?.split(" ")[0]] || "Working"}</strong>
              <ProgressBar frac={job.frac} />
              <span className="small muted">{Math.round(job.frac * 100)}% · {job.msg}{eta != null ? ` · about ${Math.ceil(eta)}s left` : ""}</span>
              <button className="btn sm" style={{ alignSelf: "flex-start" }} onClick={() => post(`/api/jobs/${job.id}/cancel`)}>Cancel</button>
            </div>
          )}
          {job?.status === "error" && <div className="banner err"><strong>Render failed:</strong> {job.error}</div>}
          {latest && !running && (
            <div className="card card-pad col">
              <div className="row">
                <strong className="grow">Latest export</strong>
                <span className="small muted">{latest.modified} · {fmtSize(latest.size)}</span>
              </div>
              <video className="video-out" ref={outVideo} src={latest.url} controls playsInline />
              {latest.acceleration && <div className={latest.acceleration.warnings.length ? "banner warn" : "small muted"}>
                {latest.acceleration.warnings.length ? "Some graphics acceleration could not be used for this export." : "Graphics acceleration requested automatically."}
                {latest.acceleration.selected_device && ` Selected card: ${latest.acceleration.selected_device.name}.`}
                <details><summary>Acceleration details</summary>
                  {latest.acceleration.browser_probe && <p style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{latest.acceleration.browser_probe}</p>}
                  {latest.acceleration.warnings.map((warning,index)=><p key={index} style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{warning}</p>)}
                </details>
              </div>}
              <section className="col" aria-label="Retention check" style={{ gap: 6 }}>
                <div className="row" style={{ alignItems: "center" }}>
                  <strong className="grow">Retention check</strong>
                  {latest.retention && <span className="small" style={{ fontVariantNumeric: "tabular-nums" }} title="100 is best. Made from how soon something appears, how long nothing changes, empty stretches, silence and reading speed.">Score {latest.retention.score}/100</span>}
                  <button className="btn sm ghost" disabled={scoring} onClick={() => { setScoring(true); post(`/api/projects/${id}/retention?name=${encodeURIComponent(latest.name)}`).then(() => files.refetch()).catch((e: any) => toast(e.errors?.[0] || e.message, "err")).finally(() => setScoring(false)); }}>{scoring ? <Spinner /> : null} {latest.retention ? "Check again" : "Check now"}</button>
                </div>
                {latest.retention ? (
                  <>
                    <div role="progressbar" aria-label="Retention score" aria-valuenow={latest.retention.score} aria-valuemin={0} aria-valuemax={100} style={{ height: 8, borderRadius: 4, background: "var(--fill)", overflow: "hidden" }}>
                      <div style={{ width: `${latest.retention.score}%`, height: "100%", background: latest.retention.risk <= 15 ? "var(--ok)" : latest.retention.risk <= 35 ? "#ff9f0a" : "#ff3b30" }} />
                    </div>
                    <span className="small">{latest.retention.verdict}</span>
                    {latest.retention.worst.length > 0 && (
                      <ul style={{ margin: 0, paddingLeft: 0, listStyle: "none" }} aria-label="Moments to look at">
                        {latest.retention.worst.map((m, i) => (
                          <li key={i} className="row" style={{ gap: 8, alignItems: "baseline" }}>
                            <button className="btn sm ghost" style={{ fontVariantNumeric: "tabular-nums" }} onClick={() => { if (outVideo.current) { outVideo.current.currentTime = m.t0; outVideo.current.play().catch(() => {}); } }} aria-label={`Show ${m.t0.toFixed(1)} seconds`}>{m.t0.toFixed(1)} s</button>
                            <span className="small grow">{m.message}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                    <span className="small muted">{latest.retention.note}</span>
                  </>
                ) : <span className="small muted">Not checked yet.</span>}
              </section>
              <div className="row wrap">
                <a className="btn" href={latest.url} download={latest.name}><Download size={14} /> Video</a>
                {latest.srt && srt && <a className="btn" href={latest.srt} download><Download size={14} /> Subtitles</a>}
                <button className="btn" onClick={() => post(`/api/projects/${id}/open-folder`).catch((e) => toast(e.message, "err"))}><FolderOpen size={14} /> Open folder</button>
                <button className="btn" onClick={() => copyText(latest.path, "Path copied")}><Copy size={14} /> Copy path</button>
              </div>
            </div>
          )}
          {files.data && files.data.length > 1 && (
            <div className="card card-pad col">
              <h3>Earlier exports</h3>
              {files.data.slice(1).map((f) => (
                <div key={f.name} className="row small">
                  <a className="grow" href={f.url} target="_blank" rel="noreferrer">{f.name}</a>
                  <span className="muted">{f.modified} · {fmtSize(f.size)}</span>
                </div>
              ))}
            </div>
          )}
          <div className="card card-pad col" aria-label="Publishing kit">
            <div className="row">
              <h3 className="grow">Publishing kit</h3>
              <button className="btn sm" onClick={makeKit} disabled={kitBusy}>{kitBusy ? <Spinner /> : <Sparkles size={14} />} {kit.data?.kit ? "Write again" : "Write title, description and cover"}</button>
            </div>
            {!kit.data?.kit && <span className="small muted">The AI writes a title, description and hashtags from what is said, and picks a cover frame with a short hook on it.</span>}
            {kit.data?.kit && (
              <div className="col" style={{ gap: 10 }}>
                {kit.data.kit.cover_url && <img src={kit.data.kit.cover_url} alt="Cover" style={{ maxWidth: 180, borderRadius: 10, alignSelf: "flex-start" }} />}
                {([["Title", kit.data.kit.title], ["Description", kit.data.kit.description], ["Hashtags", kit.data.kit.hashtags.map((h) => "#" + h).join(" ")]] as [string, string][]).map(([k, v]) => (
                  <div key={k} className="col" style={{ gap: 3 }}>
                    <span className="small muted" style={{ fontWeight: 600 }}>{k}</span>
                    <div className="row"><div className="grow bn" style={{ whiteSpace: "pre-wrap" }}>{v}</div><button className="btn sm" onClick={() => copyText(v)} aria-label={`Copy ${k}`}><Copy size={13} /></button></div>
                  </div>
                ))}
                <span className="small muted">Written by {kit.data.kit.source === "ai" ? "the AI" : "the built-in rules"}.{kit.data.kit.cover_error ? ` No cover: ${kit.data.kit.cover_error}` : ""}</span>
              </div>
            )}
          </div>
          {!latest && !running && <div className="empty">Nothing exported yet. Choose where you will post it and render.</div>}
        </div>
      </div>
      {redoOpen && p && <RedoModal id={id} title={p.title} open={redoOpen} onClose={() => setRedoOpen(false)} />}
    </div>
  );
}
