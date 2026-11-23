// W11.1: double-clicking the narration on the New timeline opens the word under the pointer in the caption inspector (the Classic word lane did).
//   VT_URL=http://localhost:5174 VT_PROJECT=<project> node e2e/timeline-words.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";
const b = await chromium.launch({ executablePath: chromePath() });
const p = await (await b.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();
const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
await p.addInitScript(() => { try { localStorage.setItem("vt-timeline", "new"); } catch {} });
await p.goto(`${base}/p/${process.env.VT_PROJECT || "c6-shot"}`, { waitUntil: "load" });
await p.waitForSelector('[data-testid="occ-timeline"]', { timeout: 45000 });
await p.waitForTimeout(2500);
const voice = p.locator('[data-item-id="voice"]').first();
await voice.scrollIntoViewIfNeeded();
const box = await voice.boundingBox();
await p.mouse.dblclick(box.x + box.width * 0.3, box.y + box.height / 2);
await p.waitForTimeout(1000);
const ok = await p.getByText("Selected caption").isVisible().catch(() => false);
const word = await p.getByLabel("Caption text").inputValue().catch(() => "");
console.log(`${ok && word ? "ok  " : "FAIL"} double-clicking the narration opens that word's caption  ${word}`);
// the captions track: words readable at any zoom, and double-clicking one opens it too
await p.keyboard.press("Escape").catch(() => {});
const cue = p.locator(".cc-caption-track-cue").nth(1);
const cb = await cue.boundingBox();
const blocks = await p.locator(".cc-caption-track-cue").evaluateAll((els) => els.map((e) => { const r = e.getBoundingClientRect(); return [r.left, r.right]; }));
const overlap = blocks.some((b, i) => i && b[0] < blocks[i - 1][1] - 1);
console.log(`${!overlap ? "ok  " : "FAIL"} caption blocks never overlap at this zoom  ${blocks.length} blocks`);
await p.mouse.dblclick(cb.x + cb.width * 0.5, cb.y + cb.height / 2);
await p.waitForTimeout(1000);
const word2 = await p.getByLabel("Caption text").inputValue().catch(() => "");
console.log(`${word2 ? "ok  " : "FAIL"} double-clicking a caption on the timeline opens that word  ${word2}`);
console.log(`${errs.length ? "FAIL" : "ok  "} no page errors`);
await b.close();
process.exit(ok && word && word2 && !overlap && !errs.length ? 0 : 1);
