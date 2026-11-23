// The owner, 2026-11-24: HyperFrames opens only for scenes made of HTML (code-native shots); Video Tool's own editor is the main editor.
// In a real browser: the editor has no whole-video HyperFrames button; a scene with an HTML shot offers "Edit this scene in HyperFrames" in its menu and
// opens its shot there (the shot editor's HyperFrames tab, the Studio in its own window); a scene without HTML does not offer it.
//   VT_URL=http://localhost:5174 VT_PROJECT=c6-shot node e2e/scene-hyperframes.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "c6-shot";
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };
const api = async (method, url) => (await fetch(base + url, { method })).json();

const plan = (await api("GET", `/api/projects/${pid}/scenes`)).plan.scenes;
const withShot = plan.findIndex((s) => s.shot), without = plan.findIndex((s) => !s.shot);
if (withShot < 0 || without < 0) { console.log(`${pid} needs one scene with an HTML shot and one without`); process.exit(1); }

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const ctx = await browser.newContext({ viewport: { width: 1500, height: 950 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
await page.waitForSelector(".wb .wb-viewer", { timeout: 45000 });
await page.waitForTimeout(1500);
check("Video Tool's own editor is the main editor (no whole-video HyperFrames button)", (await page.getByRole("button", { name: "Edit in HyperFrames" }).count()) === 0
  && (await page.locator(".studio-embed").count()) === 0);

const menuOf = async (i) => {
  await page.getByRole("button", { name: `Scene ${i + 1} actions` }).click();
  await page.waitForTimeout(400);
  const has = (await page.getByRole("button", { name: "Edit this scene in HyperFrames" }).count()) > 0;
  return has;
};
const plainHas = await menuOf(without);
await page.keyboard.press("Escape");
await page.waitForTimeout(300);
check("a scene without HTML does not offer HyperFrames", !plainHas, `scene ${without + 1}`);

const shotHas = await menuOf(withShot);
check("a scene made of HTML offers 'Edit this scene in HyperFrames'", shotHas, `scene ${withShot + 1} (shot ${plan[withShot].shot})`);
const popup = ctx.waitForEvent("page", { timeout: 90000 }).catch(() => null);
await page.getByRole("button", { name: "Edit this scene in HyperFrames" }).click();
const studio = await popup;
check("it opens that scene's shot in HyperFrames", !!studio && /#project\//.test(studio.url()), studio ? studio.url() : "no window");
check("the shot editor shows its HyperFrames tab", await page.getByRole("button", { name: "Save to video" }).isVisible().catch(() => false));
const shotApi = `/api/projects/${pid}/shots/${plan[withShot].shot}`;
check("the server's HyperFrames is open on that shot", (await api("GET", `${shotApi}/studio`)).open === true);
await page.screenshot({ path: "e2e/out/scene-hyperframes.png" });

await page.getByRole("button", { name: "Close the shot editor" }).click();
await page.waitForTimeout(2500);
check("closing the shot editor stops HyperFrames", (await api("GET", `${shotApi}/studio`)).open === false);
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
