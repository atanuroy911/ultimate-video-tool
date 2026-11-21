// The shot editor in a real browser (docs/plans/PLAN-CODE-NATIVE-EDITOR.MD, C3): open a scene's code-native shot, select an element by clicking it,
// drag it, change its text and a knob, undo, and check that only overrides.json changed (never the shot's code). Needs a project whose scene has a shot.
//   VT_URL=http://localhost:5174 VT_PROJECT=<project> VT_SCENE=<scene with a shot> VT_SHOT=<shot id> VT_ELEMENT=<data-vt-id> node e2e/shot-editor.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "c2-mix", scene = process.env.VT_SCENE || "s1", shot = process.env.VT_SHOT || "hook", target = process.env.VT_ELEMENT || "q";
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };
const shotApi = `${base}/api/projects/${pid}/shots/${shot}`;

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
const api = async (method, url, body) => page.evaluate(async ([m, u, b]) => { const r = await fetch(u, { method: m, headers: { "content-type": "application/json" }, body: b ? JSON.stringify(b) : undefined }); return r.json(); }, [method, url, body]);

await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
await page.waitForSelector(".wb .wb-viewer", { timeout: 45000 });
const codeBefore = (await api("GET", shotApi)).html;
await api("PUT", `${shotApi}/overrides`, { overrides: {} });
await page.evaluate((s) => window.dispatchEvent(new CustomEvent("vt-select-scene", { detail: s })), scene);
const open = page.getByRole("button", { name: "Edit shot" });
await open.waitFor({ timeout: 10000 });
check("a scene with a shot offers to edit it", await open.isVisible());
await open.click();
await page.waitForSelector(".shot-canvas iframe", { timeout: 15000 });
await page.waitForFunction(() => document.querySelector(".shot-side")?.textContent?.includes("Selectable:"), null, { timeout: 15000 });
check("the shot loads in a frame with no access to the Studio", await page.$eval(".shot-canvas iframe", (f) => f.getAttribute("sandbox") === "allow-scripts"));

// Find the element on screen: the bridge says where it is when picked; click the middle of the canvas region the shot puts it in.
const canvas = await page.$eval(".shot-canvas", (e) => { const r = e.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; });
const info = await api("GET", shotApi);
const where = { q: [0.5, 0.64], title: [0.3, 0.42] }[target] || [0.5, 0.5];
await page.mouse.click(canvas.x + canvas.w * where[0], canvas.y + canvas.h * where[1]);
const sel = page.locator(".shot-sel");
await sel.waitFor({ timeout: 5000 }).catch(() => {});
check("clicking an element selects it", (await page.locator(".shot-tag").textContent().catch(() => "")) === target, await page.locator(".shot-tag").textContent().catch(() => "none"));
const b0 = await sel.boundingBox();
await page.mouse.move(b0.x + b0.width / 2, b0.y + b0.height / 2);
await page.mouse.down();
await page.mouse.move(b0.x + b0.width / 2 + 40, b0.y + b0.height / 2 - 30, { steps: 8 });
await page.mouse.up();
await page.waitForTimeout(900);
const b1 = await sel.boundingBox();
check("dragging moves the selection with the element", Math.abs(b1.x - b0.x - 40) < 4 && Math.abs(b1.y - b0.y + 30) < 4, `${Math.round(b1.x - b0.x)},${Math.round(b1.y - b0.y)}`);
let saved = (await api("GET", shotApi)).overrides;
const scale = canvas.w / info.width;
check("the move is saved as an override, in shot pixels", saved.elements?.[target] && Math.abs(saved.elements[target].x - 40 / scale) < 6, JSON.stringify(saved.elements?.[target]));

const text = page.locator(".shot-side textarea");
if (await text.count()) {
  await text.fill("Edited in the Studio");
  await text.blur();
  await page.waitForTimeout(900);
  saved = (await api("GET", shotApi)).overrides;
  check("the text edit is saved", saved.elements?.[target]?.text === "Edited in the Studio");
} else check("the element offers its text", false);

const knob = page.locator(".shot-knob input[type=color]").first();
if (await knob.count()) {
  await knob.evaluate((e) => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set; set.call(e, "#22c55e"); e.dispatchEvent(new Event("input", { bubbles: true })); e.dispatchEvent(new Event("change", { bubbles: true })); });
  await page.waitForTimeout(900);
  saved = (await api("GET", shotApi)).overrides;
  check("a colour knob is saved", Object.values(saved.knobs || {}).includes("#22c55e"), JSON.stringify(saved.knobs));
}
await page.screenshot({ path: process.env.VT_SHOT_PNG || "shot-editor.png" });

// C4: the code view. Add an element in the code, save with Ctrl+S: the preview loads it and the visual edits stay.
await page.getByRole("tab", { name: "Code" }).click();
await page.waitForSelector(".shot-code-editor .cm-content", { timeout: 15000 });
check("the code view shows the shot's code", (await page.locator(".cm-content").textContent()).includes("data-composition-id"));
const newCode = codeBefore.replace("</body>", '<div data-vt-id="extra" style="position:absolute;left:100px;top:1500px;color:#fff;font-size:60px">Added in code</div>\n</body>');
await page.locator(".cm-content").click();
await page.keyboard.press("Control+a");
await page.keyboard.insertText(newCode);
check("an unsaved change is shown", (await page.locator(".shot-code-bar").textContent()).includes("Not saved"));
await page.keyboard.press("Control+s");
await page.waitForFunction(() => document.querySelector(".shot-code-bar")?.textContent?.includes("Saved"), null, { timeout: 10000 });
const afterCode = await api("GET", shotApi);
check("saving sends the code", afterCode.html.includes('data-vt-id="extra"') && afterCode.ids.includes("extra"));
check("the visual edits survive new code", afterCode.overrides.elements?.[target]?.text === "Edited in the Studio");
await page.getByRole("tab", { name: "Design" }).click();
await page.waitForFunction(() => document.querySelector(".shot-side")?.textContent?.includes("extra"), null, { timeout: 15000 }).catch(() => {});
check("the preview loads the new code", (await page.locator(".shot-side").textContent()).includes("extra"));
await page.getByRole("tab", { name: "Code" }).click();
await page.locator(".cm-content").click();
await page.keyboard.press("Control+a");
await page.keyboard.insertText("<div>no root</div>");
await page.keyboard.press("Control+s");
await page.waitForTimeout(1200);
check("code without a timed root is refused and the shot keeps its code", (await api("GET", shotApi)).html === newCode);
await page.getByRole("tab", { name: "Design" }).click();
await api("PUT", shotApi, { html: codeBefore });

await page.locator(".shot-editor").focus();
await page.keyboard.press("Control+z");
await page.waitForTimeout(900);
saved = (await api("GET", shotApi)).overrides;
check("undo takes the last change back", !Object.keys(saved.knobs || {}).length, JSON.stringify(saved.knobs));
check("the visual editor never changed the shot's code", (await api("GET", shotApi)).html === codeBefore);
await page.getByRole("button", { name: "Close the shot editor" }).click();
check("closing returns to the video", await page.getByRole("button", { name: "Edit shot" }).isVisible().catch(() => false));
check("no page errors", errors.length === 0, errors.join(" | "));
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
