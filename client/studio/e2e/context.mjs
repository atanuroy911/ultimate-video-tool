// The "What the video is about" panel: it shows the reading, the owner corrects the topic and what a named thing is, and it says when the words changed.
// Uses a project with English names (the talking-head QA project) when there is one, else the reference project.  Scratch server only.  VT_PROJECT=<id> node e2e/context.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const api = async (p, o) => { const r = await fetch(base + p, o); return r.json(); };
const list = await api("/api/projects");
const pid = process.env.VT_PROJECT || (list.find((p) => /qa-a-roll/.test(p.id))?.id) || "reference";
const browser = await chromium.launch({ executablePath: chromePath() });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const wait = async (id) => { for (let i = 0; i < 300; i++) { const j = await api(`/api/jobs/${id}`); if (j.status !== "running" && j.status !== "queued") return j; await new Promise((r) => setTimeout(r, 500)); } };

console.log("Context panel on", pid);
const j = await api(`/api/projects/${pid}/context?ai=false`, { method: "POST" });
check("reading the video works as a job", (await wait(j.id)).status === "done");
const v0 = await api(`/api/projects/${pid}/context`);
check("and gives a topic and sentences", !!v0.context?.topic && v0.context.sentences.length > 0 && v0.stale === false);

await page.goto(`${base}/p/${pid}/pro`, { waitUntil: "networkidle" });
await page.keyboard.press("Escape");                                   // nothing selected: the video's own inspector
await page.getByRole("button", { name: "What the video is about" }).click();
const topic = page.getByRole("textbox", { name: "Topic of the video" });
check("the panel shows the topic", (await topic.inputValue()) === v0.context.topic);
await topic.fill("about my little shop");
await topic.press("Enter");
await page.waitForTimeout(900);
check("a corrected topic is saved and kept", (await api(`/api/projects/${pid}/context`)).context.topic === "about my little shop");

const ents = v0.context.entities;
if (ents.length) {
  const name = ents[0].name;
  const sel = page.getByRole("combobox", { name: `What ${name} is` });
  await sel.selectOption("place");
  await page.waitForTimeout(900);
  const after = (await api(`/api/projects/${pid}/context`)).context.entities.find((e) => e.name === name);
  check(`changing what "${name}" is is saved as the owner's decision`, after.type === "place" && after.source === "owner");
  await page.getByRole("button", { name: `${name} is not a name` }).click();
  await page.waitForTimeout(900);
  check("a wrong name can be removed", !(await api(`/api/projects/${pid}/context`)).context.entities.some((e) => e.name === name));
} else console.log("  skip: this project has no named things");

// a word edit makes the reading out of date
const w = (await api(`/api/projects/${pid}/transcript`)).transcript.words[0];
await fetch(`${base}/api/projects/${pid}/words/${w.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: w.text + "x" }) });
await page.reload({ waitUntil: "networkidle" });
await page.keyboard.press("Escape");
await page.getByRole("button", { name: "What the video is about" }).click();
check("the panel says the words changed", await page.getByText(/words changed since this was read/).isVisible());
await fetch(`${base}/api/projects/${pid}/words/${w.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ restore: true }) });
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
