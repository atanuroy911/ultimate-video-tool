// Small pose guides use the cartoon engine's shoulder angles; no preview request or render is needed.
const POSES: Record<string, { left: number; right: number; tilt?: number; sit?: boolean; walk?: boolean }> = {
  stand: { left: 5, right: -5 }, point: { left: 4, right: -85 }, think: { left: 4, right: -150, tilt: -5 },
  wave: { left: 4, right: -150 }, celebrate: { left: 160, right: -160 }, sad: { left: 3, right: -3, tilt: 7 },
  shrug: { left: -38, right: 38 }, walk: { left: 24, right: -24, walk: true }, sit: { left: 10, right: -10, sit: true },
  idle: { left: 8, right: -8, tilt: 3 }, run: { left: 65, right: -65, walk: true },
  laugh: { left: -25, right: 25 }, count: { left: 4, right: -145 }, confused: { left: -38, right: -150, tilt: -10 },
  ride: { left: 25, right: -45, sit: true },
};

export default function PosePicture({ pose }: { pose: string }) {
  const p = POSES[pose] ?? POSES.stand;
  return <svg viewBox="0 0 100 110" aria-hidden="true" focusable="false">
    <path d="M16 101H84" stroke="var(--border-strong)" strokeWidth="2" />
    {pose === "ride" && <g stroke="var(--accent-text)" strokeWidth="3" fill="none"><circle cx="23" cy="85" r="15" /><circle cx="79" cy="85" r="15" /><path d="M23 85L39 61L51 85L23 85M39 61H67L51 85L79 85L67 53H77" /></g>}
    <g transform={pose === "run" ? "rotate(15 50 65)" : undefined}>
    <g stroke="var(--text)" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" fill="none">
      <path d={pose === "ride" ? "M43 69L62 73L54 88M57 69L67 79L72 88" : pose === "run" ? "M44 69L24 81L34 94M56 69L71 56L81 70" : p.sit ? "M43 71L33 81H58M57 71L67 81H83" : p.walk ? "M44 69L32 97M56 69L69 94" : "M44 69L41 97M56 69L60 97"} />
      {pose === "shrug" ? <><path d="M39 40L29 51L19 40" /><path d="M61 40L71 51L81 40" /></> : pose === "laugh" ? <><path d="M39 40L28 53L45 58" /><path d="M61 40L72 53L56 58" /></> : pose === "confused" ? <><path d="M39 40L28 51L18 43" /><path d="M61 40L72 32L61 14" /></> : pose === "ride" ? <><path d="M39 40L51 51L67 51" /><path d="M61 40L70 48" /></> : <>
        <path d="M39 40L34 66" transform={`rotate(${p.left} 39 40)`} />
        {pose === "think" ? <path d="M61 40L70 44L57 31" /> : pose === "count" ? <path d="M61 40L73 33L75 22" /> : <path d="M61 40L66 66" transform={`rotate(${p.right} 61 40)`} />}
      </>}
    </g>
    <rect x="38" y="36" width="24" height="39" rx="8" fill="var(--accent)" />
    {pose === "laugh" && <path d="M28 53L45 58M72 53L56 58" fill="none" stroke="var(--text)" strokeWidth="7" strokeLinecap="round" />}
    <g transform={`rotate(${p.tilt ?? 0} 50 34)`}>
      <circle cx="50" cy="23" r="14" fill="#e0a878" />
      <path d="M37 20Q36 6 50 8Q64 7 64 20Q51 14 37 20" fill="#493026" />
      {pose === "laugh" ? <><path d="M42 23Q45 19 48 23M52 23Q55 19 58 23" fill="none" stroke="#493026" strokeWidth="1.6" /><ellipse cx="50" cy="30" rx="5" ry="4" fill="#493026" /></> : <>
        <g fill="#29252b"><circle cx="45" cy="23" r="1.4" /><circle cx="55" cy="23" r="1.4" /></g>
        <path d={pose === "sad" ? "M45 31Q50 26 55 31" : "M45 29Q50 33 55 29"} fill="none" stroke="#493026" strokeWidth="1.6" strokeLinecap="round" />
      </>}
    </g>
    </g>
    {pose === "wave" && <path d="M78 15Q84 21 80 28M85 11Q94 20 87 32" fill="none" stroke="var(--accent-text)" strokeWidth="2" strokeLinecap="round" />}
    {["think", "confused"].includes(pose) && <text x="78" y="24" fill="var(--accent-text)" fontSize="20">?</text>}
    {pose === "count" && <path d="M75 22V12M70 23V14M80 24V15" stroke="var(--text)" strokeWidth="2.5" strokeLinecap="round" />}
  </svg>;
}
