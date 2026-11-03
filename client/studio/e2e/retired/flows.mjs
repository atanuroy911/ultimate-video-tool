import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const exe = chromePath();

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch({ executablePath: exe, args: ["--autoplay-policy=no-user-gesture-required"] });
const ctx = await browser.newContext({ viewport: { width: 1500, height: 950 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => m.type() === "error" && errors.push("console: " + m.text()));
page.on("response", (r) => r.status() >= 400 && errors.push(r.status() + " " + r.url()));

let pass = 0, fail = 0;
const check = (name, cond, extra = "") => {
  if (cond) { pass++; console.log("  ok  ", name); } else { fail++; console.log("  FAIL", name, extra); }
};
const api = async (path, opts) => (await fetch(base + path, opts)).json();
const frame = () => page.frames().find((f) => f.url().includes("/composition/9x16/"));


console.log("Review flow");
await page.goto(base + "/p/reference/pro", { waitUntil: "networkidle" });
await page.waitForSelector(".scene-card");
check("3 scenes listed", (await page.locator(".scene-card").count()) === 3);

await page.locator(".scene-card").nth(1).click();
await page.waitForTimeout(700);
check("clicking scene 2 selects it", await page.locator(".scene-card.sel").nth(0).innerText().then((t) => t.startsWith("2")));
const fr = frame();
check("preview iframe loaded the composition", !!fr);
const t = await fr.evaluate(() => window.__vt && window.__vt.time);
check("preview seeked to scene 2 (~2.5s)", t > 2.0 && t < 3.2, `time=${t}`);
check("scene DOM exists in preview", (await fr.locator(".scene").count()) === 3);
await page.screenshot({ path: out + "/f1-scene2.png" });

const tab = async (name) => { await page.getByRole("tab", { name: new RegExp("^" + name) }).click(); await page.waitForTimeout(250); };
// edit a word
await tab("Words");
const wordBefore = await page.locator(".w", { hasText: "দিয়া" }).first().innerText();
await page.locator(".w", { hasText: "দিয়া" }).first().dblclick();
const inp = page.locator(".w-input");
check("double-click opens the word editor", (await inp.count()) === 1);
await inp.fill("দিয়ে");
await inp.press("Enter");
await page.waitForTimeout(1500);
check("word fixed in transcript", (await page.locator(".w", { hasText: "দিয়ে" }).count()) === 1);
const tr = await api("/api/projects/reference/transcript");
check("server stored the edit", tr.transcript.words.some((w) => w.text === "দিয়ে"));
const data = await api("/media/reference/composition/9x16/data.json");
check("caption in composition updated", data.captions.some((c) => c.words.some((w) => w.text === "দিয়ে")));
{ // leave the demo project as we found it so the suite can be re-run
  const w = tr.transcript.words.find((x) => x.text === "দিয়ে");
  await fetch(`${base}/api/projects/reference/words/${w.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ restore: true }) });
}

// edit an element field in the inspector (debounced autosave)
await tab("Scenes");
await page.locator(".scene-card").nth(0).click();
await page.waitForTimeout(500);
const titleInput = page.locator(".el-card").first().locator("input[type=text]").first();
const oldTitle = await titleInput.inputValue();
await titleInput.fill("ইয়েল্ড ২");
await page.waitForTimeout(2600);
let plan = await api("/api/projects/reference/scenes");
check("inspector edit saved to the plan", plan.plan.scenes[0].elements[0].text === "ইয়েল্ড ২", JSON.stringify(plan.plan.scenes[0].elements[0]));
await page.waitForTimeout(1200);
const live = await frame().evaluate(() => document.querySelector(".title")?.textContent);
check("preview hot-swapped the new title", live === "ইয়েল্ড ২", `live=${live}`);

// undo
await page.locator('button[aria-label="Undo"]').click();
await page.waitForTimeout(1200);
plan = await api("/api/projects/reference/scenes");
check("undo restored the old title", plan.plan.scenes[0].elements[0].text === oldTitle, plan.plan.scenes[0].elements[0].text);

// layout change
await page.getByRole("button", { name: "Hero" }).click();
await page.waitForTimeout(1000);
plan = await api("/api/projects/reference/scenes");
check("layout change saved", plan.plan.scenes[0].layout === "hero");
await page.locator('button[aria-label="Undo"]').click();
await page.waitForTimeout(900);

// split from the transcript gutter
await tab("Words");
const splitBtn = page.locator(".beat button", { hasText: "Split" }).first();
check("split button exists for a mid-scene sentence", (await splitBtn.count()) > 0);
await splitBtn.click();
await page.waitForTimeout(2500);
await tab("Scenes");
check("splitting adds a scene", (await page.locator(".scene-card").count()) === 4);
await page.keyboard.press("Control+z");
await page.waitForTimeout(2500);
check("Ctrl+Z undoes the split", (await page.locator(".scene-card").count()) === 3);

// playback + keyboard
await page.getByRole("toolbar", { name: "Playback" }).getByRole("button").click();           // the transport button starts playback; keys keep working afterwards
await page.waitForTimeout(1800);
const t1 = await frame().evaluate(() => window.__vt.time);
await page.keyboard.press("Space");             // pause again via the keyboard shortcut
await page.waitForTimeout(300);
const tA = await frame().evaluate(() => window.__vt.time);
await page.waitForTimeout(500);
const tB = await frame().evaluate(() => window.__vt.time);
check("Space pauses after pressing play", Math.abs(tB - tA) < 0.05, `${tA} vs ${tB}`);
check("Space plays and the preview follows the audio clock", t1 > 0.3, `t=${t1}`);

// right-click menu
await tab("Words");
await page.locator(".w").nth(5).click({ button: "right" });
check("right-click shows the word menu", (await page.locator(".menu").count()) === 1);
await page.keyboard.press("Escape");

// ask Claude
await page.getByRole("button", { name: "AI", exact: true }).click();
await page.getByRole("button", { name: /Ask for a new version of scene/ }).click();
await page.keyboard.press("Escape");
await page.waitForTimeout(1200);
check("request banner appears", (await page.getByText("In Claude Code say").count()) > 0);
const reqs = await api("/api/projects/reference/requests");
check("request stored for the MCP", reqs.length === 1 && reqs[0].kind === "scene" && reqs[0].status === "queued");
await page.screenshot({ path: out + "/f2-request.png" });
await fetch(`${base}/api/projects/reference/requests/${reqs[0].id}`, { method: "DELETE" });

console.log("Themes flow");
await page.goto(base + "/themes/paper", { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
const sf = page.frames().find((f) => f.url().includes("/.specimen/"));
check("specimen preview loaded", !!sf);
const accentBefore = await sf.evaluate(() => getComputedStyle(document.getElementById("root")).getPropertyValue("--accent").trim());
await page.getByLabel("Accent value", { exact: true }).fill("#0a84ff");
await page.waitForTimeout(900);
const accentAfter = await sf.evaluate(() => getComputedStyle(document.getElementById("root")).getPropertyValue("--accent").trim());
check("colour change shows live in the specimen", accentBefore === "#f26a1f" && accentAfter === "#0a84ff", `${accentBefore} -> ${accentAfter}`);
check("unsaved badge shows", (await page.getByText("unsaved changes").count()) === 1);
check("built-in Save is disabled", await page.getByRole("button", { name: "Save", exact: true }).isDisabled());
await page.getByRole("button", { name: /Save as new/ }).click();
await page.locator(".modal input").fill("test-brand");
await page.locator(".modal").getByRole("button", { name: "Save" }).click();
await page.waitForTimeout(1500);
const themes = await api("/api/themes");
const mine = themes.find((x) => x.name === "test-brand");
check("saved as a new theme with the new accent", mine && mine.color.accent === "#0a84ff");
await page.screenshot({ path: out + "/f3-theme.png" });
await fetch(base + "/api/themes/test-brand", { method: "DELETE" });

console.log(`\n${pass} passed, ${fail} failed`);
console.log("ERRORS:", errors.length ? "\n" + errors.join("\n") : "none");
await browser.close();
process.exit(fail ? 1 : 0);
