// What sits on what in a frame, measured on the real page: node frame-facts.mjs <chrome> <composition dir> <times as JSON>. Prints {time: [fact, ...]}.
// These are facts for the director to read. Nothing here changes the video.
import path from "node:path";
import { pathToFileURL } from "node:url";
import puppeteer from "puppeteer-core";
import { measureFrame } from "./measure-frame.mjs";

const [, , chrome, compDir, timesJson, mode] = process.argv;
const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ["--no-sandbox", "--disable-gpu", "--allow-file-access-from-files"] });
const page = await browser.newPage();
const data = JSON.parse(await (await import("node:fs/promises")).readFile(path.join(compDir, "data.json"), "utf8"));
await page.setViewport({ width: data.format.width, height: data.format.height });
await page.goto(pathToFileURL(path.join(compDir, "index.html")).href, { waitUntil: "load" });
await page.waitForFunction(() => window.__vt && window.__vt.duration > 0, { timeout: 30000 });
await page.waitForFunction(() => window.__guardDone === true, { timeout: 5000 }).catch(() => {});          // the layout guard has run (it waits for the fonts)
const noRoom = Object.fromEntries((data.scenes || []).filter((s) => s.no_room_beside_person).map((s) => [s.src || s.id, true]));      // scenes whose elements the composer found no free room for beside a person
const out = {};
for (const t of JSON.parse(timesJson)) {
  out[t] = await page.evaluate(measureFrame, t, noRoom, mode === "acceptance");
}
await browser.close();
console.log(JSON.stringify(out));
