// O5 (docs/plans/PLAN-OPENMOTION.MD): the HyperFrames Studio inside the desktop app's editor, with the assistant docked beside it. The desktop app,
// started from source and connected to a server on this computer, opens the whole video in the Studio: it loads inside the canvas pane (the app lifts
// the Studio's no-framing rule for this one local page), the assistant stays open, "Back to Video Tool's editor" returns, and closing stops it.
// Needs the client built (npm --prefix client/studio run build) and a server: VT_SERVER=http://127.0.0.1:8791 VT_PROJECT=c2-mix node e2e/desktop-studio.mjs
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { _electron as electron } from "playwright-core";
import { closeDesktop, repo } from "./common.mjs";

const server = process.env.VT_SERVER || "http://127.0.0.1:8791", pid = process.env.VT_PROJECT || "c2-mix";
const desktop = path.join(repo, "desktop");
const exe = createRequire(path.join(desktop, "package.json"))("electron");
const home = fs.mkdtempSync(path.join(os.tmpdir(), "vt-desktop-studio-"));
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };
const env = { ...process.env, UVT_DEV_HOME: home };
delete env.ELECTRON_RUN_AS_NODE;
const app = await electron.launch({ executablePath: exe, args: [desktop, "--server", server], env });
try {
  const page = await app.firstWindow();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
  await page.waitForLoadState("load");
  // the app's own window size (1360 x 880): the Studio must have room in it
  const origin = new URL(page.url()).origin;
  await page.goto(`${origin}/p/${pid}`, { waitUntil: "load" });
  await page.waitForSelector(".wb .wb-viewer", { timeout: 60000 });

  await page.getByRole("button", { name: "Edit in HyperFrames" }).click();
  const frameEl = await page.waitForSelector(".studio-embed iframe", { timeout: 120000 }).catch(() => null);
  check("the Studio opens inside the editor's canvas pane", !!frameEl);
  const frame = frameEl ? await frameEl.contentFrame() : null;
  let text = "";
  for (let i = 0; frame && i < 30 && !/S\d Scene/.test(text); i++) { await page.waitForTimeout(1000); text = await frame.locator("body").innerText().catch(() => ""); }
  check("the Studio loads there (its timeline shows the scenes)", /S\d Scene/.test(text), text.slice(0, 80).replace(/\s+/g, " "));
  const shown = async (t) => frame.getByRole("button", { name: t, exact: true }).first().isVisible().catch(() => false);
  check("the Studio's cloud and product buttons are hidden inside the app", frame && !(await shown("Share")) && !(await shown("Install the desktop app")) && !(await shown("Export")));
  check("in a window this size the Studio gets the room: our toolbar and the assistant step aside", !(await page.locator(".ed-workspace-bar").isVisible()) && !(await page.locator(".wb-assistant-body").isVisible().catch(() => false)));
  const studioBox = await page.locator(".studio-embed").boundingBox();          // the scene bar and the Studio together
  const win = await page.evaluate(() => [window.innerWidth, window.innerHeight]);
  check("the Studio (with its scene bar) fills the window below the title bar", studioBox.width >= win[0] - 4 && studioBox.height >= win[1] - 110, JSON.stringify([studioBox.width, studioBox.height, win]));
  check("the editor's own panels step aside", (await page.locator(".ed-left").count()) === 0 || !(await page.locator(".ed-left").isVisible()));
  await page.screenshot({ path: path.join(repo, "studio", "e2e", "out", "o5-studio-in-the-app.png") });
  // S1: the scene bar above the Studio moves it scene by scene
  const bar = page.getByRole("toolbar", { name: "Scene in HyperFrames" });
  check("a scene bar sits above the Studio", /Scene 1 of \d+/.test(await bar.innerText()), (await bar.innerText()).slice(0, 60));
  const clockOf = async () => ((await frame.locator("body").innerText()).match(/(\d\d):(\d\d)\s*\/\s*\d\d:\d\d/) || []).slice(1).map(Number);
  await bar.getByRole("button", { name: "Next scene" }).click();
  await page.waitForTimeout(1500);
  const scenes = (await page.evaluate(async (u) => (await fetch(u)).json(), `/api/projects/${pid}/scenes`)).timing.scenes;
  const c = await clockOf();
  check("Next scene moves the Studio to scene 2", /Scene 2 of/.test(await bar.innerText()) && c.length === 2 && Math.abs(c[0] * 60 + c[1] - Math.floor(scenes[1].start + 0.05)) <= 1, JSON.stringify([c, scenes[1].start]));
  // S3: the scene's parts by name; picking one selects it in the Studio (through its address: e2e/studio-parts.mjs checks the Studio's side)
  const chips = bar.getByRole("group", { name: "Parts of this scene" }).getByRole("button");
  await chips.first().waitFor({ timeout: 8000 }).catch(() => {});
  const nChips = await chips.count();
  check("the scene bar lists the scene's parts", nChips > 0, String(nChips));
  if (nChips) {
    await chips.first().click();
    await page.waitForTimeout(1500);
    const src = await frameEl.getAttribute("src");
    check("picking a part selects it in the Studio", (await chips.first().getAttribute("aria-pressed")) === "true" && /selId=s\d+/.test(src || ""), (src || "").slice(-60));
    await page.screenshot({ path: path.join(repo, "studio", "e2e", "out", "s3-scene-parts.png") });
    await chips.first().click();
  }
  // the Studio's own agent box opens our Claude Code, started with a note about the selection
  await frame.getByText("Describe a change to the agent").first().click().catch(() => {});
  await page.waitForTimeout(800);
  await page.waitForTimeout(1500);
  const msg = page.getByLabel("Message to Claude Code");
  const v = (await msg.count()) ? await msg.inputValue() : "";
  check("the Studio's ask-the-agent opens the docked Claude Code", /part I selected in the Studio/.test(v), v.slice(0, 60));
  check("the assistant is then docked beside the Studio", await page.locator(".wb-assistant-body").isVisible());
  if (await msg.count()) await msg.fill("");

  // O7: the spoken words are a tab beside the Studio, and a change to the video reaches the open Studio by itself
  await page.getByRole("tab", { name: "Video", exact: true }).click();          // O8: the video's own panels are views of one tab
  await page.getByRole("tab", { name: "Words" }).click();
  await page.waitForTimeout(800);
  check("the Words tab shows the transcript beside the Studio", (await page.locator(".wb-assistant-body").innerText()).length > 50);
  // O7: the talk's outline and the checks are tabs beside the Studio; a time in them moves the Studio there
  {
    const sc = (await page.evaluate(async (u) => (await fetch(u)).json(), `/api/projects/${pid}/scenes`)).timing.scenes;
    const outFile = path.join(process.env.VT_PROJECTS || "E:/UltimateVideoTool/scratch/c2-projects", pid, "talk_outline.json");
    const ex = sc[Math.min(3, sc.length - 1)];
    fs.writeFileSync(outFile, JSON.stringify({ sections: [{ first: 1, last: 9, point: "Why the battery dies", start: 0, end: sc[sc.length - 1].end }],
      examples: [{ kind: "case", about: "Always-on display", show: "a watch face glowing at night", start: ex.start + 0.2, end: ex.end }], keep_on_speaker: [], summary: "" }));
    try {
      await page.getByRole("tab", { name: "Outline" }).click();
      const pane = page.locator(".wb-assistant-body");
      await pane.getByText("Always-on display").waitFor({ timeout: 10000 }).catch(() => {});
      check("the Outline tab lists the talk's sections and examples", /Why the battery dies/.test(await pane.innerText()) && /Always-on display/.test(await pane.innerText()));
      await pane.locator(".studio-examples li", { hasText: "Always-on display" }).getByRole("button").first().click();
      await page.waitForTimeout(1500);
      const c2 = ((await frame.locator("body").innerText()).match(/(\d\d):(\d\d)\s*\/\s*\d\d:\d\d/) || []).slice(1).map(Number);
      check("a time in the outline moves the Studio there", c2.length === 2 && Math.abs(c2[0] * 60 + c2[1] - Math.floor(ex.start + 0.2)) <= 1, JSON.stringify([c2, ex.start]));
      await page.getByRole("tab", { name: "Checks" }).click();
      await pane.getByText("Skipped extras").waitFor({ timeout: 10000 }).catch(() => {});
      check("the Checks tab shows the retention check and the skipped extras", /Will viewers stay/.test(await pane.innerText()) && /Skipped extras/.test(await pane.innerText()));
      await page.screenshot({ path: path.join(repo, "studio", "e2e", "out", "o7-outline-checks.png") });
      // O8: the plan's scenes beside HyperFrames: picking one moves HyperFrames there, and its menu has the plan-level actions
      await page.getByRole("tab", { name: "Scenes" }).click();
      const card = pane.getByRole("group", { name: "Scene 3" });
      await card.waitFor({ timeout: 10000 }).catch(() => {});
      await card.click({ position: { x: 20, y: 12 } });
      await page.waitForTimeout(1500);
      const c3 = ((await frame.locator("body").innerText()).match(/(\d\d):(\d\d)\s*\/\s*\d\d:\d\d/) || []).slice(1).map(Number);
      check("the Scenes tab beside HyperFrames moves it to the scene picked", c3.length === 2 && Math.abs(c3[0] * 60 + c3[1] - Math.floor(sc[2].start + 0.05)) <= 1, JSON.stringify([c3, sc[2].start]));
      await pane.getByRole("button", { name: "Scene 3 actions" }).click();
      await page.waitForTimeout(400);
      const menuText = await page.locator("body").innerText();
      check("the scene's plan actions are there (Director, pictures, HyperFrames)", /Pictures for this scene/.test(menuText) && /Edit this scene in HyperFrames/.test(menuText));
      await page.keyboard.press("Escape");
      const empty = [];
      for (const v of ["Direction", "Script", "Sound", "Media"]) {          // every panel of the old editor has a place beside HyperFrames
        await page.getByRole("tablist", { name: "What to see beside HyperFrames" }).getByRole("tab", { name: v }).click();
        await page.waitForTimeout(900);
        if ((await pane.innerText()).replace(/\s+/g, " ").length < 120) empty.push(v);
      }
      check("Direction, Script, Sound and Media open beside HyperFrames", !empty.length, empty.join(", "));
      await page.screenshot({ path: path.join(repo, "studio", "e2e", "out", "o8-video-views.png") });
    } finally { fs.rmSync(outFile, { force: true }); }
  }
  const api = (m, u, body) => page.evaluate(async ([m, u, body]) => (await fetch(u, { method: m, headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined })).json(), [m, u, body]);
  const plan0 = (await api("GET", `/api/projects/${pid}/scenes`)).plan.scenes.find((x) => x.id === "s5");
  const items0 = plan0.elements[0].items;
  await api("PATCH", `/api/projects/${pid}/scenes/s5/elements/0`, { items: [{ ...items0[0], title: "App notifications" }, ...items0.slice(1)] });
  const copyDir = path.join(process.env.VT_PROJECTS || "E:/UltimateVideoTool/scratch/c2-projects", pid, "studio-9x16");
  const copyText = () => [path.join(copyDir, "index.html"), ...(fs.existsSync(path.join(copyDir, "scenes")) ? fs.readdirSync(path.join(copyDir, "scenes")).map((f) => path.join(copyDir, "scenes", f)) : [])].map((f) => fs.readFileSync(f, "utf8")).join("\n");   // the root and each scene page (S4)
  let reached = false;
  for (let i = 0; i < 40 && !reached; i++) { await page.waitForTimeout(1000); reached = copyText().includes("App notifications"); }
  check("a change to the video reaches the open Studio's copy by itself", reached);
  await api("PATCH", `/api/projects/${pid}/scenes/s5/elements/0`, { items: items0 });
  await page.waitForTimeout(7000);
  await bar.getByRole("button", { name: "Back to the editor" }).click();
  await page.waitForTimeout(800);
  check("Back to the editor shows Video Tool's canvas again", (await page.locator(".studio-embed").count()) === 0);
  await page.getByRole("button", { name: "HyperFrames open" }).click();
  await page.getByRole("menuitem", { name: "Close the Studio" }).click();
  await page.waitForTimeout(2000);
  const st = await page.evaluate(async (u) => (await fetch(u)).json(), `/api/projects/${pid}/studio`);
  check("closing stops the Studio", st.open === false, JSON.stringify(st).slice(0, 120));
  console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
} finally {
  await closeDesktop(app, home);
}
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
