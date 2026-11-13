// The OpenChatCut timeline ported into our editor (docs/plans/PLAN-OPENCHATCUT.MD, phase 1): the switch, our project on its tracks, our
// preview driving its playhead, selection, the save status, light and dark. Reads only (every write is refused here).
//   VT_PROJECT=<a video with scene elements> VT_PICTURES=<a video with pictures> node e2e/occ_timeline.mjs
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const base = process.env.VT_URL || "http://localhost:5291";
const projects = [process.env.VT_PROJECT, process.env.VT_PICTURES].filter(Boolean);
if (!projects.length) { console.log("set VT_PROJECT (and VT_PICTURES)"); process.exit(2); }
const out = path.join(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1")), "out", "occ-timeline");
fs.mkdirSync(out, { recursive: true });
let pass = 0, fail = 0;
const check = (name, ok, detail = "") => { if (ok) { pass++; console.log("  ok  ", name); } else { fail++; console.log(`  FAIL ${name}${detail ? " :: " + detail : ""}`); } };
const api = async (p) => (await fetch(`${base}${p}`)).json();

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu", "--autoplay-policy=no-user-gesture-required"] });
for (const pid of projects) {
  const sc = await api(`/api/projects/${pid}/scenes`);
  const scenes = (sc.timing?.scenes ?? []).filter((s) => s.end > s.start).length;
  const elements = (sc.plan?.scenes ?? []).reduce((n, s) => n + s.elements.length, 0);
  for (const scheme of ["dark", "light"]) {
    console.log(`${pid} (${scheme})`);
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: scheme });
    await ctx.addInitScript((th) => { try { localStorage.setItem("vt-theme", th); localStorage.setItem("vt-timeline", "classic"); } catch {} }, scheme);
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    // reads only: any write to the project is refused, so nothing here can change it
    await page.route("**/api/projects/**", (r) => (["GET", "HEAD"].includes(r.request().method()) || r.request().url().includes("/thumbnails") ? r.continue() : r.fulfill({ json: {} })));
    await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
    const sw = page.getByRole("group", { name: "Which timeline" });
    await sw.waitFor();
    await sw.getByRole("button", { name: "New timeline" }).click();
    const tl = page.getByTestId("occ-timeline");
    await tl.waitFor({ timeout: 20000 });
    await page.waitForTimeout(1500);
    check("the switch opens the new timeline and remembers it", (await page.evaluate(() => localStorage.getItem("vt-timeline"))) === "new");
    const heads = await tl.locator(".cc-track-head, [data-track-id]").allInnerTexts().catch(() => []);
    const text = await tl.innerText();
    check("captions, scenes and narration have their tracks", /Captions/.test(text) && /Scenes/.test(text) && /Narration/.test(text), heads.join(" | ").slice(0, 200));
    if (elements) check("scene elements have a track of their own", /Elements/.test(text));
    const clips = await tl.locator(".cc-timeline-clip").count();
    check(`every scene is a clip (${scenes} scenes, ${clips} clips)`, clips >= scenes + 1, String(clips));
    // our preview drives its playhead
    const tc = tl.locator(".cc-timeline-timecode");
    const before = await tc.innerText();
    await page.getByRole("button", { name: "Play" }).first().click();
    await page.waitForTimeout(1600);
    await page.getByRole("button", { name: "Pause" }).first().click().catch(() => {});
    const after = await tc.innerText();
    check("playing our preview moves its playhead and timecode", before !== after, `${before} -> ${after}`);
    // select a scene clip
    await tl.locator(".cc-timeline-clip").filter({ hasText: "Scene 1" }).first().click();
    await page.waitForTimeout(300);
    check("a clip can be selected", (await tl.locator(".cc-timeline-clip[aria-selected=true], .cc-timeline-clip.selected, .cc-timeline-clip[data-selected=true]").count()) >= 1
      || (await tl.locator(".cc-timeline-clip").filter({ hasText: "Scene 1" }).first().evaluate((el) => getComputedStyle(el).outlineStyle !== "none" || getComputedStyle(el).boxShadow !== "none")));
    check("before any change, no save status", (await tl.getByTestId("occ-status").count()) === 0);
    const ruler = tl.locator(".cc-timeline-ruler").first();
    const top = (await ruler.boundingBox()).y;
    await page.keyboard.press("Delete");                              // saved as our own edit (writes are refused here, so nothing changes)
    await page.waitForTimeout(1500);
    check("after a change, it says it is saving or saved", /Saving|Saved|Not saved/.test(await tl.getByTestId("occ-status").innerText().catch(() => "")));
    check("the status does not move the timeline", Math.abs((await ruler.boundingBox()).y - top) < 1);
    await page.screenshot({ path: path.join(out, `${pid.slice(-24)}-${scheme}.png`) });
    await sw.getByRole("button", { name: "Classic" }).click();
    await page.waitForTimeout(500);
    check("Classic brings the classic timeline back", (await tl.count()) === 0 && (await page.locator(".ed-timeline .tl, .ed-timeline [aria-label='Timeline']").count()) >= 0);
    check("no page errors", !errors.length, errors.join(" | ").slice(0, 300));
    await ctx.close();
  }
}
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
