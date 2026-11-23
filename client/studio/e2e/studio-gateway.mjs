// The HyperFrames Studio for a person on another computer (vt/server/studio_gateway.py), in a real browser. The server is asked as another computer
// would ask (with its key and a forwarding header, so it does not count as this computer): it answers with the gateway's address and a ticket. The
// browser opens that address: the ticket becomes a cookie and the real Studio loads through the gateway (its pages, scripts and event streams).
//   VT_SERVER=http://127.0.0.1:8791 (started with VT_STUDIO_GATEWAY=1) VT_PROJECT=c2-mix node e2e/studio-gateway.mjs
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const server = process.env.VT_SERVER || "http://127.0.0.1:8791", pid = process.env.VT_PROJECT || "c2-mix";
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };
const key = (await (await fetch(`${server}/api/server/key`)).json()).key;
const asElsewhere = { authorization: `Bearer ${key}`, "x-forwarded-for": "192.168.1.50" };      // what a client on another computer sends (via its proxy)
const opened = await (await fetch(`${server}/api/projects/${pid}/studio`, { method: "POST", headers: asElsewhere })).json();
check("another computer gets the Studio's gateway address with a ticket", /^http:\/\/127\.0\.0\.1:\d+\/\?vt_ticket=[\w-]+#project\/studio-9x16$/.test(opened.url || ""), opened.url);
const here = await (await fetch(`${server}/api/projects/${pid}/studio`)).json();
check("this computer still gets the Studio itself", /^http:\/\/127\.0\.0\.1:\d+\/#project\//.test(here.url || "") && !/vt_ticket/.test(here.url), here.url);

const gate = new URL(opened.url).origin;
check("without the ticket's cookie or the key the gateway refuses another computer",
  (await fetch(`${gate}/`, { headers: { "x-forwarded-for": "192.168.1.50" } })).status === 401);

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
const streams = [];
page.on("response", (r) => { if ((r.headers()["content-type"] || "").includes("text/event-stream")) streams.push(r.url()); });
await page.goto(opened.url, { waitUntil: "load" });
await page.waitForTimeout(9000);
check("the ticket became the gateway's cookie and the address lost it", !/vt_ticket/.test(page.url()) && /#project\/studio-9x16/.test(page.url()), page.url());
const text = await page.locator("body").innerText();
check("the real Studio loads through the gateway (compositions, timeline)", /Compositions/.test(text) && /Scene S\d/.test(text), text.slice(0, 80).replace(/\s+/g, " "));
check("its live event stream comes through too", streams.some((u) => u.startsWith(gate)), streams[0] || "none");
await page.screenshot({ path: "e2e/out/studio-gateway.png" });
await browser.close();
await fetch(`${server}/api/projects/${pid}/studio`, { method: "DELETE" });
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
