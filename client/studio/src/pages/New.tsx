import { Check, ChevronLeft, ChevronRight, CornerDownLeft, Mic, Music, Pause, Play, RotateCcw, Scissors, Sparkles, Square, Subtitles, Upload, UserSquare, Video, Volume2, VolumeX } from "lucide-react";
import { useFetch, useMusic, useThemes } from "../hooks";
import { useT } from "../i18n";
import { Group, Row } from "../ds";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fmtTime, get, post, upload } from "../api";
import { settingsStore, toast, useStore } from "../store";
import type { ModelInfo, ProjectSummary, VideoStyle } from "../types";

interface VoiceEngine {
  id: string;
  label: string;
  offline: boolean;
  licence: string;
  available: boolean;
  note: string;
  voices: { id: string; label: string; lang: string }[];
}
import { Seg, Spinner } from "../ui";
import CatalogList from "../review/CatalogList";
import ElementExample from "../review/ElementExample";
import PictureChoices from "../components/PictureChoices";
import StyleChoices from "../components/StyleChoices";
import { DirectorChoices, OptionPage, OptionsHub, optionDef, type OptionId, type OptionsCtx } from "./NewOptions";

/* ------------------------------------------------------------------ recorder */
type RecState = "idle" | "recording" | "paused" | "recorded";

function useRecorder() {
  const [state, setState] = useState<RecState>("idle");
  const [level, setLevel] = useState(0);
  const [seconds, setSeconds] = useState(0);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [warn, setWarn] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const stream = useRef<MediaStream | null>(null);
  const ctx = useRef<AudioContext | null>(null);
  const raf = useRef(0);
  const clock = useRef({ acc: 0, t0: 0 });
  const quietFor = useRef(0);
  const peakHold = useRef(0);

  const loadDevices = async () => {
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      setDevices(all.filter((d) => d.kind === "audioinput"));
    } catch {
      /* ignore */
    }
  };
  useEffect(() => {
    loadDevices();
    return () => stop(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const tick = () => {
    const an = (ctx.current as any)?._an as AnalyserNode | undefined;
    if (an) {
      const buf = new Float32Array(an.fftSize);
      an.getFloatTimeDomainData(buf);
      let sum = 0,
        peak = 0;
      for (const v of buf) {
        sum += v * v;
        peak = Math.max(peak, Math.abs(v));
      }
      const rms = Math.sqrt(sum / buf.length);
      setLevel(Math.min(1, rms * 4));
      if (peak > 0.985) peakHold.current = performance.now();
      if (rec.current?.state === "recording") {
        quietFor.current = rms < 0.01 ? quietFor.current + 1 : 0;
        const clipping = performance.now() - peakHold.current < 1500;
        setWarn(clipping ? "Too loud: the sound is clipping. Move back from the mic or lower the input volume." : quietFor.current > 180 ? "Very quiet. Check the microphone or speak closer." : null);
        const now = performance.now();
        setSeconds(clock.current.acc + (now - clock.current.t0) / 1000);
      }
    }
    raf.current = requestAnimationFrame(tick);
  };

  const start = async () => {
    setError(null);
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        audio: { deviceId: deviceId ? { exact: deviceId } : undefined, echoCancellation: false, noiseSuppression: true, autoGainControl: false },
      });
      stream.current = s;
      loadDevices();
      const ac = new AudioContext();
      const src = ac.createMediaStreamSource(s);
      const an = ac.createAnalyser();
      an.fftSize = 1024;
      src.connect(an);
      (ac as any)._an = an;
      ctx.current = ac;
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
      const r = new MediaRecorder(s, mime ? { mimeType: mime } : undefined);
      chunks.current = [];
      r.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      r.onstop = () => {
        const b = new Blob(chunks.current, { type: r.mimeType || "audio/webm" });
        setBlob(b);
        setUrl(URL.createObjectURL(b));
        setState("recorded");
      };
      r.start(250);
      rec.current = r;
      clock.current = { acc: 0, t0: performance.now() };
      setSeconds(0);
      setBlob(null);
      setUrl(null);
      setState("recording");
      cancelAnimationFrame(raf.current);
      raf.current = requestAnimationFrame(tick);
    } catch (e: any) {
      setError(e?.name === "NotAllowedError" ? "Microphone access was blocked. Allow it in the browser address bar, then try again." : e?.name === "NotFoundError" ? "No microphone found." : `Could not start recording: ${e?.message || e}`);
    }
  };
  const pause = () => {
    if (rec.current?.state === "recording") {
      rec.current.pause();
      clock.current.acc += (performance.now() - clock.current.t0) / 1000;
      setState("paused");
    } else if (rec.current?.state === "paused") {
      rec.current.resume();
      clock.current.t0 = performance.now();
      setState("recording");
    }
  };
  const stop = (silent = false) => {
    cancelAnimationFrame(raf.current);
    if (rec.current && rec.current.state !== "inactive") {
      if (silent) rec.current.onstop = null;
      rec.current.stop();
    }
    stream.current?.getTracks().forEach((t) => t.stop());
    ctx.current?.close().catch(() => {});
    ctx.current = null;
    setLevel(0);
    setWarn(null);
  };
  const retake = () => {
    if (url) URL.revokeObjectURL(url);
    setBlob(null);
    setUrl(null);
    setSeconds(0);
    setState("idle");
  };
  return { state, level, seconds, blob, url, devices, deviceId, setDeviceId, warn, error, start, pause, stop: () => stop(false), retake, setBlob, setUrl, setState };
}


/* ------------------------------------------------------------------ page
   The everyday path is deliberately tiny: add content → choose where it will be posted → create.
   The backend still has every expert control, but those choices stay behind Customize on the final screen. */
type SourceKind = "voice" | "file" | "link" | "script";
type SourceMode = "talking_head" | "video" | "audio";
type StepId = "source" | "mode" | "style" | "director" | "shape" | "look" | "sound" | "voice" | "ready";
type DirectorInfo = { id: string; label: string; available: boolean; note: string };
type DirectorsResponse = { directors: DirectorInfo[] };

const LINK = /^https?:\/\/\S+\.\S+$/i;
const hasBangla = (s: string) => /[ঀ-৿]/.test(s);
const isVideoFile = (f: File | null) => !!f && (/^video\//.test(f.type) || /\.(mp4|mov|mkv|webm)$/i.test(f.name));
const rememberedStyle = (): VideoStyle => {
  try {
    const saved = localStorage.getItem("vt-new-style");
    return saved === "reel" || saved === "stick" || saved === "emoji" || saved === "cartoon" || saved === "story" || saved === "explainer" || saved === "infographic" || saved === "mixed" ? saved : "auto";
  } catch {
    return "auto";
  }
};

/** A big answer tile: letter key, title, one line of explanation. */
function Choice(props: { letter: string; selected: boolean; title: string; about?: string; icon?: React.ReactNode; onPick: () => void }) {
  return (
    <button type="button" role="radio" aria-checked={props.selected} className={`tf-choice ${props.selected ? "sel" : ""}`} onClick={props.onPick}>
      <kbd>{props.letter}</kbd>
      {props.icon && <span className="tf-icon">{props.icon}</span>}
      <span className="col grow" style={{ gap: 2 }}>
        <strong>{props.title}</strong>
        {props.about && <span className="small muted">{props.about}</span>}
      </span>
      {props.selected && <Check size={18} />}
    </button>
  );
}

/* what each style looks like, in a few words: the closed list of choices has no room for the full description, which shows under it */
const CARTOON_LOOKS = [
  { value: "ink", title: "Ink outlines", about: "Bold dark outlines, like a comic." },
  { value: "classic", title: "Classic colour", about: "Clean flat colour, no outlines." },
  { value: "paper", title: "Paper cutout", about: "Cut-paper edges and soft shadows." },
  { value: "illustrated", title: "Original illustrated cast", about: "The planner draws each scene its own way." },
];
const STYLE_SHORT: Record<string, string> = { auto: "AI picks per scene", reel: "AI draws a picture per sentence", mixed: "real footage + animated graphics", explainer: "animated titles, icons, charts", stick: "stick figures act it out", cartoon: "Cartoon 1: characters in painted places", story: "Cartoon 2: a drawn storybook, props appear on the words", emoji: "big emoji react to each line" };

const STYLE_CHOICES: { value: VideoStyle; title: string; about: string }[] = [
  { value: "auto", title: "tf.style.auto", about: "tf.style.auto.about" },
  { value: "reel", title: "tf.style.reel", about: "tf.style.reel.about" },
  { value: "mixed", title: "tf.style.mixed", about: "tf.style.mixed.about" },
  { value: "explainer", title: "tf.style.explainer", about: "tf.style.explainer.about" },
  { value: "infographic", title: "tf.style.infographic", about: "tf.style.infographic.about" },
  { value: "stick", title: "tf.style.stick", about: "tf.style.stick.about" },
  { value: "cartoon", title: "tf.style.cartoon", about: "tf.style.cartoon.about" },
  { value: "story", title: "tf.style.story", about: "tf.style.story.about" },
  { value: "emoji", title: "tf.style.emoji", about: "tf.style.emoji.about" },
];
const SHAPE_CHOICES = [
  { value: "9:16" as const, title: "tf.shape.vertical", about: "tf.shape.vertical.about" },
  { value: "16:9" as const, title: "tf.shape.wide", about: "tf.shape.wide.about" },
  { value: "1:1" as const, title: "tf.shape.square", about: "tf.shape.square.about" },
];
const LANGUAGE_LABEL: Record<string, string> = { auto: "tf.lang.auto", bn: "বাংলা", en: "English" };

export default function NewPage() {
  const t = useT();
  const nav = useNavigate();
  const settings = useStore(settingsStore);
  const { data: themes } = useThemes();
  const { data: music } = useMusic();
  const { data: models } = useFetch<ModelInfo[]>("/api/models");
  const { data: engines } = useFetch<VoiceEngine[]>("/api/voices");
  const { data: directors } = useFetch<DirectorsResponse>("/api/directors");
  const recorder = useRecorder();

  /* ---- answers */
  const [typedText, setTypedText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [subtitles, setSubtitles] = useState<File | null>(null);       // the recording's own .srt: its words and timing replace speech recognition
  const subtitlesInput = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const trimmedText = typedText.trim();
  const source: SourceKind | null = recorder.blob ? "voice" : file ? "file" : LINK.test(trimmedText) ? "link" : trimmedText ? "script" : null;

  const [detected, setDetected] = useState<{ mode: SourceMode; face_share?: number; width?: number; height?: number } | null>(null);
  const [inspecting, setInspecting] = useState(false);
  const [keepSpeaker, setKeepSpeaker] = useState(true);
  const [recordingEdit,setRecordingEdit]=useState<'auto'|'subtitles'|'screen'>('auto');
  const [style, setStyleRaw] = useState<VideoStyle>(rememberedStyle);
  const setStyle = (value: VideoStyle) => {
    setStyleRaw(value);
    try {
      localStorage.setItem("vt-new-style", value);
    } catch {
      /* private window */
    }
  };
  const [aspect, setAspect] = useState<"9:16" | "1:1" | "16:9">(settings.default_aspect);
  const [theme, setTheme] = useState(settings.default_theme);
  const [musicTrack, setMusicTrack] = useState<string>(settings.default_music === null ? "" : settings.default_music ?? "auto");
  const [captions, setCaptions] = useState("auto");
  const [endCard, setEndCard] = useState("");
  const [voiceDirection, setVoiceDirection] = useState<"auto" | "off">("auto");               // the director adds delivery notes and sounds (sigh, laugh) to a spoken script where the voice can follow them
  const [cartoonTemplate, setCartoonTemplate] = useState("ink");
  const [usecase, setUsecase] = useState("auto");                                       // the kind of video, for the director (the Purpose tile); auto decides from what is said
  const [director, setDirector] = useState("best");
  const usecases = useFetch<{ id: string; label: string; about?: string }[]>("/api/usecases");
  const [planReview, setPlanReview] = useState<"auto" | "always" | "never">("auto");      // reels only: look at the plan before anything is drawn
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState<"auto" | "bn" | "en">("auto");

  // the finer choices (the options screen)
  const [pace, setPace] = useState<"calm" | "normal" | "fast">(settings.default_pace as any);
  const [removeFillers, setRemoveFillers] = useState(true);
  const [removeRetakes, setRemoveRetakes] = useState(true);
  const [targetLength, setTargetLength] = useState<"auto" | "keep" | "60" | "90">("auto");
  const [soundEffects, setSoundEffects] = useState<"off" | "subtle" | "normal" | "rich">("normal");
  const [scriptPolicy, setScriptPolicy] = useState<"mixed" | "bangla">("mixed");
  const [speakers, setSpeakers] = useState<"auto" | "off">("auto");
  const [glossary, setGlossary] = useState("");
  const SPEECH_MODEL_DEFAULT = "bn-medium";
  const [speechModel, setSpeechModel] = useState(SPEECH_MODEL_DEFAULT);
  const [subtitlesMode, setSubtitlesMode] = useState<"auto" | "any" | "off">("auto");
  const [pictures, setPictures] = useState<File[]>([]);
  const pictureInput = useRef<HTMLInputElement>(null);

  // the AI voice that reads a script
  const [engine, setEngine] = useState("auto");
  const [voice, setVoiceRaw] = useState("auto");
  const voiceChosenByPerson = useRef(false);
  const setVoice = (id: string) => {
    voiceChosenByPerson.current = true;
    setVoiceRaw(id);
  };
  const [rate, setRate] = useState(1);
  const [samplingVoice, setSamplingVoice] = useState(false);
  const sampleAudio = useRef<HTMLAudioElement>(null);
  const musicPreview = useRef<HTMLAudioElement>(null);
  const [previewingTrack, setPreviewingTrack] = useState<string | null>(null);

  const scriptLanguage = hasBangla(typedText) ? "bn" : "en";
  useEffect(() => {
    if (voiceChosenByPerson.current || !engines) return;
    const chosenEngine = engines.find((e) => e.id === engine);
    const match = chosenEngine?.voices.find((v) => v.lang.startsWith(language === "auto" ? scriptLanguage : language));
    if (match) setVoiceRaw(match.id);
  }, [scriptLanguage, language, engine, engines]);
  useEffect(() => setAspect(settings.default_aspect), [settings.default_aspect]);
  useEffect(() => setTheme(settings.default_theme), [settings.default_theme]);

  // a video file is looked at once: is someone talking to the camera? (decides the mode and a sensible shape)
  useEffect(() => {
    setDetected(null);
    if (!file) return;
    if (!isVideoFile(file)) {
      setDetected({ mode: "audio" });
      return;
    }
    let cancelled = false;
    setInspecting(true);
    const form = new FormData();
    form.append("file", file);
    upload<{ mode: SourceMode; face_share: number; width: number; height: number }>("/api/inspect", form)
      .then((found) => {
        if (cancelled) return;
        setDetected(found);
        setKeepSpeaker(found.mode === "talking_head");
      })
      .catch(() => !cancelled && setDetected({ mode: "video" }))
      .finally(() => !cancelled && setInspecting(false));
    return () => {
      cancelled = true;
    };
  }, [file]);

  const mode: SourceMode = source === "file" ? detected?.mode ?? (isVideoFile(file) ? "video" : "audio") : source === "link" ? (detected?.mode ?? "video") : "audio";
  const hasPicture = mode !== "audio";
  const speakerStays = hasPicture && keepSpeaker;

  /* Three human decisions. Everything technical already has an automatic answer. */
  const steps: StepId[] = useMemo(() => {
    return ["source", "shape", "ready"];
  }, []);
  const [reviewScript, setReviewScript] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [detail, setDetail] = useState<OptionId | null>(null);       // the option page that is open on the last screen
  const step = steps[Math.min(stepIndex, steps.length - 1)];
  const scriptTooLong = source === "script" && trimmedText.length > 5000;
  const canContinue = step !== "source" || (!!source && recorder.state !== "recording" && recorder.state !== "paused" && !inspecting && !scriptTooLong);
  const goNext = () => canContinue && setStepIndex((i) => Math.min(i + 1, steps.length - 1));
  const goBack = () => setStepIndex((i) => Math.max(i - 1, 0));

  /* ---- start */
  const glossaryMap = useMemo(() => {
    const map: Record<string, string> = {};
    glossary.split(/[,\n]/).forEach((line) => {
      const [word, ...rest] = line.split("=");
      if (word?.trim()) map[word.trim()] = rest.join("=").trim() || word.trim();
    });
    return map;
  }, [glossary]);
  const projectOptions = () => ({
    review_script: reviewScript, remove_fillers: removeFillers, remove_retakes: removeRetakes, target_length: targetLength, caption_style: captions, music: musicTrack || null,
    sfx: soundEffects !== "off", sfx_level: soundEffects, script_policy: scriptPolicy, speakers, glossary: glossaryMap, asr_model: speechModel,
    aroll: speakerStays ? "auto" : "off", voice_direction: voiceDirection,
    director,
    ...(hasPicture&&recordingEdit!=='auto'?{recording_edit:recordingEdit,aroll:'auto',look:'classic',remove_fillers:false,remove_retakes:false,target_length:'keep',sound_events:'off',speakers:'off'}:{}),
    ...(style === "cartoon" ? {cartoon_template:cartoonTemplate} : {}),
    ...(style === "reel" && (!hasPicture||recordingEdit==='auto') ? { look: "reel", plan_review: planReview, end_card: endCard.trim() } : {}),
    ...(style === "story" && (!hasPicture||recordingEdit==='auto') ? { look: "story" } : {}),
  });
  const kind = style === "auto" || style === "reel" || style === "story" ? "explainer" : style;
  const [starting, setStarting] = useState(false);
  const [uploadShare, setUploadShare] = useState(0);
  const [linkMessage, setLinkMessage] = useState("");

  const attachPictures = async (projectId: string) => {
    if (!pictures.length) return;
    for (const picture of pictures) {
      const form = new FormData();
      form.append("file", picture);
      const res = await fetch(`/api/projects/${projectId}/media`, { method: "POST", body: form });
      if (!res.ok) toast((await res.json().catch(() => ({}))).detail || `Could not add ${picture.name}`, "err", 6000);
    }
    await post(`/api/projects/${projectId}/run`, { from_stage: null, force: false });
  };
  const waitForProject = async (jobId: string, say?: (message: string) => void) => {
    for (;;) {
      await new Promise((done) => setTimeout(done, 1000));
      const job = await get<{ status: string; msg: string; frac: number; error: string; result?: { project: string } }>(`/api/jobs/${jobId}`);
      if (job.status === "error") throw new Error(job.error || "The download failed.");
      if (job.status === "cancelled") throw new Error("Cancelled.");
      say?.(`${job.msg || "Downloading"}${job.frac > 0 && job.frac < 1 ? ` ${Math.round(job.frac * 100)}%` : ""}`);
      if (job.status === "done" && job.result) return job.result.project;
    }
  };
  const startLock = useRef(false);
  const start = async () => {
    if (!source || startLock.current) return;
    startLock.current = true;
    setStarting(true);
    const common = { language, aspect, theme, pace, usecase, kind };
    try {
      let projectId: string;
      if (source === "link") {
        setLinkMessage("Contacting the site…");
        const job = await post<{ id: string }>("/api/projects/from-link", { ...common, url: trimmedText, title: title.trim(), want_video: speakerStays, options: { ...projectOptions(), use_subtitles: subtitlesMode }, start: pictures.length === 0 });
        projectId = await waitForProject(job.id, setLinkMessage);
      } else if (source === "script") {
        const res = await post<{ project: ProjectSummary }>("/api/projects/from-script", { ...common, title: title.trim(), script: typedText, engine, voice, rate, options: projectOptions(), start: pictures.length === 0 });
        projectId = res.project.id;
      } else {
        const blob = source === "voice" ? recorder.blob! : file!;
        const form = new FormData();
        form.append("audio", blob, blob instanceof File ? blob.name : "recording.webm");
        form.append("title", title.trim());
        Object.entries(common).forEach(([key, value]) => form.append(key, value));
        if (subtitles) form.append("subtitles", subtitles);
        if (pictures.length) form.append("start", "false");
        form.append("options", JSON.stringify(projectOptions()));
        const res = await upload<{ project: ProjectSummary }>("/api/projects", form, setUploadShare);
        projectId = res.project.id;
      }
      await attachPictures(projectId);
      nav(`/p/${projectId}/progress`);
    } catch (e: any) {
      toast(e.message, "err", 9000);
      setStarting(false);
      setLinkMessage("");
      startLock.current = false;
    }
  };

  /* ---- keyboard: Enter moves on (starts on the last screen), letters pick an answer, Escape goes back */
  const letterHandlers = useRef<(() => void)[]>([]);
  letterHandlers.current = [];
  const choice = (selected: boolean, title: string, about: string | undefined, onPick: () => void, icon?: React.ReactNode) => {
    const index = letterHandlers.current.length;
    letterHandlers.current.push(onPick);
    return <Choice key={title} letter={String.fromCharCode(65 + index)} selected={selected} title={title} about={about} icon={icon} onPick={onPick} />;
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement;
      if (e.key === "Enter" && !e.shiftKey && !(e.target instanceof HTMLTextAreaElement && step === "source" && !LINK.test(trimmedText))) {
        if (typing && step === "ready") return;
        if (detail) { e.preventDefault(); setDetail(null); return; }
        if (e.target instanceof HTMLButtonElement) return;
        e.preventDefault();
        step === "ready" ? start() : goNext();
      } else if (e.key === "Escape" && detail) {
        setDetail(null);
      } else if (e.key === "Escape" && stepIndex > 0) {
        goBack();
      } else if (!typing && !e.metaKey && !e.ctrlKey && /^[a-e]$/i.test(e.key)) {
        letterHandlers.current[e.key.toUpperCase().charCodeAt(0) - 65]?.();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const takeFile = (picked: File | null | undefined) => {
    if (!picked) return;
    setFile(picked);
    setTypedText("");
    recorder.retake();
  };
  const toggleTrackPreview = (track: { id: string; url: string }) => {
    const audio = musicPreview.current;
    if (!audio) return;
    if (previewingTrack === track.id) {
      audio.pause();
      setPreviewingTrack(null);
    } else {
      audio.src = track.url;
      audio.volume = 0.6;
      audio.play().catch(() => {});
      setPreviewingTrack(track.id);
    }
  };
  const hearVoice = async () => {
    setSamplingVoice(true);
    try {
      const res = await fetch("/api/voices/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ script: trimmedText.split(/[।.?!\n]/)[0] || "", engine, voice, rate, language }) });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Could not make the sample");
      if (sampleAudio.current) {
        sampleAudio.current.src = URL.createObjectURL(await res.blob());
        await sampleAudio.current.play().catch(() => {});
      }
    } catch (e: any) {
      toast(e.message, "err", 7000);
    } finally {
      setSamplingVoice(false);
    }
  };

  const recording = recorder.state === "recording" || recorder.state === "paused";
  const chosenEngine = engines?.find((e) => e.id === engine);
  const themeLabel = theme === "auto" ? t("tf.look.auto") : (themes || []).find((th) => th.name === theme)?.label || theme;
  const musicLabel = musicTrack === "auto" ? "Picked to fit" : musicTrack ? (music || []).find((m) => m.id === musicTrack)?.title || t("tf.row.music") : t("tf.music.none");
  const sourceLabel =
    source === "voice" ? `Your recording · ${fmtTime(recorder.seconds)}`
    : source === "file" ? file!.name
    : source === "link" ? (trimmedText.includes("youtube.com") || trimmedText.includes("youtu.be") ? "YouTube video" : "Video link")
    : source === "script" ? `A script · ${trimmedText.split(/[।.?!\n]+/).filter((x) => x.trim()).length} sentences`
    : "";
  const modeLabel = mode === "talking_head" ? (speakerStays ? t("tf.mode.talking.speaker") : t("tf.mode.talking.graphics"))
    : mode === "video" ? (speakerStays ? (source === "link" ? t("tf.mode.link.speaker") : t("tf.mode.video.speaker")) : t("tf.mode.video.graphics"))
    : source === "script" ? t("tf.mode.script") : t("tf.mode.audio");
  const languageGuess = source === "script" ? (scriptLanguage === "bn" ? t("tf.lang.script.bn") : t("tf.lang.script.en")) : t("tf.lang.speech");

  /* ---- the screens */
  const optionsCtx = (): OptionsCtx => ({
    source, hasPicture, language, setLanguage, languageGuess, style, setStyle, styleTitle: t(STYLE_CHOICES.find((c) => c.value === style)?.title ?? "tf.style.auto"),
    recordingEdit, setRecordingEdit, director, setDirector, directors: directors?.directors || [{ id: "best", label: "Best available", available: true, note: "Uses your fallback order." }],
    theme, setTheme, themes: (themes || []).filter((th) => !th.name.startsWith("auto-")) as any,
    musicTrack, setMusicTrack, music: (music || []) as any, previewingTrack, toggleTrackPreview, captions, setCaptions, pace, setPace,
    removeFillers, setRemoveFillers, removeRetakes, setRemoveRetakes, targetLength, setTargetLength, soundEffects, setSoundEffects, glossary, setGlossary,
    pictures, addPictures: () => pictureInput.current?.click(), removePicture: (i) => setPictures((list) => list.filter((_, j) => j !== i)),
    reviewScript, setReviewScript, endCard, setEndCard, voiceSummary: `${chosenEngine?.label ?? "Automatic"}${voice && voice !== "auto" ? ` · ${chosenEngine?.voices.find((v) => v.id === voice)?.label ?? voice}` : ""}`,
    usecase, setUsecase, usecases: usecases.data ?? [],
    speakers, setSpeakers, scriptPolicy, setScriptPolicy, subtitlesMode, setSubtitlesMode,
    speechModel, setSpeechModel, speechModelDefault: SPEECH_MODEL_DEFAULT, models: models ?? [],
    legacy: (id) => screens[id].body(),
  });
  const screens: Record<StepId, { question: string; hint?: string; body: () => React.ReactNode }> = {
    source: {
      question: t("tf.source.q"),
      hint: t("tf.source.hint"),
      body: () => (
        <div className="col" style={{ gap: 18 }}>
          <div className="col" style={{ alignItems: "center", gap: 10 }}>
            <div className="row" style={{ gap: 18 }}>
              {(recorder.state === "idle" || recorder.state === "recorded") && !file && (
                <button className="rec-btn big" onClick={recorder.state === "recorded" ? recorder.retake : recorder.start} aria-label={recorder.state === "recorded" ? "Record again" : "Start recording"}>
                  {recorder.state === "recorded" ? <RotateCcw size={30} /> : <Mic size={40} />}
                </button>
              )}
              {recording && (
                <>
                  <button className="btn icon lg" onClick={recorder.pause} aria-label={recorder.state === "paused" ? "Resume" : "Pause"}>
                    {recorder.state === "paused" ? <Play size={18} /> : <Pause size={18} />}
                  </button>
                  <button className="rec-btn on big" onClick={recorder.stop} aria-label="Stop recording"><i /></button>
                </>
              )}
            </div>
            {recording && trimmedText && !LINK.test(trimmedText) && (
              <div className="prompter bn" data-testid="prompter" role="region" aria-label="Your script, to read from">{trimmedText}</div>
            )}
            {recording && (
              <>
                <div className="rec-time" aria-live="off">{fmtTime(recorder.seconds)}</div>
                <div className="meter" style={{ width: "min(360px, 100%)" }} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(recorder.level * 100)} aria-label="Input level"><i style={{ width: `${recorder.level * 100}%` }} /></div>
              </>
            )}
            {recorder.state === "idle" && !file && <span className="small muted">{t("tf.source.tap")}</span>}
            {recorder.state === "idle" && !file && recorder.devices.length > 1 && (
              <label className="small muted row" style={{ gap: 6 }}>Microphone
                <select value={recorder.deviceId} onChange={(e) => recorder.setDeviceId(e.target.value)} aria-label="Microphone">
                  <option value="">Default</option>
                  {recorder.devices.map((d) => <option key={d.deviceId} value={d.deviceId}>{d.label || `Microphone ${d.deviceId.slice(0, 4)}`}</option>)}
                </select>
              </label>
            )}
            {recorder.state === "recorded" && recorder.url && <audio controls src={recorder.url} style={{ width: "min(420px, 100%)" }} />}
            {recorder.warn && <div className="banner warn" style={{ width: "100%" }}>{recorder.warn}</div>}
            {recorder.error && <div className="banner err" style={{ width: "100%" }}>{recorder.error}</div>}
          </div>
          {!recording && recorder.state !== "recorded" && (
            file ? (
              <div className="col" style={{ gap: 8, width: "100%" }}>
                <div className="row file-chip">
                  {isVideoFile(file) ? <Video size={16} /> : <Music size={16} />} <strong className="grow">{file.name}</strong>
                  {inspecting && <span className="small muted row" style={{ gap: 6 }}><Spinner size={13} /> {t("tf.looking")}</span>}
                  <button className="btn sm ghost" onClick={() => { setFile(null); setSubtitles(null); }}>{t("tf.remove")}</button>
                </div>
                <input ref={subtitlesInput} type="file" accept=".srt,.vtt" hidden aria-label="Choose a subtitle file" onChange={(e) => { setSubtitles(e.target.files?.[0] || null); e.target.value = ""; }} />
                {subtitles ? (
                  <div className="row file-chip" data-testid="srt-chip">
                    <Subtitles size={16} /> <span className="grow"><strong>{subtitles.name}</strong><span className="small muted" style={{ display: "block" }}>Your words and timing will be used. No transcription.</span></span>
                    <button className="btn sm ghost" onClick={() => setSubtitles(null)}>{t("tf.remove")}</button>
                  </div>
                ) : (
                  <button type="button" className="btn ghost sm" style={{ alignSelf: "flex-start" }} onClick={() => subtitlesInput.current?.click()} data-testid="srt-add">
                    <Subtitles size={14} /> Add your subtitles (.srt) and skip transcription
                  </button>
                )}
              </div>
            ) : (
              <>
                <div className="or-line small muted"><span>{t("tf.or")}</span></div>
                <textarea rows={trimmedText && !LINK.test(trimmedText) ? 7 : 2} className="bn" value={typedText} onChange={(e) => setTypedText(e.target.value)} aria-label="Link or script"
                  placeholder={"Paste a YouTube link, or write your script here…\nলিংক দিন, অথবা এখানে স্ক্রিপ্ট লিখুন।"} maxLength={6000} />
                {trimmedText && LINK.test(trimmedText) && (
                  <div style={{ background: "rgba(99, 102, 241, 0.1)", border: "1px solid rgba(99, 102, 241, 0.25)", borderRadius: 10, padding: "10px 14px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.85rem" }}>
                      <Scissors size={16} style={{ color: "var(--accent, #6366f1)" }} />
                      <span>Want to extract multiple viral Shorts highlights from this video?</span>
                    </div>
                    <button type="button" className="btn sm primary" onClick={() => nav(`/shorts?url=${encodeURIComponent(trimmedText)}`)}>
                      Open Shorts Extractor
                    </button>
                  </div>
                )}
                {trimmedText && !LINK.test(trimmedText) && (() => {
                  const MAX = 5000;
                  const len = trimmedText.length;
                  const over = len > MAX;
                  const warn = len > MAX * 0.8;
                  return (
                    <div className="row" style={{ justifyContent: "flex-end", gap: 8 }}>
                      {over && <span className="small" style={{ color: "var(--err)", fontWeight: 600 }}>Too long — trim {len - MAX} character{len - MAX !== 1 ? "s" : ""} to continue.</span>}
                      <span className="small" style={{ color: over ? "var(--err)" : warn ? "var(--warn)" : "var(--muted)", fontWeight: over || warn ? 600 : 400, fontVariantNumeric: "tabular-nums" }}>
                        {len.toLocaleString()} / {MAX.toLocaleString()}
                      </span>
                    </div>
                  );
                })()}
                <div className="row wrap" style={{ justifyContent: "center" }}>
                  <button type="button" className="btn sm" onClick={() => fileInput.current?.click()}><Upload size={14} /> {t("tf.source.choose")}</button>
                  <span className="small muted">{t("tf.source.drop")}</span>
                </div>
                {!trimmedText && (
                  <details className="sample-voices">
                    <summary className="small">No recording yet? Make a video from a free sample voice</summary>
                    <CatalogList kind="audio" role="speech" action="Make a video" label="Free sample voices"
                      onPick={async (entry) => {
                        const job = await post<{ id: string }>(`/api/catalog/${entry.id}/project`, { language: "en", aspect, kind });
                        nav(`/p/${await waitForProject(job.id)}/progress`);
                      }} />
                  </details>
                )}
              </>
            )
          )}
          <input ref={fileInput} type="file" accept="audio/*,video/*,.m4a,.webm,.opus,.mkv" hidden onChange={(e) => takeFile(e.target.files?.[0])} aria-label="Choose a file" />
        </div>
      ),
    },
    mode: {
      question: source === "link" ? t("tf.mode.q.link") : mode === "talking_head" ? t("tf.mode.q.talking") : t("tf.mode.q.video"),
      hint: source === "link" ? t("tf.mode.hint.link") : mode === "talking_head" ? t("tf.mode.hint.talking") : t("tf.mode.hint.video"),
      body: () => (
        <div className="col tf-choices" role="radiogroup" aria-label={t("tf.row.mode")}>
          {choice(
            keepSpeaker,
            source === "link" ? t("tf.mode.keep.link") : mode === "talking_head" ? t("tf.mode.keep.talking") : t("tf.mode.keep.video"),
            source === "link" ? t("tf.mode.keep.link.about") : mode === "talking_head" ? t("tf.mode.keep.talking.about") : t("tf.mode.keep.video.about"),
            () => setKeepSpeaker(true),
            <UserSquare size={22} />
          )}
          {choice(!keepSpeaker, t("tf.mode.graphics"), t("tf.mode.graphics.about"), () => setKeepSpeaker(false), <Sparkles size={22} />)}
        </div>
      ),
    },
    style: {
      question: speakerStays ? t("tf.style.q.speaker") : t("tf.style.q"),
      hint: speakerStays ? t("tf.style.hint.speaker") : "Pick the visual aesthetic for your video. Each style features custom animations and scene layouts.",
      body: () => (
<><StyleChoices value={style} onChange={setStyle} onShortcut={pick=>{const letter=String.fromCharCode(65+letterHandlers.current.length);letterHandlers.current.push(pick);return letter;}}/>
        {style==="cartoon"&&<div style={{marginTop:18}}><h3 className="field-title">Character look</h3><PictureChoices label="Character look" value={cartoonTemplate} onChange={setCartoonTemplate} options={CARTOON_LOOKS.map((l)=>({...l,visual:<ElementExample kind="cartoon" look={l.value}/>}))}/><p className="small muted">Each picture is drawn by the same engine as your video. Change scenes, props and text later in the editor.</p></div>}</>
      ),
    },
    director: {
      question: "Who directs this video?",
      hint: "The director reads the whole script and decides what every moment should show.",
      body: () => (
        <DirectorChoices value={director} onChange={setDirector} directors={directors?.directors || [{id:"best",label:"Best available",available:true,note:"Uses your fallback order."}]} onShortcut={pick=>{letterHandlers.current.push(pick);}}/>
      ),
    },
    shape: {
      question: t("tf.shape.q"),
      hint: detected?.width && detected.height ? t(detected.width > detected.height ? "tf.shape.yours.wide" : "tf.shape.yours.vertical") : undefined,
      body: () => <div className="col tf-choices" role="radiogroup" aria-label="Shape">{SHAPE_CHOICES.map((c) => choice(aspect === c.value, t(c.title), t(c.about), () => setAspect(c.value), <span className={`tf-shape s${c.value.replace(":", "-")}`} />))}</div>,
    },
    look: {
      question: t("tf.look.q"),
      hint: t("tf.look.hint"),
      body: () => (
        <div className="tf-themes" role="radiogroup" aria-label="Look">
          <button type="button" role="radio" aria-checked={theme === "auto"} className={`theme-item ${theme === "auto" ? "sel" : ""}`} onClick={() => setTheme("auto")}>
            <span className="swatches">{["#f26a1f", "#35e0ff", "#12a36b", "#7c4dff"].map((c, i) => <i key={i} style={{ background: c }} />)}</span>
            <span style={{ fontWeight: 600 }}>{t("tf.look.auto")}</span>
          </button>
          {(themes || []).filter((th) => !th.name.startsWith("auto-")).map((th) => (
            <button key={th.name} type="button" role="radio" aria-checked={theme === th.name} className={`theme-item ${theme === th.name ? "sel" : ""}`} onClick={() => setTheme(th.name)}>
              <span className="swatches">{[th.color.bg, th.color.accent, th.color.accent2, th.color.ink].map((c, i) => <i key={i} style={{ background: c }} />)}</span>
              <span style={{ fontWeight: 600 }}>{th.label || th.name}</span>
            </button>
          ))}
        </div>
      ),
    },
    sound: {
      question: t("tf.sound.q"),
      hint: t("tf.sound.hint"),
      body: () => (
        <div className="col" style={{ gap: 18 }}>
          <div className="col tf-choices" role="radiogroup" aria-label={t("tf.row.music")}>
            {choice(musicTrack === "auto", t("tf.music.auto"), t("tf.music.auto.about"), () => setMusicTrack("auto"), <Music size={20} />)}
            {choice(musicTrack === "", t("tf.music.none"), undefined, () => setMusicTrack(""), <VolumeX size={20} />)}
          </div>
          <div className="row wrap" style={{ gap: 8 }}>
            <select value={musicTrack === "auto" || musicTrack === "" ? "" : musicTrack} onChange={(e) => setMusicTrack(e.target.value || "auto")} aria-label="A particular track">
              <option value="">{t("tf.music.pick")}</option>
              {(music || []).map((m) => <option key={m.id} value={m.id}>{m.title} · {m.mood}</option>)}
            </select>
            {musicTrack && musicTrack !== "auto" && (
              <button type="button" className="btn icon sm" aria-label="Preview track" onClick={() => toggleTrackPreview({ id: musicTrack, url: music!.find((m) => m.id === musicTrack)!.url })}>
                {previewingTrack === musicTrack ? <Square size={13} /> : <Play size={13} />}
              </button>
            )}
          </div>
          <Row label={t("tf.captions")}>
            <Seg value={captions} onChange={setCaptions} label="Caption style" options={[{ value: "auto", label: t("tf.captions.auto") }, { value: "pop", label: t("tf.captions.pop") }, { value: "theme", label: t("tf.captions.calm") }]} />
          </Row>
        </div>
      ),
    },
    voice: {
      question: t("tf.voice.q"),
      hint: chosenEngine ? `${chosenEngine.offline ? "Works offline." : "Needs internet."} ${chosenEngine.licence}` : undefined,
      body: () => (
        <Group>
          <Row label="Voice quality">
            <select value={engine} onChange={(e) => { setEngine(e.target.value); const picked = engines?.find((x) => x.id === e.target.value); if (picked && !picked.voices.some((v) => v.id === voice)) setVoiceRaw(picked.voices[0].id); }} aria-label="Voice engine">
              {(engines || []).map((e) => <option key={e.id} value={e.id} disabled={!e.available}>{e.label}{e.available ? "" : ` (${e.note})`}</option>)}
            </select>
          </Row>
          <Row label="Voice">
            <select value={voice} onChange={(e) => setVoice(e.target.value)} aria-label="Voice">{(chosenEngine?.voices || []).map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}</select>
          </Row>
          <Row label={`Speed ${rate.toFixed(2)}×`}><input type="range" min={0.7} max={1.4} step={0.05} value={rate} onChange={(e) => setRate(+e.target.value)} aria-label="Speaking speed" /></Row>
          <Row label="Delivery" stack><Seg value={voiceDirection} onChange={setVoiceDirection} label="Delivery" options={[{ value: "auto", label: "Directed (sighs, emphasis)" }, { value: "off", label: "Plain" }]} /></Row>
          <Row label="Hear it"><button type="button" className="btn sm" disabled={samplingVoice || !chosenEngine?.available} onClick={hearVoice}>{samplingVoice ? <Spinner /> : <Volume2 size={13} />} Play</button></Row>
        </Group>
      ),
    },
    ready: {
      question: "That’s it. Ready to create?",
      hint: "The app will direct, edit, caption, add pictures and choose music automatically.",
      body: () => (
        <div className="col" style={{ gap: 14 }}>
          <div className="tf-auto-card">
            <span className="tf-auto-icon"><Sparkles size={20} /></span>
            <span className="col grow" style={{ gap: 3 }}>
              <strong>Your video, your choices</strong>
              <span className="small muted">Review the choices below. Automatic lets the app choose for this video.</span>
            </span>
          </div>
          <Group>
            <Row label={t("tf.row.source")}><span className="tf-val">{sourceLabel}</span></Row>
            {source === "link" && <Row label="" stack><span className="small muted" data-testid="rights">Only use videos that are yours or free to reuse (for example Creative Commons). You are responsible for having the right to use what you download.</span></Row>}
            <Row label="Posting as"><span className="tf-val">{t(SHAPE_CHOICES.find((c) => c.value === aspect)!.title)}</span></Row>
            <Row label="Video name (optional)" stack><input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="The app can name it for you" className="bn" aria-label={t("tf.row.name")} /></Row>
          </Group>
          <OptionsHub c={optionsCtx()} onOpen={setDetail} />
          <button className="btn primary lg" disabled={starting || (source === "script" && !chosenEngine?.available)} onClick={start}>
            {starting ? <Spinner /> : <Sparkles size={16} />}{" "}
            {starting ? (source === "link" ? linkMessage || "Downloading…" : uploadShare > 0 && uploadShare < 1 ? `Uploading ${Math.round(uploadShare * 100)}%` : "Starting…") : "Make my video"}
          </button>
          {source === "script" && chosenEngine && !chosenEngine.available && <span className="small muted center">{chosenEngine.label} is unavailable: {chosenEngine.note}. Choose another voice provider above, or open Speech & voice in Settings.</span>}
        </div>
      ),
    },
  };
  const screen = screens[step];

  return (
    <div
      className={`page-inner tf ${dragOver ? "over" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); takeFile(e.dataTransfer.files?.[0]); setStepIndex(0); }}
    >
      <div className="tf-progress" aria-hidden><i style={{ width: `${((stepIndex + 1) / steps.length) * 100}%` }} /></div>
      <div className="tf-screen" key={step}>
        {detail ? (
          <>
            <button type="button" className="btn ghost opt-back" onClick={() => setDetail(null)}><ChevronLeft size={16} /> Back to your choices</button>
            <h1 className="tf-question">{optionDef(detail).question}</h1>
            {optionDef(detail).hint && <p className="tf-hint muted">{optionDef(detail).hint}</p>}
            <OptionPage id={detail} c={optionsCtx()} />
            <div className="row tf-nav"><span className="grow" /><button className="btn primary" onClick={() => setDetail(null)}>Done <Check size={14} /></button></div>
          </>
        ) : (<>
        <span className="tf-count small muted">{t("new.stepof").replace("{i}", String(stepIndex + 1)).replace("{n}", String(steps.length))}</span>
        <h1 className="tf-question">{screen.question}</h1>
        {screen.hint && <p className="tf-hint muted">{screen.hint}</p>}
        {screen.body()}
        {step !== "ready" && (
          <div className="row tf-nav">
            {stepIndex > 0 && <button className="btn ghost" onClick={goBack}><ChevronLeft size={16} /> {t("tf.back")}</button>}
            <span className="grow" />
            <button className="btn primary" disabled={!canContinue} onClick={goNext}>{t("tf.ok")} <CornerDownLeft size={14} /></button>
          </div>
        )}
        {step === "ready" && <button className="btn ghost" style={{ alignSelf: "flex-start" }} onClick={goBack}><ChevronLeft size={16} /> Change where it will be posted</button>}
        </>)}
      </div>

      <audio ref={musicPreview} onEnded={() => setPreviewingTrack(null)} />
      <audio ref={sampleAudio} />
      <input ref={pictureInput} type="file" multiple hidden accept="image/*,video/*,.gif" onChange={(e) => e.target.files && setPictures((list) => [...list, ...Array.from(e.target.files!)])} />
    </div>
  );
}
