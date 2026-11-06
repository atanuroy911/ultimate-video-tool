// The server's own pages (the overview at / and Server settings at /manage) and the graphics card question on them (PLAN-PERFECT K5).
// The pages are served from server/vt/server by a tiny static server here; the server's answers are stood in for by this script, so no server is needed:
//   cd client/studio && node e2e/server_pages.mjs [out dir]
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const pagesDir = path.resolve(here, "../../../server/vt/server");
const out = process.argv[2] || "e2e/out/server-pages";
fs.mkdirSync(out, { recursive: true });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const clone = (x) => JSON.parse(JSON.stringify(x));

const FILES = { "/": "management.html", "/management.js": "management.js", "/gpu-choice.js": "gpu-choice.js", "/manage": "engine-management.html", "/manage.js": "engine-management.js" };
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript" };
const web = http.createServer((req, res) => {
  const file = FILES[new URL(req.url, "http://x").pathname];
  if (!file) { res.writeHead(404); res.end("no"); return; }
  res.writeHead(200, { "content-type": types[path.extname(file)] });
  res.end(fs.readFileSync(path.join(pagesDir, file)));
});
await new Promise((r) => web.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${web.address().port}`;

const V100 = { index: 0, name: "Tesla V100-PCIE-16GB", uuid: "GPU-v100", free_gb: 6.2, total_gb: 16, load: 90, allowed: false, using: [{ label: "python3", gb: 9.7, ours: false }, { label: "Ollama", gb: 1.17, ours: false }] };
const RTX = { index: 1, name: "NVIDIA GeForce RTX 3060", uuid: "GPU-3060", free_gb: 11.4, total_gb: 12, load: 3, allowed: true, using: [] };
const ENGINES = [
  { id: "ollama", label: "Ollama", source: "existing", code: "existing_blocked", offer_own: true, own_installed: true, on: [], message: "Ollama was already running on this computer before Video Tool. It is using Tesla V100-PCIE-16GB (1.17 GB), a card Video Tool is not allowed to use. Video Tool did not start it and does not change it, so it keeps asking it for work. To keep Video Tool's work off that card, use Video Tool's own copy." },
  { id: "comfy", label: "ComfyUI", source: "existing", code: "existing_blocked", offer_own: true, own_installed: false, on: [], message: "ComfyUI was already running on this computer before Video Tool. It is using Tesla V100-PCIE-16GB (6 GB), a card Video Tool is not allowed to use." },
];
const UNANSWERED = { cards: [V100, RTX], saved: {}, allowed_saved: null, needs_choice: true, restart_needed: false, jobs: {}, engines: ENGINES, pinned_by_launcher: null };
const ANSWERED = { ...clone(UNANSWERED), allowed_saved: ["GPU-3060"], needs_choice: false };
const OLD = { cards: [{ index: 0, name: V100.name, uuid: V100.uuid, free_gb: 6, total_gb: 16, load: 1, allowed: true }], saved: {}, jobs: {}, separate_programs: {} };
const SETUP = { server: { name: "GPU-SERVER" }, install_dir: "", models_dir: "", hardware: { gpus: [{ index: 0, name: V100.name, memory_gb: 16 }, { index: 1, name: RTX.name, memory_gb: 12 }] } };

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const errors = [];
async function open(width, height, data) {
  const ctx = await browser.newContext({ viewport: { width, height } });
  const seen = { puts: [], posts: [], data };
  await ctx.route("**/api/**", (r) => {
    const url = new URL(r.request().url()), method = r.request().method(), body = r.request().postData();
    if (url.pathname === "/api/system/gpus") return r.fulfill({ json: seen.data });
    if (url.pathname === "/api/system/gpu" && method === "PUT") {
      const b = JSON.parse(body || "{}"); seen.puts.push(b);
      seen.data = clone(seen.data); seen.data.cards.forEach((c) => { c.allowed = b.allowed.includes(c.uuid); }); seen.data.allowed_saved = b.allowed; seen.data.needs_choice = false;
      return r.fulfill({ json: seen.data });
    }
    if (url.pathname === "/api/system/engine-own") { seen.posts.push(JSON.parse(body || "{}")); seen.data = clone(seen.data); seen.data.engines[0] = { ...ENGINES[0], source: "own", code: "own_running", offer_own: false, message: "Video Tool's own Ollama is running on NVIDIA GeForce RTX 3060 (3 GB)." }; return r.fulfill({ json: { starting: true } }); }
    if (url.pathname === "/api/server") return r.fulfill({ json: { addresses: ["http://192.168.1.10:8790"] } });
    if (url.pathname === "/api/setup") return r.fulfill({ json: SETUP });
    if (url.pathname === "/api/engines") return r.fulfill({ json: [] });
    return r.fulfill({ status: 404, json: { detail: "not stood in for" } });
  });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  return { ctx, page, seen };
}
const noOverflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - innerWidth <= 1);

console.log("The overview at /");
{
  const { ctx, page, seen } = await open(1280, 900, UNANSWERED);
  await page.goto(`${base}/`, { waitUntil: "load" });
  await page.getByTestId("gpu-cards").waitFor();
  check("the card section is on the server's own page", /Graphics cards/.test(await page.locator("[data-gpu-choice]").innerText()));
  const v = page.getByTestId("gpu-switch-0"), r = page.getByTestId("gpu-switch-1");
  check("each card has a named switch: the V100 off, the 3060 on", (await v.getAttribute("role")) === "switch" && /Video Tool may use this card: Tesla V100/.test((await v.getAttribute("aria-label")) || "") && (await v.getAttribute("aria-checked")) === "false" && (await r.getAttribute("aria-checked")) === "true");
  check("what is using each card is said in words", /python3 is using 9\.7 GB\. Ollama is using 1\.17 GB\./.test(await page.getByTestId("gpu-card-0").innerText()) && /Nothing else is using it\./.test(await page.getByTestId("gpu-card-1").innerText()));
  check("nobody has answered: it says so and which one card is used meanwhile", /Nobody has chosen yet\. Until you do, Video Tool uses one card only: NVIDIA GeForce RTX 3060\./.test(await page.getByTestId("gpu-needs-choice").innerText()));
  await page.getByTestId("gpu-keep").click();
  await page.waitForFunction(() => !document.querySelector("[data-testid=gpu-needs-choice]"));
  check("'Keep this' saves the cards that are on as the answer and the note goes", JSON.stringify(seen.puts.at(-1)) === JSON.stringify({ allowed: ["GPU-3060"] }), JSON.stringify(seen.puts));
  await page.getByTestId("gpu-switch-0").focus();
  await page.getByTestId("gpu-switch-0").click();
  await page.waitForFunction(() => document.querySelector("[data-testid=gpu-switch-0]")?.getAttribute("aria-checked") === "true");
  check("turning the V100 on saves both cards", JSON.stringify(seen.puts.at(-1).allowed.sort()) === JSON.stringify(["GPU-3060", "GPU-v100"]));
  check("the keyboard stays on the switch after the page redraws", await page.evaluate(() => document.activeElement?.dataset?.testid === "gpu-switch-0"));
  check("the status line tells a screen reader what changed", /Video Tool may now use: Tesla V100-PCIE-16GB, NVIDIA GeForce RTX 3060\./.test(await page.locator("[data-gpu-choice] [role=status]").innerText()));
  await page.getByTestId("gpu-switch-1").click();
  await page.getByTestId("gpu-switch-0").click();
  await page.waitForFunction(() => document.querySelector("[data-testid=gpu-switch-0]")?.getAttribute("aria-checked") === "false");
  check("with no card on it says what that means", /much slower/.test(await page.locator("[data-gpu-choice]").innerText()));
  await ctx.close();
}
{
  const { ctx, page, seen } = await open(1280, 900, ANSWERED);
  await page.goto(`${base}/`, { waitUntil: "load" });
  await page.getByTestId("engine-ollama").waitFor();
  const text = await page.getByTestId("engine-ollama").innerText();
  check("an engine that was already running on a card that is not allowed is described in plain words", /already running on this computer before Video Tool/.test(text) && /not allowed to use/.test(text) && /did not start it and does not change it/.test(text), text);
  check("with a button for Video Tool's own copy; where it is not installed, where to install it and no button", await page.getByTestId("engine-ollama-own").isVisible() && /not installed yet/.test(await page.getByTestId("engine-comfy").innerText()) && (await page.getByTestId("engine-comfy-own").count()) === 0);
  await page.getByTestId("engine-ollama-own").click();
  await page.waitForFunction(() => /own Ollama is running/.test(document.querySelector("[data-testid=engine-ollama]")?.innerText || ""));
  check("the button asks for exactly that engine", seen.posts.length === 1 && seen.posts[0].engine === "ollama");
  await page.screenshot({ path: path.join(out, "overview-wide.png"), fullPage: true });
  await ctx.close();
}
{
  const { ctx, page } = await open(400, 860, UNANSWERED);
  await page.goto(`${base}/`, { waitUntil: "load" });
  await page.getByTestId("gpu-cards").waitFor();
  check("at 400 px the page does not scroll sideways", await noOverflow(page));
  const small = await page.locator("[data-gpu-choice] button.gc-btn").evaluateAll((els) => els.filter((e) => e.getBoundingClientRect().height < 43.5).length);
  const rows = await page.locator("[data-gpu-choice] li").evaluateAll((els) => els.filter((e) => e.getBoundingClientRect().height < 43.5).length);
  check("every button and every row is at least 44 px tall", small === 0 && rows === 0, `${small} buttons, ${rows} rows`);
  await page.screenshot({ path: path.join(out, "overview-phone.png"), fullPage: true });
  await ctx.close();
}
{
  const { ctx, page } = await open(1280, 900, OLD);
  await page.goto(`${base}/`, { waitUntil: "load" });
  await page.locator("[data-gpu-choice]").getByText(/cannot choose graphics cards yet/).waitFor();
  check("a server older than this page says it must be updated, and the page stays up", /Update the server/.test(await page.locator("[data-gpu-choice]").innerText()) && /Processing server is running/.test(await page.locator("body").innerText()));
  await ctx.close();
}

console.log("Server settings at /manage");
{
  const { ctx, page } = await open(1280, 900, UNANSWERED);
  await page.goto(`${base}/manage`, { waitUntil: "load" });
  await page.getByTestId("gpu-cards").waitFor();
  check("when nobody has answered, Server settings opens on the Graphics cards tab", (await page.locator('[data-tab="cards"]').getAttribute("aria-selected")) === "true" && await page.locator("#cards").isVisible() && await page.locator("#engines").isHidden());
  await page.locator('[data-tab="install"]').click();
  check("the Install tab no longer asks for a graphics card for a new install, and says where the card is chosen", (await page.locator("#install select#gpu").count()) === 0 && !/Graphics card\s*$/m.test(await page.locator("#install label").allInnerTexts().then((x) => x.join("\n"))) && /see Graphics cards/.test(await page.locator("#install").innerText()));
  await page.locator('[data-tab="engines"]').click();
  check("the other tabs still work", !(await page.locator("#engines").evaluate((el) => el.hidden)) && (await page.locator("#cards").evaluate((el) => el.hidden)));
  await page.screenshot({ path: path.join(out, "manage-wide.png") });
  await ctx.close();
}
{
  const { ctx, page } = await open(1280, 900, ANSWERED);
  await page.goto(`${base}/manage`, { waitUntil: "load" });
  await page.waitForFunction(() => /Processing computer: GPU-SERVER/.test(document.querySelector("#computer")?.textContent || ""));
  check("once answered it opens on Engines as before", (await page.locator('[data-tab="engines"]').getAttribute("aria-selected")) === "true" && !(await page.locator("#engines").evaluate((el) => el.hidden)));
  await ctx.close();
}
{
  const { ctx, page } = await open(1280, 900, ANSWERED);
  await page.goto(`${base}/manage#cards`, { waitUntil: "load" });
  await page.getByTestId("gpu-cards").waitFor();
  check("a link to #cards opens the Graphics cards tab, which is what the server windows use", await page.locator("#cards").isVisible());
  await ctx.close();
}
check("no page errors", errors.length === 0, errors.join(" | ").slice(0, 300));
await browser.close();
web.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
