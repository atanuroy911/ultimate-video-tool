// Background library. A scene's `bg` = { type, ...options }. Every bg also accepts:
//   tint: '#hex' + tintOpacity (0-1)  -> colour wash (e.g. sepia flashback)
//   dark: 0-1                         -> darken (emotional drop)
//   darkFrom/darkTo + darkAt/darkEnd  -> animated darkening (seconds, absolute)
import React from 'react';
import { interpolate } from '../rt';
import { C } from '../theme';
import { STORE, sid, type Bg } from '../data';

const O = C.outline;
const TIME_SKY: Record<string, string> = { day: '#bcd6e0', morning: '#cfe3e8', evening: '#E79A62', night: '#141a33', dark: '#0f1222' };
const WALL: Record<string, [string, string]> = {
  day: ['#E2D6BE', '#D3C7B1'], morning: ['#E6DCC6', '#D6CAB3'], evening: ['#D9B892', '#C9A47C'],
  night: ['#3b4466', '#2b3150'], dark: ['#22284A', '#1a1f3a'],
};

export const Window: React.FC<{ x: number; y: number; time?: string; sky?: string; sun?: boolean; f?: number }> = ({ x, y, time = 'day', sky, sun = true, f = 0 }) => {
  const c = sky ?? TIME_SKY[time] ?? TIME_SKY.day;
  const id = sid(`win${x}_${y}`);
  return (
    <g transform={`translate(${x},${y})`}>
      <clipPath id={id}><rect width={150} height={120} /></clipPath>
      <rect width={150} height={120} fill={c} />
      <g clipPath={`url(#${id})`}>
        {sun && (time === 'night' || time === 'dark') && <>
          <path d="M100 30 a18 18 0 1 0 14 28 a14 14 0 1 1 -14 -28Z" fill="#f3e7c0" />
          {[[30, 30], [60, 80], [20, 95], [125, 90]].map(([a, b], i) => <circle key={i} cx={a} cy={b} r={2} fill="#fff" opacity={0.5 + 0.5 * Math.sin(f / 12 + i)} />)}
        </>}
        {sun && (time === 'day' || time === 'morning') && <circle cx={115} cy={30} r={16} fill="#ffe7a3" />}
        {sun && time === 'evening' && <circle cx={70} cy={100} r={22} fill="#ffd98a" />}
      </g>
      <rect width={150} height={120} fill="none" stroke="#8d7a5c" strokeWidth={6} />
      <rect x={72} width={6} height={120} fill="#8d7a5c" />
    </g>
  );
};

const Room: React.FC<{ bg: Bg; f: number }> = ({ bg, f }) => {
  const time = bg.time ?? 'day';
  const [wall, floor] = bg.wall ? [bg.wall, bg.floor ?? '#00000022'] : WALL[time] ?? WALL.day;
  return (
    <>
      <rect x={STORE.stage.x0} width={STORE.stage.w} height={960} fill={wall} />
      <rect x={STORE.stage.x0} y={606} width={STORE.stage.w} height={354} fill={floor} />
      <rect x={STORE.stage.x0} y={602} width={STORE.stage.w} height={6} fill="#00000022" />
      {bg.window !== false && <Window x={bg.windowX ?? 40} y={150} time={time} f={f} />}
      {bg.frame && (
        <g>
          <rect x={bg.frameX ?? 300} y={150} width={140} height={100} rx={6} fill="#efe6d3" stroke="#6B4A32" strokeWidth={7} />
          <path d={`M${(bg.frameX ?? 300) + 12} 235 l40 -40 l30 25 l25 -20 l20 35Z`} fill="#9db4a0" />
        </g>
      )}
      {(time === 'night' || time === 'dark') && bg.lamp !== false && (
        <><defs><radialGradient id={sid("lampglow")}><stop offset="0" stopColor="#ffd98a" stopOpacity="0.5" /><stop offset="1" stopColor="#ffd98a" stopOpacity="0" /></radialGradient></defs>
          <circle cx={bg.lampX ?? 430} cy={430} r={230} fill={`url(#${sid("lampglow")})`} opacity={0.85 + 0.1 * Math.sin(f / 15)} /></>
      )}
    </>
  );
};

const Street: React.FC<{ bg: Bg; f: number }> = ({ bg }) => {
  const time = bg.time ?? 'day';
  const sky = TIME_SKY[time] ?? TIME_SKY.day;
  return (
    <>
      <rect x={STORE.stage.x0} width={STORE.stage.w} height={960} fill={time === 'day' ? '#cfd8dc' : sky} />
      <rect x={-20} y={300} width={170} height={330} fill="#bfa98a" />
      <rect x={400} y={260} width={180} height={370} fill="#a89478" />
      {[0, 1, 2].map((r) => [0, 1].map((c) => <rect key={`${r}${c}`} x={10 + c * 60} y={330 + r * 90} width={36} height={50} fill={time === 'night' ? '#ffd98a' : '#e9dcb8'} opacity={0.85} />))}
      {[0, 1, 2].map((r) => [0, 1].map((c) => <rect key={`b${r}${c}`} x={430 + c * 56} y={290 + r * 95} width={36} height={52} fill={time === 'night' ? '#ffd98a' : '#d7c9a6'} opacity={0.85} />))}
      <rect x={STORE.stage.x0} y={610} width={STORE.stage.w} height={350} fill="#b8a88a" />
      <rect x={STORE.stage.x0} y={606} width={STORE.stage.w} height={8} fill="#a39475" />
      <rect x={262} y={250} width={10} height={360} fill="#4a3a2e" />
      <rect x={236} y={250} width={62} height={8} fill="#4a3a2e" />
    </>
  );
};

const Exterior: React.FC<{ bg: Bg; f: number }> = ({ bg }) => {
  const time = bg.time ?? 'evening';
  const sky = TIME_SKY[time] ?? TIME_SKY.day;
  const lit = time === 'evening' || time === 'night';
  return (
    <>
      <rect x={STORE.stage.x0} width={STORE.stage.w} height={960} fill={sky} />
      {time === 'evening' && <><rect x={STORE.stage.x0} width={STORE.stage.w} height={300} fill="#B5677A" opacity={0.6} /><circle cx={90} cy={260} r={40} fill="#ffd98a" opacity={0.8} /></>}
      <rect x={210} y={230} width={330} height={390} fill={bg.wall ?? '#C9B48A'} stroke={O} strokeWidth={3} />
      <path d="M190 236 L375 130 L560 236Z" fill={bg.roof ?? '#8f3b2a'} stroke={O} strokeWidth={3} />
      <rect x={330} y={380} width={100} height={230} fill="#6B4A32" stroke={O} strokeWidth={3} />
      {[250, 460].map((x) => <rect key={x} x={x} y={290} width={60} height={60} fill={lit ? '#ffd98a' : '#bcd6e0'} stroke={O} strokeWidth={3} />)}
      <rect x={STORE.stage.x0} y={610} width={STORE.stage.w} height={350} fill="#9c8565" />
    </>
  );
};

const Office: React.FC<{ bg: Bg; f: number }> = ({ bg, f }) => (
  <>
    <rect x={STORE.stage.x0} width={STORE.stage.w} height={960} fill="#D6DCDA" />
    <rect x={STORE.stage.x0} y={606} width={STORE.stage.w} height={354} fill="#B9BFBC" />
    <rect x={40} y={150} width={160} height={110} fill={TIME_SKY[bg.time ?? 'day']} stroke="#7d8a8a" strokeWidth={6} />
    <rect x={380} y={330} width={120} height={180} fill="#c5cbc9" stroke="#7d8a8a" strokeWidth={3} />
    {[0, 1, 2].map((i) => <rect key={i} x={390} y={345 + i * 55} width={100} height={40} fill="#e3e7e5" stroke="#7d8a8a" strokeWidth={2} />)}
  </>
);

const Classroom: React.FC<{ bg: Bg; f: number }> = ({ bg }) => (
  <>
    <rect x={STORE.stage.x0} width={STORE.stage.w} height={960} fill="#E4D8BF" />
    <rect x={STORE.stage.x0} y={606} width={STORE.stage.w} height={354} fill="#C9B48A" />
    <rect x={90} y={140} width={360} height={200} rx={6} fill="#2C483B" stroke="#6B4A32" strokeWidth={10} />
    {bg.board && <text x={270} y={255} textAnchor="middle" fontFamily={STORE.fonts.body} fontWeight={700} fontSize={40} fill="#F6EFE8">{bg.board}</text>}
  </>
);

const Shop: React.FC<{ bg: Bg; f: number }> = ({ f }) => (
  <>
    <rect x={STORE.stage.x0} width={STORE.stage.w} height={960} fill="#DDCFB7" />
    <rect x={STORE.stage.x0} y={610} width={STORE.stage.w} height={350} fill="#D3C7B1" />
    <path d="M0 120 Q135 150 270 120 T540 120" stroke="#6b4a32" strokeWidth={3} fill="none" />
    {[40, 130, 220, 310, 400, 490].map((x, i) => <circle key={i} cx={x} cy={128 + (i % 2 ? 6 : 14)} r={8} fill="#ffd98a" opacity={0.7 + 0.3 * Math.sin(f / 10 + i)} />)}
    <rect x={STORE.stage.x0} y={160} width={STORE.stage.w} height={60} fill="#C8451E" opacity={0.85} />
    {[0, 1, 2, 3, 4, 5].map((i) => <rect key={i} x={i * 90} y={160} width={45} height={60} fill="#F6EFE8" opacity={0.85} />)}
  </>
);

const Park: React.FC<{ bg: Bg; f: number }> = ({ bg, f }) => (
  <>
    <rect x={STORE.stage.x0} width={STORE.stage.w} height={960} fill={TIME_SKY[bg.time ?? 'day']} />
    <circle cx={440} cy={170} r={36} fill="#ffe7a3" />
    {[[60, 520, 1], [470, 540, 1.2]].map(([x, y, s], i) => (
      <g key={i} transform={`translate(${x},${y}) scale(${s}) rotate(${Math.sin(f / 30 + i) * 1.5})`}>
        <rect x={-10} y={-20} width={20} height={110} fill="#6B4A32" />
        <circle cy={-60} r={70} fill="#5f9d7a" stroke={C.outline} strokeWidth={3} />
      </g>
    ))}
    <rect x={STORE.stage.x0} y={600} width={STORE.stage.w} height={360} fill="#8fb07a" />
    <rect x={STORE.stage.x0} y={596} width={STORE.stage.w} height={6} fill="#6f8f5c" />
  </>
);

const NightSky: React.FC<{ bg: Bg; f: number }> = ({ f }) => (
  <>
    <rect x={STORE.stage.x0} width={STORE.stage.w} height={960} fill="#141a33" />
    {Array.from({ length: Math.round(30 * STORE.stage.w / 540) }).map((_, i) => <circle key={i} cx={STORE.stage.x0 + (i * 137) % STORE.stage.w} cy={(i * 89) % 560 + 30} r={1.5 + (i % 3)} fill="#fff" opacity={0.3 + 0.6 * Math.abs(Math.sin(f / 15 + i))} />)}
    <path d="M400 150 a40 40 0 1 0 30 62 a32 32 0 1 1 -30 -62Z" fill="#f3e7c0" />
    <rect x={STORE.stage.x0} y={640} width={STORE.stage.w} height={320} fill="#0b0f1f" />
  </>
);

export const Background: React.FC<{ bg?: Bg; f: number; t: number }> = ({ bg, f, t }) => {
  const b: Bg = bg ?? { type: 'plain' };
  let body: React.ReactNode;
  switch (b.type) {
    case 'room': body = <Room bg={b} f={f} />; break;
    case 'living': body = <Room bg={{ ...b, window: false, frame: true, frameX: 200 }} f={f} />; break;
    case 'street': body = <Street bg={b} f={f} />; break;
    case 'exterior': body = <Exterior bg={b} f={f} />; break;
    case 'office': body = <Office bg={b} f={f} />; break;
    case 'classroom': body = <Classroom bg={b} f={f} />; break;
    case 'shop': body = <Shop bg={b} f={f} />; break;
    case 'park': body = <Park bg={b} f={f} />; break;
    case 'nightsky': body = <NightSky bg={b} f={f} />; break;
    case 'split': body = (<>
      <rect x={STORE.stage.x0} width={STORE.stage.w} height={960} fill={b.left ?? '#CDBFA4'} />
      <rect x={b.splitX ?? 250} width={STORE.stage.w} height={960} fill={b.right ?? '#D9CBB1'} />
      <rect x={STORE.stage.x0} y={606} width={STORE.stage.w} height={354} fill="#BFB196" />
      <rect x={(b.splitX ?? 250) - 20} y={250} width={22} height={360} fill="#6B4A32" stroke={C.outline} strokeWidth={3} />
    </>); break;
    case 'gradient': body = (<>
      <defs><linearGradient id={sid("bgg")} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={b.from ?? C.navy} /><stop offset="1" stopColor={b.to ?? C.night} /></linearGradient></defs>
      <rect x={STORE.stage.x0} width={STORE.stage.w} height={960} fill={`url(#${sid("bgg")})`} />
    </>); break;
    default: body = <rect x={STORE.stage.x0} width={STORE.stage.w} height={960} fill={b.color ?? C.cream} />;
  }
  const dark = b.darkAt !== undefined ? interpolate(t, [b.darkAt, b.darkEnd ?? b.darkAt + 1], [b.darkFrom ?? 0, b.darkTo ?? 0.4], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : b.dark ?? 0;
  return (
    <>
      {body}
      {b.glow && <circle cx={270} cy={380} r={260} fill={b.glow} opacity={0.3 + 0.05 * Math.sin(f / 12)} />}
      {b.tint && <rect x={STORE.stage.x0} width={STORE.stage.w} height={960} fill={b.tint} opacity={b.tintOpacity ?? 0.18} />}
      {dark > 0 && <rect x={STORE.stage.x0} width={STORE.stage.w} height={960} fill="#000" opacity={dark} />}
    </>
  );
};

export const BG_TYPES = ['plain', 'gradient', 'room', 'living', 'split', 'street', 'exterior', 'office', 'classroom', 'shop', 'park', 'nightsky'];
