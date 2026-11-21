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
check("no page errors", errors.length === 0, errors.join(" | "));
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
