// The dashboard: a New video card first, then every video as a cover with one status line; rename, duplicate and delete
// through the card menu. Works on copies it makes itself and deletes them again. Run against a scratch server (see README).
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("response", (r) => r.status() >= 500 && errors.push(r.status() + " " + r.url()));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const api = async (p, opts) => (await fetch(base + p, opts)).json();
const made = [];
const settle = async (f, want) => { for (let i = 0; i < 30; i++) { if ((await f()) === want) return true; await page.waitForTimeout(100); } return false; };

console.log("Dashboard");
for (const p of (await api("/api/projects")).filter((x) => /\(copy\)|Dashboard test/.test(x.title))) await fetch(`${base}/api/projects/${p.id}`, { method: "DELETE" });      // leftovers of an aborted run
await page.goto(base + "/", { waitUntil: "networkidle" });
await page.waitForSelector(".dash2-card");
const total = (await api("/api/projects")).length;
check("one card per video, plus the New video card", (await page.locator(".dash2-card").count()) === total && (await page.locator(".dash2-new").count()) === 1);
check("no filter bar, stats strip or tiles", (await page.locator(".dash-stats, .dash-tiles, .dash-filters").count()) === 0);
check("every card has one status line", (await page.locator(".dash2-status").count()) === total);
check("search only appears once there are many videos", (await page.locator(".dash2-search").count()) === (total >= 9 ? 1 : 0));
await page.locator(".dash2-new").click();
await page.waitForURL(/\/new$/);
check("New video opens the first question", (await page.locator(".tf-question").innerText()).includes("What are we working with"));
await page.goBack();
await page.waitForSelector(".dash2-card");

// duplicate, rename, delete through the card menu
const card = page.locator("article.dash2-card", { hasText: "Reference frame" }).first();
await card.getByRole("button", { name: /Actions for/ }).click();
await page.getByRole("menuitem", { name: "Duplicate" }).click();
await page.waitForSelector("article:has-text('(copy)')");
const copy = (await api("/api/projects")).find((p) => p.title.includes("(copy)"));
made.push(copy.id);
check("duplicate appears as a copy", (await page.locator("article.dash2-card", { hasText: "(copy)" }).count()) === 1);
await page.waitForSelector(".busy-layer", { state: "detached", timeout: 15000 }).catch(() => {});
await page.locator("article.dash2-card", { hasText: "(copy)" }).first().getByRole("button", { name: /Actions for/ }).click();
await page.getByRole("menuitem", { name: /Rename/ }).click();
await page.getByLabel("New name").fill("Dashboard test one");
await page.getByRole("button", { name: "Save", exact: true }).click();
await page.waitForSelector("article:has-text('Dashboard test one')");
check("rename is saved on the server", (await api("/api/projects")).some((p) => p.title === "Dashboard test one"));
check("the newest edit comes first", (await page.locator(".dash2-title").first().innerText()) === "Dashboard test one");
await page.waitForSelector(".busy-layer", { state: "detached", timeout: 15000 }).catch(() => {});
await page.locator("article.dash2-card", { hasText: "Dashboard test one" }).getByRole("button", { name: /Actions for/ }).click();
await page.getByRole("menuitem", { name: /Delete/ }).click();
await page.getByRole("dialog").getByRole("button", { name: "Delete" }).click();
check("delete removes the card", await settle(() => page.locator(".dash2-card").count(), total));
await page.screenshot({ path: out + "/d1-dashboard.png" });

await page.keyboard.press("n");
check("the n key starts a new video", await settle(() => page.url().endsWith("/new"), true));
for (const id of made) await fetch(`${base}/api/projects/${id}`, { method: "DELETE" }).catch(() => {});

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
