// The Sounds lane: a project that has not been listened to offers it; after listening the lane says what it found (the reference voice is synthetic, so: nothing).
// Mutating (writes sounds_events.json): scratch server only.  VT_PROJECT=<id> node e2e/sounds.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "reference";
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const api = async (p) => (await fetch(base + p)).json();

console.log("Sounds lane");
const st = await api(`/api/projects/${pid}/sound-events`);
check("the API says whether the listener is available", typeof st.available === "boolean");
if (!st.available) { console.log("  skip: the listener (torch + transformers) is not installed"); process.exit(0); }
check("a new project has not been listened to", st.analyzed === false);
await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
await page.waitForSelector(".tl-clip", { timeout: 45000 });
const btn = page.getByRole("button", { name: /Listen for laughter/ });
check("the Sounds lane offers to listen", await btn.isVisible());
await btn.click();
await page.getByText(/No sounds other than speech were found/).waitFor({ timeout: 240000 }).catch(() => {});
check("after listening the lane reports what it found", await page.getByText(/No sounds other than speech were found/).isVisible());
const after = await api(`/api/projects/${pid}/sound-events`);
check("and the result is stored", after.analyzed === true && Array.isArray(after.events));

// events in the lane: write two by hand through the file the API reads, then reload
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
