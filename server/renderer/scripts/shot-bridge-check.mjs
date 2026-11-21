// Checks the visual editor's bridge the way the Studio uses it: node shot-bridge-check.mjs <chrome> <editor page index.html> <messages JSON>.
// A parent page holds the shot in a sandboxed frame with no origin (sandbox="allow-scripts"), waits for shot-ready, sends each message in turn
// ({wait:true} on a message waits for its answer) and prints {"ready": ..., "answers": [...], "failed": [...requests that left the page]} as JSON.
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import puppeteer from "puppeteer-core";

const [, , chrome, pageFile, messagesJson] = process.argv;
const messages = JSON.parse(messagesJson);
const dir = await fs.mkdtemp(path.join(os.tmpdir(), "shot-bridge-"));
const parent = path.join(dir, "parent.html");
await fs.writeFile(parent, `<!doctype html><body style="margin:0">
<iframe id="f" sandbox="allow-scripts" style="width:4000px;height:4000px;border:0" src="${pathToFileURL(pageFile).href}"></iframe>
<script>
  window.__answers = []; window.__ready = null;
  addEventListener("message", (e) => { if (e.data && e.data.vt === "shot-ready") window.__ready = e.data; else if (e.data && e.data.vt) window.__answers.push(e.data); });
</script></body>`);
const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ["--no-sandbox", "--disable-gpu", "--allow-file-access-from-files"] });
const failed = [];
try {
  const page = await browser.newPage();
  page.on("requestfailed", (r) => failed.push(r.url().slice(0, 120)));
  page.on("request", (r) => { const u = r.url(); if (!u.startsWith("file:") && !u.startsWith("data:")) failed.push(u.slice(0, 120)); });
  await page.goto(pathToFileURL(parent).href, { waitUntil: "load" });
  await page.waitForFunction(() => window.__ready, { timeout: 15000 });
  for (const m of messages) {
    const before = await page.evaluate(() => window.__answers.length);
    await page.evaluate((msg) => document.getElementById("f").contentWindow.postMessage(msg, "*"), m);
    if (m.wait) await page.waitForFunction((n) => window.__answers.length > n, { timeout: 5000 }, before);
    else await new Promise((r) => setTimeout(r, 80));
  }
  const out = await page.evaluate(() => ({ ready: window.__ready, answers: window.__answers }));
  console.log(JSON.stringify({ ...out, failed }));
} finally {
  await browser.close();
  await fs.rm(dir, { recursive: true, force: true });
}
