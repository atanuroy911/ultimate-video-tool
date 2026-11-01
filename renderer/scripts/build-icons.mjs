// Builds design/icons/lucide.json (name -> inner svg markup) and curated.json (names offered to the planner).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.resolve(here, "..", "node_modules", "lucide-static", "icons");
const out = path.resolve(here, "..", "..", "design", "icons");
fs.mkdirSync(out, { recursive: true });

const all = {};
for (const f of fs.readdirSync(src)) {
  if (!f.endsWith(".svg")) continue;
  const svg = fs.readFileSync(path.join(src, f), "utf8");
  const inner = svg.replace(/<!--[\s\S]*?-->/g, "").replace(/<svg[\s\S]*?>/, "").replace(/<\/svg>\s*$/, "").replace(/\s+/g, " ").trim();
  all[f.replace(/\.svg$/, "")] = inner;
}

const CURATED = `
house building-2 store warehouse landmark factory school hospital tent-tree map-pin map globe
coins banknote wallet credit-card piggy-bank receipt percent calculator badge-dollar badge-percent hand-coins circle-dollar-sign
trending-up trending-down chart-line chart-bar chart-pie chart-column scale target flag trophy award medal crown gem
user users user-round baby heart handshake smile frown thumbs-up thumbs-down
clock timer hourglass calendar calendar-days sun moon cloud
check circle-check x circle-x triangle-alert circle-alert info circle-help lightbulb key lock lock-open shield shield-check
arrow-right arrow-left arrow-up arrow-down arrow-up-right arrow-down-right refresh-cw repeat shuffle split merge
plus minus equal divide
phone smartphone laptop monitor tv camera mic headphones wifi mail message-circle send share-2 link
book book-open graduation-cap pencil file-text folder clipboard list-checks notebook
shopping-cart shopping-bag package truck plane car bus bike train ship
zap flame droplet leaf tree-pine mountain waves wind snowflake
search eye eye-off settings wrench hammer scissors paintbrush palette
play pause star bookmark bell megaphone rocket puzzle brain cpu database server
utensils coffee pizza apple wheat
`.split(/\s+/).filter(Boolean);

const curated = [...new Set(CURATED)].filter((n) => {
  const ok = n in all;
  if (!ok) console.warn("not in lucide:", n);
  return ok;
});

fs.writeFileSync(path.join(out, "lucide.json"), JSON.stringify(all));
fs.writeFileSync(path.join(out, "curated.json"), JSON.stringify(curated, null, 1));
fs.writeFileSync(path.join(out, "LICENSE.txt"), "Lucide icons (lucide-static) — ISC License, https://lucide.dev/license\n");
console.log("icons:", Object.keys(all).length, "curated:", curated.length);

// ---------------------------------------------------------------------------------------------
// Visual dictionary sources: Tabler (line icons) and Twemoji (colour stickers) next to Lucide.
// Writes tabler.json, emoji/*.svg, emoji_index.json and docs.json (one searchable text per visual).
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const nm = path.resolve(here, "..", "node_modules");

const tabler = JSON.parse(fs.readFileSync(path.join(nm, "@tabler", "icons", "icons.json"), "utf8"));
const tablerSvg = {};
for (const name of Object.keys(tabler)) {
  const f = path.join(nm, "@tabler", "icons", "icons", "outline", name + ".svg");
  if (!fs.existsSync(f)) continue;
  const svg = fs.readFileSync(f, "utf8");
  tablerSvg[name] = svg.replace(/<svg[\s\S]*?>/, "").replace(/<\/svg>\s*$/, "").replace(/<path stroke="none" d="M0 0h24v24H0z" fill="none"\s*\/>/, "").replace(/\s+/g, " ").trim();
}
fs.writeFileSync(path.join(out, "tabler.json"), JSON.stringify(tablerSvg));

const lucideTags = JSON.parse(fs.readFileSync(path.join(nm, "lucide-static", "tags.json"), "utf8"));
const en = JSON.parse(fs.readFileSync(path.join(nm, "emojibase-data", "en", "data.json"), "utf8"));
const bnData = JSON.parse(fs.readFileSync(path.join(nm, "emojibase-data", "bn", "data.json"), "utf8"));
const bnBy = new Map(bnData.map((e) => [e.hexcode, e]));
const twDir = path.join(nm, "@twemoji", "svg");
const emojiDir = path.join(out, "emoji");
fs.mkdirSync(emojiDir, { recursive: true });
const emojiIndex = {};
for (const e of en) {
  const hex = e.hexcode.toLowerCase();
  const cand = [hex, hex.replace(/-fe0f/g, "")];
  const file = cand.map((c) => path.join(twDir, c + ".svg")).find((f) => fs.existsSync(f));
  if (!file || e.group === 2 /* skin-tone modifiers/components */ || e.group === undefined) continue;
  fs.copyFileSync(file, path.join(emojiDir, hex.replace(/-fe0f/g, "") + ".svg"));
  const b = bnBy.get(e.hexcode);
  emojiIndex[hex.replace(/-fe0f/g, "")] = { emoji: e.emoji, en: e.label, en_tags: e.tags || [], bn: b ? b.label : "", bn_tags: b ? b.tags || [] : [], group: e.group };
}
fs.writeFileSync(path.join(out, "emoji_index.json"), JSON.stringify(emojiIndex));

const words = (s) => s.replace(/[-_]+/g, " ");
const docs = [];
for (const name of Object.keys(all)) docs.push({ id: "lucide:" + name, kind: "line", en: [words(name), ...(lucideTags[name] || [])].join("; "), bn: "" });
for (const [name, t] of Object.entries(tabler)) if (tablerSvg[name]) docs.push({ id: "tabler:" + name, kind: "line", en: [words(name), ...(t.tags || []), t.category || ""].filter(Boolean).join("; "), bn: "" });
for (const [hex, e] of Object.entries(emojiIndex)) docs.push({ id: "emoji:" + hex, kind: "sticker", en: [e.en, ...e.en_tags].join("; "), bn: [e.bn, ...e.bn_tags].filter(Boolean).join("; ") });
fs.writeFileSync(path.join(out, "docs.json"), JSON.stringify(docs));
fs.writeFileSync(path.join(out, "LICENSE.txt"),
  "Lucide icons (lucide-static): ISC, https://lucide.dev/license\n" +
  "Tabler Icons (@tabler/icons): MIT, https://github.com/tabler/tabler-icons\n" +
  "Twemoji artwork (@twemoji/svg, maintained fork of Twitter's Twemoji): CC-BY 4.0, https://github.com/jdecked/twemoji — attribution required\n" +
  "Emoji names, tags and Bengali annotations (emojibase-data): MIT; underlying CLDR data under the Unicode licence\n");
console.log("tabler:", Object.keys(tablerSvg).length, "emoji:", Object.keys(emojiIndex).length, "docs:", docs.length);
