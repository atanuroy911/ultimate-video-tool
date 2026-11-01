import { chromium } from "playwright-core";
import { pathToFileURL } from "node:url";
import { chromePath } from "./common.mjs";
const b = await chromium.launch({ executablePath: chromePath() });
const p = await b.newPage();
p.on("pageerror", (e) => console.log("PAGEERROR", e.message, (e.stack || "").split("\n").slice(0, 3).join(" | ")));
await p.goto(pathToFileURL(process.argv[2]).href);
await p.waitForTimeout(3000);
await b.close();
