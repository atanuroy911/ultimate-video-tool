// Another computer uses a Video Tool server (docs/plans/PLAN-CLIENT-SERVER.MD CS4 + CS5, docs/plans/PLAN-PERFECT.MD decision 7): a browser on the server's network
// opens the Studio with nothing to enter, a page from another site is refused, and a big recording still arrives when the connection drops in the middle of the upload.
//
// Needs a scratch `vt server` (it listens beyond this computer) opened by its network address, so the browser counts as another computer:
//   VT_DATA=<scratch dir> vt server --port 8771 --ollama off --comfy off --voicestudio off
//   VT_URL=http://<this computer's LAN address>:8771 node e2e/connect.mjs
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { chromium } from "playwright-core";
import { base, chromePath, repo } from "./common.mjs";

const local = base.replace(/\/\/[^:/]+/, "//127.0.0.1");
if (local === base) { console.log("Open the server by its network address (VT_URL=http://192.168.x.x:port), not 127.0.0.1"); process.exit(2); }

let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };

// a 20 MB silent recording: big enough to go up in chunks
const out = path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });
const wav = path.join(os.tmpdir(), "vt-connect-big.wav");
const n = 20 * 1024 * 1024, h = Buffer.alloc(44);
h.write("RIFF", 0); h.writeUInt32LE(36 + n, 4); h.write("WAVEfmt ", 8); h.writeUInt32LE(16, 16); h.writeUInt16LE(1, 20); h.writeUInt16LE(1, 22);
h.writeUInt32LE(16000, 24); h.writeUInt32LE(32000, 28); h.writeUInt16LE(2, 32); h.writeUInt16LE(16, 34); h.write("data", 36); h.writeUInt32LE(n, 40);
fs.writeFileSync(wav, Buffer.concat([h, Buffer.alloc(n)]));

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));

console.log("Connect to a server on another computer");
await page.goto(base + "/", { waitUntil: "networkidle" });
check("a browser on the server's network opens the Studio with nothing to enter", !(await page.getByTestId("refused-screen").isVisible().catch(() => false)) && (await page.locator("nav, aside, main").count()) > 0);
check("and the server answers this browser", await page.evaluate(async () => (await fetch("/api/health")).status === 200));
check("there is no code to ask for and no list of approved devices", (await fetch(local + "/api/server/code", { method: "POST" })).status === 404 && (await fetch(local + "/api/server/clients")).status === 404);
const status = (headers) => new Promise((resolve, reject) => { const u = new URL(base + "/api/health"); http.get({ host: u.hostname, port: u.port, path: u.pathname, headers }, (r) => { r.resume(); resolve(r.statusCode); }).on("error", reject); });
check("a page from another site is refused", (await status({ Origin: "https://evil.example" })) === 401);
check("so is a name that anyone on the internet could point at this computer", (await status({ Host: "evil.example.com" })) === 401);

console.log("A big recording, with the connection dropping halfway");
let puts = 0, dropped = 0, last = null;
page.on("response", async (r) => { if (r.request().method() === "PUT" && /\/api\/uploads\//.test(r.url()) && r.ok()) last = await r.json().catch(() => last); });
await page.route("**/api/uploads/*", (route) => {
  if (route.request().method() !== "PUT") return route.continue();
  puts++;
  if (puts === 2) { dropped++; return route.abort("connectionreset"); }      // the second chunk never arrives
  return route.continue();
});
await page.goto(base + "/new", { waitUntil: "networkidle" });
await page.getByLabel("Choose a file").setInputFiles(wav);
const make = page.getByRole("button", { name: /Make my video/i }).first();
for (let i = 0; i < 12 && !(await make.isVisible().catch(() => false)); i++) {
  const ok = page.locator(".tf-nav .btn.primary").first();
  if (!(await ok.count()) || !(await ok.isEnabled())) break;
  await ok.click();
  await page.waitForTimeout(250);
}
check("the New flow reaches Make my video", await make.isVisible());
await make.click();
await page.waitForURL(/\/p\/[^/]+\/progress/, { timeout: 120000 }).catch(() => {});
check("the project was made despite the dropped chunk", /\/p\/[^/]+\/progress/.test(page.url()), page.url());
check("the upload went in chunks and one really dropped", puts >= 3 && dropped === 1, `puts=${puts}`);
check("the whole file arrived, every byte once", last?.done && last.offset === n + 44, JSON.stringify(last));
check("no page errors", errors.length === 0, errors.join(" | "));
await page.screenshot({ path: path.join(out, "connect.png") });
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
