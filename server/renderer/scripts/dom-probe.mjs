// What the real page says: node dom-probe.mjs <chrome> <composition dir> <time in seconds> <JavaScript expression>. Opens the composition the way the renderer does (a headless browser,
// software drawing), seeks to the time, optionally saves a screenshot (a fifth argument: the file) and prints {"result": <what the expression returned>} as JSON. For checks of what the page really does, in tests and in the pipeline's own
// bookkeeping (the layout guard's log). It changes nothing in the composition.
import path from "node:path";
import { pathToFileURL } from "node:url";
import puppeteer from "puppeteer-core";

const [, , chrome, compDir, time, expression, shot] = process.argv;
const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ["--no-sandbox", "--disable-gpu", "--allow-file-access-from-files"] });
try {
  const page = await browser.newPage();
  const data = JSON.parse(await (await import("node:fs/promises")).readFile(path.join(compDir, "data.json"), "utf8"));
  await page.setViewport({ width: data.format.width, height: data.format.height });
  await page.goto(pathToFileURL(path.join(compDir, "index.html")).href, { waitUntil: "load" });
  await page.waitForFunction(() => window.__vt && window.__vt.duration > 0, { timeout: 30000 });
  await page.waitForFunction(() => window.__guardDone === true, { timeout: 5000 }).catch(() => {});          // the layout guard has run (it waits for the fonts)
  await page.evaluate((at) => window.__vt.seek(at), Number(time));
  const result = await page.evaluate(expression);
  if (shot) await page.screenshot({ path: shot });                         // the page as the viewer's browser draws it (tests compare it with the export's frame)
  console.log(JSON.stringify({ result: result === undefined ? null : result }));
} finally {
  await browser.close();
}
