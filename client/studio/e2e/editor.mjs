// The editing window: canvas selection, context inspector, timeline (drag, zoom), menus, command palette, resizable panels, AI sheet.
// Needs a running Studio and the demo project:  VT_PROJECT=reference node e2e/editor.mjs
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });
const pid = process.env.VT_PROJECT || "reference";
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const ctx = await browser.newContext({ viewport: { width: 1500, height: 950 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => m.type() === "error" && errors.push("console: " + m.text()));

let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { if (cond) { pass++; console.log("  ok  ", name); } else { fail++; console.log("  FAIL", name, extra); } };
const api = async (p, opts) => (await fetch(base + p, opts)).json();
const frame = () => page.frames().find((f) => f.url().includes("/composition/9x16/"));

console.log("Editor window");
await page.goto(`${base}/p/${pid}/pro`, { waitUntil: "networkidle" });
await page.waitForSelector(".scene-card");
check("title bar has menus", (await page.getByRole("toolbar", { name: "Menus" }).getByRole("button").count()) === 5);
check("nothing is selected at first: scene inspector shows the first scene", await page.getByRole("heading", { name: "Scene 1" }).isVisible());

// Escape -> the video inspector
await page.locator(".ed").click({ position: { x: 5, y: 5 } });
await page.keyboard.press("Escape");
check("Escape shows the video settings", await page.getByRole("heading", { name: "Video", exact: true }).isVisible());
check("video settings have the drawing style", (await page.getByRole("group", { name: "Drawing style" }).count()) === 1);

// canvas selection: click an element in the preview
await page.locator(".scene-card").nth(0).click();
await page.keyboard.press("ArrowRight");       // a moment inside scene 1 (at 0 s nothing is on screen yet)
await page.keyboard.press("ArrowRight");
await page.waitForTimeout(900);
const fr = frame();
await fr.waitForSelector(".el");
// elements take room only once they have entered: go to a moment when all of scene 1's elements are on screen
const allIn = await fr.evaluate(() => { const D = window.__vt && window.__vt.timeline && window.__vt.timeline(); return D ? D.duration() : 0; });
const lastAt = (await (await fetch(base + `/api/projects/${process.env.VT_PROJECT || "reference"}/scenes`)).json()).timing.scenes[0];
await fr.evaluate((t) => window.__vt.seek(t), Math.max(0.5, (lastAt ? lastAt.end : 2) - 0.4));
await page.waitForTimeout(700);
const first = await page.locator(".phone").boundingBox();
await page.getByRole("button", { name: "Seek" }).count();
// the second element of scene 1 (an icon): find where it is on the canvas and click it
const info = await fr.evaluate(() => { const els = [...document.querySelectorAll(".scene[data-scene='s1'] .el")]; return els.map((e) => { const b = e.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2, e.getAttribute("data-el")]; }); });
check("elements carry an index for picking", info.length >= 2 && info.every((i) => i[2] !== null));
const scale = first.width / 1080;
const target = info[info.length - 1];
await page.mouse.click(first.x + target[0] * scale, first.y + target[1] * scale);
await page.waitForTimeout(800);
check("clicking an element on the canvas opens its card", (await page.locator(".el-card.picked").count()) === 1, `index=${target[2]}`);
check("an outline is drawn around the selection", (await page.locator(".sel-box").count()) === 1);
await page.screenshot({ path: out + "/e1-canvas-select.png" });

// timeline
const clips = page.locator(".tl-clip");
check("timeline lists the scenes", (await clips.count()) === 3);
check("timeline shows elements and words", (await page.locator(".tl-chip").count()) >= 5 && (await page.locator(".tl-word").count()) >= 20);
await clips.nth(1).click();
await page.waitForTimeout(500);
check("clicking a clip selects the scene", await page.locator(".scene-card.sel").nth(0).innerText().then((t) => t.startsWith("2")));
const zoomBefore = await page.locator(".tl-inner").evaluate((e) => e.getBoundingClientRect().width);
await page.getByRole("button", { name: "Zoom in" }).click();
await page.getByRole("button", { name: "Zoom in" }).click();
await page.waitForTimeout(200);
const zoomAfter = await page.locator(".tl-inner").evaluate((e) => e.getBoundingClientRect().width);
check("zoom widens the timeline", zoomAfter > zoomBefore * 1.5, `${zoomBefore} -> ${zoomAfter}`);
await page.getByRole("button", { name: "Zoom out" }).click();
await page.getByRole("button", { name: "Zoom out" }).click();
await page.getByRole("button", { name: "Zoom out" }).click();
await page.waitForTimeout(200);

// drag the edge between scene 2 and 3 back to the start of beat b3 (5.0 s)
const c2 = await clips.nth(1).boundingBox();
const timing = (await api(`/api/projects/${pid}/scenes`)).timing.scenes;
const pps = c2.width / (timing[1].end - timing[1].start);
const grab = await clips.nth(1).locator(".grab:not(.l)").boundingBox();
await page.mouse.move(grab.x + grab.width / 2, grab.y + grab.height / 2);
await page.mouse.down();
await page.mouse.move(c2.x + (5.0 - timing[1].start) * pps, grab.y + grab.height / 2, { steps: 8 });
check("a snap line shows while dragging", (await page.locator(".tl-snap").count()) === 1);
await page.mouse.up();
await page.waitForTimeout(1500);
let plan = (await api(`/api/projects/${pid}/scenes`)).plan.scenes;
check("dragging the edge moved the sentence to the next scene", JSON.stringify(plan[1].beats) === '["b2"]' && plan[2].beats[0] === "b3", JSON.stringify(plan.map((s) => s.beats)));
await page.keyboard.press("Control+z");
await page.waitForTimeout(1300);
plan = (await api(`/api/projects/${pid}/scenes`)).plan.scenes;
check("undo puts it back", plan[1].beats.length === 3);

// menus + command palette
await page.getByRole("button", { name: "View", exact: true }).click();
await page.getByRole("menuitem", { name: /Phone safe area/ }).click();
await page.waitForTimeout(300);
check("View menu toggles the safe area", (await page.locator(".phone .safe").count()) === 1);
await page.getByRole("button", { name: "View", exact: true }).click();
await page.getByRole("menuitem", { name: /Phone safe area/ }).click();
await page.keyboard.press("Control+k");
check("Ctrl+K opens the command palette", await page.getByRole("dialog", { name: "Command palette" }).isVisible());
await page.getByLabel("Search commands").fill("stick");
check("palette filters commands", (await page.getByRole("option").count()) >= 1);
await page.keyboard.press("Escape");
await page.getByRole("button", { name: "Help", exact: true }).click();
await page.getByRole("menuitem", { name: "Keyboard shortcuts" }).click();
check("shortcuts sheet opens", await page.getByRole("dialog", { name: "Keyboard shortcuts" }).isVisible());
await page.keyboard.press("Escape");

// resizable panels, remembered
const w0 = await page.locator(".ed-left").evaluate((e) => e.getBoundingClientRect().width);
const sp = await page.getByRole("separator", { name: "Resize the browser" }).boundingBox();
await page.mouse.move(sp.x + 3, sp.y + 200);
await page.mouse.down();
await page.mouse.move(sp.x + 103, sp.y + 200, { steps: 5 });
await page.mouse.up();
const w1 = await page.locator(".ed-left").evaluate((e) => e.getBoundingClientRect().width);
check("dragging the splitter resizes the browser", w1 > w0 + 60, `${w0} -> ${w1}`);
await page.reload({ waitUntil: "networkidle" });
const w2 = await page.locator(".ed-left").evaluate((e) => e.getBoundingClientRect().width);
check("the size is remembered", Math.abs(w2 - w1) < 3, `${w1} vs ${w2}`);
await page.getByRole("separator", { name: "Resize the browser" }).dblclick();
const w3 = await page.locator(".ed-left").evaluate((e) => e.getBoundingClientRect().width);
check("double-click resets it", Math.abs(w3 - w0) < 3, `${w3} vs ${w0}`);

await page.screenshot({ path: out + "/e2-ai-sheet.png" });
await page.keyboard.press("Escape");

// the stick-figure choice exists on the New page and in the Settings assistants section
await page.goto(`${base}/new`, { waitUntil: "networkidle" });
await page.getByLabel("Link or script").fill("A short story about a lost wallet.");          // the style choice appears once there is something to make a video from
await page.getByRole("button", { name: /^OK/ }).click();                                // the style question comes next
check("New video offers stick figures", (await page.getByRole("radio", { name: /Stick figures/ }).count()) >= 1);
await page.goto(`${base}/settings`, { waitUntil: "networkidle" });
check("Settings shows the AI provider and assistants", (await page.getByText("AI that directs your videos").count()) === 1 && (await page.getByText("Use your own AI assistant").count()) === 1);
await page.screenshot({ path: out + "/e3-settings-ai.png", fullPage: true });

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
