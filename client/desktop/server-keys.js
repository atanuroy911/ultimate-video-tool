/* The keys of the servers this computer connects to (docs/plans/PLAN-WORKBENCH.MD, W2.4). A server asks another computer for its key by default; the person
 * pastes it once on the connect page and it is kept here, in a file only this user can read, next to the app's other files. It is sent by the app's own
 * connection (transport.js) and handed to the helper: the page in the window never sees it. */
const fs = require("fs");
const http = require("http");
const https = require("https");

function read(file) {
  try {
    const data = JSON.parse(fs.readFileSync(file, "utf8"));
    return data && typeof data === "object" && !Array.isArray(data) ? data : {};
  } catch { return {}; }
}

/** The key kept for a server (its origin, like http://192.168.1.20:8790), or "". */
function keyFor(file, origin) {
  const key = read(file)[origin];
  return typeof key === "string" ? key : "";
}

function saveKey(file, origin, key) {
  const all = read(file);
  if (key) all[origin] = key; else delete all[origin];
  fs.writeFileSync(file, JSON.stringify(all), { mode: 0o600 });
  try { fs.chmodSync(file, 0o600); } catch { /* Windows: the user's own folder */ }
}

/** What the server says to this key: "ok", "refused" (it answered 401) or "unreachable". */
function check(origin, key, ms = 5000) {
  return new Promise((resolve) => {
    const lib = origin.startsWith("https:") ? https : http;
    const headers = key ? { Authorization: `Bearer ${key}` } : {};
    const req = lib.get(origin + "/api/health", { headers, timeout: ms }, (res) => {
      res.resume();
      res.on("end", () => resolve(res.statusCode === 401 ? "refused" : res.statusCode < 400 ? "ok" : "unreachable"));
    });
    req.on("error", () => resolve("unreachable"));
    req.on("timeout", () => { req.destroy(); resolve("unreachable"); });
  });
}

/** A key as typed: no spaces or line breaks around it, a sensible length. */
function clean(text) {
  const key = String(text || "").trim();
  if (key.length > 512 || /[\s\u0000-\u001f]/.test(key)) throw new Error("That is not a key. Paste it exactly as the server window copied it.");
  return key;
}

module.exports = { keyFor, saveKey, check, clean };
