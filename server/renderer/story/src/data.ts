// What the engine reads besides the scene itself. Set once per draw by the runtime (vt-story entry) or by the Studio stage.
export type Character = {
  name?: string; skin: string; ear?: string; shirt: string; pants: string; hair: string;
  bun?: boolean; orna?: string; lungi?: string; glasses?: boolean; mustache?: string; long?: boolean;
};
export type Anim = {
  at?: number; until?: number;
  enter?: 'none' | 'pop' | 'fade' | 'slideL' | 'slideR' | 'slideUp' | 'slideDown' | 'drop' | 'stamp' | 'grow';
  exit?: 'none' | 'fade' | 'pop';
  loop?: 'none' | 'breathe' | 'bob' | 'float' | 'shake' | 'pulse' | 'spin' | 'sway' | 'glow' | 'walk';
  loopAmp?: number;
  move?: { t: number; x?: number; y?: number; s?: number; rot?: number; opacity?: number }[];
};
export type El = Anim & { type: string; id?: string; x?: number; y?: number; s?: number; rot?: number; opacity?: number; z?: number; [k: string]: any };
export type Bg = { type: string; [k: string]: any };
export type Scene = { s: number; e: number; bg?: Bg; push?: number; elements: El[]; tag?: string };

/** Mutable on purpose: the renderer and the Studio set it before drawing (every draw is synchronous). */
export const SPEC: { characters: Record<string, Character> } = { characters: {} };
export const SPEAK: Record<string, [number, number][]> = {};
export const STORE = {
  lang: 'en',
  loud: (_t: number) => 0,                           // voice loudness 0-1 at a video second (drives the mouths)
  fonts: { head: 'serif', body: 'sans-serif' },     // the engine's 'NSB' (display) and 'Hind' (body)
  stage: { x0: 0, w: 540, y0: 0, h: 960 },                         // the design stage: 540 wide for 9:16, wider (x0 < 0) for 16:9 and 1:1
  uid: 's',                                         // prefix for SVG ids so that scenes on one page never share a gradient
};
export const setSpeak = (sp: Record<string, [number, number][]>) => { for (const k of Object.keys(SPEAK)) delete SPEAK[k]; Object.assign(SPEAK, sp || {}); };
export const sid = (name: string) => `${STORE.uid}-${name}`;
export const RMS: number[] = [];
