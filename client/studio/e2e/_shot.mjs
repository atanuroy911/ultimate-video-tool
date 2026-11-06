import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";
const [,, url, out, w = "1440", h = "900"] = process.argv;
const b = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const p = await (await b.newContext({ viewport: { width: +w, height: +h } })).newPage();
await p.goto(base + "/" + url.split("/").filter(Boolean).join("/"), { waitUntil: "networkidle" });
await p.waitForTimeout(1500);
await p.screenshot({ path: out });
await b.close();
