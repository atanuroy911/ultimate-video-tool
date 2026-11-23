// S3 (docs/plans/PLAN-SCENE-TOOLS.MD): a scene's parts by name, and the Studio selecting one from its address. The scene bar lists the scene's parts
// (from /studio/parts); picking one puts selFile/selId in the Studio's address hash, and the Studio selects it without reloading.
//   VT_URL=http://localhost:5174 VT_PROJECT=c2-mix VT_SCENE=s4 VT_PART=s4-defn-term node e2e/studio-parts.mjs
import { chromium } from "playwright-core";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "c2-mix", sid = process.env.VT_SCENE || "s4", want = process.env.VT_PART || "s4-defn-term";
const projects = process.env.VT_PROJECTS || "E:/UltimateVideoTool/scratch/c2-projects";
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };
const api = async (method, url) => (await fetch(base + url, { method })).json();

const s = await api("POST", `/api/projects/${pid}/studio`);                // opening bakes the copy the parts come from
check("the Studio is open", !!s.url, s.url);
const parts = await api("GET", `/api/projects/${pid}/studio/parts?scene=${sid}`);
check("the scene's parts are listed by id", Array.isArray(parts) && parts.some((p) => p.id === want), parts.map?.((p) => p.id).join(", "));
check("only this scene's parts", parts.every((p) => p.scene === sid));
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
await page.goto(s.url.split("?")[0] + "?t=15", { waitUntil: "load" });
await page.waitForTimeout(7000);
const hf = path.resolve("../../server/renderer/node_modules/.bin/hyperframes.cmd");
const selected = () => {
  const out = execFileSync(hf, ["preview", "--selection", "--json", "--port", String(s.port), path.join(projects, pid, "studio-9x16")], { encoding: "utf8", shell: true, env: { ...process.env, HYPERFRAMES_NO_UPDATE_CHECK: "1", HYPERFRAMES_NO_TELEMETRY: "1" } });
  const j = JSON.parse(out.slice(out.indexOf("{"), out.lastIndexOf("}") + 1));
  return j.selection?.target?.id || null;
};
const loads = await page.evaluate(() => performance.getEntriesByType("navigation").length);
const file = parts.find((p) => p.id === want)?.file || "index.html";
check("a scene part is in its scene's own page (S4)", /^scenes\/s\d+/.test(file), file);
await page.evaluate(([id, file]) => { location.hash = location.hash.split("?")[0] + `?t=15&selFile=${encodeURIComponent(file)}&selId=${id}`; }, [want, file]);
await page.waitForTimeout(2500);
const got = selected();
check("the Studio selects the part named in its address", got === want, `selected: ${got}`);
check("without reloading", (await page.evaluate(() => performance.getEntriesByType("navigation").length)) === loads && !(await page.evaluate(() => document.readyState !== "complete")));
await page.screenshot({ path: "e2e/out/s3-part-selected.png" });
await page.evaluate(() => { location.hash = location.hash.split("?")[0] + "?t=15"; });
await browser.close();
await api("DELETE", `/api/projects/${pid}/studio`);
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
