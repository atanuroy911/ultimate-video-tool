import { chromium } from "playwright-core";
const b = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", args: ["--disable-gpu"] });
const ctx = await b.newContext({ viewport: { width: 1000, height: 1100 }, colorScheme: "dark" });
await ctx.addCookies([{ name: "vt_token", value: process.env.VT_KEY, url: "http://127.0.0.1:5173" }]);
const p = await ctx.newPage();
const scene = (n, say, a, r, layout, els, req = null) => ({ id: "s" + n, number: n, start: (n - 1) * 5, end: n * 5, narration: say, archetype: a, role: r, layout, transition_in: "fade", transition_effect: "auto", camera_move: "auto", elements: els, request: req });
const view = { title: "Why habits stick", status: "planned", planner: "claude", director: "claude@MSI-LAPTOP", approved: false, approved_at: "", whole_request: null,
  rounds: [{ at: new Date().toISOString(), scene: "s2", note: "show this as a chart", request: "r1" }],
  options: { layouts: ["stack", "split", "hero", "grid", "side", "lower", "upper"], transitions: ["cut", "fade", "slide_up", "slide_left", "zoom", "wipe", "whip"] },
  scenes: [scene(1, "Why do some habits stick while others fade away completely?", "hook", "hook", "hero", ["kinetic title: Why do habits stick?", "icon: brain"]),
           scene(2, "Studies show that 43 percent of daily actions are repeated without thought.", "stat", "number", "split", ["big number: 43%", "bar chart: habit share"], { id: "r1", status: "done", hint: "show this as a chart", error: "", alternatives_available: 2, scene_id: "s2" }),
           scene(3, "So the first rule is to make the cue obvious.", "steps", "step", "stack", ["steps list: 3 items"])] };
await p.route("**/api/projects/demo/script-review", (r) => r.fulfill({ json: view }));
await p.route("**/api/projects/demo/requests/r1/alternatives", (r) => r.fulfill({ json: [{ archetype: "chart", layout: "split", elements: [{ type: "bar_chart", title: "Habit share" }, { type: "big_number", value: "43%" }] }, { archetype: "stat", layout: "hero", elements: [{ type: "big_number", value: "43%" }, { type: "text", text: "of what you do is habit" }] }] }));
await p.goto("http://127.0.0.1:5173/p/demo/script", { waitUntil: "domcontentloaded", timeout: 20000 });
await p.waitForTimeout(3500);
await p.screenshot({ path: "e2e/out/ux-audit/script-review-1.png", fullPage: true });
await p.locator(".sr-scene-head").nth(0).click(); await p.waitForTimeout(500);
await p.screenshot({ path: "e2e/out/ux-audit/script-review-2.png", fullPage: true });
await b.close();
