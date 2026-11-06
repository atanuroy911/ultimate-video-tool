// The server's own desktop window (server/desktop/server-manager.html) and its graphics card entry (PLAN-PERFECT K5).
// The window's bridge to the program (window.serverManager) is stood in for by a script, so this needs neither Electron nor a server:
//   cd client/studio && node e2e/server_manager.mjs [out dir]
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const page_url = pathToFileURL(path.resolve(here, "../../../server/desktop/server-manager.html")).href;
const out = process.argv[2] || "e2e/out/server-manager";
fs.mkdirSync(out, { recursive: true });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };

const RUNNING = { running: true, name: "GPU-SERVER", addresses: ["http://192.168.1.10:8790"], url: "http://127.0.0.1:8790", computer: "GPU-SERVER", operation: "", error: "", progress: {}, autostart: false, tray: true };
const STATES = {
  one: { ...RUNNING, gpu: { cards: 1, needs_choice: false, allowed: ["NVIDIA GeForce RTX 3060"] }, askGpu: false },
  asking: { ...RUNNING, gpu: { cards: 2, needs_choice: true, allowed: ["NVIDIA GeForce RTX 3060"] }, askGpu: true },
  waiting: { ...RUNNING, gpu: { cards: 2, needs_choice: true, allowed: ["NVIDIA GeForce RTX 3060"] }, askGpu: false },
  answered: { ...RUNNING, gpu: { cards: 2, needs_choice: false, allowed: ["NVIDIA GeForce RTX 3060"] }, askGpu: false },
  older: { ...RUNNING, gpu: null, askGpu: false },
  stopped: { running: false, addresses: [], computer: "GPU-SERVER", operation: "", error: "", progress: {}, autostart: false, tray: true, gpu: null, askGpu: false },
};

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const errors = [];
async function open(state, keepAsking = false, width = 850, height = 820) {
  const ctx = await browser.newContext({ viewport: { width, height } });
  await ctx.route("http://127.0.0.1:8790/**", (r) => r.fulfill({ contentType: "text/html", body: "<!doctype html><title>settings</title><p>Server settings</p>" }));
  await ctx.addInitScript(([s, keep]) => {
    window.__acts = [];
    window.__state = s;
    window.serverManager = {
      state: async () => JSON.parse(JSON.stringify(window.__state)),
      act: async (a) => {
        window.__acts.push(a);
        if (a === "engine-settings") return { url: "http://127.0.0.1:8790/manage?embedded=1" };
        if (a === "gpu-settings") { if (!keep) window.__state.askGpu = false; return { url: "http://127.0.0.1:8790/manage?embedded=1#cards" }; }
        return { ok: true };
      },
      onProgress: (cb) => { window.__progress = cb; },
    };
  }, [state, keepAsking]);
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(page_url);
  await page.waitForFunction(() => document.getElementById("status")?.textContent !== "Checking…");
  return { ctx, page };
}

console.log("The Graphics cards entry");
{
  const { ctx, page } = await open(STATES.one);
  check("with one card there is nothing to choose: no entry", await page.locator("#gpu-card").isHidden());
  await ctx.close();
}
{
  const { ctx, page } = await open(STATES.older);
  check("a server that cannot say anything about cards shows no entry", await page.locator("#gpu-card").isHidden());
  await ctx.close();
}
{
  const { ctx, page } = await open(STATES.stopped);
  check("a stopped server shows no entry", await page.locator("#gpu-card").isHidden());
  await ctx.close();
}
{
  const { ctx, page } = await open(STATES.answered);
  check("answered: it says which cards Video Tool may use", /Video Tool may use: NVIDIA GeForce RTX 3060\./.test(await page.locator("#gpu-text").innerText()));
  await ctx.close();
}
{
  const { ctx, page } = await open(STATES.waiting);
  const text = await page.locator("#gpu-text").innerText();
  check("two cards and nobody has chosen: it says so and that one card is used meanwhile", /Nobody has chosen which graphics cards Video Tool may use\. Until you do, it uses one card only\./.test(text));
  check("it offers 'Choose graphics cards' and does not open anything by itself", await page.locator("#gpu-choose").isVisible() && !(await page.evaluate(() => window.__acts)).includes("gpu-settings"));
  await page.screenshot({ path: path.join(out, "manager-overview.png"), fullPage: true });
  await page.locator("#gpu-choose").click();
  await page.waitForFunction(() => !document.getElementById("engine-screen").hidden);
  check("choosing it asks for the settings at the Graphics cards tab", (await page.evaluate(() => window.__acts)).includes("gpu-settings") && /\/manage\?embedded=1#cards$/.test(await page.locator("#engine-frame").getAttribute("src")));
  await page.waitForTimeout(4700);                                                        // the window refreshes itself every 4 seconds
  check("the window's own refresh does not reload the settings page and lose the tab", /#cards$/.test(await page.locator("#engine-frame").getAttribute("src")));
  await page.locator("#engine-back").click();
  check("and Back returns to the overview", await page.locator("#overview").isVisible());
  await page.evaluate(() => window.__progress({ gpu: true }));
  await page.waitForFunction(() => window.__acts.filter((a) => a === "gpu-settings").length === 2);
  check("the tray's 'Graphics cards' item opens it too", true);
  await ctx.close();
}
{
  const { ctx, page } = await open(STATES.asking, true);                                 // even if the program kept asking (it could not write its note), the window opens it once
  await page.waitForFunction(() => window.__acts.includes("gpu-settings"));
  await page.waitForTimeout(4700);
  const acts = await page.evaluate(() => window.__acts.filter((a) => a === "gpu-settings").length);
  check("the first time it is shown, the question opens by itself, once", acts === 1, String(acts));
  await ctx.close();
}
check("no page errors", errors.length === 0, errors.join(" | ").slice(0, 300));
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
