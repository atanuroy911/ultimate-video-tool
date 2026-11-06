// One Cartoon 2 scene at a video second: the engine's SceneView + Stage + tag chip, drawn as one SVG that fills the frame.
// Used by the HyperFrames runtime (entry.tsx) and by the Studio's editable stage, so preview, editor and export are the same drawing.
import React from 'react';
import { FrameCtx, interpolate, spring } from './rt';
import { C, FPS, SPRING } from './theme';
import { STORE, type Scene } from './data';
import { Background } from './engine/backgrounds';
import { ElementView } from './engine/elements';

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const textW = (s: string, size: number) => s.length * size * 0.56;

export type StoryProps = {
  scene: Scene;
  t: number;                       // absolute video second
  width: number; height: number;   // pixels of the drawing
  chrome?: boolean;                // tag chip, vignette and grain (off in the editor's thumbnails)
  overlay?: React.ReactNode;       // the editor's selection handles, in design units
  onItemDown?: (index: number, e: React.PointerEvent) => void;
};

export const StoryScene: React.FC<StoryProps> = ({ scene, t, width, height, chrome = true, overlay, onItemDown }) => {
  const f = Math.max(0, (t - scene.s) * FPS);
  const dur = Math.max(1, (scene.e - scene.s) * FPS);
  const push = 1 + (scene.push ?? 0.05) * Math.min(1, f / dur);
  const fade = interpolate(f, [0, 4], [0.55, 1], clamp);
  const { x0, w, y0, h } = STORE.stage;
  const items = scene.elements.map((e, i) => ({ e, i })).sort((a, b) => (a.e.z ?? a.i) - (b.e.z ?? b.i));
  const c = { t, f, sceneS: scene.s, sceneE: scene.e, k: 1 };
  const tagK = scene.tag ? Math.min(1, spring({ frame: f - 6, fps: FPS, config: SPRING })) : 0;
  const tagW = scene.tag ? textW(scene.tag, 27) + 62 : 0;            // a wide frame puts the chip in the top-left corner, clear of titles
  return (
    <FrameCtx.Provider value={f}>
      <svg width={width} height={height} viewBox={`${x0} ${y0} ${w} ${h}`} preserveAspectRatio="xMidYMid slice" style={{ display: 'block', background: scene.bg?.color ?? C.beige }}>
        <g opacity={fade} transform={`translate(${x0 + w / 2} ${960 * 0.58}) scale(${push}) translate(${-(x0 + w / 2)} ${-960 * 0.58})`}>
          <Background bg={scene.bg} f={f} t={t} />
          {items.map(({ e, i }) => (
            <g key={i} data-item={i} onPointerDown={onItemDown ? (ev) => onItemDown(i, ev) : undefined} style={onItemDown ? { cursor: 'grab' } : undefined}>
              <ElementView el={e} c={c} />
            </g>
          ))}
        </g>
        {chrome && scene.tag && tagK > 0.01 && (
          <g transform={`translate(${h < 960 ? x0 + 36 + tagW / 2 : x0 + w / 2} ${h < 960 ? y0 + 42 : 92}) scale(${0.85 + 0.15 * tagK})`} opacity={tagK}>
            <rect x={-tagW / 2} y={-24} width={tagW} height={48} rx={24} fill="#F6EFE8" stroke={C.red} strokeWidth={3} />
            <circle cx={-tagW / 2 + 26} cy={0} r={6.5} fill={C.red} />
            <text x={13} y={9} textAnchor="middle" fontFamily={STORE.fonts.body} fontWeight={700} fontSize={27} fill={C.ink}>{scene.tag}</text>
          </g>
        )}
        {chrome && <>
          <defs><radialGradient id={`${STORE.uid}-vig`} cx="50%" cy="50%" r="75%"><stop offset="0.55" stopColor="#1e0f05" stopOpacity="0" /><stop offset="1" stopColor="#1e0f05" stopOpacity="0.22" /></radialGradient></defs>
          <rect x={x0} y={y0} width={w} height={h} fill={`url(#${STORE.uid}-vig)`} pointerEvents="none" />
        </>}
        {overlay}
      </svg>
    </FrameCtx.Provider>
  );
};

/** The design stage for a frame shape. 9:16 shows the whole 540 x 960 design. A wider frame shows the content band (y 70-770, where people, props
 *  and cards live) as large as it fits, with the backgrounds drawn wider so nothing is cut off at the sides. */
export const stageFor = (width: number, height: number) => {
  const tall = height / width > 1.5;
  const y0 = tall ? 0 : 70, h = tall ? 960 : 700;
  const w = Math.max(540, Math.round(h * width / height));
  return { x0: -(w - 540) / 2, w, y0, h };
};
