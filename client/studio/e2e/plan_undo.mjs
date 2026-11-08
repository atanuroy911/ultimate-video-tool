// An assistant's plan change (the MCP update_scene tool, run by the script below the server) is undone from the AI panel's
// "Undo the last plan change", and a second press puts it back. Needs `reference` on the scratch server.
// VT_URL=http://127.0.0.1:5178 VT_DATA=<scratch data> node e2e/plan_undo.mjs
import { chromium } from "playwright-core";
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { base, chromePath } from "./common.mjs";

const OUT = "e2e/out/plan-undo";
mkdirSync(OUT, { recursive: true });
const repo = path.resolve("../..");
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const captionY = async () => ((await (await fetch(`${base}/api/projects/reference/scenes`)).json()).plan?.scenes?.[0]?.caption ?? {}).y;
const assistant = (y) => execFileSync(path.join(repo, ".venv/Scripts/python.exe"), ["-X", "utf8", "-c",
  `from vt.mcp import server as m; f=getattr(m.update_scene,'fn',m.update_scene); sid=m._proj('reference').scenes().scenes[0].id; print(f('reference', sid, {'caption': {'y': ${y}}}))`],
  { cwd: path.join(repo, "server"), env: { ...process.env, CUDA_VISIBLE_DEVICES: "-1" } }).toString();

const before = await captionY();
check("the assistant's change is saved", /'ok': True/.test(assistant(0.27)) && (await captionY()) === 0.27, String(await captionY()));
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
for (const [w, h, scheme] of [[1280, 900, "light"], [400, 860, "dark"]]) {
  const tag = `${w}px ${scheme}`;
  const page = await (await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme })).newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${base}/p/reference`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "AI assistant" }).click();
  const btn = page.getByTestId("undo-plan");
  await btn.waitFor({ timeout: 8000 }).catch(() => {});
  check(`${tag}: the AI panel offers to undo the last plan change`, await btn.isVisible());
  await btn.scrollIntoViewIfNeeded().catch(() => {});
  await page.screenshot({ path: `${OUT}/${w}-${scheme}.png` });
  await btn.click();
  await page.waitForTimeout(1500);
  const y1 = await captionY();
  check(`${tag}: pressing it brings the plan back${w === 1280 ? " (the assistant's change is gone)" : " (the change is back: a second press)"}`, w === 1280 ? y1 !== 0.27 : y1 === 0.27, String(y1));
  check(`${tag}: no page errors`, errors.length === 0, errors.join("; "));
  await page.context().close();
}
await browser.close();
assistant(before ?? "None");
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
