// W11.1: the New timeline shows the cuts in the voice as marks; double-clicking one brings that cut back (the Classic cut marks did).
//   VT_URL=http://localhost:5174 VT_PROJECT=<a copy of a project> node e2e/timeline-cuts.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";
const pid = process.env.VT_PROJECT || "e2e-cuts";
let pass = 0, fail = 0;
const check = (n, ok, x = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${n}${x ? "  " + x : ""}`); };
const api = async (method, path, body) => (await fetch(base + path, { method, headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined })).json();
const before = (await api("GET", `/api/projects/${pid}/audio`)).cuts.length;
await api("POST", `/api/projects/${pid}/audio/cut`, { start: 5.0, end: 5.8 });
const made = (await api("GET", `/api/projects/${pid}/audio`)).cuts.length;
check("the project has a cut to bring back", made >= 1, `${before} -> ${made}`);
const b = await chromium.launch({ executablePath: chromePath() });
const p = await (await b.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();
const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
await p.addInitScript(() => { try { localStorage.setItem("vt-timeline", "new"); } catch {} });
await p.goto(`${base}/p/${pid}`, { waitUntil: "load" });
await p.waitForSelector('[data-testid="occ-timeline"]', { timeout: 45000 });
await p.waitForTimeout(2500);
const mark = p.locator('[data-item-id^="cut:"]').first();
check("the cut shows as a mark on the timeline", (await p.locator('[data-item-id^="cut:"]').count()) === made);
await mark.evaluate((el) => el.dispatchEvent(new MouseEvent("dblclick", { bubbles: true })));      // the mark is a few pixels wide: the real handler, without aiming
await p.waitForFunction(async ([u, n]) => (await (await fetch(u)).json()).cuts.length < n, [`/api/projects/${pid}/audio`, made], { timeout: 30000 }).catch(() => {});
const after = (await api("GET", `/api/projects/${pid}/audio`)).cuts.length;
check("double-clicking the mark brings the cut back", after === made - 1, `${made} -> ${after}`);
check("no page errors", !errs.length, errs.join(" | "));
await b.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
