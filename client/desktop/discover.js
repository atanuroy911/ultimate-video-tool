/* Finding Video Tool servers on this network from the desktop app (the server side is vt/server/discovery.py).
 * Asks once by UDP broadcast on every IPv4 network this computer is on and collects the answers; no extra package needed.
 */
const dgram = require("dgram");
const os = require("os");
const http = require("http");
const https = require("https");

const UDP_PORT = 8767;
const ASK = Buffer.from("VIDEO-TOOL? 1");

function broadcasts() {
  const out = new Set(["255.255.255.255"]);
  for (const list of Object.values(os.networkInterfaces())) {
    for (const a of list || []) {
      if (a.family !== "IPv4" && a.family !== 4) continue;
      if (a.internal) continue;
      const ip = a.address.split(".").map(Number);
      const mask = a.netmask.split(".").map(Number);
      out.add(ip.map((b, i) => (b | (~mask[i] & 255))).join("."));
    }
  }
  return [...out];
}

/** [{name, url, version}] for every server that answers within `ms`. */
function find(ms = 2000, targets = broadcasts(), port = UDP_PORT) {
  return new Promise((resolve) => {
    const found = new Map();
    const s = dgram.createSocket({ type: "udp4", reuseAddr: true });
    const done = () => { try { s.close(); } catch { /* closed */ } resolve([...found.values()].sort((a, b) => a.name.localeCompare(b.name))); };
    s.on("error", done);
    s.on("message", (msg, rinfo) => {
      try {
        const c = JSON.parse(String(msg));
        if (c.app !== "video-tool" || !Number.isInteger(c.port)) return;
        const url = `http://${rinfo.address}:${c.port}`;
        if (!found.has(url)) found.set(url, { name: String(c.name || rinfo.address), url, version: String(c.version || "") });
      } catch { /* not ours */ }
    });
    s.bind(0, () => {
      s.setBroadcast(true);
      for (const t of targets) s.send(ASK, port, t, () => {});
      setTimeout(done, ms);
    });
  });
}

/** What a typed address says about itself ({name, url, needsKey}: whether this computer must bring the server's key), or null when no Video Tool server answers there. Adds http:// and the usual port when missing. */
function probe(address, ms = 4000) {
  let url = String(address || "").trim().replace(/\/+$/, "");
  if (!url) return Promise.resolve(null);
  if (!/^https?:\/\//i.test(url)) url = "http://" + url;
  try {
    const u = new URL(url);
    if (!u.port && u.protocol === "http:") u.port = "8790";
    url = u.origin;
  } catch { return Promise.resolve(null); }
  return new Promise((resolve) => {
    const lib = url.startsWith("https:") ? https : http;
    const r = lib.get(url + "/.well-known/video-tool", { timeout: ms }, (res) => {
      let body = "";
      res.on("data", (b) => { body += b; });
      res.on("end", () => {
        try {
          const c = JSON.parse(body);
          resolve(c.app === "video-tool" ? { name: c.name || url, url, needsKey: c.needs_key === true } : null);
        } catch { resolve(null); }
      });
    });
    r.on("error", () => resolve(null));
    r.on("timeout", () => { r.destroy(); resolve(null); });
  });
}

module.exports = { find, probe, broadcasts, UDP_PORT };
