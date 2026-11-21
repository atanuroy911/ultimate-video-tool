/* Every file the app loads from its own folder must be in the installer's file list (package.json build.files, a whitelist). A file that is missing there works
   from source and breaks the installed app at startup: found 2026-11-20, when server-keys.js was added but not listed. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const pkg = require("./package.json");
const listed = new Set(pkg.build.files);
const entry = ["main.js", "helper.js", "preload.js", "main-preload.js"];
const seen = new Set();
const queue = [...entry];
while (queue.length) {
  const file = queue.pop();
  if (seen.has(file)) continue;
  seen.add(file);
  assert(listed.has(file), `${file} is loaded by the app but missing from package.json build.files`);
  assert(fs.existsSync(path.join(__dirname, file)), `${file} is listed but does not exist`);
  if (!file.endsWith(".js")) continue;
  const text = fs.readFileSync(path.join(__dirname, file), "utf8");
  for (const m of text.matchAll(/require\(\s*['"]\.\/([\w.-]+)['"]\s*\)/g)) queue.push(/\.(js|json|html)$/.test(m[1]) ? m[1] : m[1] + ".js");
  for (const m of text.matchAll(/path\.join\(__dirname,\s*['"]([\w.-]+\.(?:html|js))['"]\)/g)) queue.push(m[1]);
}
console.log(`Packaging: all ${seen.size} files the app loads are in the installer list.`);
