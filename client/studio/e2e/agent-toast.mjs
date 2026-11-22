// W14: a change made through an MCP tool shows "Claude changed scene ..." in the open Studio. Needs a scratch server; the change is made by the script below.
//   VT_URL=http://localhost:5174 VT_PROJECT=c2-mix VT_CHANGE="<command that edits a scene through an MCP tool>" node e2e/agent-toast.mjs
import { chromium } from "playwright-core";
import { execSync } from "node:child_process";
import { base, chromePath } from "./common.mjs";
const pid = process.env.VT_PROJECT || "c2-mix";
let pass = 0, fail = 0;
const check = (n, ok, x = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${n}${x ? "  " + x : ""}`); };
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();
const errors = []; page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
await page.waitForSelector(".wb .wb-viewer", { timeout: 45000 });
await page.waitForTimeout(2500);
execSync(process.env.VT_CHANGE, { stdio: "inherit", shell: process.env.VT_SHELL || true });
const toast = page.getByText(/changed scene|changed \d+ scenes|changed the video/).first();
await toast.waitFor({ timeout: 15000 }).catch(() => {});
const text = await toast.textContent().catch(() => "");
check("the person is told who changed what", /^Claude changed scene s?\d/i.test(text || "") || /Claude changed/.test(text || ""), text);
const glow = () => page.evaluate(() => document.querySelectorAll(".is-director-changed, .vt-changed").length);
check("the changed scene's clip glows on the timeline", await page.waitForFunction(() => document.querySelectorAll(".is-director-changed, .vt-changed").length > 0, null, { timeout: 8000 }).then(() => true, () => false));
await page.waitForFunction(() => document.querySelectorAll(".is-director-changed, .vt-changed").length === 0, null, { timeout: 12000 }).catch(() => {});
// While the person types in a field, the change waits; it comes in when they leave the field.
await page.evaluate(() => { const i = document.createElement("input"); i.id = "vt-test-field"; i.style.cssText = "position:fixed;top:0;left:0;z-index:99999"; document.body.appendChild(i); i.focus(); });
execSync(process.env.VT_CHANGE, { stdio: "inherit", shell: process.env.VT_SHELL || true });
await page.waitForTimeout(4000);
check("a change waits while the person is typing", (await glow()) === 0);
await page.evaluate(() => document.getElementById("vt-test-field").blur());
check("and comes in when they leave the field", await page.waitForFunction(() => document.querySelectorAll(".is-director-changed, .vt-changed").length > 0, null, { timeout: 8000 }).then(() => true, () => false));
await page.evaluate(() => window.dispatchEvent(new CustomEvent("vt-select-scene", { detail: "s2" })));
await page.waitForTimeout(500);
const sel = () => page.evaluate(() => document.querySelector('[data-scene].sel')?.getAttribute("data-scene") || "");          // the scene list shows the selection in either timeline
const before = await sel();
execSync(process.env.VT_CHANGE, { stdio: "inherit", shell: process.env.VT_SHELL || true });
await page.waitForFunction(() => document.querySelectorAll(".vt-changed, .is-director-changed").length > 0, null, { timeout: 8000 }).catch(() => {});
check("the person's selection stays the same after the agent's change", before === "s2" && (await sel()) === "s2", `${before} -> ${await sel()}`);
// W14.3: Ctrl+Z takes the agent's change back and says so.
const tone = () => page.evaluate(async (p) => { const r = await fetch(`/api/projects/${p}/scenes`); const j = await r.json(); return (j.plan || j).scenes[0].tone ?? null; }, pid);
const t0 = await tone();
execSync(process.env.VT_CHANGE, { stdio: "inherit", shell: process.env.VT_SHELL || true });
await page.waitForFunction(() => document.querySelectorAll(".vt-changed, .is-director-changed").length > 0, null, { timeout: 8000 }).catch(() => {});
await page.waitForTimeout(1500);
const t1 = await tone();
await page.mouse.click(5, 500);
await page.keyboard.press("Control+z");
const undone = await page.getByText("Undid Claude's change").waitFor({ timeout: 8000 }).then(() => true, () => false);
await page.waitForTimeout(1000);
check("Ctrl+Z undoes the agent's change and says so", undone && t1 !== t0 && (await tone()) === t0, `${t0} -> ${t1} -> ${await tone()}`);
// W14.4: the agent changes the scene the person has open: the inspector says so and offers Undo.
await page.evaluate(() => window.dispatchEvent(new CustomEvent("vt-select-scene", { detail: "s1" })));
await page.waitForTimeout(800);
const u0 = await tone();
execSync(process.env.VT_CHANGE, { stdio: "inherit", shell: process.env.VT_SHELL || true });
const notice = page.locator(".vt-agent-touched");
const shown = await notice.waitFor({ timeout: 10000 }).then(() => true, () => false);
check("the inspector says Claude just changed the open scene", shown && (await notice.textContent()).includes("Claude just changed this"));
if (shown) { await notice.getByRole("button", { name: "Undo" }).click(); await page.waitForTimeout(1500); }
check("its Undo takes the change back", (await tone()) === u0, `${u0} -> ${await tone()}`);
check("no page errors", errors.length === 0, errors.join(" | "));
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
