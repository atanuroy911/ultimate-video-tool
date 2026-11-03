// Debug helper: opens a generated composition and prints the page's script errors.  node e2e/_comp_errors.mjs <path to index.html>
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";
import { pathToFileURL } from "node:url";
import path from "node:path";

const browser = await chromium.launch({ executablePath: chromePath() });
const page = await browser.newPage();
page.on("pageerror", (e) => console.log("PAGEERROR", e.message.slice(0, 300), (e.stack || "").split("\n").slice(0, 4).join(" | ")));
page.on("console", (m) => m.type() === "error" && console.log("CONSOLE", m.text().slice(0, 300)));
await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);
await page.waitForTimeout(1500);
console.log("loaded");
for (const t of [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5]) { await page.evaluate((t) => window.__timelines.root.seek(t), t); await page.waitForTimeout(150); console.log("seek", t); }
await browser.close();
