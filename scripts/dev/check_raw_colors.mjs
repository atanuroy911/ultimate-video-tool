// Finds raw colour values (#rgb, #rrggbb, rgb(), hsl()) in the Studio's chrome: everything under client/studio/src except client/studio/src/tokens.css and the files
// listed in EXEMPT, which draw the VIDEO (looks, palettes, caption presets, the story preview) rather than the app.
//   node scripts/dev/check_raw_colors.mjs            list the counts per file; exit 1 when a non-exempt file has any (failing mode)
//   node scripts/dev/check_raw_colors.mjs --report   every hit as file:line:value with the nearest token, never fails
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const src = path.join(repo, "client", "studio", "src");
const report = process.argv.includes("--report");

// Content colours: the colours of the video, not of the app. Each entry says why.
const EXEMPT = [
  ["src/tokens.css", "the one place for the app's colours"],
  ["src/occ/", "ported timeline code (AGPL, OpenChatCut): its own skin registry; mapped to the tokens in occ.css"],
  ["src/pages/DesignStudio.tsx", "palette and look editor: the colours are the video's"],
  ["src/pages/Themes.tsx", "the video themes' swatches"],
  ["src/pages/StyleThumbnails.tsx", "thumbnails of the video styles"],
  ["src/review/story/", "the story (cartoon) preview draws the video"],
  ["src/review/CaptionLook.tsx", "caption look presets are the video's colours"],
  ["src/review/ElementExample.tsx", "examples of video elements"],
  ["src/review/VisualControls.tsx", "colour pickers for video elements"],
  ["src/review/LayerInspector.tsx", "colour fields for video elements"],
  ["src/components/ColorField.tsx", "colour pickers"],
];
const exempt = (rel) => EXEMPT.some(([p]) => rel.includes(p));

const RAW = /#[0-9a-fA-F]{3,8}\b|\brgba?\(\s*\d|\bhsla?\(/g;
const files = [];
(function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p); else if (/\.(tsx?|css)$/.test(e.name)) files.push(p);
  }
})(src);

// the nearest token by colour distance, for --report
const tokens = {};
for (const m of fs.readFileSync(path.join(src, "tokens.css"), "utf8").split("\r").join("").matchAll(/(--[\w-]+)\s*:\s*(#[0-9a-f]{6})\s*;/gi)) tokens[m[1]] = m[2];
const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const near = (hex) => {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) return "";
  const c = rgb(hex);
  return Object.entries(tokens).map(([n, v]) => [n, rgb(v).reduce((s, x, i) => s + (x - c[i]) ** 2, 0)]).sort((a, b) => a[1] - b[1])[0]?.[0] ?? "";
};

let total = 0, exemptTotal = 0;
const perFile = [];
for (const file of files) {
  const rel = path.relative(path.join(repo, "client", "studio"), file).split(path.sep).join("/");
  const lines = fs.readFileSync(file, "utf8").split("\n");
  let n = 0;
  lines.forEach((line, i) => {
    const code = line.replace(/\/\*.*?\*\//g, "").replace(/\/\/.*$/, (m) => (line.includes("://") ? m : ""));
    for (const m of code.matchAll(RAW)) {
      if (/^#[0-9a-f]{3,8}$/i.test(m[0]) && /&#|href=|id=|#\//.test(code.slice(Math.max(0, m.index - 3), m.index + 1))) continue;   // an HTML entity or an anchor
      n++;
      if (report && !exempt(rel)) console.log(`${rel}:${i + 1}: ${m[0]}${near(m[0]) ? "  ->  var(" + near(m[0]) + ")" : ""}`);
    }
  });
  if (n) perFile.push([rel, n, exempt(rel)]);
  if (exempt(rel)) exemptTotal += n; else total += n;
}
if (!report) {
  for (const [rel, n, ex] of perFile.sort((a, b) => b[1] - a[1])) if (!ex) console.log(String(n).padStart(4), rel);
}
// A ratchet: the count may go down (then lower `baseline` in raw-colors-baseline.json) but never up. The aim is 0.
const baselineFile = path.join(path.dirname(fileURLToPath(import.meta.url)), "raw-colors-baseline.json");
const baseline = JSON.parse(fs.readFileSync(baselineFile, "utf8")).max;
console.log(`${total} raw colours in the app's chrome (${exemptTotal} more in exempt files that draw the video). Allowed: ${baseline}.`);
if (!report && total > baseline) console.log("More raw colours than the baseline: use a token from tokens.css (see the comment at its top), or add the file to EXEMPT with a reason if it draws the video.");
if (!report && total < baseline) console.log(`Fewer than the baseline: set "max" in scripts/dev/raw-colors-baseline.json to ${total}.`);
process.exit(!report && total > baseline ? 1 : 0);
