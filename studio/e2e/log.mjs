// The director's log ("Details"): hidden until asked, opens with the button and with L, rows in order, filters and search, a step that
// needs something expands to its fix, technical output is off until switched on, the download is a zip of both logs, secrets are redacted.
// Makes its calls on the reference project through the module API. Scratch server only (see README).
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const api = async (p, o) => { const r = await fetch(base + p, o); return r; };
const call = (module, body) => api(`/api/projects/reference/modules/${module}/call`, {
  method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
});
const browser = await chromium.launch({ executablePath: chromePath() });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };

console.log("Director log");
await call("audio.find_retakes", { why: "Look for abandoned openings. token=abc123secret", force: true });
await call("audio.prosody", { inputs: { windows: [[0, 1]] }, why: "Measure the stress." });
await page.goto(`${base}/p/reference/result`, { waitUntil: "networkidle" });
check("the log is hidden until asked", (await page.locator("[data-testid=director-log]").count()) === 0);
await page.getByTestId("log-open").click();
await page.waitForSelector("[data-testid=director-log]");
check("the button opens it", await page.getByRole("dialog", { name: "Details" }).isVisible());
await page.waitForSelector("[data-testid=log-row]");
const rows = await page.locator("[data-testid=log-row]").count();
check("it lists the recorded steps", rows >= 2, `rows=${rows}`);
const seqOrder = await page.locator("[data-testid=log-row] .log-plain").allInnerTexts();
check("each row is a plain sentence", seqOrder.every((t) => t.length > 8 && !t.includes("{")), seqOrder.join(" | "));
check("a step that was told why shows it when opened", await (async () => {
  await page.locator("[data-testid=log-row] .log-head").first().click();
  return (await page.locator(".log-more").first().innerText()).includes("Why:");
})());
check("secrets in the reason are removed", !(await page.locator("[data-testid=director-log]").innerText()).includes("abc123secret"));

await page.getByLabel("Search the log").fill("zzzz-no-such");
check("search narrows the rows", (await page.locator("[data-testid=log-row]").count()) === 0);
await page.getByLabel("Search the log").fill("");
await page.getByRole("button", { name: "Decisions" }).click();
check("Decisions shows the steps that carry a reason", (await page.locator("[data-testid=log-row]").count()) >= 1);
await page.getByRole("button", { name: "Problems" }).click();
await page.getByRole("button", { name: "All", exact: true }).click();

check("technical output is off until switched on", (await page.getByTestId("log-technical").count()) === 0);
await page.getByLabel("Technical output").check();
check("then it appears", await page.getByTestId("log-technical").isVisible());
const zip = await api("/api/projects/reference/calls/download");
check("the download is a zip", zip.headers.get("content-type") === "application/zip" && (await zip.arrayBuffer()).byteLength > 100);

await page.keyboard.press("Escape");
check("Escape closes it", (await page.locator("[data-testid=director-log]").count()) === 0);
await page.keyboard.press("l");
check("the L key opens it", await page.locator("[data-testid=director-log]").isVisible());
await page.waitForTimeout(700);                                          // the sheet slides in
await page.screenshot({ path: process.argv[2] ? process.argv[2] + "/log-sheet.png" : undefined });
await page.keyboard.press("Escape");

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
