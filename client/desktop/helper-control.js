/* How the app starts and talks to the helper (helper.js). The app never runs Claude or Codex itself: the helper does, and it stays when the app closes. */
const path = require("path");
const { spawn } = require("child_process");
const { call, readJson } = require("./helper");

const pause = (ms) => new Promise((r) => setTimeout(r, ms));
const runFile = (home) => path.join(home, "helper-run.json");

/** {run, info} of the helper that answers, or null. */
async function status(home) {
  const run = readJson(runFile(home), null);
  const r = await call(run, "GET", "/status");
  return r && r.status === 200 && r.body.role === "helper" ? { run, info: r.body } : null;
}

/** A running helper of this version: started if there is none, and replaced if an older one runs (it keeps running across an update of the app until this stops it).
 *  It is run by the app's own program in Node mode, the way mcp-bridge.js is, detached so it outlives the app. */
async function ensure({ home, helperPath, version, execPath = process.execPath, env = process.env, wait = 12000 }) {
  let have = await status(home);
  if (have && (!version || have.info.version === version)) return have;
  if (have) {
    await call(have.run, "POST", "/stop", {});
    for (let i = 0; i < 25 && (await status(home)); i++) await pause(200);
  }
  const child = spawn(execPath, [helperPath], { detached: true, stdio: "ignore", windowsHide: true, env: { ...env, ELECTRON_RUN_AS_NODE: "1", VT_HELPER_HOME: home } });
  child.on("error", () => {});
  child.unref();
  const began = Date.now();
  while (Date.now() - began < wait) {
    await pause(200);
    have = await status(home);
    if (have) return have;
  }
  throw new Error("The helper did not start.");
}

/** One call to the running helper; throws with its own words when it refuses. */
async function request(home, method, route, body) {
  const have = await status(home);
  if (!have) throw new Error("The helper is not running.");
  const r = await call(have.run, method, route, body, 8000);
  if (!r) throw new Error("The helper did not answer.");
  if (r.status >= 400) throw new Error((r.body && r.body.error) || `The helper said ${r.status}.`);
  return r.body;
}

module.exports = { status, ensure, request };
