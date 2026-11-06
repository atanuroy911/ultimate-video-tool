import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";
const b = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const p = await (await b.newContext({ viewport: { width: 1100, height: 760 } })).newPage();
await p.goto(base + "/settings", { waitUntil: "networkidle" });
await p.waitForSelector(".engine-card");
await p.waitForTimeout(800);
await p.locator("[data-testid=engines]").screenshot({ path: process.argv[2] });
await b.close();
