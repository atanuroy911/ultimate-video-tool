// Abnormal paths: double submits, reload while a job runs, invalid and missing inputs, server errors and network loss, settings that must persist.
// Creates a few throw-away projects (deleted at the end). Run against a scratch server with VT_DATA pointing at a scratch folder.
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });
const pid = process.env.VT_PROJECT || "reference";
const browser = await chromium.launch({ executablePath: chromePath() });
const ctx = await browser.newContext({ viewport: { width: 1500, height: 950 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const api = async (p, opts) => { const r = await fetch(base + p, opts); let j = null; try { j = await r.json(); } catch {} return { status: r.status, j }; };
const made = [];

console.log("Edge cases");

// (the inputs on the New page are tested in new_flow.mjs)

// the same project: asking to run twice returns the running job
// a project that is running, to start again while it runs (made through the API: the New page is covered by new_flow.mjs)
const mk = await api("/api/projects/from-script", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "edge run", script: "Hello. This is a very short test about saving money.", language: "en", engine: "kokoro", voice: "af_heart", start: true }) });
const np = mk.j?.project;
if (np) made.push(np.id);
if (np) {                                                                 // reload while it is processing: the progress page is still there, no second job
  await page.goto(`${base}/p/${np.id}/progress`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(800);
  const jobsBefore = (await api("/api/jobs")).j.length;
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1200);
  const jobsAfter = (await api("/api/jobs")).j.length;
  check("reloading did not start another job", jobsAfter === jobsBefore, `${jobsBefore} -> ${jobsAfter}`);
  check("after a reload the progress screen is still showing", /\/progress/.test(page.url()), page.url());
}
if (np) {
  const a = await api(`/api/projects/${np.id}/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  const b = await api(`/api/projects/${np.id}/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  check("starting the pipeline again while it runs is refused or returns the same job", (a.status === 409 && b.status === 409) || (a.j?.id && a.j.id === b.j?.id), JSON.stringify([a.status, b.status, a.j, b.j]));
}

// ---- export twice: the second is refused clearly
const e1 = await api(`/api/projects/${pid}/export`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ aspects: ["9:16"], quality: "draft", music: "none", gpu: true }) });
const e2 = await api(`/api/projects/${pid}/export`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ aspects: ["9:16"], quality: "draft", music: "none", gpu: true }) });
check("a second export while one runs is refused with 409 and a reason", e1.status === 200 && e2.status === 409 && /already running/.test(JSON.stringify(e2.j)), JSON.stringify([e1.status, e2.status, e2.j]));
for (let i = 0; i < 120; i++) { const j = await api(`/api/jobs/${e1.j.id}`); if (j.j.status !== "running" && j.j.status !== "queued") break; await new Promise((r) => setTimeout(r, 1500)); }

// ---- network loss and server errors in the UI
await page.goto(base + `/p/${pid}`, { waitUntil: "networkidle" });
await page.route("**/api/projects/*/scenes/*", (r) => r.abort());
await page.getByRole("button", { name: "Big picture" }).click().catch(() => {});
await page.waitForTimeout(900);
check("a lost connection while editing shows an error and the page keeps working", (await page.locator(".toast, [role=status]").count()) > 0 && (await page.locator(".ce").count()) === 1);
await page.unroute("**/api/projects/*/scenes/*");
await page.route("**/api/projects/*/audio", (r) => r.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) }));
await page.reload({ waitUntil: "networkidle" });
check("a failing audio endpoint does not break the editor", (await page.locator(".ce").count()) === 1 && (await page.locator(".ce-tl").count()) === 1);
await page.unroute("**/api/projects/*/audio");
await page.route("**/api/health", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) }));
await page.goto(base + "/", { waitUntil: "networkidle" });
check("a server older than the page is announced with what to do", await page.getByText(/older than the page/).isVisible());
await page.unroute("**/api/health");

// ---- settings persist across reloads and apply to a new video
await page.goto(base + "/settings", { waitUntil: "networkidle" });
await page.getByRole("group", { name: "Default shape" }).getByRole("button", { name: "16:9" }).first().click().catch(() => {});
await page.waitForTimeout(600);
const s = (await api("/api/settings")).j;
check("a changed default is saved on the server", s.default_aspect === "16:9", JSON.stringify(s.default_aspect));
await page.reload({ waitUntil: "networkidle" });
check("and is still selected after a reload", (await page.getByRole("button", { name: "16:9", pressed: true }).count()) >= 1);
await page.getByRole("group", { name: "Default shape" }).getByRole("button", { name: "9:16" }).first().click().catch(() => {});
await page.waitForTimeout(600);

for (const id of made) await api(`/api/projects/${id}`, { method: "DELETE" });
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
