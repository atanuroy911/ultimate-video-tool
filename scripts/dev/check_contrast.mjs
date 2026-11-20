// Checks the colour pairs of client/studio/src/tokens.css in both themes (WCAG contrast). Usage: node scripts/dev/check_contrast.mjs
// Fails (exit 1) when a pair is below its minimum: body text and the accent's text 4.5:1, faint text and icons 3:1, white words on every timeline clip 4.5:1.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const css = fs.readFileSync(path.join(here, "..", "..", "client", "studio", "src", "tokens.css"), "utf8").split("\r").join("");

function block(selectorStart) {
  const i = css.indexOf(selectorStart);
  if (i < 0) throw new Error("no block " + selectorStart);
  const open = css.indexOf("{", i);
  let depth = 0, j = open;
  for (; j < css.length; j++) { if (css[j] === "{") depth++; if (css[j] === "}" && --depth === 0) break; }
  return css.slice(open + 1, j);
}
function vars(text) {
  const out = {};
  for (const m of text.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}
const themes = { light: vars(block(':root,\n[data-theme="light"]')), dark: vars(block('[data-theme="dark"]')) };

function parse(value, theme, over = 0) {
  value = value.trim();
  const ref = value.match(/^var\((--[\w-]+)\)$/);
  if (ref) return parse(themes[theme][ref[1]], theme, over);
  let m = value.match(/^#([0-9a-f]{3,8})$/i);
  if (m) { let h = m[1]; if (h.length === 3) h = [...h].map((c) => c + c).join(""); return { r: parseInt(h.slice(0, 2), 16), g: parseInt(h.slice(2, 4), 16), b: parseInt(h.slice(4, 6), 16), a: h.length === 8 ? parseInt(h.slice(6), 16) / 255 : 1 }; }
  m = value.match(/^rgb\(\s*(\d+)\s+(\d+)\s+(\d+)\s*(?:\/\s*([\d.]+))?\s*\)$/);
  if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] };
  m = value.match(/^color-mix\(in srgb,\s*(var\(--[\w-]+\)|#[0-9a-f]+)\s+(\d+)%,\s*transparent\)$/i);
  if (m) { const c = parse(m[1], theme); return { ...c, a: c.a * (+m[2] / 100) }; }
  throw new Error(`cannot read ${value} (${theme})`);
}
function over(top, bottom) { return { r: top.r * top.a + bottom.r * (1 - top.a), g: top.g * top.a + bottom.g * (1 - top.a), b: top.b * top.a + bottom.b * (1 - top.a), a: 1 }; }
function lum({ r, g, b }) { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); }
function ratio(a, b) { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); }

const get = (t, name) => parse(`var(${name})`, t);
let bad = 0, n = 0;
function pair(theme, fg, bg, min, why) {
  const base = get(theme, bg);
  const back = base.a < 1 ? over(base, get(theme, "--bg-panel")) : base;
  const front = fg.startsWith("#") ? parse(fg, theme) : get(theme, fg);
  const r = ratio(front.a < 1 ? over(front, back) : front, back);
  n++;
  if (r < min) { bad++; console.log(`FAIL ${theme}: ${fg} on ${bg} is ${r.toFixed(2)}:1, needs ${min}:1 (${why})`); }
}
for (const t of ["light", "dark"]) {
  for (const bg of ["--bg-panel", "--bg-raised", "--bg-app"]) {
    pair(t, "--text", bg, 4.5, "text");
    pair(t, "--text-muted", bg, 4.5, "secondary text");
    pair(t, "--text-faint", bg, 3, "hints and idle icons");
    pair(t, "--accent-text", bg, 4.5, "accent as small text");
    pair(t, "--ok", bg, 3, "state colour");
    pair(t, "--err", bg, 3, "state colour");
    pair(t, "--warn", bg, 3, "state colour");
  }
  pair(t, "--on-primary", "--primary", 4.5, "main button");
  pair(t, "--on-accent", "--accent", 4.5, "text on the accent");
  pair(t, "--accent", "--bg-panel", 3, "focus ring and the selected mark");
  for (const k of ["scene", "picture", "video", "element", "caption", "sticker", "narration", "music", "sfx"]) pair(t, "#ffffff", `--clip-${k}`, 4.5, "white label on a timeline clip");
}
console.log(bad ? `${bad} of ${n} pairs fail` : `all ${n} colour pairs pass`);
process.exit(bad ? 1 : 0);
