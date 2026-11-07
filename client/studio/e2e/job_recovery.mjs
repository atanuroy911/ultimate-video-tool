// F1: the built Studio with fake API/WebSocket responses; no engine or GPU.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const root = fileURLToPath(new URL("../dist/", import.meta.url));
const out = fileURLToPath(new URL("./out/job-recovery/", import.meta.url));
fs.mkdirSync(out, { recursive: true });
const server = createServer((req, res) => {
  const requested = path.resolve(root, "." + new URL(req.url, "http://localhost").pathname);
  if (!requested.startsWith(root)) { res.writeHead(403).end(); return; }
  const file = fs.existsSync(requested) && fs.statSync(requested).isFile() ? requested : path.join(root, "index.html");
  const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css" };
  res.setHeader("Content-Type", types[path.extname(file)] || "application/octet-stream");
  fs.createReadStream(file).pipe(res);
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
let browser;
try {
  browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
  for (const [width, theme, state] of [[1280, "light", "interrupted"], [400, "dark", "interrupted"], [1280, "light", "cancelled"], [400, "dark", "cancelled"]]) {
    const ctx = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme });
    await ctx.addInitScript(theme => localStorage.setItem("vt-theme", theme), theme);
    const errors = [], runs = [];
    const job = { id: "old-job", kind: "pipeline", project: "video", label: "Make video", status: "error", stage: "asr", frac: .4, interrupted: true,
      error: "The server stopped before this job finished. You can continue; completed stages are kept.", created_at: "2026-11-06T10:00:00Z" };
    if(state === "cancelled") Object.assign(job,{status:"cancelled",interrupted:false,error:""});
    let socket;
    await ctx.routeWebSocket("**/ws", ws => { socket = ws; ws.send(JSON.stringify({ type: "hello", jobs: [job] })); });
    await ctx.route("**/api/**", route => {
      const pathname = new URL(route.request().url()).pathname;
      if (pathname === "/api/system/stats") return route.fulfill({ status: 503, json: { detail: "No hardware in this test" } });
      let json = {};
      if (pathname === "/api/projects/video/run") {
        runs.push(route.request().postDataJSON());
        const next = { ...job, id: "new-job", status: "running", interrupted: false, error: "", stage: "context", created_at: "2026-11-06T10:01:00Z" };
        socket.send(JSON.stringify({ type: "job", job: next }));
        json = next;
      } else if (pathname === "/api/projects/video") json = { id: "video", title: "Interrupted video", status: runs.length ? "processing" : state, options: {}, media: [] };
      else if (pathname === "/api/catalogue") json = { stages: [{ key: "asr" }, { key: "context" }, { key: "plan" }, { key: "compose" }] };
      else if (pathname === "/api/settings") json = { autopilot: false };
      else if (pathname === "/api/setup") json = { done: true, server: { name: "Test" }, existing: {} };
      else if (pathname === "/api/health") json = { ok: true, api_version: 999 };
      else if (pathname === "/api/directors") json = { order: [], directors: [] };
      else if (pathname === "/api/system/gpus") json = { cards: [], needs_choice: false };
      return route.fulfill({ json });
    });
    const page = await ctx.newPage();
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(`http://127.0.0.1:${server.address().port}/p/video/progress`);
    await page.getByRole("heading", { name: state === "cancelled" ? "Making this video was stopped" : "The server stopped", exact: true }).waitFor({ timeout: 10000 }).catch(async error => {
      console.error(await page.locator("body").innerText(), errors);
      throw error;
    });
    const button = page.getByRole("button", { name: "Continue", exact: true });
    assert(await button.isVisible());
    assert.equal(await page.getByText("You can leave this page; it keeps going.", { exact: false }).count(), 0);
    await page.screenshot({ path: path.join(out, `${width}-${theme}-${state}.png`), animations: "disabled" });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await button.click();
    await page.getByRole("heading", { name: "Understanding what it is about…", exact: true }).waitFor();
    assert.deepEqual(runs, [{ from_stage: null, force: false }], "Continue keeps stage caches and runs autopilot normally");
    assert.deepEqual(errors, []);
    await ctx.close();
    console.log(`${width} ${theme}: ${state} state, Continue, cached resume, new-job selection, no page errors or overflow: PASS`);
  }
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
