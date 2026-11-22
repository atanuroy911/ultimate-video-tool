// Export page: render through the UI with non-default options and verify the file that comes out.
import { chromium } from "playwright-core";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("response", (r) => r.status() >= 500 && errors.push(r.status() + " " + r.url()));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const api = async (p) => (await fetch(base + p)).json();
const pid = process.env.VT_PROJECT || "reference";

console.log("Export page");
await page.goto(base + `/p/${pid}/export`, { waitUntil: "networkidle" });
check("nothing exported yet message or previous exports listed", (await page.getByText(/Nothing exported yet|Latest export/).count()) > 0);
await page.getByRole("group", { name: "Export preset" }).getByRole("button", { name: "Custom" }).click();
// Custom opens the options sheet (three steps)
await page.getByRole("button", { name: "720p" }).click();
await page.locator(".ios-sheet select").first().selectOption("draft");
await page.getByRole("button", { name: "Continue" }).click();
await page.getByLabel(/Burn captions/).uncheck();
await page.getByRole("button", { name: "Continue" }).click();
await page.locator(".ios-sheet select").first().selectOption("none");   // music
await page.getByRole("button", { name: "Done", exact: true }).last().click();
await page.getByRole("button", { name: /Export video/ }).click();
await page.getByText(/Exporting…/).first().waitFor({ timeout: 10000 });
check("render started and the button shows progress", true);
await page.screenshot({ path: out + "/h1-rendering.png" });
await page.locator("video.video-out").waitFor({ timeout: 240000 });
check("finished: the video appears with a player", true);
const files = await api(`/api/projects/${pid}/exports`);
check("export listed with a subtitle file", files.length >= 1 && files[0].srt);
const f = files[0].path;
const probe = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,codec_name", "-of", "csv=p=0", f], { encoding: "utf8" }).trim();
check("720p vertical H.264 at 30 fps (" + probe + ")", probe === "h264,720,1280,30/1");
const a = execFileSync("ffprobe", ["-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name,channels", "-of", "csv=p=0", f], { encoding: "utf8" }).trim();
check("has a stereo AAC audio track (" + a + ")", a === "aac,2");
const comp = await api(`/media/${pid}/composition/9x16/data.json`);
check("preview composition has its captions back after a no-captions export", comp.captions_enabled !== false);
const srt = await (await fetch(base + files[0].srt)).text();
check("subtitle file has timed lines", /00:00:\d\d,\d{3} --> /.test(srt));
await page.screenshot({ path: out + "/h2-done.png" });

console.log(`\n${pass} passed, ${fail} failed`);
console.log("ERRORS:", errors.length ? "\n" + errors.join("\n") : "none");
await browser.close();
process.exit(fail ? 1 : 0);
