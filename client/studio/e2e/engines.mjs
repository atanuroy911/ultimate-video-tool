// Settings, Engines: a card for each engine with where it runs and whether it answers; Change opens a Step 1-2-3 sheet; Test reports in words; the key is never shown.
// Reads the scratch server's engine settings and puts them back. Scratch server only (see README).
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const api = async (p, o) => (await fetch(base + p, o)).json();
const before = await api("/api/engines?health=false");
const browser = await chromium.launch({ executablePath: chromePath() });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 1000 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };

console.log("Engines settings");
await page.goto(`${base}/settings`, { waitUntil: "networkidle" });
await page.waitForSelector("[data-testid=engines] .engine-card");
const cards = page.locator("[data-testid=engines] .engine-card[data-engine]");
check("one card for each engine", (await cards.count()) === before.length && before.length >= 3);
const text = await page.getByTestId("engines").innerText();
check("each says where it runs in words", /Language AI/.test(text) && /Pictures and clips/.test(text) && /Voices/.test(text));
check("no port numbers or JSON on the cards", !/\{|\}/.test(text));
check("the key is never shown", !(await page.content()).includes("OMNIVOICE_API_KEY"));

await page.locator(".engine-card[data-engine=voicestudio]").getByRole("button", { name: /Change/ }).click();
const dlg = page.getByRole("dialog");
await dlg.waitFor();
await dlg.getByRole("button", { name: "Another computer" }).click();
check("Change opens a step sheet", (await page.getByText("Step 1 of 3").count()) === 1);
await page.getByRole("button", { name: "Continue" }).click();
check("step 2 asks for the address and the key", (await dlg.getByLabel("Address", { exact: true }).count()) === 1 && (await dlg.getByLabel("Key", { exact: true }).count()) === 1);
check("the key field is a password field", (await dlg.getByLabel("Key", { exact: true }).getAttribute("type")) === "password");
await dlg.getByLabel("Address", { exact: true }).fill("http://127.0.0.1:9");
await dlg.getByRole("button", { name: "Continue" }).click();
await dlg.getByRole("button", { name: "Test", exact: true }).click();
await dlg.getByRole("status").waitFor({ timeout: 20000 });
check("a wrong address is reported in words, not as an error page", /Could not reach/.test(await dlg.getByRole("status").innerText()));
await page.screenshot({ path: process.argv[2] ? process.argv[2] + "/engines-sheet.png" : undefined });
await page.getByRole("button", { name: "Cancel" }).click();
check("Cancel changes nothing", JSON.stringify((await api("/api/engines?health=false")).map((e) => e.endpoint)) === JSON.stringify(before.map((e) => e.endpoint)));

// Share this computer (the Engine hub): the card is there and offers to start; starting is covered by tests/test_hub.py
check("the Share this computer card is offered", await page.getByTestId("share-card").isVisible());
check("it offers to start sharing", await page.getByTestId("share-start").isVisible());

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
