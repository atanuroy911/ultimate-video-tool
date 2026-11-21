export type Aspect = "9:16" | "1:1" | "16:9";
export type VideoStyle = "auto" | "explainer" | "infographic" | "stick" | "cartoon" | "story" | "emoji" | "mixed" | "reel";

export interface Options {
  recording_edit?: "auto" | "subtitles" | "screen";
  remove_fillers: boolean;
  asr_model: string;
  music: string | null;
  music_volume: number;
  review_script?: boolean;
  duck?: boolean;
  duck_amount?: number;
  duck_release?: number;
  target_lufs?: number;
  music_fade_in?: number;
  music_fade_out?: number;
  sfx: boolean;
  sfx_level: "off" | "subtle" | "normal" | "rich";
  script_policy: "mixed" | "bangla";
  speakers?: "auto" | "off";
  caption_style?: string;
  look?: "classic" | "reel";
  end_card?: string;
  glossary: Record<string, string>;
}

export interface JobInfo {
  id: string;
  kind: string;
  project: string | null;
  label: string;
  status: "queued" | "running" | "done" | "error" | "cancelled";
  stage: string;
  frac: number;
  msg: string;
  result: any;
  error: string;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
  interrupted?: boolean;
}

export interface ProjectSummary {
  canvas?: {width:number;height:number};
  id: string;
  title: string;
  language: string;
  aspect: Aspect;
  theme: string;
  pace: "calm" | "normal" | "fast";
  options: Options;
  created_at: string;
  status: string;
  stages: Record<string, any>;
  director?: { who: string; requested: string; at: string; fallback_reason?: string };
  source?: "recording" | "script";
  usecase?: string;
  video_kind?: string;
  source_mode?: "talking_head" | "video" | "audio";
  updated_at?: string;
  export_count: number;
  last_export?: string | null;
  last_export_url?: string | null;
  cover_url?: string | null;
  usecase_used?: { requested: string; used: string; profile: string } | null;
  media?: MediaItem[];
  has_transcript: boolean;
  scene_count: number;
  planner: string | null;
  duration: number | null;
  pending_requests: number;
  audio_url: string | null;
  thumb: string | null;
  plan_notice: { at: string; planner: string; message: string } | null;
  ai_notice?: { at: string; message: string } | null;
  ai_brief?: { topic?: string; summary?: string; characters?: string[]; place?: string } | null;
  active_job: JobInfo | null;
  needs_reprocess_from?: string | null;
}

export interface Word {
  caption_start?: number | null;
  caption_end?: number | null;
  id: string;
  text: string;
  start: number;
  end: number;
  conf: number;
  lang: "bn" | "en" | "other";
  flag: "review" | null;
  cut: boolean;
}
export interface Beat {
  id: string;
  word_ids: string[];
  start: number;
  end: number;
  text: string;
}
export interface TranscriptData {
  transcript: { language: string; words: Word[] };
  beats: { beats: Beat[] };
  glossary: Record<string, string>;
}

export type El = { type: string; at_word: string; id?: string; keyframes?: MotionPoint[]; [k: string]: any };
export interface Scene {
  start?: number | null;
  id: string;
  beats: string[];
  layout: "stack" | "split" | "hero" | "grid" | "side" | "lower" | "upper";
  archetype?: string | null;
  role?: string | null;
  tone?: number;
  backdrop?: { media: string; motion: string; scrim: { ink: string; kind: string; strength: number; ratio: number } } | null;
  transition_in: string;
  transition_effect?: string;
  camera_move?: string;
  elements: El[];
  caption: { highlight_words: string[]; y?: number | null };
  stick?: { cast?: StickCast[]; actions?: StickAction[] } | null;
  shot?: string | null;   // a code-native shot drawn full-frame behind the scene (server/vt/shots.py)
}
export interface StickCast { id: string; name?: string; role?: string; kind?: "person" | "toon" | "emoji"; emoji?: string | null; art?: string | null; style?: { color?: string; head?: string; accessory?: string; height?: string; hair?: string; shirt?: string | null; skin?: string | null } }
export interface StickAction {
  who: string;
  do: string;
  at_word: string;
  start: number;
  end: number;
  bubble?: string;
  target?: string;
  emotion?: string;
  from?: "left" | "right";
  to?: number;
  to_side?: "left" | "right";
  side?: "left" | "right";
  prop?: string;
  count?: number;
  mark?: string;
}
export interface Plan {
  theme: string;
  planner: "rules" | "llm" | "claude" | "assistant" | "manual";
  scenes: Scene[];
}
export interface SceneTime {
  id: string;
  start: number;
  end: number;
}
export interface ScenesResponse {
  plan: Plan | null;
  elements?: Record<string, {start:number; end:number}>;
  timing: { scenes: SceneTime[]; duration: number };
}

export interface ComponentSpec {
  variant?: string;
  type: string;
  name?: string;
  category?: string;
  starter?: El;
  description: string;
  use_when: string;
  fields: Record<string, any>;
  defs: Record<string, any>;
  required: string[];
  example: El;
}
export interface Catalogue {
  templates?: ComponentSpec[];
  motion?: {entrances:{id:string;name:string}[];transitions:{id:string;name:string}[];cameras:{id:string;name:string}[]};
  elements: ComponentSpec[];
  layouts: Record<string, string>;
  transitions: string[];
  icons: string[];
  stages: { key: string; label: string }[];
}

export interface PlanRequest {
  id: string;
  project: string;
  kind: "full" | "scene";
  scene_id: string | null;
  hint: string;
  alternatives: number;
  status: "queued" | "done" | "failed";
  created_at: string;
  alternatives_available: number;
}

export interface Theme {
  name: string;
  label: string;
  color: Record<string, string>;
  font: { headline: string[]; body: string[]; numeral?: string[]; caption?: string[]; headline_weight: number };
  shape: { radius: number; stroke: number; shadow: { x: number; y: number; color: string; blur?: number }; card_tilt: number };
  background: { kind: "paper" | "flat" | "gradient" | "grid" | "dots" | "stripes" | "checks" | "waves" | "rings" | "mesh" | "aurora"; grain: number; arcs: boolean; pattern?: number; animated?: boolean };
  motion: { preset: "snappy" | "smooth" | "bouncy" };
  caption: {
    style: "box" | "pill" | "underline" | "none";
    reveal: "line" | "words";
    weight: number;
    size: number;
    words_per_line: number;
    safe_bottom: { portrait: number; landscape: number };
  };
  currency: string;
  sfx: string;
  style?: string;
  palette?: string;
}

export interface MusicTrack {
  id: string;
  title: string;
  mood: string;
  bpm: number | null;
  url: string;
  file: string;
}

export interface McpStatus {
  last_seen: string | null;
  last_tool: string | null;
  seconds_ago: number | null;
  connected: boolean;
  pending: number;
  add_command: string;
    codex_connected: boolean;
    codex_seconds_ago: number | null;
    codex_add_command: string;
  say: string;
}

export interface RetentionMoment { t0: number; t1: number; kind: string; severity: number; message: string }
export interface RetentionSummary { risk: number; score: number; verdict: string; worst: RetentionMoment[]; hook_s: number; longest_gap_s: number; empty_longest_s: number; targets: { hook_s: number; gap_s: number; empty_s: number }; note: string }
export interface ExportFile {
  acceleration?: {gpu_requested: boolean; selected_device?: {name:string; uuid:string}|null; warnings:string[]; browser_probe?:string} | null;
  acceleration_url?: string | null;
  retention?: RetentionSummary | null;
  name: string;
  size: number;
  url: string;
  srt: string | null;
  credits?: string;          // what the licences of the media and music ask for (vt/credits.py); '' when all is the person's own
  modified: string;
  path: string;
}

export interface Settings {
  default_theme: string;
  default_aspect: Aspect;
  default_pace: string;
  default_music: string | null;
  autopilot?: boolean;
  plan_review?: "when_expensive" | "always" | "never";
  llm_mode?: "auto" | "off";
  ollama_url?: string;
  ollama_model?: string;
  director_order?: string[];
  director_model?: string;
  director_wait_seconds?: number | "wait";
}

export interface DoctorRow {
  name: string;
  ok: boolean;
  detail: string;
  fix: string;
}
export interface ModelInfo {
  key: string;
  hf: string;
  note: string;
  installed: boolean;
}

export interface MediaItem {
  id: string;
  file: string;
  url: string;
  kind: "image" | "video" | "gif" | "audio";
  audio_file?: string;
  role?: "asset" | "a_roll" | "b_roll";
  caption: string;
  tags: string[];
  width: number;
  height: number;
  duration: number;
  fx?: number;                  // where the main subject is, as fractions of the picture (0 = left, 0 = top)
  fy?: number;
  source: string;
  credit: string;
  licence: string;
}

export interface UseCase {
  id: string;
  label: string;
  about: string;
}

/** Layers: extra tracks of text, pictures, video clips and sounds (vt/layers.py). Tracks are listed top layer first. */
export interface LTrack { id: string; name: string; kind: "visual" | "audio"; hidden: boolean; muted: boolean; locked: boolean }
export interface LClip {
  scale?: number; rotation?: number; transform?: import("./review/transformMath").Transform | null;
  keyframes?: MotionPoint[];
  id: string; track: string; type: "text" | "media" | "audio"; start: number; dur: number; fade_in: number; fade_out: number;
  media?: string; in?: number; text?: string; anim?: string; x?: number; y?: number; w?: number; h?: number | null; opacity?: number; fit?: "cover" | "contain"; volume?: number;
  style?: { size: number; color: string; bg: string | null; weight: number; align: "left" | "center" | "right" };
}
export interface LDoc { v: 1; tracks: LTrack[]; clips: LClip[] }
export interface MotionPoint {time:number;x:number;y:number;scale:number;rotation:number;opacity:number;stretch_x?:number;stretch_y?:number;skew_x?:number;skew_y?:number;tilt_x?:number;tilt_y?:number;blur?:number;ease:"linear"|"smooth"|"in"|"out"|"hold"}

/** A sound that is not speech, found in the voice track (vt/sounds.py). */
export interface SoundEvent { concept: string; label: string; emoji: string; query: string; start: number; end: number; score: number }
export interface SoundEvents { events: SoundEvent[]; analyzed: boolean; available: boolean; error?: string | null; duration: number }
