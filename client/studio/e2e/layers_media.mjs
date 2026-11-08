// Pictures and sounds from the media bin go on the timeline: Add to timeline puts them at the playhead on a track of the right kind; trimming a sound keeps its place in the file.
// Mutating (then undone): scratch server only.  VT_PROJECT=<id> node e2e/layers_media.mjs
import { chromium } from "playwright-core";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import zlib from "node:zlib";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "reference";
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "vt-lm-"));

// a 64x36 blue PNG and a 2 s 440 Hz WAV, written by hand so the test needs no files
function png(w, h, rgb) {
  const crc = (buf) => { let c, t = []; for (let n = 0; n < 256; n++) { c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } let x = 0xffffffff; for (const b of buf) x = t[(x ^ b) & 255] ^ (x >>> 8); return (x ^ 0xffffffff) >>> 0; };
  const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) { raw[y * (w * 3 + 1)] = 0; for (let x = 0; x < w; x++) raw.set(rgb, y * (w * 3 + 1) + 1 + x * 3); }
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}
function wav(seconds, hz) {
  const sr = 16000, n = sr * seconds, b = Buffer.alloc(44 + n * 2);
  b.write("RIFF", 0); b.writeUInt32LE(36 + n * 2, 4); b.write("WAVEfmt ", 8); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22); b.writeUInt32LE(sr, 24); b.writeUInt32LE(sr * 2, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write("data", 36); b.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) b.writeInt16LE(Math.round(8000 * Math.sin((2 * Math.PI * hz * i) / sr)), 44 + i * 2);
  return b;
}
fs.writeFileSync(path.join(tmp, "blue.png"), png(64, 36, [30, 120, 220]));
fs.writeFileSync(path.join(tmp, "tone.wav"), wav(2, 440));

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const api = async (p) => (await fetch(base + p)).json();
const doc = async () => (await api(`/api/projects/${pid}/layers`)).doc;
const settle = (ms = 1800) => page.waitForTimeout(ms);

console.log("Layers from the media bin");
await page.goto(`${base}/p/${pid}/pro`, { waitUntil: "networkidle" });
await page.waitForSelector(".tl-clip");
await page.getByRole("button", { name: "Add a picture, video or sound" }).click();
await page.locator('input[type=file][accept*="image"]').setInputFiles(path.join(tmp, "blue.png"));
await settle(2500);
check("the picture is in the media bin", (await api(`/api/projects/${pid}/media`)).some((m) => m.id === "blue"));
const mediaClipsBefore = await page.locator(".tl-lclip.media").count();
await page.getByRole("button", { name: "Select blue", exact: true }).click();          // a picture is selected first, then put on the timeline
await page.getByRole("button", { name: "Put blue on the timeline" }).click();
await settle();
let d = await doc();
const pic = d.clips.find((c) => c.media === "blue");
check("Add to timeline puts the picture on a picture track", !!pic && d.tracks.find((t) => t.id === pic.track)?.kind === "visual", JSON.stringify(d));
check("and shows it in the timeline", (await page.locator(".tl-lclip.media").count()) === mediaClipsBefore + 1);   // one more clip (earlier runs may have left theirs)
await page.getByRole("tab", { name: "Position", exact: true }).click();
check("the inspector offers place and opacity", await page.getByRole("slider", { name: "Opacity" }).first().isVisible());

await page.getByRole("button", { name: "Add a picture, video or sound" }).click();
await page.getByRole("button", { name: "Audio", exact: true }).click();                 // sounds have their own tab in the media bin
await page.locator('input[type=file][accept*="audio"]').setInputFiles(path.join(tmp, "tone.wav"));
await settle(3000);
check("the sound is in the bin", (await api(`/api/projects/${pid}/sounds`)).some((m) => m.id === "tone"));
await page.getByRole("button", { name: "Put tone on the timeline" }).click();
await settle();
d = await doc();
const snd = d.clips.find((c) => c.media === "tone");
check("Add to timeline puts the sound on a sound track", !!snd && d.tracks.find((t) => t.id === snd.track)?.kind === "audio");
check("below the voice, in its own lane", (await page.locator(".tl-lane.layer.audio .tl-lclip.audio").count()) === 1);
check("the sound is as long as the file (about 2 s)", snd && snd.dur > 1.8 && snd.dur < 2.3, String(snd?.dur));

// trimming the start of a sound keeps its place in the file: `in` moves with it
const c = page.locator(".tl-lclip.audio").first();
await c.scrollIntoViewIfNeeded();                    // the timeline has several lanes now: bring the sound lane into view
await page.waitForTimeout(300);
const le = await c.locator(".tl-ledge.l").boundingBox();
await page.mouse.move(le.x + 4, le.y + le.height / 2);
await page.mouse.down();
for (let i = 1; i <= 6; i++) { await page.mouse.move(le.x + 4 + i * 6, le.y + le.height / 2); await page.waitForTimeout(25); }
await page.mouse.up();
await settle();
d = await doc();
const t2 = d.clips.find((x) => x.media === "tone");
check("trimming the start moves where in the file it plays from", t2.in > 0.1 && Math.abs(t2.start + t2.dur - (snd.start + snd.dur)) < 0.02, JSON.stringify([snd.start, snd.dur, t2.start, t2.dur, t2.in]));

// the volume control
await page.getByRole("slider", { name: "Volume" }).first().fill("0.5");
await page.getByRole("slider", { name: "Volume" }).first().dispatchEvent("pointerup");
await settle();
check("volume is saved", (await doc()).clips.find((x) => x.media === "tone").volume === 0.5);

// a file used by a layer cannot be deleted from under it
const del = await fetch(`${base}/api/projects/${pid}/sounds/tone`, { method: "DELETE" });
check("a sound that is used cannot be removed", del.status === 409);

// clean up: undo everything on the layers, then remove the files
for (let i = 0; i < 20; i++) { const v = await api(`/api/projects/${pid}/layers`); if (!v.can_undo) break; await fetch(`${base}/api/projects/${pid}/layers/undo`, { method: "POST" }); }
await fetch(`${base}/api/projects/${pid}/layers`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ doc: { v: 1, tracks: [], clips: [] } }) });
await fetch(`${base}/api/projects/${pid}/sounds/tone`, { method: "DELETE" });
await fetch(`${base}/api/projects/${pid}/media/blue`, { method: "DELETE" });
await browser.close();
fs.rmSync(tmp, { recursive: true, force: true });
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
