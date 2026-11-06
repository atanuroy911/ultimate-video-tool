// What sits on what in a frame, measured on the real page: node frame-facts.mjs <chrome> <composition dir> <times as JSON>. Prints {time: [fact, ...]}.
// These are facts for the director to read. Nothing here changes the video.
import path from "node:path";
import { pathToFileURL } from "node:url";
import puppeteer from "puppeteer-core";

const [, , chrome, compDir, timesJson] = process.argv;
const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ["--no-sandbox", "--disable-gpu", "--allow-file-access-from-files"] });
const page = await browser.newPage();
const data = JSON.parse(await (await import("node:fs/promises")).readFile(path.join(compDir, "data.json"), "utf8"));
await page.setViewport({ width: data.format.width, height: data.format.height });
await page.goto(pathToFileURL(path.join(compDir, "index.html")).href, { waitUntil: "load" });
await page.waitForFunction(() => window.__vt && window.__vt.duration > 0, { timeout: 30000 });
await page.waitForFunction(() => window.__guardDone === true, { timeout: 5000 }).catch(() => {});          // the layout guard has run (it waits for the fonts)
const noRoom = Object.fromEntries((data.scenes || []).filter((s) => s.no_room_beside_person).map((s) => [s.src || s.id, true]));      // scenes whose elements the composer found no free room for beside a person
const out = {};
for (const t of JSON.parse(timesJson)) {
  out[t] = await page.evaluate((at, noRoom) => {
    window.__vt.seek(at);
    const shown = (n) => {
      for (let e = n; e && e.nodeType === 1; e = e.parentElement) {
        const s = getComputedStyle(e);
        if (s.display === "none" || s.visibility === "hidden" || parseFloat(s.opacity) < 0.3) return false;
      }
      const r = n.getBoundingClientRect();
      return r.width > 1 && r.height > 1;
    };
    const area = (r) => Math.max(0, r.right - r.left) * Math.max(0, r.bottom - r.top);
    const both = (a, b) => ({ left: Math.max(a.left, b.left), right: Math.min(a.right, b.right), top: Math.max(a.top, b.top), bottom: Math.min(a.bottom, b.bottom) });
    const part = (a, b) => (area(a) && a.right > b.left && b.right > a.left && a.bottom > b.top && b.bottom > a.top ? area(both(a, b)) / area(a) : 0);
    const W = innerWidth, H = innerHeight, facts = [];
    const faces = [...document.querySelectorAll(".cn-actor")].filter(shown).map((b) => {   // the drawing is 300 by 520: the head is the middle of its top third
      const r = (b.querySelector("svg") || b).getBoundingClientRect();
      return { name: b.getAttribute("data-name") || "a character", body: { left: r.left + r.width * 0.2, right: r.right - r.width * 0.2, top: r.top + r.height * 0.33, bottom: r.bottom }, box: { left: r.left + r.width * 0.25, right: r.right - r.width * 0.25, top: r.top + r.height * 0.05, bottom: r.top + r.height * 0.33 } };
    });
    const els = [...document.querySelectorAll(".el[data-el]")].filter((e) => shown(e) && !e.classList.contains("el-cartoon") && !e.classList.contains("el-story"))
      .map((e) => ({ label: `element ${e.getAttribute("data-el")} (${(/el-(\w+)/.exec(e.className) || [])[1] || "visual"})`, box: e.getBoundingClientRect() }));
    const caps = [...document.querySelectorAll(".cap")].filter(shown).map((e) => ({ label: "the caption", box: (e.querySelector(".cap-inner") || e).getBoundingClientRect() }));
    for (const f of faces) for (const e of [...els, ...caps]) {
      const covered = part(f.box, e.box);
      if (covered > 0.1) facts.push(`${e.label} covers ${Math.round(covered * 100)}% of ${f.name}'s face.`);
      const hidden = part(f.body, e.box);
      if (hidden > 0.08) facts.push(`${e.label} covers ${Math.round(hidden * 100)}% of ${f.name}'s body.`);
    }
    if (faces.length && !facts.length) facts.push("Nothing covers any character.");
    for (const e of els) {
      const r = e.box, kept = area(both(r, { left: 0, top: 0, right: W, bottom: H })) / (area(r) || 1);
      if (kept < 0.9) facts.push(`${e.label} is ${Math.round((1 - kept) * 100)}% outside the frame.`);
      for (const c of caps) if (part(c.box, r) > 0.1) facts.push(`${e.label} overlaps the caption.`);
    }
    for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
      const small = area(els[i].box) < area(els[j].box) ? [els[i], els[j]] : [els[j], els[i]];
      const o = part(small[0].box, small[1].box);
      if (o > 0.2) facts.push(`${small[1].label} covers ${Math.round(o * 100)}% of ${small[0].label}.`);
    }
    // What the layout guard would have done to a scene an AI directed. It did nothing: the director is told instead. Measured on the scene's last frame, when everything has arrived.
    // A finding the measurements above already say (an element outside the frame, one covering another) is not said twice.
    const here = [...document.querySelectorAll(".scene")].find(shown), sceneId = here ? here.dataset.scene : "";
    const add = (text) => { if (!facts.includes(text)) facts.push(text); };
    const said = (...needles) => facts.some((f) => needles.every((n) => f.includes(n)));
    for (const g of window.__guard || []) {
      if (!g.directed) continue;
      if (/^prop:/.test(g.type)) { if (g.scene === sceneId) add(`The prop ${g.type.slice(5)} is cut by the shot: more than a quarter of it is outside the frame.`); continue; }
      if (!els.some((e) => e.label.startsWith(`element ${g.el} (`))) continue;           // on another page of the scene, or not on screen at this moment
      const what = `element ${g.el} (${g.type})`;
      if (g.rule === "cut-off" && !said(what, "outside the frame")) add(`${what} runs off the frame.`);
      else if (g.rule === "too-small") add(`${what} has letters too small to read on a phone.`);
      else if (g.rule === "overlap" && !said(what, `element ${g.with} (`)) add(`${what} overlaps element ${g.with} by more than a fifth of the smaller one.`);
    }
    if (noRoom[sceneId]) add("There is no free room beside the person in the picture for this scene's elements: they sit on the picture.");
    if (facts.some((f) => f !== "Nothing covers any character.")) {             // where a moved element could go
      const taken = [...faces.flatMap((f) => [f.box, f.body]), ...els.map((e) => e.box), ...caps.map((c) => c.box)];
      const free = [];
      for (let y = 0.04; y < 0.82; y += 0.04) {
        const band = { left: W * 0.08, right: W * 0.92, top: H * y, bottom: H * (y + 0.04) };
        if (!taken.some((r) => part(band, r) > 0)) { const last = free[free.length - 1]; if (last && Math.abs(last[1] - y) < 0.001) last[1] = y + 0.04; else free.push([y, y + 0.04]); }
      }
      const room = free.filter(([a, b]) => b - a >= 0.08).map(([a, b]) => `y ${a.toFixed(2)} to ${b.toFixed(2)}`);
      if (room.length) facts.push(`Empty across the frame: ${room.join(", ")}.`);
    }
    return facts;
  }, t, noRoom);
}
await browser.close();
console.log(JSON.stringify(out));
