import { chromium } from "playwright-core";
import http from "node:http"; import fs from "node:fs"; import path from "node:path";
const dir = process.argv[2];
const srv = http.createServer((q, r) => { const f = path.join(dir, decodeURIComponent(q.url.split("?")[0])); fs.readFile(f, (e, d) => { r.writeHead(e ? 404 : 200); r.end(d); }); }).listen(8137);
const b = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", args: ["--disable-gpu"] });
const p = await b.newPage({ viewport: { width: 1200, height: 1100 } });
p.on("pageerror", (e) => console.log("PAGEERROR", e.message)); p.on("console", (m) => m.type() === "error" && console.log("CONSOLE", m.text()));
for (const [name, q] of [["tall", "w=270&h=480"], ["wide", "w=384&h=216"]]) {
  await p.goto(`http://127.0.0.1:8137/page.html?${q}`); await p.waitForFunction(() => document.title === "done", null, { timeout: 15000 });
  await p.waitForTimeout(300); await p.screenshot({ path: path.join(dir, name + ".png"), fullPage: true });
}
await b.close(); srv.close();
