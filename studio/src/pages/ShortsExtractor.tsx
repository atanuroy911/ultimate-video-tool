import React, { useEffect, useState, useRef } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, ChevronLeft, ChevronRight, Sparkles, Scissors, Play, Pause, Flame, Video, RefreshCw, Wand2, Layers, Upload } from "lucide-react";
import { get, post, upload } from "../api";
import { useT } from "../i18n";
import { ProjectSummary } from "../types";

interface Highlight {
  title: string;
  start_time: number;
  end_time: number;
  duration?: number;
  score: number;
  hook_sentence: string;
  virality_reason: string;
}

interface ShortsData {
  highlights: Highlight[];
  content_info?: { content_type?: string; density?: string };
  total_duration?: number;
  preview_url?: string | null;
}

export default function ShortsExtractor() {
  const t = useT();
  const nav = useNavigate();
  const { id: paramProjectId } = useParams<{ id?: string }>();
  const [searchParams] = useSearchParams();
  const initialUrl = searchParams.get("url") || "";

  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedPid, setSelectedPid] = useState<string>(paramProjectId || "");
  const [youtubeUrl, setYoutubeUrl] = useState<string>(initialUrl);
  const [loading, setLoading] = useState<boolean>(false);
  const [statusMsg, setStatusMsg] = useState<string>("");
  const [shortsData, setShortsData] = useState<ShortsData | null>(null);
  const [selectedIndices, setSelectedIndices] = useState<number[]>([]);
  const [playingIndex, setPlayingIndex] = useState<number | null>(null);
  const [slicingIndex, setSlicingIndex] = useState<number | null>(null);
  const [batchSlicing, setBatchSlicing] = useState<boolean>(false);
  const [batchExporting, setBatchExporting] = useState(false);
  const [exported, setExported] = useState<{ child_project_id: string; url: string }[]>([]);
  const [importing, setImporting] = useState(false);
  const [clipCount, setClipCount] = useState(6);
  const [captionStyle, setCaptionStyle] = useState<"pop" | "box" | "pill" | "underline" | "theme">("pop");
  const [aroll, setAroll] = useState<"auto" | "off">("auto");
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [uploadProgress, setUploadProgress] = useState(0);

  const mediaRef = useRef<HTMLMediaElement | null>(null);
  const touchStart = useRef<number | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  // Load project list
  useEffect(() => {
    get<ProjectSummary[]>("/api/projects").then((list) => {
      setProjects(list);
      if (!selectedPid && list.length > 0) {
        setSelectedPid(list[0].id);
      }
    }).catch(() => {});
  }, []);

  // When project changes, fetch existing detected shorts if any
  useEffect(() => {
    if (!selectedPid) return;
    setShortsData(null);
    setSelectedIndices([]);
    setFocusedIndex(0);
    mediaRef.current?.pause();
    setPlayingIndex(null);
    get<ShortsData>(`/api/projects/${selectedPid}/shorts`)
      .then((data) => {
        if (data && data.highlights && data.highlights.length > 0) {
          setShortsData(data);
          setSelectedIndices(data.highlights.map((_, i) => i));
        } else {
          setShortsData(null);
        }
      })
      .catch(() => {});
  }, [selectedPid]);

  const handleDetect = async (pid = selectedPid) => {
    if (!pid) return;
    setLoading(true);
    setStatusMsg("Analyzing transcript with AI Virality framework...");
    try {
      const job = await post<{ id: string }>(`/api/projects/${pid}/shorts/detect`, { num_clips: clipCount });
      for (let attempt = 0; attempt < 300; attempt++) {
        const current = await get<{ status: string; msg?: string; error?: string }>(`/api/jobs/${job.id}`);
        if (current.status === "error" || current.status === "cancelled") throw new Error(current.error || "Highlight detection stopped");
        if (current.status === "done") {
          const fresh = await get<ShortsData>(`/api/projects/${pid}/shorts`);
          setShortsData(fresh);
          setFocusedIndex(0);
          setSelectedIndices(fresh.highlights.map((_, i) => i));
          setLoading(false);
          setStatusMsg(fresh.highlights.length ? "" : "No suitable clips found in this transcript.");
          return;
        }
        setStatusMsg(current.msg || "Analyzing transcript…");
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
      throw new Error("Highlight detection is still running. Check again shortly.");
    } catch (err: any) {
      setLoading(false);
      setStatusMsg(err?.message || "Detection failed. Ensure project has a transcript.");
    }
  };

  const handleFile = async (file?: File) => {
    if (!file) return;
    if (!/\.(mp4|mov|mkv|webm)$/i.test(file.name)) {
      setStatusMsg("Choose an MP4, MOV, MKV or WebM video.");
      return;
    }
    setImporting(true);
    setUploadProgress(0);
    setStatusMsg("Uploading video…");
    try {
      const form = new FormData();
      form.append("audio", file);
      form.append("title", file.name.replace(/\.[^.]+$/, ""));
      form.append("language", "auto");
      form.append("aspect", "9:16");
      form.append("usecase", "discussion");
      form.append("options", JSON.stringify({ aroll, caption_style: captionStyle, target_length: "keep" }));
      const result = await upload<{ project: { id: string }; job?: { id: string } }>("/api/projects", form, setUploadProgress);
      const pid = result.project.id;
      setSelectedPid(pid);
      setProjects(await get<ProjectSummary[]>("/api/projects"));
      if (result.job?.id) await waitForJob(result.job.id);
      setStatusMsg("Video analyzed. Finding the best moments…");
      const job = await post<{ id: string }>(`/api/projects/${pid}/shorts/detect`, { num_clips: clipCount });
      await waitForJob(job.id);
      const data = await get<ShortsData>(`/api/projects/${pid}/shorts`);
      setShortsData(data);
      setSelectedIndices(data.highlights.map((_, i) => i));
      setFocusedIndex(0);
      setStatusMsg(data.highlights.length ? "Swipe through the picks, then create or export your Shorts." : "No suitable clips found. Try another video or adjust the number of picks.");
    } catch (err: any) {
      setStatusMsg(err?.message || "Could not prepare this video.");
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleImport = async () => {
    if (!youtubeUrl.trim()) return;
    setImporting(true);
    setStatusMsg("Downloading the video and preparing its transcript…");
    try {
      const job = await post<{ id: string }>("/api/projects/from-link", { url: youtubeUrl.trim(), language: "auto", aspect: "9:16", want_video: true, start: true, options: { aroll: "auto" } });
      let project = "";
      for (let i = 0; i < 300; i++) {
        const current = await get<{ status: string; error?: string; result?: { project?: string }; msg?: string }>(`/api/jobs/${job.id}`);
        if (current.status === "error" || current.status === "cancelled") throw new Error(current.error || "Import stopped");
        if (current.status === "done") { project = current.result?.project || ""; break; }
        setStatusMsg(current.msg || "Downloading the video…");
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
      if (!project) throw new Error("Import is still running. Check Projects and return when it finishes.");
      setSelectedPid(project);
      setProjects(await get<ProjectSummary[]>("/api/projects"));
      setStatusMsg("Video imported. Waiting for transcript…");
      for (let i = 0; i < 300; i++) {
        const transcript = await get<{ transcript?: { words?: unknown[] } }>(`/api/projects/${project}/transcript`).catch(() => null);
        if (transcript?.transcript?.words?.length) { setProjects(await get<ProjectSummary[]>("/api/projects")); await handleDetect(project); return; }
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
      setStatusMsg("The project is ready; transcription is still running. Try finding highlights shortly.");
    } catch (e: any) { setStatusMsg(e.message || "Could not import video"); }
    finally { setImporting(false); }
  };

  const focusClip = (index: number) => {
    if (!shortsData?.highlights.length) return;
    mediaRef.current?.pause();
    setPlayingIndex(null);
    const next = Math.max(0, Math.min(shortsData.highlights.length - 1, index));
    setFocusedIndex(next);
    if (mediaRef.current?.readyState) mediaRef.current.currentTime = shortsData.highlights[next].start_time;
  };

  const handlePlayToggle = (idx: number, highlight: Highlight) => {
    if (playingIndex === idx) {
      mediaRef.current?.pause();
      setPlayingIndex(null);
      return;
    }

    if (!selectedPid) return;
    if (focusedIndex !== idx) setFocusedIndex(idx);
    const media = mediaRef.current;
    if (!media) { setStatusMsg("Preview is still preparing. Try again shortly."); return; }
    media.currentTime = highlight.start_time;
    media.play().catch(() => setStatusMsg("Preview could not play in this browser. Try an MP4 video."));
    setPlayingIndex(idx);
  };

  const handleSliceOne = async (index: number) => {
    if (!selectedPid) return;
    setSlicingIndex(index);
    try {
      const job = await post<{ id: string }>(`/api/projects/${selectedPid}/shorts/slice`, {
        index,
        aroll,
        caption_style: captionStyle,
      });
      const res = await waitForJob<{ child_project_id: string }>(job.id);
      nav(`/p/${res.child_project_id}`);
    } catch (err: any) {
      alert("Failed to slice short: " + (err?.message || "unknown error"));
      setSlicingIndex(null);
    }
  };

  const handleBatchSlice = async () => {
    if (!selectedPid || selectedIndices.length === 0) return;
    setBatchSlicing(true);
    try {
      const job = await post<{ id: string }>(`/api/projects/${selectedPid}/shorts/batch-slice`, {
        indices: selectedIndices,
        aroll,
        caption_style: captionStyle,
      });
      const res = await waitForJob<{ created: { child_project_id: string }[] }>(job.id);
      setBatchSlicing(false);
      if (res && res.created && res.created.length > 0) {
        nav("/");
      }
    } catch (err: any) {
      setBatchSlicing(false);
      alert("Batch creation failed: " + (err?.message || "unknown error"));
    }
  };

  const waitForJob = async <T,>(jobId: string): Promise<T> => {
    for (let i = 0; i < 900; i++) {
      const job = await get<{ status: string; result?: T; error?: string; msg?: string }>(`/api/jobs/${jobId}`);
      if (job.status === "done") return job.result as T;
      if (job.status === "error" || job.status === "cancelled") throw new Error(job.error || "Job did not finish");
      setStatusMsg(job.msg || "Working on Shorts…");
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
    throw new Error("Still working. Check Projects shortly.");
  };

  const handleBatchExport = async () => {
    if (!selectedPid || !selectedIndices.length) return;
    setBatchExporting(true);
    try {
      const job = await post<{ id: string }>(`/api/projects/${selectedPid}/shorts/batch-export`, { indices: selectedIndices, aroll, caption_style: captionStyle });
      const result = await waitForJob<{ exports: { child_project_id: string; url: string }[] }>(job.id);
      setExported(result.exports);
      setStatusMsg(`Exported ${result.exports.length} Shorts. Find them in Projects.`);
    } catch (e: any) { setStatusMsg(e.message || "Batch export failed"); }
    finally { setBatchExporting(false); }
  };

  const toggleSelectIndex = (i: number) => {
    if (selectedIndices.includes(i)) {
      setSelectedIndices(selectedIndices.filter((x) => x !== i));
    } else {
      setSelectedIndices([...selectedIndices, i]);
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="page" style={{ maxWidth: 1140, margin: "0 auto", padding: "28px 20px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <button className="btn icon ghost" onClick={() => nav("/")} title="Back to Projects">
            <ArrowLeft size={20} />
          </button>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <h1 style={{ margin: 0, fontSize: "1.6rem", fontWeight: 700, letterSpacing: "-0.02em" }}>
                AI Shorts & Viral Highlights
              </h1>
              
            </div>
            <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "0.9rem" }}>
              Find high-retention scenes, opinion bombs, revelations, and hooks from long videos and auto-generate 9:16 vertical shorts.
            </p>
          </div>
        </div>

        {shortsData && shortsData.highlights.length > 0 && (
          <div className="row wrap" style={{ gap: 8 }}><button className="btn" disabled={batchExporting || selectedIndices.length === 0} onClick={handleBatchExport}>{batchExporting ? "Exporting…" : `Batch Export ${selectedIndices.length} Videos`}</button><button
            className="btn primary"
            onClick={handleBatchSlice}
            disabled={batchSlicing || selectedIndices.length === 0}
            style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 18px", fontWeight: 600 }}
          >
            <Layers size={18} />
            {batchSlicing ? "Creating Shorts..." : `Batch Create ${selectedIndices.length} Shorts`}
          </button></div>
        )}
      </div>

      {/* Control Card */}
      <div className="card" style={{ padding: 22, marginBottom: 28, background: "var(--card-bg, #18181b)", borderRadius: 14, border: "1px solid var(--border)" }}>
        <div className="row wrap" style={{ gap: 12, alignItems: "end", marginBottom: 16 }}>
          <div style={{ flex: "1 1 240px" }}>
            <strong>Start with a video</strong>
            <p className="small muted" style={{ margin: "4px 0 0" }}>Upload a recording. We transcribe it, find strong moments, then make captioned vertical Shorts from your picks.</p>
          </div>
          <label className="small" style={{ display: "grid", gap: 4 }}>Picks to find
            <select aria-label="Number of Shorts suggestions" value={clipCount} onChange={e => setClipCount(Number(e.target.value))} disabled={importing || loading}>
              {[3, 5, 6, 8, 10, 12].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <label className="small" style={{ display: "grid", gap: 4 }}>Captions
            <select aria-label="Shorts caption style" value={captionStyle} onChange={e => setCaptionStyle(e.target.value as typeof captionStyle)}>
              <option value="pop">Pop</option><option value="box">Box</option><option value="pill">Pill</option><option value="underline">Underline</option><option value="theme">Theme default</option>
            </select>
          </label>
          <label className="small" style={{ display: "grid", gap: 4 }}>Original video
            <select aria-label="Keep original speaker video" value={aroll} onChange={e => setAroll(e.target.value as typeof aroll)}>
              <option value="auto">Keep speaker in frame</option><option value="off">Graphics only</option>
            </select>
          </label>
          <input ref={fileRef} type="file" accept=".mp4,.mov,.mkv,.webm,video/*" hidden onChange={e => handleFile(e.target.files?.[0])} />
          <button className="btn primary" disabled={importing || loading} onClick={() => fileRef.current?.click()}><Upload size={16} /> {importing ? (uploadProgress < 1 ? `Uploading ${Math.round(uploadProgress * 100)}%` : "Preparing video…") : "Upload video & find Shorts"}</button>
        </div>
        <div className="row wrap" style={{ gap: 8, marginBottom: 16 }}><input aria-label="YouTube video URL" placeholder="Paste a YouTube or video URL" value={youtubeUrl} onChange={e => setYoutubeUrl(e.target.value)} style={{ flex: "1 1 280px" }} /><button className="btn" disabled={importing || !youtubeUrl.trim()} onClick={handleImport}>{importing ? "Importing…" : "Import video for Shorts"}</button></div>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 16 }}>
          <div style={{ flex: "1 1 280px" }}>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "var(--muted)", marginBottom: 6 }}>
              Select Long-Form Video / Project
            </label>
            <select
              aria-label="Long video to find shorts in"
              value={selectedPid}
              onChange={(e) => setSelectedPid(e.target.value)}
              style={{ width: "100%", padding: "9px 12px", borderRadius: 8, background: "var(--input-bg, #27272a)", border: "1px solid var(--border)", color: "var(--fg)" }}
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} ({p.duration ? `${Math.round(p.duration)}s` : "Video"})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: "flex", alignItems: "flex-end", gap: 10 }}>
            <button
              className="btn primary"
              onClick={() => handleDetect()}
              disabled={loading || !selectedPid}
              style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 20px", fontWeight: 600 }}
            >
              {loading ? <RefreshCw className="spin" size={18} /> : <Wand2 size={18} />}
              {loading ? "Analyzing Video..." : "Find Viral Highlights"}
            </button>
          </div>
        </div>

        {statusMsg && (
          <div style={{ marginTop: 14, fontSize: "0.85rem", color: "var(--accent, #6366f1)", display: "flex", alignItems: "center", gap: 8 }}>
            <Sparkles size={16} />
            <span>{statusMsg}</span>
          </div>
        )}
        {exported.length > 0 && <div className="col" style={{ gap: 6, marginTop: 10 }}>{exported.map(item => <div key={item.child_project_id} className="row wrap" style={{ gap: 8 }}><a href={item.url} download>Download {item.child_project_id}</a><a href={`/p/${item.child_project_id}/result`}>Open and publish</a></div>)}</div>}
      </div>

      {/* Highlights Grid */}
      {shortsData && shortsData.highlights.length > 0 ? (
        <div>
          <div className="card" style={{ padding: 18, marginBottom: 20 }} onTouchStart={e => { touchStart.current = (e.target as HTMLElement).closest("video, audio, input, button, select") ? null : e.touches[0]?.clientX ?? null; }} onTouchEnd={e => { if (touchStart.current == null) return; const distance = e.changedTouches[0].clientX - touchStart.current; if (Math.abs(distance) > 70) focusClip(focusedIndex + (distance < 0 ? 1 : -1)); touchStart.current = null; }}>
            <div className="row wrap" style={{ justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
              <div><strong>Review pick {focusedIndex + 1} of {shortsData.highlights.length}</strong><div className="small muted">Swipe left or right, or use the arrows. Scrub the source video to inspect the moment.</div></div>
              <div className="row" style={{ gap: 8 }}>
                <button className="btn icon" aria-label="Previous Short" disabled={focusedIndex === 0} onClick={() => focusClip(focusedIndex - 1)}><ChevronLeft size={18} /></button>
                <button className="btn icon" aria-label="Next Short" disabled={focusedIndex === shortsData.highlights.length - 1} onClick={() => focusClip(focusedIndex + 1)}><ChevronRight size={18} /></button>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 18, alignItems: "center" }}>
              <div style={{ background: "#09090b", borderRadius: 12, overflow: "hidden", minHeight: 220, display: "grid", placeItems: "center" }}>
                {shortsData.preview_url && /\.(mp4|mov|mkv|webm)(\?|$)/i.test(shortsData.preview_url) ?
                  <video ref={mediaRef as React.RefObject<HTMLVideoElement>} src={shortsData.preview_url} controls playsInline preload="metadata" style={{ width: "100%", maxHeight: 430, objectFit: "contain" }} onLoadedMetadata={e => { e.currentTarget.currentTime = shortsData.highlights[focusedIndex].start_time; }} onTimeUpdate={e => { if (playingIndex === focusedIndex && e.currentTarget.currentTime >= shortsData.highlights[focusedIndex].end_time) { e.currentTarget.pause(); setPlayingIndex(null); } }} onEnded={() => setPlayingIndex(null)} /> :
                  <div style={{ padding: 24, width: "100%" }}><Video size={26} /><p>Video preview unavailable for this project. Listen to the source audio below.</p><audio ref={mediaRef as React.RefObject<HTMLAudioElement>} src={shortsData.preview_url || projects.find(p => p.id === selectedPid)?.audio_url || ""} controls onLoadedMetadata={e => { e.currentTarget.currentTime = shortsData.highlights[focusedIndex].start_time; }} onTimeUpdate={e => { if (playingIndex === focusedIndex && e.currentTarget.currentTime >= shortsData.highlights[focusedIndex].end_time) { e.currentTarget.pause(); setPlayingIndex(null); } }} onEnded={() => setPlayingIndex(null)} /></div>}
              </div>
              <div>
                <div className="small muted">{formatTime(shortsData.highlights[focusedIndex].start_time)} – {formatTime(shortsData.highlights[focusedIndex].end_time)} · {Math.round(shortsData.highlights[focusedIndex].score)}/100</div>
                <h2 style={{ margin: "8px 0" }}>{shortsData.highlights[focusedIndex].title}</h2>
                <p>{shortsData.highlights[focusedIndex].hook_sentence}</p>
                <p className="small muted">{shortsData.highlights[focusedIndex].virality_reason}</p>
                <div className="row wrap" style={{ gap: 8 }}>
                  <button className="btn" onClick={() => handlePlayToggle(focusedIndex, shortsData.highlights[focusedIndex])}>{playingIndex === focusedIndex ? <Pause size={15} /> : <Play size={15} />} {playingIndex === focusedIndex ? "Pause clip" : "Play clip"}</button>
                  <button className="btn" onClick={() => toggleSelectIndex(focusedIndex)}>{selectedIndices.includes(focusedIndex) ? "Remove from batch" : "Add to batch"}</button>
                  <button className="btn primary" disabled={slicingIndex !== null} onClick={() => handleSliceOne(focusedIndex)}><Scissors size={15} /> Create & open in Studio</button>
                </div>
                <p className="small muted">In Studio, you can ask Codex or Claude to direct the Short, inspect its framing, and render it. Batch export uses the automatic draft.</p>
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ fontSize: "1.1rem", fontWeight: 700 }}>
              Detected Clips ({shortsData.highlights.length})
              {shortsData.content_info?.content_type && (
                <span style={{ marginLeft: 12, fontSize: "0.8rem", fontWeight: 500, color: "var(--muted)" }}>
                  Genre: <strong>{shortsData.content_info.content_type}</strong> | Density: <strong>{shortsData.content_info.density || "medium"}</strong>
                </span>
              )}
            </div>

            <div style={{ display: "flex", gap: 10 }}>
              <button
                className="btn ghost sm"
                onClick={() => setSelectedIndices(shortsData.highlights.map((_, i) => i))}
              >
                Select All
              </button>
              <button
                className="btn ghost sm"
                onClick={() => setSelectedIndices([])}
              >
                Deselect All
              </button>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 20 }}>
            {shortsData.highlights.map((h, i) => {
              const isSelected = selectedIndices.includes(i);
              const isPlaying = playingIndex === i;
              const isSlicing = slicingIndex === i;
              const dur = Math.round(h.end_time - h.start_time);

              // Virality color gradient
              let scoreColor = "#10b981"; // green
              if (h.score < 80) scoreColor = "#0284c7"; // blue
              if (h.score >= 90) scoreColor = "#ec4899"; // pink/hot

              return (
                <div
                  key={i}
                  className="card"
                  onClick={() => focusClip(i)}
                  style={{
                    position: "relative",
                    borderRadius: 14,
                    padding: 18,
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    border: isSelected ? "2px solid var(--accent, #6366f1)" : "1px solid var(--border)",
                    background: "var(--card-bg, #18181b)",
                    boxShadow: isSelected ? "0 4px 20px rgba(99, 102, 241, 0.15)" : "none",
                    transition: "transform 0.15s ease, border-color 0.15s ease",
                  }}
                >
                  <div>
                    {/* Top row: Checkbox, Score, Duration */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                      <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: "0.85rem", fontWeight: 600 }}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectIndex(i)}
                          style={{ cursor: "pointer", width: 16, height: 16 }}
                        />
                        <span>Clip #{i + 1}</span>
                      </label>

                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: "0.75rem", color: "var(--muted)", fontWeight: 500 }}>
                          {formatTime(h.start_time)} - {formatTime(h.end_time)} ({dur}s)
                        </span>

                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "3px 8px",
                            borderRadius: 12,
                            background: `${scoreColor}22`,
                            color: scoreColor,
                            fontWeight: 700,
                            fontSize: "0.8rem",
                            border: `1px solid ${scoreColor}44`,
                          }}
                        >
                          <Flame size={14} fill="currentColor" />
                          <span>{h.score}/100</span>
                        </div>
                      </div>
                    </div>

                    {/* Clip Title */}
                    <h3 style={{ margin: "0 0 10px", fontSize: "1.1rem", fontWeight: 700, lineHeight: 1.3 }}>
                      {h.title}
                    </h3>

                    {/* Opening Hook Quote */}
                    {h.hook_sentence && (
                      <div
                        style={{
                          background: "var(--input-bg, #27272a)",
                          padding: "10px 12px",
                          borderRadius: 8,
                          fontSize: "0.88rem",
                          fontStyle: "italic",
                          color: "var(--fg)",
                          marginBottom: 10,
                          borderLeft: "3px solid var(--accent, #6366f1)",
                        }}
                      >
                        "{h.hook_sentence}"
                      </div>
                    )}

                    {/* Why this is viral */}
                    {h.virality_reason && (
                      <p style={{ margin: "0 0 16px", fontSize: "0.8rem", color: "var(--muted)", lineHeight: 1.4 }}>
                        💡 <strong>Why it hooks:</strong> {h.virality_reason}
                      </p>
                    )}
                  </div>

                  {/* Actions */}
                  <div style={{ display: "flex", alignItems: "center", gap: 10, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
                    <button
                      className="btn secondary sm"
                      onClick={(e) => { e.stopPropagation(); handlePlayToggle(i, h); }}
                      style={{ display: "flex", alignItems: "center", gap: 6, flex: "1 1 auto" }}
                    >
                      {isPlaying ? <Pause size={14} /> : <Play size={14} />}
                      {isPlaying ? "Pause" : "Play clip"}
                    </button>

                    <button
                      className="btn primary sm"
                      onClick={(e) => { e.stopPropagation(); handleSliceOne(i); }}
                      disabled={isSlicing}
                      style={{ display: "flex", alignItems: "center", gap: 6 }}
                    >
                      {isSlicing ? <RefreshCw className="spin" size={14} /> : <Scissors size={14} />}
                      {isSlicing ? "Slicing..." : "Open in Studio"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        !loading && (
          <div
            style={{
              textAlign: "center",
              padding: "60px 20px",
              background: "var(--card-bg, #18181b)",
              borderRadius: 16,
              border: "1px dashed var(--border)",
            }}
          >
            <div style={{ width: 64, height: 64, borderRadius: "50%", background: "rgba(99, 102, 241, 0.1)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 18px", color: "var(--accent, #6366f1)" }}>
              <Scissors size={32} />
            </div>
            <h3 style={{ margin: "0 0 8px", fontSize: "1.2rem", fontWeight: 600 }}>No Shorts Extracted Yet</h3>
            <p style={{ margin: "0 auto 24px", maxWidth: 440, color: "var(--muted)", fontSize: "0.9rem" }}>
              Click <strong>"Find Viral Highlights"</strong> above to parse the recording with our multi-signal virality framework and identify scroll-stopping clips.
            </p>
          </div>
        )
      )}
    </div>
  );
}
