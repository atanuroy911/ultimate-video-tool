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
console.log(`${errs.length ? "FAIL" : "ok  "} no page errors`);
await b.close();
process.exit(ok && word && !errs.length ? 0 : 1);
