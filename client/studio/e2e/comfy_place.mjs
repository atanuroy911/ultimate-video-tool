// A generated clip must end up in the finished video: place it from the media bin ("Use in the video"), see it saved on the timeline.
// Usage: VT_URL=... VT_PROJECT=<id> VT_CLIP=<media id> node e2e/comfy_place.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT, clip = process.env.VT_CLIP;
let fails = 0;
const check = (name, ok, extra = "") => { console.log(`${ok ? "PASS" : "FAIL"} ${name} ${ok ? "" : extra}`); if (!ok) fails++; };
const b = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await b.newPage({ viewport: { width: 1280, height: 1000 } });
await page.goto(`${base}/p/${pid}`, { waitUntil: "networkidle" });
await page.getByText("File", { exact: true }).click();
await page.getByRole("menuitem", { name: /Media bin/ }).click();
const section = page.getByLabel("Generate motion clip");
await section.waitFor({ timeout: 20000 });
check("the made clips are listed with their words and seed", /seed \d+/.test(await section.innerText()));
await section.getByRole("button", { name: "Use in the video" }).first().click();
let placed = null;
for (let i = 0; i < 40 && !placed; i++) {
  await page.waitForTimeout(500);
  const doc = await (await fetch(`${base}/api/projects/${pid}/layers`)).json();
  placed = JSON.stringify(doc).match(/clip[0-9a-f]{16}/) ? doc : null;
}
check("the timeline saved a layer that plays the generated clip", !!placed, "no layer with a generated clip id");
console.log("LAYERS", JSON.stringify(placed && (placed.doc || placed)).slice(0, 500));
await b.close();
process.exit(fails ? 1 : 0);
