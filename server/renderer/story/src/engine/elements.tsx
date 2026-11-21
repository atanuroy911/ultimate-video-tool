// ELEMENT LIBRARY. Each element is drawn around its own origin (0,0) in the 540x960 design space;
// the wrapper in SceneView applies x/y/s/rot + enter/loop/exit/move animation.
// Add a new element: write `const MyThing: R = (el, c) => <g>...</g>` and register it in ELEMENTS.
import React from 'react';
import { interpolate } from '../rt';
import { C, FPS, bn } from '../theme';
import { Person } from '../figures';
import { SPEC, SPEAK, STORE, sid, type El } from '../data';
import { sp, c01, scheduled } from './anim';
import { Window as WindowBg } from './backgrounds';

const O = C.outline;
export type Ctx = { t: number; f: number; sceneS: number; sceneE: number; k: number };
type R = (el: El, c: Ctx) => React.ReactNode;
const cl = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

// ---------- helpers ----------
const FONT: Record<string, string> = new Proxy({} as Record<string, string>, { get: (_, k: string) => ({ serif: STORE.fonts.head, hind: STORE.fonts.body, sans: STORE.fonts.body, latin: STORE.fonts.head } as Record<string, string>)[k] });
/** text with {red} highlights; '\n' line breaks */
export const RichText: React.FC<{ text: string; size?: number; color?: string; hl?: string; font?: string; anchor?: 'start' | 'middle' | 'end'; weight?: number; lh?: number }> = ({ text, size = 36, color = C.ink, hl = C.red, font = 'serif', anchor = 'middle', weight, lh = 1.3 }) => {
  const lines = String(text ?? '').split('\n');                 // a number or nothing must never stop a render (a plan once had steps 3, 6, 9)
  const y0 = -((lines.length - 1) * size * lh) / 2 + size * 0.35;
  return (
    <text textAnchor={anchor} fontFamily={FONT[font] ?? font} fontWeight={weight ?? (font === 'serif' ? 800 : 700)} fontSize={size} fill={color}>
      {lines.map((ln, i) => (
        <tspan key={i} x={0} y={y0 + i * size * lh}>
          {ln.split(/(\{[^}]+\})/).map((p, j) => p.startsWith('{') ? <tspan key={j} fill={hl}>{p.slice(1, -1)}</tspan> : <tspan key={j}>{p}</tspan>)}
        </tspan>
      ))}
    </text>
  );
};
const textW = (s: string, size: number) => Math.max(...String(s ?? '').split('\n').map((l) => l.replace(/[{}]/g, '').length)) * size * 0.55;
const local = (c: Ctx, sec: number) => (c.t - sec) * FPS;

export const mouthOpen = (who: string, t: number) => {
  const w = SPEAK[who] || [];
  if (!w.some(([a, b]) => t >= a && t <= b)) return false;
  return STORE.loud(t) > 0.2;
};

// arm presets in the person's local coords (facing right, before flip)
const ARMS: Record<string, { sit: [number[], number[]]; stand: [number[], number[]] }> = {
  rest: { sit: [[128, -126], [62, -96]], stand: [[18, -30], [10, -90]] },
  lap: { sit: [[60, -40], [50, -100]], stand: [[18, -30], [10, -90]] },
  phone: { sit: [[120, -110], [60, -90]], stand: [[110, -120], [60, -90]] },
  phoneEar: { sit: [[14, -262], [80, -180]], stand: [[14, -262], [80, -180]] },
  raise: { sit: [[120, -150], [64, -112]], stand: [[120, -150], [64, -112]] },
  wave: { sit: [[140, -300], [110, -200]], stand: [[140, -300], [110, -200]] },
  point: { sit: [[175, -175], [95, -165]], stand: [[175, -175], [95, -165]] },
  reach: { sit: [[160, -130], [85, -120]], stand: [[160, -140], [85, -125]] },
  knock: { sit: [[200, -170], [90, -130]], stand: [[200, -170], [90, -130]] },
  hug: { sit: [[150, -170], [80, -130]], stand: [[150, -170], [80, -130]] },
  headPat: { sit: [[158, -262], [70, -200]], stand: [[158, -262], [70, -200]] },
  face: { sit: [[50, -250], [80, -170]], stand: [[50, -250], [80, -170]] },
  desk: { sit: [[150, -62], [70, -90]], stand: [[150, -62], [70, -90]] },
  hold: { sit: [[80, -130], [50, -90]], stand: [[80, -130], [50, -90]] },
};
const armOf = (a: any, pose: 'sit' | 'stand'): [number[], number[]] => {
  if (!a) return ARMS.rest[pose];
  if (typeof a === 'string') return (ARMS[a] ?? ARMS.rest)[pose];
  if (a.hand) return [a.hand, a.elbow ?? [a.hand[0] / 2, (a.hand[1] - 160) / 2]];
  return (ARMS[a.arm] ?? ARMS.rest)[pose];
};
const lerp2 = (a: number[], b: number[], k: number) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k] as [number, number];

// ---------- characters ----------
const PersonEl: R = (el, c) => {
  const ch = SPEC.characters[el.char] ?? { skin: '#9A6238', ear: '#8A5530', shirt: '#6E96BB', pants: '#2A3550', hair: '#15110e' };
  const pose = (el.pose ?? 'sit') as 'sit' | 'stand';
  const sch = scheduled<{ t: number; expr?: string }>(el.exprs, c.t);
  const expr = sch?.expr ?? el.expr ?? 'neutral';
  // arm schedule with 0.45 s blending
  const arms: { t: number; arm?: string; hand?: number[]; elbow?: number[] }[] = el.arms ? [...el.arms].sort((a: any, b: any) => a.t - b.t) : [];
  let hand: [number, number], elbow: [number, number];
  const base = armOf(el.hand ? { hand: el.hand, elbow: el.elbow } : el.arm, pose);
  const idx = arms.reduce((acc, a, i) => (c.t >= a.t ? i : acc), -1);
  if (idx < 0) { hand = base[0] as any; elbow = base[1] as any; } else {
    const prev = idx === 0 ? base : armOf(arms[idx - 1], pose);
    const cur = armOf(arms[idx], pose);
    const k = c01((c.t - arms[idx].t) / 0.45);
    hand = lerp2(prev[0], cur[0], k); elbow = lerp2(prev[1], cur[1], k);
  }
  if (el.arm === 'wave' || arms[idx]?.arm === 'wave') hand = [hand[0] + Math.sin(c.f / 3) * 14, hand[1]];
  const talking = el.talk === true ? c.f % 8 < 4 : el.talk === false ? false : mouthOpen(el.char, c.t);
  const off = (el.char?.length ?? 0) * 17;
  const blink = expr === 'sleep' || expr === 'eyesClosed' ? true : expr === 'shock' ? false : (c.f + off) % 105 < 4;
  return (
    <Person x={0} y={0} s={1} pose={pose} flip={el.flip} {...(ch as any)} blink={blink} mouth={talking}
      smile={expr === 'smile' || expr === 'happy'} sad={expr === 'sad' || expr === 'cry'} angry={expr === 'angry'}
      scared={expr === 'scared' || expr === 'shock'} tear={expr === 'cry' ? ((c.f + off) % 36) / 36 : undefined}
      hand={hand} elbow={elbow} />
  );
};

const MiniFig: React.FC<{ color: string; skin?: string; flip?: boolean; hair?: string }> = ({ color, skin = '#9A6238', flip, hair = '#17120f' }) => (
  <g transform={`scale(${flip ? -1 : 1},1)`}>
    <rect x={-12} y={-12} width={10} height={50} rx={5} fill="#2A3550" />
    <rect x={2} y={-12} width={10} height={50} rx={5} fill="#2A3550" />
    <rect x={-17} y={-76} width={34} height={70} rx={17} fill={color} />
    <circle cx={0} cy={-96} r={17} fill={skin} />
    <path d="M-17 -100 Q-12 -118 4 -114 Q17 -112 17 -100 Q4 -108 -17 -100Z" fill={hair} />
    <circle cx={7} cy={-96} r={2.6} fill="#17120f" />
  </g>
);
const Mini: R = (el) => {
  const ch = el.char ? SPEC.characters[el.char] : undefined;
  return <MiniFig color={el.color ?? ch?.shirt ?? '#B5543A'} skin={el.skin ?? ch?.skin} flip={el.flip} />;
};
const Crowd: R = (el, c) => {
  const n = el.count ?? 5, gap = el.gap ?? 95, cols: string[] = el.colors ?? ['#B5543A', '#8f98a0', '#D9A93A', '#5f9d7a', '#7a5c8f', '#c97f4a'];
  const texts: string[] | undefined = el.texts;
  const at = el.at ?? c.sceneS;
  return (
    <g>
      {Array.from({ length: n }).map((_, i) => {
        const k = sp(local(c, at) - i * 3);
        const x = (i - (n - 1) / 2) * gap;
        const bob = el.laugh ? -Math.abs(Math.sin(c.f / 5 + i * 1.7)) * 9 : Math.sin(c.f / 20 + i) * 1.5;
        return (
          <g key={i} opacity={c01(k)} transform={`translate(${x},${(1 - c01(k)) * 30 + bob})`}>
            <g transform="scale(1.7)"><MiniFig color={cols[i % cols.length]} flip={el.flip ?? i % 2 === 1} skin={['#9A6238', '#A86D40', '#8A5530'][i % 3]} /></g>
            {texts && texts[i % texts.length] && (
              <g transform={`translate(4,${-250 - (i % 2) * 28}) scale(${c01(sp(local(c, at + 0.3) - i * 4))})`}>
                <BubbleShape text={texts[i % texts.length]} dark={el.dark} />
              </g>
            )}
          </g>
        );
      })}
    </g>
  );
};

// ---------- speech & thought ----------
const BubbleShape: React.FC<{ text: string; w?: number; tail?: 'l' | 'r' | 'none'; dark?: boolean; size?: number }> = ({ text, w, tail = 'l', dark, size = 22 }) => {
  const W = w ?? Math.max(54, textW(text, size) + 34);
  const fill = dark ? '#2f2a27' : '#F6EFE8';
  return (
    <g>
      <rect x={-W / 2} y={-26} width={W} height={42} rx={20} fill={fill} stroke={O} strokeWidth={2.5} />
      {tail !== 'none' && <path d={tail === 'l' ? 'M-14 14 L-24 30 L2 14Z' : 'M14 14 L24 30 L-2 14Z'} fill={fill} stroke={O} strokeWidth={2.5} strokeLinejoin="round" />}
      {tail !== 'none' && <rect x={-W / 2 + 3} y={8} width={W - 6} height={9} fill={fill} />}
      <text x={0} y={5} textAnchor="middle" fontFamily={STORE.fonts.body} fontWeight={700} fontSize={size} fill={dark ? '#F6EFE8' : C.ink}>{text}</text>
    </g>
  );
};
const Bubble: R = (el) => <BubbleShape text={el.text ?? '…'} w={el.w} tail={el.tail} dark={el.dark} size={el.size} />;
const Thought: R = (el) => {
  const w = el.w ?? 190, h = el.h ?? 150;
  return (
    <g>
      <circle cx={el.tailX ?? -w / 2 - 15} cy={h / 2 + 35} r={9} fill="#F6EFE8" stroke={O} strokeWidth={2} />
      <circle cx={(el.tailX ?? -w / 2 - 15) + 22} cy={h / 2 + 8} r={15} fill="#F6EFE8" stroke={O} strokeWidth={2} />
      <rect x={-w / 2} y={-h / 2} width={w} height={h} rx={h / 3} fill="#F6EFE8" stroke={O} strokeWidth={3} />
      {el.icon && <g transform={`translate(0,${el.text ? -18 : 0}) scale(${el.iconScale ?? 1})`}>{ICON(el.icon)}</g>}
      {el.text && <g transform={`translate(0,${el.icon ? 42 : 0})`}><RichText text={el.text} size={el.size ?? 28} /></g>}
    </g>
  );
};

// ---------- text & cards ----------
const Text: R = (el, c) => {
  let txt: string = el.text ?? '';
  if (el.typewriter) { const n = Math.floor((c.t - (el.at ?? c.sceneS)) * (el.cps ?? 14)); txt = txt.slice(0, Math.max(0, n)); }
  return <RichText text={txt} size={el.size ?? 44} color={el.color ?? C.ink} hl={el.hl ?? C.red} font={el.font ?? 'serif'} anchor={el.anchor ?? 'middle'} />;
};
const Pill: R = (el) => {
  const size = el.size ?? 26, W = el.w ?? textW(el.text ?? '', size) + 48;
  return (
    <g>
      <rect x={-W / 2} y={-size * 0.95} width={W} height={size * 1.9} rx={size} fill={el.fill ?? C.teal} stroke={O} strokeWidth={3} />
      <RichText text={el.text ?? ''} size={size} color={el.color ?? '#fff'} font={el.font ?? 'hind'} />
    </g>
  );
};
const Card: R = (el) => {
  const w = el.w ?? 300, h = el.h ?? 200;
  return (
    <g>
      <rect x={-w / 2} y={-h / 2} width={w} height={h} rx={el.r ?? 20} fill={el.fill ?? '#F6EFE8'} stroke={O} strokeWidth={3} />
      {el.title && <>
        <rect x={-w / 2} y={-h / 2} width={w} height={56} rx={el.r ?? 20} fill={el.titleFill ?? C.teal} />
        <rect x={-w / 2} y={-h / 2 + 30} width={w} height={26} fill={el.titleFill ?? C.teal} />
        <g transform={`translate(0,${-h / 2 + 28})`}><RichText text={el.title} size={26} color="#fff" font="serif" /></g>
      </>}
      {el.text && <g transform={`translate(0,${el.title ? 28 : 0})`}><RichText text={el.text} size={el.size ?? 32} color={el.color ?? C.ink} font={el.font ?? 'serif'} /></g>}
      {!el.text && Array.from({ length: el.lines ?? 0 }).map((_, i) => (
        <rect key={i} x={-w / 2 + 28} y={-h / 2 + (el.title ? 84 : 34) + i * 34} width={i % 2 ? w * 0.5 : w * 0.75} height={12} rx={6} fill="#cdbfa8" />
      ))}
    </g>
  );
};
const Quote: R = (el) => {
  const w = el.w ?? 420, h = el.h ?? 200;
  return (
    <g>
      <rect x={-w / 2} y={-h / 2} width={w} height={h} rx={24} fill={el.fill ?? C.night} />
      <text x={-w / 2 + 26} y={-h / 2 + 70} fontFamily={STORE.fonts.head} fontSize={90} fill={C.red}>“</text>
      <RichText text={el.text ?? ''} size={el.size ?? 34} color="#F6EFE8" font="serif" />
    </g>
  );
};
const Badge: R = (el) => (
  <g>
    <circle r={el.r ?? 70} fill={el.fill ?? '#E8B84A'} stroke={O} strokeWidth={4} />
    <circle r={(el.r ?? 70) * 0.78} fill="none" stroke="#fff6" strokeWidth={4} />
    <g transform="translate(0,4)"><RichText text={el.text ?? '★'} size={el.size ?? 44} color={el.color ?? C.ink} font="serif" /></g>
    {el.sub && <text y={-(el.r ?? 70) * 0.42} textAnchor="middle" fontFamily={STORE.fonts.body} fontWeight={700} fontSize={14} fill={el.color ?? C.ink}>{el.sub}</text>}
  </g>
);
const Stamp: R = (el) => {
  const size = el.size ?? 30, W = el.w ?? textW(el.text ?? '', size) + 40;
  const col = el.color ?? C.red;
  return (
    <g>
      {el.shape === 'circle' ? <circle r={W / 2} fill="none" stroke={col} strokeWidth={8} /> : <rect x={-W / 2} y={-size} width={W} height={size * 2} rx={8} fill={el.fill ?? 'none'} stroke={col} strokeWidth={5} />}
      <RichText text={el.text ?? ''} size={size} color={col} hl={col} font={el.font ?? 'serif'} />
    </g>
  );
};
const Steps: R = (el, c) => {
  const items: string[] = el.items ?? [], times: number[] = el.times ?? items.map((_, i) => (el.at ?? c.sceneS) + i * 0.8);
  const gap = el.gap ?? 150;
  return (
    <g>
      {items.map((it, i) => {
        const k = sp(local(c, times[i]));
        return (
          <g key={i} transform={`translate(0,${i * gap + (1 - c01(k)) * 40}) scale(${0.9 + 0.1 * c01(k)})`} opacity={c01(k)}>
            <rect x={-190} y={-60} width={380} height={120} rx={24} fill="#F6EFE8" stroke={O} strokeWidth={3} />
            <circle cx={-125} cy={0} r={32} fill={el.numFill ?? C.red} />
            <text x={-125} y={13} textAnchor="middle" fontFamily={STORE.fonts.head} fontWeight={800} fontSize={36} fill="#fff">{el.icons ? '' : bn(i + 1)}</text>
            {el.icons && <g transform="translate(-125,0) scale(0.5)">{ICON(el.icons[i] ?? 'check')}</g>}
            <g transform="translate(40,0)"><RichText text={it} size={el.size ?? 38} font="serif" /></g>
          </g>
        );
      })}
    </g>
  );
};
const Paper: R = (el) => (
  <g>
    <rect x={-190} y={-250} width={380} height={500} rx={8} fill={el.fill ?? '#E9D9AE'} stroke={O} strokeWidth={3} />
    <text y={-200} textAnchor="middle" fontFamily={STORE.fonts.head} fontWeight={700} fontSize={30} fill="#5a4630">{el.title ?? ''}</text>
    <text y={-162} textAnchor="middle" fontFamily={STORE.fonts.head} fontWeight={700} fontSize={22} fill="#7a6448">{el.sub ?? ''}</text>
    {Array.from({ length: el.lines ?? 6 }).map((_, i) => (
      <g key={i}><rect x={-150} y={-120 + i * 36} width={170} height={10} rx={5} fill="#c4ad82" /><rect x={70} y={-120 + i * 36} width={70} height={10} rx={5} fill="#c4ad82" /></g>
    ))}
    {el.footer && <text x={-150} y={190} fontFamily={STORE.fonts.head} fontWeight={700} fontSize={24} fill="#5a4630">{el.footer}</text>}
  </g>
);
const SmallPaper: R = (el) => (
  <g>
    <rect x={-32} y={-40} width={64} height={80} rx={4} fill={el.fill ?? '#E9D9AE'} stroke={O} strokeWidth={3} />
    {[-26, 10, 22].map((y, i) => <rect key={i} x={-22} y={y} width={i ? 30 : 44} height={5} rx={2} fill="#a08b64" />)}
  </g>
);

// ---------- data / infographics ----------
const Counter: R = (el, c) => {
  const at = el.at ?? c.sceneS, d = el.dur ?? 1.2;
  const v = interpolate(c.t, [at, at + d], [el.from ?? 0, el.to ?? 100], cl);
  const str = v.toFixed(el.decimals ?? 0);
  return <RichText text={`${el.prefix ?? ''}${el.latin ? str : bn(str)}${el.suffix ?? ''}`} size={el.size ?? 90} color={el.color ?? C.red} font="serif" />;
};
const Gauge: R = (el, c) => {
  const at = el.at ?? c.sceneS, d = el.dur ?? 2;
  const v = el.value ?? interpolate(c.t, [at, at + d], [el.from ?? 0.1, el.to ?? 0.95], cl);
  const h = el.h ?? 300;
  return (
    <g>
      <rect x={-22} y={0} width={44} height={h} rx={22} fill="#F6EFE8" stroke={O} strokeWidth={3} />
      <rect x={-15} y={h - 8 - (h - 16) * v} width={30} height={(h - 16) * v} rx={15} fill={el.color ?? C.red} />
      {el.label && <text y={-14} textAnchor="middle" fontFamily={STORE.fonts.body} fontWeight={700} fontSize={26} fill={el.labelColor ?? C.ink}>{el.label}</text>}
    </g>
  );
};
const Progress: R = (el, c) => {
  const at = el.at ?? c.sceneS, d = el.dur ?? 1.2;
  const v = el.value ?? interpolate(c.t, [at, at + d], [el.from ?? 1, el.to ?? 0.25], cl);
  const w = el.w ?? 320;
  return (
    <g>
      <rect x={-w / 2 - 30} y={-80} width={w + 60} height={150} rx={20} fill="#F6EFE8" stroke={O} strokeWidth={3} />
      <text x={-w / 2} y={-30} fontFamily={STORE.fonts.body} fontWeight={700} fontSize={26} fill={C.ink}>{el.label ?? ''}</text>
      <text x={w / 2} y={-30} textAnchor="end" fontFamily={STORE.fonts.head} fontWeight={800} fontSize={30} fill={C.red}>{bn(Math.round(v * 100))}%</text>
      <rect x={-w / 2} y={10} width={w} height={26} rx={13} fill="#d9cbb2" />
      <rect x={-w / 2} y={10} width={w * v} height={26} rx={13} fill={el.color ?? C.teal} />
    </g>
  );
};
const Bars: R = (el, c) => {
  const vals: number[] = el.values ?? [3, 5, 2], labels: string[] = el.labels ?? [];
  const max = el.max ?? Math.max(...vals), bw = el.bw ?? 70, gap = el.gap ?? 40, H = el.h ?? 280;
  const at = el.at ?? c.sceneS;
  const W = vals.length * bw + (vals.length - 1) * gap;
  return (
    <g>
      <path d={`M${-W / 2 - 20} 0 H${W / 2 + 20}`} stroke={O} strokeWidth={4} />
      {vals.map((v, i) => {
        const k = c01(sp(local(c, at) - i * 5));
        const h = (v / max) * H * k;
        const x = -W / 2 + i * (bw + gap);
        return (
          <g key={i}>
            <rect x={x} y={-h} width={bw} height={h} rx={8} fill={(el.colors ?? [C.teal, C.red, '#D9A93A', C.navy])[i % 4]} stroke={O} strokeWidth={3} />
            <text x={x + bw / 2} y={-h - 12} textAnchor="middle" fontFamily={STORE.fonts.head} fontWeight={800} fontSize={24} fill={C.ink} opacity={k}>{bn(v)}</text>
            {labels[i] && <text x={x + bw / 2} y={34} textAnchor="middle" fontFamily={STORE.fonts.body} fontWeight={700} fontSize={22} fill={C.ink}>{labels[i]}</text>}
          </g>
        );
      })}
    </g>
  );
};
const Calendar: R = (el, c) => {
  const n = el.count ?? 3, at = el.at ?? c.sceneS, iv = el.interval ?? 0.5, cols = el.cols ?? 6;
  return (
    <g>
      {Array.from({ length: n }).map((_, i) => {
        const k = sp(local(c, at + i * iv));
        const x = (i % cols) * 70, y = Math.floor(i / cols) * 74;
        return (
          <g key={i} transform={`translate(${x},${y}) scale(${c01(k)})`} opacity={c01(k)}>
            <rect width={58} height={62} rx={8} fill="#F6EFE8" stroke={O} strokeWidth={2.5} />
            <rect width={58} height={18} rx={6} fill={el.color ?? C.red} />
            <text x={29} y={52} textAnchor="middle" fontFamily={STORE.fonts.head} fontWeight={800} fontSize={26} fill={C.ink}>{bn((el.start ?? 1) + i)}</text>
          </g>
        );
      })}
      {el.label && <text x={((Math.min(n, cols) - 1) * 70 + 58) / 2} y={-18} textAnchor="middle" fontFamily={STORE.fonts.head} fontWeight={800} fontSize={28} fill={el.labelColor ?? C.red}>{el.label}</text>}
    </g>
  );
};
const Clock: R = (el, c) => {
  const r = el.r ?? 120, h = el.hour ?? 10, m = el.minute ?? 0;
  const spin = el.spin ? c.f * (el.spin as number) : 0;
  return (
    <g>
      <circle r={r} fill="#F6EFE8" stroke={O} strokeWidth={r / 20} />
      {Array.from({ length: 12 }).map((_, i) => <rect key={i} x={-r / 40} y={-r * 0.9} width={r / 20} height={i % 3 ? r / 12 : r / 6} fill={O} transform={`rotate(${i * 30})`} />)}
      <rect x={-r / 24} y={-r * 0.52} width={r / 12} height={r * 0.55} rx={r / 24} fill={O} transform={`rotate(${(h % 12) * 30 + m * 0.5 + spin / 12})`} />
      <rect x={-r / 34} y={-r * 0.77} width={r / 17} height={r * 0.8} rx={r / 34} fill={C.red} transform={`rotate(${m * 6 + spin})`} />
      <circle r={r / 13} fill={O} />
    </g>
  );
};
export const HeartShape: React.FC<{ color?: string; broken?: boolean }> = ({ color = C.red, broken }) => (
  <g>
    <path d="M0 30 C-60 -10 -40 -60 0 -30 C40 -60 60 -10 0 30Z" fill={color} stroke={O} strokeWidth={3} strokeLinejoin="round" />
    {broken && <path d="M0 -30 L-8 -10 L6 2 L-4 18 L0 30" stroke={O} strokeWidth={4} fill="none" />}
  </g>
);
const Heart: R = (el, c) => {
  const beats: number[] = el.beats ?? [];
  const b = beats.reduce((acc, s) => acc + (c.t > s ? Math.exp(-(c.t - s) * 7) : 0), 0);
  return <g transform={`scale(${1 + 0.35 * b})`}><HeartShape color={el.color} broken={el.broken} /></g>;
};
const Eyes: R = (el, c) => {
  const pts: number[][] = el.points ?? [[60, -100], [200, -20], [-20, 0], [-180, -60], [210, 110], [100, 60]];
  const look: number[] = el.look ?? [0, 200];
  return (
    <g>
      {pts.map(([x, y], i) => {
        const k = c01(sp(local(c, el.at ?? c.sceneS) - i * 10));
        const dx = look[0] - x, dy = look[1] - y, n = Math.hypot(dx, dy) || 1;
        return (
          <g key={i} transform={`translate(${x},${y}) scale(${k})`} opacity={k}>
            <ellipse rx={24} ry={15} fill="#F6EFE8" stroke={O} strokeWidth={3} />
            <circle cx={(dx / n) * 8} cy={(dy / n) * 5} r={7} fill={O} />
          </g>
        );
      })}
    </g>
  );
};

// ---------- icons ----------
export const ICON = (name: string): React.ReactNode => {
  switch (name) {
    case 'check': return <g><circle r={40} fill={C.teal} stroke={O} strokeWidth={4} /><path d="M-18 0 L-4 14 L20 -14" stroke="#fff" strokeWidth={10} fill="none" strokeLinecap="round" strokeLinejoin="round" /></g>;
    case 'cross': return <g><circle r={40} fill={C.red} stroke={O} strokeWidth={4} /><path d="M-16 -16 L16 16 M16 -16 L-16 16" stroke="#fff" strokeWidth={10} strokeLinecap="round" /></g>;
    case 'x': return <path d="M-26 -26 L26 26 M26 -26 L-26 26" stroke={C.red} strokeWidth={12} strokeLinecap="round" />;
    case 'question': return <g><circle r={40} fill="#D9A93A" stroke={O} strokeWidth={4} /><text y={18} textAnchor="middle" fontFamily={STORE.fonts.head} fontWeight={800} fontSize={54} fill="#fff">?</text></g>;
    case 'exclaim': return <g><circle r={40} fill={C.red} stroke={O} strokeWidth={4} /><text y={20} textAnchor="middle" fontFamily={STORE.fonts.head} fontWeight={800} fontSize={60} fill="#fff">!</text></g>;
    case 'star': return <path d="M0 -40 L11 -12 L40 -12 L17 6 L26 36 L0 18 L-26 36 L-17 6 L-40 -12 L-11 -12Z" fill="#E8B84A" stroke={O} strokeWidth={3} strokeLinejoin="round" />;
    case 'bulb': return <g><circle r={34} fill="#E8B84A" stroke={O} strokeWidth={3} /><rect x={-14} y={30} width={28} height={18} rx={4} fill="#8d8d8d" stroke={O} strokeWidth={2} />{[0, 1, 2, 3, 4].map((i) => <path key={i} d="M0 -46 V-60" stroke={C.red} strokeWidth={4} strokeLinecap="round" transform={`rotate(${-60 + i * 30})`} />)}</g>;
    case 'heart': return <g transform="scale(0.9)"><HeartShape /></g>;
    case 'lock': return <g><rect x={-30} y={-6} width={60} height={46} rx={8} fill="#D9A93A" stroke={O} strokeWidth={3} /><path d="M-18 -6 V-22 a18 18 0 0 1 36 0 V-6" stroke={O} strokeWidth={7} fill="none" /></g>;
    case 'bell': return <g><path d="M-30 20 Q-30 -36 0 -36 Q30 -36 30 20 Z" fill="#E8B84A" stroke={O} strokeWidth={3} /><circle cy={28} r={8} fill={O} /></g>;
    case 'money': return <g><rect x={-44} y={-26} width={88} height={52} rx={8} fill="#7FB07A" stroke={O} strokeWidth={3} /><circle r={14} fill="#F6EFE8" stroke={O} strokeWidth={2} /><text y={7} textAnchor="middle" fontFamily={STORE.fonts.body} fontWeight={800} fontSize={18} fill={O}>{STORE.lang === 'bn' ? '৳' : '$'}</text></g>;
    case 'book': return <g><rect x={-40} y={-30} width={80} height={60} rx={4} fill={C.red} stroke={O} strokeWidth={3} /><path d="M0 -30 V30" stroke={O} strokeWidth={3} /></g>;
    case 'home': return <g><path d="M-40 0 L0 -36 L40 0" fill="none" stroke={O} strokeWidth={6} strokeLinejoin="round" /><rect x={-28} y={0} width={56} height={40} fill="#C9B48A" stroke={O} strokeWidth={3} /></g>;
    case 'warning': return <g><path d="M0 -40 L42 34 H-42Z" fill="#E8B84A" stroke={O} strokeWidth={4} strokeLinejoin="round" /><text y={26} textAnchor="middle" fontFamily={STORE.fonts.head} fontWeight={800} fontSize={44} fill={O}>!</text></g>;
    case 'fire': return <path d="M0 40 C-36 40 -40 4 -18 -14 C-16 0 -6 4 -6 4 C-10 -18 4 -34 10 -42 C14 -20 40 -6 30 20 C26 34 14 40 0 40Z" fill="#E07A2F" stroke={O} strokeWidth={3} />;
    case 'zzz': return <text textAnchor="middle" fontFamily={STORE.fonts.body} fontWeight={800} fontSize={40} fill={C.navy}>Z z z</text>;
    case 'trophy': return <g><path d="M-30 -36 H30 V-6 Q30 22 0 22 Q-30 22 -30 -6Z" fill="#E8B84A" stroke={O} strokeWidth={3} /><rect x={-6} y={22} width={12} height={14} fill="#E8B84A" /><rect x={-22} y={34} width={44} height={10} rx={3} fill="#6B4A32" /></g>;
    case 'mail': return <g><rect x={-40} y={-26} width={80} height={52} rx={6} fill="#F6EFE8" stroke={O} strokeWidth={3} /><path d="M-40 -26 L0 6 L40 -26" fill="none" stroke={O} strokeWidth={3} /></g>;
    case 'music': return <g><path d="M-10 24 V-30 L26 -38 V16" stroke={O} strokeWidth={6} fill="none" /><circle cx={-18} cy={26} r={10} fill={O} /><circle cx={18} cy={18} r={10} fill={O} /></g>;
    case 'server': return <g><rect x={-30} y={-36} width={60} height={72} rx={8} fill="#8f98a0" stroke={O} strokeWidth={3} /><path d="M-18 -16 H18 M-18 0 H18 M-18 16 H18" stroke="#fff" strokeWidth={4} /></g>;
    default: return <text textAnchor="middle" y={14} fontFamily={STORE.fonts.body} fontSize={44}>{name}</text>;
  }
};
const Icon: R = (el) => ICON(el.name ?? 'star');

// ---------- devices & props ----------
const PhoneScreen: React.FC<{ el: El; c: Ctx; W: number; H: number }> = ({ el, c, W, H }) => {
  const lines: { text: string; at?: number; color?: string; size?: number }[] = el.lines ?? [];
  const typing = el.typing as { text: string; at: number; cps?: number; label?: string } | undefined;
  return (
    <g>
      {el.header && <><rect width={W} height={56} fill={el.headerFill ?? C.teal} rx={4} /><text x={W / 2} y={37} textAnchor="middle" fontFamily={STORE.fonts.body} fontWeight={700} fontSize={22} fill="#fff">{el.header}</text></>}
      {lines.map((l, i) => c.t >= (l.at ?? 0) && (
        <text key={i} x={W / 2} y={110 + i * 46} textAnchor="middle" fontFamily={STORE.fonts.body} fontWeight={700} fontSize={l.size ?? 26} fill={l.color ?? (el.dark ? '#cbd5e1' : C.ink)} opacity={c01(local(c, l.at ?? 0) / 6)}>{l.text}</text>
      ))}
      {typing && <>
        {typing.label && <text x={20} y={H * 0.5 - 14} fontFamily={STORE.fonts.body} fontWeight={700} fontSize={18} fill="#6f6252">{typing.label}</text>}
        <rect x={18} y={H * 0.5} width={W - 36} height={52} rx={10} fill="#fff" stroke={O} strokeWidth={2.5} />
        <text x={32} y={H * 0.5 + 36} fontFamily={STORE.fonts.body} fontWeight={700} fontSize={26} letterSpacing={4} fill={C.ink}>
          {typing.text.slice(0, Math.max(0, Math.floor((c.t - typing.at) * (typing.cps ?? 4))))}{c.f % 20 < 10 ? '|' : ''}
        </text>
      </>}
      {el.big && c.t >= (el.bigAt ?? 0) && (() => {
        const k = c01(sp(local(c, el.bigAt ?? 0), { damping: 9, stiffness: 200, mass: 0.8 }));
        return <g transform={`translate(${W / 2},${H * 0.62}) scale(${k})`} opacity={k}><RichText text={el.big} size={el.bigSize ?? 80} color={el.bigColor ?? C.red} font="serif" /></g>;
      })()}
      {el.loading && c.t >= el.loading[0] && c.t < el.loading[1] && [0, 1, 2].map((i) => (
        <circle key={i} cx={W / 2 - 30 + i * 30} cy={H * 0.55} r={8} fill="#9ca3af" opacity={Math.floor(c.f / 6) % 3 === i ? 1 : 0.3} />
      ))}
      {el.icon && c.t >= (el.iconAt ?? 0) && <g transform={`translate(${W / 2},${H * 0.6}) scale(${c01(sp(local(c, el.iconAt ?? 0)))})`}>{ICON(el.icon)}</g>}
    </g>
  );
};
const Phone: R = (el, c) => {
  if (!el.big && !el.header && !el.lines && !el.typing) {
    return (
      <g>
        {el.glow !== false && <circle r={34} fill="#bfe3ff" opacity={0.35} />}
        <rect x={-13} y={-22} width={26} height={44} rx={5} fill="#1f1f24" stroke={O} strokeWidth={2} />
        <rect x={-9} y={-17} width={18} height={32} rx={2} fill="#9fd0f2" />
      </g>
    );
  }
  const W = 232, H = 400, dark = el.dark;
  return (
    <g transform="translate(-130,-240)">
      <rect width={260} height={480} rx={36} fill={dark ? '#2e2e36' : '#1f1f24'} stroke={dark ? '#5a5a66' : O} strokeWidth={4} />
      <rect x={14} y={40} width={W} height={H} rx={16} fill={dark ? '#111827' : '#F4F1EA'} />
      <rect x={100} y={16} width={60} height={10} rx={5} fill="#3a3a44" />
      <g transform="translate(14,40)"><PhoneScreen el={el} c={c} W={W} H={H} /></g>
      {el.hands !== false && <>
        <circle cx={60} cy={500} r={34} fill={el.skin ?? '#A0663A'} stroke={O} strokeWidth={3} />
        <circle cx={200} cy={500} r={34} fill={el.skin ?? '#A0663A'} stroke={O} strokeWidth={3} />
      </>}
    </g>
  );
};
const Monitor: R = (el) => (
  <g>
    <rect x={-65} y={-46} width={130} height={92} rx={6} fill="#2b2f3f" stroke={O} strokeWidth={3} />
    <rect x={-57} y={-38} width={114} height={76} fill={el.screen ?? '#9fd0f2'} />
    {el.text && <g transform="translate(0,2)"><RichText text={el.text} size={el.size ?? 28} color={el.color ?? C.red} /></g>}
    <rect x={-10} y={46} width={20} height={12} fill="#2b2f3f" />
    <rect x={-30} y={56} width={60} height={6} rx={3} fill="#2b2f3f" />
  </g>
);
const Door: R = (el, c) => {
  let open = el.open ?? 0;
  if (el.closeAt !== undefined) open = interpolate(c.t, [el.closeAt, el.closeAt + 0.5], [1, 0], cl);
  if (el.openAt !== undefined) open = interpolate(c.t, [el.openAt, el.openAt + 0.6], [0, 1], cl);
  const slam = el.closeAt !== undefined && c.t > el.closeAt + 0.5 ? Math.exp(-(c.t - el.closeAt - 0.5) * 5) : 0;
  return (
    <g transform={`translate(${Math.sin(c.f * 2) * 4 * slam},0)`}>
      <rect x={-68} y={-348} width={136} height={348} fill="#5a3d28" />
      <rect x={-60} y={-340} width={120} height={340} fill="#2b2420" />
      <rect x={-60} y={-340} width={120 * (1 - open) + 14 * open} height={340} fill={el.color ?? '#8a5a3a'} stroke={O} strokeWidth={3} />
      {open < 0.6 && <circle cx={-60 + 120 * (1 - open) - 18} cy={-160} r={7} fill="#E8B84A" stroke={O} strokeWidth={2} />}
      {slam > 0.05 && [0, 1, 2].map((i) => <path key={i} d={`M${80 + i * 10} ${-300 + i * 60} l${30 + slam * 20} ${-10 + i * 10}`} stroke={C.ink} strokeWidth={5} strokeLinecap="round" opacity={slam} />)}
    </g>
  );
};
// furniture / scenery: origin = floor contact point (bottom-centre)
const Bed: R = (el) => { const w = el.w ?? 260; return (
  <g><rect x={-w / 2} y={-95} width={w} height={70} rx={10} fill={el.color ?? '#E8DCC4'} stroke={O} strokeWidth={3} />
    <rect x={-w / 2} y={-30} width={w} height={22} fill="#6B4A32" stroke={O} strokeWidth={3} />
    <rect x={-w / 2 - 6} y={-180} width={20} height={175} rx={6} fill="#6B4A32" stroke={O} strokeWidth={3} /></g>); };
const Sofa: R = (el) => { const w = el.w ?? 330, cc = el.color ?? '#8c6a4f'; return (
  <g><rect x={-w / 2} y={-175} width={w} height={130} rx={30} fill={cc} stroke={O} strokeWidth={3} />
    <rect x={-w / 2 + 10} y={-60} width={w - 20} height={60} rx={14} fill={cc} stroke={O} strokeWidth={3} /></g>); };
const Desk: R = (el) => { const w = el.w ?? 330; return (
  <g><rect x={-w / 2} y={-154} width={w} height={14} rx={5} fill="#6B4A32" stroke={O} strokeWidth={3} />
    <rect x={-w / 2 + 7} y={-140} width={14} height={140} fill="#5a3d28" /><rect x={w / 2 - 21} y={-140} width={14} height={140} fill="#5a3d28" /></g>); };
const Chair: R = () => (<g><rect x={-40} y={-120} width={80} height={14} rx={4} fill="#6B4A32" stroke={O} strokeWidth={3} /><rect x={30} y={-220} width={12} height={110} fill="#6B4A32" /><rect x={-36} y={-106} width={10} height={106} fill="#5a3d28" /><rect x={26} y={-106} width={10} height={106} fill="#5a3d28" /></g>);
const Lamp: R = (el, c) => (<g><circle cx={30} cy={-150} r={90} fill="#ffd98a" opacity={0.25 + 0.05 * Math.sin(c.f / 10)} /><rect x={-23} y={-12} width={46} height={12} rx={5} fill="#3b2a20" /><path d="M0 -12 L-13 -80 L27 -108" stroke="#3b2a20" strokeWidth={7} fill="none" strokeLinecap="round" /><path d="M12 -116 L52 -108 L37 -82 Z" fill="#E8B84A" stroke={O} strokeWidth={3} /></g>);
const Books: R = () => (<g>{([['#C8451E', 0], ['#2C483B', -14], ['#D9A93A', -28]] as [string, number][]).map(([cc, y], i) => <rect key={i} x={-45 + i * 4} y={y - 14} width={90} height={14} rx={3} fill={cc} stroke={O} strokeWidth={2.5} />)}</g>);
const Cup: R = (el, c) => (<g><rect x={-17} y={-50} width={34} height={50} rx={5} fill="#fbf6ee" stroke={O} strokeWidth={3} /><rect x={-17} y={-38} width={34} height={9} fill={el.color ?? '#D4601F'} />
  {el.steam !== false && <path d="M0 -58 q-6 -12 0 -22 q6 -10 0 -22" stroke="#fff" strokeWidth={3} fill="none" opacity={0.35 + 0.3 * Math.sin(c.f / 9)} transform={`translate(0,${-(c.f % 26) * 0.5})`} />}</g>);
const Bag: R = () => (<g><rect x={-26} y={-40} width={52} height={40} rx={6} fill="#3b2a20" stroke={O} strokeWidth={2.5} /><path d="M-12 -40 V-50 H12 V-40" stroke={O} strokeWidth={4} fill="none" /></g>);
const Plant: R = (el, c) => (<g><path d="M-26 0 L-20 -50 H20 L26 0Z" fill="#B5543A" stroke={O} strokeWidth={3} /><g transform={`rotate(${Math.sin(c.f / 25) * 3})`}>{[-30, 0, 30].map((r, i) => <ellipse key={i} cx={0} cy={-90} rx={14} ry={40} fill="#5f9d7a" stroke={O} strokeWidth={2.5} transform={`rotate(${r} 0 -50)`} />)}</g></g>);
const Tree: R = (el, c) => (<g transform={`rotate(${Math.sin(c.f / 30) * 1.5})`}><rect x={-12} y={-130} width={24} height={130} fill="#6B4A32" /><circle cy={-180} r={80} fill={el.color ?? '#5f9d7a'} stroke={O} strokeWidth={3} /></g>);
const House: R = (el) => (<g><rect x={-120} y={-200} width={240} height={200} fill={el.color ?? '#C9B48A'} stroke={O} strokeWidth={3} /><path d="M-140 -196 L0 -290 L140 -196Z" fill="#8f3b2a" stroke={O} strokeWidth={3} /><rect x={-30} y={-110} width={60} height={110} fill="#6B4A32" stroke={O} strokeWidth={3} /><rect x={-100} y={-170} width={50} height={46} fill={el.lit ? '#ffd98a' : '#bcd6e0'} stroke={O} strokeWidth={3} /><rect x={50} y={-170} width={50} height={46} fill={el.lit ? '#ffd98a' : '#bcd6e0'} stroke={O} strokeWidth={3} /></g>);
const Car: R = (el, c) => (<g><path d="M-110 -40 L-80 -90 H60 L100 -40 H120 V-10 H-120 V-40Z" fill={el.color ?? C.red} stroke={O} strokeWidth={3} strokeLinejoin="round" /><rect x={-66} y={-82} width={56} height={36} fill="#bcd6e0" /><rect x={0} y={-82} width={50} height={36} fill="#bcd6e0" />{[-70, 70].map((x) => <g key={x} transform={`translate(${x},-6) rotate(${c.f * (el.wheelSpin ?? 0)})`}><circle r={22} fill="#222" stroke={O} strokeWidth={3} /><path d="M-12 0 H12" stroke="#888" strokeWidth={4} /></g>)}</g>);
const WindowEl: R = (el, c) => <g transform="translate(-75,-60)"><WindowBg x={0} y={0} time={el.time ?? 'day'} sky={el.sky} f={c.f} /></g>;

// ---------- effects ----------
const Particles: R = (el, c) => {
  const kind = el.kind ?? 'stars', n = el.count ?? 20;
  return (
    <g>
      {Array.from({ length: n }).map((_, i) => {
        const x = ((i * 137) % 540) - 270, yb = (i * 211) % 700;
        if (kind === 'rain') { const y = (yb + c.f * 14) % 800 - 400; return <path key={i} d={`M${x} ${y} l-6 22`} stroke="#9fc3e8" strokeWidth={2.5} opacity={0.6} />; }
        if (kind === 'snow') { const y = (yb + c.f * 2) % 800 - 400; return <circle key={i} cx={x + Math.sin(c.f / 20 + i) * 10} cy={y} r={3 + (i % 3)} fill="#fff" opacity={0.8} />; }
        if (kind === 'hearts') { const y = 300 - ((c.f * 2 + i * 40) % 600); return <g key={i} transform={`translate(${x},${y}) scale(0.3)`} opacity={0.7}><HeartShape color={el.color ?? '#E07A5F'} /></g>; }
        if (kind === 'confetti') { const y = (yb + c.f * 6) % 800 - 400; return <rect key={i} x={x} y={y} width={8} height={14} fill={[C.red, C.teal, '#E8B84A', C.navy][i % 4]} transform={`rotate(${c.f * 6 + i * 40} ${x} ${y})`} />; }
        if (kind === 'sparkle') { const o = Math.abs(Math.sin(c.f / 8 + i)); return <path key={i} d={`M${x} ${yb - 350} l4 10 l10 4 l-10 4 l-4 10 l-4 -10 l-10 -4 l10 -4Z`} fill="#ffe7a3" opacity={o} />; }
        return <circle key={i} cx={x} cy={yb - 350} r={2 + (i % 3)} fill={el.color ?? '#fff'} opacity={0.3 + 0.6 * Math.abs(Math.sin(c.f / 12 + i))} />;
      })}
    </g>
  );
};
const Overlay: R = (el) => <rect x={-1000} y={-1000} width={3000} height={3000} fill={el.color ?? '#000'} opacity={el.alpha ?? 0.3} />;
const Ecg: R = (el, c) => <path d={`M-230 0 H-100 L-75 -40 L-50 50 L-25 -80 L0 0 H230`} stroke={el.color ?? '#F6EFE8'} strokeWidth={5} fill="none" strokeLinejoin="round" opacity={0.8} strokeDasharray={700} strokeDashoffset={700 - Math.min(700, (c.t - (el.at ?? c.sceneS)) * FPS * 18)} />;
const Arrow: R = (el, c) => {
  const dx = el.dx ?? 0, dy = el.dy ?? 100, k = c01((c.t - (el.at ?? c.sceneS)) * 2.5);
  const ex = dx * k, ey = dy * k, a = Math.atan2(dy, dx);
  return (
    <g stroke={el.color ?? C.ink} strokeWidth={el.w ?? 8} strokeLinecap="round" strokeLinejoin="round" fill="none">
      <path d={el.curve ? `M0 0 Q${dx / 2 + el.curve} ${dy / 2} ${ex} ${ey}` : `M0 0 L${ex} ${ey}`} />
      {k > 0.9 && <path d={`M${ex - 24 * Math.cos(a - 0.5)} ${ey - 24 * Math.sin(a - 0.5)} L${ex} ${ey} L${ex - 24 * Math.cos(a + 0.5)} ${ey - 24 * Math.sin(a + 0.5)}`} />}
    </g>
  );
};
const Lines: R = (el, c) => (<g stroke={el.color ?? C.ink} strokeWidth={5} strokeLinecap="round">{[0, 1, 2, 3, 4, 5, 6, 7].map((i) => {
  const a = (i / 8) * Math.PI * 2, r1 = 60 + Math.sin(c.f / 3 + i) * 6, r2 = r1 + 30;
  return <path key={i} d={`M${Math.cos(a) * r1} ${Math.sin(a) * r1} L${Math.cos(a) * r2} ${Math.sin(a) * r2}`} />;
})}</g>);
const Spotlight: R = (el) => (<g><defs><radialGradient id={sid("spot")}><stop offset="0" stopColor={el.color ?? '#ffd98a'} stopOpacity="0.55" /><stop offset="1" stopColor={el.color ?? '#ffd98a'} stopOpacity="0" /></radialGradient></defs><circle r={el.r ?? 220} fill={`url(#${sid("spot")})`} /></g>);
const Shape: R = (el) => {
  const p = { fill: el.fill ?? 'none', stroke: el.stroke ?? O, strokeWidth: el.strokeWidth ?? 3 };
  switch (el.shape) {
    case 'rect': return <rect x={-(el.w ?? 100) / 2} y={-(el.h ?? 60) / 2} width={el.w ?? 100} height={el.h ?? 60} rx={el.rx ?? 8} {...p} />;
    case 'circle': return <circle r={el.r ?? 40} {...p} />;
    case 'ellipse': return <ellipse rx={el.rx ?? 60} ry={el.ry ?? 20} {...p} />;
    case 'line': return <path d={`M0 0 L${el.dx ?? 100} ${el.dy ?? 0}`} {...p} />;
    default: return <path d={el.d ?? 'M0 0'} {...p} />;
  }
};
const Image: R = (el) => <image href={`${el.src}`} x={-(el.w ?? 200) / 2} y={-(el.h ?? 200) / 2} width={el.w ?? 200} height={el.h ?? 200} />;
const Group: R = (el, c) => <g>{(el.children ?? []).map((ch: El, i: number) => <ElementView key={i} el={ch} c={c} />)}</g>;

export const ELEMENTS: Record<string, R> = {
  person: PersonEl, mini: Mini, crowd: Crowd,
  bubble: Bubble, thought: Thought,
  text: Text, title: Text, pill: Pill, card: Card, quote: Quote, badge: Badge, stamp: Stamp, steps: Steps, paper: Paper, note: SmallPaper,
  counter: Counter, gauge: Gauge, progress: Progress, bars: Bars, calendar: Calendar, clock: Clock, heart: Heart, eyes: Eyes, icon: Icon,
  phone: Phone, monitor: Monitor, door: Door, window: WindowEl, bed: Bed, sofa: Sofa, desk: Desk, chair: Chair, lamp: Lamp, books: Books,
  cup: Cup, bag: Bag, plant: Plant, tree: Tree, house: House, car: Car,
  particles: Particles, overlay: Overlay, ecg: Ecg, arrow: Arrow, lines: Lines, spotlight: Spotlight, shape: Shape, image: Image, group: Group,
};

// imported lazily to avoid a cycle
import { animState } from './anim';
export const ElementView: React.FC<{ el: El; c: Ctx }> = ({ el, c }) => {
  const R0 = ELEMENTS[el.type];
  if (!R0) return null;
  const loopDefault = el.type === 'person' && el.loop === undefined ? { ...el, loop: 'breathe' as const } : el;
  const a = animState(loopDefault, c.t, c.f, c.sceneS, c.sceneE);
  if (!a.visible) return null;
  return <g data-story-type={el.type} transform={a.transform} opacity={a.opacity}>{R0(el, { ...c, k: a.k })}</g>;
};
