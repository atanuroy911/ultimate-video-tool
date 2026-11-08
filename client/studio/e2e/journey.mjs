import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const exe = chromePath();

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch({
  executablePath: exe,
  args: ["--disable-gpu", "--autoplay-policy=no-user-gesture-required", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
});
const ctx = await browser.newContext({ viewport: { width: 1500, height: 950 }, permissions: ["microphone"] });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => m.type() === "error" && errors.push("console: " + m.text()));
page.on("response", (r) => r.status() >= 500 && errors.push(r.status() + " " + r.url()));

let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const api = async (path, opts) => (await fetch(base + path, opts)).json();
const created = [];

console.log("Upload -> progress -> review (real speech model)");
await fetch(base + "/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ autopilot: false }) });   // this suite checks the editor; simple.mjs covers autopilot
await page.goto(base + "/new", { waitUntil: "networkidle" });
await page.getByLabel("Choose a file").setInputFiles(path.join(repo, "..", "samples", "audio", "bn_plain.mp3"));
check("file name shown", (await page.getByText("bn_plain.mp3").count()) > 0);
for (let i = 0; i < 6 && !(await page.getByRole("button", { name: "Make my video" }).count()); i++) await page.locator(".tf-nav .btn.primary").first().click();   // OK through the screens
await page.locator("input[placeholder='The app can name it for you']").fill("UI upload test");                                                     // the last screen's video name
const gen = page.getByRole("button", { name: "Make my video" });
check("Make enabled once a file is chosen", await gen.isEnabled());
await gen.click();
await page.waitForURL(/\/p\/[^/]+\/progress/, { timeout: 15000 });
const pid = page.url().split("/p/")[1].split("/")[0];
created.push(pid);
check("navigated to the progress screen", true);
await page.waitForSelector("h1", { timeout: 10000 });
check("the making screen shows one plain-words step", /…$/.test((await page.locator("h1").innerText()).trim()));
await page.screenshot({ path: out + "/g1-progress.png" });
await page.waitForURL(new RegExp(`/p/${pid}$`), { timeout: 120000 });
check("auto-opened the review screen when done", true);
await page.waitForSelector(".scene-card");
await page.waitForTimeout(1500);
check("scenes were drafted (the 4-sentence clip becomes 2-3 scenes)", (await page.locator(".scene-card").count()) >= 2);
await page.getByRole("tab", { name: /^Words/ }).click();
await page.waitForTimeout(500);
const nWords = await page.locator(".w").count();
check(`transcript shown (${nWords} words)`, nWords >= 26);
check("first word is correct and in Latin letters (default policy)", (await page.locator(".w").first().innerText()) === "yield");
check("preview iframe is live", !!page.frames().find((f) => f.url().includes("/composition/9x16/")));
const proj = await api(`/api/projects/${pid}`);
check("project is ready with a duration", proj.status === "planned" && proj.duration > 8 && proj.has_transcript, JSON.stringify({ s: proj.status, d: proj.duration }));
await page.screenshot({ path: out + "/g2-review.png" });

await browser.close();

console.log("Record with no speech -> clear error (fake microphone plays a noise file)");
const browser2 = await chromium.launch({
  executablePath: exe,
  args: ["--disable-gpu", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--use-file-for-fake-audio-capture=" + path.join(repo, "..", "samples", "audio", "noise.wav") + ""],
});
const ctx2 = await browser2.newContext({ viewport: { width: 1500, height: 950 }, permissions: ["microphone"] });
const page2 = await ctx2.newPage();
page2.on("pageerror", (e) => errors.push("pageerror: " + e.message));

await page2.goto(base + "/new", { waitUntil: "networkidle" });
await page2.getByRole("button", { name: "Start recording" }).click();
await page2.waitForTimeout(3500);
check("recording timer runs", /0:0[2-9]/.test(await page2.locator("text=/0:0\\d/").first().innerText()));
await page2.getByRole("button", { name: "Stop recording" }).click();
await page2.waitForSelector("audio[controls]");
check("recorded clip can be played back", true);
const gen2 = page2.getByRole("button", { name: "Make my video" });
check("Make enabled after recording", await gen2.isEnabled());
await gen2.click();
await page2.waitForURL(/\/p\/[^/]+\/progress/, { timeout: 15000 });
created.push(page2.url().split("/p/")[1].split("/")[0]);
await page2.getByText(/No speech was found/).waitFor({ timeout: 90000 });
check("no-speech error is shown in plain language", true);
check("retry and start-over buttons offered", (await page2.getByRole("button", { name: "Retry this step" }).count()) === 1);
await page2.screenshot({ path: out + "/g3-nospeech.png" });

console.log("Delete from the projects list");
await page2.goto(base + "/", { waitUntil: "networkidle" });
const before = (await api("/api/projects")).length;
await page2.locator("article", { hasText: "UI upload test" }).getByRole("button", { name: /Delete/ }).click();
await page2.getByRole("dialog").getByRole("button", { name: "Delete" }).click();
await page2.waitForTimeout(1200);
check("project deleted", (await api("/api/projects")).length === before - 1);
for (const id of created) await fetch(`${base}/api/projects/${id}`, { method: "DELETE" }).catch(() => {});

console.log(`\n${pass} passed, ${fail} failed`);
console.log("ERRORS:", errors.length ? "\n" + errors.join("\n") : "none");
await browser2.close();
process.exit(fail ? 1 : 0);
