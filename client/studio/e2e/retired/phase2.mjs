// Phase 2 in the real Studio: kind of video, the media bin, "Show as", backdrop with contrast scrim, stock keys.
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: chromePath() });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("response", (r) => r.status() >= 400 && !/\/api\/(projects\/reference\/scenes\/s\d+\/reshow)/.test(r.url()) && errors.push(r.status() + " " + r.url()));

let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { if (cond) { pass++; console.log("  ok  ", name); } else { fail++; console.log("  FAIL", name, extra); } };
const api = async (p, opts) => (await fetch(base + p, opts)).json();
const frame = () => page.frames().find((f) => f.url().includes("/composition/9x16/"));

// a small noisy PNG made without extra libraries
function png(w, h) {
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) { raw[y * (w * 3 + 1)] = 0; for (let x = 0; x < w * 3; x++) raw[y * (w * 3 + 1) + 1 + x] = ((x * 7 + y * 13) % 5) * 60; }
  const crc = (buf) => { let c, t = []; for (let n = 0; n < 256; n++) { c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } let r = 0xffffffff; for (const b of buf) r = t[(r ^ b) & 255] ^ (r >>> 8); return (r ^ 0xffffffff) >>> 0; };
  const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}
const pic = path.join(out, "e2e-photo.png");
fs.writeFileSync(pic, png(320, 240));

console.log("New video: kind of video and pictures");
await page.goto(base + "/new", { waitUntil: "networkidle" });
await page.waitForSelector("[aria-label='Kind of video']");
const kinds = await page.locator("[aria-label='Kind of video'] button").allInnerTexts();
check("six kinds of video are offered", kinds.length === 6 && kinds.includes("Product showcase") && kinds.includes("Storytelling") && kinds.includes("Discussion") && kinds.includes("Education"), kinds.join(","));
await page.locator("[aria-label='Kind of video'] button", { hasText: "Education" }).click();
check("choosing one marks it", (await page.locator("[aria-label='Kind of video'] button[aria-checked=true]").innerText()) === "Education");
await page.locator("input[type=file][multiple]").first().setInputFiles(pic);
check("a picture can be attached before generating", (await page.getByText("e2e-photo.png").count()) >= 1);
await page.screenshot({ path: out + "/p2-new.png" });

console.log("Review: kind of video, media bin, show as");
await page.goto(base + "/p/reference/pro", { waitUntil: "networkidle" });
await page.waitForSelector(".scene-card");
await page.locator(".ed").click({ position: { x: 5, y: 5 } });
await page.keyboard.press("Escape");                       // nothing selected: the inspector shows the video's settings
const sel = page.getByLabel("Kind of video").last();
await sel.selectOption("product");
await page.waitForTimeout(600);
check("the kind of video is saved on the project", (await api("/api/projects/reference")).usecase === "product");
await sel.selectOption("auto");

await page.getByRole("tab", { name: /^Media/ }).click();
await page.getByRole("button", { name: "Open the media bin" }).click();
await page.waitForSelector("[aria-label='Media bin']");
await page.locator(".modal input[type=file]").setInputFiles(pic);
await page.waitForSelector(".media-card img", { timeout: 20000 });
check("an uploaded picture appears in the bin", (await page.locator(".media-card img").count()) === 1);
const mid = (await api("/api/projects/reference/media"))[0].id;
await page.locator(".modal input.bn").first().fill("our shop front");
await page.locator(".modal input.bn").first().blur();
await page.waitForTimeout(500);
check("its caption is saved", (await api("/api/projects/reference/media"))[0].caption === "our shop front");
await page.screenshot({ path: out + "/p2-bin.png" });
await page.getByRole("button", { name: "Done" }).click();

await page.getByRole("tab", { name: /^Scenes/ }).click();
await page.locator(".scene-card").nth(1).click();
await page.waitForSelector("[aria-label='Show this scene as']");
const optsBefore = await page.locator("[aria-label='Show this scene as'] button").allInnerTexts();
check("scene types are offered (including the picture types now that a picture exists)", optsBefore.length >= 2 && optsBefore.includes("Full-screen picture"), optsBefore.join(","));
await page.locator("[aria-label='Show this scene as'] button", { hasText: "Full-screen picture" }).click();
await page.waitForTimeout(2500);
const sc = (await api("/api/projects/reference/scenes")).plan.scenes[1];
check("the scene now has the picture as a backdrop with a computed scrim", sc.archetype === "media_hero" && sc.backdrop && sc.backdrop.media === mid && sc.backdrop.scrim.ratio >= 4.5, JSON.stringify(sc.backdrop));
let info = { bd: 0, ink: false };
for (let i = 0; i < 24 && !info.bd; i++) {                       // the preview hot-swaps its data a moment after the plan changes
  await page.waitForTimeout(500);
  info = await (frame() || { evaluate: async () => info }).evaluate(() => ({ bd: document.querySelectorAll(".bd-media").length, ink: !!document.querySelector(".ink-light, .ink-dark") })).catch(() => info);
}
check("the preview draws the backdrop and the chosen text colour", info.bd === 1 && info.ink, JSON.stringify(info));
await page.screenshot({ path: out + "/p2-showas.png" });
await page.locator("[aria-label='Show this scene as'] button[aria-pressed=false]").first().click();     // another type, then undo everything
await page.waitForTimeout(1500);
await page.keyboard.press("Control+z");
await page.waitForTimeout(800);

console.log("Settings: stock keys");
await page.goto(base + "/settings", { waitUntil: "networkidle" });
await page.waitForSelector("[aria-label='Stock media']");
await page.locator("[aria-label='Stock media'] input[type=password]").first().fill("e2e-secret-key");
await page.locator("[aria-label='Stock media'] input[type=password]").first().blur();
await page.waitForTimeout(800);
const st = await api("/api/stock/status");
const raw = await (await fetch(base + "/api/settings")).text();
check("a key is saved and reported as set, but never sent back", st.pexels === true && !raw.includes("e2e-secret-key"));
await fetch(base + "/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pexels_key: "" }) });

// leave the reference project as we found it
await fetch(`${base}/api/projects/reference/media/${mid}`, { method: "DELETE" });
const reset = await api("/api/projects/reference/scenes");
if (reset.plan.scenes[1].backdrop) await fetch(base + "/api/projects/reference/scenes/undo", { method: "POST" });
await fetch(base + "/api/projects/reference/plan-notice", { method: "DELETE" });

console.log(`\n${pass} passed, ${fail} failed`);
console.log("ERRORS:", errors.length ? "\n" + errors.join("\n") : "none");
await browser.close();
process.exit(fail ? 1 : 0);
