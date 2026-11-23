// Runs without VS Code: the helpers are plain functions.
const Module = require("module");
const orig = Module._load;
Module._load = function (r, ...a) { return r === "vscode" ? { commands: {}, window: {}, workspace: {}, ViewColumn: {} } : orig.call(this, r, ...a); };
const { clean, page } = require("./extension.js");
const assert = require("assert");
assert.strictEqual(clean("a/../b c"), "a..bc");
const html = page("http://127.0.0.1:8790/x");
assert(html.includes("sandbox=\"allow-scripts\"") && html.includes("frame-src http://127.0.0.1:8790"));
console.log("VS Code extension helpers pass.");
