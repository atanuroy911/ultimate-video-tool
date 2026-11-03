import React, { useEffect, useState, useRef } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, ChevronLeft, ChevronRight, Sparkles, Scissors, Play, Pause, Flame, Video, RefreshCw, Wand2, Layers, Upload } from "lucide-react";
import { get, post, upload } from "../api";
import "../social/social.css";
import "../shorts.css";
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
  const nav = useNavigate();
  const { id: paramProjectId } = useParams<{ id?: string }>();
  const [searchParams] = useSearchParams();
  const initialUrl = searchParams.get("url") || "";
  const [source, setSource] = useState<"upload"|"link"|"library">(paramProjectId ? "library" : initialUrl ? "link" : "upload");
  const [changingSource, setChangingSource] = useState(false);
  const [created, setCreated] = useState<{child_project_id:string}[]>([]);

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
  const busy = importing || loading || batchExporting || batchSlicing || slicingIndex !== null;

  const mediaRef = useRef<HTMLMediaElement | null>(null);
  const touchStart = useRef<number | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  // Load project list
  useEffect(() => {
    get<ProjectSummary[]>("/api/projects").then((list) => {
      setProjects(list);
    }).catch((e) => setStatusMsg(e.message || "Could not load your videos. Refresh to try again."));
  }, []);

  // When project changes, fetch existing detected shorts if any
  useEffect(() => {
    let cancelled = false;
    setShortsData(null);
    setExported([]);
    setCreated([]);
    setStatusMsg("");
    setSelectedIndices([]);
    setFocusedIndex(0);
    mediaRef.current?.pause();
    setPlayingIndex(null);
    if (!selectedPid) return;
    get<ShortsData>(`/api/projects/${selectedPid}/shorts`)
      .then((data) => {
        if (cancelled) return;
        if (data && data.highlights && data.highlights.length > 0) {
          setShortsData(data);
          setSelectedIndices(data.highlights.map((_, i) => i));
        } else {
          setShortsData(null);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [selectedPid]);

  const handleDetect = async (pid = selectedPid) => {
    if (!pid) return;
    setLoading(true);
    setStatusMsg("Reading your video to find moments that work as short clips…");
    try {
      const job = await post<{ id: string }>(`/api/projects/${pid}/shorts/detect`, { num_clips: clipCount });
      for (let attempt = 0; attempt < 300; attempt++) {
        const current = await get<{ status: string; msg?: string; error?: string }>(`/api/jobs/${job.id}`);
        if (current.status === "error" || current.status === "cancelled") throw new Error(current.error || "Highlight detection stopped");
        if (current.status === "done") {
          const fresh = await get<ShortsData>(`/api/projects/${pid}/shorts`);
          setShortsData(fresh);
          setChangingSource(false);
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
      setChangingSource(false);
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
      const job = await post<{ id: string }>("/api/projects/from-link", { url: youtubeUrl.trim(), language: "auto", aspect: "9:16", want_video: true, start: true, options: { aroll, caption_style: captionStyle, target_length: "keep" } });
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
    setPlayingIndex(idx);
    media.play().catch(() => {
      setPlayingIndex(null);
      setStatusMsg("Preview could not play in this browser. Try an MP4 video.");
    });
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
      setStatusMsg("Could not create clip: " + (err?.message || "unknown error"));
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
        setCreated(res.created);
        setStatusMsg(`${res.created.length} editable clips ready.`);
      }
    } catch (err: any) {
      setBatchSlicing(false);
      setStatusMsg("Could not create clips: " + (err?.message || "unknown error"));
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

  const picks=shortsData?.highlights ?? [];
  const current=picks[focusedIndex];
  const showSource=!picks.length||changingSource;
  const stopAtEnd=(e:React.SyntheticEvent<HTMLMediaElement>)=>{
    if(playingIndex===focusedIndex&&current&&e.currentTarget.currentTime>=current.end_time){e.currentTarget.pause();setPlayingIndex(null);}
  };
  const startPreview=(e:React.SyntheticEvent<HTMLMediaElement>)=>{
    if(current&&(e.currentTarget.currentTime<current.start_time||e.currentTarget.currentTime>=current.end_time))e.currentTarget.currentTime=current.start_time;
    setPlayingIndex(focusedIndex);
  };
  return <div className="page-inner workflow-page shorts-workflow">
    <header className="workflow-header"><div><h1>Make short clips</h1><p>A long video. Your best moments. Ready to share.</p></div>{!!picks.length&&<button className="btn" disabled={busy} onClick={()=>setChangingSource(!changingSource)}>{changingSource?'Back to picks':'Change video'}</button>}</header>
    <ol className="shorts-steps" aria-label="Clip progress"><li aria-current={showSource?'step':undefined}><b>1</b> Choose a video</li><li aria-current={!showSource&&!created.length&&!exported.length?'step':undefined}><b>2</b> Pick moments</li><li aria-current={created.length||exported.length?'step':undefined}><b>3</b> Make clips</li></ol>
    {showSource&&<section className="shorts-source card card-pad">
      <nav className="workflow-tabs" aria-label="Video source">{([['upload','Upload'],['link','Paste a link'],['library','Your videos']] as const).map(([key,label])=><button key={key} disabled={busy} className={source===key?'selected':''} aria-pressed={source===key} onClick={()=>setSource(key)}>{label}</button>)}</nav>
      {source==='upload'&&<button className="shorts-dropzone" disabled={busy} onClick={()=>fileRef.current?.click()} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(!busy)handleFile(e.dataTransfer.files[0]);}}><Upload size={32}/><strong>{importing?'Preparing your video…':'Drop a video here, or choose a file'}</strong><span>MP4, MOV, MKV or WebM</span></button>}
      <input ref={fileRef} type="file" accept=".mp4,.mov,.mkv,.webm,video/*" hidden onChange={e=>handleFile(e.target.files?.[0])}/>
      {source==='link'&&<div className="col"><label className="field">Video link<input type="url" value={youtubeUrl} disabled={busy} onChange={e=>setYoutubeUrl(e.target.value)} placeholder="https://youtube.com/watch…"/></label><button className="btn primary self-start" disabled={busy||!youtubeUrl.trim()} onClick={handleImport}>Import & find moments</button></div>}
      {source==='library'&&<div className="col"><label className="field">Choose a video<select value={selectedPid} disabled={busy} onChange={e=>setSelectedPid(e.target.value)}><option value="" disabled>Select a video</option>{projects.map(p=><option key={p.id} value={p.id}>{p.title} · {formatTime(p.duration||0)}</option>)}</select></label><button className="btn primary self-start" disabled={busy||!selectedPid} onClick={()=>handleDetect()}><Sparkles size={16}/> Find moments</button>{!projects.length&&<p className="muted">Upload a recording or paste a link to start.</p>}</div>}
      <label className="field shorts-count">Moments to find<select value={clipCount} disabled={busy} onChange={e=>setClipCount(+e.target.value)}>{[3,5,6,8,10,12].map(n=><option key={n}>{n}</option>)}</select></label>
    </section>}
    {statusMsg&&<div className={`banner ${busy?'':'info'}`} role="status">{busy&&<RefreshCw size={16} className="spin"/>}{statusMsg}{importing&&uploadProgress>0&&uploadProgress<1&&<progress max={1} value={uploadProgress} aria-label="Upload progress"/>}</div>}
    {!!picks.length&&!showSource&&<>
      <div className="shorts-workspace">
        <aside className="shorts-picks" aria-label="Suggested moments"><div className="row wrap"><h2 className="grow">{picks.length} moments</h2><button className="btn ghost sm" disabled={busy} onClick={()=>setSelectedIndices(selectedIndices.length===picks.length?[]:picks.map((_,i)=>i))}>{selectedIndices.length===picks.length?'Clear picks':'Keep all'}</button></div>
          {picks.map((h,i)=><article key={i} className={`shorts-pick ${i===focusedIndex?'on':''}`}><label className="shorts-keep"><input type="checkbox" aria-label={`Keep ${h.title}`} checked={selectedIndices.includes(i)} disabled={busy} onChange={()=>toggleSelectIndex(i)}/></label><button className="shorts-pick-body" onClick={()=>focusClip(i)} aria-pressed={i===focusedIndex}><strong>{h.title}</strong><small>{formatTime(h.start_time)} – {formatTime(h.end_time)} · {Math.round(h.end_time-h.start_time)}s</small></button></article>)}
          <button className="btn ghost sm" disabled={busy} onClick={()=>handleDetect()}><RefreshCw size={14}/> Find new suggestions</button>
        </aside>
        {current&&<section className="shorts-review card card-pad" aria-label="Review moment"><div className="shorts-player">{shortsData?.preview_url&&/\.(mp4|mov|mkv|webm)(\?|$)/i.test(shortsData.preview_url)?<video key={selectedPid} ref={mediaRef as React.RefObject<HTMLVideoElement>} src={shortsData.preview_url} controls playsInline preload="metadata" onLoadedMetadata={e=>{e.currentTarget.currentTime=current.start_time;}} onPlay={startPreview} onPause={()=>setPlayingIndex(null)} onTimeUpdate={stopAtEnd} onEnded={()=>setPlayingIndex(null)}/>:<div className="col"><Video size={30}/><span>Audio preview</span><audio ref={mediaRef as React.RefObject<HTMLAudioElement>} src={shortsData?.preview_url||projects.find(p=>p.id===selectedPid)?.audio_url||''} controls onPlay={startPreview} onPause={()=>setPlayingIndex(null)} onTimeUpdate={stopAtEnd}/></div>}</div>
          <div className="row"><span className="small muted grow">Moment {focusedIndex+1} of {picks.length} · {formatTime(current.start_time)} – {formatTime(current.end_time)}</span><button className="btn icon sm" aria-label="Previous moment" disabled={!focusedIndex} onClick={()=>focusClip(focusedIndex-1)}><ChevronLeft size={16}/></button><button className="btn icon sm" aria-label="Next moment" disabled={focusedIndex===picks.length-1} onClick={()=>focusClip(focusedIndex+1)}><ChevronRight size={16}/></button></div>
          <h2>{current.title}</h2><blockquote>{current.hook_sentence}</blockquote><p className="small muted">{current.virality_reason}</p>
          <div className="row wrap"><button className="btn" onClick={()=>handlePlayToggle(focusedIndex,current)}>{playingIndex===focusedIndex?<Pause size={15}/>:<Play size={15}/>} {playingIndex===focusedIndex?'Pause':'Play moment'}</button><button className="btn" disabled={busy} onClick={()=>handleSliceOne(focusedIndex)}><Scissors size={15}/> Edit this clip</button></div>
        </section>}
      </div>
      <section className="shorts-finish card card-pad"><div className="grow"><h2>{selectedIndices.length} {selectedIndices.length===1?'moment':'moments'} selected</h2><p className="small muted">Each becomes a separate, editable video.</p></div><label className="field">Caption look<select disabled={busy} value={captionStyle} onChange={e=>setCaptionStyle(e.target.value as typeof captionStyle)}><option value="pop">Pop</option><option value="box">Box</option><option value="pill">Pill</option><option value="underline">Underline</option><option value="theme">Match the theme</option></select></label><label className="field">Picture<select disabled={busy} value={aroll} onChange={e=>setAroll(e.target.value as typeof aroll)}><option value="auto">Keep original video</option><option value="off">Use graphics</option></select></label><div className="row wrap"><button className="btn" disabled={busy||!selectedIndices.length} onClick={handleBatchSlice}>{batchSlicing?'Creating…':'Create editable clips'}</button><button className="btn primary" disabled={busy||!selectedIndices.length} onClick={handleBatchExport}>{batchExporting?'Exporting…':'Export clips'}</button></div></section>
    </>}
    {(created.length>0||exported.length>0)&&<section className="col shorts-results"><h2>Your clips are ready</h2>{(exported.length?exported:created).map((item,i)=><div className="account-card" key={item.child_project_id}><span className="grow">Clip {i+1}</span><Link className="btn sm" to={`/p/${item.child_project_id}`}>Edit</Link>{'url'in item&&<><a className="btn sm" href={String(item.url)} download>Download</a><Link className="btn primary sm" to={`/social?video=${item.child_project_id}`}>Share</Link></>}</div>)}</section>}
  </div>;
}
