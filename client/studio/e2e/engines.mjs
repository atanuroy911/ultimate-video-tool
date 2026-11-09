// Server page, AI programs: a card for each program with where it runs and whether it answers; Set up / Change opens a Step 1-2-3 sheet; Test reports in words.
// Reads the scratch server's engine settings and puts them back. Scratch server only (see README).
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const api = async (p, o) => (await fetch(base + p, o)).json();
const before = await api("/api/engines?health=false");
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 1000 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };

console.log("Engines settings");
await page.goto(`${base}/server`, { waitUntil: "networkidle" });   // the engine cards are on the Server page
await page.waitForSelector("[data-testid=engines] .engine-card");
const cards = page.locator("[data-testid=engines] .engine-card[data-engine]");
check("one card for each program in use (another Video Tool computer only once it is linked)", (await cards.count()) === before.filter((e) => e.id !== "vtengine" || e.endpoint.mode !== "off").length && (await cards.count()) >= 2);
const text = await page.getByTestId("engines").innerText();
check("each says where it runs in words", /Writing AI/.test(text) && /Picture AI/.test(text) && /(Not set up|On this server|Installed by Video Tool)/.test(text));
check("no port numbers or JSON on the cards", !/\{|\}/.test(text));

await page.locator(".engine-card[data-engine=comfy]").getByRole("button", { name: /Set up|Change/ }).click();
const dlg = page.getByRole("dialog");
await dlg.waitFor();
await dlg.getByRole("button", { name: "Another computer" }).click();
check("Set up opens a step sheet", (await page.getByText("Step 1 of 3").count()) === 1);
await page.getByRole("button", { name: "Continue" }).click();
check("step 2 asks only for the address (ComfyUI has no key)", (await dlg.getByLabel("Address", { exact: true }).count()) === 1 && (await dlg.getByLabel("Key", { exact: true }).count()) === 0);
await dlg.getByLabel("Address", { exact: true }).fill("http://127.0.0.1:9");
await dlg.getByRole("button", { name: "Continue" }).click();
await dlg.getByRole("button", { name: "Test", exact: true }).click();
await dlg.getByRole("status").waitFor({ timeout: 20000 });
check("a wrong address is reported in words, not as an error page", /Could not reach|didn't answer|not answering/i.test(await dlg.getByRole("status").innerText()), await dlg.getByRole("status").innerText());
await page.screenshot({ path: process.argv[2] ? process.argv[2] + "/engines-sheet.png" : undefined });
await page.getByRole("button", { name: "Cancel" }).click();
check("Cancel changes nothing", JSON.stringify((await api("/api/engines?health=false")).map((e) => e.endpoint)) === JSON.stringify(before.map((e) => e.endpoint)));

// Linking another Video Tool computer and sharing this one are rare: they wait under Advanced (starting is covered by tests/test_hub.py)
check("the Share card is not on the page until Advanced is opened", !(await page.getByTestId("share-card").isVisible()));
await page.getByTestId("server-advanced").locator("summary").click();
check("Advanced offers to share this computer (start, or its address and code when already sharing)", await page.getByTestId("share-card").isVisible() && (await page.getByTestId("share-start").isVisible() || /\d+\.\d+\.\d+\.\d+/.test(await page.getByTestId("share-card").innerText())));

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
