/* The shapes of vt/direction/plan_doc.py as the page sees them. */
export type Medium = "made" | "repeat" | "card";
export interface WordRef { id: string; text: string; stress: number }
export interface Moment {
  id: string; start: number; end: number; sentence_ids: string[]; text: string; words: WordRef[];
  beat: { word_id: string; time: number; kind: string; strength: number; why: string };
  medium: Medium; alternatives: { medium: Medium; why: string }[]; draw: string; why: string; card: string; turn: boolean; locked: boolean;
  status: "planned" | "waiting" | "making" | "ready" | "replaced" | "failed"; media: string; problem: string; seconds_taken: number; preview: string;
}
export interface Idea { goal: string; audience: string; tone: string; kind: string; style: string; style_why: string; character: string; pace: "punchy" | "balanced" | "calm"; hook: string }
export interface Line { label: string; count: number; seconds: number; where: string }
export interface Plan {
  version: number; rev: number; state: "draft" | "approved" | "running" | "done" | "declined"; source: string; idea: Idea; moments: Moment[];
  budget: { n_generated: number | null }; estimate: { lines: Line[]; total_seconds: number; made: number; gpu_seconds: number }; notes: string[]; still_seconds: number;
}
export interface PlanView {
  plan: Plan | null; checks: string[]; project_status: string; title: string; speech: Record<string, string>;
  review: { setting: string; project: string; wanted: boolean }; changes?: string[]; said?: string;
}
export const MEDIUM: Record<Medium, { label: string; short: string; about: string }> = {
  made: { label: "Made for you", short: "Made for you", about: "A new picture is drawn for this moment." },
  repeat: { label: "Same picture again", short: "Same picture", about: "Keeps the picture before it, moved a little. No drawing time." },
  card: { label: "Word card", short: "Word card", about: "The key word on a plain card. No drawing time." },
};
export const STYLES: { value: string; label: string }[] = [
  { value: "cartoon", label: "Clean cartoon" }, { value: "line-art", label: "Pencil line art" }, { value: "comic", label: "Inked comic" }, { value: "photo", label: "Cinematic photo" },
];
export const fmt = (s: number) => (s < 60 ? `${Math.round(s)} s` : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`);
export const range = (m: Moment) => `${m.start.toFixed(1)}–${m.end.toFixed(1)} s`;
